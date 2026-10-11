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
    let first = &base.missions[&ContentId::from("base:sector_1_wave_1")];
    let mut ground: Vec<_> = first
        .spawns
        .iter()
        .map(|spawn| spawn.enemy.clone())
        .filter(|id| base.enemies[id].ground && !base.enemies[id].boss)
        .collect();
    ground.sort();
    ground.dedup();
    assert!(!ground.is_empty());
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
    for id in ground {
        let pilot = Pilot {
            mission: "test:ground_range".into(),
            ..starter()
        };
        let mut world = World::new(&pilot.mission, &pilot, &active.registry).unwrap();
        let entity = world.spawn(&id, 144, 24, &active.registry).unwrap();
        let initial = world.enemies[0].health;
        let mut lowest = initial;
        for _ in 0..120 {
            // Normal bounded absolute mouse movement aligns the ship with the
            // observed ground target; health and projectiles are never injected.
            let target = world.enemies.iter().find(|enemy| enemy.entity == entity);
            let Some(enemy) = target else {
                break;
            };
            let x = (enemy.x + enemy.width / 2 - 16).clamp(5, 282);
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
            if let Some(enemy) = world.enemies.iter().find(|enemy| enemy.entity == entity) {
                lowest = lowest.min(enemy.health);
            }
        }
        assert!(lowest < initial, "starter machine gun did not damage {id}");
        assert!(
            !world.enemies.iter().any(|enemy| enemy.entity == entity),
            "starter machine gun did not destroy {id}; lowest health {lowest}"
        );
        assert_eq!(
            world.player.credits,
            pilot.credits + active.registry.enemies[&id].reward,
            "incorrect kill reward for {id}"
        );
        observations.push(json!({
            "id": id,
            "name": active.registry.enemies[&id].name,
            "initial_health": initial,
            "lowest_observed_health": lowest,
            "destroyed": true,
            "ticks": world.tick,
            "reward": world.player.credits - pilot.credits,
            "remaining_shield": world.player.shield
        }));
    }
    if let Some(path) = std::env::var_os("RAPTOR_GROUND_REPORT") {
        std::fs::write(path, serde_json::to_vec_pretty(&observations).unwrap()).unwrap();
    }
}
