//! Portable assembly/progression checks use synthetic resources; the ignored
//! playable route requires the original untracked game catalog.
use raptor_replica::{
    assets::Catalog,
    content::{ContentPack, Registry},
    mod_selection,
    modding::{self, ActiveMods, Manifest},
    persistence::Pilot,
    simulation::{Input, Outcome, World},
};
use serde_json::{Value, json};
use std::{
    collections::BTreeSet,
    fs,
    path::{Path, PathBuf},
    sync::OnceLock,
};

const CAMPAIGN: &str = "iron_coast_campaign";
const MISSIONS: [&str; 6] = [
    "iron_coast_mission_1:mission_01",
    "iron_coast_mission_2:mission_02",
    "iron_coast_mission_3:mission_03",
    "iron_coast_mission_4:mission_04",
    "iron_coast_mission_5:mission_05",
    "iron_coast_mission_6:mission_06",
];

fn fixture_resources(value: &Value, root: &Path, original: &Path) {
    match value {
        Value::Object(object) => {
            if let (Some(width), Some(height)) = (
                object.get("logical_width").and_then(Value::as_u64),
                object.get("logical_height").and_then(Value::as_u64),
            ) {
                let frames = object.get("frames").and_then(Value::as_u64).unwrap_or(1);
                // Use the minimum valid HD resolution in portable tests. Actual
                // generated 4x artwork is validated separately by the CLI.
                for (key, scale) in [("png", 1), ("hd_png", 2)] {
                    if let Some(file) = object.get(key).and_then(Value::as_str) {
                        let path = root.join(file);
                        fs::create_dir_all(path.parent().unwrap()).unwrap();
                        image::RgbaImage::from_pixel(
                            (width * frames * scale) as u32,
                            (height * scale) as u32,
                            image::Rgba([80, 96, 104, 255]),
                        )
                        .save(path)
                        .unwrap();
                    }
                }
            }
            if let Some(file) = object.get("file").and_then(Value::as_str) {
                let path = root.join(file);
                fs::create_dir_all(path.parent().unwrap()).unwrap();
                if Path::new(file)
                    .extension()
                    .is_some_and(|extension| extension.eq_ignore_ascii_case("mus"))
                {
                    // The new soundtrack is original mod content, independent
                    // of the game catalog, so its bounded score can be tested.
                    fs::copy(original.join(file), path).unwrap();
                } else {
                    let mut wav = Vec::new();
                    wav.extend_from_slice(b"RIFF");
                    wav.extend_from_slice(&100_u32.to_le_bytes());
                    wav.extend_from_slice(b"WAVEfmt ");
                    wav.extend_from_slice(&16_u32.to_le_bytes());
                    wav.extend_from_slice(&1_u16.to_le_bytes());
                    wav.extend_from_slice(&1_u16.to_le_bytes());
                    wav.extend_from_slice(&22050_u32.to_le_bytes());
                    wav.extend_from_slice(&44100_u32.to_le_bytes());
                    wav.extend_from_slice(&2_u16.to_le_bytes());
                    wav.extend_from_slice(&16_u16.to_le_bytes());
                    wav.extend_from_slice(b"data");
                    wav.extend_from_slice(&64_u32.to_le_bytes());
                    wav.extend_from_slice(&[0; 64]);
                    fs::write(path, wav).unwrap();
                }
            }
            for child in object.values() {
                fixture_resources(child, root, original);
            }
        }
        Value::Array(values) => {
            for child in values {
                fixture_resources(child, root, original);
            }
        }
        _ => {}
    }
}

fn fixture_directory() -> &'static Path {
    static FIXTURE: OnceLock<tempfile::TempDir> = OnceLock::new();
    FIXTURE
        .get_or_init(|| {
            let temporary = tempfile::tempdir().unwrap();
            let source = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("mods");
            let mut visited = BTreeSet::new();
            let mut packages = vec![CAMPAIGN.to_string()];
            while let Some(id) = packages.pop() {
                if !visited.insert(id.clone()) {
                    continue;
                }
                let original = source.join(&id);
                let root = temporary.path().join(&id);
                fs::create_dir_all(&root).unwrap();
                let manifest_data = fs::read(original.join("mod.toml")).unwrap();
                let manifest: Manifest =
                    toml::from_str(std::str::from_utf8(&manifest_data).unwrap()).unwrap();
                packages.extend(manifest.dependencies.keys().cloned());
                fs::write(root.join("mod.toml"), manifest_data).unwrap();
                let content = fs::read(original.join(&manifest.content)).unwrap();
                let value: Value = serde_json::from_slice(&content).unwrap();
                fs::write(root.join(&manifest.content), content).unwrap();
                for script in manifest.scripts {
                    let path = root.join(&script);
                    fs::create_dir_all(path.parent().unwrap()).unwrap();
                    fs::copy(original.join(script), path).unwrap();
                }
                fixture_resources(&value, &root, &original);
            }
            temporary
        })
        .path()
}

fn base() -> Registry {
    let mut registry = Registry::default();
    let mut value = json!({
        "weapons":[{"id":"base:projectile_forward_guns","name":"Forward Guns","damage":1,"speed":8,"cooldown":2,"behavior":"straight","target":"all","legacy":0,"art":{"asset":42,"logical_width":4,"logical_height":8,"frames":4}}],
        "items":[
            {"id":"base:forward_guns","name":"Forward Guns","price":0,"max_count":1,"weapon":"base:projectile_forward_guns","legacy":0},
            {"id":"base:energy","name":"Shield","price":10000,"initial_count":25,"max_count":100,"legacy":16},
            {"id":"base:super_shield","name":"Super Shield","price":78500,"initial_count":100,"max_count":100,"legacy":15}
        ],
        "missions":[{"id":"base:sector_1_wave_1","name":"Base fixture","duration":1000}]
    });
    for n in 0..18 {
        value["items"].as_array_mut().unwrap().push(json!({"id":format!("base:fixture_item_{n}"),"name":"Synthetic equipment","price":0,"max_count":1}));
    }
    let pack: ContentPack = serde_json::from_value(value).unwrap();
    registry.apply(pack, "base").unwrap();
    registry.validate().unwrap();
    registry
}

fn discovery() -> modding::Discovery {
    let discovery = modding::discover(fixture_directory());
    assert!(discovery.errors.is_empty(), "{:?}", discovery.errors);
    discovery
}

/// Native IDs are present only to validate the portable dependency graph and
/// first-step inventory grants. These placeholders supply no native behavior.
/// The playable campaign test below uses the original catalog, not this base.
fn structural_base(discovery: &modding::Discovery) -> Registry {
    let mut registry = base();
    let mut native = BTreeSet::new();
    for package in discovery.mods.values() {
        let pack: ContentPack = serde_json::from_slice(
            &fs::read(package.root.join(&package.manifest.content)).unwrap(),
        )
        .unwrap();
        for mission in pack.missions {
            for spawn in mission.spawns {
                if spawn.enemy.0.starts_with("base:enemy_") {
                    native.insert(spawn.enemy);
                }
            }
        }
    }
    let enemies = native
        .into_iter()
        .map(|id| {
            json!({
                "id":id,
                "name":"Structural native-ID placeholder; no gameplay acceptance",
                "health":1,
                "speed":0
            })
        })
        .collect::<Vec<_>>();
    registry
        .apply(
            serde_json::from_value(json!({"enemies":enemies})).unwrap(),
            "base",
        )
        .unwrap();
    registry.validate().unwrap();
    registry
}

fn active() -> ActiveMods {
    let discovery = discovery();
    let enabled = mod_selection::plan_enable(&discovery, &[], CAMPAIGN).unwrap();
    ActiveMods::build(&structural_base(&discovery), &discovery, &enabled, None).unwrap()
}

fn active_original() -> ActiveMods {
    let data = std::env::var_os("RAPTOR_TEST_DATA")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../data"));
    let catalog = Catalog::open(data).unwrap();
    let registry = Registry::base(&catalog).unwrap();
    let discovery = modding::discover(&PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("mods"));
    assert!(discovery.errors.is_empty(), "{:?}", discovery.errors);
    let enabled = mod_selection::plan_enable(&discovery, &[], CAMPAIGN).unwrap();
    ActiveMods::build(&registry, &discovery, &enabled, Some(&catalog)).unwrap()
}

#[test]
fn explicit_mission_next_wins_over_campaign_order_and_standalone_stays_replayable() {
    let mut registry = base();
    registry
        .apply(
            serde_json::from_value(json!({
                "missions": [
                    {"id":"base:test_a","name":"Explicit route","duration":20,"next":"base:test_c"},
                    {"id":"base:test_b","name":"Campaign route","duration":20},
                    {"id":"base:test_c","name":"Standalone destination","duration":20}
                ],
                "campaigns":[{"id":"base:test_campaign","name":"Test route","missions":["base:test_a","base:test_b"]}]
            }))
            .unwrap(),
            "base",
        )
        .unwrap();
    registry.validate().unwrap();
    let mut pilot = Pilot::default();
    pilot.mission = "base:test_a".into();
    pilot.complete_mission(&registry).unwrap();
    assert_eq!(pilot.mission.0, "base:test_c");
    pilot.complete_mission(&registry).unwrap();
    assert_eq!(pilot.mission.0, "base:test_c");
    assert_eq!(pilot.completed.len(), 2);
}

#[test]
fn campaign_order_fallback_uses_stable_campaign_id_order() {
    let mut registry = base();
    registry
        .apply(
            serde_json::from_value(json!({
                "missions": [
                    {"id":"base:test_a","name":"Shared mission","duration":20},
                    {"id":"base:test_b","name":"First route","duration":20},
                    {"id":"base:test_c","name":"Second route","duration":20}
                ],
                "campaigns":[
                    {"id":"base:z_route","name":"Later ID","missions":["base:test_a","base:test_c"]},
                    {"id":"base:a_route","name":"Earlier ID","missions":["base:test_a","base:test_b"]}
                ]
            }))
            .unwrap(),
            "base",
        )
        .unwrap();
    registry.validate().unwrap();
    let mut pilot = Pilot::default();
    pilot.mission = "base:test_a".into();
    pilot.complete_mission(&registry).unwrap();
    assert_eq!(pilot.mission.0, "base:test_b");
    pilot.complete_mission(&registry).unwrap();
    assert_eq!(pilot.mission.0, "base:test_b");
}

#[test]
fn selecting_campaign_selects_nineteen_packages_and_respects_shared_dependencies() {
    let discovery = discovery();
    let enabled = mod_selection::plan_enable(&discovery, &[], CAMPAIGN).unwrap();
    assert_eq!(enabled.len(), 19);
    assert_eq!(enabled.last().unwrap(), CAMPAIGN);
    for number in 1..=6 {
        let id = format!("iron_coast_mission_{number}");
        assert!(enabled.contains(&id));
        let standalone = mod_selection::plan_enable(&discovery, &[], &id).unwrap();
        assert_eq!(standalone.len(), 8, "{id} must remain standalone");
        assert!(!standalone.iter().any(|id| id == CAMPAIGN));
        ActiveMods::build(&structural_base(&discovery), &discovery, &standalone, None).unwrap();
    }
    let disable = mod_selection::plan_disable(&discovery, &enabled, CAMPAIGN);
    assert_eq!(disable.removed.len(), 19);
    assert!(disable.enabled.is_empty());

    // Two independent missions share content. Disabling one keeps the other's
    // shared content while removing the disabled mission's unused stage boss.
    let standalone = mod_selection::plan_enable(&discovery, &[], "iron_coast_mission_1").unwrap();
    let standalone =
        mod_selection::plan_enable(&discovery, &standalone, "iron_coast_mission_6").unwrap();
    let disable = mod_selection::plan_disable(&discovery, &standalone, "iron_coast_mission_6");
    assert_eq!(disable.removed.len(), 2);
    assert!(
        disable
            .removed
            .contains(&"iron_coast_mission_6".to_string())
    );
    assert!(disable.removed.contains(&"iron_coast_boss_6".to_string()));
    assert!(
        disable
            .enabled
            .contains(&"iron_coast_mission_1".to_string())
    );
    assert!(disable.enabled.contains(&"pulse_cannon".to_string()));
}

#[test]
fn campaign_order_is_complete_and_owns_only_its_campaign_definition() {
    let active = active();
    let campaign = &active.registry.campaigns[&"iron_coast_mission_1:campaign".into()];
    assert_eq!(
        campaign
            .missions
            .iter()
            .map(|id| id.0.as_str())
            .collect::<Vec<_>>(),
        MISSIONS
    );
    assert_eq!(active.registry.overrides.len(), 1);
    assert_eq!(
        active.registry.owners[&"iron_coast_music:iron_coast".into()],
        "iron_coast_music"
    );
    for (number, id) in MISSIONS.iter().enumerate() {
        let owner = format!("iron_coast_mission_{}", number + 1);
        assert_eq!(&active.registry.owners[&(*id).into()], &owner);
        let mission = &active.registry.missions[&(*id).into()];
        assert!(!mission.auto_complete);
        assert_eq!(
            serde_json::to_value(mission).unwrap()["music_track"],
            "iron_coast_music:iron_coast"
        );
        let boss_id = if number == 0 {
            "iron_coast_boss:unit".to_string()
        } else {
            format!("iron_coast_boss_{}:unit", number + 1)
        };
        let bosses = mission
            .spawns
            .iter()
            .filter(|spawn| active.registry.enemies[&spawn.enemy].boss)
            .collect::<Vec<_>>();
        assert_eq!(bosses.len(), if number == 5 { 2 } else { 1 });
        assert!(bosses.iter().all(|spawn| spawn.enemy.0 == boss_id));
        if number > 0 {
            assert!(
                mission
                    .spawns
                    .iter()
                    .any(|spawn| spawn.enemy.0.starts_with("base:enemy_"))
            );
        }
    }
}

#[test]
fn campaign_progression_round_trips_pilot_inventory_and_script_state() {
    let active = active();
    let temporary = tempfile::tempdir().unwrap();
    let path = temporary.path().join("pilot.json");
    let mut pilot = Pilot::default();
    pilot.mission = MISSIONS[0].into();
    pilot.mods = active.pins.clone();
    pilot.inventory.insert("seeker_swarm:equipment".into(), 1);
    pilot.script_state.insert(
        "iron_coast_scout/scripts/ai.rhai".into(),
        json!({"destroyed":4,"shots":17}),
    );
    pilot.script_rng.insert(
        "iron_coast_scout/scripts/ai.rhai".into(),
        raptor_replica::simulation::LegacyRng::new(12345),
    );
    for (number, id) in MISSIONS.iter().enumerate() {
        assert_eq!(pilot.mission.0, *id);
        pilot.complete_mission(&active.registry).unwrap();
        assert_eq!(pilot.completed.len(), number + 1);
        let expected = MISSIONS[(number + 1).min(5)];
        assert_eq!(pilot.mission.0, expected);
        pilot.save(&path).unwrap();
        let recovered = Pilot::load(&path, &active.registry, &active.pins).unwrap();
        assert_eq!(
            serde_json::to_value(&recovered).unwrap(),
            serde_json::to_value(&pilot).unwrap()
        );
        pilot = recovered;
    }
    // Revisiting the finale does not duplicate completed progression records.
    pilot.complete_mission(&active.registry).unwrap();
    assert_eq!(pilot.completed.len(), 6);
    assert!(fs::metadata(path).unwrap().len() > 0);
}

#[test]
fn every_campaign_mission_accepts_a_full_twenty_slot_ship() {
    let mut active = active();
    for id in MISSIONS {
        for reserves in [0, 4] {
            let mut pilot = Pilot::default();
            if reserves > 0 {
                pilot.inventory.insert("base:super_shield".into(), 100);
                pilot.super_shield_reserves = vec![100; reserves];
            }
            for index in 0..18 {
                if pilot.inventory_slots() == 20 {
                    break;
                }
                pilot
                    .inventory
                    .insert(format!("base:fixture_item_{index}").as_str().into(), 1);
            }
            assert_eq!(pilot.inventory_slots(), 20);
            pilot.validate(&active.registry, &[]).unwrap();
            let mut world = World::new(&id.into(), &pilot, &active.registry).unwrap();
            world
                .step(Input::default(), &active.registry, &mut active.scripts)
                .unwrap();
            assert_eq!(
                world.player.inventory, pilot.inventory,
                "{id} changed a full inventory"
            );
            assert_eq!(
                world.player.super_shield_reserves,
                pilot.super_shield_reserves
            );
            assert_eq!(world.outcome, Outcome::Playing);
        }
    }
}

/// Controlled mouse input moves at most four horizontal pixels per simulation
/// step, fires continuously and cycles equipment using ordinary input edges.
/// It targets mission-local structures before shared turrets, then bosses and
/// scouts. Repairs are activated through their actual item callbacks.
fn campaign_input(world: &World, registry: &Registry) -> Input {
    let namespace = world.mission.0.split_once(':').unwrap().0;
    let target = world
        .enemies
        .iter()
        .filter(|enemy| enemy.health > 0 && enemy.y >= 0 && enemy.y < 145)
        .min_by_key(|enemy| {
            let priority = if enemy.definition.0.starts_with(&format!("{namespace}:")) {
                0
            } else if enemy.definition.0 == "iron_coast_turret:unit" {
                1
            } else if registry.enemies[&enemy.definition].boss {
                2
            } else {
                3
            };
            (priority, enemy.entity)
        });
    let goal = target
        .map(|enemy| enemy.x + enemy.width / 2 - 16)
        .unwrap_or(144)
        .clamp(5, 282);
    let x = world.player.x + (goal - world.player.x).clamp(-4, 4);
    let special = world
        .player
        .inventory
        .iter()
        .filter_map(|(id, count)| {
            let item = registry.items.get(id)?;
            (*count > 0 && item.special).then_some((id, item))
        })
        .collect::<Vec<_>>();
    let repair = special
        .iter()
        .find(|(_, item)| item.consumable && item.weapon.is_none())
        .map(|(id, _)| *id);
    let weapon = special
        .iter()
        .filter(|(_, item)| item.weapon.is_some())
        .max_by_key(|(_, item)| item.price)
        .map(|(id, _)| *id);
    let wanted = if world.player.shield <= 70 {
        repair.or(weapon)
    } else {
        weapon.or(repair)
    };
    let cycle =
        wanted.is_some_and(|id| world.player.selected.as_ref() != Some(id)) && !world.cycle_held;
    let consume = world.player.shield <= 70
        && repair.is_some_and(|id| world.player.selected.as_ref() == Some(id))
        && !world.special_held;
    Input {
        fire: true,
        cycle,
        special: consume,
        absolute: Some([x, 160]),
        ..Input::default()
    }
}

#[test]
#[ignore = "requires the original untracked catalog; native enemy paths and weapon behavior"]
fn registered_pilot_can_complete_six_real_missions_and_save_round_trips() {
    let mut active = active_original();
    assert_eq!(active.pins.len(), 19);
    assert_eq!(active.registry.overrides.len(), 1);
    let temporary = tempfile::tempdir().unwrap();
    let path = temporary.path().join("campaign-pilot.json");
    let mut pilot = Pilot::default();
    pilot.name = "Campaign Acceptance".into();
    pilot.callsign = "COAST".into();
    pilot.credits = 10_000;
    pilot.inventory.insert("base:energy".into(), 75);
    pilot.mission = MISSIONS[0].into();
    pilot.mods = active.pins.clone();
    let mut reports = Vec::new();
    let mut paid_refills = 0;
    for (number, mission) in MISSIONS.iter().enumerate() {
        assert_eq!(pilot.mission.0, *mission);
        let refills_before = paid_refills;
        // The hangar replenishes through the real purchase operation and its
        // actual price; this test never inserts free shield or premium weapons.
        while pilot.inventory[&"base:energy".into()] < 75 && pilot.credits >= 10_000 {
            pilot.buy(&"base:energy".into(), &active.registry).unwrap();
            paid_refills += 1;
        }
        let start_shield = pilot.inventory[&"base:energy".into()];
        let start_credits = pilot.credits;
        let mut world = World::new(&pilot.mission, &pilot, &active.registry).unwrap();
        let mut native_seen = BTreeSet::new();
        let mut native_motion = BTreeSet::new();
        let limit = active.registry.missions[&pilot.mission].duration + 1600;
        while world.tick < limit && world.outcome == Outcome::Playing {
            let input = campaign_input(&world, &active.registry);
            world
                .step(input, &active.registry, &mut active.scripts)
                .unwrap();
            for enemy in &world.enemies {
                if enemy.definition.0.starts_with("base:enemy_") {
                    assert!(active.registry.enemies[&enemy.definition].legacy.is_some());
                    native_seen.insert(enemy.definition.clone());
                    if enemy.x != enemy.sx || enemy.y != enemy.sy {
                        native_motion.insert(enemy.definition.clone());
                    }
                }
            }
        }
        assert_eq!(
            world.outcome,
            Outcome::Complete,
            "{mission}: tick={}, shield={}, objectives={:?}",
            world.tick,
            world.player.shield,
            world.objectives
        );
        assert!(world.player.shield > 0);
        if number > 0 {
            assert!(
                !native_seen.is_empty(),
                "{mission} never spawned a classic enemy"
            );
            assert!(
                !native_motion.is_empty(),
                "{mission} showed no classic enemy movement"
            );
        }
        let namespace = mission.split_once(':').unwrap().0;
        assert_eq!(world.objectives[&format!("{namespace}:complete")], 1);
        assert_eq!(world.objectives[&format!("{namespace}:debrief")], 1);
        let final_boss_tick = active.registry.missions[&pilot.mission]
            .spawns
            .iter()
            .filter(|spawn| active.registry.enemies[&spawn.enemy].boss)
            .map(|spawn| spawn.tick)
            .max()
            .unwrap();
        assert!(world.tick > final_boss_tick);
        let credits = world.player.credits;
        world
            .step(Input::default(), &active.registry, &mut active.scripts)
            .unwrap();
        assert_eq!(
            world.player.credits, credits,
            "{mission} paid victory twice"
        );
        eprintln!(
            "{mission}: complete at {}, shield {start_shield} -> {}, credits {}, classic types {}, moving types {}",
            world.tick,
            world.player.shield,
            world.player.credits,
            native_seen.len(),
            native_motion.len()
        );
        let native_definitions = native_seen
            .iter()
            .map(|id| {
                let definition = &active.registry.enemies[id];
                let legacy = definition.legacy.as_ref().unwrap();
                json!({
                    "id":id,
                    "name":definition.name,
                    "native_path_points":legacy.fields[19],
                    "native_move_type":legacy.fields[21],
                    "native_guns":legacy.fields[22]
                })
            })
            .collect::<Vec<_>>();
        reports.push(json!({
            "mission":mission,
            "completion_tick":world.tick,
            "start_shield":start_shield,
            "start_credits":start_credits,
            "energy_refills":paid_refills - refills_before,
            "final_shield":world.player.shield,
            "credits":world.player.credits,
            "objectives":world.objectives,
            "native_enemies":native_definitions,
            "native_motion_seen":native_motion,
            "digest":world.digest()
        }));
        pilot = world.pilot(&pilot);
        assert!(
            !pilot
                .inventory
                .contains_key(&"pulse_cannon:equipment".into()),
            "{mission} retained a mission-only Pulse loan"
        );
        assert!(
            !pilot.inventory.contains_key(&"ion_lance:equipment".into()),
            "{mission} retained a mission-only Ion loan"
        );
        pilot.merge_runtime_snapshot(&active.pins, &active.scripts.states, &active.scripts.rng);
        pilot.complete_mission(&active.registry).unwrap();
        assert_eq!(pilot.completed.len(), number + 1);
        pilot.save(&path).unwrap();
        let recovered = Pilot::load(&path, &active.registry, &active.pins).unwrap();
        assert_eq!(
            serde_json::to_value(&pilot).unwrap(),
            serde_json::to_value(&recovered).unwrap()
        );
        active
            .scripts
            .restore((recovered.script_state.clone(), recovered.script_rng.clone()));
        pilot = recovered;
    }
    assert_eq!(pilot.mission.0, MISSIONS[5]);
    assert_eq!(pilot.completed.len(), 6);
    // A completed finale must work again with its serialized mission and boss
    // state, rather than inheriting completion gates or dead entity cursors.
    let mut replay = World::new(&pilot.mission, &pilot, &active.registry).unwrap();
    let replay_limit = active.registry.missions[&pilot.mission].duration + 1600;
    while replay.tick < replay_limit && replay.outcome == Outcome::Playing {
        let input = campaign_input(&replay, &active.registry);
        replay
            .step(input, &active.registry, &mut active.scripts)
            .unwrap();
    }
    assert_eq!(
        replay.outcome,
        Outcome::Complete,
        "finale replay: {:?}",
        replay.objectives
    );
    assert_eq!(replay.objectives["iron_coast_boss_6:defeated"], 2);
    assert_eq!(replay.objectives["iron_coast_mission_6:complete"], 1);
    assert_eq!(replay.objectives["iron_coast_mission_6:debrief"], 1);
    assert!(replay.player.shield > 0);
    let replay_report = json!({
        "completion_tick":replay.tick,
        "final_shield":replay.player.shield,
        "credits":replay.player.credits,
        "objectives":replay.objectives,
        "digest":replay.digest()
    });
    pilot = replay.pilot(&pilot);
    pilot.merge_runtime_snapshot(&active.pins, &active.scripts.states, &active.scripts.rng);
    pilot.complete_mission(&active.registry).unwrap();
    assert_eq!(pilot.completed.len(), 6);
    assert_eq!(pilot.mission.0, MISSIONS[5]);
    pilot.save(&path).unwrap();
    let recovered = Pilot::load(&path, &active.registry, &active.pins).unwrap();
    assert_eq!(
        serde_json::to_value(&pilot).unwrap(),
        serde_json::to_value(&recovered).unwrap()
    );
    eprintln!(
        "Finale replay: {} ticks, {} shield",
        replay.tick, replay.player.shield
    );
    let report = serde_json::to_string_pretty(&json!({
        "original_catalog":true,
        "package_count":active.pins.len(),
        "package_pins":active.pins,
        "paid_refills":paid_refills,
        "reports":reports,
        "finale_replay":replay_report
    }))
    .unwrap();
    if let Ok(report_path) = std::env::var("RAPTOR_IRON_COAST_REPORT") {
        let report_path = PathBuf::from(report_path);
        if let Some(parent) = report_path.parent() {
            fs::create_dir_all(parent).unwrap();
        }
        fs::write(&report_path, format!("{report}\n")).unwrap();
        eprintln!("Campaign acceptance report: {}", report_path.display());
    }
    eprintln!(
        "Six-stage route and recovered finale replay passed; {paid_refills} paid Energy refills"
    );
}
