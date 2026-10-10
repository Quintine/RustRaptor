//! Package-local acceptance using the actual Rust simulation and Rhai runtime.
use raptor_replica::{
    assets::Catalog,
    content::{ContentId, Registry},
    modding::{self, ActiveMods, Command},
    persistence::Pilot,
    simulation::{Input, Outcome, World},
};
use std::path::PathBuf;

const OWNER: &str = "iron_coast_boss_4";
const UNIT: &str = "iron_coast_boss_4:unit";
const PROJECTILE: &str = "iron_coast_boss_4:projectile";
const MISSION: &str = "base:sector_1_wave_1";
const STATE: &str = "iron_coast_boss_4/scripts/ai.rhai";

fn active() -> ActiveMods {
    let project = PathBuf::from(std::env::var("RAPTOR_PROJECT").unwrap());
    let catalog = Catalog::open(project.join("data")).unwrap();
    let base = Registry::base(&catalog).unwrap();
    let discovery = modding::discover(&project.join("RustRaptor/mods"));
    let mut active =
        ActiveMods::build(&base, &discovery, &[OWNER.to_owned()], Some(&catalog)).unwrap();
    // Make an isolated non-legacy arena while retaining the real original guns.
    let mission = active.registry.missions.get_mut(&MISSION.into()).unwrap();
    mission.legacy_map = None;
    mission.spawns.clear();
    mission.tiles.clear();
    mission.layout.clear();
    mission.columns = 0;
    mission.script = None;
    mission.auto_complete = false;
    mission.duration = 10_000;
    active
}

fn world(active: &ActiveMods) -> World {
    let mut pilot = Pilot::default();
    pilot.difficulty = 3;
    pilot.inventory.insert("base:energy".into(), 100);
    World::new(&MISSION.into(), &pilot, &active.registry).unwrap()
}

fn step(world: &mut World, active: &mut ActiveMods) {
    world
        .step(Input::default(), &active.registry, &mut active.scripts)
        .unwrap();
}

#[test]
fn warning_precedes_three_shells_and_batteries_alternate() {
    let mut active = active();
    let mut world = world(&active);
    let id = world
        .spawn(&UNIT.into(), 112, 24, &active.registry)
        .unwrap();
    for tick in 0..12 {
        step(&mut world, &mut active);
        assert!(world.projectiles.iter().all(|p| p.weapon.0 != PROJECTILE));
        let unit = world.enemies.iter().find(|e| e.entity == id).unwrap();
        assert_eq!((unit.y, unit.vx, unit.vy), (24, 0, 0));
        if tick == 0 {
            assert!(
                world
                    .mod_sounds
                    .iter()
                    .any(|id| id.0 == "iron_coast_boss_4:warning")
            );
        }
    }
    step(&mut world, &mut active);
    let shells = world
        .projectiles
        .iter()
        .filter(|p| p.weapon.0 == PROJECTILE)
        .collect::<Vec<_>>();
    assert_eq!(shells.len(), 3);
    assert_eq!(
        shells.iter().filter(|p| p.vx == 0).next().unwrap().x,
        112 + 28
    );
    assert!(shells.iter().all(|p| p.hostile && p.vy == 4));
    assert!(
        world
            .mod_sounds
            .iter()
            .any(|id| id.0 == "iron_coast_boss_4:shot")
    );
    for _ in 13..67 {
        step(&mut world, &mut active);
    }
    let unit = world.enemies.iter().find(|e| e.entity == id).unwrap();
    let latest = world
        .projectiles
        .iter()
        .filter(|p| p.weapon.0 == PROJECTILE && p.age == 0)
        .collect::<Vec<_>>();
    assert_eq!(latest.len(), 3);
    assert_eq!(
        latest.iter().filter(|p| p.vx == 0).next().unwrap().x,
        unit.x + 68
    );
    assert_eq!(active.scripts.states[STATE]["salvos"].as_i64(), Some(2));
    assert_eq!(world.outcome, Outcome::Playing);
}

#[test]
fn two_bosses_have_independent_state_and_death_counts_once() {
    let mut active = active();
    let mut world = world(&active);
    let a = world.spawn(&UNIT.into(), 80, 24, &active.registry).unwrap();
    for _ in 0..20 {
        step(&mut world, &mut active);
    }
    let b = world
        .spawn(&UNIT.into(), 144, 24, &active.registry)
        .unwrap();
    step(&mut world, &mut active);
    assert_eq!(
        active.scripts.states[STATE]["units"][a.to_string()]["age"].as_i64(),
        Some(21)
    );
    assert_eq!(
        active.scripts.states[STATE]["units"][b.to_string()]["age"].as_i64(),
        Some(1)
    );
    world
        .apply_commands(
            &[Command::Damage {
                entity: a,
                amount: 100_000,
            }],
            &active.registry,
        )
        .unwrap();
    step(&mut world, &mut active);
    assert_eq!(world.objectives["iron_coast_boss_4:defeated"], 1);
    assert!(
        active.scripts.states[STATE]["units"]
            .get(a.to_string())
            .is_none()
    );
    assert!(
        world
            .mod_sounds
            .iter()
            .any(|id| id.0 == "iron_coast_boss_4:death")
    );
    for _ in 0..10 {
        step(&mut world, &mut active);
    }
    assert_eq!(world.objectives["iron_coast_boss_4:defeated"], 1);
    assert!(world.enemies.iter().any(|e| e.entity == b && e.health > 0));
    world
        .apply_commands(
            &[Command::Damage {
                entity: b,
                amount: 100_000,
            }],
            &active.registry,
        )
        .unwrap();
    step(&mut world, &mut active);
    assert_eq!(world.objectives["iron_coast_boss_4:defeated"], 2);
    assert_eq!(world.outcome, Outcome::Playing);
    assert!(
        active.scripts.states[STATE]["units"]
            .as_object()
            .unwrap()
            .is_empty()
    );
}

#[test]
fn saved_script_state_and_rng_reproduce_identical_future() {
    let mut a = active();
    let mut first = world(&a);
    first.spawn(&UNIT.into(), 112, -40, &a.registry).unwrap();
    for _ in 0..90 {
        step(&mut first, &mut a);
    }
    let mut second = first.clone();
    let mut b = active();
    b.scripts.restore(a.scripts.checkpoints());
    for _ in 0..100 {
        step(&mut first, &mut a);
        step(&mut second, &mut b);
        assert_eq!(first.digest(), second.digest());
        assert_eq!(a.scripts.states, b.scripts.states);
        assert_eq!(
            format!("{:?}", a.scripts.rng),
            format!("{:?}", b.scripts.rng)
        );
    }
}

#[test]
fn a_new_sortie_clears_reused_entity_death_guards() {
    let mut active = active();
    let mut first = world(&active);
    let a = first
        .spawn(&UNIT.into(), 112, 24, &active.registry)
        .unwrap();
    step(&mut first, &mut active);
    first
        .apply_commands(
            &[Command::Damage {
                entity: a,
                amount: 100_000,
            }],
            &active.registry,
        )
        .unwrap();
    step(&mut first, &mut active);
    let mut second = world(&active);
    let b = second
        .spawn(&UNIT.into(), 112, 24, &active.registry)
        .unwrap();
    assert_eq!(a, b);
    step(&mut second, &mut active);
    second
        .apply_commands(
            &[Command::Damage {
                entity: b,
                amount: 100_000,
            }],
            &active.registry,
        )
        .unwrap();
    step(&mut second, &mut active);
    assert_eq!(second.objectives["iron_coast_boss_4:defeated"], 1);
}

#[test]
fn restored_dead_guard_does_not_hide_a_lethal_hit_on_the_reused_spawn_step() {
    let mut prior = active();
    let mut previous_world = world(&prior);
    let old = previous_world
        .spawn(&UNIT.into(), 112, 24, &prior.registry)
        .unwrap();
    step(&mut previous_world, &mut prior);
    previous_world
        .apply_commands(
            &[Command::Damage {
                entity: old,
                amount: 100_000,
            }],
            &prior.registry,
        )
        .unwrap();
    step(&mut previous_world, &mut prior);
    assert_eq!(
        prior.scripts.states[STATE]["dead"][old.to_string()].as_bool(),
        Some(true)
    );

    let saved_script_checkpoint = prior.scripts.checkpoints();
    let mut restored = active();
    restored.scripts.restore(saved_script_checkpoint);
    restored
        .registry
        .weapons
        .get_mut(&PROJECTILE.into())
        .unwrap()
        .damage = 100_000;
    let mut replay = world(&restored);
    let reused = replay
        .spawn(&UNIT.into(), 112, 24, &restored.registry)
        .unwrap();
    assert_eq!(old, reused);
    // Preserve the actual queued spawn event to invoke duplicate death later.
    let duplicate_event = replay
        .events
        .iter()
        .find(|e| e.hook == "on_spawn")
        .unwrap()
        .event
        .clone();
    let credits = replay.player.credits;
    replay
        .apply_commands(
            &[Command::Projectile {
                weapon: PROJECTILE.into(),
                x: 160,
                y: 56,
                vx: 0,
                vy: 0,
                hostile: false,
            }],
            &restored.registry,
        )
        .unwrap();
    // Advance hits before the queued on_spawn callback. No dead entity may
    // receive velocity, a warning or a projectile from that callback.
    step(&mut replay, &mut restored);
    assert!(
        replay
            .enemies
            .iter()
            .all(|e| e.entity != reused || e.health <= 0)
    );
    assert!(
        restored.scripts.states[STATE]["units"]
            .get(reused.to_string())
            .is_none()
    );
    assert!(
        replay
            .mod_sounds
            .iter()
            .all(|id| id.0 != "iron_coast_boss_4:warning" && id.0 != "iron_coast_boss_4:shot")
    );
    assert!(replay.projectiles.iter().all(|p| !p.hostile));
    step(&mut replay, &mut restored);
    assert_eq!(replay.objectives["iron_coast_boss_4:defeated"], 1);
    assert_eq!(replay.player.credits, credits + 1_800);
    assert!(replay.enemies.iter().all(|e| e.entity != reused));

    let state = restored.scripts.states[STATE].clone();
    let duplicate_commands = restored
        .scripts
        .invoke(OWNER, "scripts/ai.rhai", "on_death", &duplicate_event, 1)
        .unwrap();
    assert!(duplicate_commands.is_empty());
    assert_eq!(restored.scripts.states[STATE], state);
    for _ in 0..60 {
        step(&mut replay, &mut restored);
    }
    assert_eq!(replay.objectives["iron_coast_boss_4:defeated"], 1);
    assert_eq!(replay.player.credits, credits + 1_800);
    assert!(replay.projectiles.iter().all(|p| !p.hostile));
    assert_eq!(replay.outcome, Outcome::Playing);
}

#[test]
fn live_boss_enters_and_persists_in_safe_bounds_without_auto_completion() {
    let mut active = active();
    let mut world = world(&active);
    let boss = world
        .spawn(&ContentId::from(UNIT), 112, -64, &active.registry)
        .unwrap();
    for _ in 0..600 {
        // Keep the player outside the cannon lane so the test measures persistence.
        world.player.x = 0;
        step(&mut world, &mut active);
        assert_eq!(world.outcome, Outcome::Playing);
    }
    let unit = world.enemies.iter().find(|e| e.entity == boss).unwrap();
    assert_eq!(unit.y, 24);
    assert!((80..=145).contains(&unit.x));
    assert_eq!(unit.health, 160);
    assert!(!world.objectives.contains_key("iron_coast_boss_4:defeated"));
}
