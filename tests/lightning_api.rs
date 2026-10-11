use raptor_replica::{
    content::{ContentId, ContentPack, Registry},
    modding::{Command, ScriptRuntime},
    persistence::Pilot,
    render::{Canvas, draw_lightning_arcs, draw_world_lightning_arcs},
    simulation::{Input, LightningArc, MAX_LIGHTNING_ARCS, Outcome, World},
};
use serde_json::json;

fn registry() -> Registry {
    let mut registry = Registry::default();
    let mut pack: ContentPack = serde_json::from_value(json!({
        "weapons":[
            {"id":"test:selected","name":"Selected","damage":20,"speed":0,"cooldown":4,
             "behavior":"scripted","target":"all","script":"selected.rhai"},
            {"id":"test:equipped","name":"Equipped","damage":2,"speed":0,"cooldown":2,
             "behavior":"scripted","target":"air","script":"equipped.rhai"}
        ],
        "items":[
            {"id":"test:gun","name":"Gun","price":100,"weapon":"test:selected","special":true},
            {"id":"test:shield","name":"Shield","price":100,"weapon":"test:equipped"}
        ],
        "enemies":[
            {"id":"test:air","name":"Air","health":100,"speed":0,"cooldown":2,"weapon":"test:selected"},
            {"id":"test:ground","name":"Ground","health":100,"speed":0,"ground":true}
        ],
        "missions":[{"id":"base:sector_1_wave_1","name":"Test","duration":1000}]
    })).unwrap();
    let missions = std::mem::take(&mut pack.missions);
    registry
        .apply(
            ContentPack {
                missions,
                ..ContentPack::default()
            },
            "base",
        )
        .unwrap();
    registry.apply(pack, "test").unwrap();
    registry.validate().unwrap();
    registry
}

fn world(registry: &Registry) -> World {
    let mut pilot = Pilot::default();
    pilot.inventory.clear();
    pilot.inventory.insert("base:energy".into(), 100);
    pilot.inventory.insert("test:gun".into(), 1);
    pilot.inventory.insert("test:shield".into(), 1);
    pilot.selected = Some("test:gun".into());
    World::new(&pilot.mission, &pilot, registry).unwrap()
}

fn arc(ticks: u32) -> Command {
    Command::Arc {
        x: 160,
        y: 160,
        to_x: 160,
        to_y: 30,
        ticks,
        anchor: None,
        to_anchor: None,
    }
}

#[test]
fn scripted_selected_and_equipped_weapons_follow_input_and_cooldowns_without_projectiles() {
    let registry = registry();
    let mut world = world(&registry);
    let mut runtime = ScriptRuntime::new();
    for path in ["selected.rhai", "equipped.rhai"] {
        runtime
            .add(
                "test",
                path,
                r#"fn on_fire(e,s,r) {
            let count=if s.contains("count") {s.count+1} else {1};
            #{commands:[],state:#{count:count,hostile:e.hostile,entity:e.entity}}
        }"#,
            )
            .unwrap();
    }
    world
        .step(Input::default(), &registry, &mut runtime)
        .unwrap();
    assert!(runtime.states.is_empty());
    for _ in 0..9 {
        world
            .step(
                Input {
                    fire: true,
                    ..Input::default()
                },
                &registry,
                &mut runtime,
            )
            .unwrap();
    }
    assert_eq!(runtime.states["test/selected.rhai"]["count"], 3);
    assert_eq!(runtime.states["test/equipped.rhai"]["count"], 5);
    assert_eq!(runtime.states["test/selected.rhai"]["entity"], 0);
    assert_eq!(runtime.states["test/selected.rhai"]["hostile"], false);
    assert!(world.projectiles.is_empty());
    // Special input fires the selected weapon while ordinary equipment remains idle.
    for _ in 0..4 {
        world
            .step(
                Input {
                    special: true,
                    ..Input::default()
                },
                &registry,
                &mut runtime,
            )
            .unwrap();
    }
    assert_eq!(runtime.states["test/selected.rhai"]["count"], 4);
    assert_eq!(runtime.states["test/equipped.rhai"]["count"], 5);
    assert!(world.projectiles.is_empty());
}

#[test]
fn scripted_enemy_weapons_emit_fire_hooks_without_native_projectiles() {
    let registry = registry();
    let mut world = world(&registry);
    let entity = world
        .spawn(&ContentId::from("test:air"), 30, 30, &registry)
        .unwrap();
    let mut runtime = ScriptRuntime::new();
    runtime
        .add(
            "test",
            "selected.rhai",
            r#"fn on_fire(e,s,r) {
        #{commands:[],state:#{hostile:e.hostile,entity:e.entity}}
    }"#,
        )
        .unwrap();
    world
        .step(Input::default(), &registry, &mut runtime)
        .unwrap();
    assert_eq!(runtime.states["test/selected.rhai"]["entity"], entity);
    assert_eq!(runtime.states["test/selected.rhai"]["hostile"], true);
    assert!(world.projectiles.is_empty());
}

#[test]
fn enemy_snapshots_expose_registry_ground_flags() {
    let mut registry = registry();
    registry
        .missions
        .get_mut(&ContentId::from("base:sector_1_wave_1"))
        .unwrap()
        .script = Some("queries.rhai".into());
    let mut world = world(&registry);
    world
        .spawn(&ContentId::from("test:air"), 30, 30, &registry)
        .unwrap();
    world
        .spawn(&ContentId::from("test:ground"), 90, 30, &registry)
        .unwrap();
    let mut runtime = ScriptRuntime::new();
    runtime.add("test", "selected.rhai", "").unwrap();
    runtime
        .add(
            "base",
            "queries.rhai",
            r#"fn on_mission_start(e,s,r) {
        #{commands:[],state:#{air:e.entities[0].ground,ground:e.entities[1].ground}}
    }"#,
        )
        .unwrap();
    world
        .step(Input::default(), &registry, &mut runtime)
        .unwrap();
    assert_eq!(
        runtime.states["base/queries.rhai"],
        json!({"air":false,"ground":true})
    );
}

#[test]
fn scripted_behavior_requires_a_script_and_arc_defaults_to_three_ticks() {
    let mut registry = registry();
    registry
        .weapons
        .get_mut(&ContentId::from("test:selected"))
        .unwrap()
        .script = None;
    assert!(
        registry
            .validate()
            .unwrap_err()
            .to_string()
            .contains("requires a script")
    );
    let command: Command = serde_json::from_value(json!({
        "op":"arc","x":0,"y":0,"to_x":20,"to_y":20
    }))
    .unwrap();
    assert!(matches!(
        command,
        Command::Arc {
            ticks: 3,
            anchor: None,
            to_anchor: None,
            ..
        }
    ));
}

#[test]
fn arcs_validate_coordinates_lifetime_and_capacity_transactionally() {
    let registry = registry();
    let mut world = world(&registry);
    let before = world.digest();
    for bad in [
        arc(0),
        arc(13),
        Command::Arc {
            x: i32::MIN,
            y: 0,
            to_x: 0,
            to_y: 0,
            ticks: 3,
            anchor: None,
            to_anchor: None,
        },
        Command::Arc {
            x: 0,
            y: 32769,
            to_x: 0,
            to_y: 0,
            ticks: 3,
            anchor: None,
            to_anchor: None,
        },
        Command::Arc {
            x: 0,
            y: 0,
            to_x: -32769,
            to_y: 0,
            ticks: 3,
            anchor: None,
            to_anchor: None,
        },
        Command::Arc {
            x: 0,
            y: 0,
            to_x: 0,
            to_y: 32769,
            ticks: 3,
            anchor: None,
            to_anchor: None,
        },
    ] {
        assert!(
            world
                .apply_commands(&[arc(3), Command::Credits { amount: 5 }, bad], &registry)
                .is_err()
        );
        assert_eq!(world.digest(), before);
        assert!(world.lightning_arcs.is_empty());
    }
    world
        .apply_commands(
            &[Command::Arc {
                x: -32768,
                y: 32768,
                to_x: 32768,
                to_y: -32768,
                ticks: 12,
                anchor: None,
                to_anchor: None,
            }],
            &registry,
        )
        .unwrap();
    world
        .apply_commands(&vec![arc(3); MAX_LIGHTNING_ARCS - 1], &registry)
        .unwrap();
    assert!(
        world
            .apply_commands(&[Command::Credits { amount: 5 }, arc(3)], &registry)
            .is_err()
    );
    assert_eq!(world.lightning_arcs.len(), MAX_LIGHTNING_ARCS);
    assert_eq!(world.digest(), before);
}

#[test]
fn invalid_arc_hook_rolls_back_world_script_state_and_rng() {
    let registry = registry();
    let mut world = world(&registry);
    let before = world.digest();
    let mut runtime = ScriptRuntime::new();
    runtime.add("test", "equipped.rhai", "").unwrap();
    runtime
        .add(
            "test",
            "selected.rhai",
            r#"fn on_fire(e,s,r) {
        #{commands:[#{op:"arc",x:0,y:0,to_x:10,to_y:10},
                    #{op:"credits",amount:5},
                    #{op:"arc",x:0,y:0,to_x:10,to_y:10,ticks:13}],
          state:#{used:r[0]}}
    }"#,
        )
        .unwrap();
    let error = world
        .step(
            Input {
                fire: true,
                ..Input::default()
            },
            &registry,
            &mut runtime,
        )
        .unwrap_err();
    assert!(error.to_string().contains("arc lifetime"), "{error:#}");
    assert!(error.to_string().contains("test/selected.rhai::on_fire"));
    assert_eq!(world.digest(), before);
    assert!(world.lightning_arcs.is_empty());
    assert!(runtime.states.is_empty());
    assert!(runtime.rng.is_empty());
}

#[test]
fn arc_lifetime_uses_simulation_ticks_and_never_changes_gameplay_state() {
    let registry = registry();
    let mut world = world(&registry);
    let mut plain = world.clone();
    world.apply_commands(&[arc(1), arc(3)], &registry).unwrap();
    assert_eq!(world.digest(), plain.digest());
    assert!(
        serde_json::to_value(&world)
            .unwrap()
            .get("lightning_arcs")
            .is_none()
    );
    let mut runtime = ScriptRuntime::new();
    let mut plain_runtime = ScriptRuntime::new();
    for expected in [1, 1, 0] {
        world
            .step(Input::default(), &registry, &mut runtime)
            .unwrap();
        plain
            .step(Input::default(), &registry, &mut plain_runtime)
            .unwrap();
        assert_eq!(world.lightning_arcs.len(), expected);
        assert_eq!(world.digest(), plain.digest());
        assert_eq!(world.rng, plain.rng);
    }
    world.apply_commands(&[arc(3)], &registry).unwrap();
    world.outcome = Outcome::Complete;
    world
        .step(Input::default(), &registry, &mut runtime)
        .unwrap();
    assert_eq!(world.lightning_arcs[0].age, 0);
}

#[test]
fn successive_discharge_seeds_vary_without_using_gameplay_randomness() {
    let registry = registry();
    let mut world = world(&registry);
    let rng = world.rng;
    let mut replay = world.clone();
    for _ in 0..3 {
        let previous = world.lightning_arcs.last().map(|arc| arc.seed);
        world.apply_commands(&[arc(3)], &registry).unwrap();
        replay.apply_commands(&[arc(3)], &registry).unwrap();
        assert_ne!(previous, Some(world.lightning_arcs.last().unwrap().seed));
        assert_eq!(world.lightning_arcs, replay.lightning_arcs);
        assert_eq!(world.rng, rng);
    }
    let first = world.lightning_arcs[0].seed;
    world.lightning_arcs.clear();
    world
        .step(Input::default(), &registry, &mut ScriptRuntime::new())
        .unwrap();
    world.apply_commands(&[arc(3)], &registry).unwrap();
    assert_ne!(first, world.lightning_arcs[0].seed);
}

#[test]
fn lightning_renderer_draws_visible_jagged_cyan_white_lines_at_all_scales_without_mutation() {
    let mut palette = [[0; 3]; 256];
    palette[1] = [24, 198, 255];
    palette[2] = [230, 255, 255];
    let arcs = vec![LightningArc {
        x: 20,
        y: 160,
        to_x: 200,
        to_y: 30,
        ticks: 3,
        age: 0,
        seed: 0,
        anchor: None,
        to_anchor: None,
    }];
    for scale in [1, 2, 3, 4] {
        let mut canvas = Canvas::new(scale);
        draw_lightning_arcs(&mut canvas, &arcs, &palette);
        assert!(canvas.image.pixels.contains(&1));
        assert!(canvas.image.pixels.contains(&2));
        assert_eq!(
            canvas.image.pixels[160 * scale * canvas.image.width + 20 * scale],
            2
        );
        assert_eq!(
            canvas.image.pixels[30 * scale * canvas.image.width + 200 * scale],
            2
        );
        let first = canvas.image.clone();
        canvas.clear(0);
        draw_lightning_arcs(&mut canvas, &arcs, &palette);
        assert_eq!(canvas.image, first);
        // Reusing a renderer cache across palettes must not reuse old indices.
        let mut alternate = [[0; 3]; 256];
        alternate[1] = palette[2];
        canvas.clear(0);
        draw_lightning_arcs(&mut canvas, &arcs, &alternate);
        assert_eq!(
            canvas.image.pixels[160 * scale * canvas.image.width + 20 * scale],
            1
        );
        canvas.clear(0);
        draw_lightning_arcs(&mut canvas, &arcs, &palette);
        assert_eq!(canvas.image, first);
        let mut later = arcs.clone();
        later[0].age = 1;
        canvas.clear(0);
        draw_lightning_arcs(&mut canvas, &later, &palette);
        assert_ne!(canvas.image, first);
        later[0].age = 0;
        later[0].seed = 12345;
        canvas.clear(0);
        draw_lightning_arcs(&mut canvas, &later, &palette);
        assert_ne!(canvas.image, first);
    }
    assert_eq!(arcs[0].age, 0);
    let mut canvas = Canvas::new(4);
    let offscreen = [LightningArc {
        x: -32768,
        y: -32768,
        to_x: 32768,
        to_y: 32768,
        ticks: 3,
        age: 0,
        seed: 0,
        anchor: None,
        to_anchor: None,
    }];
    draw_lightning_arcs(&mut canvas, &offscreen, &palette);
    assert!(canvas.image.pixels.contains(&2));
    canvas.clear(0);
    let expired = [LightningArc {
        age: 3,
        ..arcs[0].clone()
    }];
    draw_lightning_arcs(&mut canvas, &expired, &palette);
    assert!(canvas.image.pixels.iter().all(|p| *p == 0));
}

#[test]
fn lightning_glow_has_falloff_lights_background_and_avoids_animated_colors() {
    let mut palette = [[0; 3]; 256];
    for (i, rgb) in palette[..240].iter_mut().enumerate() {
        *rgb = [i as u8 / 2, i as u8, i as u8];
    }
    palette[239] = [255; 3];
    palette[240..].fill([230, 255, 255]); // Deliberately perfect, but reserved.
    let arcs = [LightningArc {
        x: 80,
        y: 160,
        to_x: 160,
        to_y: 20,
        ticks: 3,
        age: 0,
        seed: 4,
        anchor: None,
        to_anchor: None,
    }];
    let brightness =
        |rgb: [u8; 3]| 3 * u32::from(rgb[0]) + 6 * u32::from(rgb[1]) + u32::from(rgb[2]);
    for scale in [1, 4] {
        let mut canvas = Canvas::new(scale);
        canvas.clear(40);
        draw_lightning_arcs(&mut canvas, &arcs, &palette);
        assert_eq!(canvas.image.pixels[0], 40);
        let colors: std::collections::BTreeSet<_> = canvas.image.pixels.iter().copied().collect();
        assert!(
            colors.len() > 6,
            "glow must have a gradient, not a flat outline"
        );
        assert!(colors.iter().all(|index| *index < 240));
        assert!(
            colors
                .iter()
                .all(|index| brightness(palette[*index as usize]) >= brightness(palette[40]))
        );
        canvas.clear(239);
        draw_lightning_arcs(&mut canvas, &arcs, &palette);
        assert!(canvas.image.pixels.iter().all(|index| *index == 239));
    }
}

#[test]
fn lightning_handles_point_discharges_and_fully_offscreen_segments() {
    let mut palette = [[0; 3]; 256];
    palette[1] = [24, 198, 255];
    palette[2] = [230, 255, 255];
    let mut canvas = Canvas::new(4);
    let point = LightningArc {
        x: 0,
        y: 100,
        to_x: 0,
        to_y: 100,
        ticks: 3,
        age: 0,
        seed: 1,
        anchor: None,
        to_anchor: None,
    };
    draw_lightning_arcs(&mut canvas, &[point.clone()], &palette);
    assert_eq!(canvas.image.pixels[400 * canvas.image.width], 2);
    assert_eq!(canvas.image.pixels[0], 0);
    canvas.clear(0);
    let offscreen = LightningArc {
        x: -32768,
        y: -32768,
        to_x: -32000,
        to_y: -32000,
        ..point
    };
    draw_lightning_arcs(&mut canvas, &[offscreen], &palette);
    assert!(canvas.image.pixels.iter().all(|pixel| *pixel == 0));
}

fn anchored_arc(anchor: Option<u64>, to_anchor: Option<u64>) -> Command {
    Command::Arc {
        x: 160,
        y: 179,
        to_x: 86,
        to_y: 56,
        ticks: 8,
        anchor,
        to_anchor,
    }
}

#[test]
fn anchored_arcs_preserve_absolute_creation_positions_and_follow_both_ships() {
    let registry = registry();
    let mut world = world(&registry);
    let entity = world
        .spawn(&ContentId::from("test:ground"), 70, 40, &registry)
        .unwrap();
    let fixed = arc(8);
    world
        .apply_commands(
            &[
                anchored_arc(Some(0), Some(entity)),
                anchored_arc(Some(0), Some(0)),
                fixed,
                Command::Velocity {
                    entity,
                    vx: 3,
                    vy: -2,
                },
            ],
            &registry,
        )
        .unwrap();
    assert_eq!(
        (world.lightning_arcs[0].x, world.lightning_arcs[0].y),
        (160, 179)
    );
    assert_eq!(
        (world.lightning_arcs[0].to_x, world.lightning_arcs[0].to_y),
        (86, 56)
    );
    assert_eq!(world.lightning_arcs[0].anchor.unwrap().offset, [16, 19]);
    assert_eq!(world.lightning_arcs[0].to_anchor.unwrap().offset, [16, 16]);
    let mut runtime = ScriptRuntime::new();
    world
        .step(
            Input {
                absolute: Some([110, 130]),
                ..Input::default()
            },
            &registry,
            &mut runtime,
        )
        .unwrap();
    assert_eq!(
        (world.lightning_arcs[0].x, world.lightning_arcs[0].y),
        (126, 149)
    );
    assert_eq!(
        (world.lightning_arcs[0].to_x, world.lightning_arcs[0].to_y),
        (89, 54)
    );
    // Both ends of a ring segment retain their offset from the player origin.
    assert_eq!(
        (world.lightning_arcs[1].x, world.lightning_arcs[1].y),
        (126, 149)
    );
    assert_eq!(
        (world.lightning_arcs[1].to_x, world.lightning_arcs[1].to_y),
        (52, 26)
    );
    // Existing unanchored commands remain fixed in world space.
    assert_eq!(
        (world.lightning_arcs[2].x, world.lightning_arcs[2].y),
        (160, 160)
    );
    assert_eq!(
        (world.lightning_arcs[2].to_x, world.lightning_arcs[2].to_y),
        (160, 30)
    );
    assert!(world.lightning_arcs.iter().all(|arc| arc.age == 1));
}

#[test]
fn attached_lightning_renders_at_interpolated_ship_positions_without_mutating_world() {
    let registry = registry();
    let mut world = world(&registry);
    let entity = world
        .spawn(&ContentId::from("test:ground"), 70, 40, &registry)
        .unwrap();
    let point = |x, y, anchor| Command::Arc {
        x,
        y,
        to_x: x,
        to_y: y,
        ticks: 8,
        anchor,
        to_anchor: anchor,
    };
    world
        .apply_commands(
            &[
                point(160, 179, Some(0)),
                point(86, 56, Some(entity)),
                point(240, 80, None),
                Command::Velocity {
                    entity,
                    vx: 4,
                    vy: 2,
                },
            ],
            &registry,
        )
        .unwrap();
    world
        .step(
            Input {
                absolute: Some([154, 156]),
                ..Input::default()
            },
            &registry,
            &mut ScriptRuntime::new(),
        )
        .unwrap();
    let before = world.digest();
    let arcs_before = world.lightning_arcs.clone();
    let mut palette = [[0; 3]; 256];
    palette[1] = [24, 198, 255];
    palette[2] = [230, 255, 255];
    for scale in [1, 4] {
        for (alpha, player_point, enemy_point) in [
            (0.0, [160, 179], [86, 56]),
            (0.5, [165, 177], [88, 57]),
            (1.0, [170, 175], [90, 58]),
        ] {
            let mut canvas = Canvas::new(scale);
            draw_world_lightning_arcs(&mut canvas, &world, &palette, alpha);
            // Point discharges have no directional noise: compare the complete
            // image with fixed discharges at the independently expected sprite
            // positions, including the endpoint that is not attached to a ship.
            let mut expected_arcs = arcs_before.clone();
            for (arc, [x, y]) in
                expected_arcs
                    .iter_mut()
                    .zip([player_point, enemy_point, [240, 80]])
            {
                arc.x = x;
                arc.y = y;
                arc.to_x = x;
                arc.to_y = y;
                arc.anchor = None;
                arc.to_anchor = None;
            }
            let mut expected = Canvas::new(scale);
            draw_lightning_arcs(&mut expected, &expected_arcs, &palette);
            assert_eq!(
                canvas.image.pixels, expected.image.pixels,
                "attached arc drift at scale {scale}, alpha {alpha}"
            );
            assert_eq!(world.digest(), before);
            assert_eq!(world.lightning_arcs, arcs_before);
        }
    }
    world
        .apply_commands(&[Command::Despawn { entity }], &registry)
        .unwrap();
    let mut canvas = Canvas::new(4);
    draw_world_lightning_arcs(&mut canvas, &world, &palette, 0.0);
    let frozen = &world.lightning_arcs[1];
    assert!(frozen.anchor.is_none() && frozen.to_anchor.is_none());
    assert_ne!(
        canvas.image.pixels[frozen.y as usize * 4 * canvas.image.width + frozen.x as usize * 4],
        0
    );
}

#[test]
fn moved_then_despawned_anchors_freeze_at_the_last_command_position() {
    let registry = registry();
    let mut world = world(&registry);
    let entity = world
        .spawn(&ContentId::from("test:ground"), 70, 40, &registry)
        .unwrap();
    world
        .apply_commands(
            &[
                anchored_arc(Some(0), Some(entity)),
                Command::Move {
                    entity,
                    x: 90,
                    y: 70,
                },
                Command::Despawn { entity },
            ],
            &registry,
        )
        .unwrap();
    assert_eq!(
        (world.lightning_arcs[0].to_x, world.lightning_arcs[0].to_y),
        (106, 86)
    );
    assert!(world.lightning_arcs[0].to_anchor.is_none());
    let mut runtime = ScriptRuntime::new();
    world
        .step(
            Input {
                absolute: Some([120, 140]),
                ..Input::default()
            },
            &registry,
            &mut runtime,
        )
        .unwrap();
    assert_eq!(
        (world.lightning_arcs[0].x, world.lightning_arcs[0].y),
        (136, 159)
    );
    assert_eq!(
        (world.lightning_arcs[0].to_x, world.lightning_arcs[0].to_y),
        (106, 86)
    );
}

#[test]
fn automatically_retired_enemy_anchors_freeze_at_their_final_simulation_position() {
    let registry = registry();
    let mut world = world(&registry);
    let entity = world
        .spawn(&ContentId::from("test:ground"), 70, 240, &registry)
        .unwrap();
    let command = serde_json::from_value(json!({
        "op":"arc","x":160,"y":160,"to_x":86,"to_y":256,
        "to_anchor":entity,"ticks":8
    }))
    .unwrap();
    world
        .apply_commands(
            &[
                command,
                Command::Velocity {
                    entity,
                    vx: 0,
                    vy: 4,
                },
            ],
            &registry,
        )
        .unwrap();
    let mut runtime = ScriptRuntime::new();
    world
        .step(Input::default(), &registry, &mut runtime)
        .unwrap();
    assert!(world.enemies.is_empty());
    assert_eq!(
        (world.lightning_arcs[0].to_x, world.lightning_arcs[0].to_y),
        (86, 260)
    );
    assert!(world.lightning_arcs[0].to_anchor.is_none());
    world
        .step(Input::default(), &registry, &mut runtime)
        .unwrap();
    assert_eq!(
        (world.lightning_arcs[0].to_x, world.lightning_arcs[0].to_y),
        (86, 260)
    );
}

#[test]
fn missing_anchors_reject_the_entire_batch_and_do_not_accept_projectile_ids() {
    let registry = registry();
    let mut world = world(&registry);
    let before = world.digest();
    for command in [
        anchored_arc(Some(u64::MAX), None),
        anchored_arc(Some(0), Some(999)),
    ] {
        let error = world
            .apply_commands(
                &[
                    anchored_arc(Some(0), Some(0)),
                    Command::Credits { amount: 50 },
                    command,
                ],
                &registry,
            )
            .unwrap_err();
        assert!(error.to_string().contains("arc anchor does not exist"));
        assert_eq!(world.digest(), before);
        assert!(world.lightning_arcs.is_empty());
    }
    world
        .apply_commands(
            &[Command::Projectile {
                weapon: "test:selected".into(),
                x: 10,
                y: 10,
                vx: 0,
                vy: 0,
                hostile: false,
            }],
            &registry,
        )
        .unwrap();
    let projectile = world.projectiles[0].entity;
    assert!(
        world
            .apply_commands(&[anchored_arc(None, Some(projectile))], &registry)
            .is_err()
    );
    assert!(
        serde_json::from_value::<Command>(json!({
            "op":"arc","x":0,"y":0,"to_x":1,"to_y":1,"anchor":-1
        }))
        .is_err()
    );
}

#[test]
fn bad_anchor_callbacks_restore_already_moved_arcs_and_script_rng() {
    let registry = registry();
    let mut world = world(&registry);
    world
        .apply_commands(&[anchored_arc(Some(0), Some(0))], &registry)
        .unwrap();
    let before = world.digest();
    let arcs_before = world.lightning_arcs.clone();
    let mut runtime = ScriptRuntime::new();
    runtime.add("test", "equipped.rhai", "").unwrap();
    runtime
        .add(
            "test",
            "selected.rhai",
            r#"fn on_fire(e,s,r) {
        #{commands:[#{op:"arc",x:e.x,y:e.y,to_x:10,to_y:10,anchor:0,to_anchor:999}],
          state:#{used:r[0]}}
    }"#,
        )
        .unwrap();
    let error = world
        .step(
            Input {
                fire: true,
                absolute: Some([110, 130]),
                ..Input::default()
            },
            &registry,
            &mut runtime,
        )
        .unwrap_err();
    assert!(error.to_string().contains("arc anchor does not exist"));
    assert!(error.to_string().contains("test/selected.rhai::on_fire"));
    assert_eq!(world.digest(), before);
    assert_eq!(world.lightning_arcs, arcs_before);
    assert!(runtime.states.is_empty());
    assert!(runtime.rng.is_empty());
}

#[test]
fn following_arcs_remain_cosmetic_and_clamp_extreme_endpoints_to_world_bounds() {
    let registry = registry();
    let mut world = world(&registry);
    let mut plain = world.clone();
    world
        .apply_commands(
            &[Command::Arc {
                x: 32768,
                y: -32768,
                to_x: -32768,
                to_y: 32768,
                ticks: 8,
                anchor: Some(0),
                to_anchor: Some(0),
            }],
            &registry,
        )
        .unwrap();
    assert_eq!(world.digest(), plain.digest());
    assert!(
        serde_json::to_value(&world)
            .unwrap()
            .get("lightning_arcs")
            .is_none()
    );
    let mut runtime = ScriptRuntime::new();
    let mut plain_runtime = ScriptRuntime::new();
    for input in [
        Input {
            absolute: Some([282, 160]),
            ..Input::default()
        },
        Input {
            absolute: Some([5, 0]),
            ..Input::default()
        },
    ] {
        world.step(input, &registry, &mut runtime).unwrap();
        plain.step(input, &registry, &mut plain_runtime).unwrap();
        assert_eq!(world.digest(), plain.digest());
        assert_eq!(world.rng, plain.rng);
        assert!(world.lightning_arcs.iter().all(|arc| {
            [arc.x, arc.y, arc.to_x, arc.to_y]
                .iter()
                .all(|n| n.unsigned_abs() <= 32768)
        }));
    }
    assert_eq!(world.lightning_arcs[0].y, -32768);
    assert_eq!(world.lightning_arcs[0].to_x, -32768);
}
