use raptor_replica::{
    content::{ContentId, ContentPack, Registry},
    modding::{Command, ScriptRuntime},
    persistence::Pilot,
    simulation::{Input, LineMove, World},
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
