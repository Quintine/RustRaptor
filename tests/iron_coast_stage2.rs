//! Portable assembly/progression checks use synthetic resources; the ignored
//! playable route requires the original game catalog.
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

const CAMPAIGN: &str = "iron_coast_stage2_campaign";
const MISSIONS: [&str; 8] = [
    "iron_coast_stage2_mission_1:mission_01",
    "iron_coast_stage2_mission_2:mission_02",
    "iron_coast_stage2_mission_3:mission_03",
    "iron_coast_stage2_mission_4:mission_04",
    "iron_coast_stage2_mission_5:mission_05",
    "iron_coast_stage2_mission_6:mission_06",
    "iron_coast_stage2_mission_7:mission_07",
    "iron_coast_stage2_mission_8:mission_08",
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
        .unwrap_or_else(|| PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("data"));
    let catalog = Catalog::open(data).unwrap();
    let registry = Registry::base(&catalog).unwrap();
    let discovery = modding::discover(&PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("mods"));
    assert!(discovery.errors.is_empty(), "{:?}", discovery.errors);
    let enabled = mod_selection::plan_enable(&discovery, &[], CAMPAIGN).unwrap();
    ActiveMods::build(&registry, &discovery, &enabled, Some(&catalog)).unwrap()
}

#[test]
fn stage2_selects_complete_dependencies_and_prunes_unused_packages() {
    let discovery = discovery();
    let enabled = mod_selection::plan_enable(&discovery, &[], CAMPAIGN).unwrap();
    assert_eq!(enabled.len(), 23);
    let positions = enabled
        .iter()
        .enumerate()
        .map(|(n, id)| (id.clone(), n))
        .collect::<std::collections::BTreeMap<_, _>>();
    for id in &enabled {
        for dependency in discovery.mods[id].manifest.dependencies.keys() {
            assert!(
                positions[dependency] < positions[id],
                "{dependency} must precede {id}"
            );
        }
    }
    let active = active();
    let campaign = &active.registry.campaigns[&"iron_coast_stage2_campaign:campaign".into()];
    assert_eq!(
        campaign
            .missions
            .iter()
            .map(|id| id.0.as_str())
            .collect::<Vec<_>>(),
        MISSIONS
    );
    assert!(active.registry.overrides.is_empty());
    let disabled = mod_selection::plan_disable(&discovery, &enabled, CAMPAIGN);
    assert!(disabled.enabled.is_empty());
    for n in 1..=8 {
        let mission = format!("iron_coast_stage2_mission_{n}");
        let standalone = mod_selection::plan_enable(&discovery, &[], &mission).unwrap();
        assert!(
            standalone
                .iter()
                .all(|id| !id.starts_with("iron_coast_stage2_mission_") || id == &mission)
        );
        assert!(!standalone.contains(&CAMPAIGN.into()));
        assert!(!standalone.contains(&"iron_coast_railburst".into()));
        assert!(!standalone.contains(&"iron_coast_depth_charge".into()));
        ActiveMods::build(&structural_base(&discovery), &discovery, &standalone, None).unwrap();
    }
}

#[test]
fn eight_distinct_objective_missions_have_native_waves_and_own_bosses() {
    let active = active();
    let mut names = BTreeSet::new();
    for (n, id) in MISSIONS.iter().enumerate() {
        let mission = &active.registry.missions[&(*id).into()];
        assert!(names.insert(&mission.name));
        assert!(!mission.auto_complete);
        assert!(mission.script.is_some());
        assert!(
            mission.layout.len() / mission.columns as usize * 32
                >= mission.duration as usize + 2000,
            "{id} runs out of terrain during a delayed objective fight"
        );
        assert!(
            mission
                .spawns
                .iter()
                .any(|spawn| spawn.enemy.0.starts_with("base:enemy_"))
        );
        let bosses = mission
            .spawns
            .iter()
            .filter(|spawn| active.registry.enemies[&spawn.enemy].boss)
            .collect::<Vec<_>>();
        assert!(!bosses.is_empty());
        let boss = format!("iron_coast_stage2_boss_{}:unit", n + 1);
        assert!(bosses.iter().all(|spawn| spawn.enemy.0 == boss));
        assert!(bosses.iter().all(|spawn| spawn.tick < mission.duration));
        assert!(
            bosses.iter().all(|spawn| spawn.difficulty == 0),
            "{id} omits its required boss on easy difficulties"
        );
        assert!(
            mission
                .music_track
                .as_ref()
                .unwrap()
                .0
                .starts_with("iron_coast_stage2_music:")
        );
    }
}

#[test]
fn progression_pins_state_and_optional_equipment_round_trip_without_overrides() {
    let active = active();
    let temporary = tempfile::tempdir().unwrap();
    let path = temporary.path().join("stage2-pilot.json");
    let mut pilot = Pilot::default();
    pilot.mission = MISSIONS[0].into();
    pilot.mods = active.pins.clone();
    pilot
        .inventory
        .insert("iron_coast_railburst:equipment".into(), 1);
    pilot.script_state.insert(
        "iron_coast_stage2_interceptor/scripts/ai.rhai".into(),
        json!({"shots":17}),
    );
    pilot.script_rng.insert(
        "iron_coast_stage2_interceptor/scripts/ai.rhai".into(),
        raptor_replica::simulation::LegacyRng::new(12345),
    );
    for (n, id) in MISSIONS.iter().enumerate() {
        assert_eq!(pilot.mission.0, *id);
        pilot.complete_mission(&active.registry).unwrap();
        assert_eq!(pilot.completed.len(), n + 1);
        assert_eq!(pilot.mission.0, MISSIONS[(n + 1).min(7)]);
        pilot.save(&path).unwrap();
        let recovered = Pilot::load(&path, &active.registry, &active.pins).unwrap();
        assert_eq!(
            serde_json::to_value(&pilot).unwrap(),
            serde_json::to_value(&recovered).unwrap()
        );
        pilot = recovered;
    }
    pilot.complete_mission(&active.registry).unwrap();
    assert_eq!(pilot.completed.len(), 8);
}

#[test]
fn stage2_never_replaces_owned_equipment_or_breaks_full_inventories() {
    let mut active = active();
    for mission in MISSIONS {
        for reserves in [0, 4] {
            let mut pilot = Pilot::default();
            pilot.mission = mission.into();
            pilot
                .inventory
                .insert("iron_coast_railburst:equipment".into(), 1);
            pilot
                .inventory
                .insert("iron_coast_depth_charge:equipment".into(), 1);
            if reserves > 0 {
                pilot.inventory.insert("base:super_shield".into(), 100);
                pilot.super_shield_reserves = vec![100; reserves];
            }
            for n in 0..18 {
                if pilot.inventory_slots() == 20 {
                    break;
                }
                pilot
                    .inventory
                    .insert(format!("base:fixture_item_{n}").as_str().into(), 1);
            }
            pilot.validate(&active.registry, &[]).unwrap();
            assert_eq!(pilot.inventory_slots(), 20);
            let mut world = World::new(&pilot.mission, &pilot, &active.registry).unwrap();
            world
                .step(Input::default(), &active.registry, &mut active.scripts)
                .unwrap();
            assert_eq!(world.player.inventory, pilot.inventory, "{mission}");
            assert_eq!(
                world.player.super_shield_reserves,
                pilot.super_shield_reserves
            );
        }
    }
}

fn route_input(world: &World, registry: &Registry) -> Input {
    let namespace = world.mission.0.split_once(':').unwrap().0;
    let target = world
        .enemies
        .iter()
        .filter(|enemy| enemy.health > 0 && enemy.y >= 0 && enemy.y < 145)
        .min_by_key(|enemy| {
            let definition = &registry.enemies[&enemy.definition];
            let priority = if enemy.definition.0.starts_with(&format!("{namespace}:")) {
                0
            } else if definition.boss {
                1
            } else if definition.ground {
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
    let aimed = world.player.x + (goal - world.player.x).clamp(-4, 4);
    // Ordinary four-pixel mouse steps evade imminent projectile lanes. This
    // controller changes input only; enemies, health and damage stay real.
    let score = |x: i32| {
        let mut danger = 0_i32;
        for shot in world
            .projectiles
            .iter()
            .filter(|shot| shot.hostile && shot.y >= 100 && shot.y <= 196)
        {
            let dy = (shot.y - shot.py).max(shot.vy);
            if dy <= 0 {
                continue;
            }
            let ticks = ((160 - shot.y) / dy).clamp(0, 8);
            let predicted = shot.x + (shot.x - shot.px) * ticks;
            danger += (24 - (x + 16 - predicted).abs()).max(0) * (10 - ticks);
        }
        danger * 1000 + (goal - x).abs()
    };
    let x = [
        aimed,
        (world.player.x - 4).max(5),
        (world.player.x + 4).min(282),
    ]
    .into_iter()
    .min_by_key(|x| score(*x))
    .unwrap();
    Input {
        fire: true,
        absolute: Some([x, 160]),
        ..Input::default()
    }
}

#[test]
#[ignore = "requires original catalog; full real eight-sortie gameplay and pilot continuation"]
fn starter_ship_completes_all_eight_missions_with_paid_repairs_and_finale_replay() {
    let mut active = active_original();
    let temporary = tempfile::tempdir().unwrap();
    let path = temporary.path().join("route.json");
    let mut pilot = Pilot::default();
    pilot.name = "Black Tide Acceptance".into();
    pilot.credits = 10_000;
    pilot.inventory.insert("base:energy".into(), 75);
    pilot.difficulty = std::env::var("RAPTOR_STAGE2_DIFFICULTY")
        .map(|value| value.parse().unwrap())
        .unwrap_or(2);
    assert!(pilot.difficulty <= 3);
    pilot.mission = MISSIONS[0].into();
    pilot.mods = active.pins.clone();
    let mut reports = Vec::new();
    let mut paid_refills = 0;
    for (n, mission) in MISSIONS
        .iter()
        .chain(std::iter::once(&MISSIONS[7]))
        .enumerate()
    {
        assert_eq!(pilot.mission.0, *mission);
        while pilot.inventory[&"base:energy".into()] < 90 && pilot.credits >= 10_000 {
            pilot.buy(&"base:energy".into(), &active.registry).unwrap();
            paid_refills += 1;
        }
        let start_shield = pilot.inventory[&"base:energy".into()];
        let start_credits = pilot.credits;
        let mut world = World::new(&pilot.mission, &pilot, &active.registry).unwrap();
        let mut native_motion = BTreeSet::new();
        let mut seen_bosses = BTreeSet::new();
        let limit = active.registry.missions[&pilot.mission].duration + 1800;
        while world.tick < limit && world.outcome == Outcome::Playing {
            let input = route_input(&world, &active.registry);
            world
                .step(input, &active.registry, &mut active.scripts)
                .unwrap();
            for enemy in &world.enemies {
                let definition = &active.registry.enemies[&enemy.definition];
                if definition.boss {
                    seen_bosses.insert(enemy.definition.clone());
                }
                if enemy.definition.0.starts_with("base:enemy_")
                    && (enemy.x != enemy.sx || enemy.y != enemy.sy)
                {
                    assert!(definition.legacy.is_some());
                    native_motion.insert(enemy.definition.clone());
                }
            }
        }
        assert_eq!(
            world.outcome,
            Outcome::Complete,
            "{mission}: tick={},shield={},objectives={:?}",
            world.tick,
            world.player.shield,
            world.objectives
        );
        assert!(world.player.shield > 0);
        assert!(
            !native_motion.is_empty(),
            "{mission} did not show classic native movement"
        );
        assert!(!seen_bosses.is_empty());
        let namespace = mission.split_once(':').unwrap().0;
        assert_eq!(world.objectives[&format!("{namespace}:complete")], 1);
        assert_eq!(world.objectives[&format!("{namespace}:debrief")], 1);
        let credits = world.player.credits;
        world
            .step(Input::default(), &active.registry, &mut active.scripts)
            .unwrap();
        assert_eq!(world.player.credits, credits, "{mission} paid twice");
        eprintln!(
            "{mission}: complete {} ticks, shields {start_shield}-> {}, credits {}",
            world.tick, world.player.shield, world.player.credits
        );
        reports.push(json!({"mission":mission,"replay":n==8,"ticks":world.tick,"start_shield":start_shield,"shield":world.player.shield,"start_credits":start_credits,"credits":credits,"native_motion":native_motion,"objectives":world.objectives,"digest":world.digest()}));
        pilot = world.pilot(&pilot);
        pilot.merge_runtime_snapshot(&active.pins, &active.scripts.states, &active.scripts.rng);
        pilot.complete_mission(&active.registry).unwrap();
        assert_eq!(pilot.completed.len(), (n + 1).min(8));
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
    if let Ok(path) = std::env::var("RAPTOR_STAGE2_REPORT") {
        let path = PathBuf::from(path);
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent).unwrap();
        }
        fs::write(path,serde_json::to_vec_pretty(&json!({"original_catalog":true,"difficulty":pilot.difficulty,"pins":active.pins,"paid_refills":paid_refills,"reports":reports})).unwrap()).unwrap();
    }
}
