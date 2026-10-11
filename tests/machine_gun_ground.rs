//! Starter forward guns must damage ground enemies and destructible terrain.
use raptor_replica::{
    assets::Catalog,
    content::{ContentId, ContentPack, Registry},
    mod_selection,
    modding::{self, ActiveMods, ScriptRuntime},
    persistence::Pilot,
    simulation::{Input, World},
};
use serde_json::json;
use std::path::PathBuf;

fn starter() -> Pilot {
    let mut pilot = Pilot::default();
    pilot.inventory.insert("base:energy".into(), 75);
    pilot.credits = 10_000;
    pilot
}

fn fixture(legacy_terrain: bool) -> Registry {
    let mut layout = vec![0; 90];
    layout[4 * 9 + 4] = 1;
    let pack: ContentPack = serde_json::from_value(json!({
        "weapons":[{"id":"base:projectile_forward_guns","name":"Forward Guns","damage":1,"speed":8,"cooldown":2,"behavior":"straight","target":"all","legacy":0,"art":{"asset":42,"logical_width":4,"logical_height":8,"frames":4}}],
        "items":[
            {"id":"base:forward_guns","name":"Forward Guns","price":0,"weapon":"base:projectile_forward_guns","legacy":0},
            {"id":"base:energy","name":"Energy","price":10000,"max_count":100,"initial_count":25,"legacy":16}
        ],
        "enemies":[{"id":"base:ground","name":"Ground emplacement","health":12,"speed":0,"ground":true,"reward":120}],
        "missions":[{"id":"base:sector_1_wave_1","name":"Ground range","duration":10000,"auto_complete":false,"columns":9,"layout":layout,"legacy_map":if legacy_terrain {Some(123)} else {None},
            "tiles":[
                {"art":{"asset":60,"logical_width":32,"logical_height":32}},
                {"art":{"asset":61,"logical_width":32,"logical_height":32},"health":2,"reward":230,"destroyed":{"asset":62,"logical_width":32,"logical_height":32}}
            ]}
        ]
    })).unwrap();
    let mut registry = Registry::default();
    registry.apply(pack, "base").unwrap();
    registry.validate().unwrap();
    registry
}

fn shoot(world: &mut World, registry: &Registry, scripts: &mut ScriptRuntime, ticks: usize) {
    assert_eq!(world.player.selected, None);
    assert_eq!(
        world
            .player
            .inventory
            .keys()
            .filter(|id| registry.items[*id].weapon.is_some())
            .count(),
        1,
        "the test must exercise only the default machine gun"
    );
    for _ in 0..ticks {
        world
            .step(
                Input {
                    fire: true,
                    ..Input::default()
                },
                registry,
                scripts,
            )
            .unwrap();
    }
}

#[test]
fn starter_machine_gun_destroys_ground_enemy_and_awards_its_reward() {
    let mut registry = fixture(false);
    registry
        .missions
        .get_mut(&Pilot::default().mission)
        .unwrap()
        .layout
        .fill(0);
    let pilot = starter();
    let mut world = World::new(&pilot.mission, &pilot, &registry).unwrap();
    let entity = world
        .spawn(&"base:ground".into(), 144, 72, &registry)
        .unwrap();
    let mut scripts = ScriptRuntime::new();
    shoot(&mut world, &registry, &mut scripts, 30);
    assert!(!world.enemies.iter().any(|enemy| enemy.entity == entity));
    assert_eq!(world.player.credits, pilot.credits + 120);
}

#[test]
fn starter_machine_gun_destroys_json_terrain_and_rewards_it_once() {
    let registry = fixture(false);
    let pilot = starter();
    let mut world = World::new(&pilot.mission, &pilot, &registry).unwrap();
    let mut scripts = ScriptRuntime::new();
    let mut explosion_sounds = 0;
    for _ in 0..60 {
        shoot(&mut world, &registry, &mut scripts, 1);
        explosion_sounds += world
            .sound_events
            .iter()
            .filter(|sound| sound.asset == 139)
            .count();
    }
    let position = 4 * 9 + 4;
    assert!(
        world.terrain_dead[position],
        "forward gun damage never destroys mod terrain (health {})",
        world.terrain_health[position]
    );
    assert_eq!(world.player.credits, pilot.credits + 230);
    assert_eq!(
        explosion_sounds, 1,
        "terrain destruction should emit one original ground-explosion sound"
    );
    let health = world.terrain_health[position];
    shoot(&mut world, &registry, &mut scripts, 30);
    assert_eq!(world.terrain_health[position], health);
    assert_eq!(world.player.credits, pilot.credits + 230);
}

#[test]
fn short_json_maps_use_their_actual_screen_position_for_forward_gun_hits() {
    let mut registry = fixture(false);
    let mission = registry
        .missions
        .get_mut(&Pilot::default().mission)
        .unwrap();
    mission.layout = vec![0; 36];
    mission.layout[9 + 4] = 1;
    let pilot = starter();
    let mut world = World::new(&pilot.mission, &pilot, &registry).unwrap();
    shoot(&mut world, &registry, &mut ScriptRuntime::new(), 25);
    assert!(world.terrain_dead[9 + 4]);
    assert_eq!(world.player.credits, pilot.credits + 230);
}

#[test]
fn starter_machine_gun_keeps_native_delayed_terrain_destruction() {
    let registry = fixture(true);
    let pilot = starter();
    let mut world = World::new(&pilot.mission, &pilot, &registry).unwrap();
    let mut scripts = ScriptRuntime::new();
    shoot(&mut world, &registry, &mut scripts, 60);
    assert!(world.terrain_dead[4 * 9 + 4]);
    assert!(world.terrain_settled[4 * 9 + 4]);
    assert_eq!(world.player.credits, pilot.credits + 230);
}

#[test]
fn json_terrain_collision_matches_its_visible_rows_after_the_native_scroll_limit() {
    let mut registry = fixture(false);
    let mission = registry
        .missions
        .get_mut(&Pilot::default().mission)
        .unwrap();
    mission.layout.fill(0);
    mission.layout[4] = 1;
    let pilot = starter();
    let mut world = World::new(&pilot.mission, &pilot, &registry).unwrap();
    let mut scripts = ScriptRuntime::new();
    for _ in 0..180 {
        world
            .step(Input::default(), &registry, &mut scripts)
            .unwrap();
    }
    // The first row is now at screen y=60, rather than the repeating native
    // terrain-window y=-4. It must be hittable at its displayed position.
    assert_eq!(world.scroll, 180);
    shoot(&mut world, &registry, &mut scripts, 25);
    assert!(world.terrain_dead[4]);
    assert_eq!(world.player.credits, pilot.credits + 230);
}

#[test]
fn json_terrain_that_scrolled_offscreen_cannot_absorb_forward_gun_shots() {
    let mut registry = fixture(false);
    let mission = registry
        .missions
        .get_mut(&Pilot::default().mission)
        .unwrap();
    mission.layout.fill(0);
    mission.layout[9 + 4] = 1;
    let pilot = starter();
    let mut world = World::new(&pilot.mission, &pilot, &registry).unwrap();
    let mut scripts = ScriptRuntime::new();
    for _ in 0..400 {
        world
            .step(Input::default(), &registry, &mut scripts)
            .unwrap();
    }
    shoot(&mut world, &registry, &mut scripts, 60);
    assert_eq!(world.terrain_health[9 + 4], 2);
    assert!(!world.terrain_dead[9 + 4]);
    assert_eq!(world.player.credits, pilot.credits);
}

#[test]
fn health_based_mod_terrain_does_not_require_replacement_artwork_to_be_destructible() {
    let mut registry = fixture(false);
    registry
        .missions
        .get_mut(&Pilot::default().mission)
        .unwrap()
        .tiles[1]
        .destroyed = None;
    let pilot = starter();
    let mut world = World::new(&pilot.mission, &pilot, &registry).unwrap();
    shoot(&mut world, &registry, &mut ScriptRuntime::new(), 60);
    assert!(world.terrain_dead[4 * 9 + 4]);
    assert_eq!(world.player.credits, pilot.credits + 230);
}

fn catalog() -> Catalog {
    let path = std::env::var_os("RAPTOR_TEST_DATA")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../data"));
    Catalog::open(&path).unwrap()
}

#[test]
#[ignore = "requires locally installed original catalog and packaged campaign definitions"]
fn real_forward_guns_damage_classic_and_iron_coast_ground_units() {
    let catalog = catalog();
    let base = Registry::base(&catalog).unwrap();
    let discovery = modding::discover(&PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("mods"));
    let mut enabled = Vec::new();
    for mission in [
        "iron_coast_mission_1",
        "iron_coast_mission_2",
        "iron_coast_mission_3",
        "iron_coast_mission_5",
    ] {
        enabled = mod_selection::plan_enable(&discovery, &enabled, mission).unwrap();
    }
    // Asset decoding is covered by package validation. This combat check loads
    // actual definitions and callbacks without requantizing every unrelated
    // terrain PNG before it can exercise a single enemy collision.
    let mut active = ActiveMods {
        registry: base.clone(),
        pins: Vec::new(),
        scripts: ScriptRuntime::new(),
    };
    for id in &enabled {
        let package = &discovery.mods[id];
        let content: ContentPack = serde_json::from_slice(
            &std::fs::read(package.root.join(&package.manifest.content)).unwrap(),
        )
        .unwrap();
        active
            .registry
            .asset_roots
            .insert(id.clone(), package.root.clone());
        active.registry.apply(content, id).unwrap();
        for script in &package.manifest.scripts {
            active
                .scripts
                .add(
                    id,
                    script,
                    &std::fs::read_to_string(package.root.join(script)).unwrap(),
                )
                .unwrap();
        }
    }
    active.registry.validate().unwrap();
    // A quiet JSON mission leaves enemy definitions, original gun art, damage,
    // movement and scripts intact while isolating their actual collisions.
    let mission: ContentPack = serde_json::from_value(json!({"missions":[{"id":"test:ground_range","name":"Ground range","duration":10000,"auto_complete":false}]})).unwrap();
    active.registry.apply(mission, "test").unwrap();
    // Retain the original ten-case kill assertions. Additional native enemies
    // include the 100-health secret cow; a starter pilot may die in this fixed
    // firing lane, so those cases check damage without claiming combat wins.
    let must_destroy: std::collections::BTreeSet<_> = base.missions
        [&ContentId::from("base:sector_1_wave_1")]
        .spawns
        .iter()
        .map(|spawn| spawn.enemy.clone())
        .filter(|id| base.enemies[id].ground && !base.enemies[id].boss)
        .collect();
    let mut ground: Vec<_> = base
        .missions
        .values()
        .filter(|mission| mission.legacy_map.is_some())
        .flat_map(|mission| mission.spawns.iter())
        .map(|spawn| spawn.enemy.clone())
        .filter(|id| base.enemies[id].ground && !base.enemies[id].boss)
        .collect();
    ground.sort();
    ground.dedup();
    assert!(
        ground.len() > 5,
        "exercise every native ground unit referenced by the 27 maps"
    );
    eprintln!(
        "Auditing {} original non-boss ground definitions",
        ground.len()
    );
    ground.extend(
        [
            "iron_coast_turret:unit",
            "iron_coast_mission_1:depot",
            "iron_coast_mission_2:relay",
            "iron_coast_mission_3:convoy",
            "iron_coast_mission_5:foundry",
        ]
        .map(ContentId::from),
    );
    let mut observations = Vec::new();
    let mut undamaged = Vec::new();
    for id in ground {
        let pilot = Pilot {
            mission: "test:ground_range".into(),
            ..starter()
        };
        let mut attempts = Vec::new();
        let mut final_world = None;
        let mut final_entity = 0;
        let mut lowest = active.registry.enemies[&id].health;
        let initial = lowest;
        for attempt in 0..2 {
            let mut world = World::new(&pilot.mission, &pilot, &active.registry).unwrap();
            let entity = world.spawn(&id, 144, 24, &active.registry).unwrap();
            lowest = initial;
            for _ in 0..120 {
                // Normal bounded absolute mouse movement aligns the ship with the
                // observed ground target; health and projectiles are never injected.
                let target = world.enemies.iter().find(|enemy| enemy.entity == entity);
                let Some(enemy) = target else {
                    break;
                };
                // The first attempt preserves the original ten-case firing lane.
                // If it cannot reach an additional native target, a second ordinary
                // input strategy uses a closer lane and leads horizontal movement.
                // Narrow moving units can outrun shots aimed at their old position;
                // hostile secret units can kill a stationary pilot before a distant
                // shot reaches them. Neither case establishes a collision defect.
                let y = if attempt == 0 { 160 } else { 80 };
                let lead = if attempt == 0 {
                    0
                } else {
                    let velocity = active.registry.enemies[&id].legacy.as_ref().map_or(
                        0,
                        |legacy| match legacy.fields[21] {
                            4 => -active.registry.enemies[&id].speed,
                            5 => active.registry.enemies[&id].speed,
                            _ => 0,
                        },
                    );
                    let flight_steps = ((y + 16 - enemy.y - enemy.height / 2).max(0) + 11) / 12;
                    velocity * flight_steps
                };
                let x = (enemy.x + enemy.width / 2 - 16 + lead).clamp(5, 282);
                world
                    .step(
                        Input {
                            fire: true,
                            absolute: Some([x, y]),
                            ..Input::default()
                        },
                        &active.registry,
                        &mut active.scripts,
                    )
                    .unwrap();
                if let Some(enemy) = world.enemies.iter().find(|enemy| enemy.entity == entity) {
                    lowest = lowest.min(enemy.health);
                }
            }
            attempts.push(json!({
                "control": if attempt == 0 { "current-position aim at y160" } else { "movement lead at y80" },
                "lowest_observed_health": lowest,
                "ticks": world.tick,
                "outcome": format!("{:?}", world.outcome),
                "remaining_shield": world.player.shield
            }));
            final_entity = entity;
            final_world = Some(world);
            if lowest < initial {
                break;
            }
        }
        let world = final_world.unwrap();
        let entity = final_entity;
        if lowest >= initial {
            undamaged.push(format!(
                "{id}: health {initial}, tick {}, outcome {:?}",
                world.tick, world.outcome
            ));
        }
        let target_present = world.enemies.iter().any(|enemy| enemy.entity == entity);
        let destroyed = !target_present && lowest <= 0;
        if must_destroy.contains(&id) || active.registry.enemies[&id].legacy.is_none() {
            assert!(
                destroyed,
                "starter machine gun did not destroy {id}; lowest health {lowest}, outcome {:?}",
                world.outcome
            );
        }
        if destroyed {
            assert_eq!(
                world.player.credits,
                pilot.credits + active.registry.enemies[&id].reward,
                "incorrect kill reward for {id}"
            );
        }
        observations.push(json!({
            "id": id,
            "name": active.registry.enemies[&id].name,
            "initial_health": initial,
            "lowest_observed_health": lowest,
            "destroyed": destroyed,
            "escaped": !target_present && !destroyed,
            "outcome": format!("{:?}", world.outcome),
            "ticks": world.tick,
            "reward": world.player.credits - pilot.credits,
            "remaining_shield": world.player.shield
            ,"attempts": attempts
        }));
    }
    if let Some(path) = std::env::var_os("RAPTOR_GROUND_REPORT") {
        std::fs::write(path, serde_json::to_vec_pretty(&observations).unwrap()).unwrap();
    }
    assert!(
        undamaged.is_empty(),
        "Ground definitions never damaged: {undamaged:?}"
    );
}

#[test]
#[ignore = "requires locally installed original catalog"]
fn real_forward_guns_damage_every_classic_destructible_terrain_definition() {
    use std::collections::BTreeMap;
    let catalog = catalog();
    let mut registry = Registry::base(&catalog).unwrap();
    // Buildings, parked cars and other scenery are native terrain, not EnemyDef.
    // Use every intact/destruction pair actually referenced by the 27 maps.
    let mut definitions = BTreeMap::new();
    for mission in registry
        .missions
        .values()
        .filter(|m| m.legacy_map.is_some())
    {
        for tile in &mission.tiles {
            if tile.destroyed.is_some() {
                definitions
                    .entry(tile.art.asset.unwrap())
                    .or_insert_with(|| tile.clone());
            }
        }
    }
    assert!(definitions.len() > 100);
    eprintln!(
        "Auditing {} original destructible terrain definitions",
        definitions.len()
    );
    let mission_id = ContentId::from("base:sector_1_wave_1");
    let background = registry.missions[&mission_id]
        .tiles
        .iter()
        .find(|tile| tile.destroyed.is_none())
        .unwrap()
        .clone();
    let mut observations = Vec::new();
    for (asset, tile) in definitions {
        let mission = registry.missions.get_mut(&mission_id).unwrap();
        mission.spawns.clear();
        mission.auto_complete = false;
        mission.duration = 10000;
        mission.tiles = vec![background.clone(), tile.clone()];
        mission.layout = vec![0; 90];
        let position = 4 * 9 + 4;
        mission.layout[position] = 1;
        let pilot = starter();
        let mut world = World::new(&mission_id, &pilot, &registry).unwrap();
        let mut scripts = ScriptRuntime::new();
        let mut sounds = 0;
        for _ in 0..100 {
            shoot(&mut world, &registry, &mut scripts, 1);
            sounds += world.sound_events.iter().filter(|s| s.asset == 139).count();
        }
        assert!(
            world.terrain_dead[position],
            "classic tile {asset:05x} was not destroyed; health {} from {}",
            world.terrain_health[position], tile.health
        );
        assert!(
            world.terrain_settled[position],
            "classic tile {asset:05x} never settled"
        );
        assert_eq!(
            world.player.credits,
            pilot.credits + tile.reward,
            "classic tile {asset:05x} reward"
        );
        assert_eq!(sounds, 1, "classic tile {asset:05x} ground-explosion sound");
        observations.push(json!({"asset":format!("{asset:05x}"),"original_health":tile.health,"reward":tile.reward,"destroyed":true,"settled":true,"ticks":world.tick}));
    }
    if let Some(path) = std::env::var_os("RAPTOR_TERRAIN_REPORT") {
        std::fs::write(path, serde_json::to_vec_pretty(&observations).unwrap()).unwrap();
    }
}

#[test]
#[ignore = "requires locally installed original catalog"]
fn real_wave_6_and_7_early_terrain_hits_match_visible_original_map_positions() {
    let catalog = catalog();
    let mut registry = Registry::base(&catalog).unwrap();
    let mut observations = Vec::new();
    let mut destroyed_count = 0;
    let mut static_count = 0;
    for wave in [6, 7] {
        let id = ContentId::new(format!("base:sector_1_wave_{wave}")).unwrap();
        let original = registry.missions[&id].clone();
        // Keep the complete original layout, art, tile rules and native map
        // identity. Only enemy spawns are suppressed to isolate terrain hits.
        let mut quiet = original.clone();
        quiet.spawns.clear();
        quiet.auto_complete = false;
        registry.missions.insert(id.clone(), quiet);
        for row in 130..150 {
            for col in 0..9 {
                let position = row * 9 + col;
                let tile = &original.tiles[original.layout[position]];
                let asset = tile.art.asset.unwrap();
                // Include every destructible object in the early map section,
                // plus the explicitly static industrial/fence artwork nearby.
                let destructible = tile.destroyed.is_some();
                let static_landmark = matches!(asset, 0x1045c..=0x1045f);
                if !destructible && !static_landmark {
                    continue;
                }
                let pilot = Pilot {
                    mission: id.clone(),
                    ..starter()
                };
                let mut world = World::new(&id, &pilot, &registry).unwrap();
                let mut scripts = ScriptRuntime::new();
                let rows = original.layout.len() / 9;
                // This is exactly scene()'s original terrain row position:
                // 200 - rows*32 + scroll + row*32. Advance ordinary idle
                // steps until the tested row is at y=40, then fire normally.
                let idle = (40 - (200 - rows as i32 * 32 + row as i32 * 32)).max(0);
                for _ in 0..idle {
                    world
                        .step(Input::default(), &registry, &mut scripts)
                        .unwrap();
                }
                assert_eq!(200 - rows as i32 * 32 + world.scroll + row as i32 * 32, 40);
                let initial_health = world.terrain_health[position];
                for _ in 0..70 {
                    world
                        .step(
                            Input {
                                fire: true,
                                absolute: Some([16 + col as i32 * 32, 160]),
                                ..Input::default()
                            },
                            &registry,
                            &mut scripts,
                        )
                        .unwrap();
                }
                if destructible {
                    assert!(
                        world.terrain_dead[position],
                        "wave{wave} row{row} col{col} asset{asset:05x} remains alive at its displayed position, health {}",
                        world.terrain_health[position]
                    );
                    assert!(world.terrain_settled[position]);
                    destroyed_count += 1;
                } else {
                    assert_eq!(world.terrain_health[position], initial_health);
                    assert!(!world.terrain_dead[position]);
                    static_count += 1;
                }
                observations.push(json!({"wave":wave,"row":row,"col":col,"asset":format!("{asset:05x}"),"destructible":destructible,"initial_health":initial_health,"final_health":world.terrain_health[position],"dead":world.terrain_dead[position],"settled":world.terrain_settled[position],"idle_steps":idle,"normal_fire_steps":70,"credits_gained":world.player.credits-pilot.credits}));
            }
        }
    }
    assert_eq!(destroyed_count, 17);
    assert!(static_count >= 4);
    if let Some(path) = std::env::var_os("RAPTOR_EARLY_TERRAIN_REPORT") {
        std::fs::write(path, serde_json::to_vec_pretty(&observations).unwrap()).unwrap();
    }
}

#[test]
#[ignore = "requires locally installed original catalog"]
fn real_wave_6_and_7_early_ground_spawns_use_original_visible_positions() {
    let catalog = catalog();
    let mut registry = Registry::base(&catalog).unwrap();
    let mut observations = Vec::new();
    for wave in [6, 7] {
        let id = ContentId::new(format!("base:sector_1_wave_{wave}")).unwrap();
        let original = registry.missions[&id].clone();
        let early: Vec<_> = original
            .spawns
            .iter()
            .filter(|spawn| {
                // Native difficulty codes 0..2 are disabled secret placements.
                // These four early ordinary emplacements are enabled at all levels.
                spawn.tick <= 600
                    && spawn.difficulty == 3
                    && registry.enemies[&spawn.enemy].ground
                    && !registry.enemies[&spawn.enemy].boss
            })
            .cloned()
            .collect();
        assert_eq!(early.len(), 2);
        for spawn in early {
            let mut isolated = original.clone();
            isolated.spawns = vec![spawn.clone()];
            isolated.auto_complete = false;
            registry.missions.insert(id.clone(), isolated);
            let pilot = Pilot {
                mission: id.clone(),
                ..starter()
            };
            let mut world = World::new(&id, &pilot, &registry).unwrap();
            let mut scripts = ScriptRuntime::new();
            let def = &registry.enemies[&spawn.enemy];
            let art = def.art.as_ref().unwrap();
            assert_eq!(def.legacy.as_ref().unwrap().fields[21], 3);
            let expected_x = spawn.x + 16 - art.logical_width as i32 / 2;
            let expected_y = spawn.y - art.logical_height as i32 / 2 + 1;
            let mut observed_spawn = None;
            let mut first_damage = None;
            let mut entity = None;
            let mut lowest = def.health;
            let mut last_health = None;
            for _ in 0..spawn.tick + 400 {
                // Capped mouse movement is achievable with ordinary controls.
                // Full original terrain remains present, including objects
                // that can intercept bullets before the emplacement is hit.
                let desired = (expected_x + art.logical_width as i32 / 2 - 16).clamp(5, 282);
                let x = world.player.x + (desired - world.player.x).clamp(-4, 4);
                world
                    .step(
                        Input {
                            fire: true,
                            absolute: Some([x, 160]),
                            ..Input::default()
                        },
                        &registry,
                        &mut scripts,
                    )
                    .unwrap();
                if let Some(enemy) = world
                    .enemies
                    .iter()
                    .find(|enemy| enemy.definition == spawn.enemy)
                {
                    if entity.is_none() {
                        entity = Some(enemy.entity);
                        assert_eq!([enemy.x, enemy.y], [expected_x, expected_y]);
                        assert_eq!(enemy.age, 1);
                        assert_eq!(world.tick, spawn.tick + 1);
                        observed_spawn = Some(
                            json!({"world_tick":world.tick,"position":[enemy.x,enemy.y],"previous_position":[enemy.px,enemy.py],"width":enemy.width,"height":enemy.height}),
                        );
                    }
                    lowest = lowest.min(enemy.health);
                    last_health = Some(enemy.health);
                    if first_damage.is_none() && enemy.health < def.health {
                        let hit_points: Vec<_> = world
                            .projectiles
                            .iter()
                            .filter(|projectile| {
                                projectile.weapon == ContentId::from("base:projectile_forward_guns")
                                    && projectile.legacy.as_ref().is_some_and(|shot| shot.hit)
                                    && projectile.x > enemy.x
                                    && projectile.x < enemy.x + enemy.width - 1
                                    && projectile.y > enemy.y
                                    && projectile.y < enemy.y + enemy.height - 1
                            })
                            .map(|projectile| [projectile.x, projectile.y])
                            .collect();
                        assert!(
                            !hit_points.is_empty(),
                            "first damage lacks a default-gun collision point"
                        );
                        first_damage = Some(
                            json!({"world_tick":world.tick,"health":enemy.health,"logical_bounds":[enemy.x,enemy.y,enemy.width,enemy.height],"interpolation_start":[enemy.px,enemy.py],"hit_points":hit_points}),
                        );
                    }
                } else if entity.is_some() {
                    break;
                }
            }
            assert!(entity.is_some(), "wave {wave} never spawns {}", spawn.enemy);
            assert!(
                lowest < def.health,
                "wave {wave} default gun never damages {}",
                spawn.enemy
            );
            assert!(
                last_health.is_some_and(|health| health <= 0),
                "wave {wave} target escaped rather than being destroyed: {} / health {last_health:?}",
                spawn.enemy
            );
            assert!(
                !world
                    .enemies
                    .iter()
                    .any(|enemy| Some(enemy.entity) == entity)
            );
            assert_eq!(format!("{:?}", world.outcome), "Playing");
            assert!(world.player.credits >= pilot.credits + def.reward);
            observations.push(json!({"wave":wave,"id":spawn.enemy,"name":def.name,"native_spawn_tick":spawn.tick,"native_spawn_position":[spawn.x,spawn.y],"observed_spawn":observed_spawn,"first_damage":first_damage,"initial_health":def.health,"lowest_observed_health":lowest,"destroyed":true,"finished_tick":world.tick,"remaining_shield":world.player.shield,"credits_gained":world.player.credits-pilot.credits}));
        }
    }
    assert_eq!(observations.len(), 4);
    if let Some(path) = std::env::var_os("RAPTOR_EARLY_SPAWN_REPORT") {
        std::fs::write(path, serde_json::to_vec_pretty(&observations).unwrap()).unwrap();
    }
}
