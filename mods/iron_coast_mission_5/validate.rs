//! Local original-data acceptance probe; run using validate.sh from any directory.
use raptor_replica::{
    assets::Catalog,
    content::Registry,
    modding::{self, ActiveMods},
    persistence::Pilot,
    simulation::{Input, Outcome, World},
};
use std::collections::{BTreeMap, BTreeSet};
use std::path::PathBuf;

const MISSION: &str = "iron_coast_mission_5:mission_05";
const IDS: [&str; 8] = [
    "iron_coast_scout",
    "iron_coast_turret",
    "iron_coast_boss_5",
    "pulse_cannon",
    "seeker_swarm",
    "ion_lance",
    "iron_coast_mission_5",
    "iron_coast_music",
];

fn build_active(base: &Registry, mods: &PathBuf, catalog: &Catalog) -> ActiveMods {
    let discovery = modding::discover(mods);
    assert!(discovery.errors.is_empty(), "{:?}", discovery.errors);
    ActiveMods::build(base, &discovery, &IDS.map(str::to_string), Some(catalog)).unwrap()
}

fn play(active: &mut ActiveMods, shield: u32) -> World {
    active.scripts.states.clear();
    active.scripts.rng.clear();
    let mut pilot = Pilot::default();
    pilot.inventory.insert("base:energy".into(), shield);
    pilot.credits = if shield == 75 { 10_000 } else { 0 };
    pilot.difficulty = 2;
    pilot.mission = MISSION.into();
    let mut world = World::new(&pilot.mission, &pilot, &active.registry).unwrap();
    let mut used = 0;
    let mut native_first = BTreeMap::new();
    let mut native_seen = BTreeSet::new();
    let mut native_moved = BTreeSet::new();
    for tick in 0..3600 {
        let target = world
            .enemies
            .iter()
            .find(|e| e.health > 0 && e.definition.0 == "iron_coast_mission_5:foundry");
        let target_x = target.map(|e| e.x + 8).unwrap_or(144);
        let input = Input {
            fire: true,
            dx: (target_x - world.player.x).signum(),
            special: world.player.shield <= 65 && tick % 2 == 0,
            ..Input::default()
        };
        let before = world
            .player
            .inventory
            .get(&"iron_coast_mission_5:coolant".into())
            .copied()
            .unwrap_or(0);
        world
            .step(input, &active.registry, &mut active.scripts)
            .unwrap();
        for enemy in &world.enemies {
            if enemy.definition.0.starts_with("base:enemy_") {
                native_seen.insert(enemy.definition.0.clone());
                let first = native_first
                    .entry(enemy.entity)
                    .or_insert((enemy.x, enemy.y));
                if *first != (enemy.x, enemy.y) {
                    native_moved.insert(enemy.definition.0.clone());
                }
            }
        }
        if tick == 0 {
            world.player.selected = Some("iron_coast_mission_5:coolant".into());
        }
        let after = world
            .player
            .inventory
            .get(&"iron_coast_mission_5:coolant".into())
            .copied()
            .unwrap_or(0);
        if after < before {
            used += before - after;
        }
        if world.outcome != Outcome::Playing {
            break;
        }
    }
    println!(
        "start_shield={shield} tick={} outcome={:?} shield={} credits={} coolant_used={used} foundries={} boss={} digest={}",
        world.tick,
        world.outcome,
        world.player.shield,
        world.player.credits,
        world
            .objectives
            .get("iron_coast_mission_5:foundries_destroyed")
            .copied()
            .unwrap_or(0),
        world
            .objectives
            .get("iron_coast_boss_5:defeated")
            .copied()
            .unwrap_or(0),
        world.digest()
    );
    assert_eq!(world.outcome, Outcome::Complete);
    assert!(world.player.shield > 0);
    assert_eq!(
        world.objectives["iron_coast_mission_5:foundries_destroyed"],
        2
    );
    assert!(world.objectives["iron_coast_boss_5:defeated"] >= 1);
    assert!(world.player.credits >= pilot.credits + 15_000);
    assert!(
        native_seen.len() >= 6,
        "all six native libraries should appear"
    );
    assert!(
        native_moved.len() >= 6,
        "native library paths must move in actual simulation"
    );
    println!("classic seen={native_seen:?}; moving={native_moved:?}");
    world
}

fn main() {
    let args = std::env::args().collect::<Vec<_>>();
    let catalog = Catalog::open(PathBuf::from(&args[1])).unwrap();
    let base = Registry::base(&catalog).unwrap();
    let mods = PathBuf::from(&args[2]);
    let mut active = build_active(&base, &mods, &catalog);
    assert_eq!(active.pins.len(), 8);
    let a = play(&mut active, 75);
    let b = play(&mut active, 75);
    assert_eq!(
        a.digest(),
        b.digest(),
        "repeat with same inputs must be deterministic"
    );
    play(&mut active, 100);

    for reserves in [0, 4] {
        active.scripts.states.clear();
        active.scripts.rng.clear();
        let mut pilot = Pilot::default();
        if reserves > 0 {
            pilot.inventory.insert("base:super_shield".into(), 100);
            pilot.super_shield_reserves = vec![100; reserves];
        }
        for id in active.registry.items.keys() {
            if pilot.inventory_slots() == 20 {
                break;
            }
            if id.0 != "base:super_shield" {
                pilot.inventory.entry(id.clone()).or_insert(1);
            }
        }
        assert_eq!(pilot.inventory_slots(), 20);
        let before = pilot.inventory.clone();
        let mut world = World::new(&MISSION.into(), &pilot, &active.registry).unwrap();
        world
            .step(Input::default(), &active.registry, &mut active.scripts)
            .unwrap();
        assert_eq!(world.player.inventory.len(), before.len());
        assert_eq!(
            world.player.super_shield_reserves,
            pilot.super_shield_reserves
        );
        for (id, count) in before {
            assert!(world.player.inventory[&id] >= count);
        }
        println!("full inventory start: 20 physical slots preserved, reserves={reserves}");
    }

    // The encounter timer and killing only the cruiser cannot award victory.
    active.scripts.states.clear();
    active.scripts.rng.clear();
    let mut world = World::new(&MISSION.into(), &Pilot::default(), &active.registry).unwrap();
    world
        .step(Input::default(), &active.registry, &mut active.scripts)
        .unwrap();
    world
        .objectives
        .insert("iron_coast_boss_5:defeated".into(), 1);
    world
        .step(Input::default(), &active.registry, &mut active.scripts)
        .unwrap();
    assert_eq!(world.outcome, Outcome::Playing);
    world
        .objectives
        .insert("iron_coast_mission_5:foundries_destroyed".into(), 2);
    let credits = world.player.credits;
    world
        .step(Input::default(), &active.registry, &mut active.scripts)
        .unwrap();
    assert_eq!(world.outcome, Outcome::Complete);
    assert_eq!(world.player.credits, credits + 15_000);
    world
        .step(Input::default(), &active.registry, &mut active.scripts)
        .unwrap();
    assert_eq!(world.player.credits, credits + 15_000);
    println!("objectives and one-time reward: passed");

    // Re-enter with completed script state retained. The start callback must
    // clear encounter flags/counters instead of inheriting the former victory.
    let mut retry = World::new(&MISSION.into(), &Pilot::default(), &active.registry).unwrap();
    retry
        .step(Input::default(), &active.registry, &mut active.scripts)
        .unwrap();
    assert_eq!(retry.outcome, Outcome::Playing);
    assert_eq!(
        retry.objectives["iron_coast_mission_5:foundries_destroyed"],
        0
    );
    assert_eq!(retry.objectives["iron_coast_boss_5:defeated"], 0);
    assert_eq!(retry.objectives["iron_coast_mission_5:complete"], 0);
    println!("mission restart with saved state: reset correctly");
}
