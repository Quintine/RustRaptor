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

const PACKAGES: [&str; 3] = ["pulse_cannon", "seeker_swarm", "ion_lance"];
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
fn each_weapon_package_is_independent_and_the_three_can_coexist() {
    for id in PACKAGES {
        let (_root, active) = activate(&[id]);
        assert_eq!(active.pins.len(), 1);
        assert_eq!(active.pins[0].version, "1.0.0");
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
    assert_eq!(all.pins.len(), 3);
    assert_eq!(all.registry.weapons.len(), 3);
    assert_eq!(all.registry.sounds.len(), 6);
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
    for id in PACKAGES {
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
    let mut hit_sound = false;
    for _ in 0..8 {
        world
            .step(Input::default(), &active.registry, &mut active.scripts)
            .unwrap();
        hit_sound |= world.mod_sounds.contains(&"pulse_cannon:impact".into());
    }
    assert_eq!(world.enemies[0].health, 92);
    assert_eq!(state(&active, "pulse_cannon")["hits"], 2);
    assert!(hit_sound);
    assert!(!world.effects.is_empty());
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
    world
        .step(Input::default(), &active.registry, &mut active.scripts)
        .unwrap();
    assert_eq!(
        world.enemies.iter().map(|e| e.health).collect::<Vec<_>>(),
        [84, 84, 100]
    );
    assert_eq!(state(&active, "ion_lance")["hits"], 4);
    assert!(world.mod_sounds.contains(&"ion_lance:impact".into()));
    assert!(!world.effects.is_empty());
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
    for id in PACKAGES {
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
