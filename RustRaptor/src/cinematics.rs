//! Checked original AGX cinematic deltas and a platform-independent 70 Hz player.
//! MDS catalog files are RIFF MIDI streams; they are not the movie format.
use crate::{
    assets::{Catalog, Sprite},
    simulation::{LegacyRng, SoundEvent},
    sound::SoundBank,
};
use anyhow::{Context, Result, ensure};

#[derive(Debug, Clone)]
pub struct DeltaFrame {
    fill: Option<u8>,
    spans: Vec<(usize, Vec<u8>)>,
}
impl DeltaFrame {
    pub fn decode(bytes: &[u8], first: bool) -> Result<Self> {
        let fill = if first {
            Some(*bytes.first().context("missing cinematic fill byte")?)
        } else {
            None
        };
        let mut offset = usize::from(first);
        let mut spans = Vec::new();
        loop {
            let header = bytes
                .get(offset..offset + 8)
                .context("truncated AGX span header")?;
            offset += 8;
            let read = |n: usize| u16::from_le_bytes([header[n], header[n + 1]]) as usize;
            if read(0) == 0 {
                break;
            }
            let position = read(4);
            let length = read(6);
            ensure!(
                length > 0
                    && position
                        .checked_add(length)
                        .is_some_and(|end| end <= 320 * 200),
                "AGX span exceeds 320x200 canvas"
            );
            let pixels = bytes
                .get(offset..offset + length)
                .context("truncated AGX span pixels")?;
            offset += length;
            spans.push((position, pixels.to_vec()));
            ensure!(spans.len() <= 64000, "too many AGX spans");
        }
        Ok(Self { fill, spans })
    }
    pub fn apply(&self, canvas: &mut Sprite) -> Result<()> {
        ensure!(
            canvas.width == 320 && canvas.height == 200 && canvas.pixels.len() == 64000,
            "AGX requires original 320x200 canvas"
        );
        if let Some(fill) = self.fill {
            canvas.pixels.fill(fill as u16);
        }
        for (start, pixels) in &self.spans {
            for (destination, source) in canvas.pixels[*start..*start + pixels.len()]
                .iter_mut()
                .zip(pixels)
            {
                *destination = *source as u16;
            }
        }
        Ok(())
    }
}
#[derive(Debug, Clone, Copy)]
pub enum Kind {
    Intro,
    OpeningCredits,
    Landing,
    Death,
    CampaignEnd(u8),
}
#[derive(Clone)]
struct ClipSpec {
    name: &'static str,
    count: u32,
    dwell: u32,
    repeats: u32,
    fade_in: u32,
    fade_out: u32,
    fade_color: [u8; 3],
    background: Option<&'static str>,
    picture_palette: Option<&'static str>,
    discard_last_frame: bool,
}
fn clip(name: &'static str, count: u32, dwell: u32, repeats: u32) -> ClipSpec {
    ClipSpec {
        name,
        count,
        dwell,
        repeats,
        fade_in: 0,
        fade_out: 0,
        fade_color: [0; 3],
        background: None,
        picture_palette: None,
        discard_last_frame: false,
    }
}
fn movie_clip(name: &'static str, count: u32, frame_rate: u32, repeats: u32) -> ClipSpec {
    // Native GFX_WaitUpdate takes frames per second, then waits integer
    // 70 / frame_rate service ticks. It does not take a dwell in ticks.
    clip(name, count, 70 / frame_rate.clamp(1, 70), repeats)
}
fn specs(kind: Kind) -> Vec<ClipSpec> {
    match kind {
        Kind::OpeningCredits => {
            let mut apogee = clip("APOGEE_PIC", 1, 120, 1);
            apogee.fade_in = 64;
            apogee.fade_out = 63;
            apogee.picture_palette = Some("POGPAL_DAT");
            let mut cygnus = clip("CYGNUS_PIC", 1, 195, 1);
            cygnus.fade_in = 64;
            cygnus.fade_out = 63;
            cygnus.picture_palette = Some("CYGPAL_DAT");
            vec![apogee, cygnus]
        }
        Kind::Intro => {
            let mut city = movie_clip("CHASE_AGX", 30, 8, 1);
            city.fade_in = 128;
            let mut side = movie_clip("SHIPSD1_AGX", 20, 18, 2);
            side.background = Some("FX_JETSND");
            let mut pilot = movie_clip("PILOT_AGX", 21, 10, 1);
            pilot.background = Some("FX_IJETSND");
            let mut side_before_fire = side.clone();
            side_before_fire.repeats = 1;
            // MOVIE_Play stops the prelude's background patch. The firing
            // half of INTRO_Side2 does not start that patch again.
            let firing = movie_clip("SHIPSD2_AGX", 20, 18, 1);
            let mut explosion = movie_clip("EXPLO_AGX", 22, 12, 1);
            explosion.background = Some("FX_EJETSND");
            explosion.fade_out = 60;
            explosion.fade_color = [255, 113, 12];
            vec![city, side, pilot, side_before_fire, firing, explosion]
        }
        Kind::Landing => {
            let mut landing = movie_clip("LANDING_AGX", 33, 10, 1);
            landing.fade_out = 64;
            // The native last FRAME starts with M_FADEOUT, which fades the
            // previously displayed frame and never renders its own delta.
            landing.discard_last_frame = true;
            vec![landing]
        }
        Kind::Death => {
            let mut ground = movie_clip("SDEATH_AGX", 6, 3, 8);
            ground.fade_out = 100;
            vec![movie_clip("DOWN_AGX", 30, 11, 1), ground]
        }
        Kind::CampaignEnd(sector) => {
            let mut ending = match sector {
                0 => movie_clip("GAME1END_AGX", 5, 4, 8),
                1 => movie_clip("GAME2END_AGX", 25, 4, 1),
                _ => movie_clip("GAME3END_AGX", 39, 8, 1),
            };
            ending.fade_out = 120;
            if sector >= 2 {
                ending.background = Some("FX_JETSND");
            }
            let mut base = movie_clip("BASE_AGX", 30, 10, 1);
            base.fade_in = 128;
            let mut clips = vec![ending, base];
            clips.extend(specs(Kind::Landing));
            clips
        }
    }
}
struct Clip {
    spec: ClipSpec,
    frames: Vec<DeltaFrame>,
    background: Option<(SoundEvent, u64)>,
    palette: Option<[[u8; 3]; 256]>,
}
#[derive(Clone, Copy)]
enum Phase {
    FadeIn(u32),
    Frame(u32),
    FadeOut(u32),
    Finished,
}
#[derive(Debug, Clone)]
pub enum CinematicAudioEvent {
    Play(SoundEvent),
    Stop(u32),
}
pub struct Cinematic {
    pub image: Sprite,
    /// Ordered patches and stops; draining two separate queues would reorder
    /// an outgoing clip's stop after the next clip starts the same patch.
    pub audio_events: Vec<CinematicAudioEvent>,
    pub music_events: Vec<(&'static str, bool)>,
    clips: Vec<Clip>,
    current: usize,
    frame: usize,
    repetition: u32,
    phase: Phase,
    clock: u64,
    ticks: u64,
    background_at: u64,
    rng: LegacyRng,
}
impl Cinematic {
    pub fn load(catalog: &Catalog, kind: Kind) -> Result<Self> {
        let mut clips = Vec::new();
        let mut total = 0_usize;
        let mut sound_bank = SoundBank::default();
        for mut spec in specs(kind) {
            let start = catalog.id(spec.name)?;
            let mut frames = Vec::new();
            let palette = if let Some(name) = spec.picture_palette {
                let picture = Sprite::decode(&catalog.named(spec.name)?)?;
                ensure!(
                    picture.width == 320 && picture.height == 200,
                    "opening logo requires 320x200 canvas"
                );
                let pixels = picture
                    .pixels
                    .into_iter()
                    .map(|p| p.min(255) as u8)
                    .collect();
                frames.push(DeltaFrame {
                    fill: Some(0),
                    spans: vec![(0, pixels)],
                });
                if spec.name == "APOGEE_PIC" {
                    let score = crate::audio::MusScore::decode(&catalog.named("APOGEE_MUS")?)?;
                    spec.dwell = score
                        .groups
                        .last()
                        .map_or(120, |(tick, _)| (*tick + 1).max(120));
                }
                Some(crate::assets::decode_palette(&catalog.named(name)?)?)
            } else {
                for index in 0..spec.count {
                    let bytes = catalog.read(start + index)?;
                    total += bytes.len();
                    ensure!(total <= 32 * 1024 * 1024, "cinematic exceeds 32 MiB");
                    frames.push(
                        DeltaFrame::decode(&bytes, index == 0)
                            .with_context(|| format!("{} frame {}", spec.name, index))?,
                    );
                }
                None
            };
            if spec.discard_last_frame {
                frames.pop();
            }
            let background = if let Some(name) = spec.background {
                let event = sound(name, 127, &mut LegacyRng::new(0))
                    .with_context(|| format!("unknown cinematic background sound {name}"))?;
                // FX IDs are zero-byte catalog markers; the sound bank
                // resolves their +4 digital device variants.
                let sample = sound_bank.original(catalog, event.asset)?;
                let ticks = sample.duration_ticks(event.pitch, 70).max(1);
                Some((event, ticks))
            } else {
                None
            };
            clips.push(Clip {
                spec,
                frames,
                background,
                palette,
            });
        }
        let mut result = Self {
            image: Sprite::blank(320, 200),
            audio_events: Vec::new(),
            music_events: Vec::new(),
            clips,
            current: 0,
            frame: 0,
            repetition: 0,
            phase: Phase::Finished,
            clock: 0,
            ticks: 0,
            background_at: 0,
            rng: LegacyRng::new(0),
        };
        result.begin()?;
        Ok(result)
    }
    fn begin(&mut self) -> Result<()> {
        if self.current == self.clips.len() {
            self.phase = Phase::Finished;
            return Ok(());
        }
        self.frame = 0;
        self.repetition = 0;
        self.clips[self.current].frames[0].apply(&mut self.image)?;
        let spec = &self.clips[self.current].spec;
        self.phase = if spec.fade_in > 0 {
            Phase::FadeIn(spec.fade_in)
        } else {
            Phase::Frame(spec.dwell)
        };
        if let Some((event, period)) = &self.clips[self.current].background {
            self.audio_events
                .push(CinematicAudioEvent::Play(event.clone()));
            self.background_at = self.ticks + period;
        }
        Ok(())
    }
    fn end_clip(&mut self) {
        let clip = &self.clips[self.current];
        if let Some((event, _)) = &clip.background {
            self.audio_events
                .push(CinematicAudioEvent::Stop(event.asset));
        }
        match clip.spec.name {
            "CHASE_AGX" => self.audio_events.push(CinematicAudioEvent::Stop(129)),
            "SHIPSD2_AGX" => self.audio_events.push(CinematicAudioEvent::Stop(144)),
            _ => {}
        }
    }
    fn frame_sound(&mut self) {
        let name = self.clips[self.current].spec.name;
        let sound_name = match name {
            "CHASE_AGX" if self.frame == 4 || self.frame == 9 => Some("FX_FLYBY"),
            "SHIPSD2_AGX" if self.frame > 1 => Some("FX_INTROGUN"),
            "EXPLO_AGX" if self.frame == 21 || self.frame >= 8 && self.frame % 2 == 1 => {
                Some("FX_AIREXPLO")
            }
            "EXPLO_AGX" if (2..10).contains(&self.frame) => Some("FX_INTROHIT"),
            "GAME2END_AGX" if self.frame == 22 || self.frame == 24 => Some("FX_AIREXPLO"),
            "GAME3END_AGX" if self.frame == 30 || self.frame == 32 => Some("FX_AIREXPLO"),
            _ => None,
        };
        let pan = match (name, self.frame) {
            ("CHASE_AGX", 4) => 210,
            ("CHASE_AGX", 9) => 100,
            ("GAME3END_AGX", _) => 100,
            ("EXPLO_AGX", frame) if (2..10).contains(&frame) => 110 + self.rng.next_value() % 40,
            _ => 127,
        };
        if let Some(event) = sound_name.and_then(|name| sound(name, pan, &mut self.rng)) {
            self.audio_events.push(CinematicAudioEvent::Play(event));
        }
    }
    pub fn advance(&mut self, nanos: u64) -> Result<()> {
        self.clock = self.clock.saturating_add(nanos.min(1_000_000_000) * 70);
        while self.clock >= 1_000_000_000 && !self.finished() {
            self.clock -= 1_000_000_000;
            self.ticks += 1;
            if let Some((event, period)) = &self.clips[self.current].background {
                if self.ticks >= self.background_at {
                    self.audio_events
                        .push(CinematicAudioEvent::Play(event.clone()));
                    self.background_at = self.ticks + period;
                }
            }
            match self.phase {
                Phase::FadeIn(n) if n > 1 => self.phase = Phase::FadeIn(n - 1),
                Phase::FadeIn(_) => {
                    let spec = &self.clips[self.current].spec;
                    if spec.name == "APOGEE_PIC" {
                        self.music_events.push(("APOGEE_MUS", false));
                    }
                    self.phase = Phase::Frame(spec.dwell);
                }
                Phase::Frame(n) if n > 1 => {
                    let spec = &self.clips[self.current].spec;
                    if spec.name == "CYGNUS_PIC" {
                        let elapsed = spec.dwell - n + 1;
                        if elapsed == 3 || elapsed == 120 {
                            if let Some(event) = sound("FX_BOSS1", 127, &mut self.rng) {
                                self.audio_events.push(CinematicAudioEvent::Play(event));
                            }
                        }
                        if elapsed == 135 {
                            self.music_events.push(("RINTRO_MUS", true));
                        }
                    }
                    self.phase = Phase::Frame(n - 1);
                }
                Phase::Frame(_) => {
                    // MOVIE_Play dispatches a frame's patch after its timed
                    // display, before processing the frame's final fade.
                    self.frame_sound();
                    if self.frame + 1 < self.clips[self.current].frames.len() {
                        self.frame += 1;
                    } else if self.repetition + 1 < self.clips[self.current].spec.repeats {
                        self.repetition += 1;
                        self.frame = 0;
                    } else {
                        let fade = self.clips[self.current].spec.fade_out;
                        if fade > 0 {
                            self.phase = Phase::FadeOut(fade);
                        } else {
                            self.end_clip();
                            self.current += 1;
                            self.begin()?;
                        }
                        continue;
                    }
                    self.clips[self.current].frames[self.frame].apply(&mut self.image)?;
                    self.phase = Phase::Frame(self.clips[self.current].spec.dwell);
                }
                Phase::FadeOut(n) if n > 1 => self.phase = Phase::FadeOut(n - 1),
                Phase::FadeOut(_) => {
                    self.end_clip();
                    self.current += 1;
                    self.begin()?;
                }
                Phase::Finished => {}
            }
        }
        Ok(())
    }
    pub fn finished(&self) -> bool {
        matches!(self.phase, Phase::Finished)
    }
    pub fn palette(&self, base: &[[u8; 3]; 256]) -> [[u8; 3]; 256] {
        let base = self
            .clips
            .get(self.current)
            .and_then(|clip| clip.palette.as_ref())
            .unwrap_or(base);
        let (progress, total, target) = match self.phase {
            Phase::FadeIn(remaining) => {
                let total = self.clips[self.current].spec.fade_in;
                (total - remaining, total, [0; 3])
            }
            Phase::FadeOut(remaining) => {
                let spec = &self.clips[self.current].spec;
                (remaining, spec.fade_out, spec.fade_color)
            }
            _ => return *base,
        };
        std::array::from_fn(|i| {
            std::array::from_fn(|j| {
                ((base[i][j] as u32 * progress + target[j] as u32 * (total - progress))
                    / total.max(1)) as u8
            })
        })
    }
}
fn sound(name: &str, pan: i32, rng: &mut LegacyRng) -> Option<SoundEvent> {
    let definition = crate::legacy_tables::sounds()
        .into_iter()
        .find(|sound| sound.name == name)?;
    let pitch = definition.pitch
        + if definition.random {
            rng.next_value() % 40 - 20
        } else {
            0
        };
    Some(SoundEvent {
        asset: definition.asset,
        pan,
        pitch,
        volume: definition.volume,
        priority: definition.priority,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    fn synthetic_player(specs: Vec<ClipSpec>) -> Cinematic {
        let clips = specs
            .into_iter()
            .map(|spec| {
                let count = spec.count - u32::from(spec.discard_last_frame);
                let frames = (0..count)
                    .map(|frame| {
                        DeltaFrame::decode(&delta(frame == 0, 0, &[(frame + 1) as u8]), frame == 0)
                            .unwrap()
                    })
                    .collect();
                let palette = spec.picture_palette.map(|_| [[80, 120, 200]; 256]);
                Clip {
                    spec,
                    frames,
                    background: None,
                    palette,
                }
            })
            .collect();
        let mut player = Cinematic {
            image: Sprite::blank(320, 200),
            audio_events: vec![],
            music_events: vec![],
            clips,
            current: 0,
            frame: 0,
            repetition: 0,
            phase: Phase::Finished,
            clock: 0,
            ticks: 0,
            background_at: 0,
            rng: LegacyRng::new(0),
        };
        player.begin().unwrap();
        player
    }
    fn drain_patches(player: &mut Cinematic) -> impl Iterator<Item = SoundEvent> + use<> {
        std::mem::take(&mut player.audio_events)
            .into_iter()
            .filter_map(|event| match event {
                CinematicAudioEvent::Play(event) => Some(event),
                CinematicAudioEvent::Stop(_) => None,
            })
    }
    fn tick(player: &mut Cinematic) {
        // Round upward by less than a nanosecond so each call services one
        // 70 Hz tick, without losing a tick to integer division.
        player.advance(1_000_000_000_u64.div_ceil(70)).unwrap();
    }
    fn delta(first: bool, offset: u16, pixels: &[u8]) -> Vec<u8> {
        let mut bytes = if first { vec![5] } else { vec![] };
        for value in [1_u16, 0, offset, pixels.len() as u16] {
            bytes.extend(value.to_le_bytes());
        }
        bytes.extend(pixels);
        bytes.extend([0; 8]);
        bytes
    }
    #[test]
    fn deltas_preserve_unchanged_pixels_and_initial_fill() {
        let mut canvas = Sprite::blank(320, 200);
        DeltaFrame::decode(&delta(true, 4, &[1, 2, 3]), true)
            .unwrap()
            .apply(&mut canvas)
            .unwrap();
        assert_eq!(&canvas.pixels[..8], &[5, 5, 5, 5, 1, 2, 3, 5]);
        DeltaFrame::decode(&delta(false, 5, &[9]), false)
            .unwrap()
            .apply(&mut canvas)
            .unwrap();
        assert_eq!(&canvas.pixels[4..8], &[1, 9, 3, 5]);
    }
    #[test]
    fn malformed_delta_cannot_write_outside_canvas() {
        assert!(DeltaFrame::decode(&delta(false, 63999, &[1, 2]), false).is_err());
        let valid = delta(false, 5, &[1, 2]);
        for length in 0..valid.len() - 8 {
            assert!(DeltaFrame::decode(&valid[..length], false).is_err());
        }
    }
    #[test]
    fn player_timing_is_independent_of_render_rate() {
        fn player() -> Cinematic {
            let frames = vec![
                DeltaFrame::decode(&delta(true, 0, &[1]), true).unwrap(),
                DeltaFrame::decode(&delta(false, 0, &[2]), false).unwrap(),
            ];
            let mut p = Cinematic {
                image: Sprite::blank(320, 200),
                audio_events: vec![],
                music_events: vec![],
                clips: vec![Clip {
                    spec: clip("fixture", 2, 8, 2),
                    frames,
                    background: None,
                    palette: None,
                }],
                current: 0,
                frame: 0,
                repetition: 0,
                phase: Phase::Finished,
                clock: 0,
                ticks: 0,
                background_at: 0,
                rng: LegacyRng::new(0),
            };
            p.begin().unwrap();
            p
        }
        let mut a = player();
        let mut b = player();
        a.advance(300_000_000).unwrap();
        for _ in 0..30 {
            b.advance(10_000_000).unwrap();
        }
        assert_eq!(a.image, b.image);
        assert_eq!(a.frame, b.frame);
        assert_eq!(a.repetition, b.repetition);
        assert_eq!(a.ticks, b.ticks);
    }
    #[test]
    fn original_movie_rates_and_frame_cues_follow_native_wait_update() {
        let expected = [
            (Kind::Intro, 925),
            (Kind::Landing, 288),
            (Kind::Death, 1384),
            (Kind::CampaignEnd(0), 1426),
            (Kind::CampaignEnd(1), 1171),
            (Kind::CampaignEnd(2), 1058),
        ];
        for (kind, ticks) in expected {
            let mut movie = synthetic_player(specs(kind));
            while !movie.finished() {
                tick(&mut movie);
            }
            assert_eq!(movie.ticks, ticks, "{kind:?}");
        }
        let mut movie = synthetic_player(specs(Kind::Intro));
        let mut cues = Vec::new();
        while !movie.finished() {
            tick(&mut movie);
            for event in drain_patches(&mut movie) {
                cues.push((movie.ticks, event.asset, event.pan));
            }
        }
        assert_eq!(&cues[..2], &[(168, 129, 210), (208, 129, 100)]);
        assert_eq!(cues[2], (704, 144, 127));
        assert_eq!(cues[19], (755, 144, 127));
        assert_eq!(cues[20].0, 770);
        assert!((110..150).contains(&cues[20].2));
        assert_eq!(cues.last(), Some(&(865, 104, 127)));
        assert!(specs(Kind::Intro)[4].background.is_none());
    }
    #[test]
    fn background_stop_precedes_the_next_clip_play_even_in_a_batched_advance() {
        let mut movie = synthetic_player(vec![clip("first", 1, 2, 1), clip("second", 1, 2, 1)]);
        for clip in &mut movie.clips {
            clip.background = Some((
                sound("FX_JETSND", 127, &mut LegacyRng::new(0)).unwrap(),
                100,
            ));
        }
        movie.begin().unwrap();
        movie.advance(100_000_000).unwrap();
        let commands: Vec<_> = std::mem::take(&mut movie.audio_events)
            .into_iter()
            .map(|event| match event {
                CinematicAudioEvent::Play(event) => ("play", event.asset),
                CinematicAudioEvent::Stop(asset) => ("stop", asset),
            })
            .collect();
        assert_eq!(
            commands,
            [("play", 149), ("stop", 149), ("play", 149), ("stop", 149)]
        );
        assert!(movie.finished());
    }
    #[test]
    fn opening_logos_have_their_own_palettes_and_native_music_cue_times() {
        let mut movie = synthetic_player(specs(Kind::OpeningCredits));
        let base = [[240, 20, 16]; 256];
        assert_eq!(movie.palette(&base), [[0; 3]; 256]);
        let mut music = Vec::new();
        let mut patches = Vec::new();
        while !movie.finished() {
            tick(&mut movie);
            match movie.ticks {
                32 => assert_eq!(movie.palette(&base), [[40, 60, 100]; 256]),
                64 | 311 => assert_eq!(movie.palette(&base), [[80, 120, 200]; 256]),
                247 => assert_eq!(movie.palette(&base), [[0; 3]; 256]),
                _ => {}
            }
            for event in std::mem::take(&mut movie.music_events) {
                music.push((movie.ticks, event));
            }
            for event in drain_patches(&mut movie) {
                patches.push((movie.ticks, event.asset));
            }
        }
        assert_eq!(movie.ticks, 569);
        assert_eq!(
            music,
            [(64, ("APOGEE_MUS", false)), (446, ("RINTRO_MUS", true))]
        );
        assert_eq!(patches, [(314, 179), (431, 179)]);
        assert_eq!(movie.palette(&base), base);
    }
    #[test]
    #[ignore = "requires original local game assets"]
    fn original_opening_palettes_and_complete_intro_timeline_are_preserved() {
        let root = std::env::var("RAPTOR_TEST_DATA")
            .expect("set RAPTOR_TEST_DATA to the original asset directory");
        let catalog = Catalog::open(root).unwrap();
        let apogee_palette =
            crate::assets::decode_palette(&catalog.named("POGPAL_DAT").unwrap()).unwrap();
        let cygnus_palette =
            crate::assets::decode_palette(&catalog.named("CYGPAL_DAT").unwrap()).unwrap();
        let mut movie = Cinematic::load(&catalog, Kind::OpeningCredits).unwrap();
        let mut music = Vec::new();
        let mut patches = Vec::new();
        while !movie.finished() {
            tick(&mut movie);
            match movie.ticks {
                64 => assert_eq!(movie.palette(&catalog.palette().unwrap()), apogee_palette),
                708 => assert_eq!(movie.palette(&catalog.palette().unwrap()), cygnus_palette),
                _ => {}
            }
            for event in std::mem::take(&mut movie.music_events) {
                music.push((movie.ticks, event));
            }
            for event in drain_patches(&mut movie) {
                patches.push((movie.ticks, event.asset));
            }
        }
        assert_eq!(movie.ticks, 966);
        assert_eq!(
            music,
            [(64, ("APOGEE_MUS", false)), (843, ("RINTRO_MUS", true))]
        );
        assert_eq!(patches, [(711, 179), (828, 179)]);
        let mut intro = Cinematic::load(&catalog, Kind::Intro).unwrap();
        for index in [1, 2, 3, 5] {
            let (event, period) = intro.clips[index].background.as_ref().unwrap();
            assert_eq!(event.asset, 149);
            assert!(*period > 0);
        }
        assert!(intro.clips[4].background.is_none());
        let mut cues = Vec::new();
        while !intro.finished() {
            tick(&mut intro);
            for event in drain_patches(&mut intro) {
                if event.asset != 149 {
                    cues.push((intro.ticks, event.asset, event.pan));
                }
            }
        }
        assert_eq!(intro.ticks, 925);
        assert_eq!(&cues[..2], &[(168, 129, 210), (208, 129, 100)]);
        assert_eq!(cues.last(), Some(&(865, 104, 127)));
        assert!(intro.music_events.is_empty());
    }
    #[test]
    #[ignore = "requires original local game assets"]
    fn all_original_cinematic_sequences_decode() {
        let root = std::env::var("RAPTOR_TEST_DATA")
            .expect("set RAPTOR_TEST_DATA to the original asset directory");
        let catalog = Catalog::open(root).unwrap();
        for kind in [
            Kind::OpeningCredits,
            Kind::Intro,
            Kind::Landing,
            Kind::Death,
            Kind::CampaignEnd(0),
            Kind::CampaignEnd(1),
            Kind::CampaignEnd(2),
        ] {
            let mut movie = Cinematic::load(&catalog, kind).unwrap();
            while !movie.finished() {
                movie.advance(1_000_000_000).unwrap();
            }
        }
    }
}
