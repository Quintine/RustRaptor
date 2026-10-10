use raptor_replica::{
    content::{ContentPack, Registry},
    modding::{Command, ScriptRuntime},
    persistence::Pilot,
    simulation::{Effect, EffectKind, Input, VisualEffect, VisualEffectKind, World},
};
use serde_json::json;

fn fixture() -> (Registry, World) {
    let pack: ContentPack = serde_json::from_value(json!({
        "weapons":[{"id":"base:gun","name":"Gun","damage":1,"speed":8,"cooldown":8,"behavior":"straight","target":"all",
            "legacy":0,"art":{"asset":0x101c3,"logical_width":4,"logical_height":8,"frames":4}}],
        "items":[{"id":"base:forward_guns","name":"Guns","price":0,"legacy":0,"weapon":"base:gun"},
            {"id":"base:energy","name":"Energy","price":0,"legacy":16,"max_count":100},
            {"id":"base:super_shield","name":"Shield","price":0,"legacy":15,"max_count":100}],
        "missions":[{"id":"base:sector_1_wave_1","name":"Effects fixture","duration":1000}]
    })).unwrap();
    let mut registry = Registry::default();
    registry.apply(pack, "base").unwrap();
    let pilot = Pilot::default();
    let world = World::new(&pilot.mission, &pilot, &registry).unwrap();
    (registry, world)
}

#[test]
fn original_forward_gun_casings_stay_in_world_space_and_do_not_create_explosions() {
    let (registry, mut world) = fixture();
    let mut scripts = ScriptRuntime::new();
    world
        .step(
            Input {
                fire: true,
                demo_bank: Some(3),
                ..Input::default()
            },
            &registry,
            &mut scripts,
        )
        .unwrap();
    assert!(world.effects.is_empty());
    assert_eq!(world.visual_effects.len(), 2);
    assert!(
        world
            .visual_effects
            .iter()
            .all(|e| e.kind == VisualEffectKind::Casing)
    );
    let positions: Vec<_> = world.visual_effects.iter().map(|e| (e.x, e.y)).collect();
    assert_eq!(positions, [(166, 176), (153, 176)]);
    world
        .step(
            Input {
                absolute: Some([180, 150]),
                ..Input::default()
            },
            &registry,
            &mut scripts,
        )
        .unwrap();
    assert_eq!(
        world
            .visual_effects
            .iter()
            .map(|e| (e.x, e.y))
            .collect::<Vec<_>>(),
        [(166, 177), (153, 177)]
    );
    for _ in 0..3 {
        world
            .step(Input::default(), &registry, &mut scripts)
            .unwrap();
    }
    assert!(
        world.visual_effects.is_empty(),
        "native casing animation lasts four simulation steps"
    );
}

#[test]
fn native_smoke_uses_two_pixel_drift_and_exact_frame_lifetimes() {
    let (registry, mut world) = fixture();
    world
        .visual_effects
        .push(VisualEffect::new(VisualEffectKind::SmokeDown, 100, 100));
    world
        .visual_effects
        .push(VisualEffect::new(VisualEffectKind::SmokeTrail, 120, 100));
    let mut scripts = ScriptRuntime::new();
    for age in 1..=4 {
        world
            .step(Input::default(), &registry, &mut scripts)
            .unwrap();
        assert_eq!(
            (world.visual_effects[0].age, world.visual_effects[0].y),
            (age, 100 + 2 * (age as i32 - 1))
        );
        assert_eq!(
            (world.visual_effects[1].age, world.visual_effects[1].y),
            (age, 100 - 2 * (age as i32 - 1))
        );
    }
    world
        .step(Input::default(), &registry, &mut scripts)
        .unwrap();
    assert_eq!(world.visual_effects.len(), 1);
    world
        .step(Input::default(), &registry, &mut scripts)
        .unwrap();
    assert!(world.visual_effects.is_empty());
}

#[test]
fn shield_hit_follows_player_and_secondary_animations_do_not_change_gameplay_hashes() {
    let (registry, mut world) = fixture();
    world.player.super_shield = 20;
    world
        .player
        .inventory
        .insert("base:super_shield".into(), 20);
    world
        .apply_commands(
            &[Command::Damage {
                entity: 0,
                amount: 3,
            }],
            &registry,
        )
        .unwrap();
    assert_eq!(world.visual_effects.len(), 1);
    assert_eq!(world.visual_effects[0].kind, VisualEffectKind::Shield);
    assert_eq!(world.visual_effects[0].anchor, Some(0));
    let mut scripts = ScriptRuntime::new();
    world
        .step(
            Input {
                absolute: Some([100, 100]),
                ..Input::default()
            },
            &registry,
            &mut scripts,
        )
        .unwrap();
    assert_eq!(
        (world.visual_effects[0].x, world.visual_effects[0].y),
        (116, 116)
    );
    let digest = world.digest();
    let snapshot = world.reference_state(&registry);
    let seed = world.rng.seed;
    world.visual_effects.clear();
    assert_eq!(world.digest(), digest);
    assert_eq!(world.reference_state(&registry), snapshot);
    assert_eq!(world.rng.seed, seed);
}

#[test]
fn saturated_native_animation_pool_shares_one_limit_without_changing_fire_or_rng() {
    let (registry, initial) = fixture();
    let mut snapshots = Vec::new();
    for existing in [98, 99, 100] {
        let mut world = initial.clone();
        world.effects = vec![
            Effect {
                x: 40,
                y: 40,
                px: 40,
                py: 40,
                age: 0,
                kind: EffectKind::AirBlast,
                ground: false
            };
            existing
        ];
        world
            .step(
                Input {
                    fire: true,
                    demo_bank: Some(3),
                    ..Input::default()
                },
                &registry,
                &mut ScriptRuntime::new(),
            )
            .unwrap();
        assert_eq!(world.effects.len() + world.visual_effects.len(), 100);
        assert_eq!(world.visual_effects.len(), 100 - existing);
        assert_eq!(
            world.projectiles.len(),
            2,
            "visual allocation failure must not prevent real gun rounds"
        );
        snapshots.push(world.reference_state(&registry));
    }
    assert!(snapshots.windows(2).all(|pair| pair[0] == pair[1]));
}
