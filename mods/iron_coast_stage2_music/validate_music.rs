//! Native score/audio QA; built by validate_music.py against this game's library.
use raptor_replica::{
    assets::Catalog,
    audio::{Mixer, MusScore, MusicEvent},
    content::Registry,
    modding::{self, ActiveMods},
    sound,
};
use serde_json::{Value, json};
use std::{
    collections::{BTreeMap, BTreeSet},
    fs,
    path::Path,
};

const RATE: u32 = 22_050;

fn rms(samples: &[i16]) -> f64 {
    (samples.iter().map(|&v| (v as f64).powi(2)).sum::<f64>() / samples.len() as f64).sqrt()
}
fn render(bank: &[u8], score: &MusScore, frames: usize, looping: bool, volume: u8) -> Vec<i16> {
    let mut mixer = Mixer::new(RATE, bank).expect("native FM bank");
    mixer.music_volume = volume;
    mixer.play(score.clone(), looping);
    let mut pcm = vec![0; frames * 2];
    mixer.mix(&mut pcm);
    pcm
}
fn wav(path: &Path, pcm: &[i16]) {
    let size = (pcm.len() * 2) as u32;
    let mut data = Vec::with_capacity(44 + size as usize);
    data.extend(b"RIFF");
    data.extend((36 + size).to_le_bytes());
    data.extend(b"WAVEfmt ");
    data.extend(16u32.to_le_bytes());
    data.extend(1u16.to_le_bytes());
    data.extend(2u16.to_le_bytes());
    data.extend(RATE.to_le_bytes());
    data.extend((RATE * 4).to_le_bytes());
    data.extend(4u16.to_le_bytes());
    data.extend(16u16.to_le_bytes());
    data.extend(b"data");
    data.extend(size.to_le_bytes());
    for sample in pcm {
        data.extend(sample.to_le_bytes());
    }
    fs::write(path, data).expect("write WAV preview outside mod");
}
fn metrics(pcm: &[i16]) -> Value {
    json!({
        "rms": rms(pcm),
        "peak": pcm.iter().map(|v| (*v as i32).abs()).max().unwrap(),
        "clipped_samples": pcm.iter().filter(|&&v| v == i16::MIN || v == i16::MAX).count(),
        "nonzero_samples": pcm.iter().filter(|&&v| v != 0).count(),
        "dc_mean": pcm.iter().map(|&v| v as f64).sum::<f64>() / pcm.len() as f64,
    })
}
fn inspect(key: &str, package: &Path, output: &Path, bank: &[u8]) -> Value {
    let bytes = fs::read(package.join(format!("music/{key}.mus"))).expect("score file");
    let u16_at = |i| u16::from_le_bytes([bytes[i], bytes[i + 1]]) as usize;
    let (length, start, channels, secondary, count, reserved) = (
        u16_at(4),
        u16_at(6),
        u16_at(8),
        u16_at(10),
        u16_at(12),
        u16_at(14),
    );
    assert_eq!(&bytes[..4], b"MUS\x1a");
    assert_eq!(start, 16 + count * 2);
    assert_eq!(start + length, bytes.len());
    assert_eq!(channels, 5);
    assert_eq!(secondary, 0);
    assert_eq!(reserved, 0);
    let declared = (0..count)
        .map(|i| u16_at(16 + i * 2))
        .collect::<BTreeSet<_>>();
    assert_eq!(declared.len(), count, "duplicate instrument preload");
    let score = sound::decode_music(&bytes).expect("checked mod MUS decoder");
    let ticks = score.groups.last().expect("groups").0;
    assert!(
        (5_600..=9_100).contains(&ticks),
        "requested 80–130 sec duration"
    );
    let mut program = [0usize; 16];
    let mut used = BTreeSet::new();
    let mut channels_used = BTreeSet::new();
    let mut percussion = BTreeSet::new();
    let mut pressed = BTreeMap::new();
    let mut max_notes = 0usize;
    let mut max_opl_voices = 0usize;
    let mut notes = 0usize;
    let mut per_channel_notes = [0usize; 16];
    let mut end_events = 0usize;
    let mut same_tick_events = BTreeMap::new();
    let mut events = 0usize;
    let mut final_note_off = 0u32;
    for (tick, group) in &score.groups {
        *same_tick_events.entry(*tick).or_insert(0usize) += group.len();
        events += group.len();
        for event in group {
            match *event {
                MusicEvent::Control(c, 0, p) => {
                    assert!(c < 5);
                    program[c as usize] = p as usize;
                    used.insert(p as usize);
                }
                MusicEvent::On(c, key, velocity) => {
                    assert!(c < 5 || c == 15);
                    assert!(velocity > 0);
                    let instrument = if c == 15 {
                        assert!((35..=81).contains(&key));
                        percussion.insert(key);
                        used.insert(100 + key as usize);
                        128 + (key - 35) as usize
                    } else {
                        program[c as usize]
                    };
                    let offset = 8 + instrument * 36;
                    let flags = u16::from_le_bytes([bank[offset], bank[offset + 1]]);
                    let voices = if flags & 4 != 0 { 2 } else { 1 };
                    assert!(
                        pressed.insert((c, key), voices).is_none(),
                        "overlapping same pitch"
                    );
                    channels_used.insert(c);
                    notes += 1;
                    per_channel_notes[c as usize] += 1;
                }
                MusicEvent::Off(c, key) => {
                    assert!(pressed.remove(&(c, key)).is_some(), "unmatched release");
                    final_note_off = *tick;
                }
                MusicEvent::System(c, 11) => {
                    assert!(
                        !pressed.keys().any(|&(channel, _)| channel == c),
                        "forced release hides dangling note"
                    );
                }
                MusicEvent::End => {
                    assert_eq!(*tick, ticks);
                    end_events += 1;
                }
                MusicEvent::OnInherited(..) => panic!("recipe must have explicit velocity"),
                _ => {}
            }
            max_notes = max_notes.max(pressed.len());
            max_opl_voices = max_opl_voices.max(pressed.values().sum());
        }
    }
    assert!(pressed.is_empty());
    assert_eq!(end_events, 1);
    assert_eq!(
        used, declared,
        "preload declaration must match programs and 100 + drum key"
    );
    assert_eq!(channels_used, BTreeSet::from([0, 1, 2, 3, 4, 15]));
    assert!(max_opl_voices <= 18, "arrangement requires voice stealing");
    assert!(final_note_off < ticks - 1);

    // The native bus services tick 0 after the first 70 Hz quantum. The loop
    // restarts after ticks + 1 quanta, then preserves synth oscillator phase.
    let loop_frame = ((ticks as u64 + 1) * RATE as u64).div_ceil(70) as usize;
    let frames = loop_frame + RATE as usize * 8;
    let preview = render(bank, &score, frames, true, 85);
    let full_volume = render(bank, &score, frames, true, 127);
    let single = render(bank, &score, frames, false, 85);
    let default_metrics = metrics(&preview);
    let full_metrics = metrics(&full_volume);
    assert_eq!(default_metrics["clipped_samples"], 0);
    assert_eq!(full_metrics["clipped_samples"], 0);
    assert!(default_metrics["peak"].as_i64().unwrap() > 1_000);
    let second_rms = preview
        .chunks_exact(RATE as usize * 2)
        .map(rms)
        .collect::<Vec<_>>();
    assert!(
        second_rms.iter().all(|&v| v > 10.),
        "unexpected silent second"
    );
    let tail = (frames - RATE as usize * 2) * 2;
    let single_tail_rms = rms(&single[tail..]);
    let loop_tail_rms = rms(&preview[tail..]);
    assert!(
        single_tail_rms < loop_tail_rms / 20.,
        "one-play tail does not decay"
    );
    let muted = render(bank, &score, RATE as usize, true, 0);
    assert!(muted.iter().all(|&v| v == 0), "native Music volume mute");
    let preview_file = output.join(format!("{key}-preview.wav"));
    wav(&preview_file, &preview);
    let boundary_start = loop_frame.saturating_sub(RATE as usize * 4);
    let boundary_end = loop_frame + RATE as usize * 4;
    let boundary_file = output.join(format!("{key}-loop-boundary.wav"));
    wav(
        &boundary_file,
        &preview[boundary_start * 2..boundary_end * 2],
    );
    let sample_delta = (0..2)
        .map(|channel| {
            (preview[loop_frame * 2 + channel] as i32
                - preview[(loop_frame - 1) * 2 + channel] as i32)
                .abs()
        })
        .max()
        .unwrap();
    let nearby_max_delta = preview[(loop_frame - 100) * 2..(loop_frame + 100) * 2]
        .windows(3)
        .map(|v| (v[2] as i32 - v[0] as i32).abs())
        .max()
        .unwrap();
    assert!(sample_delta <= nearby_max_delta);
    json!({
        "track": key, "duration_ticks": ticks, "duration_seconds": ticks as f64 / 70.,
        "score_bytes": bytes.len(), "score_start": start, "score_stream_bytes": length,
        "primary_channels": channels, "secondary_channels": secondary,
        "events": events, "notes": notes, "groups": score.groups.len(),
        "maximum_events_per_tick": same_tick_events.values().max(),
        "maximum_pressed_notes": max_notes, "maximum_required_opl_voices": max_opl_voices,
        "per_channel_note_counts": per_channel_notes, "percussion_keys": percussion,
        "declared_instruments": declared, "unmatched_or_dangling_notes": 0,
        "end_events": end_events, "last_note_release_tick": final_note_off,
        "sample_rate": RATE, "rendered_frames": frames, "rendered_seconds": frames as f64 / RATE as f64,
        "native_loop_restart_frame": loop_frame, "native_loop_restart_seconds": loop_frame as f64 / RATE as f64,
        "default_volume_85": default_metrics, "maximum_volume_127": full_metrics,
        "per_second_rms": second_rms, "one_play_tail_rms": single_tail_rms,
        "looping_tail_rms": loop_tail_rms, "music_mute_exact_zero": true,
        "boundary_sample_delta": sample_delta, "nearby_maximum_sample_delta": nearby_max_delta,
        "boundary_first_half_rms": rms(&preview[boundary_start * 2..loop_frame * 2]),
        "boundary_second_half_rms": rms(&preview[loop_frame * 2..boundary_end * 2]),
        "preview": preview_file, "loop_boundary_preview": boundary_file,
        "waveform_splice_identical": false,
    })
}
fn main() {
    let args = std::env::args().collect::<Vec<_>>();
    assert_eq!(args.len(), 4, "validate_music DATA_DIR MODS_DIR OUTPUT_DIR");
    let catalog = Catalog::open(Path::new(&args[1])).expect("local catalog");
    let mods = Path::new(&args[2]);
    let output = Path::new(&args[3]);
    fs::create_dir_all(output).unwrap();
    let package = mods.join("iron_coast_stage2_music");
    let active = ActiveMods::build(
        &Registry::default(),
        &modding::discover(mods),
        &["iron_coast_stage2_music".to_owned()],
        Some(&catalog),
    )
    .expect("independent activation");
    assert_eq!(active.pins.len(), 1);
    assert_eq!(active.registry.music.len(), 3);
    let bank = catalog
        .named("GENMIDI_OP2")
        .expect("local original FM instruments");
    let tracks = ["assault", "pursuit", "finale"].map(|key| inspect(key, &package, output, &bank));
    let report = json!({"renderer": "Rust checked mod MUS decoder and native GENMIDI/OPL3 Mixer",
        "independent_activation": true, "pins": active.pins, "tracks": tracks,
        "preview_storage": "Ignored local QA; full previews are not digital sound definitions",
        "audition_method": "Objective native PCM inspection, no claim of human listening",
        "percussion_preload_convention": "100 + GM key; bank playback index separately 128 + key - 35",
        "loop_limit": "Intentional musical cadence; native envelope/oscillator phase means no sample-exact splice"});
    fs::write(
        output.join("native-validation.json"),
        serde_json::to_vec_pretty(&report).unwrap(),
    )
    .unwrap();
    for track in report["tracks"].as_array().unwrap() {
        println!(
            "{}: {} ticks, {} notes, {} FM voices max, peak85={} peak127={}, clipped=0, loop/mute/release checks passed",
            track["track"],
            track["duration_ticks"],
            track["notes"],
            track["maximum_required_opl_voices"],
            track["default_volume_85"]["peak"],
            track["maximum_volume_127"]["peak"]
        );
    }
}
