//! Original shield-module inventory and recharge behavior, with synthetic data.
use raptor_replica::{
    content::{ContentId, ContentPack, Registry},
    modding::{Command, ScriptRuntime},
    persistence::Pilot,
    simulation::{Input, Pickup, World},
};
use serde_json::json;

fn fixture() -> Registry {
    let mut items = vec![
        json!({"id":"base:forward_guns","name":"Guns","price":12000,"weapon":"base:shot","legacy":0}),
        json!({"id":"base:energy","name":"Energy","price":10000,"max_count":100,"initial_count":25,"shield":25,"legacy":16}),
        json!({"id":"base:super_shield","name":"Super Shield","price":78500,"max_count":100,"initial_count":100,"legacy":15}),
    ];
    for n in 0..20 {
        items.push(json!({"id":format!("base:filler_{n}"),"name":"Inventory slot","price":1}));
    }
    let pack: ContentPack = serde_json::from_value(json!({
        "items":items,
        "weapons":[{"id":"base:shot","name":"Gun","damage":1,"speed":8,"cooldown":5,"behavior":"straight","target":"all"}],
        "missions":[{"id":"base:sector_1_wave_1","name":"Shield fixture","duration":100000}]
    })).unwrap();
    let mut registry = Registry::default();
    registry.apply(pack, "base").unwrap();
    registry.validate().unwrap();
    registry
}
fn super_id() -> ContentId {
    "base:super_shield".into()
}
fn shielded(active: u32, reserves: &[u32]) -> Pilot {
    let mut pilot = Pilot {
        credits: 2_000_000,
        difficulty: 2,
        ..Pilot::default()
    };
    pilot.inventory.insert(super_id(), active);
    pilot.super_shield_reserves = reserves.to_vec();
    pilot
}
fn mission_world(pilot: &Pilot, registry: &Registry) -> World {
    World::new(&pilot.mission, pilot, registry).unwrap()
}
fn hit(world: &mut World, damage: i32, registry: &Registry) {
    world
        .apply_commands(
            &[Command::Damage {
                entity: 0,
                amount: damage,
            }],
            registry,
        )
        .unwrap();
}
fn idle(world: &mut World, ticks: usize, registry: &Registry) {
    let mut scripts = ScriptRuntime::new();
    for _ in 0..ticks {
        world
            .step(Input::default(), registry, &mut scripts)
            .unwrap();
    }
}
fn collect(world: &mut World, item: &str, registry: &Registry) {
    world.pickups.push(Pickup {
        entity: 9000,
        item: item.into(),
        x: world.player.x,
        y: world.player.y,
        legacy: None,
    });
    idle(world, 1, registry);
    assert!(world.pickups.is_empty());
}

#[test]
fn purchases_preserve_active_charge_and_enforce_five_modules_and_twenty_slots() {
    let registry = fixture();
    let mut pilot = shielded(17, &[]);
    for _ in 0..4 {
        pilot.buy(&super_id(), &registry).unwrap();
    }
    assert_eq!(pilot.inventory[&super_id()], 17);
    assert_eq!(pilot.super_shield_reserves, vec![100; 4]);
    assert_eq!(pilot.item_count(&super_id()), 5);
    assert_eq!(pilot.inventory_slots(), 7);
    let before = serde_json::to_value(&pilot).unwrap();
    assert!(pilot.buy(&super_id(), &registry).is_err());
    assert_eq!(serde_json::to_value(&pilot).unwrap(), before);
    let mut full = shielded(100, &[100]);
    for n in 0..16 {
        full.inventory
            .insert(format!("base:filler_{n}").as_str().into(), 1);
    }
    assert_eq!(full.inventory_slots(), 20);
    assert!(full.buy(&super_id(), &registry).is_err());
    full.inventory.insert("base:energy".into(), 75);
    full.buy(&"base:energy".into(), &registry).unwrap();
    assert_eq!(full.inventory[&ContentId::from("base:energy")], 100);
    full.validate(&registry, &[]).unwrap();
}

#[test]
fn selling_removes_full_equipped_module_and_selects_first_reserve() {
    let registry = fixture();
    let mut pilot = shielded(100, &[37, 100]);
    let credits = pilot.credits;
    pilot.sell(&super_id(), &registry).unwrap();
    assert_eq!(pilot.credits, credits + 39250);
    assert_eq!(pilot.inventory[&super_id()], 37);
    assert_eq!(pilot.super_shield_reserves, vec![100]);
    assert_eq!(pilot.item_count(&super_id()), 2);
    let before = serde_json::to_value(&pilot).unwrap();
    assert!(
        pilot.sell(&super_id(), &registry).is_err(),
        "partial active module cannot sell a reserve instead"
    );
    assert_eq!(serde_json::to_value(&pilot).unwrap(), before);
    pilot.inventory.insert(super_id(), 100);
    pilot.sell(&super_id(), &registry).unwrap();
    pilot.sell(&super_id(), &registry).unwrap();
    assert_eq!(pilot.item_count(&super_id()), 0);
    assert!(!pilot.inventory.contains_key(&super_id()));
}

#[test]
fn normal_energy_sales_remove_one_purchase_and_retain_positive_shield() {
    let registry = fixture();
    let mut pilot = Pilot::default();
    pilot.sell(&"base:energy".into(), &registry).unwrap();
    assert_eq!(pilot.inventory[&ContentId::from("base:energy")], 75);
    assert_eq!(pilot.credits, 5000);
    pilot.inventory.insert("base:energy".into(), 26);
    pilot.sell(&"base:energy".into(), &registry).unwrap();
    assert_eq!(pilot.inventory[&ContentId::from("base:energy")], 1);
    assert!(pilot.sell(&"base:energy".into(), &registry).is_err());
}

#[test]
fn hits_do_not_spill_into_reserves_or_normal_shields_and_exact_zero_remains_equipped() {
    let registry = fixture();
    let pilot = shielded(5, &[37, 0, 100]);
    let mut world = mission_world(&pilot, &registry);
    hit(&mut world, 5, &registry);
    assert_eq!(world.player.super_shield, 0);
    assert!(world.player.inventory.contains_key(&super_id()));
    assert_eq!(world.player.super_shield_reserves, vec![37, 0, 100]);
    hit(&mut world, 9000, &registry);
    assert_eq!(world.player.super_shield, 37);
    assert_eq!(world.player.shield, 100);
    hit(&mut world, 38, &registry);
    assert_eq!(
        world.player.super_shield, 0,
        "a zero-charge reserve may become equipped"
    );
    assert!(world.player.inventory.contains_key(&super_id()));
    hit(&mut world, 1, &registry);
    assert_eq!(world.player.super_shield, 100);
    hit(&mut world, 101, &registry);
    assert!(!world.player.inventory.contains_key(&super_id()));
    assert!(world.player.super_shield_reserves.is_empty());
    assert_eq!(world.player.shield, 100);
    hit(&mut world, 3, &registry);
    assert_eq!(world.player.shield, 97);
    let saved = world.pilot(&pilot);
    assert!(saved.super_shield_reserves.is_empty());
    assert_eq!(saved.inventory[&ContentId::from("base:energy")], 97);
}

#[test]
fn rookie_damage_is_halved_before_module_depletion_and_round_trips() {
    let registry = fixture();
    let mut pilot = shielded(5, &[71, 99]);
    pilot.difficulty = 0;
    let mut world = mission_world(&pilot, &registry);
    hit(&mut world, 7, &registry);
    assert_eq!(world.player.super_shield, 2);
    hit(&mut world, 4, &registry);
    assert_eq!(world.player.super_shield, 0);
    hit(&mut world, 5, &registry);
    assert_eq!(world.player.super_shield, 71);
    let saved = world.pilot(&pilot);
    saved.validate(&registry, &[]).unwrap();
    let restored = mission_world(&saved, &registry);
    assert_eq!(restored.player.super_shield, 71);
    assert_eq!(restored.player.super_shield_reserves, vec![99]);
}

#[test]
fn pickups_add_modules_without_refilling_active_charge_and_energy_only_charges_active() {
    let registry = fixture();
    let pilot = shielded(20, &[100; 4]);
    let mut world = mission_world(&pilot, &registry);
    collect(&mut world, "base:super_shield", &registry);
    assert_eq!(world.player.super_shield, 20);
    assert_eq!(
        world.player.super_shield_reserves,
        vec![100; 5],
        "native pickup capacity is slots; five is the shop limit"
    );
    collect(&mut world, "base:energy", &registry);
    assert_eq!(world.player.super_shield, 26);
    assert_eq!(world.player.super_shield_reserves, vec![100; 5]);
    world.player.shield = 90;
    collect(&mut world, "base:energy", &registry);
    assert_eq!(world.player.shield, 100);
    assert_eq!(
        world.player.super_shield, 26,
        "normal-shield overflow is discarded, not charged into a module"
    );
    world.player.super_shield = 0;
    world.player.inventory.insert(super_id(), 0);
    collect(&mut world, "base:energy", &registry);
    assert_eq!(
        world.player.super_shield, 0,
        "normal energy cannot revive an empty equipped module"
    );
    let mut full = shielded(20, &[99]);
    for n in 0..16 {
        full.inventory
            .insert(format!("base:filler_{n}").as_str().into(), 1);
    }
    let mut world = mission_world(&full, &registry);
    collect(&mut world, "base:super_shield", &registry);
    assert_eq!(world.player.super_shield, 20);
    assert_eq!(world.player.super_shield_reserves, vec![99]);
}

#[test]
fn idle_recharge_uses_97_steps_pauses_on_weapon_attempts_and_preserves_rng() {
    let registry = fixture();
    let mut pilot = shielded(44, &[88]);
    pilot.inventory.insert("base:energy".into(), 75);
    let mut world = mission_world(&pilot, &registry);
    let rng = world.rng;
    idle(&mut world, 96, &registry);
    assert_eq!(world.player.shield, 75);
    assert_eq!(world.shield_recharge_ticks, 96);
    let checkpoint = world.pilot(&pilot);
    let mut world = mission_world(&checkpoint, &registry);
    idle(&mut world, 1, &registry);
    assert_eq!(world.player.shield, 76);
    assert_eq!(world.player.super_shield, 44);
    assert_eq!(world.player.super_shield_reserves, vec![88]);
    assert_eq!(world.rng, rng);
    idle(&mut world, 96, &registry);
    world
        .step(
            Input {
                fire: true,
                ..Input::default()
            },
            &registry,
            &mut ScriptRuntime::new(),
        )
        .unwrap();
    assert_eq!(world.shield_recharge_ticks, 0);
    idle(&mut world, 96, &registry);
    assert_eq!(world.player.shield, 76);
    idle(&mut world, 1, &registry);
    assert_eq!(world.player.shield, 77);
    world.player.shield = 100;
    idle(&mut world, 97, &registry);
    assert_eq!(
        world.player.super_shield, 44,
        "one-unit idle recharge rounds to zero for super shields"
    );
    let mut ace = pilot.clone();
    ace.difficulty = 3;
    let mut ace = mission_world(&ace, &registry);
    idle(&mut ace, 200, &registry);
    assert_eq!(ace.player.shield, 75);
    let mut ending = mission_world(&pilot, &registry);
    ending.end_timer = Some(500);
    idle(&mut ending, 97, &registry);
    assert_eq!(ending.player.shield, 75);
}

#[test]
fn charge_unit_script_commands_preserve_reserves_and_rollback_all_module_state() {
    let registry = fixture();
    let pilot = shielded(12, &[44, 100]);
    let mut world = mission_world(&pilot, &registry);
    world
        .apply_commands(
            &[
                Command::GiveItem {
                    item: super_id().0,
                    count: 16,
                },
                Command::ConsumeItem {
                    item: super_id().0,
                    count: 18,
                },
            ],
            &registry,
        )
        .unwrap();
    assert_eq!(world.player.super_shield, 10);
    assert_eq!(world.player.inventory[&super_id()], 10);
    assert_eq!(world.player.super_shield_reserves, vec![44, 100]);
    let before = serde_json::to_value(&world).unwrap();
    assert!(
        world
            .apply_commands(
                &[
                    Command::Damage {
                        entity: 0,
                        amount: 15
                    },
                    Command::Velocity {
                        entity: 999,
                        vx: 1,
                        vy: 1
                    }
                ],
                &registry
            )
            .is_err()
    );
    assert_eq!(serde_json::to_value(&world).unwrap(), before);
    world
        .apply_commands(
            &[
                Command::ConsumeItem {
                    item: super_id().0,
                    count: 10,
                },
                Command::ConsumeItem {
                    item: "base:energy".into(),
                    count: 100,
                },
            ],
            &registry,
        )
        .unwrap();
    assert_eq!(world.player.super_shield, 0);
    assert_eq!(world.player.shield, 0);
    assert_eq!(world.player.inventory[&super_id()], 0);
    assert_eq!(world.player.inventory[&ContentId::from("base:energy")], 0);
    assert_eq!(world.player.super_shield_reserves, vec![44, 100]);
}

#[test]
fn consumed_equipment_releases_slot_selects_next_special_and_rolls_back_atomically() {
    let mut registry = fixture();
    for n in 0..2 {
        let item = registry
            .items
            .get_mut(&ContentId::from(format!("base:filler_{n}").as_str()))
            .unwrap();
        item.special = true;
        item.weapon = Some("base:shot".into());
    }
    let first = ContentId::from("base:filler_0");
    let second = ContentId::from("base:filler_1");
    let mut pilot = shielded(17, &[100]);
    for n in 0..16 {
        pilot
            .inventory
            .insert(format!("base:filler_{n}").as_str().into(), 1);
    }
    pilot.selected = Some(first.clone());
    assert_eq!(pilot.inventory_slots(), 20);
    let mut world = mission_world(&pilot, &registry);
    let before = serde_json::to_value(&world).unwrap();
    let consume = Command::ConsumeItem {
        item: first.0.clone(),
        count: 1,
    };
    assert!(
        world
            .apply_commands(
                &[
                    consume.clone(),
                    Command::Velocity {
                        entity: 999,
                        vx: 1,
                        vy: 1,
                    },
                ],
                &registry,
            )
            .is_err()
    );
    assert_eq!(serde_json::to_value(&world).unwrap(), before);
    world.apply_commands(&[consume], &registry).unwrap();
    assert!(!world.player.inventory.contains_key(&first));
    assert_eq!(world.player.selected, Some(second.clone()));
    assert_eq!(world.pilot(&pilot).inventory_slots(), 19);
    world
        .apply_commands(
            &[
                Command::GiveItem {
                    item: "base:filler_16".into(),
                    count: 1,
                },
                Command::ConsumeItem {
                    item: second.0,
                    count: 1,
                },
            ],
            &registry,
        )
        .unwrap();
    assert_eq!(world.player.selected, None);
    assert_eq!(world.pilot(&pilot).inventory_slots(), 19);
    world.pilot(&pilot).validate(&registry, &[]).unwrap();
}

#[test]
fn version_one_saves_without_extended_fields_remain_readable_without_source_changes() {
    let registry = fixture();
    let pilot = shielded(31, &[]);
    let mut old = serde_json::to_value(&pilot).unwrap();
    old.as_object_mut().unwrap().remove("super_shield_reserves");
    old.as_object_mut().unwrap().remove("shield_recharge_ticks");
    let bytes = serde_json::to_vec(&old).unwrap();
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path().join("old-v1.json");
    std::fs::write(&path, &bytes).unwrap();
    let saved = Pilot::load(&path, &registry, &[]).unwrap();
    assert_eq!(saved.item_count(&super_id()), 1);
    assert!(saved.super_shield_reserves.is_empty());
    assert_eq!(saved.shield_recharge_ticks, 0);
    let mut world = mission_world(&saved, &registry);
    hit(&mut world, 12, &registry);
    assert_eq!(world.pilot(&saved).inventory[&super_id()], 19);
    assert_eq!(std::fs::read(path).unwrap(), bytes);
    let mut bad = shielded(100, &[101]);
    assert!(bad.validate(&registry, &[]).is_err());
    bad.super_shield_reserves = vec![100];
    bad.inventory.remove(&super_id());
    assert!(bad.validate(&registry, &[]).is_err());
}

#[test]
fn failed_callback_restores_module_order_charge_recharge_and_script_state() {
    let mut registry = fixture();
    registry
        .missions
        .get_mut(&ContentId::from("base:sector_1_wave_1"))
        .unwrap()
        .script = Some("failed.rhai".into());
    let mut pilot = shielded(12, &[44, 100]);
    pilot.shield_recharge_ticks = 95;
    let mut world = mission_world(&pilot, &registry);
    let mut scripts = ScriptRuntime::new();
    scripts
        .add(
            "base",
            "failed.rhai",
            r#"
        fn on_mission_start(e, s, r) {
            #{commands:[#{op:"damage",entity:0,amount:15},
                #{op:"velocity",entity:999,vx:1,vy:1}],state:#{fired:true}}
        }
    "#,
        )
        .unwrap();
    let before = serde_json::to_value(&world).unwrap();
    let states = scripts.states.clone();
    let rng = scripts.rng.clone();
    assert!(
        world
            .step(Input::default(), &registry, &mut scripts)
            .is_err()
    );
    assert_eq!(serde_json::to_value(&world).unwrap(), before);
    assert_eq!(scripts.states, states);
    assert_eq!(scripts.rng, rng);
}

fn encrypt(bytes: &[u8]) -> Vec<u8> {
    let key = b"CASTLE";
    let mut index = 25 % key.len();
    let mut previous = key[index];
    bytes
        .iter()
        .map(|clear| {
            let byte = clear.wrapping_add(key[index]).wrapping_add(previous);
            previous = byte;
            index = (index + 1) % key.len();
            byte
        })
        .collect()
}
fn legacy_module_save(modules: &[(i32, i32)]) -> Vec<u8> {
    let mut header = vec![0_u8; 88];
    for (offset, value) in [
        (40, -1_i32),
        (60, modules.len() as i32 + 2),
        (64, 2),
        (68, 2),
        (72, 2),
        (76, 2),
    ] {
        header[offset..offset + 4].copy_from_slice(&value.to_le_bytes());
    }
    let mut records = vec![(1_i32, 0_i32, 1_i32), (75, 16, 1)];
    records.extend(modules.iter().map(|&(charge, inuse)| (charge, 15, inuse)));
    let mut body = vec![];
    for (charge, kind, inuse) in records {
        let mut record = vec![0_u8; 24];
        for (offset, value) in [(8, charge), (12, kind), (20, inuse)] {
            record[offset..offset + 4].copy_from_slice(&value.to_le_bytes());
        }
        body.extend(record);
    }
    [encrypt(&header), encrypt(&body)].concat()
}
#[test]
fn legacy_import_preserves_independent_charges_equipped_flag_and_inventory_order() {
    let registry = fixture();
    let bytes = legacy_module_save(&[(11, 0), (22, 0), (100, 1)]);
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path().join("CHAR0000.FIL");
    std::fs::write(&path, &bytes).unwrap();
    let pilot = Pilot::import_legacy(&path, &registry).unwrap();
    assert_eq!(pilot.inventory[&super_id()], 100);
    assert_eq!(pilot.super_shield_reserves, vec![11, 22]);
    assert_eq!(pilot.item_count(&super_id()), 3);
    let mut world = mission_world(&pilot, &registry);
    hit(&mut world, 101, &registry);
    assert_eq!(world.player.super_shield, 11);
    assert_eq!(world.player.super_shield_reserves, vec![22]);
    let output = temp.path().join("rust.json");
    world.pilot(&pilot).save(&output).unwrap();
    let restored = Pilot::load(&output, &registry, &[]).unwrap();
    assert_eq!(restored.item_count(&super_id()), 2);
    assert_eq!(std::fs::read(path).unwrap(), bytes);
}
