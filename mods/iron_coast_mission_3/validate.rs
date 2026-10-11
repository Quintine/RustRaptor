//! Local mission acceptance probe. Compile against the RustRaptor library.
use raptor_replica::{
    assets::Catalog,
    content::Registry,
    modding::{self, ActiveMods},
    persistence::Pilot,
    simulation::{Input, Outcome, World},
};
use std::{
    collections::{BTreeMap, BTreeSet},
    path::Path,
};

const MISSION: &str = "iron_coast_mission_3:mission_03";
const PACKAGES: [&str; 8] = [
    "iron_coast_scout",
    "iron_coast_turret",
    "iron_coast_boss_3",
    "pulse_cannon",
    "seeker_swarm",
    "ion_lance",
    "iron_coast_music",
    "iron_coast_mission_3",
];

fn active(root: &Path) -> ActiveMods {
    let catalog = Catalog::open(root.join("data")).unwrap();
    let base = Registry::base(&catalog).unwrap();
    let discovery = modding::discover(&root.join("RustRaptor/mods"));
    ActiveMods::build(
        &base,
        &discovery,
        &PACKAGES.iter().map(|s| s.to_string()).collect::<Vec<_>>(),
        Some(&catalog),
    )
    .unwrap()
}

fn pilot(shield: u32, credits: u32, difficulty: u32) -> Pilot {
    let mut pilot = Pilot::default();
    pilot.mission = MISSION.into();
    pilot.difficulty = difficulty;
    pilot.credits = credits;
    pilot.inventory.insert("base:energy".into(), shield);
    pilot
}

fn main() {
    let root = std::env::args().nth(1).expect("pass repository root");
    let mut reports = Vec::new();
    for (shield, credits, difficulty) in [
        (75, 10_000, 1),
        (75, 10_000, 2),
        (75, 10_000, 3),
        (100, 0, 2),
    ] {
        let mut active = active(Path::new(&root));
        let mut world = World::new(
            &MISSION.into(),
            &pilot(shield, credits, difficulty),
            &active.registry,
        )
        .unwrap();
        let mut native_positions = BTreeMap::new();
        let mut native_seen = BTreeSet::new();
        let mut native_moving = BTreeSet::new();
        for _ in 0..3000 {
            world
                .step(
                    Input {
                        fire: true,
                        absolute: Some([144, 160]),
                        ..Input::default()
                    },
                    &active.registry,
                    &mut active.scripts,
                )
                .unwrap();
            for enemy in &world.enemies {
                if enemy.definition.0.starts_with("base:enemy_") {
                    native_seen.insert(enemy.definition.0.clone());
                    if let Some(prior) = native_positions.insert(enemy.entity, (enemy.x, enemy.y)) {
                        if prior != (enemy.x, enemy.y) {
                            native_moving.insert(enemy.definition.0.clone());
                        }
                    }
                }
            }
            if world.outcome != Outcome::Playing {
                break;
            }
        }
        assert_eq!(
            world.outcome,
            Outcome::Complete,
            "difficulty={difficulty} tick={} shield={} objectives={:?}",
            world.tick,
            world.player.shield,
            world.objectives
        );
        assert_eq!(
            world.objectives["iron_coast_mission_3:convoys_intercepted"],
            3
        );
        assert_eq!(world.objectives["iron_coast_mission_3:complete"], 1);
        assert!(world.objectives["iron_coast_turret:defeated"] >= 2);
        assert!(world.objectives["iron_coast_boss_3:defeated"] >= 1);
        assert!(world.player.shield > 0);
        for id in [
            "base:enemy_0_20",
            "base:enemy_0_21",
            "base:enemy_0_22",
            "base:enemy_0_73",
        ] {
            assert!(native_seen.contains(id), "native enemy {id} never appeared");
            assert!(native_moving.contains(id), "native enemy {id} never moved");
            let original = &active.registry.enemies[&id.into()];
            assert!(original.legacy.is_some() && !original.path.is_empty());
        }
        reports.push(format!("initial_shield={shield} initial_credits={credits} difficulty={difficulty} tick={} shield={} credits={} digest={}",
            world.tick,world.player.shield,world.player.credits,world.digest()));
    }
    // All essential targets survive unattended indefinitely in the corridor.
    let mut active = active(Path::new(&root));
    let mut world = World::new(&MISSION.into(), &pilot(75, 10_000, 2), &active.registry).unwrap();
    for _ in 0..2200 {
        world.player.shield = 100; // Retention test only; never used in playthroughs.
        world
            .step(Input::default(), &active.registry, &mut active.scripts)
            .unwrap();
    }
    assert_eq!(world.outcome, Outcome::Playing);
    let cargo = world
        .enemies
        .iter()
        .filter(|e| e.definition.0 == "iron_coast_mission_3:convoy" && e.health > 0)
        .collect::<Vec<_>>();
    assert_eq!(cargo.len(), 3);
    assert!(cargo.iter().all(|e| e.y == 44));
    let escorts = world
        .enemies
        .iter()
        .filter(|e| e.definition.0 == "iron_coast_turret:unit" && e.health > 0)
        .collect::<Vec<_>>();
    assert_eq!(escorts.len(), 2);
    assert!(escorts.iter().all(|e| e.y == 74));
    assert!(
        world
            .enemies
            .iter()
            .any(|e| e.definition.0 == "iron_coast_boss_3:unit" && e.health > 0 && e.y == 24)
    );
    // Starting again resets restored state, and no grants consume inventory slots.
    let mut full = pilot(75, 10_000, 2);
    for item in active.registry.items.keys() {
        if full.inventory.len() == 20 {
            break;
        }
        if item.0 != "base:super_shield" {
            full.inventory.entry(item.clone()).or_insert(1);
        }
    }
    assert_eq!(full.inventory.len(), 20);
    let before = full.inventory.clone();
    let mut restarted = World::new(&MISSION.into(), &full, &active.registry).unwrap();
    restarted
        .step(Input::default(), &active.registry, &mut active.scripts)
        .unwrap();
    assert_eq!(restarted.player.inventory, before);
    assert_eq!(
        restarted.objectives["iron_coast_mission_3:convoys_intercepted"],
        0
    );
    // Boss and escorts alone cannot win; all cargo is required. Reward paid once.
    restarted
        .objectives
        .insert("iron_coast_boss_3:defeated".into(), 1);
    restarted
        .objectives
        .insert("iron_coast_turret:defeated".into(), 2);
    restarted
        .step(Input::default(), &active.registry, &mut active.scripts)
        .unwrap();
    assert_eq!(restarted.outcome, Outcome::Playing);
    restarted
        .objectives
        .insert("iron_coast_mission_3:convoys_intercepted".into(), 3);
    restarted
        .step(Input::default(), &active.registry, &mut active.scripts)
        .unwrap();
    assert_eq!(restarted.outcome, Outcome::Complete);
    assert_eq!(restarted.player.credits, 17_500);
    restarted
        .step(Input::default(), &active.registry, &mut active.scripts)
        .unwrap();
    assert_eq!(restarted.player.credits, 17_500);
    let mut full_flight = World::new(&MISSION.into(), &full, &active.registry).unwrap();
    for _ in 0..3000 {
        full_flight
            .step(
                Input {
                    fire: true,
                    absolute: Some([144, 160]),
                    ..Input::default()
                },
                &active.registry,
                &mut active.scripts,
            )
            .unwrap();
        if full_flight.outcome != Outcome::Playing {
            break;
        }
    }
    assert_eq!(full_flight.outcome, Outcome::Complete);
    assert_eq!(full_flight.player.inventory.len(), 20);
    for (item, count) in &before {
        if item.0 != "base:energy" {
            assert_eq!(
                full_flight.player.inventory.get(item),
                Some(count),
                "equipment changed: {item}"
            );
        }
    }
    reports.push(format!(
        "full_inventory=20 tick={} shield={} credits={}",
        full_flight.tick, full_flight.player.shield, full_flight.player.credits
    ));
    for report in reports {
        println!("{report}");
    }
    println!(
        "retained cargo/escorts/boss; full inventory; restart reset; gated completion; single reward: passed"
    );
}
