//! Validate the shipped weapon definitions/scripts using synthetic PNG and WAV inputs.
//! No original or locally generated game artwork is needed in CI.
use raptor_replica::{
    content::{ContentId, ContentPack, Registry},
    modding::{self, ActiveMods},
    persistence::Pilot,
    simulation::{Input, World},
};
use serde_json::{Value, json};
use std::{fs, path::Path};

const PROJECTILE_PACKAGES: [&str; 3] = ["pulse_cannon", "seeker_swarm", "ion_lance"];
const PACKAGES: [&str; 5] = [
    "pulse_cannon",
    "seeker_swarm",
    "ion_lance",
    "lightning_cannon",
    "lightning_shield",
];
fn content(value: Value) -> ContentPack {
    serde_json::from_value(value).unwrap()
}
fn base() -> Registry {
    let mut registry = Registry::default();
    registry.apply(content(json!({
        "items": [{"id":"base:energy","name":"Shield","price":100,"max_count":100}],
        "missions": [{"id":"base:practice","name":"Practice","duration":2000}],
        "enemies": [
            {"id":"base:target","name":"Stationary target","health":100,"speed":0},
            {"id":"base:ground_target","name":"Ground target","health":100,"speed":0,"ground":true}
        ]
    })), "base").unwrap();
    registry
}
fn wav() -> Vec<u8> {
    let mut bytes = b"RIFF".to_vec();
    bytes.extend(164u32.to_le_bytes());
    bytes.extend(b"WAVEfmt ");
    bytes.extend(16u32.to_le_bytes());
    bytes.extend(1u16.to_le_bytes());
    bytes.extend(1u16.to_le_bytes());
    bytes.extend(11025u32.to_le_bytes());
    bytes.extend(22050u32.to_le_bytes());
    bytes.extend(2u16.to_le_bytes());
    bytes.extend(16u16.to_le_bytes());
    bytes.extend(b"data");
    bytes.extend(128u32.to_le_bytes());
    bytes.extend([0; 128]);
    bytes
}
fn install_synthetic(root: &Path, id: &str) {
    let source = Path::new(env!("CARGO_MANIFEST_DIR")).join("mods").join(id);
    let target = root.join(id);
    fs::create_dir_all(target.join("scripts")).unwrap();
    fs::create_dir_all(target.join("art")).unwrap();
    fs::create_dir_all(target.join("audio")).unwrap();
    for file in [
        "mod.toml",
        "content.json",
        "scripts/weapon.rhai",
        "scripts/equipment.rhai",
    ] {
        fs::copy(source.join(file), target.join(file)).unwrap();
    }
    let definitions: Value =
        serde_json::from_slice(&fs::read(target.join("content.json")).unwrap()).unwrap();
    for entry in definitions["weapons"]
        .as_array()
        .unwrap()
        .iter()
        .chain(definitions["items"].as_array().unwrap())
    {
        let art = &entry["art"];
        if art.is_null() {
            continue;
        }
        for (property, scale) in [("png", 1), ("hd_png", 4)] {
            let image = image::RgbaImage::from_pixel(
                art["logical_width"].as_u64().unwrap() as u32 * scale,
                art["logical_height"].as_u64().unwrap() as u32 * scale,
                image::Rgba([60, 90, 120, 255]),
            );
            image
                .save(target.join(art[property].as_str().unwrap()))
                .unwrap();
        }
    }
    for sound in definitions["sounds"].as_array().unwrap() {
        fs::write(target.join(sound["file"].as_str().unwrap()), wav()).unwrap();
    }
}
fn activate(ids: &[&str]) -> (tempfile::TempDir, ActiveMods) {
    let root = tempfile::tempdir().unwrap();
    for id in ids {
        install_synthetic(root.path(), id);
    }
    let discovery = modding::discover(root.path());
    assert!(discovery.errors.is_empty(), "{:?}", discovery.errors);
    let active = ActiveMods::build(
        &base(),
        &discovery,
        &ids.iter().map(|id| id.to_string()).collect::<Vec<_>>(),
        None,
    )
    .unwrap();
    (root, active)
}
fn pilot(id: &str, registry: &Registry) -> Pilot {
    let equipment = ContentId::new(format!("{id}:equipment")).unwrap();
    Pilot {
        inventory: [(equipment.clone(), 1), ("base:energy".into(), 100)]
            .into_iter()
            .collect(),
        selected: registry.items[&equipment].special.then_some(equipment),
        mission: "base:practice".into(),
        ..Pilot::default()
    }
}
fn world(id: &str, registry: &Registry) -> World {
    World::new(&"base:practice".into(), &pilot(id, registry), registry).unwrap()
}
fn state<'a>(active: &'a ActiveMods, id: &str) -> &'a Value {
    &active.scripts.states[&format!("{id}/scripts/weapon.rhai")]
}

#[test]
fn each_weapon_package_is_independent_and_all_five_can_coexist() {
    for id in PACKAGES {
        let (_root, active) = activate(&[id]);
        assert_eq!(active.pins.len(), 1);
        assert_eq!(
            active.pins[0].version,
            if PROJECTILE_PACKAGES.contains(&id) {
                "1.1.0"
            } else {
                "1.0.0"
            },
            "{id}"
        );
        assert_eq!(active.registry.weapons.len(), 1);
        assert_eq!(active.registry.sounds.len(), 2);
        assert!(
            active
                .registry
                .items
                .contains_key(&format!("{id}:equipment").as_str().into())
        );
        assert!(
            active
                .registry
                .weapons
                .contains_key(&format!("{id}:projectile").as_str().into())
        );
    }
    let (_root, all) = activate(&PACKAGES);
    assert_eq!(all.pins.len(), 5);
    assert_eq!(all.registry.weapons.len(), 5);
    assert_eq!(all.registry.sounds.len(), 10);
    assert!(all.registry.overrides.is_empty());
}

#[test]
fn shop_charges_each_price_and_rejects_duplicate_equipment() {
    let (_root, active) = activate(&PACKAGES);
    for id in PACKAGES {
        let item: ContentId = format!("{id}:equipment").as_str().into();
        let price = active.registry.items[&item].price;
        let mut pilot = Pilot {
            credits: price,
            inventory: Default::default(),
            ..Pilot::default()
        };
        pilot.buy(&item, &active.registry).unwrap();
        assert_eq!(pilot.credits, 0);
        assert_eq!(pilot.inventory[&item], 1);
        assert!(pilot.buy(&item, &active.registry).is_err());
        pilot.sell(&item, &active.registry).unwrap();
        assert!(pilot.credits > 0);
        assert_eq!(pilot.inventory.get(&item).copied().unwrap_or(0), 0);
    }
}

#[test]
fn pulse_cannon_emits_paired_rounds_and_every_third_burst_is_scripted() {
    let (_root, mut active) = activate(&["pulse_cannon"]);
    let mut world = world("pulse_cannon", &active.registry);
    for _ in 0..19 {
        world
            .step(
                Input {
                    fire: true,
                    ..Input::default()
                },
                &active.registry,
                &mut active.scripts,
            )
            .unwrap();
    }
    assert_eq!(state(&active, "pulse_cannon")["bursts"], 3);
    assert_eq!(world.projectiles.len(), 8);
    assert_eq!(world.projectiles.iter().filter(|p| p.vx != 0).count(), 2);
    assert_eq!(world.mod_sounds, vec![ContentId::from("pulse_cannon:fire")]);
    assert!(
        world.effects.is_empty(),
        "firing into empty space must not create muzzle explosions"
    );
}

#[test]
fn continuous_firing_has_audio_and_projectiles_without_explosions_at_the_muzzle() {
    for id in PROJECTILE_PACKAGES {
        let (_root, mut active) = activate(&[id]);
        let mut world = world(id, &active.registry);
        let mut heard_fire = false;
        let mut saw_projectile = false;
        for _ in 0..80 {
            world
                .step(
                    Input {
                        fire: true,
                        ..Input::default()
                    },
                    &active.registry,
                    &mut active.scripts,
                )
                .unwrap();
            heard_fire |= world
                .mod_sounds
                .contains(&format!("{id}:fire").as_str().into());
            saw_projectile |= !world.projectiles.is_empty();
            assert!(
                world.effects.is_empty(),
                "{id} created an explosion while firing into empty space"
            );
        }
        assert!(
            heard_fire && saw_projectile,
            "{id} lost its firing sound or projectiles"
        );
    }
}

#[test]
fn pulse_hits_deal_damage_and_run_effect_audio_and_hit_state_callbacks() {
    let (_root, mut active) = activate(&["pulse_cannon"]);
    let mut world = world("pulse_cannon", &active.registry);
    world
        .spawn(&"base:target".into(), 140, 100, &active.registry)
        .unwrap();
    world
        .step(
            Input {
                fire: true,
                ..Input::default()
            },
            &active.registry,
            &mut active.scripts,
        )
        .unwrap();
    let mut hit_sound = world.mod_sounds.contains(&"pulse_cannon:impact".into());
    let mut saw_contact_arc = false;
    for _ in 0..8 {
        world
            .step(Input::default(), &active.registry, &mut active.scripts)
            .unwrap();
        hit_sound |= world.mod_sounds.contains(&"pulse_cannon:impact".into());
        saw_contact_arc |= !world.lightning_arcs.is_empty();
        assert!(world.lightning_arcs.iter().all(|arc| arc.ticks == 2));
        assert!(
            world.effects.is_empty(),
            "compact hits must not spawn explosions"
        );
    }
    assert_eq!(world.enemies[0].health, 92);
    assert_eq!(state(&active, "pulse_cannon")["hits"], 2);
    assert!(hit_sound && saw_contact_arc);
    assert!(
        world.lightning_arcs.is_empty(),
        "short contact feedback must expire"
    );
}

#[test]
fn seeker_swarm_homes_and_fragmentation_damages_nearby_enemies() {
    let (_root, mut active) = activate(&["seeker_swarm"]);
    let mut world = world("seeker_swarm", &active.registry);
    let primary = world
        .spawn(&"base:target".into(), 180, 110, &active.registry)
        .unwrap();
    let neighbor = world
        .spawn(&"base:ground_target".into(), 180, 110, &active.registry)
        .unwrap();
    world
        .step(
            Input {
                fire: true,
                ..Input::default()
            },
            &active.registry,
            &mut active.scripts,
        )
        .unwrap();
    assert_eq!(world.projectiles.len(), 3);
    assert!(world.projectiles.iter().all(|p| p.vx > 0));
    for _ in 0..12 {
        world
            .step(Input::default(), &active.registry, &mut active.scripts)
            .unwrap();
    }
    let target = world.enemies.iter().find(|e| e.entity == primary).unwrap();
    let nearby = world.enemies.iter().find(|e| e.entity == neighbor).unwrap();
    assert_eq!(target.health, 82);
    assert_eq!(nearby.health, 94);
    assert_eq!(state(&active, "seeker_swarm")["hits"], 3);
}

#[test]
fn ion_lance_pierces_air_and_ground_targets_in_its_column_only() {
    let (_root, mut active) = activate(&["ion_lance"]);
    let mut world = world("ion_lance", &active.registry);
    world
        .spawn(&"base:target".into(), 144, 100, &active.registry)
        .unwrap();
    world
        .spawn(&"base:ground_target".into(), 144, 60, &active.registry)
        .unwrap();
    world
        .spawn(&"base:target".into(), 220, 60, &active.registry)
        .unwrap();
    world
        .step(
            Input {
                fire: true,
                ..Input::default()
            },
            &active.registry,
            &mut active.scripts,
        )
        .unwrap();
    let heard_impact = world.mod_sounds.contains(&"ion_lance:impact".into());
    let saw_arc = !world.lightning_arcs.is_empty();
    world
        .step(Input::default(), &active.registry, &mut active.scripts)
        .unwrap();
    assert_eq!(
        world.enemies.iter().map(|e| e.health).collect::<Vec<_>>(),
        [84, 84, 100]
    );
    assert_eq!(state(&active, "ion_lance")["hits"], 4);
    assert!(heard_impact && saw_arc);
    assert!(
        !world.mod_sounds.contains(&"ion_lance:impact".into()),
        "the audio gate prevents repeated contact spam"
    );
    assert!(world.effects.is_empty());
    assert!(world.lightning_arcs.iter().all(|arc| arc.ticks == 2));
}

#[test]
fn equipped_specials_and_primary_upgrade_fire_without_consuming_equipment() {
    let (_root, mut active) = activate(&PACKAGES);
    let mut pilot = pilot("pulse_cannon", &active.registry);
    pilot.inventory.insert("seeker_swarm:equipment".into(), 1);
    pilot.inventory.insert("ion_lance:equipment".into(), 1);
    pilot.selected = Some("ion_lance:equipment".into());
    let mut world = World::new(&pilot.mission, &pilot, &active.registry).unwrap();
    world
        .step(
            Input {
                fire: true,
                ..Input::default()
            },
            &active.registry,
            &mut active.scripts,
        )
        .unwrap();
    assert_eq!(state(&active, "pulse_cannon")["bursts"], 1);
    assert_eq!(state(&active, "ion_lance")["bursts"], 1);
    assert!(
        !active
            .scripts
            .states
            .contains_key("seeker_swarm/scripts/weapon.rhai")
    );
    for id in PROJECTILE_PACKAGES {
        assert_eq!(
            world.player.inventory[&format!("{id}:equipment").as_str().into()],
            1
        );
    }
    world.player.selected = Some("seeker_swarm:equipment".into());
    world
        .step(
            Input {
                special: true,
                ..Input::default()
            },
            &active.registry,
            &mut active.scripts,
        )
        .unwrap();
    assert_eq!(state(&active, "seeker_swarm")["bursts"], 1);
}

#[test]
fn scripted_bursts_and_state_resume_deterministically() {
    let (_root, mut active) = activate(&["pulse_cannon"]);
    let mut world = world("pulse_cannon", &active.registry);
    for _ in 0..10 {
        world
            .step(
                Input {
                    fire: true,
                    ..Input::default()
                },
                &active.registry,
                &mut active.scripts,
            )
            .unwrap();
    }
    let mut resumed = world.clone();
    let (_other_root, mut other) = activate(&["pulse_cannon"]);
    other.scripts.states = active.scripts.states.clone();
    other.scripts.rng = active.scripts.rng.clone();
    for _ in 0..20 {
        let input = Input {
            fire: true,
            ..Input::default()
        };
        world
            .step(input, &active.registry, &mut active.scripts)
            .unwrap();
        resumed
            .step(input, &other.registry, &mut other.scripts)
            .unwrap();
    }
    assert_eq!(world.digest(), resumed.digest());
    assert_eq!(active.scripts.states, other.scripts.states);
    assert_eq!(
        serde_json::to_value(&active.scripts.rng).unwrap(),
        serde_json::to_value(&other.scripts.rng).unwrap()
    );
}

fn fire_once(world: &mut World, active: &mut ActiveMods) {
    world
        .step(
            Input {
                fire: true,
                ..Input::default()
            },
            &active.registry,
            &mut active.scripts,
        )
        .unwrap();
}

#[test]
fn lightning_cannon_chains_from_each_hit_with_falling_damage_and_a_four_target_cap() {
    let (_root, mut active) = activate(&["lightning_cannon"]);
    let mut world = world("lightning_cannon", &active.registry);
    for (enemy, x, y) in [
        ("base:target", 144, 80),
        ("base:ground_target", 184, 80),
        ("base:target", 224, 80),
        ("base:target", 264, 80),
        ("base:target", 264, 120),
        ("base:target", 32, 80),
    ] {
        world.spawn(&enemy.into(), x, y, &active.registry).unwrap();
    }
    fire_once(&mut world, &mut active);
    assert_eq!(
        world.enemies.iter().map(|e| e.health).collect::<Vec<_>>(),
        [68, 80, 88, 92, 100, 100]
    );
    assert_eq!(state(&active, "lightning_cannon")["hits"], 4);
    assert_eq!(state(&active, "lightning_cannon")["bursts"], 1);
    assert!(world.projectiles.is_empty(), "no damaging carrier shot");
    assert!(
        world.effects.is_empty(),
        "electrical arcs are not explosions"
    );
    assert!(world.mod_sounds.contains(&"lightning_cannon:fire".into()));
    assert!(world.mod_sounds.contains(&"lightning_cannon:impact".into()));
    assert_eq!(world.player.shield, 100);
}

#[test]
fn lightning_cannon_cannot_rehit_a_target_or_jump_across_a_gap() {
    let (_root, mut active) = activate(&["lightning_cannon"]);
    let mut world = world("lightning_cannon", &active.registry);
    for x in [144, 184, 234] {
        world
            .spawn(&"base:target".into(), x, 80, &active.registry)
            .unwrap();
    }
    // The initial victim dies, but its position still launches the next arc.
    world.enemies[0].health = 10;
    fire_once(&mut world, &mut active);
    assert_eq!(
        world.enemies.iter().map(|e| e.health).collect::<Vec<_>>(),
        [-22, 80, 100]
    );
    assert_eq!(state(&active, "lightning_cannon")["hits"], 2);
}

#[test]
fn lightning_cannon_requires_forward_aim_and_respects_its_cooldown() {
    let (_root, mut active) = activate(&["lightning_cannon"]);
    let mut world = world("lightning_cannon", &active.registry);
    for (x, y) in [(190, 80), (144, 196)] {
        world
            .spawn(&"base:target".into(), x, y, &active.registry)
            .unwrap();
    }
    fire_once(&mut world, &mut active);
    assert!(world.enemies.iter().all(|e| e.health == 100));
    assert_eq!(state(&active, "lightning_cannon")["hits"], 0);
    assert!(world.mod_sounds.contains(&"lightning_cannon:fire".into()));
    assert!(!world.mod_sounds.contains(&"lightning_cannon:impact".into()));
    let aligned = world
        .spawn(&"base:target".into(), 144, 80, &active.registry)
        .unwrap();
    for _ in 0..17 {
        fire_once(&mut world, &mut active);
    }
    assert_eq!(
        world
            .enemies
            .iter()
            .find(|e| e.entity == aligned)
            .unwrap()
            .health,
        100
    );
    assert_eq!(state(&active, "lightning_cannon")["bursts"], 1);
    fire_once(&mut world, &mut active);
    assert_eq!(
        world
            .enemies
            .iter()
            .find(|e| e.entity == aligned)
            .unwrap()
            .health,
        68
    );
    assert_eq!(state(&active, "lightning_cannon")["bursts"], 2);
}

#[test]
fn lightning_shield_zaps_close_aircraft_in_all_directions_only_while_firing() {
    let (_root, mut active) = activate(&["lightning_shield"]);
    let mut world = world("lightning_shield", &active.registry);
    for (enemy, x, y) in [
        ("base:target", 104, 160),
        ("base:target", 184, 160),
        ("base:target", 144, 120),
        ("base:target", 144, 196),
        ("base:target", 192, 160),
        ("base:ground_target", 184, 160),
    ] {
        world.spawn(&enemy.into(), x, y, &active.registry).unwrap();
    }
    world
        .step(Input::default(), &active.registry, &mut active.scripts)
        .unwrap();
    assert!(world.enemies.iter().all(|e| e.health == 100));
    assert!(
        !active
            .scripts
            .states
            .contains_key("lightning_shield/scripts/weapon.rhai")
    );
    assert!(world.player.selected.is_none());
    assert!(world.lightning_arcs.is_empty());
    fire_once(&mut world, &mut active);
    assert_eq!(
        world.enemies.iter().map(|e| e.health).collect::<Vec<_>>(),
        [98, 98, 98, 98, 100, 100]
    );
    assert_eq!(state(&active, "lightning_shield")["hits"], 4);
    assert!(world.mod_sounds.contains(&"lightning_shield:fire".into()));
    assert_eq!(
        world.player.inventory[&"lightning_shield:equipment".into()],
        1
    );
    assert_eq!(world.player.shield, 100);
    assert!(world.projectiles.is_empty());
    assert!(world.effects.is_empty());
    let center = (world.player.x + 16, world.player.y + 16);
    let zaps: Vec<_> = world
        .lightning_arcs
        .iter()
        .filter(|arc| arc.ticks == 3)
        .collect();
    assert_eq!(zaps.len(), 4);
    for arc in zaps {
        let radius_squared = (arc.x - center.0).pow(2) + (arc.y - center.1).pow(2);
        assert!((18 * 18..=20 * 20).contains(&radius_squared));
        assert_eq!(arc.anchor.as_ref().unwrap().entity, 0);
        assert_ne!(arc.to_anchor.as_ref().unwrap().entity, 0);
    }
    for _ in 0..7 {
        fire_once(&mut world, &mut active);
    }
    assert_eq!(state(&active, "lightning_shield")["bursts"], 1);
    fire_once(&mut world, &mut active);
    assert_eq!(state(&active, "lightning_shield")["bursts"], 2);
    assert_eq!(state(&active, "lightning_shield")["hits"], 8);
}

#[test]
fn lightning_shield_has_a_strict_range_boundary_and_a_bounded_pulse() {
    let (_root, mut active) = activate(&["lightning_shield"]);
    let mut world = world("lightning_shield", &active.registry);
    // Centers are far away, but the hull is exactly 28px from the pilot center.
    world
        .spawn(&"base:target".into(), 188, 160, &active.registry)
        .unwrap();
    world
        .spawn(&"base:target".into(), 189, 160, &active.registry)
        .unwrap();
    fire_once(&mut world, &mut active);
    assert_eq!(
        world.enemies.iter().map(|e| e.health).collect::<Vec<_>>(),
        [98, 100]
    );
    for _ in 0..4 {
        world
            .spawn(&"base:target".into(), 184, 160, &active.registry)
            .unwrap();
    }
    for _ in 0..8 {
        fire_once(&mut world, &mut active);
    }
    assert_eq!(state(&active, "lightning_shield")["hits"], 5);
    assert_eq!(world.enemies[0].health, 98);
    assert_eq!(world.enemies[1].health, 100);
}

#[test]
fn lightning_shield_is_quiet_when_no_aircraft_are_close_and_when_sold() {
    let (_root, mut active) = activate(&["lightning_shield"]);
    let mut world = world("lightning_shield", &active.registry);
    world
        .spawn(&"base:ground_target".into(), 184, 160, &active.registry)
        .unwrap();
    world
        .spawn(&"base:target".into(), 144, 80, &active.registry)
        .unwrap();
    fire_once(&mut world, &mut active);
    assert_eq!(state(&active, "lightning_shield")["hits"], 0);
    assert!(world.mod_sounds.is_empty());
    world
        .player
        .inventory
        .remove(&"lightning_shield:equipment".into());
    world
        .spawn(&"base:target".into(), 184, 160, &active.registry)
        .unwrap();
    for _ in 0..10 {
        fire_once(&mut world, &mut active);
    }
    assert!(world.enemies.iter().all(|e| e.health == 100));
    assert_eq!(state(&active, "lightning_shield")["bursts"], 1);
    assert!(world.lightning_arcs.is_empty());
}

#[test]
fn lightning_shield_halo_closes_around_hull_follows_movement_and_expires_after_firing() {
    let (_root, mut active) = activate(&["lightning_shield"]);
    let mut world = world("lightning_shield", &active.registry);
    fire_once(&mut world, &mut active);
    let ring = world.lightning_arcs.clone();
    assert_eq!(ring.len(), 16);
    assert!(world.mod_sounds.is_empty());
    assert_eq!(state(&active, "lightning_shield")["hits"], 0);
    let center = (world.player.x + 16, world.player.y + 16);
    for (i, arc) in ring.iter().enumerate() {
        assert_eq!(
            (arc.to_x, arc.to_y),
            (ring[(i + 1) % ring.len()].x, ring[(i + 1) % ring.len()].y)
        );
        let radius_squared = (arc.x - center.0).pow(2) + (arc.y - center.1).pow(2);
        assert!((18 * 18..=20 * 20).contains(&radius_squared));
        assert_eq!(arc.anchor.as_ref().unwrap().entity, 0);
        assert_eq!(arc.to_anchor.as_ref().unwrap().entity, 0);
    }
    let old_position = (world.player.x, world.player.y);
    world
        .step(
            Input {
                dx: 1,
                ..Input::default()
            },
            &active.registry,
            &mut active.scripts,
        )
        .unwrap();
    let movement = (
        world.player.x - old_position.0,
        world.player.y - old_position.1,
    );
    assert_ne!(movement, (0, 0));
    for (old, arc) in ring.iter().zip(&world.lightning_arcs) {
        assert_eq!((arc.x - old.x, arc.y - old.y), movement);
        assert_eq!((arc.to_x - old.to_x, arc.to_y - old.to_y), movement);
    }
    for _ in 0..8 {
        world
            .step(Input::default(), &active.registry, &mut active.scripts)
            .unwrap();
    }
    assert!(world.lightning_arcs.is_empty());
    assert_eq!(state(&active, "lightning_shield")["bursts"], 1);
}

#[test]
fn lightning_shield_fires_with_other_primaries_and_the_selected_cannon() {
    let (_root, mut active) = activate(&PACKAGES);
    let mut pilot = pilot("lightning_cannon", &active.registry);
    pilot
        .inventory
        .insert("lightning_shield:equipment".into(), 1);
    pilot.inventory.insert("pulse_cannon:equipment".into(), 1);
    let mut world = World::new(&pilot.mission, &pilot, &active.registry).unwrap();
    world
        .spawn(&"base:target".into(), 144, 80, &active.registry)
        .unwrap();
    world
        .spawn(&"base:target".into(), 184, 160, &active.registry)
        .unwrap();
    fire_once(&mut world, &mut active);
    for id in ["lightning_cannon", "lightning_shield", "pulse_cannon"] {
        assert_eq!(state(&active, id)["bursts"], 1);
        assert_eq!(
            world.player.inventory[&format!("{id}:equipment").as_str().into()],
            1
        );
    }
    assert_eq!(world.enemies[0].health, 68);
    assert_eq!(world.enemies[1].health, 98);
    assert_eq!(world.projectiles.len(), 2);
    world.player.selected = Some("ion_lance:equipment".into());
    world
        .player
        .inventory
        .insert("ion_lance:equipment".into(), 1);
    for _ in 0..8 {
        fire_once(&mut world, &mut active);
    }
    assert_eq!(state(&active, "lightning_shield")["bursts"], 2);
    assert_eq!(state(&active, "lightning_cannon")["bursts"], 1);
}

#[test]
fn lightning_loadout_state_and_damage_resume_deterministically() {
    let ids = ["lightning_cannon", "lightning_shield"];
    let (_root, mut active) = activate(&ids);
    let mut pilot = pilot("lightning_cannon", &active.registry);
    pilot
        .inventory
        .insert("lightning_shield:equipment".into(), 1);
    let mut world = World::new(&pilot.mission, &pilot, &active.registry).unwrap();
    for (x, y) in [(144, 80), (184, 80), (184, 160)] {
        world
            .spawn(&"base:target".into(), x, y, &active.registry)
            .unwrap();
    }
    for _ in 0..10 {
        fire_once(&mut world, &mut active);
    }
    let mut resumed = world.clone();
    let (_other_root, mut other) = activate(&ids);
    other.scripts.states = active.scripts.states.clone();
    other.scripts.rng = active.scripts.rng.clone();
    for tick in 0..24 {
        let input = Input {
            fire: tick % 3 != 0,
            ..Input::default()
        };
        world
            .step(input, &active.registry, &mut active.scripts)
            .unwrap();
        resumed
            .step(input, &other.registry, &mut other.scripts)
            .unwrap();
    }
    assert_eq!(world.digest(), resumed.digest());
    assert_eq!(active.scripts.states, other.scripts.states);
    assert_eq!(
        serde_json::to_value(&active.scripts.rng).unwrap(),
        serde_json::to_value(&other.scripts.rng).unwrap()
    );
}

#[test]
#[ignore = "requires original local palette/player artwork; writes ignored SD/HD visual proofs"]
fn lightning_mods_render_real_icons_and_discharge_arcs_in_sd_and_hd() {
    use raptor_replica::{
        assets::{Catalog, Sprite},
        render::{BitmapFont, Canvas, draw_lightning_arcs, nearest},
    };
    let package = Path::new(env!("CARGO_MANIFEST_DIR"));
    let data = std::env::var_os("RAPTOR_TEST_DATA")
        .map(std::path::PathBuf::from)
        .unwrap_or_else(|| package.join("../data"));
    let catalog = Catalog::open(data).unwrap();
    let palette = catalog.palette().unwrap();
    let font = BitmapFont::decode(&catalog.named("SYSTEM_FNT").unwrap()).unwrap();
    let player = catalog
        .sprite(catalog.id("LPLAYER_PIC").unwrap() + 3)
        .unwrap();
    let discovery = modding::discover(&package.join("mods"));
    let output = package.join("../.reference/lightning-mods");
    fs::create_dir_all(&output).unwrap();
    for id in ["lightning_cannon", "lightning_shield"] {
        let mut active =
            ActiveMods::build(&base(), &discovery, &[id.to_string()], Some(&catalog)).unwrap();
        let mut world = world(id, &active.registry);
        let positions = if id == "lightning_cannon" {
            vec![(144, 80), (184, 80), (224, 80), (264, 80)]
        } else {
            vec![(104, 160), (184, 160), (144, 120), (144, 196)]
        };
        for (x, y) in positions {
            world
                .spawn(&"base:target".into(), x, y, &active.registry)
                .unwrap();
        }
        fire_once(&mut world, &mut active);
        assert_eq!(
            world.lightning_arcs.len(),
            if id == "lightning_shield" { 20 } else { 4 }
        );
        let digest = world.digest();
        let script_rng = serde_json::to_value(&active.scripts.rng).unwrap();
        for (mode, scale) in [("sd", 1), ("hd", 4)] {
            let mut canvas = Canvas::new(scale);
            canvas.clear(0);
            font.text(
                &mut canvas,
                8,
                8,
                &format!(
                    "{} / {mode}",
                    active.registry.items[&format!("{id}:equipment").as_str().into()].name
                ),
                8,
            );
            let equipment = Sprite::png(
                &package
                    .join("mods")
                    .join(id)
                    .join(format!("art/equipment-{mode}.png")),
                &palette,
            )
            .unwrap();
            assert!(
                equipment
                    .pixels
                    .iter()
                    .all(|pixel| *pixel < 240 || *pixel == raptor_replica::assets::TRANSPARENT)
            );
            canvas.blit(&equipment, 8 * scale as i32, 28 * scale as i32);
            let price = active.registry.items[&format!("{id}:equipment").as_str().into()].price;
            font.text(&mut canvas, 8, 48, &format!("${price}"), 8);
            let unit = Sprite::png(
                &package.join(format!("mods/iron_coast_scout/art/unit-{mode}.png")),
                &palette,
            )
            .unwrap();
            // The scout's HD master is 8x; fit to the same 24px logical canvas
            // as the game renderer rather than drawing the raw master size.
            let mut fitted_unit = Sprite::blank(24 * scale, 24 * scale);
            for y in 0..fitted_unit.height {
                for x in 0..fitted_unit.width {
                    fitted_unit.pixels[y * fitted_unit.width + x] =
                        unit.pixels[(y * unit.height / fitted_unit.height) * unit.width
                            + x * unit.width / fitted_unit.width];
                }
            }
            for enemy in &world.enemies {
                canvas.blit(
                    &fitted_unit,
                    (enemy.x + 4) * scale as i32,
                    (enemy.y + 4) * scale as i32,
                );
            }
            canvas.blit(
                &nearest(&player, scale),
                world.player.x * scale as i32,
                world.player.y * scale as i32,
            );
            let scene = canvas.image.clone();
            // Show successive discharges at their actual firing cadence, not
            // just a single still: the cosmetic seed changes between bursts.
            let weapon = active.registry.items[&format!("{id}:equipment").as_str().into()]
                .weapon
                .as_ref()
                .unwrap();
            let cooldown = active.registry.weapons[weapon].cooldown;
            for frame in 0..cooldown * 3 {
                canvas.image = scene.clone();
                let mut arcs = world.lightning_arcs.clone();
                for arc in &mut arcs {
                    arc.age = frame % cooldown;
                    arc.seed = arc
                        .seed
                        .wrapping_add((frame / cooldown * cooldown).wrapping_mul(0x1656_67b1));
                }
                draw_lightning_arcs(&mut canvas, &arcs, &palette);
                image::save_buffer(
                    output.join(format!("{id}-{mode}-{frame:02}.png")),
                    &canvas.rgba(&palette, false),
                    canvas.image.width as u32,
                    canvas.image.height as u32,
                    image::ColorType::Rgba8,
                )
                .unwrap();
                if frame == 0 {
                    image::save_buffer(
                        output.join(format!("{id}-{mode}.png")),
                        &canvas.rgba(&palette, false),
                        canvas.image.width as u32,
                        canvas.image.height as u32,
                        image::ColorType::Rgba8,
                    )
                    .unwrap();
                }
            }
            assert_eq!(world.digest(), digest);
            assert_eq!(
                serde_json::to_value(&active.scripts.rng).unwrap(),
                script_rng
            );
        }
    }
}
