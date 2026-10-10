use raptor_replica::{
    content::{ContentPack, Registry},
    modding::{self, ActiveMods, Command, ScriptRuntime},
    persistence::Pilot,
    simulation::{Input, Outcome, World},
    sound,
};
use serde_json::json;

fn digital_patch() -> Vec<u8> {
    let data: Vec<_> = (0..4000)
        .map(|i| if i % 20 < 10 { 240 } else { 16 })
        .collect();
    let mut bytes = vec![3, 0];
    bytes.extend(11025_u16.to_le_bytes());
    bytes.extend(((data.len() + 32) as i32).to_le_bytes());
    bytes.extend([0; 16]);
    bytes.extend(data);
    bytes.extend([0; 16]);
    bytes
}
fn original_catalog() -> (tempfile::TempDir, raptor_replica::assets::Catalog) {
    let root = tempfile::tempdir().unwrap();
    std::fs::write(root.path().join("marker"), []).unwrap();
    let bytes = digital_patch();
    std::fs::write(root.path().join("digital"), &bytes).unwrap();
    std::fs::write(
        root.path().join("INDEX"),
        format!("00090 0 marker\n00094 {} digital\n", bytes.len()),
    )
    .unwrap();
    let catalog = raptor_replica::assets::Catalog::open(root.path()).unwrap();
    (root, catalog)
}
fn mixer() -> raptor_replica::audio::Mixer {
    let mut genmidi = b"#OPL_II#".to_vec();
    genmidi.resize(8 + 175 * 36, 0);
    let mut mixer = raptor_replica::audio::Mixer::new(44100, &genmidi).unwrap();
    mixer.fx_volume = 127;
    mixer
}
#[test]
fn original_marker_resolves_digital_variant_and_keeps_decoded_cache() {
    let (root, catalog) = original_catalog();
    assert!(raptor_replica::audio::DigitalSample::decode(&catalog.read(144).unwrap()).is_err());
    let mut bank = sound::SoundBank::default();
    let resolved = bank.original(&catalog, 144).unwrap();
    assert_eq!(resolved.data.len(), 4000);
    assert_eq!(bank.original_count(), 1);
    std::fs::remove_file(root.path().join("digital")).unwrap();
    assert_eq!(bank.original(&catalog, 144).unwrap().data, resolved.data);
    assert!(bank.original(&catalog, 999).is_err());
}

#[test]
fn live_world_firing_reaches_the_native_digital_mixer() {
    let (_root, catalog) = original_catalog();
    let mut registry = registry();
    registry
        .missions
        .get_mut(&Pilot::default().mission)
        .unwrap()
        .script = None;
    let content: ContentPack = serde_json::from_value(json!({
        "weapons":[{"id":"base:test_guns","name":"Test guns","damage":2,"speed":8,"cooldown":2,"target":"all","behavior":"straight","legacy":0}]
    })).unwrap();
    registry.apply(content, "base").unwrap();
    registry
        .items
        .get_mut(&"base:forward_guns".into())
        .unwrap()
        .weapon = Some("base:test_guns".into());
    let mut world = World::new(&Pilot::default().mission, &Pilot::default(), &registry).unwrap();
    world
        .step(
            Input {
                fire: true,
                ..Input::default()
            },
            &registry,
            &mut ScriptRuntime::new(),
        )
        .unwrap();
    let event = world
        .sound_events
        .iter()
        .find(|s| s.asset == 144)
        .expect("firing did not emit native gun sound");
    let mut mixer = mixer();
    let mut bank = sound::SoundBank::default();
    bank.queue_original(&catalog, &mut mixer, event).unwrap();
    let mut pcm = vec![0; 4096];
    mixer.mix(&mut pcm);
    assert!(pcm.iter().any(|s| *s != 0));
}

#[cfg(feature = "desktop")]
#[test]
fn production_sdl_callback_outputs_and_captures_resolved_original_effect() {
    use sdl2::audio::AudioCallback;
    let (_root, catalog) = original_catalog();
    let mut mixer = mixer();
    mixer.start_capture(1).unwrap();
    let mut bank = sound::SoundBank::default();
    bank.queue_original(&catalog, &mut mixer, &sound::ui_event("FX_GUN").unwrap())
        .unwrap();
    let mut output = [99; 4096];
    AudioCallback::callback(&mut mixer, &mut output);
    assert!(output.iter().any(|s| *s != 0));
    assert!(output.chunks_exact(2).any(|s| s[0] != 0 && s[1] != 0));
    assert_eq!(mixer.take_capture().unwrap().samples, output);
}

#[cfg(feature = "desktop")]
#[test]
#[ignore = "requires the original untracked catalog; uses only the Rust audio callback"]
fn all_original_effect_cues_reach_the_production_callback_locally() {
    use raptor_replica::{assets::Catalog, audio::Mixer};
    use sdl2::audio::AudioCallback;
    let root = std::env::var_os("RAPTOR_TEST_DATA")
        .map(std::path::PathBuf::from)
        .unwrap_or_else(|| std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../data"));
    let catalog = Catalog::open(root).unwrap();
    let instruments = catalog.named("GENMIDI_OP2").unwrap();
    let mut bank = sound::SoundBank::default();
    bank.preload_originals(&catalog).unwrap();
    assert_eq!(bank.original_count(), 26);
    let names = [
        "FX_MON1",
        "FX_MON2",
        "FX_MON3",
        "FX_MON4",
        "FX_MON5",
        "FX_MON6",
        "FX_DAVE",
        "FX_THEME",
        "FX_AIREXPLO",
        "FX_AIREXPLO2",
        "FX_BONUS",
        "FX_CRASH",
        "FX_DOOR",
        "FX_FLYBY",
        "FX_EGRAB",
        "FX_GEXPLO",
        "FX_GUN",
        "FX_JETSND",
        "FX_LASER",
        "FX_MISSLE",
        "FX_SWEP",
        "FX_TURRET",
        "FX_WARNING",
        "FX_BOSS1",
        "FX_IJETSND",
        "FX_EJETSND",
        "FX_INTROHIT",
        "FX_INTROGUN",
        "FX_ENEMYSHOT",
        "FX_ENEMYLASER",
        "FX_ENEMYMISSLE",
        "FX_ENEMYPLASMA",
        "FX_SHIT",
        "FX_HIT",
        "FX_NOSHOOT",
        "FX_PULSE",
    ];
    for name in names {
        let mut mixer = Mixer::new(44100, &instruments).unwrap();
        mixer.fx_volume = 127;
        bank.queue_original(&catalog, &mut mixer, &sound::ui_event(name).unwrap())
            .unwrap();
        let mut output = vec![0; 44100 * 2];
        AudioCallback::callback(&mut mixer, &mut output);
        assert!(output.iter().any(|s| *s != 0), "silent original cue {name}");
    }
    println!(
        "36 original cue variants produced PCM through the Rust SDL callback; 26 cached digital assets"
    );
}

fn wav(channels: u16, bits: u16, data: &[u8]) -> Vec<u8> {
    let align = channels * bits / 8;
    let mut bytes = b"RIFF".to_vec();
    bytes.extend((36u32 + data.len() as u32 + (data.len() as u32 % 2)).to_le_bytes());
    bytes.extend(b"WAVEfmt ");
    bytes.extend(16u32.to_le_bytes());
    bytes.extend(1u16.to_le_bytes());
    bytes.extend(channels.to_le_bytes());
    bytes.extend(11025u32.to_le_bytes());
    bytes.extend((11025u32 * align as u32).to_le_bytes());
    bytes.extend(align.to_le_bytes());
    bytes.extend(bits.to_le_bytes());
    bytes.extend(b"data");
    bytes.extend((data.len() as u32).to_le_bytes());
    bytes.extend(data);
    if data.len() % 2 == 1 {
        bytes.push(0);
    }
    bytes
}
fn registry() -> Registry {
    let mut registry = Registry::default();
    let pack: ContentPack=serde_json::from_value(json!({
        "items":[{"id":"base:energy","name":"Shield","price":0,"max_count":100},
            {"id":"base:forward_guns","name":"Guns","price":0}],
        "missions":[{"id":"base:sector_1_wave_1","name":"Test","duration":1,"auto_complete":false,"script":"mission.rhai"}],
        "sounds":[{"id":"base:test","name":"Test","file":"test.wav"}]
    })).unwrap();
    registry.apply(pack, "base").unwrap();
    registry.validate().unwrap();
    registry
}
#[test]
fn wav_handles_padding_unsigned_eight_bit_and_stereo_sixteen_bit() {
    let decoded = sound::decode(&wav(1, 8, &[0, 128, 255])).unwrap();
    assert_eq!(decoded.data, [0, 128, 255]);
    assert_eq!(decoded.rate, 11025);
    let samples: Vec<_> = [-32768i16, 32767, -32768, -32768, 32767, 32767]
        .into_iter()
        .flat_map(i16::to_le_bytes)
        .collect();
    assert_eq!(
        sound::decode(&wav(2, 16, &samples)).unwrap().data,
        [128, 0, 255]
    );
}
#[test]
fn malformed_wave_ranges_formats_and_padding_fail() {
    let bytes = wav(1, 8, &[128, 200, 0]);
    for end in 0..bytes.len() {
        assert!(sound::decode(&bytes[..end]).is_err());
    }
    assert!(sound::decode(&wav(3, 8, &[0, 0, 0])).is_err());
    assert!(sound::decode(&wav(1, 32, &[0, 0, 0, 0])).is_err());
    let mut huge = bytes.clone();
    huge[40..44].copy_from_slice(&u32::MAX.to_le_bytes());
    assert!(sound::decode(&huge).is_err());
}
#[test]
fn scripted_completion_emits_end_hook_once_and_sound_ids_are_checked() {
    let registry = registry();
    let mut world = World::new(&Pilot::default().mission, &Pilot::default(), &registry).unwrap();
    let mut scripts = ScriptRuntime::new();
    scripts.add("base","mission.rhai",r#"
        fn on_tick(event,state,random) { #{commands:[#{op:"complete"}],state:state} }
        fn on_mission_end(event,state,random) { #{commands:[#{op:"play_sound",sound:"base:test"}],state:#{ended:1}} }
    "#).unwrap();
    world
        .step(Input::default(), &registry, &mut scripts)
        .unwrap();
    assert_eq!(world.outcome, Outcome::Complete);
    assert_eq!(world.mod_sounds.len(), 1);
    world
        .step(Input::default(), &registry, &mut scripts)
        .unwrap();
    assert_eq!(world.mod_sounds.len(), 1);
    assert!(
        world
            .apply_commands(
                &[Command::PlaySound {
                    sound: "base:missing".into()
                }],
                &registry
            )
            .is_err()
    );
}

#[test]
fn scripted_mod_cue_outputs_pcm_and_cache_is_cleared_when_mods_change() {
    let root = tempfile::tempdir().unwrap();
    let mut registry = registry();
    registry
        .asset_roots
        .insert("base".into(), root.path().to_path_buf());
    let path = root.path().join("test.wav");
    std::fs::write(&path, wav(1, 8, &vec![240; 2000])).unwrap();
    let mut world = World::new(&Pilot::default().mission, &Pilot::default(), &registry).unwrap();
    let mut scripts = ScriptRuntime::new();
    scripts.add("base", "mission.rhai", r#"
        fn on_tick(event,state,random) { #{commands:[#{op:"complete"}],state:state} }
        fn on_mission_end(event,state,random) { #{commands:[#{op:"play_sound",sound:"base:test"}],state:state} }
    "#).unwrap();
    world
        .step(Input::default(), &registry, &mut scripts)
        .unwrap();
    assert_eq!(world.mod_sounds.len(), 1);
    let id = &world.mod_sounds[0];
    let mut bank = sound::SoundBank::default();
    let mut audible = mixer();
    bank.queue_mod(&registry, &mut audible, id).unwrap();
    let mut pcm = [0; 1024];
    audible.mix(&mut pcm);
    assert!(pcm.iter().any(|s| *s != 0));
    std::fs::write(&path, wav(1, 8, &vec![128; 2000])).unwrap();
    assert!(
        bank.mod_sample(&registry, id)
            .unwrap()
            .data
            .iter()
            .any(|v| *v != 128)
    );
    bank.clear_mods();
    let mut replaced = mixer();
    bank.queue_mod(&registry, &mut replaced, id).unwrap();
    replaced.mix(&mut pcm);
    assert!(pcm.iter().all(|s| *s == 0));
}
#[test]
fn package_local_sounds_validate_and_missing_files_reject_activation() {
    let dir = tempfile::tempdir().unwrap();
    let package = dir.path().join("tone");
    std::fs::create_dir_all(&package).unwrap();
    std::fs::write(
        package.join("mod.toml"),
        "id='tone'\nname='Tone'\nversion='1.0.0'\napi_version=1\ncontent='content.json'\n",
    )
    .unwrap();
    std::fs::write(
        package.join("content.json"),
        serde_json::to_vec(&json!({"sounds":[{"id":"tone:shot","name":"Shot","file":"shot.wav"}]}))
            .unwrap(),
    )
    .unwrap();
    std::fs::write(package.join("shot.wav"), wav(1, 8, &[128, 200, 50])).unwrap();
    let found = modding::discover(dir.path());
    assert!(ActiveMods::build(&Registry::default(), &found, &["tone".into()], None).is_ok());
    std::fs::remove_file(package.join("shot.wav")).unwrap();
    let found = modding::discover(dir.path());
    assert!(ActiveMods::build(&Registry::default(), &found, &["tone".into()], None).is_err());
}
