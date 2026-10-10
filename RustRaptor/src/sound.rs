//! Checked package-local PCM WAV and MUS loading, independent of SDL2.
//! RIFF chunks are little-endian and padded to a two-byte boundary.
use crate::{
    assets::Catalog,
    audio::{DigitalSample, Mixer, MusScore},
    content::{ContentId, Registry},
    simulation::SoundEvent,
};
use anyhow::{Context, Result, ensure};
use std::{collections::BTreeMap, io::Read, path::Path};

/// Original FX IDs name empty catalog markers. Their digital device variant is
/// four entries later, matching SND_Setup's SND_DIGITAL offset.
const DIGITAL_VARIANT: u32 = 4;
const MOD_CACHE_LIMIT: usize = 64 * 1024 * 1024;
pub const MAX_MUSIC_BYTES: usize = 128 * 1024;
const MAX_MUSIC_EVENTS: usize = 16384;
const MAX_MUSIC_TICKS: u32 = 30 * 60 * 70;
const MUSIC_CACHE_LIMIT: usize = 16 * 1024 * 1024;

#[derive(Default)]
pub struct SoundBank {
    original: BTreeMap<u32, DigitalSample>,
    mods: BTreeMap<ContentId, DigitalSample>,
    music: BTreeMap<ContentId, MusScore>,
}
impl SoundBank {
    pub fn preload_originals(&mut self, catalog: &Catalog) -> Result<()> {
        for sound in crate::legacy_tables::sounds() {
            self.original(catalog, sound.asset)?;
        }
        Ok(())
    }
    pub fn original(&mut self, catalog: &Catalog, marker: u32) -> Result<DigitalSample> {
        if !self.original.contains_key(&marker) {
            let is_marker = crate::legacy_tables::sounds()
                .iter()
                .any(|s| s.asset == marker);
            let asset = if is_marker {
                marker
                    .checked_add(DIGITAL_VARIANT)
                    .context("sound variant overflow")?
            } else {
                marker
            };
            let sample = DigitalSample::decode(&catalog.read(asset)?)
                .with_context(|| format!("original sound {marker:#x}, digital asset {asset:#x}"))?;
            self.original.insert(marker, sample);
        }
        Ok(self.original[&marker].clone())
    }
    pub fn queue_original(
        &mut self,
        catalog: &Catalog,
        mixer: &mut Mixer,
        event: &SoundEvent,
    ) -> Result<()> {
        let sample = self.original(catalog, event.asset)?;
        mixer.sample(sample, event.pan, event.pitch, event.volume, event.priority);
        Ok(())
    }
    pub fn mod_sample(&mut self, registry: &Registry, id: &ContentId) -> Result<DigitalSample> {
        let definition = registry
            .sounds
            .get(id)
            .context("missing mod sound definition")?;
        if !self.mods.contains_key(id) {
            let owner = registry.owners.get(id).context("missing sound owner")?;
            let root = registry
                .asset_roots
                .get(owner)
                .context("missing sound asset root")?;
            let path = crate::assets::contained(root, Path::new(&definition.file))?;
            let sample =
                decode(&std::fs::read(path)?).with_context(|| format!("mod sound {id}"))?;
            if self.mods.values().map(|s| s.data.len()).sum::<usize>() + sample.data.len()
                > MOD_CACHE_LIMIT
            {
                self.mods.clear();
            }
            self.mods.insert(id.clone(), sample);
        }
        Ok(self.mods[id].clone())
    }
    pub fn queue_mod(
        &mut self,
        registry: &Registry,
        mixer: &mut Mixer,
        id: &ContentId,
    ) -> Result<()> {
        let sample = self.mod_sample(registry, id)?;
        let definition = &registry.sounds[id];
        mixer.sample(
            sample,
            definition.pan,
            definition.pitch,
            definition.volume,
            definition.priority as i32,
        );
        Ok(())
    }
    pub fn clear_mods(&mut self) {
        self.mods.clear();
        self.music.clear();
    }
    /// Cache validated package scores independently from the digital FX bus.
    pub fn mod_music(&mut self, registry: &Registry, id: &ContentId) -> Result<MusScore> {
        if !self.music.contains_key(id) {
            let definition = registry
                .music
                .get(id)
                .context("missing mod music definition")?;
            let owner = registry.owners.get(id).context("missing music owner")?;
            let root = registry
                .asset_roots
                .get(owner)
                .context("missing music asset root")?;
            let score =
                load_music(root, &definition.file).with_context(|| format!("music {id}"))?;
            if self.music.values().map(score_size).sum::<usize>() + score_size(&score)
                > MUSIC_CACHE_LIMIT
            {
                self.music.clear();
            }
            self.music.insert(id.clone(), score);
        }
        Ok(self.music[id].clone())
    }
    pub fn original_count(&self) -> usize {
        self.original.len()
    }
}
fn score_size(score: &MusScore) -> usize {
    score.groups.len() * std::mem::size_of::<(u32, Vec<crate::audio::MusicEvent>)>()
        + score
            .groups
            .iter()
            .map(|(_, events)| events.len() * std::mem::size_of::<crate::audio::MusicEvent>())
            .sum::<usize>()
}

/// Extra limits apply only to untrusted mod tracks; the legacy MUS decoder and
/// its native timing/controller compatibility remain unchanged.
pub fn decode_music(bytes: &[u8]) -> Result<MusScore> {
    ensure!(bytes.len() <= MAX_MUSIC_BYTES, "music exceeds 128 KiB");
    let score = MusScore::decode(bytes)?;
    let mut count = 0;
    let mut at_tick = 0;
    let mut simultaneous = 0;
    for (tick, events) in &score.groups {
        ensure!(
            *tick <= MAX_MUSIC_TICKS,
            "music duration exceeds 30 minutes"
        );
        count += events.len();
        ensure!(count <= MAX_MUSIC_EVENTS, "music exceeds 16384 events");
        if *tick != at_tick {
            at_tick = *tick;
            simultaneous = 0;
        }
        simultaneous += events.len();
        ensure!(
            simultaneous <= 256,
            "music exceeds 256 events on one service tick"
        );
    }
    ensure!(
        score.groups.last().is_some_and(|(tick, _)| *tick > 0),
        "music must have positive duration"
    );
    Ok(score)
}

pub fn load_music(root: &Path, file: &str) -> Result<MusScore> {
    let path = crate::assets::contained(root, Path::new(file))?;
    let metadata = std::fs::metadata(&path)?;
    ensure!(metadata.is_file(), "music must be a regular file");
    ensure!(
        metadata.len() <= MAX_MUSIC_BYTES as u64,
        "music exceeds 128 KiB"
    );
    let mut bytes = Vec::with_capacity(metadata.len() as usize);
    std::fs::File::open(path)?
        .take(MAX_MUSIC_BYTES as u64 + 1)
        .read_to_end(&mut bytes)?;
    decode_music(&bytes)
}

/// UI cues use the native metadata without consuming gameplay RNG.
pub fn ui_event(name: &str) -> Result<SoundEvent> {
    let sound = crate::legacy_tables::sounds()
        .into_iter()
        .find(|s| s.name == name)
        .context("unknown original UI sound")?;
    Ok(SoundEvent {
        asset: sound.asset,
        pan: 127,
        pitch: sound.pitch,
        volume: sound.volume,
        priority: sound.priority,
    })
}

/// Write a captured production stereo callback as a standard PCM16 WAV.
pub fn encode_capture(capture: &crate::audio::AudioCapture) -> Result<Vec<u8>> {
    ensure!(
        capture.samples.len() % 2 == 0,
        "partial captured stereo frame"
    );
    let size = capture
        .samples
        .len()
        .checked_mul(2)
        .and_then(|n| u32::try_from(n).ok())
        .context("audio capture too large")?;
    let mut bytes = Vec::with_capacity(size as usize + 44);
    bytes.extend_from_slice(b"RIFF");
    bytes.extend_from_slice(&(36 + size).to_le_bytes());
    bytes.extend_from_slice(b"WAVEfmt ");
    bytes.extend_from_slice(&16_u32.to_le_bytes());
    bytes.extend_from_slice(&1_u16.to_le_bytes());
    bytes.extend_from_slice(&2_u16.to_le_bytes());
    bytes.extend_from_slice(&capture.rate.to_le_bytes());
    bytes.extend_from_slice(&(capture.rate * 4).to_le_bytes());
    bytes.extend_from_slice(&4_u16.to_le_bytes());
    bytes.extend_from_slice(&16_u16.to_le_bytes());
    bytes.extend_from_slice(b"data");
    bytes.extend_from_slice(&size.to_le_bytes());
    for sample in &capture.samples {
        bytes.extend_from_slice(&sample.to_le_bytes());
    }
    Ok(bytes)
}

pub fn decode(bytes: &[u8]) -> Result<DigitalSample> {
    ensure!(bytes.len() <= 8 * 1024 * 1024, "sound exceeds 8 MiB");
    if !bytes.starts_with(b"RIFF") {
        return DigitalSample::decode(bytes);
    }
    let u32_at = |offset| -> Result<u32> {
        Ok(u32::from_le_bytes(
            bytes
                .get(offset..offset + 4)
                .context("truncated WAV field")?
                .try_into()?,
        ))
    };
    ensure!(
        bytes.get(8..12) == Some(b"WAVE") && u32_at(4)? as usize == bytes.len().saturating_sub(8),
        "invalid RIFF/WAVE length"
    );
    let mut format = None;
    let mut audio = None;
    let mut offset = 12;
    while offset < bytes.len() {
        let tag = bytes
            .get(offset..offset + 4)
            .context("truncated WAV chunk")?;
        let length = u32_at(offset + 4)? as usize;
        let start = offset + 8;
        let end = start
            .checked_add(length)
            .context("WAV chunk size overflow")?;
        let chunk = bytes
            .get(start..end)
            .context("truncated WAV chunk payload")?;
        match tag {
            b"fmt " => {
                ensure!(
                    format.is_none() && chunk.len() >= 16,
                    "duplicate/truncated WAV format"
                );
                let u16_at = |n| u16::from_le_bytes([chunk[n], chunk[n + 1]]);
                let rate = u32::from_le_bytes(chunk[4..8].try_into()?);
                let channels = u16_at(2) as usize;
                let bits = u16_at(14) as usize;
                ensure!(
                    u16_at(0) == 1
                        && matches!(channels, 1 | 2)
                        && matches!(bits, 8 | 16)
                        && (8000..=48000).contains(&rate),
                    "sound must be 8/16-bit PCM WAV, mono/stereo, 8–48 kHz"
                );
                let align = channels * bits / 8;
                ensure!(
                    u16_at(12) as usize == align
                        && u32::from_le_bytes(chunk[8..12].try_into()?) == rate * align as u32,
                    "invalid WAV block/byte rate"
                );
                format = Some((rate, channels, bits, align));
            }
            b"data" => {
                ensure!(audio.is_none(), "duplicate WAV data");
                audio = Some(chunk);
            }
            _ => {}
        }
        offset = end
            .checked_add(length & 1)
            .context("WAV padding overflow")?;
        ensure!(offset <= bytes.len(), "truncated WAV padding");
    }
    let (rate, channels, bits, align) = format.context("WAV has no format")?;
    let audio = audio.context("WAV has no audio data")?;
    ensure!(
        !audio.is_empty() && audio.len() % align == 0 && audio.len() / align <= rate as usize * 30,
        "invalid WAV sample count (maximum 30 seconds)"
    );
    let data = audio
        .chunks_exact(align)
        .map(|frame| {
            let total: i32 = (0..channels)
                .map(|channel| {
                    if bits == 8 {
                        (frame[channel] as i32 - 128) * 256
                    } else {
                        i16::from_le_bytes([frame[channel * 2], frame[channel * 2 + 1]]) as i32
                    }
                })
                .sum();
            ((total / channels as i32) / 256 + 128).clamp(0, 255) as u8
        })
        .collect();
    Ok(DigitalSample { rate, data })
}
