use raptor_replica::audio::{DigitalSample, Mixer, MusScore};
use std::{fs, path::Path, process::Command};

fn instruments(double: bool) -> Vec<u8> {
    let mut bytes = b"#OPL_II#".to_vec();
    for n in 0..175 {
        let mut instrument = [0u8; 36];
        instrument[0] = if n == 1 {
            1
        } else if double {
            4
        } else {
            0
        };
        instrument[2] = 128;
        instrument[3] = 48;
        for part in 0..2 {
            let start = 4 + part * 16;
            instrument[start..start + 6].copy_from_slice(&[0x21, 0xf2, 0x52, 0, 0, 32]);
            instrument[start + 6] = 0;
            instrument[start + 7..start + 13].copy_from_slice(&[0x21, 0xf2, 0x52, 0, 0, 0]);
        }
        bytes.extend(instrument);
    }
    bytes
}
fn mus(body: &[u8], channels: u16) -> Vec<u8> {
    let mut bytes = b"MUS\x1a".to_vec();
    bytes.extend((body.len() as u16).to_le_bytes());
    bytes.extend(16u16.to_le_bytes());
    bytes.extend(channels.to_le_bytes());
    bytes.extend([0; 6]);
    bytes.extend(body);
    bytes
}
fn score() -> Vec<u8> {
    mus(
        &[
            0x40, 0, 0, 0x90, 188, 100, 10, 0xa0, 144, 5, 0xc0, 3, 90, 5, 0x80, 60, 10, 0x60,
        ],
        1,
    )
}
fn sample(data: Vec<u8>) -> DigitalSample {
    DigitalSample { rate: 11025, data }
}
fn patch(data: &[u8]) -> Vec<u8> {
    let mut bytes = vec![3, 0];
    bytes.extend(11025u16.to_le_bytes());
    bytes.extend(((data.len() + 32) as u32).to_le_bytes());
    bytes.extend([0xff; 16]);
    bytes.extend(data);
    bytes.extend([0; 16]);
    bytes
}
fn mixer() -> Mixer {
    Mixer::new(44100, &instruments(false)).unwrap()
}

#[test]
fn digital_decoder_excludes_both_padding_regions() {
    let decoded = DigitalSample::decode(&patch(&[0, 64, 128, 192, 255])).unwrap();
    assert_eq!(decoded.rate, 11025);
    assert_eq!(decoded.data, vec![0, 64, 128, 192, 255]);
    assert!(DigitalSample::decode(&patch(&[])).is_err());
}

#[test]
fn music_events_start_on_the_first_seventy_hertz_service_tick() {
    let mut mixer = mixer();
    mixer.music_volume = 127;
    mixer.play(MusScore::decode(&score()).unwrap(), false);
    let mut prefix = vec![1; 630 * 2];
    mixer.mix(&mut prefix);
    assert!(prefix.iter().all(|n| *n == 0));
    let mut following = vec![0; 3000 * 2];
    mixer.mix(&mut following);
    assert!(following.iter().any(|n| *n != 0));
}

#[test]
fn fm_and_digital_output_do_not_depend_on_audio_callback_size() {
    let table = instruments(true);
    let mut whole = Mixer::new(44117, &table).unwrap();
    let mut chunked = Mixer::new(44117, &table).unwrap();
    for m in [&mut whole, &mut chunked] {
        m.play_with_fade(MusScore::decode(&score()).unwrap(), true, true);
        m.sample(
            sample((0..255).cycle().take(5000).collect()),
            37,
            192,
            100,
            1,
        );
    }
    let mut expected = vec![0; 44117 * 2];
    whole.mix(&mut expected);
    let mut actual = vec![0; expected.len()];
    let mut frame = 0;
    for count in [1usize, 3, 17, 512, 127].into_iter().cycle() {
        let count = count.min(actual.len() / 2 - frame);
        chunked.mix(&mut actual[frame * 2..(frame + count) * 2]);
        frame += count;
        if frame == actual.len() / 2 {
            break;
        }
    }
    assert_eq!(actual, expected);
}

#[test]
fn digital_mixing_uses_the_original_11025_hertz_sample_hold() {
    let mut mixer = mixer();
    mixer.fx_volume = 127;
    mixer.sample(sample(vec![255, 255]), 128, 128, 127, 1);
    let mut out = [0; 24];
    mixer.mix(&mut out);
    assert_eq!(&out[..6], &[0; 6]);
    assert!(out[6] > 0 && out[7] > 0);
    assert_eq!(&out[6..8], &out[8..10]);
    assert_eq!(&out[6..8], &out[10..12]);
    assert_eq!(&out[6..8], &out[12..14]);
    assert_eq!(&out[22..24], &[0, 0]);
}

#[test]
fn pitch_zero_is_a_valid_quarter_speed_pitch() {
    let mut normal = mixer();
    let mut slow = mixer();
    normal.fx_volume = 127;
    slow.fx_volume = 127;
    normal.sample(sample(vec![255; 8]), 128, 128, 127, 1);
    slow.sample(sample(vec![255; 8]), 128, 0, 127, 1);
    let mut fast = [0; 100];
    let mut quarter = [0; 100];
    normal.mix(&mut fast);
    slow.mix(&mut quarter);
    assert!(fast[80..].iter().all(|v| *v == 0));
    assert!(quarter[80..].iter().any(|v| *v > 0));
}

#[test]
fn lower_numeric_digital_priority_wins() {
    let mut mixer = mixer();
    mixer.fx_volume = 127;
    mixer.set_fx_channels(1);
    mixer.sample(sample(vec![255; 1000]), 128, 128, 127, 1);
    mixer.sample(sample(vec![0; 1000]), 128, 128, 127, 8);
    let mut protected = [0; 64];
    mixer.mix(&mut protected);
    assert!(protected[8..].iter().all(|v| *v > 0));
    mixer.sample(sample(vec![0; 1000]), 128, 128, 127, 0);
    let mut replaced = [0; 64];
    mixer.mix(&mut replaced);
    assert!(replaced[8..].iter().all(|v| *v < 0));
}

#[test]
fn digital_voices_clip_together_before_being_added_to_fm() {
    let mut mixer = mixer();
    mixer.fx_volume = 127;
    mixer.set_fx_channels(8);
    for _ in 0..8 {
        mixer.sample(sample(vec![255; 100]), 128, 128, 127, 1);
    }
    let mut out = [0; 64];
    mixer.mix(&mut out);
    assert_eq!(out[20], 127 * 128);
    assert_eq!(out[21], 127 * 128);
}

#[test]
fn malformed_scores_controller_values_and_missing_end_events_are_rejected() {
    for body in [
        vec![0x90, 188],
        vec![0x90, 188, 200, 1, 0x60],
        vec![0xc0, 3, 255, 1, 0x60],
        vec![0x30, 9, 0x60],
        vec![0x90, 188, 127, 1],
    ] {
        assert!(MusScore::decode(&mus(&body, 1)).is_err());
    }
    assert!(MusScore::decode(&mus(&[0x60], 16)).is_err());
}

#[test]
fn a_zero_duration_loop_and_an_odd_output_slice_terminate_cleanly() {
    let mut mixer = mixer();
    mixer.play(MusScore::decode(&mus(&[0x60], 1)).unwrap(), true);
    let mut out = [99; 2001];
    mixer.mix(&mut out);
    assert_eq!(out[2000], 0);
}

#[test]
#[ignore = "requires the original untracked catalog"]
fn original_music_and_sound_assets_decode_locally() {
    use raptor_replica::assets::Catalog;
    let root = std::env::var_os("RAPTOR_TEST_DATA")
        .map(std::path::PathBuf::from)
        .unwrap_or_else(|| Path::new(env!("CARGO_MANIFEST_DIR")).join("data"));
    let catalog = Catalog::open(root).unwrap();
    let mut music = 0;
    let mut sounds = 0;
    for entry in catalog.entries.values() {
        let bytes = catalog.read(entry.id).unwrap();
        if bytes.starts_with(b"MUS\x1a") {
            MusScore::decode(&bytes).unwrap();
            music += 1;
        }
        if bytes.get(..4) == Some(&[3, 0, 0x11, 0x2b]) {
            DigitalSample::decode(&bytes).unwrap();
            sounds += 1;
        }
    }
    assert_eq!(music, 16);
    assert_eq!(sounds, 26, "digital samples");
    Mixer::new(44100, &catalog.named("GENMIDI_OP2").unwrap()).unwrap();
}

const NATIVE_REFERENCE: &str = r#"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>
#include <fstream>
#include <iterator>
#include "SDL.h"
#include "musapi.h"
#include "i_oplmusic.h"
#include "dspapi.h"
#include "cards.h"
int fx_freq=44100, gsshack=0, gssrate=0, sys_midi=0;
musdevice_t mus_device_alsa={}, mus_device_tsf={};
void SND_Lock(){} void SND_Unlock(){} void GSS_Service(){} void GSS_Poll(){}
extern "C" Uint32 SDL_GetTicks(){return 0;}
std::vector<char> read(const char *path){std::ifstream in(path,std::ios::binary);return {std::istreambuf_iterator<char>(in),{}};}
int main(int argc,char **argv){
 if(argc!=9)return 2;
 auto gen=read(argv[1]),score=read(argv[2]),patch=read(argv[3]);
 int frames=std::atoi(argv[4]),mode=std::atoi(argv[5]),fade=std::atoi(argv[6]),loop=std::atoi(argv[7]);
 std::vector<int16_t> out(frames*2,0);
 if(mode!=1){LoadInstrumentTable(gen.data());MUS_Init(M_ADLIB,0);MUS_SetVolume(127);MUS_PlaySong(score.data(),loop,fade);}
 if(mode!=0){DSP_Init(8,11025);DSP_StartPatch((dsp_t*)patch.data(),37,192,85,1);}
 if(mode!=1)MUS_Mix(out.data(),frames);
 if(mode!=0)DSP_Mix(out.data(),frames);
 FILE *file=fopen(argv[8],"wb");if(!file)return 3;
 fwrite(out.data(),sizeof(int16_t),out.size(),file);fclose(file);return 0;
}
"#;

#[test]
#[ignore = "requires g++ and SDL2 development headers; synthetic assets only"]
fn rust_fm_mus_and_digital_pcm_match_the_retained_native_reference() {
    let temp = tempfile::tempdir().unwrap();
    let binary = compile_reference(temp.path());
    let patch_data: Vec<_> = (0..255).cycle().take(2000).collect();
    let patch_path = temp.path().join("patch.bin");
    fs::write(&patch_path, patch(&patch_data)).unwrap();
    for (double, mode, fade, looping) in [
        (false, 0, false, false),
        (true, 0, false, false),
        (false, 1, false, false),
        (true, 2, true, true),
    ] {
        let bank = instruments(double);
        let song = score();
        let frames = 44100;
        let gen_path = temp.path().join("genmidi.bin");
        fs::write(&gen_path, &bank).unwrap();
        let score_path = temp.path().join("score.bin");
        fs::write(&score_path, &song).unwrap();
        let output = temp.path().join("reference.pcm");
        let status = Command::new(&binary)
            .arg(&gen_path)
            .arg(&score_path)
            .arg(&patch_path)
            .arg(frames.to_string())
            .arg(mode.to_string())
            .arg(i32::from(fade).to_string())
            .arg(i32::from(looping).to_string())
            .arg(&output)
            .status()
            .unwrap();
        assert!(status.success());
        let expected = fs::read(output).unwrap();
        let mut mixer = Mixer::new(44100, &bank).unwrap();
        mixer.music_volume = 127;
        mixer.fx_volume = 127;
        mixer.set_fx_channels(8);
        if mode != 1 {
            mixer.play_with_fade(MusScore::decode(&song).unwrap(), looping, fade);
        }
        if mode != 0 {
            mixer.sample(sample(patch_data.clone()), 37, 192, 85, 1);
        }
        let mut out = vec![0; frames * 2];
        mixer.mix(&mut out);
        let actual: Vec<_> = out.iter().flat_map(|v| v.to_le_bytes()).collect();
        if let Some(index) = actual
            .chunks_exact(2)
            .zip(expected.chunks_exact(2))
            .position(|(a, b)| a != b)
        {
            let want = i16::from_le_bytes(expected[index * 2..index * 2 + 2].try_into().unwrap());
            panic!(
                "PCM mismatch double={double} mode={mode} fade={fade} loop={looping}: frame={} channel={} got={} expected={want}",
                index / 2,
                index % 2,
                out[index]
            );
        }
        assert_eq!(actual.len(), expected.len());
    }
}

fn compile_reference(directory: &Path) -> std::path::PathBuf {
    let root = Path::new(env!("CARGO_MANIFEST_DIR"));
    let source = directory.join("reference.cpp");
    fs::write(&source, NATIVE_REFERENCE).unwrap();
    let binary = directory.join("reference");
    let mut compile = Command::new("g++");
    compile
        .args(["-std=c++17", "-O2"])
        .arg("-I")
        .arg(root.join("raptor/src"));
    compile.arg("-I").arg("/usr/include/SDL2");
    if let Some(home) = std::env::var_os("HOME") {
        compile
            .arg("-I")
            .arg(Path::new(&home).join(".local/include/SDL2"));
    }
    compile.arg(&source);
    for path in ["i_oplmusic.cpp", "opl3.cpp", "musapi.cpp", "dspapi.cpp"] {
        compile.arg(root.join("raptor/src").join(path));
    }
    let result = compile.arg("-o").arg(&binary).output().unwrap();
    assert!(
        result.status.success(),
        "{}",
        String::from_utf8_lossy(&result.stderr)
    );
    binary
}

#[test]
#[ignore = "requires original untracked music assets, g++ and SDL2 headers"]
fn original_intro_pcm_matches_the_retained_native_reference() {
    use raptor_replica::assets::Catalog;
    let temp = tempfile::tempdir().unwrap();
    let root = std::env::var_os("RAPTOR_TEST_DATA")
        .map(std::path::PathBuf::from)
        .unwrap_or_else(|| Path::new(env!("CARGO_MANIFEST_DIR")).join("data"));
    let catalog = Catalog::open(root).unwrap();
    let bank = catalog.named("GENMIDI_OP2").unwrap();
    let song = catalog.named("RINTRO_MUS").unwrap();
    let binary = compile_reference(temp.path());
    fs::write(temp.path().join("genmidi.bin"), &bank).unwrap();
    fs::write(temp.path().join("score.bin"), &song).unwrap();
    fs::write(temp.path().join("patch.bin"), patch(&[128; 33])).unwrap();
    let frames = 44100 * 4;
    let output = temp.path().join("reference.pcm");
    let status = Command::new(binary)
        .arg(temp.path().join("genmidi.bin"))
        .arg(temp.path().join("score.bin"))
        .arg(temp.path().join("patch.bin"))
        .arg(frames.to_string())
        .args(["0", "1", "1"])
        .arg(&output)
        .status()
        .unwrap();
    assert!(status.success());
    let expected = fs::read(output).unwrap();
    let mut mixer = Mixer::new(44100, &bank).unwrap();
    mixer.music_volume = 127;
    mixer.play_with_fade(MusScore::decode(&song).unwrap(), true, true);
    let mut actual = vec![0i16; frames * 2];
    mixer.mix(&mut actual);
    for (index, (got, bytes)) in actual.iter().zip(expected.chunks_exact(2)).enumerate() {
        let want = i16::from_le_bytes(bytes.try_into().unwrap());
        assert_eq!(
            *got,
            want,
            "original intro frame {} channel {}",
            index / 2,
            index % 2
        );
    }
    assert_eq!(actual.len() * 2, expected.len());
}
