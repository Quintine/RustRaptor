//! Original-data integration coverage. Run explicitly with --ignored; no game data is tracked.
//! The assisted campaign fixture is described in tools/campaign_check.rs.
#[path = "../tools/campaign_check.rs"]
mod campaign_check;
use raptor_replica::{
    assets::{Catalog, decode_demo},
    content::ContentId,
    modding::ScriptRuntime,
    persistence::Pilot,
    simulation::{Input, World},
};
use std::{collections::BTreeSet, path::PathBuf};

fn catalog_registry() -> (Catalog, raptor_replica::content::Registry) {
    let root = std::env::var_os("RAPTOR_TEST_DATA")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("data"));
    campaign_check::catalog_registry(&root).unwrap()
}
fn registry() -> raptor_replica::content::Registry {
    catalog_registry().1
}

#[test]
#[ignore = "requires original untracked catalog; assisted inspection, not ordinary gameplay wins"]
fn every_original_wave_reaches_its_end_on_all_four_difficulties() {
    let registry = registry();
    assert_eq!(registry.missions.len(), 27);
    let mut failures = vec![];
    let mut reports = vec![];
    for difficulty in 0..=3 {
        for sector in 1..=3 {
            for wave in 1..=9 {
                let report =
                    campaign_check::run_wave(&registry, sector, wave, difficulty, 12000).unwrap();
                eprintln!("{}", report.csv());
                if !report.completed()
                    || report.visited_spawns != report.total_spawns
                    || report.bosses_seen != report.expected_bosses
                {
                    failures.push(format!("{report:?}"));
                }
                reports.push(report.csv());
            }
        }
    }
    if let Some(path) = std::env::var_os("RAPTOR_CAMPAIGN_REPORT") {
        std::fs::write(
            path,
            format!("{}\n{}\n", campaign_check::csv_header(), reports.join("\n")),
        )
        .unwrap();
    }
    assert!(
        failures.is_empty(),
        "Assisted fixture blockers:\n{}",
        failures.join("\n")
    );
}

#[test]
#[ignore = "requires original untracked catalog; progression fixture bypasses combat"]
fn all_original_campaign_and_training_progression_paths_are_available() {
    let registry = registry();
    for difficulty in 0..=3 {
        let mut pilot = Pilot {
            difficulty,
            ..Pilot::default()
        };
        let waves = if difficulty == 0 { 4 } else { 9 };
        let sectors = if difficulty == 0 { 1 } else { 3 };
        for sector in 1..=sectors {
            for wave in 1..=waves {
                let expected = ContentId::new(format!("base:sector_{sector}_wave_{wave}")).unwrap();
                assert_eq!(pilot.mission, expected);
                pilot.complete_mission(&registry).unwrap();
                pilot.validate(&registry, &[]).unwrap();
            }
        }
        assert_eq!(pilot.mission, ContentId::from("base:sector_1_wave_1"));
        assert_eq!(pilot.difficulty, (difficulty + 1).min(3));
        let progress = pilot.legacy_progress.as_ref().unwrap();
        assert!(progress.waves.iter().all(|wave| *wave == 0));
        if difficulty == 0 {
            assert!(progress.training_completed);
            assert_eq!(pilot.credits, 10000);
            assert_eq!(pilot.inventory[&"base:energy".into()], 75);
        } else {
            assert_eq!(pilot.completed.len(), 27);
            assert_eq!(&progress.difficulties[..3], &[(difficulty + 1).min(3); 3]);
        }
    }
}

#[test]
#[ignore = "requires original untracked catalog; assisted weapon exercise, no weapon parity claim"]
fn every_original_player_weapon_emits_with_live_mission_targets() {
    let registry = registry();
    let weapons: Vec<_> = registry
        .items
        .values()
        .filter(|i| i.weapon.is_some() && i.legacy.is_some())
        .collect();
    assert_eq!(weapons.len(), 15);
    let mut exercised = BTreeSet::new();
    for item in weapons {
        let id = item.weapon.clone().unwrap();
        let mut pilot = Pilot {
            difficulty: 3,
            selected: Some(item.id.clone()),
            ..Pilot::default()
        };
        pilot.inventory = [
            (item.id.clone(), item.max_count),
            ("base:energy".into(), 100),
        ]
        .into_iter()
        .collect();
        let mut world = World::new(&pilot.mission, &pilot, &registry).unwrap();
        let mut scripts = ScriptRuntime::new();
        for tick in 0..1500 {
            world.player.shield = 100;
            world.player.super_shield = 100;
            world
                .step(
                    Input {
                        fire: true,
                        absolute: Some([144, 160]),
                        bomb: tick % 180 == 0,
                        ..Input::default()
                    },
                    &registry,
                    &mut scripts,
                )
                .unwrap();
            if world.projectiles.iter().any(|p| p.weapon == id) {
                exercised.insert(id.clone());
                break;
            }
        }
        assert!(
            exercised.contains(&id),
            "original weapon {id} produced no projectile with mission targets"
        );
    }
    assert_eq!(exercised.len(), 15);
}

#[test]
#[ignore = "requires original catalog and rebuilt C++ full-demo reference trace"]
fn complete_demo_1_matches_every_reference_gameplay_snapshot() {
    let path = std::env::var_os("RAPTOR_REFERENCE_DEMO1")
        .map(PathBuf::from)
        .unwrap_or_else(|| {
            PathBuf::from(env!("CARGO_MANIFEST_DIR")).join(".reference/cpp-demo1-full.jsonl")
        });
    let reference: Vec<serde_json::Value> = std::fs::read_to_string(&path)
        .expect("produce the trace using the command in docs/campaign-validation.md")
        .lines()
        .map(|line| serde_json::from_str(line).unwrap())
        .collect();
    assert_eq!(
        reference.len(),
        1889,
        "expected the entire available DEMO1G1 recording"
    );
    let (catalog, registry) = catalog_registry();
    let (sector, wave, frames) = decode_demo(&catalog.named("DEMO1G1_REC").unwrap()).unwrap();
    assert_eq!(frames.len(), reference.len());
    let mut pilot = Pilot::demo(sector, &registry).unwrap();
    pilot.mission = format!("base:sector_{}_wave_{}", sector + 1, wave + 1)
        .as_str()
        .into();
    let mut world = World::new(&pilot.mission, &pilot, &registry).unwrap();
    let mut scripts = ScriptRuntime::new();
    for (frame, expected) in frames.into_iter().zip(reference) {
        world
            .step(
                Input {
                    fire: frame.buttons[0],
                    cycle: frame.buttons[1],
                    bomb: frame.buttons[2],
                    absolute: Some([frame.x as i32, frame.y as i32]),
                    demo_bank: Some(frame.bank as i32),
                    ..Input::default()
                },
                &registry,
                &mut scripts,
            )
            .unwrap();
        assert_eq!(
            world.reference_state(&registry),
            expected,
            "reference mismatch at simulation step {}",
            world.tick
        );
    }
    assert_eq!(world.tick, 1889);
    assert_eq!(world.player.shield, 3);
    assert_eq!(world.player.credits, 60825);
}
