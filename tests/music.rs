use raptor_replica::{
    audio::{DigitalSample, Mixer},
    content::{ContentId, ContentPack, Registry},
    modding::{self, ActiveMods},
    sound::{self, SoundBank},
};
use serde_json::{Value, json};
use std::{fs, path::Path};

fn mus(body: &[u8], channels: u16) -> Vec<u8> {
    let mut bytes = b"MUS\x1a".to_vec();
    bytes.extend((body.len() as u16).to_le_bytes());
    bytes.extend(16_u16.to_le_bytes());
    bytes.extend(channels.to_le_bytes());
    bytes.extend([0; 6]);
    bytes.extend(body);
    bytes
}
fn theme(key: u8) -> Vec<u8> {
    mus(
        &[0x40, 0, 0, 0x90, 128 | key, 100, 4, 0x80, key, 4, 0x60],
        1,
    )
}
fn pack(value: Value) -> ContentPack {
    serde_json::from_value(value).unwrap()
}
fn install(root: &Path, id: &str, content: Value, score: &[u8]) {
    let path = root.join(id);
    fs::create_dir_all(&path).unwrap();
    fs::write(
        path.join("mod.toml"),
        format!("id = \"{id}\"\nname = \"{id}\"\nversion = \"1.0.0\"\napi_version = 1\n"),
    )
    .unwrap();
    fs::write(
        path.join("content.json"),
        serde_json::to_vec_pretty(&content).unwrap(),
    )
    .unwrap();
    fs::write(path.join("theme.mus"), score).unwrap();
}
fn selected(ids: &[&str]) -> Vec<String> {
    ids.iter().map(|id| (*id).to_owned()).collect()
}
fn error<T>(result: anyhow::Result<T>) -> String {
    match result {
        Ok(_) => panic!("expected failure"),
        Err(error) => format!("{error:#}"),
    }
}
fn music_pack() -> Value {
    json!({
        "music":[{"id":"demo:theme","name":"Demo theme","file":"theme.mus"}],
        "missions":[{"id":"demo:mission","name":"Demo mission","duration":100,"music_track":"demo:theme"}]
    })
}
fn build(root: &Path, enabled: &[&str]) -> anyhow::Result<ActiveMods> {
    ActiveMods::build(
        &Registry::default(),
        &modding::discover(root),
        &selected(enabled),
        None,
    )
}
fn instruments() -> Vec<u8> {
    let mut bytes = b"#OPL_II#".to_vec();
    for _ in 0..175 {
        let mut instrument = [0; 36];
        instrument[2] = 128;
        for part in 0..2 {
            let start = 4 + part * 16;
            instrument[start..start + 6].copy_from_slice(&[0x21, 0xf2, 0x0f, 0, 0, 32]);
            instrument[start + 7..start + 13].copy_from_slice(&[0x21, 0xf2, 0x0f, 0, 0, 0]);
        }
        bytes.extend(instrument);
    }
    bytes
}

#[test]
fn music_registry_references_defaults_and_selection_are_checked() {
    let mut registry = Registry::default();
    registry.apply(pack(music_pack()), "demo").unwrap();
    registry.validate().unwrap();
    assert!(registry.music[&ContentId::from("demo:theme")].looping);
    let mission = registry.missions.get_mut(&"demo:mission".into()).unwrap();
    mission.music = Some(86);
    assert!(error(registry.validate()).contains("both music and music_track"));
    let mission = registry.missions.get_mut(&"demo:mission".into()).unwrap();
    mission.music = None;
    mission.music_track = Some("missing:theme".into());
    assert!(error(registry.validate()).contains("missing music track missing:theme"));
}

#[test]
fn music_additions_and_explicit_overrides_use_the_winning_package_files() {
    let temp = tempfile::tempdir().unwrap();
    install(temp.path(), "demo", music_pack(), &theme(60));
    install(
        temp.path(),
        "override",
        json!({
            "overrides":["demo:theme"],
            "music":[{"id":"demo:theme","name":"Replacement","file":"theme.mus","looping":false}]
        }),
        &theme(67),
    );
    let active = build(temp.path(), &["demo", "override"]).unwrap();
    assert_eq!(active.registry.owners[&"demo:theme".into()], "override");
    assert!(!active.registry.music[&"demo:theme".into()].looping);
    let mut bank = SoundBank::default();
    let score = bank
        .mod_music(&active.registry, &"demo:theme".into())
        .unwrap();
    assert_eq!(
        score.groups,
        sound::decode_music(&theme(67)).unwrap().groups
    );
    let mut registry = Registry::default();
    registry.apply(pack(music_pack()), "demo").unwrap();
    assert!(
        error(registry.apply(
            pack(json!({"music":[{"id":"demo:theme","name":"Duplicate","file":"theme.mus"}]})),
            "other"
        ))
        .contains("explicit override")
    );
    assert!(error(registry.apply(pack(json!({"overrides":["demo:theme"],"sounds":[{"id":"demo:theme","name":"Wrong type","file":"theme.wav"}]})), "other")).contains("cannot change content type"));
}

#[test]
fn music_files_are_part_of_package_hashes_and_cache_clears_with_active_mods() {
    let temp = tempfile::tempdir().unwrap();
    install(temp.path(), "demo", music_pack(), &theme(60));
    let discovery = modding::discover(temp.path());
    let active =
        ActiveMods::build(&Registry::default(), &discovery, &selected(&["demo"]), None).unwrap();
    let mut bank = SoundBank::default();
    let first = bank
        .mod_music(&active.registry, &"demo:theme".into())
        .unwrap();
    fs::write(temp.path().join("demo/theme.mus"), theme(65)).unwrap();
    assert_ne!(
        discovery.mods["demo"].hash,
        modding::discover(temp.path()).mods["demo"].hash
    );
    assert!(
        error(ActiveMods::build(
            &Registry::default(),
            &discovery,
            &selected(&["demo"]),
            None
        ))
        .contains("changed since discovery")
    );
    let cached = bank
        .mod_music(&active.registry, &"demo:theme".into())
        .unwrap();
    assert_eq!(first.groups, cached.groups);
    bank.clear_mods();
    let replaced = bank
        .mod_music(&active.registry, &"demo:theme".into())
        .unwrap();
    assert_ne!(first.groups, replaced.groups);
}

#[test]
fn missing_malformed_oversized_and_escaping_music_reject_activation() {
    for (file, expected) in [
        ("missing.mus", "missing asset"),
        ("../outside.mus", "parent traversal"),
        ("theme.wav", ".mus file"),
    ] {
        let temp = tempfile::tempdir().unwrap();
        let mut content = music_pack();
        content["music"][0]["file"] = json!(file);
        install(temp.path(), "demo", content, &theme(60));
        assert!(error(build(temp.path(), &["demo"])).contains(expected));
    }
    let temp = tempfile::tempdir().unwrap();
    install(temp.path(), "demo", music_pack(), b"MThd");
    assert!(error(build(temp.path(), &["demo"])).contains("invalid MUS signature"));
    fs::write(
        temp.path().join("demo/theme.mus"),
        vec![0; sound::MAX_MUSIC_BYTES + 1],
    )
    .unwrap();
    assert!(error(build(temp.path(), &["demo"])).contains("128 KiB"));
}

#[cfg(unix)]
#[test]
fn music_symlinks_cannot_escape_package_ownership() {
    let temp = tempfile::tempdir().unwrap();
    install(temp.path(), "demo", music_pack(), &theme(60));
    let outside = temp.path().join("outside.mus");
    fs::write(&outside, theme(67)).unwrap();
    fs::remove_file(temp.path().join("demo/theme.mus")).unwrap();
    std::os::unix::fs::symlink(&outside, temp.path().join("demo/theme.mus")).unwrap();
    assert!(sound::load_music(&temp.path().join("demo"), "theme.mus").is_err());
    assert!(!modding::discover(temp.path()).errors.is_empty());
}

#[test]
fn mod_mus_has_bounded_events_density_channels_and_duration() {
    assert!(sound::decode_music(&mus(&[0x60], 1)).is_err());
    assert!(sound::decode_music(&mus(&[0x90, 188, 100, 1, 0x60], 16)).is_err());
    let mut simultaneous = vec![0x10, 60].repeat(256);
    simultaneous.extend([0x90, 60, 1, 0x60]);
    assert!(error(sound::decode_music(&mus(&simultaneous, 1))).contains("256 events"));
    let mut events = vec![0x90, 60, 1].repeat(16385);
    events.push(0x60);
    assert!(error(sound::decode_music(&mus(&events, 1))).contains("16384 events"));
    // 126001 encoded as a MUS base-128 time delta.
    assert!(
        error(sound::decode_music(&mus(
            &[0x90, 188, 100, 0x87, 0xd8, 0x31, 0x60],
            1
        )))
        .contains("30 minutes")
    );
}

#[test]
fn mod_music_uses_original_fm_music_volume_and_its_declared_loop() {
    let temp = tempfile::tempdir().unwrap();
    let mut content = music_pack();
    content["music"]
        .as_array_mut()
        .unwrap()
        .push(json!({"id":"demo:once","name":"One play","file":"theme.mus","looping":false}));
    install(temp.path(), "demo", content, &theme(60));
    let active = build(temp.path(), &["demo"]).unwrap();
    let mut bank = SoundBank::default();
    let score = bank
        .mod_music(&active.registry, &"demo:theme".into())
        .unwrap();
    let mut looping = Mixer::new(44100, &instruments()).unwrap();
    looping.music_volume = 127;
    looping.fx_volume = 0;
    looping.play_with_fade(
        score.clone(),
        active.registry.music[&"demo:theme".into()].looping,
        true,
    );
    let mut first = vec![0; 44100 * 2];
    looping.mix(&mut first);
    assert!(first.iter().any(|value| *value != 0));
    looping.music_volume = 0;
    let mut muted = vec![1; 4096];
    looping.mix(&mut muted);
    assert!(muted.iter().all(|value| *value == 0));
    looping.fx_volume = 127;
    looping.sample(
        DigitalSample {
            rate: 11025,
            data: vec![220; 500],
        },
        127,
        128,
        100,
        1,
    );
    looping.mix(&mut muted);
    assert!(muted.iter().any(|value| *value != 0));
    looping.music_volume = 127;
    looping.fx_volume = 0;
    let mut repeating_tail = vec![0; 44100 * 2];
    looping.mix(&mut repeating_tail);
    assert!(repeating_tail.iter().any(|value| *value != 0));
    let mut once = Mixer::new(44100, &instruments()).unwrap();
    once.music_volume = 127;
    once.play_with_fade(
        score,
        active.registry.music[&"demo:once".into()].looping,
        true,
    );
    once.mix(&mut first);
    let mut ended_tail = vec![0; 44100 * 2];
    once.mix(&mut ended_tail);
    let repeating_energy: u64 = repeating_tail
        .iter()
        .map(|value| value.unsigned_abs() as u64)
        .sum();
    let ended_energy: u64 = ended_tail
        .iter()
        .map(|value| value.unsigned_abs() as u64)
        .sum();
    assert!(
        ended_energy < repeating_energy / 20,
        "ended energy {ended_energy}, loop energy {repeating_energy}"
    );
}
