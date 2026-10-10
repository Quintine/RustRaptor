//! Checked original AGX cinematic deltas and a platform-independent 70 Hz player.
//! MDS catalog files are RIFF MIDI streams; they are not the movie format.
use crate::{
    assets::{Catalog, Sprite},
    audio::DigitalSample,
    simulation::{LegacyRng, SoundEvent},
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
    }
}
fn specs(kind: Kind) -> Vec<ClipSpec> {
    match kind {
        Kind::Intro => {
            let mut city = clip("CHASE_AGX", 30, 8, 1);
            city.fade_in = 128;
            let mut side = clip("SHIPSD1_AGX", 20, 18, 2);
            side.background = Some("FX_JETSND");
            let mut pilot = clip("PILOT_AGX", 21, 10, 1);
            pilot.background = Some("FX_IJETSND");
            let mut side_before_fire = side.clone();
            side_before_fire.repeats = 1;
            let mut firing = clip("SHIPSD2_AGX", 20, 18, 1);
            firing.background = Some("FX_JETSND");
            let mut explosion = clip("EXPLO_AGX", 22, 12, 1);
            explosion.background = Some("FX_EJETSND");
            explosion.fade_out = 60;
            explosion.fade_color = [255, 113, 12];
            vec![city, side, pilot, side_before_fire, firing, explosion]
        }
        Kind::Landing => {
            let mut landing = clip("LANDING_AGX", 33, 10, 1);
            landing.fade_out = 64;
            vec![landing]
        }
        Kind::Death => {
            let mut ground = clip("SDEATH_AGX", 6, 3, 8);
            ground.fade_out = 100;
            vec![clip("DOWN_AGX", 30, 11, 1), ground]
        }
        Kind::CampaignEnd(sector) => {
            let mut ending = match sector {
                0 => clip("GAME1END_AGX", 5, 4, 8),
                1 => clip("GAME2END_AGX", 25, 4, 1),
                _ => clip("GAME3END_AGX", 39, 8, 1),
            };
            ending.fade_out = 120;
            if sector >= 2 {
                ending.background = Some("FX_JETSND");
            }
            let mut base = clip("BASE_AGX", 30, 10, 1);
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
}
#[derive(Clone, Copy)]
enum Phase {
    FadeIn(u32),
    Frame(u32),
    FadeOut(u32),
    Finished,
}
pub struct Cinematic {
    pub image: Sprite,
    pub sounds: Vec<SoundEvent>,
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
        for spec in specs(kind) {
            let start = catalog.id(spec.name)?;
            let mut frames = Vec::new();
            for index in 0..spec.count {
                let bytes = catalog.read(start + index)?;
                total += bytes.len();
                ensure!(total <= 32 * 1024 * 1024, "cinematic exceeds 32 MiB");
                frames.push(
                    DeltaFrame::decode(&bytes, index == 0)
                        .with_context(|| format!("{} frame {}", spec.name, index))?,
                );
            }
            let background = spec
                .background
                .and_then(|name| sound(name, 127, &mut LegacyRng::new(0)))
                .and_then(|event| {
                    let sample = catalog
                        .read(event.asset)
                        .and_then(|b| DigitalSample::decode(&b))
                        .ok()?;
                    let ticks = (sample.data.len() as u64 * 70 * 128)
                        .div_ceil(sample.rate as u64 * event.pitch.clamp(1, 255) as u64)
                        .max(1);
                    Some((event, ticks))
                });
            clips.push(Clip {
                spec,
                frames,
                background,
            });
        }
        let mut result = Self {
            image: Sprite::blank(320, 200),
            sounds: Vec::new(),
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
        self.background_at = self.ticks;
        self.frame_sound();
        Ok(())
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
            ("EXPLO_AGX", _) => 110 + self.rng.next_value() % 40,
            _ => 127,
        };
        if let Some(event) = sound_name.and_then(|name| sound(name, pan, &mut self.rng)) {
            self.sounds.push(event);
        }
    }
    pub fn advance(&mut self, nanos: u64) -> Result<()> {
        self.clock = self.clock.saturating_add(nanos.min(1_000_000_000) * 70);
        while self.clock >= 1_000_000_000 && !self.finished() {
            self.clock -= 1_000_000_000;
            self.ticks += 1;
            if let Some((event, period)) = &self.clips[self.current].background {
                if self.ticks >= self.background_at {
                    self.sounds.push(event.clone());
                    self.background_at = self.ticks + period;
                }
            }
            match self.phase {
                Phase::FadeIn(n) if n > 1 => self.phase = Phase::FadeIn(n - 1),
                Phase::FadeIn(_) => self.phase = Phase::Frame(self.clips[self.current].spec.dwell),
                Phase::Frame(n) if n > 1 => self.phase = Phase::Frame(n - 1),
                Phase::Frame(_) => {
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
                            self.current += 1;
                            self.begin()?;
                        }
                        continue;
                    }
                    self.clips[self.current].frames[self.frame].apply(&mut self.image)?;
                    self.phase = Phase::Frame(self.clips[self.current].spec.dwell);
                    self.frame_sound();
                }
                Phase::FadeOut(n) if n > 1 => self.phase = Phase::FadeOut(n - 1),
                Phase::FadeOut(_) => {
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
                sounds: vec![],
                clips: vec![Clip {
                    spec: clip("fixture", 2, 8, 2),
                    frames,
                    background: None,
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
    #[ignore = "requires original local game assets"]
    fn all_original_cinematic_sequences_decode() {
        let root = std::env::var("RAPTOR_TEST_DATA")
            .expect("set RAPTOR_TEST_DATA to the original asset directory");
        let catalog = Catalog::open(root).unwrap();
        for kind in [
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
