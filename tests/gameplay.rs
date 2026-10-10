use raptor_replica::{
    content::{ContentId, ContentPack, Registry},
    modding::{Command, ScriptRuntime},
    persistence::Pilot,
    simulation::{Input, LegacyProjectile, LineMove, Projectile, World},
};
use serde_json::json;

fn fixture() -> Registry {
    let pack: ContentPack = serde_json::from_value(json!({
        "weapons": [{"id":"base:projectile_forward_guns", "name":"Guns", "damage":1,"speed":8,"cooldown":2,"behavior":"straight","target":"all","legacy":0,"art":{"asset":42,"logical_width":4,"logical_height":8,"frames":4}}],
        "items":[
            {"id":"base:forward_guns","name":"Guns","price":0,"weapon":"base:projectile_forward_guns","legacy":0},
            {"id":"base:energy","name":"Shield","price":0,"max_count":100,"legacy":16},
            {"id":"base:super_shield","name":"Super Shield","price":0,"max_count":100,"legacy":15},
            {"id":"base:medkit","name":"Medkit","price":0,"max_count":5,"special":true,"consumable":true,"shield":25,"script":"medkit.rhai"}
        ],
        "enemies":[{"id":"base:drone","name":"Drone","speed":1,"health":20,"path":[[0,200]]}],
        "missions":[{"id":"base:sector_1_wave_1","name":"Synthetic Mission","duration":1000}]
    })).unwrap();
    let mut reg = Registry::default();
    reg.apply(pack, "base").unwrap();
    reg.validate().unwrap();
    reg
}

#[test]
fn demo_coordinates_bypass_normal_input_bounds() {
    let reg = fixture();
    let mut world = World::new(&Pilot::default().mission, &Pilot::default(), &reg).unwrap();
    let mut scripts = ScriptRuntime::new();
    world
        .step(
            Input {
                absolute: Some([284, 162]),
                demo_bank: Some(3),
                ..Input::default()
            },
            &reg,
            &mut scripts,
        )
        .unwrap();
    assert_eq!((world.player.x, world.player.y), (284, 162));
    world
        .step(
            Input {
                absolute: Some([284, 162]),
                ..Input::default()
            },
            &reg,
            &mut scripts,
        )
        .unwrap();
    assert_eq!((world.player.x, world.player.y), (282, 160));
}

#[test]
fn original_guns_use_banked_muzzles_and_accelerate_after_position_snapshot() {
    let reg = fixture();
    let mut world = World::new(&"base:sector_1_wave_1".into(), &Pilot::default(), &reg).unwrap();
    let mut scripts = ScriptRuntime::new();
    world
        .step(
            Input {
                fire: true,
                demo_bank: Some(3),
                ..Input::default()
            },
            &reg,
            &mut scripts,
        )
        .unwrap();
    // Center (160,176), gun offsets +6/-7, sprite half-size (2,4).
    assert_eq!(
        world
            .projectiles
            .iter()
            .map(|p| (p.x, p.y))
            .collect::<Vec<_>>(),
        [(164, 172), (151, 172)]
    );
    world
        .step(
            Input {
                fire: true,
                ..Input::default()
            },
            &reg,
            &mut scripts,
        )
        .unwrap();
    assert_eq!(world.projectiles.len(), 2);
    assert_eq!(world.projectiles[0].y, 163); // Speed rose from 8 to 9 after the first position.
    world
        .step(
            Input {
                fire: true,
                ..Input::default()
            },
            &reg,
            &mut scripts,
        )
        .unwrap();
    assert_eq!(world.projectiles.len(), 4);
    assert_eq!(world.projectiles[0].y, 153);
}

#[test]
fn enemy_paths_stop_at_endpoint_but_shots_cross_it() {
    let mut enemy = LineMove::new(0, 0, 2, 1);
    enemy.advance(5);
    assert_eq!((enemy.x, enemy.y), (2, 1));
    let mut shot = LineMove::new(0, 0, 2, 1);
    shot.advance_shot(5);
    assert_eq!((shot.x, shot.y), (5, 3));
    assert!(shot.done);
}

#[test]
fn mission_transition_preserves_remaining_super_shield() {
    let reg = fixture();
    let mut pilot = Pilot::default();
    pilot.inventory.insert("base:super_shield".into(), 31);
    let mut world = World::new(&pilot.mission, &pilot, &reg).unwrap();
    assert_eq!(world.player.super_shield, 31);
    world
        .apply_commands(
            &[Command::Damage {
                entity: 0,
                amount: 12,
            }],
            &reg,
        )
        .unwrap();
    let saved = world.pilot(&pilot);
    assert_eq!(saved.inventory[&ContentId::from("base:super_shield")], 19);
    assert_eq!(
        World::new(&pilot.mission, &saved, &reg)
            .unwrap()
            .player
            .super_shield,
        19
    );
}

#[test]
fn moving_an_entity_rebases_its_path() {
    let reg = fixture();
    let mut world = World::new(&"base:sector_1_wave_1".into(), &Pilot::default(), &reg).unwrap();
    let entity = world.spawn(&"base:drone".into(), 100, 0, &reg).unwrap();
    world
        .apply_commands(
            &[Command::Move {
                entity,
                x: 20,
                y: 20,
            }],
            &reg,
        )
        .unwrap();
    let mut scripts = ScriptRuntime::new();
    world.step(Input::default(), &reg, &mut scripts).unwrap();
    assert_eq!((world.enemies[0].x, world.enemies[0].y), (20, 20));
    world.step(Input::default(), &reg, &mut scripts).unwrap();
    assert_eq!((world.enemies[0].x, world.enemies[0].y), (20, 21));
}

#[test]
fn consumable_use_has_snapshot_and_only_fires_on_press() {
    let reg = fixture();
    let mut pilot = Pilot::default();
    pilot.inventory.insert("base:medkit".into(), 2);
    pilot.inventory.insert("base:energy".into(), 50);
    pilot.selected = Some("base:medkit".into());
    let mut world = World::new(&pilot.mission, &pilot, &reg).unwrap();
    let mut scripts = ScriptRuntime::new();
    scripts.add("base","medkit.rhai",r#"fn on_use(event,state,rng) {#{commands:[#{op:"credits",amount:7}], state:#{shield:event.player.shield,quantity:event.player.inventory["base:medkit"]}}}"#).unwrap();
    world
        .step(
            Input {
                special: true,
                ..Input::default()
            },
            &reg,
            &mut scripts,
        )
        .unwrap();
    assert_eq!(world.player.shield, 75);
    assert_eq!(world.player.credits, 7);
    assert_eq!(world.player.inventory[&ContentId::from("base:medkit")], 1);
    world
        .step(
            Input {
                special: true,
                ..Input::default()
            },
            &reg,
            &mut scripts,
        )
        .unwrap();
    assert_eq!(world.player.credits, 7);
    world.step(Input::default(), &reg, &mut scripts).unwrap();
    world
        .step(
            Input {
                special: true,
                ..Input::default()
            },
            &reg,
            &mut scripts,
        )
        .unwrap();
    assert_eq!(world.player.shield, 100);
    assert_eq!(world.player.credits, 14);
    assert_eq!(world.player.selected, None);
}

fn loss_fixture() -> Registry {
    let mut registry = fixture();
    registry.apply(serde_json::from_value(json!({"items":[
        {"id":"base:dumb_missile","name":"Dumb Missile","price":0,"special":true,"legacy":3},
        {"id":"base:mini_gun","name":"Mini Gun","price":0,"special":true,"legacy":4},
        {"id":"base:death_ray","name":"Death Ray","price":0,"special":true,"legacy":14},
        {"id":"base:detect","name":"Detector","price":0,"legacy":17},
        {"id":"base:itembuy6","name":"Cash Cargo","price":0,"max_count":50,"legacy":23}
    ]})).unwrap(), "base").unwrap();
    registry
}

fn low_shield_world(registry: &Registry) -> (World, ScriptRuntime) {
    let mut pilot = Pilot {
        difficulty: 3,
        ..Pilot::default()
    };
    for id in [
        "base:dumb_missile",
        "base:mini_gun",
        "base:death_ray",
        "base:detect",
    ] {
        pilot.inventory.insert(id.into(), 1);
    }
    pilot.inventory.insert("base:itembuy6".into(), 50);
    let mut world = World::new(&pilot.mission, &pilot, registry).unwrap();
    let mut scripts = ScriptRuntime::new();
    world
        .step(Input::default(), registry, &mut scripts)
        .unwrap();
    (world, scripts)
}

#[test]
fn low_shield_damage_loses_selected_weapon_then_cycles_in_legacy_order() {
    let registry = loss_fixture();
    let (mut world, mut scripts) = low_shield_world(&registry);
    world.player.selected = Some("base:death_ray".into());
    world
        .apply_commands(
            &[Command::Damage {
                entity: 0,
                amount: 92,
            }],
            &registry,
        )
        .unwrap();
    let seed = world.rng.seed;
    world
        .step(Input::default(), &registry, &mut scripts)
        .unwrap();
    assert_eq!(world.player.shield, 8);
    assert!(
        !world
            .player
            .inventory
            .contains_key(&"base:death_ray".into())
    );
    assert_eq!(world.player.selected, Some("base:dumb_missile".into()));
    assert_eq!(
        world.player.inventory[&ContentId::from("base:itembuy6")],
        50
    );
    assert!(world.sounds.contains(&119)); // FX_CRASH has no random pitch.
    assert_eq!(world.rng.seed, seed);

    world
        .apply_commands(
            &[Command::Damage {
                entity: 0,
                amount: 1,
            }],
            &registry,
        )
        .unwrap();
    world
        .step(Input::default(), &registry, &mut scripts)
        .unwrap();
    assert!(
        !world
            .player
            .inventory
            .contains_key(&"base:dumb_missile".into())
    );
    assert_eq!(world.player.selected, Some("base:mini_gun".into()));
}

#[test]
fn low_shield_without_selection_loses_highest_legacy_item_and_protects_essentials() {
    let registry = loss_fixture();
    let (mut world, mut scripts) = low_shield_world(&registry);
    world
        .apply_commands(
            &[Command::Damage {
                entity: 0,
                amount: 92,
            }],
            &registry,
        )
        .unwrap();
    world
        .step(Input::default(), &registry, &mut scripts)
        .unwrap();
    assert!(!world.player.inventory.contains_key(&"base:itembuy6".into()));
    for id in [
        "base:forward_guns",
        "base:energy",
        "base:detect",
        "base:death_ray",
    ] {
        assert!(
            world.player.inventory.contains_key(&id.into()),
            "protected or lower-numbered item {id} lost"
        );
    }
    assert_eq!(world.player.selected, None);
    world
        .step(Input::default(), &registry, &mut scripts)
        .unwrap();
    assert!(
        world
            .player
            .inventory
            .contains_key(&"base:death_ray".into())
    );
    assert!(!world.sounds.contains(&119)); // Remaining at low shield does not lose another item.
}

#[test]
fn low_energy_with_super_shield_and_damage_above_threshold_preserve_equipment() {
    let registry = loss_fixture();
    let (mut world, mut scripts) = low_shield_world(&registry);
    world.player.selected = Some("base:death_ray".into());
    world
        .apply_commands(
            &[Command::Damage {
                entity: 0,
                amount: 89,
            }],
            &registry,
        )
        .unwrap();
    world
        .step(Input::default(), &registry, &mut scripts)
        .unwrap();
    assert_eq!(world.player.shield, 11);
    assert!(
        world
            .player
            .inventory
            .contains_key(&"base:death_ray".into())
    );
    world.player.super_shield = 5;
    world
        .apply_commands(&[Command::Shield { amount: -3 }], &registry)
        .unwrap();
    world
        .step(Input::default(), &registry, &mut scripts)
        .unwrap();
    assert_eq!(world.player.shield, 8);
    assert!(
        world
            .player
            .inventory
            .contains_key(&"base:death_ray".into())
    );
    assert!(!world.sounds.contains(&119));
}

#[test]
fn legacy_kamikaze_arms_chase_when_final_leg_starts_and_crosses_target() {
    let mut registry = fixture();
    let enemy = registry
        .enemies
        .get_mut(&ContentId::from("base:drone"))
        .unwrap();
    enemy.health = 10000;
    enemy.speed = 4;
    enemy.path = vec![[0, -114], [0, -96]];
    let mut fields = vec![0; 26];
    fields[7] = 1;
    fields[9] = 1;
    fields[18] = 4;
    fields[19] = 2;
    fields[21] = 2; // Original F_KAMI.
    enemy.legacy = Some(raptor_replica::assets::LegacyEnemy {
        name: "Synthetic Kamikaze".into(),
        fields,
        shoot_type: vec![0; 24],
        engine_x: vec![0; 24],
        engine_y: vec![0; 24],
        engine_width: vec![0; 24],
        gun_x: vec![0; 24],
        gun_y: vec![0; 24],
        flight_x: vec![0; 32],
        flight_y: vec![0; 32],
    });
    let mut world = World::new(&Pilot::default().mission, &Pilot::default(), &registry).unwrap();
    let entity = world
        .spawn(&"base:drone".into(), 48, -131, &registry)
        .unwrap();
    let mut scripts = ScriptRuntime::new();
    let mut armed = false;
    let mut crossed = false;
    for _ in 0..120 {
        world
            .step(
                Input {
                    absolute: Some([96, 136]),
                    ..Input::default()
                },
                &registry,
                &mut scripts,
            )
            .unwrap();
        let Some(enemy) = world.enemies.iter().find(|e| e.entity == entity) else {
            break;
        };
        if enemy.kami == 1 {
            armed = true;
            assert_eq!(enemy.movement.ty, -12);
            assert!(!enemy.movement.done);
            assert_eq!(enemy.path_index, 1);
        }
        if enemy.kami == 2 {
            assert_eq!((enemy.movement.tx, enemy.movement.ty), (112, 152));
            crossed |= enemy.movement.y > 152;
        }
    }
    assert!(armed, "last authored leg never armed chase");
    assert!(crossed, "terminal chase stopped at its target");
    assert!(
        !world.enemies.iter().any(|e| e.entity == entity),
        "terminal kamikaze failed to retire offscreen"
    );
}

#[test]
fn legacy_beam_hits_launch_column_before_following_player_for_display() {
    let mut registry = fixture();
    registry.apply(serde_json::from_value(json!({
        "weapons":[{"id":"base:projectile_death_ray","name":"Death Ray","damage":6,"speed":0,"cooldown":7,"behavior":"beam","target":"all","legacy":14,"art":{"asset":50,"logical_width":2,"logical_height":8,"frames":4}}],
        "items":[{"id":"base:death_ray","name":"Death Ray","price":0,"special":true,"legacy":14,"weapon":"base:projectile_death_ray"}]
    })).unwrap(), "base").unwrap();
    let pilot = Pilot {
        selected: Some("base:death_ray".into()),
        inventory: [("base:death_ray".into(), 1), ("base:energy".into(), 100)]
            .into_iter()
            .collect(),
        ..Pilot::default()
    };
    let mut world = World::new(&pilot.mission, &pilot, &registry).unwrap();
    world
        .spawn(&"base:drone".into(), 157, 40, &registry)
        .unwrap();
    let mut scripts = ScriptRuntime::new();
    world
        .step(
            Input {
                fire: true,
                ..Input::default()
            },
            &registry,
            &mut scripts,
        )
        .unwrap();
    assert_eq!(world.enemies[0].health, 14);
    world
        .step(
            Input {
                absolute: Some([141, 160]),
                ..Input::default()
            },
            &registry,
            &mut scripts,
        )
        .unwrap();
    assert_eq!(world.projectiles[0].x, 156); // Followed artwork is outside the enemy.
    assert_eq!(world.enemies[0].health, 8); // Damage still tests launch column159.
}

fn collision_fixture() -> Registry {
    let mut registry = fixture();
    registry.apply(serde_json::from_value(json!({"weapons":[
        {"id":"base:projectile_energy_grab","name":"Energy Grab","damage":3,"speed":4,"cooldown":2,"behavior":"straight","target":"air","legacy":10,"art":{"asset":51,"logical_width":8,"logical_height":8,"frames":6}},
        {"id":"base:projectile_ground_bomb","name":"Ground Bomb","damage":50,"speed":1,"cooldown":30,"behavior":"straight","target":"ground","legacy":9,"art":{"asset":52,"logical_width":8,"logical_height":8}},
        {"id":"base:projectile_mega_bomb","name":"Mega Bomb","damage":50,"speed":2,"cooldown":60,"behavior":"straight","target":"all","legacy":11,"art":{"asset":53,"logical_width":8,"logical_height":8,"frames":4}},
        {"id":"base:hostile","name":"Hostile","damage":2,"speed":2,"cooldown":1,"behavior":"straight","target":"all"}
    ],"enemies":[
        {"id":"base:ground","name":"Ground Target","health":30,"ground":true},
        {"id":"base:air","name":"Air Target","health":64,"speed":0,"path":[[0,200]],"weapon":"base:hostile"}
    ]})).unwrap(), "base").unwrap();
    let air = registry
        .enemies
        .get_mut(&ContentId::from("base:air"))
        .unwrap();
    let mut fields = vec![0; 26];
    fields[5] = 1; // Native suck susceptibility.
    fields[7] = 1;
    fields[9] = 1;
    fields[13] = 64;
    fields[16] = 1;
    fields[21] = 3;
    fields[22] = 1;
    air.legacy = Some(raptor_replica::assets::LegacyEnemy {
        name: "Synthetic Susceptible Air Target".into(),
        fields,
        shoot_type: vec![1; 24],
        engine_x: vec![0; 24],
        engine_y: vec![0; 24],
        engine_width: vec![0; 24],
        gun_x: vec![16; 24],
        gun_y: vec![16; 24],
        flight_x: vec![0; 32],
        flight_y: vec![0; 32],
    });
    registry
}

fn inject_legacy_shot(
    world: &mut World,
    id: &str,
    x: i32,
    y: i32,
    done: bool,
    registry: &Registry,
) -> u64 {
    let weapon = &registry.weapons[&ContentId::from(id)];
    let art = weapon.art.as_ref().unwrap();
    let mut movement = LineMove::new(
        x + art.logical_width as i32 / 2,
        y + art.logical_height as i32 / 2,
        x,
        0,
    );
    movement.done = done;
    let entity = world.next_entity;
    world.next_entity += 1;
    world.projectiles.push(Projectile {
        entity,
        weapon: id.into(),
        x,
        y,
        px: x,
        py: y,
        vx: 0,
        vy: 0,
        hostile: false,
        age: 0,
        legacy_enemy: None,
        legacy: Some(LegacyProjectile {
            movement,
            speed: weapon.speed,
            frame: 0,
            art_frame: 0,
            delay: false,
            hit: false,
            start: [world.player.x + 16, world.player.y + 16],
        }),
    });
    entity
}

#[test]
fn energy_grab_hits_air_by_one_and_suppresses_fire_after_resistance_is_exhausted() {
    let registry = collision_fixture();
    let mut world = World::new(&Pilot::default().mission, &Pilot::default(), &registry).unwrap();
    world
        .spawn(&"base:ground".into(), 64, 64, &registry)
        .unwrap();
    let entity = world.spawn(&"base:air".into(), 64, 64, &registry).unwrap();
    let mut scripts = ScriptRuntime::new();
    for (expected_health, expected_resistance, disabled) in
        [(63, 1, false), (62, -2, false), (61, -2, true)]
    {
        inject_legacy_shot(
            &mut world,
            "base:projectile_energy_grab",
            80,
            80,
            false,
            &registry,
        );
        world
            .step(Input::default(), &registry, &mut scripts)
            .unwrap();
        let air = world.enemies.iter().find(|e| e.entity == entity).unwrap();
        assert_eq!(air.health, expected_health);
        assert_eq!(air.energy_resistance, expected_resistance);
        assert_eq!(air.shoot_disabled, disabled);
        assert_eq!(world.enemies[0].health, 30); // Ground target overlaps the shot.
    }
    assert!(world.sounds.contains(&134)); // FX_EGRAB.
    let hostile = world.projectiles.iter().filter(|p| p.hostile).count();
    world
        .step(Input::default(), &registry, &mut scripts)
        .unwrap();
    assert_eq!(
        world.projectiles.iter().filter(|p| p.hostile).count(),
        hostile
    );
    assert!(
        world
            .enemies
            .iter()
            .find(|e| e.entity == entity)
            .unwrap()
            .shoot_disabled
    );
}

#[test]
fn energy_grab_does_not_disable_an_immune_air_enemy() {
    let mut registry = collision_fixture();
    registry
        .enemies
        .get_mut(&"base:air".into())
        .unwrap()
        .legacy
        .as_mut()
        .unwrap()
        .fields[5] = 0;
    let mut world = World::new(&Pilot::default().mission, &Pilot::default(), &registry).unwrap();
    world.spawn(&"base:air".into(), 64, 64, &registry).unwrap();
    let mut scripts = ScriptRuntime::new();
    for _ in 0..5 {
        inject_legacy_shot(
            &mut world,
            "base:projectile_energy_grab",
            80,
            80,
            false,
            &registry,
        );
        world
            .step(Input::default(), &registry, &mut scripts)
            .unwrap();
    }
    assert_eq!(world.enemies[0].health, 59);
    assert_eq!(world.enemies[0].energy_resistance, 4);
    assert!(!world.enemies[0].shoot_disabled);
}

fn terrain_fixture() -> Registry {
    let mut registry = collision_fixture();
    let pack = serde_json::from_value(json!({"missions":[{
        "id":"base:sector_1_wave_1","name":"Terrain Fixture","duration":1000,"auto_complete":false,"legacy_map":123,"columns":3,"layout":vec![0;30],
        "tiles":[
            {"art":{"asset":60,"logical_width":32,"logical_height":32},"health":200,"destroyed":{"asset":61,"logical_width":32,"logical_height":32}},
            {"art":{"asset":62,"logical_width":32,"logical_height":32},"health":200}
        ]
    }],"overrides":["base:sector_1_wave_1"]})).unwrap();
    registry.apply(pack, "base").unwrap();
    registry
}

#[test]
fn ground_bomb_damages_tile_neighbors_and_overlapping_ground_enemy_together() {
    let registry = terrain_fixture();
    let mut world = World::new(&Pilot::default().mission, &Pilot::default(), &registry).unwrap();
    world
        .spawn(&"base:ground".into(), 48, 73, &registry)
        .unwrap();
    let shot = inject_legacy_shot(
        &mut world,
        "base:projectile_ground_bomb",
        64,
        89,
        false,
        &registry,
    );
    let mut scripts = ScriptRuntime::new();
    world
        .step(Input::default(), &registry, &mut scripts)
        .unwrap();
    assert_eq!(world.enemies[0].health, 25);
    assert!(!world.projectiles.iter().any(|p| p.entity == shot));
    for position in [19, 18, 16, 20] {
        assert_eq!(
            world.terrain_health[position], 150,
            "primary neighbor {position}"
        );
    }
    for position in [15, 13, 17] {
        assert_eq!(
            world.terrain_health[position], 175,
            "upper neighbor {position}"
        );
    }
    assert_eq!(world.terrain_health[22], 200);
    assert_eq!(world.terrain_health[21], 200);
}

#[test]
fn mega_bomb_uses_visible_destructible_tiles_at_fixed_twenty_damage_and_clears_shots() {
    let mut registry = terrain_fixture();
    registry
        .missions
        .get_mut(&Pilot::default().mission)
        .unwrap()
        .layout[8] = 1;
    let mut world = World::new(&Pilot::default().mission, &Pilot::default(), &registry).unwrap();
    world.terrain_dead[7] = true;
    world
        .spawn(&"base:ground".into(), 64, 64, &registry)
        .unwrap();
    let hostile = world.next_entity;
    world.next_entity += 1;
    world.projectiles.push(Projectile {
        entity: hostile,
        weapon: "base:hostile".into(),
        x: 100,
        y: 100,
        px: 100,
        py: 100,
        vx: 0,
        vy: 1,
        hostile: true,
        age: 0,
        legacy: None,
        legacy_enemy: None,
    });
    inject_legacy_shot(
        &mut world,
        "base:projectile_mega_bomb",
        100,
        100,
        true,
        &registry,
    );
    let mut scripts = ScriptRuntime::new();
    world
        .step(Input::default(), &registry, &mut scripts)
        .unwrap();
    assert_eq!(world.enemies[0].health, -20); // Original enemy damage50, separate from tiles.
    assert!(world.projectiles.is_empty());
    for position in 0..30 {
        let expected = if position < 6 || position == 7 || position == 8 {
            200
        } else {
            180
        };
        assert_eq!(
            world.terrain_health[position], expected,
            "terrain position{position}"
        );
    }
}
