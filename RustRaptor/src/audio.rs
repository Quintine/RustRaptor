//! Checked MUS decoding, the original GENMIDI/OPL3 driver behavior and digital DSP mixing.
//!
//! Driver and DSP behavior is ported from the retained GPL-2.0-or-later sources.
//! The OPL driver credits Id Software (1993–1996) and Simon Howard (2005–2014).
use crate::assets::{i16_at, i32_at};
use anyhow::{Context, Result, bail, ensure};
mod opl3;
use opl3::Chip as Opl3Chip;
use std::collections::VecDeque;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum MusicEvent {
    Off(u8, u8),
    On(u8, u8, u8),
    OnInherited(u8, u8),
    Bend(u8, u8),
    System(u8, u8),
    Control(u8, u8, u8),
    End,
}
#[derive(Debug, Clone)]
pub struct MusScore {
    pub groups: Vec<(u32, Vec<MusicEvent>)>,
    pub channels: u8,
}
impl MusScore {
    pub fn decode(bytes: &[u8]) -> Result<Self> {
        ensure!(bytes.get(..4) == Some(b"MUS\x1a"), "invalid MUS signature");
        let length = i16_at(bytes, 4)? as u16 as usize;
        let start = i16_at(bytes, 6)? as u16 as usize;
        let channels = i16_at(bytes, 8)? as u16;
        let instruments = i16_at(bytes, 12)? as u16 as usize;
        ensure!(channels <= 15, "MUS has too many primary channels");
        ensure!(
            start >= 16 + instruments * 2
                && start.checked_add(length).is_some_and(|e| e <= bytes.len()),
            "MUS score range is invalid"
        );
        let data = &bytes[start..start + length];
        let mut p = 0usize;
        let mut tick = 0u32;
        let mut groups = Vec::new();
        let mut pending = Vec::new();
        let mut ended = false;
        let byte = |p: &mut usize| -> Result<u8> {
            let value = *data.get(*p).context("truncated MUS event")?;
            *p += 1;
            Ok(value)
        };
        while p < data.len() {
            let descriptor = byte(&mut p)?;
            let channel = descriptor & 15;
            let kind = (descriptor >> 4) & 7;
            let event = match kind {
                0 => MusicEvent::Off(channel, byte(&mut p)? & 127),
                1 => {
                    let key = byte(&mut p)?;
                    if key & 128 != 0 {
                        let velocity = byte(&mut p)?;
                        ensure!(velocity <= 127, "invalid MUS note velocity");
                        MusicEvent::On(channel, key & 127, velocity)
                    } else {
                        MusicEvent::OnInherited(channel, key)
                    }
                }
                2 => MusicEvent::Bend(channel, byte(&mut p)?),
                3 => {
                    let control = byte(&mut p)?;
                    ensure!((10..=14).contains(&control), "invalid MUS system event");
                    MusicEvent::System(channel, control)
                }
                4 => {
                    let control = byte(&mut p)?;
                    let value = byte(&mut p)?;
                    ensure!(
                        control <= 14 && value <= 127,
                        "invalid MUS controller event"
                    );
                    MusicEvent::Control(channel, control, value)
                }
                6 => MusicEvent::End,
                _ => bail!("unsupported MUS event {kind}"),
            };
            let end = matches!(event, MusicEvent::End);
            pending.push(event);
            if descriptor & 128 != 0 || end {
                groups.push((tick, std::mem::take(&mut pending)));
                if end {
                    ended = true;
                    break;
                }
                let mut delay = 0u32;
                for n in 0..5 {
                    let v = byte(&mut p)?;
                    delay = delay
                        .checked_mul(128)
                        .and_then(|x| x.checked_add((v & 127) as u32))
                        .context("MUS delay overflow")?;
                    if v & 128 == 0 {
                        break;
                    }
                    ensure!(n < 4, "MUS delay too long");
                }
                tick = tick.checked_add(delay).context("MUS time overflow")?;
            }
        }
        ensure!(ended, "MUS score has no end event");
        Ok(Self {
            groups,
            channels: channels as u8,
        })
    }
}
#[derive(Clone)]
struct Instrument {
    flags: u16,
    fixed: u8,
    fine: u8,
    voice: [[u8; 16]; 2],
}
#[derive(Clone, Copy, Default)]
struct Voice {
    channel: u8,
    key: u8,
    frequency: u16,
    velocity: u8,
    active: bool,
    instrument: usize,
    part: usize,
    note: i32,
    loaded: bool,
    car_volume: u8,
    mod_volume: u8,
}
#[derive(Clone, PartialEq, Eq)]
pub struct DigitalSample {
    pub rate: u32,
    pub data: Vec<u8>,
}
impl DigitalSample {
    pub fn decode(data: &[u8]) -> Result<Self> {
        ensure!(i16_at(data, 0)? == 3, "not a digital sound patch");
        let rate = i16_at(data, 2)? as u16 as u32;
        let length = i32_at(data, 4)?;
        ensure!(
            rate > 0 && length > 32 && length as usize <= data.len().saturating_sub(8),
            "invalid digital sound header"
        );
        // DMX patches include sixteen bytes of padding at each end.
        Ok(Self {
            rate,
            data: data[24..8 + length as usize - 16].to_vec(),
        })
    }
}
struct SampleVoice {
    sample: DigitalSample,
    position: usize,
    step: usize,
    fraction: usize,
    remaining: usize,
    left: [i16; 256],
    right: [i16; 256],
    priority: i32,
    volume: i32,
    pan: usize,
}
pub struct AudioCapture {
    pub rate: u32,
    pub samples: Vec<i16>,
    limit: usize,
}
struct Fade {
    level: i32,
    target: i32,
    add: i32,
    remainder: i32,
    steps: i32,
    accumulator: i32,
}
pub struct Mixer {
    chip: Opl3Chip,
    rate: u32,
    instruments: Vec<Instrument>,
    voices: [Voice; 18],
    free: VecDeque<usize>,
    allocated: Vec<usize>,
    pan: [u8; 16],
    program: [usize; 16],
    volume: [u8; 16],
    channel_volume: [u8; 16],
    velocity: [u8; 16],
    bend: [u8; 16],
    score: Option<MusScore>,
    group: usize,
    score_tick: u32,
    music_phase: u32,
    fader_phase: u32,
    last_volume: u8,
    fade: Option<Fade>,
    looping: bool,
    digital: [Option<SampleVoice>; 8],
    digital_channels: usize,
    digital_phase: u32,
    digital_hold: [i32; 2],
    pub music_volume: u8,
    pub fx_volume: u8,
    last_fx_volume: u8,
    capture: Option<AudioCapture>,
}
impl Mixer {
    pub fn new(rate: u32, genmidi: &[u8]) -> Result<Self> {
        ensure!(
            genmidi.get(..8) == Some(b"#OPL_II#") && genmidi.len() >= 8 + 175 * 36,
            "invalid GENMIDI instrument table"
        );
        ensure!((8000..=192000).contains(&rate), "invalid mixer sample rate");
        let instruments = genmidi[8..8 + 175 * 36]
            .chunks_exact(36)
            .map(|b| Instrument {
                flags: u16::from_le_bytes([b[0], b[1]]),
                fixed: b[3],
                fine: b[2],
                voice: [b[4..20].try_into().unwrap(), b[20..36].try_into().unwrap()],
            })
            .collect();
        let mut chip = Opl3Chip::new(rate);
        initialize_chip(&mut chip);
        Ok(Self {
            chip,
            rate,
            instruments,
            voices: [Voice::default(); 18],
            free: (0..18).collect(),
            allocated: vec![],
            pan: [0x30; 16],
            program: [0; 16],
            volume: [127; 16],
            channel_volume: [100; 16],
            velocity: [0; 16],
            bend: [128; 16],
            score: None,
            group: 0,
            score_tick: 0,
            music_phase: 0,
            fader_phase: 0,
            last_volume: 0,
            fade: None,
            looping: false,
            digital: std::array::from_fn(|_| None),
            digital_channels: 2,
            digital_phase: 0,
            digital_hold: [0; 2],
            music_volume: 85,
            fx_volume: 85,
            last_fx_volume: 85,
            capture: None,
        })
    }
    pub fn play(&mut self, score: MusScore, looping: bool) {
        self.play_with_fade(score, looping, false);
    }
    pub fn play_with_fade(&mut self, score: MusScore, looping: bool, fade_in: bool) {
        self.all_off();
        self.score = Some(score);
        self.looping = looping;
        self.group = 0;
        self.score_tick = 0;
        self.fade = None;
        self.reset_channels();
        if fade_in {
            self.fade = Some(make_fade(0, 127));
        }
    }
    pub fn stop(&mut self) {
        self.all_off();
        self.score = None;
        self.fade = None;
    }
    pub fn stop_with_fade(&mut self) {
        let level = self
            .fade
            .as_ref()
            .map_or(self.music_volume as i32, |f| f.level);
        if level == 0 {
            self.stop();
        } else {
            self.fade = Some(make_fade(level, 0));
        }
    }
    pub fn set_fx_channels(&mut self, count: usize) {
        self.digital_channels = count.clamp(1, 8);
        for slot in &mut self.digital[self.digital_channels..] {
            *slot = None;
        }
    }
    fn release(&mut self, n: usize) {
        self.chip
            .write_reg_buffered(register(0xb0, n), (self.voices[n].frequency >> 8) as u8);
        self.voices[n].active = false;
        self.allocated.retain(|v| *v != n);
        self.free.push_back(n);
    }
    fn all_off(&mut self) {
        for n in self.allocated.clone() {
            self.release(n);
        }
    }
    fn off(&mut self, channel: u8, key: u8) {
        for n in self.allocated.clone() {
            if self.voices[n].channel == channel && self.voices[n].key == key {
                self.release(n);
            }
        }
    }
    fn channel_off(&mut self, channel: u8) {
        for n in self.allocated.clone() {
            if self.voices[n].channel == channel {
                self.release(n);
            }
        }
    }
    fn reset_channels(&mut self) {
        self.channel_volume.fill(100);
        let channels = self.score.as_ref().map_or(15, |s| s.channels);
        for c in 0..16 {
            self.channel_off(c);
            if c < channels || c == 15 {
                self.bend[c as usize] = 128;
                self.pan[c as usize] = 0x30;
                self.set_channel_volume(
                    c,
                    100.min(self.music_volume.min(127)).min(self.fade_level()),
                );
            }
        }
    }
    fn on(&mut self, channel: u8, key: u8, velocity: u8) {
        if velocity == 0 {
            self.off(channel, key);
            return;
        }
        if channel == 15 && !(35..=81).contains(&key) {
            return;
        }
        let instrument = if channel == 15 {
            128 + (key - 35) as usize
        } else {
            self.program[channel as usize].min(127)
        };
        if self.free.is_empty() {
            let mut result = self.allocated[0];
            for &n in &self.allocated {
                if self.voices[n].part != 0 || self.voices[n].channel >= self.voices[result].channel
                {
                    result = n;
                }
            }
            self.release(result);
        }
        self.voice_on(channel, key, velocity, instrument, 0);
        if self.instruments[instrument].flags & 4 != 0 {
            self.voice_on(channel, key, velocity, instrument, 1);
        }
    }
    fn voice_on(&mut self, channel: u8, key: u8, velocity: u8, instrument: usize, part: usize) {
        let Some(n) = self.free.pop_front() else {
            return;
        };
        let ins = self.instruments[instrument].clone();
        let v = ins.voice[part];
        if !self.voices[n].loaded
            || self.voices[n].instrument != instrument
            || self.voices[n].part != part
        {
            let op = operator(n);
            let bank = (n as u16 / 9) << 8;
            for (offset, base) in [(3u16, 7usize), (0, 0)] {
                let level = v[base + 4]
                    | if base == 7 || v[6] & 1 != 0 {
                        63
                    } else {
                        v[base + 5]
                    };
                if base == 7 {
                    self.voices[n].car_volume = level;
                } else {
                    self.voices[n].mod_volume = level;
                }
                for (reg, value) in [
                    (0x40, level),
                    (0x20, v[base]),
                    (0x60, v[base + 1]),
                    (0x80, v[base + 2]),
                    (0xe0, v[base + 3]),
                ] {
                    self.chip
                        .write_reg_buffered((reg + op + offset) | bank, value);
                }
            }
            self.chip
                .write_reg_buffered(register(0xc0, n), v[6] | self.pan[channel as usize]);
        }
        let note = if ins.flags & 1 != 0 {
            ins.fixed as i32
        } else {
            (if channel == 15 { 60 } else { key as i32 })
                + i16::from_le_bytes([v[14], v[15]]) as i32
        };
        let old = self.voices[n];
        self.voices[n] = Voice {
            channel,
            key,
            frequency: 0,
            velocity,
            active: true,
            instrument,
            part,
            note,
            loaded: true,
            ..old
        };
        self.allocated.push(n);
        self.voice_volume(n);
        self.voice_frequency(n);
    }
    fn voice_volume(&mut self, n: usize) {
        let voice = self.voices[n];
        let v = self.instruments[voice.instrument].voice[voice.part];
        let midi = 2
            * (crate::legacy_tables::VOLUME_CURVE[self.volume[voice.channel as usize] as usize]
                + 1);
        let full = (crate::legacy_tables::VOLUME_CURVE[voice.velocity as usize] * midi) >> 9;
        let car = (63 - full) as u8;
        if car != voice.car_volume & 63 {
            let op = operator(n);
            let bank = (n as u16 / 9) << 8;
            self.voices[n].car_volume = (voice.car_volume & 192) | car;
            self.chip
                .write_reg_buffered((0x43 + op) | bank, self.voices[n].car_volume);
            if v[6] & 1 != 0 && v[5] != 63 {
                let level = (voice.mod_volume & 192) | v[5].max(car);
                if level != voice.mod_volume {
                    self.voices[n].mod_volume = level;
                    self.chip
                        .write_reg_buffered((0x40 + op) | bank, level | (v[4] & 192));
                }
            }
        }
    }
    fn voice_frequency(&mut self, n: usize) {
        let voice = self.voices[n];
        let ins = &self.instruments[voice.instrument];
        let fine = if voice.part != 0 {
            ins.fine as i32 / 2 - 64
        } else {
            0
        };
        let f = frequency(voice.note, self.bend[voice.channel as usize], fine);
        if f != voice.frequency {
            self.voices[n].frequency = f;
            self.chip.write_reg_buffered(register(0xa0, n), f as u8);
            self.chip
                .write_reg_buffered(register(0xb0, n), ((f >> 8) as u8) | 0x20);
        }
    }
    fn set_channel_volume(&mut self, c: u8, v: u8) {
        self.volume[c as usize] = v.min(127);
        // Preserve original physical voice iteration order, which affects buffered writes.
        for n in 0..18 {
            if self.voices[n].active && self.voices[n].channel == c {
                self.voice_volume(n);
            }
        }
    }
    fn event(&mut self, e: MusicEvent) {
        match e {
            MusicEvent::Off(c, k) => self.off(c, k),
            MusicEvent::On(c, k, v) => {
                self.velocity[c as usize] = v;
                self.on(c, k, v);
            }
            MusicEvent::OnInherited(c, k) => self.on(c, k, self.velocity[c as usize]),
            MusicEvent::Bend(c, b) => {
                self.bend[c as usize] = b;
                let (updated, others): (Vec<_>, Vec<_>) = self
                    .allocated
                    .iter()
                    .copied()
                    .partition(|n| self.voices[*n].channel == c);
                for &n in &updated {
                    self.voice_frequency(n);
                }
                self.allocated = others.into_iter().chain(updated).collect();
            }
            MusicEvent::System(c, 10 | 11 | 14) => {
                self.channel_off(c);
                if matches!(e, MusicEvent::System(_, 14)) {
                    self.bend[c as usize] = 128;
                    self.pan[c as usize] = 0x30;
                }
            }
            MusicEvent::Control(c, 0, p) => self.program[c as usize] = p.min(127) as usize,
            MusicEvent::Control(c, 3, v) => {
                self.channel_volume[c as usize] = v;
                self.set_channel_volume(
                    c,
                    v.min(self.music_volume.min(127)).min(self.fade_level()),
                );
            }
            MusicEvent::Control(c, 4, p) => {
                let pan = if p >= 96 {
                    0x10
                } else if p <= 48 {
                    0x20
                } else {
                    0x30
                };
                if self.pan[c as usize] != pan {
                    self.pan[c as usize] = pan;
                    for n in 0..18 {
                        let voice = self.voices[n];
                        if voice.active && voice.channel == c {
                            self.chip.write_reg_buffered(
                                register(0xc0, n),
                                self.instruments[voice.instrument].voice[voice.part][6] | pan,
                            );
                        }
                    }
                }
            }
            MusicEvent::Control(c, 10 | 11, _) => self.channel_off(c),
            MusicEvent::Control(c, 14, _) => {
                self.channel_off(c);
                self.set_channel_volume(
                    c,
                    self.velocity[c as usize]
                        .min(self.music_volume.min(127))
                        .min(self.fade_level()),
                );
            }
            _ => {}
        }
    }
    fn fade_level(&self) -> u8 {
        self.fade
            .as_ref()
            .map_or(127, |f| f.level.clamp(0, 127) as u8)
    }
    fn service_music(&mut self) {
        // Events are serviced at 70Hz after that output sample, matching MUS_Mix.
        let mut restarts = 0;
        loop {
            let group = self
                .score
                .as_ref()
                .and_then(|s| s.groups.get(self.group))
                .filter(|(time, _)| *time <= self.score_tick)
                .cloned();
            let Some((time, events)) = group else {
                break;
            };
            self.group += 1;
            for event in events {
                if matches!(event, MusicEvent::End) {
                    if self.looping && time > 0 && restarts == 0 {
                        self.group = 0;
                        self.score_tick = 0;
                        self.reset_channels();
                        restarts += 1;
                    } else {
                        self.score = None;
                    }
                } else {
                    self.event(event);
                }
            }
            if self.score.is_none() {
                break;
            }
        }
        self.score_tick = self.score_tick.saturating_add(1);
    }
    fn service_fader(&mut self) {
        let mut update = self.last_volume != self.music_volume;
        self.last_volume = self.music_volume;
        if let Some(f) = &mut self.fade {
            update = true;
            if f.level < self.music_volume as i32 || f.target < self.music_volume as i32 {
                let mut count = f.add;
                f.accumulator += f.remainder;
                if f.accumulator >= f.steps {
                    f.accumulator -= f.steps;
                    count += 1;
                }
                if f.target < f.level {
                    f.level = (f.level - count).max(0);
                } else {
                    f.level = (f.level + count)
                        .min(f.target)
                        .min(self.music_volume.min(127) as i32);
                }
            }
            if f.level == 0 && f.target == 0 {
                self.stop();
                return;
            }
            if f.level >= f.target && f.target != 0 {
                self.fade = None;
            } else if f.target != 0 && f.level >= self.music_volume.min(127) as i32 {
                self.fade = None;
            }
        }
        if update {
            let channels = self.score.as_ref().map_or(15, |s| s.channels);
            for c in 0..16 {
                if c < channels || c == 15 {
                    let v = self.music_volume.min(127).min(self.fade_level());
                    self.set_channel_volume(
                        c,
                        if c == 15 {
                            v
                        } else {
                            v.min(self.channel_volume[c as usize])
                        },
                    );
                }
            }
        }
    }
    pub fn sample(
        &mut self,
        sample: DigitalSample,
        pan: i32,
        pitch: i32,
        volume: i32,
        priority: i32,
    ) {
        if sample.data.is_empty() || sample.rate == 0 {
            return;
        }
        let pan = pan.clamp(0, 255) as usize;
        let step = ((DSP_PITCH[pitch.clamp(0, 255) as usize] as u64 * sample.rate as u64
            + 11025 / 2)
            / 11025)
            .max(1) as usize;
        let remaining = sample.data.len().saturating_mul(256) / step;
        if remaining == 0 {
            return;
        }
        let slot = if let Some(n) = self.digital[..self.digital_channels]
            .iter()
            .position(Option::is_none)
        {
            n
        } else {
            let mut lowest = 0;
            let mut fewest = usize::MAX;
            let mut best = 0;
            for (n, v) in self.digital[..self.digital_channels].iter().enumerate() {
                let v = v.as_ref().unwrap();
                if v.priority > lowest {
                    lowest = v.priority;
                    best = n;
                } else if v.priority == lowest && v.remaining < fewest {
                    fewest = v.remaining;
                    best = n;
                }
            }
            if lowest < priority || lowest == 0 {
                return;
            }
            if lowest == priority && self.digital[best].as_ref().unwrap().sample != sample {
                if let Some(n) = self.digital[..self.digital_channels]
                    .iter()
                    .position(|v| v.as_ref().is_some_and(|v| v.sample == sample))
                {
                    best = n;
                }
            }
            best
        };
        let event_volume = volume.clamp(0, 127);
        let volume = event_volume * self.fx_volume.min(127) as i32 / 127;
        let left = volume_table(DSP_PAN[255 - pan] as i32 * volume / 127);
        let right = volume_table(DSP_PAN[pan] as i32 * volume / 127);
        self.digital[slot] = Some(SampleVoice {
            sample,
            position: 0,
            step,
            fraction: (step & 255) >> 1,
            remaining,
            left,
            right,
            priority,
            volume: event_volume,
            pan,
        });
    }
    pub fn start_capture(&mut self, seconds: u32) -> Result<()> {
        ensure!(
            (1..=120).contains(&seconds),
            "capture duration must be 1–120 seconds"
        );
        let limit = self.rate as usize * seconds as usize * 2;
        self.capture = Some(AudioCapture {
            rate: self.rate,
            samples: Vec::with_capacity(limit),
            limit,
        });
        Ok(())
    }
    pub fn take_capture(&mut self) -> Option<AudioCapture> {
        self.capture.take()
    }
    fn refresh_fx_volume(&mut self) {
        let master = self.fx_volume.min(127);
        if master == self.last_fx_volume {
            return;
        }
        self.last_fx_volume = master;
        for voice in self.digital.iter_mut().flatten() {
            let volume = voice.volume * master as i32 / 127;
            voice.left = volume_table(DSP_PAN[255 - voice.pan] as i32 * volume / 127);
            voice.right = volume_table(DSP_PAN[voice.pan] as i32 * volume / 127);
        }
        // Muting must silence the held sample immediately, including a callback
        // beginning between two 11025 Hz digital service ticks.
        if master == 0 {
            self.digital_hold = [0; 2];
        }
    }
    fn service_digital(&mut self) {
        let mut sample = [0i32; 2];
        for slot in &mut self.digital[..self.digital_channels] {
            if let Some(v) = slot {
                if let Some(value) = v.sample.data.get(v.position) {
                    sample[0] += v.left[*value as usize] as i32;
                    sample[1] += v.right[*value as usize] as i32;
                }
                v.fraction += v.step & 255;
                let carry = usize::from(v.fraction >= 256);
                v.fraction &= 255;
                v.position = v.position.saturating_add((v.step >> 8) + carry);
                v.remaining -= 1;
                if v.remaining == 0 {
                    *slot = None;
                }
            }
        }
        self.digital_hold = sample.map(|v| v.clamp(-128, 127) * 128);
    }
    pub fn mix(&mut self, out: &mut [i16]) {
        self.refresh_fx_volume();
        // A partial stereo frame is explicitly silent, not leftover caller memory.
        out.fill(0);
        for frame in out.chunks_exact_mut(2) {
            let mut fm = [0i16; 2];
            self.chip.generate_resampled(&mut fm);
            // Maximum OPL attenuation still leaks a small signal. Keep the
            // score and synthesizer advancing while a user-selected mute
            // produces digital silence immediately.
            if self.music_volume == 0 {
                fm = [0; 2];
            }
            self.music_phase += 70;
            while self.music_phase >= self.rate {
                self.music_phase -= self.rate;
                self.service_music();
            }
            self.fader_phase += 50;
            while self.fader_phase >= self.rate {
                self.fader_phase -= self.rate;
                self.service_fader();
            }
            self.digital_phase += 11025;
            while self.digital_phase >= self.rate {
                self.digital_phase -= self.rate;
                self.service_digital();
            }
            frame[0] = (fm[0] as i32 + self.digital_hold[0]).clamp(-32768, 32767) as i16;
            frame[1] = (fm[1] as i32 + self.digital_hold[1]).clamp(-32768, 32767) as i16;
        }
        if let Some(capture) = &mut self.capture {
            let remaining = capture.limit.saturating_sub(capture.samples.len());
            let count = remaining.min(out.len()) & !1;
            capture.samples.extend_from_slice(&out[..count]);
        }
    }
}
fn make_fade(level: i32, target: i32) -> Fade {
    let steps = (target - level).abs();
    Fade {
        level,
        target,
        add: steps / 51,
        remainder: steps % 51,
        steps: steps.max(1),
        accumulator: -((steps % 51) >> 1),
    }
}
fn volume_table(volume: i32) -> [i16; 256] {
    let mut value = -(volume / 2);
    let step = volume >> 8;
    let sub = volume & 255;
    let mut accumulator = sub >> 1;
    std::array::from_fn(|_| {
        let out = value as i16;
        value += step;
        accumulator += sub;
        while accumulator >= 256 {
            value += 1;
            accumulator -= 256;
        }
        out
    })
}
fn initialize_chip(chip: &mut Opl3Chip) {
    for r in 0x40..=0x55 {
        chip.write_reg_buffered(r, 63);
    }
    for r in 0x60..=0xf5 {
        chip.write_reg_buffered(r, 0);
    }
    for r in 1..0x40 {
        chip.write_reg_buffered(r, 0);
    }
    chip.write_reg_buffered(4, 0x60);
    chip.write_reg_buffered(4, 0x80);
    chip.write_reg_buffered(1, 0x20);
    chip.write_reg_buffered(0x105, 1);
    for r in 0x40..=0x55 {
        chip.write_reg_buffered(r | 0x100, 63);
    }
    for r in 0x60..=0xf5 {
        chip.write_reg_buffered(r | 0x100, 0);
    }
    for r in 1..0x40 {
        chip.write_reg_buffered(r | 0x100, 0);
    }
    chip.write_reg_buffered(8, 0x40);
    chip.write_reg_buffered(0x105, 1);
}
fn register(reg: u16, n: usize) -> u16 {
    (reg + n as u16 % 9) | ((n as u16 / 9) << 8)
}
fn operator(n: usize) -> u16 {
    [0, 1, 2, 8, 9, 10, 16, 17, 18][n % 9]
}
fn frequency(mut note: i32, bend: u8, fine: i32) -> u16 {
    while note < 0 {
        note += 12;
    }
    while note > 95 {
        note -= 12;
    }
    let index = (64 + 32 * note + (bend as i32 / 2 - 64) + fine).max(0) as usize;
    if index < 284 {
        crate::legacy_tables::FREQUENCY_CURVE[index]
    } else {
        crate::legacy_tables::FREQUENCY_CURVE[(index - 284) % 384 + 284]
            | ((((index - 284) / 384).min(7) as u16) << 10)
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn truncated_scores_are_rejected() {
        for n in 0..16 {
            assert!(MusScore::decode(&vec![0; n]).is_err());
        }
    }
    #[test]
    fn simple_score() {
        let mut data = b"MUS\x1a".to_vec();
        data.extend([5, 0, 16, 0, 1, 0, 0, 0, 0, 0, 0, 0]);
        data.extend([0x90, 0x80 | 60, 100, 1, 0x60]);
        let s = MusScore::decode(&data).unwrap();
        assert_eq!(s.groups.len(), 2);
    }
    #[test]
    fn bad_digital_length() {
        assert!(DigitalSample::decode(&[3, 0, 68, 172, 99, 0, 0, 0, 128]).is_err());
    }
}

// Exact lookup values from the original digital mixer.
const DSP_PITCH: [u16; 256] = [
    0x0040, 0x0040, 0x0041, 0x0042, 0x0042, 0x0043, 0x0044, 0x0045, 0x0045, 0x0046, 0x0047, 0x0048,
    0x0048, 0x0049, 0x004A, 0x004B, 0x004C, 0x004C, 0x004D, 0x004E, 0x004F, 0x0050, 0x0051, 0x0052,
    0x0053, 0x0053, 0x0054, 0x0055, 0x0056, 0x0057, 0x0058, 0x0059, 0x005A, 0x005B, 0x005C, 0x005D,
    0x005E, 0x005F, 0x0060, 0x0061, 0x0062, 0x0063, 0x0064, 0x0066, 0x0067, 0x0068, 0x0069, 0x006A,
    0x006B, 0x006C, 0x006E, 0x006F, 0x0070, 0x0071, 0x0072, 0x0074, 0x0075, 0x0076, 0x0077, 0x0079,
    0x007A, 0x007B, 0x007D, 0x007E, 0x0080, 0x0081, 0x0082, 0x0084, 0x0085, 0x0087, 0x0088, 0x008A,
    0x008B, 0x008D, 0x008E, 0x0090, 0x0091, 0x0093, 0x0095, 0x0096, 0x0098, 0x0099, 0x009B, 0x009D,
    0x009F, 0x00A0, 0x00A2, 0x00A4, 0x00A6, 0x00A7, 0x00A9, 0x00AB, 0x00AD, 0x00AF, 0x00B1, 0x00B3,
    0x00B5, 0x00B7, 0x00B9, 0x00BB, 0x00BD, 0x00BF, 0x00C1, 0x00C3, 0x00C5, 0x00C7, 0x00C9, 0x00CB,
    0x00CE, 0x00D0, 0x00D2, 0x00D5, 0x00D7, 0x00D9, 0x00DC, 0x00DE, 0x00E0, 0x00E3, 0x00E5, 0x00E8,
    0x00EA, 0x00ED, 0x00EF, 0x00F2, 0x00F5, 0x00F7, 0x00FA, 0x00FD, 0x0100, 0x0102, 0x0105, 0x0108,
    0x010B, 0x010E, 0x0111, 0x0114, 0x0117, 0x011A, 0x011D, 0x0120, 0x0123, 0x0126, 0x0129, 0x012D,
    0x0130, 0x0133, 0x0137, 0x013A, 0x013D, 0x0141, 0x0144, 0x0148, 0x014C, 0x014F, 0x0153, 0x0157,
    0x015A, 0x015E, 0x0162, 0x0166, 0x016A, 0x016E, 0x0172, 0x0176, 0x017A, 0x017E, 0x0182, 0x0186,
    0x018A, 0x018F, 0x0193, 0x0197, 0x019C, 0x01A0, 0x01A5, 0x01A9, 0x01AE, 0x01B3, 0x01B8, 0x01BC,
    0x01C1, 0x01C6, 0x01CB, 0x01D0, 0x01D5, 0x01DA, 0x01DF, 0x01E5, 0x01EA, 0x01EF, 0x01F5, 0x01FA,
    0x0200, 0x0205, 0x020B, 0x0210, 0x0216, 0x021C, 0x0222, 0x0228, 0x022E, 0x0234, 0x023A, 0x0240,
    0x0247, 0x024D, 0x0253, 0x025A, 0x0260, 0x0267, 0x026E, 0x0275, 0x027B, 0x0282, 0x0289, 0x0290,
    0x0298, 0x029F, 0x02A6, 0x02AD, 0x02B5, 0x02BC, 0x02C4, 0x02CC, 0x02D4, 0x02DC, 0x02E3, 0x02EC,
    0x02F4, 0x02FC, 0x0304, 0x030D, 0x0315, 0x031E, 0x0326, 0x032F, 0x0338, 0x0341, 0x034A, 0x0353,
    0x035D, 0x0366, 0x036F, 0x0379, 0x0383, 0x038D, 0x0396, 0x03A0, 0x03AB, 0x03B5, 0x03BF, 0x03CA,
    0x03D4, 0x03DF, 0x03EA, 0x03F5,
];

// Exact lookup values from the original digital mixer.
const DSP_PAN: [u8; 256] = [
    0x0E, 0x13, 0x19, 0x1D, 0x22, 0x26, 0x2A, 0x2F, 0x33, 0x37, 0x3B, 0x3F, 0x41, 0x45, 0x49, 0x4C,
    0x50, 0x53, 0x55, 0x59, 0x5C, 0x5E, 0x61, 0x65, 0x67, 0x6A, 0x6C, 0x6F, 0x71, 0x74, 0x75, 0x78,
    0x7A, 0x7D, 0x7F, 0x80, 0x83, 0x85, 0x86, 0x89, 0x8B, 0x8C, 0x8E, 0x90, 0x92, 0x93, 0x95, 0x96,
    0x99, 0x9A, 0x9C, 0x9D, 0x9E, 0xA0, 0xA2, 0xA3, 0xA5, 0xA6, 0xA7, 0xA9, 0xAA, 0xAB, 0xAC, 0xAE,
    0xAF, 0xB0, 0xB1, 0xB2, 0xB3, 0xB5, 0xB6, 0xB7, 0xB8, 0xB9, 0xBA, 0xBB, 0xBC, 0xBD, 0xBE, 0xBF,
    0xC0, 0xC1, 0xC2, 0xC3, 0xC4, 0xC5, 0xC5, 0xC6, 0xC7, 0xC8, 0xC9, 0xCA, 0xCB, 0xCC, 0xCD, 0xCD,
    0xCD, 0xCE, 0xCF, 0xD0, 0xD1, 0xD2, 0xD2, 0xD3, 0xD3, 0xD4, 0xD5, 0xD6, 0xD6, 0xD6, 0xD7, 0xD8,
    0xD9, 0xD9, 0xD9, 0xDA, 0xDB, 0xDC, 0xDC, 0xDC, 0xDD, 0xDE, 0xDE, 0xDF, 0xDF, 0xE0, 0xE0, 0xE1,
    0xE1, 0xE1, 0xE2, 0xE3, 0xE4, 0xE4, 0xE4, 0xE5, 0xE5, 0xE6, 0xE6, 0xE6, 0xE7, 0xE7, 0xE7, 0xE8,
    0xE9, 0xE9, 0xE9, 0xE9, 0xEA, 0xEB, 0xEB, 0xEB, 0xEC, 0xEC, 0xEC, 0xEC, 0xED, 0xED, 0xED, 0xEE,
    0xEE, 0xEF, 0xEF, 0xEF, 0xF0, 0xF0, 0xF0, 0xF0, 0xF1, 0xF1, 0xF1, 0xF2, 0xF2, 0xF2, 0xF2, 0xF3,
    0xF3, 0xF3, 0xF3, 0xF4, 0xF4, 0xF4, 0xF5, 0xF5, 0xF5, 0xF5, 0xF6, 0xF6, 0xF6, 0xF6, 0xF7, 0xF7,
    0xF7, 0xF7, 0xF7, 0xF7, 0xF8, 0xF8, 0xF8, 0xF8, 0xF9, 0xF9, 0xF9, 0xF9, 0xF9, 0xF9, 0xF9, 0xFA,
    0xFA, 0xFA, 0xFA, 0xFB, 0xFB, 0xFB, 0xFB, 0xFB, 0xFB, 0xFC, 0xFC, 0xFC, 0xFC, 0xFC, 0xFC, 0xFC,
    0xFD, 0xFD, 0xFD, 0xFD, 0xFD, 0xFD, 0xFD, 0xFE, 0xFE, 0xFE, 0xFE, 0xFE, 0xFE, 0xFE, 0xFF, 0xFF,
    0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
];
