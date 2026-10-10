//! A confirmed changed-capacity save retains equipment without increasing the
//! original combat shield limits or losing quantities on additive operations.
use raptor_replica::{
    content::{ContentId, ContentPack, Registry},
    modding::{Command, ScriptRuntime},
    persistence::Pilot,
    simulation::{Input, Pickup, World},
};
use serde_json::json;

fn registry() -> Registry {
    let mut registry = Registry::default();
    let pack: ContentPack = serde_json::from_value(json!({
        "items": [
            {"id":"base:forward_guns","name":"Guns","price":0},
            {"id":"base:energy","name":"Energy","price":0,"max_count":100,"initial_count":25,"shield":25,"legacy":16},
            {"id":"base:super_shield","name":"Super Shield","price":0,"max_count":100,"initial_count":100,"legacy":15},
            {"id":"base:ammo","name":"Ammo","price":0,"max_count":3}
        ],
        "missions":[{"id":"base:sector_1_wave_1","name":"Test","duration":10000}]
    })).unwrap();
    registry.apply(pack, "base").unwrap();
    registry.validate().unwrap();
    registry
}
fn id(value: &str) -> ContentId {
    value.into()
}
fn overflowing() -> Pilot {
    let mut pilot = Pilot::default();
    pilot.inventory.insert(id("base:energy"), 105);
    pilot.inventory.insert(id("base:super_shield"), 125);
    pilot.super_shield_reserves = vec![130];
    pilot
}
fn command(world: &mut World, registry: &Registry, command: Command) {
    world.apply_commands(&[command], registry).unwrap();
}
fn collect(world: &mut World, registry: &Registry, item: &str) {
    world.pickups.push(Pickup {
        entity: 123,
        item: item.into(),
        x: world.player.x,
        y: world.player.y,
        legacy: None,
    });
    world
        .step(Input::default(), registry, &mut ScriptRuntime::new())
        .unwrap();
    assert!(world.pickups.is_empty());
}

#[test]
fn confirmed_load_steps_and_snapshots_keep_full_charge_with_bounded_usable_shields() {
    let registry = registry();
    let saved = overflowing();
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("pilot.json");
    saved.save(&path).unwrap();
    let loaded = Pilot::inspect_load(&path, &registry, &[]).unwrap();
    assert!(!loaded.compatibility.is_compatible());
    let pilot = loaded.confirm_load();
    let mut world = World::new(&pilot.mission, &pilot, &registry).unwrap();
    assert_eq!((world.player.shield, world.player.super_shield), (100, 100));
    for _ in 0..10 {
        world
            .step(Input::default(), &registry, &mut ScriptRuntime::new())
            .unwrap();
    }
    let after = world.pilot(&pilot);
    assert_eq!(after.inventory, saved.inventory);
    assert_eq!(after.super_shield_reserves, saved.super_shield_reserves);
    // A serialized in-progress world also keeps its retained charge.
    let world: World = serde_json::from_value(serde_json::to_value(world).unwrap()).unwrap();
    assert_eq!(world.pilot(&pilot).inventory, saved.inventory);
}

#[test]
fn original_world_serialization_omits_overflow_and_old_worlds_default_to_zero() {
    let registry = registry();
    let pilot = Pilot::default();
    let world = World::new(&pilot.mission, &pilot, &registry).unwrap();
    let value = serde_json::to_value(world).unwrap();
    assert!(value.get("energy_overflow").is_none());
    assert!(value.get("super_shield_overflow").is_none());
    let decoded: World = serde_json::from_value(value).unwrap();
    assert_eq!(
        (decoded.energy_overflow, decoded.super_shield_overflow),
        (0, 0)
    );
}

#[test]
fn damage_consumes_usable_charge_and_destroyed_modules_do_not_resurrect_overflow() {
    let registry = registry();
    let pilot = overflowing();
    let mut world = World::new(&pilot.mission, &pilot, &registry).unwrap();
    command(
        &mut world,
        &registry,
        Command::Damage {
            entity: 0,
            amount: 20,
        },
    );
    assert_eq!(world.player.super_shield, 80);
    assert_eq!(world.pilot(&pilot).inventory[&id("base:super_shield")], 105);
    command(
        &mut world,
        &registry,
        Command::Damage {
            entity: 0,
            amount: 81,
        },
    );
    assert_eq!(world.player.super_shield, 100);
    assert_eq!(world.super_shield_overflow, 30);
    assert!(world.player.super_shield_reserves.is_empty());
    assert_eq!(world.pilot(&pilot).inventory[&id("base:super_shield")], 130);
    command(
        &mut world,
        &registry,
        Command::Damage {
            entity: 0,
            amount: 101,
        },
    );
    assert_eq!(world.super_shield_overflow, 0);
    assert!(
        !world
            .pilot(&pilot)
            .inventory
            .contains_key(&id("base:super_shield"))
    );
    command(
        &mut world,
        &registry,
        Command::Damage {
            entity: 0,
            amount: 10,
        },
    );
    assert_eq!(world.player.shield, 90);
    assert_eq!(world.pilot(&pilot).inventory[&id("base:energy")], 95);
    collect(&mut world, &registry, "base:energy");
    assert_eq!(world.player.shield, 100);
    assert_eq!(world.pilot(&pilot).inventory[&id("base:energy")], 105);
}

#[test]
fn additive_pickup_and_script_grants_never_reduce_quantities_above_current_capacity() {
    let registry = registry();
    let mut pilot = overflowing();
    pilot.inventory.insert(id("base:ammo"), 7);
    let mut world = World::new(&pilot.mission, &pilot, &registry).unwrap();
    for item in ["base:ammo", "base:energy", "base:super_shield"] {
        command(
            &mut world,
            &registry,
            Command::GiveItem {
                item: item.into(),
                count: 1,
            },
        );
    }
    assert_eq!(world.pilot(&pilot).inventory, pilot.inventory);
    collect(&mut world, &registry, "base:ammo");
    assert_eq!(world.pilot(&pilot).inventory[&id("base:ammo")], 7);
    command(
        &mut world,
        &registry,
        Command::ConsumeItem {
            item: "base:ammo".into(),
            count: 2,
        },
    );
    command(
        &mut world,
        &registry,
        Command::GiveItem {
            item: "base:ammo".into(),
            count: 1,
        },
    );
    assert_eq!(world.pilot(&pilot).inventory[&id("base:ammo")], 5);
}

#[test]
fn scripted_consumption_reduces_retained_charge_without_restoring_spent_charge() {
    let registry = registry();
    let pilot = overflowing();
    let mut world = World::new(&pilot.mission, &pilot, &registry).unwrap();
    command(
        &mut world,
        &registry,
        Command::ConsumeItem {
            item: "base:energy".into(),
            count: 10,
        },
    );
    command(
        &mut world,
        &registry,
        Command::ConsumeItem {
            item: "base:super_shield".into(),
            count: 110,
        },
    );
    assert_eq!(world.player.shield, 90);
    assert_eq!(world.pilot(&pilot).inventory[&id("base:energy")], 95);
    assert_eq!(world.player.super_shield, 0);
    assert_eq!(world.pilot(&pilot).inventory[&id("base:super_shield")], 15);
    command(
        &mut world,
        &registry,
        Command::ConsumeItem {
            item: "base:super_shield".into(),
            count: 15,
        },
    );
    command(
        &mut world,
        &registry,
        Command::ConsumeItem {
            item: "base:energy".into(),
            count: 90,
        },
    );
    assert_eq!(world.pilot(&pilot).inventory[&id("base:energy")], 5);
    assert_eq!(world.super_shield_overflow, 0);
    command(
        &mut world,
        &registry,
        Command::Damage {
            entity: 0,
            amount: 1,
        },
    );
    assert_eq!(world.pilot(&pilot).inventory[&id("base:super_shield")], 130);
}

#[test]
fn new_large_grants_are_split_once_without_duplicating_default_energy() {
    let mut registry = registry();
    for item in ["base:energy", "base:super_shield"] {
        registry.items.get_mut(&id(item)).unwrap().max_count = 200;
    }
    let mut pilot = Pilot::default();
    pilot.inventory.remove(&id("base:energy"));
    let mut world = World::new(&pilot.mission, &pilot, &registry).unwrap();
    for item in ["base:energy", "base:super_shield"] {
        command(
            &mut world,
            &registry,
            Command::GiveItem {
                item: item.into(),
                count: 125,
            },
        );
        assert_eq!(world.pilot(&pilot).inventory[&id(item)], 125);
    }
    assert_eq!((world.player.shield, world.player.super_shield), (100, 100));
}
