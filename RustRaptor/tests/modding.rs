use raptor_replica::{
    content::{ContentId, ContentPack, Registry},
    modding::{self, ActiveMods, Command, Manifest, ScriptRuntime},
    persistence::Pilot,
    simulation::{Input, World},
};
use serde_json::{Value, json};
use std::{collections::BTreeMap, fs, path::Path};

fn pack(value: Value) -> ContentPack {
    serde_json::from_value(value).unwrap()
}
fn item(id: &str, price: u32) -> Value {
    json!({"id": id, "name": id, "price": price, "max_count": 100})
}
fn base() -> Registry {
    let mut reg = Registry::default();
    reg.apply(pack(json!({
        "weapons": [{"id":"base:projectile_forward_guns", "name":"Forward Guns", "damage":1,"speed":8,"cooldown":2,"behavior":"straight","target":"all"}],
        "items": [
            {"id":"base:forward_guns","name":"Forward Guns","price":0,"weapon":"base:projectile_forward_guns"},
            {"id":"base:energy","name":"Shield","price":0,"max_count":100}
        ],
        "missions":[{"id":"base:sector_1_wave_1","name":"Test Mission","duration":1000}]
    })), "base").unwrap();
    reg.validate().unwrap();
    reg
}
fn install(root: &Path, folder: &str, id: &str, content: Value) -> Manifest {
    let dir = root.join(folder);
    fs::create_dir_all(&dir).unwrap();
    let manifest = Manifest {
        id: id.into(),
        name: id.into(),
        version: "1.0.0".into(),
        api_version: 1,
        description: String::new(),
        dependencies: BTreeMap::new(),
        conflicts: vec![],
        content: "content.json".into(),
        scripts: vec![],
    };
    write_manifest(&dir, &manifest);
    fs::write(
        dir.join("content.json"),
        serde_json::to_vec_pretty(&content).unwrap(),
    )
    .unwrap();
    manifest
}
fn write_manifest(dir: &Path, manifest: &Manifest) {
    fs::write(dir.join("mod.toml"), toml::to_string(manifest).unwrap()).unwrap();
}
fn ids(values: &[&str]) -> Vec<String> {
    values.iter().map(|v| (*v).into()).collect()
}
fn error<T>(result: anyhow::Result<T>) -> String {
    match result {
        Ok(_) => panic!("expected failure"),
        Err(e) => format!("{e:#}"),
    }
}

#[test]
fn dependencies_load_before_dependents_and_keep_independent_priority() {
    let temp = tempfile::tempdir().unwrap();
    install(temp.path(), "alpha", "alpha", json!({}));
    let mut beta = install(temp.path(), "beta", "beta", json!({}));
    beta.dependencies.insert("alpha".into(), "^1.0".into());
    write_manifest(&temp.path().join("beta"), &beta);
    install(temp.path(), "gamma", "gamma", json!({}));
    let d = modding::discover(temp.path());
    assert!(d.errors.is_empty());
    assert_eq!(
        modding::order(&d, &ids(&["gamma", "beta", "alpha"])).unwrap(),
        ids(&["gamma", "alpha", "beta"])
    );
}

#[test]
fn missing_disabled_wrong_version_and_cyclic_dependencies_are_actionable() {
    let temp = tempfile::tempdir().unwrap();
    let mut alpha = install(temp.path(), "alpha", "alpha", json!({}));
    let mut beta = install(temp.path(), "beta", "beta", json!({}));
    beta.dependencies.insert("alpha".into(), "^2".into());
    write_manifest(&temp.path().join("beta"), &beta);
    let d = modding::discover(temp.path());
    assert!(error(modding::order(&d, &ids(&["beta"]))).contains("requires enabled mod alpha"));
    assert!(error(modding::order(&d, &ids(&["alpha", "beta"]))).contains("installed 1.0.0"));
    beta.dependencies.insert("alpha".into(), "^1".into());
    alpha.dependencies.insert("beta".into(), "^1".into());
    write_manifest(&temp.path().join("beta"), &beta);
    write_manifest(&temp.path().join("alpha"), &alpha);
    assert!(
        error(modding::order(
            &modding::discover(temp.path()),
            &ids(&["alpha", "beta"])
        ))
        .contains("cyclic")
    );
}

#[test]
fn api_conflicts_and_duplicate_selected_ids_reject_activation() {
    let temp = tempfile::tempdir().unwrap();
    let mut alpha = install(temp.path(), "alpha", "alpha", json!({}));
    install(temp.path(), "beta", "beta", json!({}));
    alpha.api_version = 99;
    write_manifest(&temp.path().join("alpha"), &alpha);
    assert!(
        error(modding::order(
            &modding::discover(temp.path()),
            &ids(&["alpha"])
        ))
        .contains("requires API 99")
    );
    alpha.api_version = 1;
    alpha.conflicts.push("beta".into());
    write_manifest(&temp.path().join("alpha"), &alpha);
    let d = modding::discover(temp.path());
    assert!(error(modding::order(&d, &ids(&["alpha", "beta"]))).contains("conflicts with beta"));
    assert!(error(modding::order(&d, &ids(&["beta", "beta"]))).contains("duplicate mod"));
}

#[test]
fn every_duplicate_installed_namespace_is_unusable() {
    let temp = tempfile::tempdir().unwrap();
    for folder in ["first", "second", "third"] {
        install(temp.path(), folder, "collision", json!({}));
    }
    let d = modding::discover(temp.path());
    assert!(!d.mods.contains_key("collision"));
    assert_eq!(d.errors.len(), 2);
    assert!(
        error(ActiveMods::build(&base(), &d, &ids(&["collision"]), None)).contains("not installed")
    );
}

#[test]
fn adding_a_duplicate_after_discovery_requires_rescanning() {
    let temp = tempfile::tempdir().unwrap();
    install(temp.path(), "first", "alpha", json!({}));
    let original = modding::discover(temp.path());
    install(temp.path(), "second", "alpha", json!({}));
    let message = error(ActiveMods::build(
        &base(),
        &original,
        &ids(&["alpha"]),
        None,
    ));
    assert!(message.contains("duplicated since discovery") && message.contains("rescan"));
}

#[test]
fn changed_files_require_a_new_discovery_snapshot() {
    let temp = tempfile::tempdir().unwrap();
    install(
        temp.path(),
        "alpha",
        "alpha",
        json!({"items":[item("alpha:cell", 10)]}),
    );
    let original = modding::discover(temp.path());
    let before = ActiveMods::build(&base(), &original, &ids(&["alpha"]), None).unwrap();
    fs::write(
        temp.path().join("alpha/content.json"),
        serde_json::to_vec(&json!({"items":[item("alpha:cell", 12)]})).unwrap(),
    )
    .unwrap();
    assert!(
        error(ActiveMods::build(
            &base(),
            &original,
            &ids(&["alpha"]),
            None
        ))
        .contains("rescan")
    );
    let after = ActiveMods::build(
        &base(),
        &modding::discover(temp.path()),
        &ids(&["alpha"]),
        None,
    )
    .unwrap();
    assert_ne!(before.pins[0].hash, after.pins[0].hash);
    assert_eq!(
        after.registry.items[&ContentId::from("alpha:cell")].price,
        12
    );
}

#[test]
fn package_hash_covers_added_assets_and_manifest_changes() {
    let temp = tempfile::tempdir().unwrap();
    let mut manifest = install(temp.path(), "alpha", "alpha", json!({}));
    let d = modding::discover(temp.path());
    fs::write(temp.path().join("alpha/readme.txt"), "Extra package file").unwrap();
    assert!(error(ActiveMods::build(&base(), &d, &ids(&["alpha"]), None)).contains("rescan"));
    let d = modding::discover(temp.path());
    manifest.version = "1.0.1".into();
    write_manifest(&temp.path().join("alpha"), &manifest);
    assert!(error(ActiveMods::build(&base(), &d, &ids(&["alpha"]), None)).contains("rescan"));
}

#[test]
fn package_paths_depth_and_size_are_bounded() {
    let temp = tempfile::tempdir().unwrap();
    let mut m = install(temp.path(), "traversal", "traversal", json!({}));
    m.content = "../outside.json".into();
    write_manifest(&temp.path().join("traversal"), &m);
    install(temp.path(), "deep", "deep", json!({}));
    let mut nested = temp.path().join("deep");
    for _ in 0..17 {
        nested = nested.join("nested");
    }
    fs::create_dir_all(nested).unwrap();
    install(temp.path(), "large", "large", json!({}));
    fs::File::create(temp.path().join("large/huge.bin"))
        .unwrap()
        .set_len(64 * 1024 * 1024 + 1)
        .unwrap();
    let d = modding::discover(temp.path());
    assert!(d.mods.is_empty());
    assert!(d.errors.iter().any(|e| e.contains("parent traversal")));
    assert!(d.errors.iter().any(|e| e.contains("depth exceeds")));
    assert!(d.errors.iter().any(|e| e.contains("64 MiB")));
}

#[cfg(unix)]
#[test]
fn symlink_folders_and_files_are_rejected() {
    use std::os::unix::fs::symlink;
    let temp = tempfile::tempdir().unwrap();
    install(temp.path(), "alpha", "alpha", json!({}));
    symlink("/etc/passwd", temp.path().join("alpha/link")).unwrap();
    symlink(temp.path().join("alpha"), temp.path().join("alias")).unwrap();
    let d = modding::discover(temp.path());
    assert!(d.mods.is_empty());
    assert_eq!(d.errors.len(), 2);
    assert!(d.errors.iter().all(|e| e.contains("symlink")));
}

#[test]
fn invalid_manifest_versions_and_duplicate_sources_fail_discovery() {
    let temp = tempfile::tempdir().unwrap();
    let mut m = install(temp.path(), "alpha", "alpha", json!({}));
    m.dependencies
        .insert("beta".into(), "obviously invalid".into());
    write_manifest(&temp.path().join("alpha"), &m);
    assert!(modding::discover(temp.path()).mods.is_empty());
    m.dependencies.clear();
    m.scripts = ids(&["script.rhai", "script.rhai"]);
    fs::write(temp.path().join("alpha/script.rhai"), "").unwrap();
    write_manifest(&temp.path().join("alpha"), &m);
    assert!(modding::discover(temp.path()).errors[0].contains("duplicate script"));
}

#[test]
fn later_explicit_overrides_win_and_report_the_previous_owner() {
    let temp = tempfile::tempdir().unwrap();
    install(
        temp.path(),
        "alpha",
        "alpha",
        json!({"items":[item("base:energy", 10)], "overrides":["base:energy"]}),
    );
    install(
        temp.path(),
        "beta",
        "beta",
        json!({"items":[item("base:energy", 20)], "overrides":["base:energy"]}),
    );
    let d = modding::discover(temp.path());
    let active = ActiveMods::build(&base(), &d, &ids(&["alpha", "beta"]), None).unwrap();
    assert_eq!(
        active.registry.items[&ContentId::from("base:energy")].price,
        20
    );
    assert_eq!(
        active.registry.owners[&ContentId::from("base:energy")],
        "beta"
    );
    assert_eq!(
        active.registry.overrides,
        ids(&["base:energy: base -> alpha", "base:energy: alpha -> beta"])
    );
    let reversed = ActiveMods::build(&base(), &d, &ids(&["beta", "alpha"]), None).unwrap();
    assert_eq!(
        reversed.registry.items[&ContentId::from("base:energy")].price,
        10
    );
}

#[test]
fn accidental_duplicates_type_changes_and_failed_packs_leave_registry_intact() {
    let mut registry = base();
    let previous = registry.items.len();
    assert!(
        registry
            .apply(
                pack(json!({"items":[item("alpha:valid", 1), item("base:energy", 2)]})),
                "alpha"
            )
            .is_err()
    );
    assert_eq!(registry.items.len(), previous);
    assert!(
        !registry
            .owners
            .contains_key(&ContentId::from("alpha:valid"))
    );
    assert!(
        registry
            .apply(
                pack(json!({"items":[item("alpha:twice", 1), item("alpha:twice", 2)]})),
                "alpha"
            )
            .is_err()
    );
    assert!(registry.apply(pack(json!({"enemies":[{"id":"base:energy","name":"Wrong type"}],"overrides":["base:energy"]})), "alpha").is_err());
    assert!(
        registry
            .apply(pack(json!({"items":[item("foreign:cell", 1)]})), "alpha")
            .is_err()
    );
    assert!(
        registry
            .apply(
                pack(json!({"items":[item("alpha:new", 1)],"overrides":["alpha:new"]})),
                "alpha"
            )
            .is_err()
    );
}

#[test]
fn content_references_and_undeclared_scripts_reject_the_whole_mod() {
    let temp = tempfile::tempdir().unwrap();
    install(
        temp.path(),
        "alpha",
        "alpha",
        json!({"items":[{"id":"alpha:cell","name":"Cell","price":1,"weapon":"alpha:missing"}]}),
    );
    assert!(
        error(ActiveMods::build(
            &base(),
            &modding::discover(temp.path()),
            &ids(&["alpha"]),
            None
        ))
        .contains("missing weapon")
    );
    fs::write(temp.path().join("alpha/content.json"), serde_json::to_vec(&json!({"items":[{"id":"alpha:cell","name":"Cell","price":1,"script":"undeclared.rhai"}]})).unwrap()).unwrap();
    assert!(
        error(ActiveMods::build(
            &base(),
            &modding::discover(temp.path()),
            &ids(&["alpha"]),
            None
        ))
        .contains("manifest.scripts")
    );
}

#[test]
fn script_failure_rolls_back_world_state_and_deterministic_rng() {
    let mut registry = base();
    registry
        .missions
        .get_mut(&ContentId::from("base:sector_1_wave_1"))
        .unwrap()
        .script = Some("mission.rhai".into());
    let mut runtime = ScriptRuntime::new();
    runtime
        .add(
            "base",
            "mission.rhai",
            r#"fn on_mission_start(e,s,r) {
        #{commands:[#{op:"credits",amount:7}, #{op:"move",entity:999,x:0,y:0}],state:#{random:r[0]}}
    }"#,
        )
        .unwrap();
    let pilot = Pilot::default();
    let mut world = World::new(&pilot.mission, &pilot, &registry).unwrap();
    let before = world.digest();
    assert!(
        world
            .step(Input::default(), &registry, &mut runtime)
            .is_err()
    );
    assert_eq!(world.digest(), before);
    assert!(runtime.states.is_empty());
    assert!(runtime.rng.is_empty());
    let source = r#"fn on_mission_start(e,s,r) { #{commands:[#{op:"credits",amount:r[0]}],state:#{random:r[0]}} }"#;
    runtime.add("base", "mission.rhai", source).unwrap();
    world
        .step(Input::default(), &registry, &mut runtime)
        .unwrap();
    let mut fresh_runtime = ScriptRuntime::new();
    fresh_runtime.add("base", "mission.rhai", source).unwrap();
    let mut fresh_world = World::new(&pilot.mission, &pilot, &registry).unwrap();
    fresh_world
        .step(Input::default(), &registry, &mut fresh_runtime)
        .unwrap();
    assert_eq!(world.digest(), fresh_world.digest());
    assert_eq!(runtime.states, fresh_runtime.states);
    assert_eq!(runtime.rng, fresh_runtime.rng);
}

#[test]
fn command_batches_are_atomic_even_after_an_earlier_valid_command() {
    let registry = base();
    let pilot = Pilot::default();
    let mut world = World::new(&pilot.mission, &pilot, &registry).unwrap();
    let before = world.digest();
    let commands = [
        Command::Credits { amount: 100 },
        Command::Spawn {
            enemy: "missing:enemy".into(),
            x: 0,
            y: 0,
        },
    ];
    assert!(world.apply_commands(&commands, &registry).is_err());
    assert_eq!(world.digest(), before);
}

#[test]
fn malformed_result_excessive_commands_and_oversized_state_are_rejected() {
    let mut runtime = ScriptRuntime::new();
    for (source, expected) in [
        (
            r#"fn on_tick(e,s,r) { #{commands:[#{op:"unknown"}],state:#{}} }"#,
            "invalid result",
        ),
        (
            r#"fn on_tick(e,s,r) { let a=[]; for i in 0..257 { a.push(#{op:"complete"}); } #{commands:a,state:#{}} }"#,
            "too many commands",
        ),
        (
            r#"fn on_tick(e,s,r) { let a=[]; for i in 0..4000 { a.push(999999999999999999); } #{commands:[],state:a} }"#,
            "state exceeds",
        ),
    ] {
        runtime.begin_tick();
        runtime.add("test", "limits.rhai", source).unwrap();
        let message = error(runtime.invoke("test", "limits.rhai", "on_tick", &json!({}), 17));
        assert!(
            message.contains(expected),
            "expected {expected}, got {message}"
        );
        assert!(runtime.states.is_empty());
        assert!(runtime.rng.is_empty());
    }
}

#[test]
fn execution_budget_is_shared_across_callbacks_and_resets_per_tick() {
    let mut runtime = ScriptRuntime::new();
    runtime.add("test", "budget.rhai", r#"fn on_tick(e,s,r) { let x=0; for n in 0..2500 { x+=1; } #{commands:[],state:#{iterations:x}} }"#).unwrap();
    runtime.begin_tick();
    let mut success = 0;
    for _ in 0..100 {
        if runtime
            .invoke("test", "budget.rhai", "on_tick", &json!({}), 1)
            .is_err()
        {
            break;
        }
        success += 1;
    }
    assert!(
        success > 1 && success < 100,
        "successful callbacks: {success}"
    );
    runtime.begin_tick();
    runtime
        .invoke("test", "budget.rhai", "on_tick", &json!({}), 1)
        .unwrap();
}

#[test]
fn missing_hook_does_not_advance_rng_or_state() {
    let mut runtime = ScriptRuntime::new();
    runtime
        .add(
            "test",
            "empty.rhai",
            "fn other(e,s,r) { #{commands:[],state:s} }",
        )
        .unwrap();
    assert!(
        runtime
            .invoke("test", "empty.rhai", "on_tick", &json!({}), 1)
            .unwrap()
            .is_empty()
    );
    assert!(runtime.states.is_empty());
    assert!(runtime.rng.is_empty());
}

#[test]
fn saves_allow_added_mods_while_preserving_required_versions_and_order() {
    let registry = base();
    let pin = |id: &str| modding::ModPin {
        id: id.into(),
        version: "1.0.0".into(),
        hash: format!("{id}-content"),
    };
    let a = pin("alpha");
    let b = pin("beta");
    let c = pin("extra");
    let mut pilot = Pilot::default();
    assert!(pilot.validate(&registry, &[a.clone(), b.clone()]).is_ok());
    pilot.mods = vec![a.clone(), b.clone()];
    pilot
        .script_state
        .insert("alpha/ai.rhai".into(), json!({"kills": 17}));
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("pilot.json");
    pilot.save(&path).unwrap();
    let before = fs::read(&path).unwrap();
    let loaded = Pilot::load(&path, &registry, &[a.clone(), c, b.clone()]).unwrap();
    assert_eq!(loaded.script_state, pilot.script_state);
    assert!(Pilot::load(&path, &registry, &[b.clone(), a.clone()]).is_err());
    assert!(Pilot::load(&path, &registry, &[a.clone()]).is_err());
    let mut changed = b;
    changed.version = "2.0.0".into();
    assert!(Pilot::load(&path, &registry, &[a, changed]).is_err());
    assert_eq!(fs::read(path).unwrap(), before);
}

#[test]
fn incompatible_save_pins_and_disabled_equipment_do_not_modify_the_save() {
    let temp = tempfile::tempdir().unwrap();
    install(
        temp.path(),
        "alpha",
        "alpha",
        json!({"items":[item("alpha:cell", 1)]}),
    );
    let active = ActiveMods::build(
        &base(),
        &modding::discover(temp.path()),
        &ids(&["alpha"]),
        None,
    )
    .unwrap();
    let mut pilot = Pilot::default();
    pilot.mods = active.pins.clone();
    pilot.inventory.insert("alpha:cell".into(), 1);
    let path = temp.path().join("pilot.json");
    pilot.save(&path).unwrap();
    let before = fs::read(&path).unwrap();
    Pilot::load(&path, &active.registry, &active.pins).unwrap();
    assert!(error(Pilot::load(&path, &base(), &[])).contains("enable the matching mods"));
    let mut changed = active.pins.clone();
    changed[0].hash = "different-content-hash".into();
    assert!(Pilot::load(&path, &active.registry, &changed).is_err());
    assert!(
        error(Pilot::load(&path, &base(), &active.pins))
            .contains("saved item alpha:cell is unavailable")
    );
    assert_eq!(fs::read(path).unwrap(), before);
}

#[test]
fn saved_script_state_and_rng_resume_the_same_callback_sequence() {
    let mut runtime = ScriptRuntime::new();
    let source = r#"fn on_tick(e,s,r) { let n=if s.contains("n") {s.n+1} else {1}; #{commands:[#{op:"credits",amount:r[0]}],state:#{n:n,last:r[0]}} }"#;
    runtime.add("test", "state.rhai", source).unwrap();
    runtime
        .invoke("test", "state.rhai", "on_tick", &json!({}), 42)
        .unwrap();
    let mut pilot = Pilot::default();
    pilot.script_state = runtime.states.clone();
    pilot.script_rng = runtime.rng.clone();
    let restored_pilot: Pilot =
        serde_json::from_slice(&serde_json::to_vec(&pilot).unwrap()).unwrap();
    let mut restored = ScriptRuntime::new();
    restored.add("test", "state.rhai", source).unwrap();
    restored.states = restored_pilot.script_state;
    restored.rng = restored_pilot.script_rng;
    let a = runtime
        .invoke("test", "state.rhai", "on_tick", &json!({}), 42)
        .unwrap();
    let b = restored
        .invoke("test", "state.rhai", "on_tick", &json!({}), 42)
        .unwrap();
    assert_eq!(
        serde_json::to_value(a).unwrap(),
        serde_json::to_value(b).unwrap()
    );
    assert_eq!(runtime.states, restored.states);
    assert_eq!(runtime.rng, restored.rng);
}

#[test]
fn example_mod_compiles_and_its_weapon_enemy_item_and_mission_hooks_execute() {
    let dir = Path::new(env!("CARGO_MANIFEST_DIR")).join("mods");
    let mut active =
        ActiveMods::build(&base(), &modding::discover(&dir), &ids(&["aurora"]), None).unwrap();
    assert!(
        active
            .registry
            .weapons
            .contains_key(&ContentId::from("aurora:pulse_projectile"))
    );
    assert!(
        active
            .registry
            .items
            .contains_key(&ContentId::from("aurora:pulse_cannon"))
    );
    assert!(
        active
            .registry
            .enemies
            .contains_key(&ContentId::from("aurora:weaver"))
    );
    assert!(
        active
            .registry
            .campaigns
            .contains_key(&ContentId::from("aurora:trials"))
    );
    let mission = ContentId::from("aurora:field_trials");
    let pilot = Pilot::default();
    let mut world = World::new(&mission, &pilot, &active.registry).unwrap();
    world
        .step(Input::default(), &active.registry, &mut active.scripts)
        .unwrap();
    assert_eq!(
        world
            .player
            .inventory
            .get(&ContentId::from("aurora:pulse_cannon")),
        Some(&1)
    );
    world
        .step(
            Input {
                fire: true,
                ..Input::default()
            },
            &active.registry,
            &mut active.scripts,
        )
        .unwrap();
    assert_eq!(
        active.scripts.states["aurora/scripts/weapon.rhai"]["shots"],
        1
    );
    assert!(
        world
            .projectiles
            .iter()
            .filter(|p| p.weapon.0 == "aurora:pulse_projectile")
            .count()
            >= 3
    );
    let entity = world
        .spawn(&ContentId::from("aurora:weaver"), 60, 30, &active.registry)
        .unwrap();
    world
        .step(Input::default(), &active.registry, &mut active.scripts)
        .unwrap();
    assert_eq!(
        world
            .enemies
            .iter()
            .find(|e| e.entity == entity)
            .unwrap()
            .vx,
        1
    );
    let commands = active
        .scripts
        .invoke(
            "aurora",
            "scripts/cell.rhai",
            "on_pickup",
            &json!({"entity":1}),
            0,
        )
        .unwrap();
    world.apply_commands(&commands, &active.registry).unwrap();
    assert_eq!(world.player.credits, 25);
}

#[test]
fn png_strips_are_validated_without_the_original_catalog() {
    let temp = tempfile::tempdir().unwrap();
    let art = json!({"png":"cell.png","logical_width":1,"logical_height":1,"frames":2});
    install(
        temp.path(),
        "alpha",
        "alpha",
        json!({"items":[{"id":"alpha:cell","name":"Cell","price":1,"art":art}]}),
    );
    image::RgbaImage::from_pixel(3, 1, image::Rgba([20, 40, 60, 255]))
        .save(temp.path().join("alpha/cell.png"))
        .unwrap();
    let message = error(ActiveMods::build(
        &base(),
        &modding::discover(temp.path()),
        &ids(&["alpha"]),
        None,
    ));
    assert!(message.contains("strip width"));
    image::RgbaImage::from_pixel(4, 2, image::Rgba([20, 40, 60, 255]))
        .save(temp.path().join("alpha/cell.png"))
        .unwrap();
    ActiveMods::build(
        &base(),
        &modding::discover(temp.path()),
        &ids(&["alpha"]),
        None,
    )
    .unwrap();
}

#[test]
fn callback_arity_and_source_size_are_checked_before_activation() {
    let mut runtime = ScriptRuntime::new();
    assert!(
        error(runtime.add("test", "bad.rhai", "fn on_fire(event,state) { state }"))
            .contains("callbacks require")
    );
    assert!(
        error(runtime.add("test", "huge.rhai", &" ".repeat(1024 * 1024 + 1)))
            .contains("source exceeds 1 MiB")
    );
}

#[test]
fn callbacks_can_query_player_entities_projectiles_pickups_and_objectives() {
    let mut registry = base();
    registry
        .missions
        .get_mut(&ContentId::from("base:sector_1_wave_1"))
        .unwrap()
        .script = Some("queries.rhai".into());
    let mut runtime = ScriptRuntime::new();
    runtime.add("base", "queries.rhai", r#"fn on_mission_start(e,s,r) {
        #{commands:[],state:#{shield:e.player.shield,inventory:e.player.inventory,
          enemies:e.entities.len,shots:e.projectiles.len,pickups:e.pickups.len,objectives:e.objectives}}
    }"#).unwrap();
    let pilot = Pilot::default();
    let mut world = World::new(&pilot.mission, &pilot, &registry).unwrap();
    world
        .step(Input::default(), &registry, &mut runtime)
        .unwrap();
    let state = &runtime.states["base/queries.rhai"];
    assert_eq!(state["shield"], 100);
    assert_eq!(state["inventory"]["base:forward_guns"], 1);
    assert_eq!(state["enemies"], 0);
    assert_eq!(state["shots"], 0);
    assert_eq!(state["pickups"], 0);
    assert_eq!(state["objectives"], json!({}));
}

#[test]
fn consumable_special_items_run_on_use_once_per_button_press() {
    let mut registry = base();
    registry
        .apply(
            pack(json!({"items":[{
                "id":"test:repair","name":"Repair","price":5,"max_count":10,"shield":7,
                "special":true,"consumable":true,"script":"repair.rhai"
            }]})),
            "test",
        )
        .unwrap();
    let mut runtime = ScriptRuntime::new();
    runtime
        .add(
            "test",
            "repair.rhai",
            r#"fn on_use(e,s,r) {
        let n=if s.contains("n") {s.n+1} else {1};
        #{commands:[#{op:"credits",amount:5}],state:#{n:n}}
    }"#,
        )
        .unwrap();
    let mut pilot = Pilot::default();
    pilot.inventory.insert("base:energy".into(), 50);
    pilot.inventory.insert("test:repair".into(), 2);
    pilot.selected = Some("test:repair".into());
    let mut world = World::new(&pilot.mission, &pilot, &registry).unwrap();
    let input = Input {
        special: true,
        ..Input::default()
    };
    world.step(input, &registry, &mut runtime).unwrap();
    world.step(input, &registry, &mut runtime).unwrap();
    assert_eq!(world.player.shield, 57);
    assert_eq!(world.player.inventory[&ContentId::from("test:repair")], 1);
    assert_eq!(runtime.states["test/repair.rhai"]["n"], 1);
    world
        .step(Input::default(), &registry, &mut runtime)
        .unwrap();
    world.step(input, &registry, &mut runtime).unwrap();
    assert_eq!(world.player.shield, 64);
    assert_eq!(world.player.credits, 10);
    assert_eq!(runtime.states["test/repair.rhai"]["n"], 2);
}

#[test]
fn wall_clock_sleep_and_indirect_native_calls_are_not_exposed() {
    let mut runtime = ScriptRuntime::new();
    for source in [
        "fn on_tick(e,s,r) { timestamp(); #{commands:[],state:s} }",
        "fn on_tick(e,s,r) { sleep(0); #{commands:[],state:s} }",
        "fn on_tick(e,s,r) { let f=Fn(\"sleep\"); f.call(0); #{commands:[],state:s} }",
        "fn on_tick(e,s,r) { let f=Fn(\"timestamp\"); f.call(); #{commands:[],state:s} }",
    ] {
        runtime.begin_tick();
        runtime.add("test", "unsafe.rhai", source).unwrap();
        let message = error(runtime.invoke("test", "unsafe.rhai", "on_tick", &json!({}), 1));
        assert!(message.contains("Function not found"), "{message}");
    }
    assert!(runtime.states.is_empty());
    assert!(runtime.rng.is_empty());
}

#[test]
fn dynamic_eval_and_imports_cannot_be_reintroduced_by_function_pointers() {
    let mut runtime = ScriptRuntime::new();
    assert!(
        runtime
            .add("test", "eval.rhai", "fn on_tick(e,s,r) { eval(\"42\"); }")
            .is_err()
    );
    assert!(
        runtime
            .add("test", "imports.rhai", "import \"external\" as x;")
            .is_err()
    );
    runtime
        .add(
            "test",
            "indirect.rhai",
            "fn on_tick(e,s,r) { let f=Fn(\"eval\"); f.call(\"42\"); #{commands:[],state:s} }",
        )
        .unwrap();
    assert!(
        runtime
            .invoke("test", "indirect.rhai", "on_tick", &json!({}), 1)
            .is_err()
    );
}

#[test]
fn script_inventory_commands_preserve_the_twenty_item_capacity() {
    let mut registry = base();
    let extra: Vec<_> = (0..19)
        .map(|n| item(&format!("test:item_{n}"), 1))
        .collect();
    registry
        .apply(pack(json!({"items":extra})), "test")
        .unwrap();
    let pilot = Pilot::default();
    let mut world = World::new(&pilot.mission, &pilot, &registry).unwrap();
    for n in 0..18 {
        world
            .apply_commands(
                &[Command::GiveItem {
                    item: format!("test:item_{n}"),
                    count: 1,
                }],
                &registry,
            )
            .unwrap();
    }
    assert_eq!(world.player.inventory.len(), 20);
    let before = world.digest();
    assert!(
        world
            .apply_commands(
                &[Command::GiveItem {
                    item: "test:item_18".into(),
                    count: 1
                }],
                &registry
            )
            .is_err()
    );
    assert_eq!(before, world.digest());
    world
        .apply_commands(
            &[Command::GiveItem {
                item: "test:item_0".into(),
                count: 1,
            }],
            &registry,
        )
        .unwrap();
    assert_eq!(world.player.inventory[&ContentId::from("test:item_0")], 2);
}

#[test]
fn existing_objectives_remain_updatable_at_the_capacity_limit() {
    let registry = base();
    let pilot = Pilot::default();
    let mut world = World::new(&pilot.mission, &pilot, &registry).unwrap();
    for n in 0..1024 {
        world.objectives.insert(format!("test:{n}"), 0);
    }
    world
        .apply_commands(
            &[Command::Objective {
                key: "test:0".into(),
                value: 10,
            }],
            &registry,
        )
        .unwrap();
    assert_eq!(world.objectives["test:0"], 10);
    assert!(
        world
            .apply_commands(
                &[Command::Objective {
                    key: "test:new".into(),
                    value: 1
                }],
                &registry
            )
            .is_err()
    );
    assert_eq!(world.objectives.len(), 1024);
}

#[test]
fn enemy_weapons_and_enemies_receive_fire_and_damage_hooks() {
    let mut registry = base();
    registry.apply(pack(json!({
        "weapons":[{"id":"test:bolt","name":"Bolt","damage":1,"speed":1,"cooldown":2,"behavior":"straight","target":"all","script":"weapon.rhai"}],
        "enemies":[{"id":"test:fighter","name":"Fighter","health":100,"speed":1,"cooldown":2,"weapon":"test:bolt","script":"enemy.rhai"}]
    })), "test").unwrap();
    let mut runtime = ScriptRuntime::new();
    runtime
        .add(
            "test",
            "weapon.rhai",
            r#"fn on_fire(e,s,r) {
        #{commands:[],state:#{hostile:e.hostile,entity:e.entity}}
    }"#,
        )
        .unwrap();
    runtime
        .add(
            "test",
            "enemy.rhai",
            r#"fn on_fire(e,s,r) { #{commands:[],state:#{fired:true}} }
        fn on_hit(e,s,r) { s.hit=e.damage; s.scripted=e.scripted; #{commands:[],state:s} }"#,
        )
        .unwrap();
    let pilot = Pilot::default();
    let mut world = World::new(&pilot.mission, &pilot, &registry).unwrap();
    let entity = world
        .spawn(&ContentId::from("test:fighter"), 30, 30, &registry)
        .unwrap();
    world
        .step(Input::default(), &registry, &mut runtime)
        .unwrap();
    assert_eq!(runtime.states["test/weapon.rhai"]["hostile"], true);
    assert_eq!(runtime.states["test/weapon.rhai"]["entity"], entity);
    assert_eq!(runtime.states["test/enemy.rhai"]["fired"], true);
    world
        .apply_commands(&[Command::Damage { entity, amount: 7 }], &registry)
        .unwrap();
    world
        .step(Input::default(), &registry, &mut runtime)
        .unwrap();
    assert_eq!(runtime.states["test/enemy.rhai"]["hit"], 7);
    assert_eq!(runtime.states["test/enemy.rhai"]["scripted"], true);
}
