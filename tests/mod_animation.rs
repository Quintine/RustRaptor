use raptor_replica::{
    content::{ContentPack, Registry},
    modding::{Command, ScriptEffectKind, ScriptRuntime},
    persistence::Pilot,
    simulation::{EffectKind, Input, World},
};
use serde_json::json;

fn fixture() -> Registry {
    let mut registry = Registry::default();
    let pack: ContentPack = serde_json::from_value(json!({
        "weapons":[{"id":"base:projectile_forward_guns","name":"Guns","damage":1,"speed":8,"cooldown":2,"behavior":"straight","target":"all"}],
        "items":[
            {"id":"base:forward_guns","name":"Guns","price":0,"weapon":"base:projectile_forward_guns"},
            {"id":"base:energy","name":"Shield","price":0,"max_count":100}
        ],
        "enemies":[
            {"id":"base:phase_boss","name":"Phase boss","health":100,"speed":0,
             "art":{"asset":42,"logical_width":32,"logical_height":32,"frames":3}},
            {"id":"base:invisible","name":"No artwork","health":100,"speed":0}
        ],
        "missions":[{"id":"base:sector_1_wave_1","name":"Fixture","duration":1000}]
    })).unwrap();
    registry.apply(pack, "base").unwrap();
    registry.validate().unwrap();
    registry
}

#[test]
fn boss_phase_frame_remains_selected_and_resumes_normal_animation() {
    let registry = fixture();
    let pilot = Pilot::default();
    let mut world = World::new(&pilot.mission, &pilot, &registry).unwrap();
    let entity = world
        .spawn(&"base:phase_boss".into(), 100, 20, &registry)
        .unwrap();
    assert!(
        serde_json::to_value(&world.enemies[0])
            .unwrap()
            .get("pinned_art_frame")
            .is_none()
    );
    let rng = world.rng.clone();
    world
        .apply_commands(
            &[Command::Animation {
                entity,
                frame: Some(2),
            }],
            &registry,
        )
        .unwrap();
    assert_eq!(world.rng, rng);
    let mut runtime = ScriptRuntime::new();
    for _ in 0..17 {
        world
            .step(Input::default(), &registry, &mut runtime)
            .unwrap();
        assert_eq!(world.enemies[0].art_frame, 2);
        assert_eq!(world.enemies[0].pinned_art_frame, Some(2));
    }
    let serialized = serde_json::to_vec(&world).unwrap();
    let mut recovered: World = serde_json::from_slice(&serialized).unwrap();
    recovered
        .step(Input::default(), &registry, &mut runtime)
        .unwrap();
    assert_eq!(recovered.enemies[0].art_frame, 2);
    recovered
        .apply_commands(
            &[Command::Animation {
                entity,
                frame: None,
            }],
            &registry,
        )
        .unwrap();
    recovered
        .step(Input::default(), &registry, &mut runtime)
        .unwrap();
    assert_eq!(recovered.enemies[0].art_frame, recovered.enemies[0].age / 3);
    assert!(recovered.enemies[0].pinned_art_frame.is_none());
}

#[test]
fn invalid_phase_frame_rolls_back_the_entire_batch() {
    let registry = fixture();
    let pilot = Pilot::default();
    let mut world = World::new(&pilot.mission, &pilot, &registry).unwrap();
    let entity = world
        .spawn(&"base:phase_boss".into(), 100, 20, &registry)
        .unwrap();
    let invisible = world
        .spawn(&"base:invisible".into(), 20, 20, &registry)
        .unwrap();
    for (target, frame) in [
        (entity, 3),
        (entity, u32::MAX),
        (invisible, 0),
        (u64::MAX, 0),
        (0, 0),
    ] {
        let before = world.digest();
        let commands = [
            Command::Credits { amount: 100 },
            Command::Animation {
                entity: target,
                frame: Some(frame),
            },
        ];
        assert!(world.apply_commands(&commands, &registry).is_err());
        assert_eq!(world.digest(), before);
    }
}

#[test]
fn scripts_cannot_pin_or_reset_original_enemy_animation() {
    let mut registry = fixture();
    let pilot = Pilot::default();
    let mut world = World::new(&pilot.mission, &pilot, &registry).unwrap();
    let entity = world
        .spawn(&"base:phase_boss".into(), 100, 20, &registry)
        .unwrap();
    registry
        .enemies
        .get_mut(&"base:phase_boss".into())
        .unwrap()
        .legacy = Some(raptor_replica::assets::LegacyEnemy {
        name: "Native category fixture".into(),
        fields: vec![0; 26],
        shoot_type: vec![0; 24],
        engine_x: vec![0; 24],
        engine_y: vec![0; 24],
        engine_width: vec![0; 24],
        gun_x: vec![0; 24],
        gun_y: vec![0; 24],
        flight_x: vec![0; 32],
        flight_y: vec![0; 32],
    });
    let before = world.digest();
    for frame in [None, Some(1)] {
        assert!(
            world
                .apply_commands(&[Command::Animation { entity, frame }], &registry)
                .is_err()
        );
        assert_eq!(world.digest(), before);
    }
}

#[test]
fn phase_callbacks_use_serializable_state_and_restore_the_tick_on_failure() {
    let mut registry = fixture();
    registry
        .enemies
        .get_mut(&"base:phase_boss".into())
        .unwrap()
        .script = Some("phase.rhai".into());
    let mut runtime = ScriptRuntime::new();
    runtime.add("base", "phase.rhai", r#"
        fn on_spawn(e,s,r) { #{commands:[#{op:"animation",entity:e.entity,frame:1}],state:#{phase:1}} }
        fn on_tick(e,s,r) { #{commands:[#{op:"animation",entity:e.entity,frame:s.phase}],state:s} }
    "#).unwrap();
    let pilot = Pilot::default();
    let mut world = World::new(&pilot.mission, &pilot, &registry).unwrap();
    world
        .spawn(&"base:phase_boss".into(), 100, 20, &registry)
        .unwrap();
    world
        .step(Input::default(), &registry, &mut runtime)
        .unwrap();
    assert_eq!(world.enemies[0].art_frame, 1);
    runtime
        .states
        .insert("base/phase.rhai".into(), json!({"phase":99}));
    let world_before = world.digest();
    let states_before = runtime.states.clone();
    let rng_before = runtime.rng.clone();
    let error = world
        .step(Input::default(), &registry, &mut runtime)
        .unwrap_err();
    assert!(format!("{error:#}").contains("base/phase.rhai::on_tick"));
    assert_eq!(world.digest(), world_before);
    assert_eq!(runtime.states, states_before);
    assert_eq!(runtime.rng, rng_before);
}

#[test]
fn script_ground_impact_scrolls_with_terrain_and_legacy_effect_defaults_stay_airborne() {
    let registry = fixture();
    let pilot = Pilot::default();
    let mut world = World::new(&pilot.mission, &pilot, &registry).unwrap();
    let default: Command = serde_json::from_value(json!({"op":"effect","x":80,"y":40})).unwrap();
    world
        .apply_commands(
            &[
                default,
                Command::Effect {
                    x: 80,
                    y: 40,
                    kind: ScriptEffectKind::GroundBlast,
                },
                Command::Effect {
                    x: 80,
                    y: 40,
                    kind: ScriptEffectKind::SmallGround,
                },
                Command::Effect {
                    x: 80,
                    y: 40,
                    kind: ScriptEffectKind::SmallAir,
                },
            ],
            &registry,
        )
        .unwrap();
    assert_eq!(world.effects[0].kind, EffectKind::AirBlast);
    let mut runtime = ScriptRuntime::new();
    for _ in 0..8 {
        world
            .step(Input::default(), &registry, &mut runtime)
            .unwrap();
    }
    assert_eq!(world.effects.len(), 4);
    assert_eq!(world.effects[0].y, 40);
    assert!(world.effects[1].y > 40);
    assert_eq!(world.effects[1].y, world.effects[2].y);
    assert_eq!(world.effects[3].y, 40);
}

#[test]
fn invalid_effect_kind_and_out_of_bounds_positions_cannot_partially_commit() {
    assert!(
        serde_json::from_value::<Command>(json!({"op":"effect","x":0,"y":0,"kind":"unknown"}))
            .is_err()
    );
    let registry = fixture();
    let pilot = Pilot::default();
    let mut world = World::new(&pilot.mission, &pilot, &registry).unwrap();
    for (x, y) in [(32769, 0), (0, -32769), (i32::MIN, 0), (0, i32::MAX)] {
        let before = world.digest();
        let commands = [
            Command::Credits { amount: 100 },
            Command::Effect {
                x,
                y,
                kind: ScriptEffectKind::GroundBlast,
            },
        ];
        assert!(world.apply_commands(&commands, &registry).is_err());
        assert_eq!(world.digest(), before);
    }
}
