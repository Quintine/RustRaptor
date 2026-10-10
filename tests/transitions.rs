use raptor_replica::{
    content::{ContentPack, Registry},
    modding::{Command, ScriptRuntime},
    persistence::Pilot,
    simulation::{EffectKind, Input, LegacyRng, Outcome, Projectile, World},
};
use serde_json::json;

fn fixture(legacy: bool, automatic: bool) -> (Registry, World, ScriptRuntime) {
    let pack: ContentPack = serde_json::from_value(json!({
        "weapons":[{"id":"base:shot","name":"Shot","damage":8,"speed":0,"cooldown":1,"behavior":"straight","target":"all"}],
        "items":[{"id":"base:forward_guns","name":"Guns","price":0,"weapon":"base:shot","legacy":0},{"id":"base:energy","name":"Shield","price":0,"max_count":100,"legacy":16}],
        "enemies":[{"id":"base:target","name":"Final Target","health":1,"ground":true,"reward":10}],
        "missions":[{"id":"base:sector_1_wave_1","name":"Transition Fixture","duration":1,"auto_complete":automatic,"legacy_map":if legacy {Some(123)} else {None}}]
    })).unwrap();
    let mut registry = Registry::default();
    registry.apply(pack, "base").unwrap();
    let world = World::new(&Pilot::default().mission, &Pilot::default(), &registry).unwrap();
    (registry, world, ScriptRuntime::new())
}

fn after_calls(mut rng: LegacyRng, calls: usize) -> i32 {
    for _ in 0..calls {
        rng.next_value();
    }
    rng.seed
}

#[test]
fn original_departure_pauses_at_forty_and_flies_off_before_completion() {
    let (registry, mut world, mut scripts) = fixture(true, false);
    world.end_timer = Some(60);
    for step in 1..=20 {
        world
            .step(Input::default(), &registry, &mut scripts)
            .unwrap();
        assert_eq!(world.end_timer, Some(60 - step));
        assert_eq!(world.outcome, Outcome::Playing);
        assert!(world.draw_player);
        assert_eq!((world.player.x, world.player.y), (144, 160));
        assert_eq!(world.control_paused, step == 20);
        assert_eq!(world.sounds.contains(&129), step == 20); // FX_FLYBY.
    }
    world
        .step(
            Input {
                absolute: Some([280, 0]),
                fire: true,
                ..Input::default()
            },
            &registry,
            &mut scripts,
        )
        .unwrap();
    assert_eq!((world.player.x, world.player.y), (152, 156));
    assert!(world.projectiles.is_empty()); // Paused input cannot fire.
    world
        .step(Input::default(), &registry, &mut scripts)
        .unwrap();
    assert_eq!((world.player.x, world.player.y), (160, 148)); // Input+stats movement.
    while world.outcome == Outcome::Playing {
        world
            .step(Input::default(), &registry, &mut scripts)
            .unwrap();
    }
    assert_eq!(world.tick, 61);
    assert_eq!(world.outcome, Outcome::Complete);
    assert_eq!((world.player.x, world.player.y), (160, -160));
    assert!(world.draw_player);
}

#[test]
fn recorded_departure_positions_are_not_moved_a_second_time() {
    let (registry, mut world, mut scripts) = fixture(true, false);
    world.end_timer = Some(39);
    world.control_paused = true;
    world.departure_delta = [8, -4];
    world
        .step(
            Input {
                absolute: Some([155, -8]),
                demo_bank: Some(2),
                ..Input::default()
            },
            &registry,
            &mut scripts,
        )
        .unwrap();
    assert_eq!(
        (world.player.x, world.player.y, world.player.bank),
        (155, -8, 2)
    );
    assert_eq!(world.end_timer, Some(38));
}

#[test]
fn final_enemy_removal_arms_immunity_before_hostile_shot_updates() {
    let (registry, mut world, mut scripts) = fixture(true, true);
    let entity = world
        .spawn(&"base:target".into(), 20, 20, &registry)
        .unwrap();
    world
        .apply_commands(&[Command::Damage { entity, amount: 1 }], &registry)
        .unwrap();
    world.projectiles.push(Projectile {
        entity: world.next_entity,
        weapon: "base:shot".into(),
        x: 160,
        y: 176,
        px: 160,
        py: 176,
        vx: 0,
        vy: 0,
        hostile: true,
        age: 0,
        legacy: None,
        legacy_enemy: None,
    });
    world.next_entity += 1;
    world
        .step(Input::default(), &registry, &mut scripts)
        .unwrap();
    assert_eq!(world.end_timer, Some(60));
    assert_eq!(world.player.shield, 100);
    assert_eq!(world.player.credits, 10);
    assert_eq!(world.outcome, Outcome::Playing);
    assert!(world.projectiles.is_empty());
    let seed = world.rng.seed;
    world
        .apply_commands(
            &[Command::Damage {
                entity: 0,
                amount: 500,
            }],
            &registry,
        )
        .unwrap();
    assert_eq!(world.player.shield, 100);
    assert_eq!(world.rng.seed, seed);
}

#[test]
fn original_death_delays_failure_hides_ship_at_twenty_four_and_consumes_full_burst_rng() {
    let (registry, mut world, mut scripts) = fixture(true, false);
    world.player.shield = 0;
    let seed = world.rng;
    world
        .step(Input::default(), &registry, &mut scripts)
        .unwrap();
    assert_eq!(world.tick, 1);
    assert_eq!(world.end_timer, Some(60));
    assert_eq!(world.outcome, Outcome::Playing);
    assert!(world.draw_player);
    assert_eq!(world.rng.seed, after_calls(seed, 4)); // Two x/y positions, no early sound.
    assert_eq!(world.effects.len(), 2);
    assert_eq!(world.effects[0].kind, EffectKind::MediumAir);
    assert_eq!(world.effects[1].kind, EffectKind::SmallAir);
    let mut positions = seed;
    let y = 160 + positions.next_value() % 32;
    let x = 144 + positions.next_value() % 32;
    assert_eq!((world.effects[0].x, world.effects[0].y), (x, y));
    let seed = world.rng;
    world
        .step(Input::default(), &registry, &mut scripts)
        .unwrap();
    assert_eq!(world.rng.seed, after_calls(seed, 6)); // Two positions, sound pan and pitch.
    assert!(
        world
            .sound_events
            .iter()
            .any(|s| s.asset == 104 && matches!(s.pan, 30 | 225))
    );
    while world.end_timer != Some(25) {
        world
            .step(Input::default(), &registry, &mut scripts)
            .unwrap();
        assert!(world.draw_player);
    }
    let seed = world.rng;
    world
        .step(Input::default(), &registry, &mut scripts)
        .unwrap();
    assert_eq!(world.end_timer, Some(24));
    assert!(!world.draw_player);
    assert_eq!(world.effects.len(), 100); // Original pool cap, despite512requests.
    assert_eq!(world.rng.seed, after_calls(seed, 1032)); // Palette1,positions4,pitches3,burst1024.
    assert_eq!(world.sounds.iter().filter(|s| **s == 104).count(), 1);
    assert_eq!(world.sounds.iter().filter(|s| **s == 109).count(), 2);
    while world.outcome == Outcome::Playing {
        world
            .step(Input::default(), &registry, &mut scripts)
            .unwrap();
        assert!(world.tick <= 62);
    }
    assert_eq!(world.tick, 62);
    assert_eq!(world.outcome, Outcome::Failed);
    assert!(!world.draw_player);
    assert!(!world.control_paused);
    let stopped = world.digest();
    world
        .step(Input::default(), &registry, &mut scripts)
        .unwrap();
    assert_eq!(world.digest(), stopped);
}

#[test]
fn authored_mod_missions_keep_their_immediate_outcome_contract() {
    let (registry, mut world, mut scripts) = fixture(false, true);
    world
        .step(Input::default(), &registry, &mut scripts)
        .unwrap();
    assert_eq!(world.outcome, Outcome::Complete);
    assert_eq!(world.end_timer, None);
    let (registry, mut world, mut scripts) = fixture(false, false);
    world.player.shield = 0;
    world
        .step(Input::default(), &registry, &mut scripts)
        .unwrap();
    assert_eq!(world.outcome, Outcome::Failed);
    assert_eq!(world.end_timer, None);
}
