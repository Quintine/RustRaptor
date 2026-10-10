use raptor_replica::{
    content::{ContentPack, Registry},
    modding::{self, ActiveMods, Command, ScriptRuntime},
    persistence::Pilot,
    simulation::{Input, Outcome, World},
    sound,
};
use serde_json::json;

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
