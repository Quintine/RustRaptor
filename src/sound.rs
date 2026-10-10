//! Checked package-local PCM WAV loading, independent of SDL2.
//! RIFF chunks are little-endian and padded to a two-byte boundary.
use crate::audio::DigitalSample;
use anyhow::{Context, Result, ensure};

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
