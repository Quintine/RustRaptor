//! Compile with validate.py; runs the actual simulation and Rhai callbacks.
use raptor_replica::{
    assets::Catalog,
    content::{ContentId, Registry},
    modding::{self, ActiveMods, Command},
    persistence::Pilot,
    simulation::{Input, Outcome, World},
};
use std::{
    collections::{BTreeMap, BTreeSet},
    path::PathBuf,
};

const MISSION: &str = "iron_coast_mission_4:mission_04";
const MODS: [&str; 8] = [
    "iron_coast_scout",
    "iron_coast_turret",
    "iron_coast_boss_4",
    "iron_coast_music",
    "pulse_cannon",
    "seeker_swarm",
    "ion_lance",
    "iron_coast_mission_4",
];

fn active() -> ActiveMods {
    let project = PathBuf::from(std::env::var("RAPTOR_PROJECT").unwrap());
    let catalog = Catalog::open(project.join("data")).unwrap();
    let base = Registry::base(&catalog).unwrap();
    let discovery = modding::discover(&project.join("RustRaptor/mods"));
    ActiveMods::build(
        &base,
        &discovery,
        &MODS.iter().map(|s| s.to_string()).collect::<Vec<_>>(),
        Some(&catalog),
    )
    .unwrap()
}

fn pilot(shield: u32) -> Pilot {
    let mut pilot = Pilot::default();
    pilot.inventory.insert("base:energy".into(), shield);
    pilot.credits = if shield == 75 { 10_000 } else { 0 };
    pilot
}

#[derive(Default)]
struct NativeProof {
    seen: BTreeSet<String>,
    moved: BTreeSet<String>,
    positions: BTreeMap<u64, (i32, i32)>,
}

fn play(pilot: &Pilot, active: &mut ActiveMods) -> (World, NativeProof) {
    let mut world = World::new(&MISSION.into(), pilot, &active.registry).unwrap();
    let mut proof = NativeProof::default();
    for _ in 0..4000 {
        for enemy in &world.enemies {
            if enemy.definition.0.starts_with("base:enemy_") {
                proof.seen.insert(enemy.definition.0.clone());
                let prior = proof.positions.insert(enemy.entity, (enemy.x, enemy.y));
                if prior.is_some_and(|p| p != (enemy.x, enemy.y)) {
                    proof.moved.insert(enemy.definition.0.clone());
                }
            }
        }
        let target = world
            .enemies
            .iter()
            .filter(|e| e.health > 0 && e.y >= 0 && e.y < 130)
            .min_by_key(|e| {
                (
                    if e.definition.0 == "iron_coast_turret:unit" {
                        0
                    } else if e.definition.0 == "iron_coast_boss_4:unit" {
                        1
                    } else {
                        2
                    },
                    (world.player.x - e.x).abs(),
                )
            });
        let target_x = target.map(|e| e.x + e.width / 2 - 16).unwrap_or(144);
        let x = world.player.x + (target_x - world.player.x).clamp(-4, 4);
        world
            .step(
                Input {
                    fire: true,
                    absolute: Some([x, 160]),
                    ..Input::default()
                },
                &active.registry,
                &mut active.scripts,
            )
            .unwrap();
        if world.outcome != Outcome::Playing {
            break;
        }
    }
    (world, proof)
}

#[test]
fn starter_registration_and_default_fixture_complete_with_real_inputs() {
    for shield in [75, 100] {
        let mut active = active();
        let (world, proof) = play(&pilot(shield), &mut active);
        eprintln!(
            "Stormwall start={shield}, tick={}, outcome={:?}, shield={}, credits={}, objectives={:?}",
            world.tick, world.outcome, world.player.shield, world.player.credits, world.objectives
        );
        assert_eq!(world.outcome, Outcome::Complete);
        assert!(world.player.shield > 0);
        assert_eq!(world.objectives["iron_coast_mission_4:complete"], 1);
        assert!(world.objectives["iron_coast_turret:defeated"] >= 4);
        assert!(world.objectives["iron_coast_boss_4:defeated"] >= 1);
        assert_eq!(proof.seen.len(), 6, "native seen: {:?}", proof.seen);
        assert_eq!(proof.moved.len(), 6, "native moved: {:?}", proof.moved);
        for id in &proof.seen {
            let def = &active.registry.enemies[&ContentId::from(id.as_str())];
            assert!(def.legacy.is_some());
            assert!(def.script.is_none());
            assert!(def.path.len() >= 3);
            assert_eq!(
                active.registry.owners[&ContentId::from(id.as_str())],
                "base"
            );
        }
        assert!(
            !world
                .player
                .inventory
                .contains_key(&ContentId::from("pulse_cannon:equipment"))
        );
        assert_eq!(
            active.scripts.states["iron_coast_mission_4/scripts/mission.rhai"]["loaned"],
            false
        );
    }
}

#[test]
fn successful_replay_reuses_script_state_without_stale_death_flags() {
    let mut active = active();
    for _ in 0..2 {
        let (world, proof) = play(&pilot(75), &mut active);
        assert_eq!(world.outcome, Outcome::Complete);
        assert_eq!(proof.moved.len(), 6);
        assert_eq!(world.objectives["iron_coast_boss_4:defeated"], 1);
        assert_eq!(world.objectives["iron_coast_mission_4:debrief"], 1);
        assert!(
            !world
                .player
                .inventory
                .contains_key(&ContentId::from("pulse_cannon:equipment"))
        );
    }
}

#[test]
fn owned_cannon_and_full_inventory_can_win_without_losing_equipment() {
    let mut active = active();
    let mut owned = pilot(75);
    owned.inventory.insert("pulse_cannon:equipment".into(), 1);
    let (world, _) = play(&owned, &mut active);
    assert_eq!(world.outcome, Outcome::Complete);
    assert_eq!(
        world.player.inventory[&ContentId::from("pulse_cannon:equipment")],
        1
    );

    let mut full = pilot(75);
    for id in active.registry.items.keys() {
        if full.inventory_slots() == 20 {
            break;
        }
        if id.0.starts_with("base:") && id.0 != "base:super_shield" {
            full.inventory.entry(id.clone()).or_insert(1);
        }
    }
    assert_eq!(full.inventory_slots(), 20);
    let original = full.inventory.clone();
    let (world, _) = play(&full, &mut active);
    assert_eq!(world.outcome, Outcome::Complete);
    assert_eq!(world.objectives["iron_coast_mission_4:trial_issued"], 0);
    assert!(
        !world
            .player
            .inventory
            .contains_key(&ContentId::from("pulse_cannon:equipment"))
    );
    for (id, count) in original {
        if id.0 != "base:energy" {
            assert_eq!(world.player.inventory[&id], count, "changed equipment {id}");
        }
    }
}

#[test]
fn late_surviving_turrets_remain_reachable() {
    let mut active = active();
    let mut world = World::new(&MISSION.into(), &pilot(100), &active.registry).unwrap();
    // Real movement avoids incoming aimed fire without killing the objectives.
    for tick in 0..1050 {
        let x = if (tick / 40) % 2 == 0 { 32 } else { 128 };
        world
            .step(
                Input {
                    absolute: Some([x, 140]),
                    ..Input::default()
                },
                &active.registry,
                &mut active.scripts,
            )
            .unwrap();
        if world.outcome != Outcome::Playing {
            break;
        }
    }
    assert_eq!(world.outcome, Outcome::Playing);
    let turrets: Vec<_> = world
        .enemies
        .iter()
        .filter(|e| e.definition.0 == "iron_coast_turret:unit" && e.health > 0)
        .collect();
    assert_eq!(turrets.len(), 4);
    assert!(turrets.iter().all(|e| (0..=72).contains(&e.y)));
}

#[test]
fn full_inventory_is_unchanged_and_owned_cannon_survives_failure() {
    let mut active = active();
    let mut full = pilot(100);
    for id in active.registry.items.keys() {
        if full.inventory_slots() == 20 {
            break;
        }
        if id.0 != "pulse_cannon:equipment" && id.0 != "base:super_shield" {
            full.inventory.entry(id.clone()).or_insert(1);
        }
    }
    assert_eq!(full.inventory_slots(), 20);
    let before = full.inventory.clone();
    let mut world = World::new(&MISSION.into(), &full, &active.registry).unwrap();
    world
        .step(Input::default(), &active.registry, &mut active.scripts)
        .unwrap();
    assert_eq!(world.player.inventory, before);
    assert_eq!(world.objectives["iron_coast_mission_4:trial_issued"], 0);
    let mut owned = pilot(100);
    owned.inventory.insert("pulse_cannon:equipment".into(), 1);
    let mut world = World::new(&MISSION.into(), &owned, &active.registry).unwrap();
    world
        .step(Input::default(), &active.registry, &mut active.scripts)
        .unwrap();
    world
        .apply_commands(
            &[Command::Damage {
                entity: 0,
                amount: 100_000,
            }],
            &active.registry,
        )
        .unwrap();
    world
        .step(Input::default(), &active.registry, &mut active.scripts)
        .unwrap();
    assert_eq!(world.outcome, Outcome::Failed);
    assert_eq!(
        world.player.inventory[&ContentId::from("pulse_cannon:equipment")],
        1
    );
}

#[test]
fn failed_loan_is_returned_and_retry_resets_mission_state() {
    let mut active = active();
    for _ in 0..2 {
        let mut world = World::new(&MISSION.into(), &pilot(100), &active.registry).unwrap();
        world
            .step(Input::default(), &active.registry, &mut active.scripts)
            .unwrap();
        assert_eq!(
            world.player.inventory[&ContentId::from("pulse_cannon:equipment")],
            1
        );
        world
            .apply_commands(
                &[Command::Damage {
                    entity: 0,
                    amount: 100_000,
                }],
                &active.registry,
            )
            .unwrap();
        world
            .step(Input::default(), &active.registry, &mut active.scripts)
            .unwrap();
        assert_eq!(world.outcome, Outcome::Failed);
        assert!(
            !world
                .player
                .inventory
                .contains_key(&ContentId::from("pulse_cannon:equipment"))
        );
        assert_eq!(world.objectives["iron_coast_mission_4:debrief"], 0);
        assert_eq!(
            active.scripts.states["iron_coast_mission_4/scripts/mission.rhai"]["loaned"],
            false
        );
    }
}

#[test]
fn boss_alone_cannot_win_and_reward_is_paid_once() {
    let mut active = active();
    let mut world = World::new(&MISSION.into(), &pilot(100), &active.registry).unwrap();
    world
        .step(Input::default(), &active.registry, &mut active.scripts)
        .unwrap();
    world
        .objectives
        .insert("iron_coast_boss_4:defeated".into(), 1);
    world
        .objectives
        .insert("iron_coast_turret:defeated".into(), 3);
    world
        .step(Input::default(), &active.registry, &mut active.scripts)
        .unwrap();
    assert_eq!(world.outcome, Outcome::Playing);
    world
        .objectives
        .insert("iron_coast_turret:defeated".into(), 4);
    world
        .step(Input::default(), &active.registry, &mut active.scripts)
        .unwrap();
    assert_eq!(world.outcome, Outcome::Complete);
    assert_eq!(world.player.credits, 12000);
    world
        .step(Input::default(), &active.registry, &mut active.scripts)
        .unwrap();
    assert_eq!(world.player.credits, 12000);
    assert_eq!(world.objectives["iron_coast_mission_4:debrief"], 1);
}
