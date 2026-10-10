//! Campaign acceptance uses synthetic PNG/WAV assets; original data is unnecessary.
use raptor_replica::{
    content::{ContentPack, Registry},
    modding::{self, ActiveMods, Manifest},
    persistence::Pilot,
    simulation::{Input, Outcome, World},
};
use serde_json::{Value, json};
use std::{
    fs,
    path::{Path, PathBuf},
};

const PACKAGES: [&str; 7] = [
    "iron_coast_scout",
    "iron_coast_turret",
    "iron_coast_boss",
    "pulse_cannon",
    "seeker_swarm",
    "ion_lance",
    "iron_coast_mission_1",
];
const MISSION: &str = "iron_coast_mission_1:mission_01";

fn base() -> Registry {
    let mut registry = Registry::default();
    let mut value = json!({
        "weapons":[{"id":"base:projectile_forward_guns","name":"Forward Guns","damage":1,"speed":8,"cooldown":2,"behavior":"straight","target":"all","legacy":0,"art":{"asset":42,"logical_width":4,"logical_height":8,"frames":4}}],
        "items":[{"id":"base:forward_guns","name":"Forward Guns","price":0,"max_count":1,"weapon":"base:projectile_forward_guns","legacy":0},{"id":"base:energy","name":"Shield","price":0,"max_count":100,"legacy":16}],
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

fn fixture_resources(value: &Value, root: &Path) {
    match value {
        Value::Object(object) => {
            if let (Some(width), Some(height)) = (
                object.get("logical_width").and_then(Value::as_u64),
                object.get("logical_height").and_then(Value::as_u64),
            ) {
                let frames = object.get("frames").and_then(Value::as_u64).unwrap_or(1);
                for (key, scale) in [("png", 1), ("hd_png", 4)] {
                    if let Some(file) = object.get(key).and_then(Value::as_str) {
                        let path = root.join(file);
                        fs::create_dir_all(path.parent().unwrap()).unwrap();
                        let image = image::RgbaImage::from_pixel(
                            (width * frames * scale) as u32,
                            (height * scale) as u32,
                            image::Rgba([80, 96, 104, 255]),
                        );
                        image.save(path).unwrap();
                    }
                }
            }
            if let Some(file) = object.get("file").and_then(Value::as_str) {
                let path = root.join(file);
                fs::create_dir_all(path.parent().unwrap()).unwrap();
                // Small valid mono PCM16 WAV; integration checks use the actual cues.
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
            for child in object.values() {
                fixture_resources(child, root);
            }
        }
        Value::Array(values) => {
            for child in values {
                fixture_resources(child, root);
            }
        }
        _ => {}
    }
}

fn active() -> (tempfile::TempDir, ActiveMods) {
    let started = std::time::Instant::now();
    let temporary = tempfile::tempdir().unwrap();
    let source = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("examples/mods");
    for id in PACKAGES {
        let original = source.join(id);
        let root = temporary.path().join(id);
        fs::create_dir_all(&root).unwrap();
        let manifest_data = fs::read(original.join("mod.toml"))
            .expect("all seven Iron Coast packages must be installed");
        let manifest: Manifest =
            toml::from_str(std::str::from_utf8(&manifest_data).unwrap()).unwrap();
        fs::write(root.join("mod.toml"), manifest_data).unwrap();
        let content = fs::read(original.join(&manifest.content)).unwrap();
        let value: Value = serde_json::from_slice(&content).unwrap();
        fs::write(root.join(&manifest.content), content).unwrap();
        for script in &manifest.scripts {
            let path = root.join(script);
            fs::create_dir_all(path.parent().unwrap()).unwrap();
            fs::copy(original.join(script), path).unwrap();
        }
        fixture_resources(&value, &root);
    }
    let discovery = modding::discover(temporary.path());
    assert!(discovery.errors.is_empty(), "{:?}", discovery.errors);
    let enabled = PACKAGES.iter().map(|s| s.to_string()).collect::<Vec<_>>();
    let active = ActiveMods::build(&base(), &discovery, &enabled, None).unwrap();
    eprintln!(
        "Iron Coast synthetic seven-package activation: {:.3}s",
        started.elapsed().as_secs_f64()
    );
    (temporary, active)
}

#[test]
fn campaign_dependencies_and_generated_footprints_validate_together() {
    let (_temporary, active) = active();
    assert_eq!(active.pins.len(), 7);
    let mission = &active.registry.missions[&MISSION.into()];
    assert!(!mission.auto_complete);
    assert_eq!(mission.columns, 9);
    assert_eq!(mission.layout.len(), 72 * 9);
    assert!(
        mission
            .spawns
            .iter()
            .any(|s| s.enemy.0 == "iron_coast_boss:unit" && s.tick == 720)
    );
    assert_eq!(mission.art.as_ref().unwrap().logical_width, 320);
    assert!(
        active.registry.campaigns[&"iron_coast_mission_1:campaign".into()]
            .missions
            .contains(&MISSION.into())
    );
}

#[test]
fn boss_alone_cannot_complete_and_reward_is_paid_once() {
    let (_temporary, mut active) = active();
    let mut world = World::new(&MISSION.into(), &Pilot::default(), &active.registry).unwrap();
    world
        .step(Input::default(), &active.registry, &mut active.scripts)
        .unwrap();
    world
        .objectives
        .insert("iron_coast_boss:defeated".into(), 1);
    world
        .objectives
        .insert("iron_coast_turret:defeated".into(), 1);
    world
        .step(Input::default(), &active.registry, &mut active.scripts)
        .unwrap();
    assert_eq!(world.outcome, Outcome::Playing);
    world
        .objectives
        .insert("iron_coast_turret:defeated".into(), 2);
    world
        .step(Input::default(), &active.registry, &mut active.scripts)
        .unwrap();
    assert_eq!(world.outcome, Outcome::Complete);
    assert_eq!(world.objectives["iron_coast_mission_1:complete"], 1);
    assert_eq!(world.player.credits, 5000);
    assert_eq!(world.objectives["iron_coast_mission_1:debrief"], 1);
    world
        .step(Input::default(), &active.registry, &mut active.scripts)
        .unwrap();
    assert_eq!(world.player.credits, 5000);
}

fn play(use_trial: bool) -> (World, Vec<(u64, String)>) {
    let (_temporary, mut active) = active();
    let mut world = World::new(&MISSION.into(), &Pilot::default(), &active.registry).unwrap();
    let mut seen = Vec::new();
    for tick in 0..2000 {
        let input = Input {
            fire: true,
            special: tick % 90 == 60,
            cycle: tick == 1,
            absolute: Some([144, 160]),
            ..Input::default()
        };
        world
            .step(input, &active.registry, &mut active.scripts)
            .unwrap();
        if tick == 0 && !use_trial {
            world
                .player
                .inventory
                .remove(&"pulse_cannon:equipment".into());
        }
        for enemy in &world.enemies {
            if !seen.iter().any(|(_, id)| id == &enemy.definition.0) {
                seen.push((world.tick, enemy.definition.0.clone()));
            }
        }
        if world.outcome != Outcome::Playing {
            break;
        }
    }
    if use_trial {
        let weapon_state = &active.scripts.states["pulse_cannon/scripts/weapon.rhai"];
        assert!(weapon_state["bursts"].as_i64().unwrap() > 0);
        assert!(weapon_state["hits"].as_i64().unwrap() > 0);
        let serialized = serde_json::to_string(&active.scripts.states).unwrap();
        let recovered: serde_json::Value = serde_json::from_str(&serialized).unwrap();
        assert_eq!(recovered["pulse_cannon/scripts/weapon.rhai"], *weapon_state);
    }
    eprintln!(
        "Iron Coast {} run: tick={} outcome={:?} shield={} credits={} repairs_remaining={}",
        if use_trial {
            "trial Pulse"
        } else {
            "starter guns"
        },
        world.tick,
        world.outcome,
        world.player.shield,
        world.player.credits,
        world
            .player
            .inventory
            .get(&"iron_coast_mission_1:repair".into())
            .copied()
            .unwrap_or(0)
    );
    (world, seen)
}

#[test]
fn full_inventory_can_start_without_deleting_saved_equipment() {
    let (_temporary, mut active) = active();
    let mut pilot = Pilot::default();
    for n in 0..18 {
        pilot
            .inventory
            .insert(format!("base:fixture_item_{n}").as_str().into(), 1);
    }
    assert_eq!(pilot.inventory.len(), 20);
    let mut world = World::new(&MISSION.into(), &pilot, &active.registry).unwrap();
    world
        .step(Input::default(), &active.registry, &mut active.scripts)
        .unwrap();
    assert_eq!(world.player.inventory, pilot.inventory);
    assert_eq!(world.objectives["iron_coast_mission_1:trial_issued"], 0);
    assert_eq!(world.outcome, Outcome::Playing);
}

#[test]
fn restarted_mission_counts_new_turret_kills_independently_of_saved_statistics() {
    let (_temporary, mut active) = active();
    for _ in 0..2 {
        let mut world = World::new(&MISSION.into(), &Pilot::default(), &active.registry).unwrap();
        world
            .step(Input::default(), &active.registry, &mut active.scripts)
            .unwrap();
        let entity = world
            .spawn(&"iron_coast_turret:unit".into(), 144, 0, &active.registry)
            .unwrap();
        world
            .step(Input::default(), &active.registry, &mut active.scripts)
            .unwrap();
        world
            .apply_commands(
                &[modding::Command::Damage {
                    entity,
                    amount: 1000,
                }],
                &active.registry,
            )
            .unwrap();
        world
            .step(Input::default(), &active.registry, &mut active.scripts)
            .unwrap();
        assert_eq!(world.objectives["iron_coast_turret:defeated"], 1);
        assert_eq!(world.outcome, Outcome::Playing);
    }
    assert_eq!(
        active.scripts.states["iron_coast_turret/scripts/ai.rhai"]["destroyed"],
        2
    );
}

#[test]
fn starter_guns_can_complete_real_waves_and_boss() {
    let (world, seen) = play(false);
    assert_eq!(
        world.outcome,
        Outcome::Complete,
        "tick={} shield={} objectives={:?}",
        world.tick,
        world.player.shield,
        world.objectives
    );
    assert!(
        seen.iter()
            .any(|(tick, id)| *tick >= 720 && id == "iron_coast_boss:unit")
    );
    assert!(world.objectives["iron_coast_turret:defeated"] >= 2);
    assert!(world.objectives["iron_coast_boss:defeated"] >= 1);
    assert_eq!(world.objectives["iron_coast_mission_1:phase"], 4);
    assert!(world.player.shield > 0);
    assert!(world.tick > 720 && world.tick < 2000);
}

#[test]
fn trial_pulse_cannon_completes_and_preserves_scripted_weapon_state() {
    let (world, _seen) = play(true);
    assert_eq!(
        world.outcome,
        Outcome::Complete,
        "tick={} shield={} objectives={:?}",
        world.tick,
        world.player.shield,
        world.objectives
    );
    assert!(
        world
            .player
            .inventory
            .contains_key(&"pulse_cannon:equipment".into())
    );
    assert!(world.player.credits >= 5000);
}
