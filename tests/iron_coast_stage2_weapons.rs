//! API-level tests use synthetic artwork/audio; the ignored balance run uses
//! the installed original catalog and actual public mod packages.
use raptor_replica::{
    assets::Catalog,
    content::{ContentId, ContentPack, Registry},
    modding::{self, ActiveMods},
    persistence::Pilot,
    simulation::{EffectKind, Input, Outcome, World},
};
use serde_json::{Value, json};
use std::{fs, path::Path};

const PACKAGES: [&str; 2] = ["iron_coast_railburst", "iron_coast_depth_charge"];
const HEALTH: i32 = 100_000;

fn range(registry: &mut Registry) {
    let definitions: ContentPack = serde_json::from_value(json!({
        "missions": [{"id":"stage2range:range","name":"Controlled range","duration":10000,"auto_complete":false}],
        "enemies": [
            {"id":"stage2range:air","name":"Air fixture","health":HEALTH,"speed":0},
            {"id":"stage2range:ground","name":"Ground fixture","health":HEALTH,"speed":0,"ground":true,"script":"ground.rhai"}
        ]
    })).unwrap();
    registry.apply(definitions, "stage2range").unwrap();
}

fn attach_range_script(active: &mut ActiveMods) {
    active
        .scripts
        .add(
            "stage2range",
            "ground.rhai",
            r#"
        // Cancel terrain scroll after collision processing, without changing weapons.
        fn on_tick(event,state,random) {
            #{commands:[#{op:"move",entity:event.entity,x:event.x,y:event.y-1}],state:state}
        }
    "#,
        )
        .unwrap();
}

fn synthetic_install(root: &Path, id: &str) {
    let source = Path::new(env!("CARGO_MANIFEST_DIR")).join("mods").join(id);
    let target = root.join(id);
    for directory in ["scripts", "art", "audio"] {
        fs::create_dir_all(target.join(directory)).unwrap();
    }
    for file in ["mod.toml", "content.json", "scripts/weapon.rhai"] {
        fs::copy(source.join(file), target.join(file)).unwrap();
    }
    let content: Value =
        serde_json::from_slice(&fs::read(target.join("content.json")).unwrap()).unwrap();
    for entry in content["weapons"]
        .as_array()
        .unwrap()
        .iter()
        .chain(content["items"].as_array().unwrap())
    {
        let art = &entry["art"];
        for (property, scale) in [("png", 1), ("hd_png", 4)] {
            image::RgbaImage::from_pixel(
                art["logical_width"].as_u64().unwrap() as u32 * scale,
                art["logical_height"].as_u64().unwrap() as u32 * scale,
                image::Rgba([80, 100, 120, 255]),
            )
            .save(target.join(art[property].as_str().unwrap()))
            .unwrap();
        }
    }
    let mut wav = b"RIFF".to_vec();
    wav.extend(164u32.to_le_bytes());
    wav.extend(b"WAVEfmt ");
    wav.extend(16u32.to_le_bytes());
    wav.extend(1u16.to_le_bytes());
    wav.extend(1u16.to_le_bytes());
    wav.extend(11025u32.to_le_bytes());
    wav.extend(22050u32.to_le_bytes());
    wav.extend(2u16.to_le_bytes());
    wav.extend(16u16.to_le_bytes());
    wav.extend(b"data");
    wav.extend(128u32.to_le_bytes());
    wav.extend([0; 128]);
    for sound in content["sounds"].as_array().unwrap() {
        fs::write(target.join(sound["file"].as_str().unwrap()), &wav).unwrap();
    }
}

fn activate(ids: &[&str]) -> (tempfile::TempDir, ActiveMods) {
    let root = tempfile::tempdir().unwrap();
    for id in ids {
        synthetic_install(root.path(), id);
    }
    let discovery = modding::discover(root.path());
    assert!(discovery.errors.is_empty(), "{:?}", discovery.errors);
    let mut base = Registry::default();
    base.apply(
        serde_json::from_value(
            json!({"items":[{"id":"base:energy","name":"Shield","price":100,"max_count":100}]}),
        )
        .unwrap(),
        "base",
    )
    .unwrap();
    let mut active = ActiveMods::build(
        &base,
        &discovery,
        &ids.iter().map(|s| s.to_string()).collect::<Vec<_>>(),
        None,
    )
    .unwrap();
    range(&mut active.registry);
    attach_range_script(&mut active);
    (root, active)
}

fn world(item: &str, registry: &Registry) -> World {
    let id = ContentId::from(item);
    let pilot = Pilot {
        mission: "stage2range:range".into(),
        difficulty: 2,
        inventory: [(id.clone(), 1), ("base:energy".into(), 100)]
            .into_iter()
            .collect(),
        selected: registry.items[&id].special.then_some(id),
        ..Pilot::default()
    };
    World::new(&pilot.mission, &pilot, registry).unwrap()
}

fn step(world: &mut World, active: &mut ActiveMods, fire: bool) {
    world
        .step(
            Input {
                fire,
                ..Input::default()
            },
            &active.registry,
            &mut active.scripts,
        )
        .unwrap();
}

fn spawn(world: &mut World, active: &ActiveMods, targets: &[(&str, i32, i32)]) -> Vec<u64> {
    targets
        .iter()
        .map(|(kind, x, y)| {
            world
                .spawn(
                    &format!("stage2range:{kind}").as_str().into(),
                    *x,
                    *y,
                    &active.registry,
                )
                .unwrap()
        })
        .collect()
}

fn damage(world: &World, entities: &[u64]) -> Vec<i32> {
    entities
        .iter()
        .map(|id| {
            HEALTH
                - world
                    .enemies
                    .iter()
                    .find(|e| e.entity == *id)
                    .unwrap()
                    .health
        })
        .collect()
}

#[test]
fn independent_activation_coexistence_and_real_shop_resale() {
    for ids in [vec![PACKAGES[0]], vec![PACKAGES[1]], PACKAGES.to_vec()] {
        let (_root, active) = activate(&ids);
        assert_eq!(active.pins.len(), ids.len());
        assert!(active.registry.overrides.is_empty());
        for id in ids {
            let item: ContentId = format!("{id}:equipment").as_str().into();
            let definition = &active.registry.items[&item];
            assert!(definition.special && !definition.consumable);
            assert!(definition.description.contains("Selectable"));
            let mut pilot = Pilot {
                credits: definition.price,
                inventory: Default::default(),
                ..Pilot::default()
            };
            pilot.buy(&item, &active.registry).unwrap();
            assert_eq!(pilot.credits, 0);
            assert_eq!(pilot.inventory[&item], 1);
            assert!(pilot.buy(&item, &active.registry).is_err());
            pilot.selected = Some(item.clone());
            pilot.sell(&item, &active.registry).unwrap();
            assert_eq!(pilot.credits, definition.price / 2);
            assert!(!pilot.inventory.contains_key(&item));
            assert!(pilot.selected.is_none());
        }
    }
}

#[test]
fn railburst_contact_penetrates_only_three_aligned_targets_with_falling_damage() {
    let (_root, mut active) = activate(&[PACKAGES[0]]);
    let mut world = world("iron_coast_railburst:equipment", &active.registry);
    let ids = spawn(
        &mut world,
        &active,
        &[
            ("air", 144, 104),
            ("ground", 144, 64),
            ("air", 144, 24),
            ("air", 144, 0),
            ("air", 200, 64),
        ],
    );
    step(&mut world, &mut active, true);
    assert!(
        world.effects.is_empty(),
        "no muzzle explosion before real contact"
    );
    for _ in 0..3 {
        step(&mut world, &mut active, false);
    }
    assert_eq!(damage(&world, &ids), [42, 32, 22, 0, 0]);
    assert_eq!(
        active.scripts.states["iron_coast_railburst/scripts/weapon.rhai"]["hits"],
        3
    );
    assert!(world.effects.iter().any(|e| e.kind == EffectKind::SmallAir));
    assert!(
        world
            .effects
            .iter()
            .any(|e| e.kind == EffectKind::SmallGround)
    );
    assert_eq!(
        world.player.inventory[&"iron_coast_railburst:equipment".into()],
        1
    );
}

#[test]
fn depth_charge_has_contact_only_ground_splash_falloff_radius_and_neighbor_cap() {
    let (_root, mut active) = activate(&[PACKAGES[1]]);
    let mut world = world("iron_coast_depth_charge:equipment", &active.registry);
    let ids = spawn(
        &mut world,
        &active,
        &[
            ("ground", 144, 96),
            ("ground", 154, 96),
            ("ground", 169, 96),
            ("ground", 179, 96),
            ("ground", 180, 96),
            ("ground", 181, 96),
            ("air", 144, 96),
        ],
    );
    step(&mut world, &mut active, true);
    assert!(world.effects.is_empty());
    for _ in 0..8 {
        step(&mut world, &mut active, false);
    }
    assert_eq!(damage(&world, &ids), [72, 36, 20, 20, 0, 0, 0]);
    assert_eq!(world.effects.len(), 1);
    assert_eq!(world.effects[0].kind, EffectKind::GroundBlast);
    assert!(world.effects[0].ground);
    assert_eq!(
        active.scripts.states["iron_coast_depth_charge/scripts/weapon.rhai"]["hits"],
        4
    );
}

#[test]
fn unselected_idle_and_missed_shots_do_not_inflict_damage_or_make_explosions() {
    let (_root, mut active) = activate(&PACKAGES);
    for id in PACKAGES {
        active
            .scripts
            .restore((Default::default(), Default::default()));
        let mut world = world(&format!("{id}:equipment"), &active.registry);
        world.player.inventory.insert(
            format!(
                "{}:equipment",
                if id == PACKAGES[0] {
                    PACKAGES[1]
                } else {
                    PACKAGES[0]
                }
            )
            .as_str()
            .into(),
            1,
        );
        let ids = spawn(
            &mut world,
            &active,
            &[("air", 220, 80), ("ground", 220, 80)],
        );
        for _ in 0..60 {
            step(&mut world, &mut active, false);
        }
        assert!(active.scripts.states.keys().all(|s| !s.starts_with(id)));
        step(&mut world, &mut active, true);
        for _ in 0..35 {
            step(&mut world, &mut active, false);
        }
        assert_eq!(damage(&world, &ids), [0, 0]);
        assert!(world.effects.is_empty());
        let other = if id == PACKAGES[0] {
            PACKAGES[1]
        } else {
            PACKAGES[0]
        };
        assert!(
            !active
                .scripts
                .states
                .contains_key(&format!("{other}/scripts/weapon.rhai"))
        );
    }
}

#[test]
fn saved_script_state_and_rng_resume_identically_and_failed_callbacks_roll_back() {
    for id in PACKAGES {
        let (_root, mut active) = activate(&[id]);
        let mut original = world(&format!("{id}:equipment"), &active.registry);
        spawn(
            &mut original,
            &active,
            &[("ground", 144, 96), ("ground", 154, 96), ("air", 144, 64)],
        );
        for _ in 0..75 {
            step(&mut original, &mut active, true);
        }
        let mut resumed = original.clone();
        let (_other, mut replay) = activate(&[id]);
        let serialized = serde_json::to_vec(&active.scripts.checkpoints()).unwrap();
        replay
            .scripts
            .restore(serde_json::from_slice(&serialized).unwrap());
        for _ in 0..100 {
            step(&mut original, &mut active, true);
            step(&mut resumed, &mut replay, true);
        }
        assert_eq!(original.digest(), resumed.digest());
        assert_eq!(
            serde_json::to_value(active.scripts.checkpoints()).unwrap(),
            serde_json::to_value(replay.scripts.checkpoints()).unwrap()
        );
        active.scripts.add(id,"scripts/weapon.rhai",r#"fn on_fire(event,state,random){#{commands:[#{op:"credits",amount:500},#{op:"damage",entity:999999999,amount:1}],state:#{counter:random[0]}}}"#).unwrap();
        let mut bad = world(&format!("{id}:equipment"), &active.registry);
        let before = bad.digest();
        let scripts = serde_json::to_value(active.scripts.checkpoints()).unwrap();
        let error = bad
            .step(
                Input {
                    fire: true,
                    ..Input::default()
                },
                &active.registry,
                &mut active.scripts,
            )
            .unwrap_err();
        assert!(error.to_string().contains("target"));
        assert_eq!(before, bad.digest());
        assert_eq!(
            scripts,
            serde_json::to_value(active.scripts.checkpoints()).unwrap()
        );
    }
}

#[test]
fn cadence_is_explicit_and_equipment_is_reusable() {
    for (id, cooldown, shots) in [(PACKAGES[0], 22, 4), (PACKAGES[1], 48, 2)] {
        let (_root, mut active) = activate(&[id]);
        let mut world = world(&format!("{id}:equipment"), &active.registry);
        for _ in 0..70 {
            step(&mut world, &mut active, true);
        }
        assert_eq!(
            active.registry.weapons[&format!("{id}:projectile").as_str().into()].cooldown,
            cooldown
        );
        assert_eq!(
            active.scripts.states[&format!("{id}/scripts/weapon.rhai")]["shots"],
            shots
        );
        assert_eq!(
            world.player.inventory[&format!("{id}:equipment").as_str().into()],
            1
        );
        assert_eq!(world.player.shield, 100);
    }
}

#[test]
fn lethal_primary_contacts_still_trigger_finite_secondary_damage() {
    for id in PACKAGES {
        let (_root, mut active) = activate(&[id]);
        let mut world = world(&format!("{id}:equipment"), &active.registry);
        let targets = if id == PACKAGES[0] {
            vec![
                ("ground", 144, 104),
                ("air", 144, 64),
                ("ground", 144, 24),
                ("air", 220, 64),
            ]
        } else {
            vec![
                ("ground", 144, 96),
                ("ground", 154, 96),
                ("air", 144, 96),
                ("ground", 220, 96),
            ]
        };
        let entities = spawn(&mut world, &active, &targets);
        world.enemies[0].health = 1;
        step(&mut world, &mut active, true);
        for _ in 0..15 {
            step(&mut world, &mut active, false);
        }
        assert!(
            !world.enemies.iter().any(|e| e.entity == entities[0]),
            "lethal primary retires normally"
        );
        assert_eq!(
            world
                .enemies
                .iter()
                .find(|e| e.entity == entities[1])
                .unwrap()
                .health,
            HEALTH - if id == PACKAGES[0] { 32 } else { 36 }
        );
        assert_eq!(
            world
                .enemies
                .iter()
                .find(|e| e.entity == *entities.last().unwrap())
                .unwrap()
                .health,
            HEALTH
        );
    }
}

#[test]
fn full_inventory_rejects_purchase_without_changing_owned_equipment() {
    let (_root, active) = activate(&PACKAGES);
    for id in PACKAGES {
        let mut pilot = Pilot {
            credits: 2_000_000,
            inventory: (0..20)
                .map(|n| (ContentId::new(format!("unavailable:slot{n}")).unwrap(), 1))
                .collect(),
            ..Pilot::default()
        };
        let before = serde_json::to_value(&pilot).unwrap();
        assert!(
            pilot
                .buy(&format!("{id}:equipment").as_str().into(), &active.registry)
                .is_err()
        );
        assert_eq!(before, serde_json::to_value(&pilot).unwrap());
    }
}

#[test]
fn disabling_and_reenabling_keeps_saved_equipment_mod_pins_and_script_state() {
    let (_root, mut active) = activate(&PACKAGES);
    let mut flight = world("iron_coast_railburst:equipment", &active.registry);
    step(&mut flight, &mut active, true);
    let pilot = Pilot {
        mission: "stage2range:range".into(),
        inventory: [
            ("iron_coast_railburst:equipment".into(), 1),
            ("iron_coast_depth_charge:equipment".into(), 1),
            ("base:energy".into(), 100),
        ]
        .into_iter()
        .collect(),
        selected: Some("iron_coast_railburst:equipment".into()),
        mods: active.pins.clone(),
        script_state: active.scripts.states.clone(),
        script_rng: active.scripts.rng.clone(),
        ..Pilot::default()
    };
    let save = tempfile::tempdir().unwrap();
    let path = save.path().join("pilot.json");
    pilot.save(&path).unwrap();
    let original = fs::read(&path).unwrap();
    let (_disabled, disabled) = activate(&[]);
    let missing = Pilot::inspect_load(&path, &disabled.registry, &disabled.pins).unwrap();
    assert!(!missing.compatibility.is_compatible());
    assert_eq!(
        serde_json::to_value(&missing.pilot).unwrap(),
        serde_json::to_value(&pilot).unwrap()
    );
    assert_eq!(
        original,
        fs::read(&path).unwrap(),
        "read-only compatibility inspection must preserve the original save"
    );
    let (_restored, reenabled) = activate(&PACKAGES);
    let compatible = Pilot::inspect_load(&path, &reenabled.registry, &reenabled.pins).unwrap();
    assert!(
        compatible.compatibility.is_compatible(),
        "{:?}",
        compatible.compatibility.messages()
    );
    assert_eq!(compatible.pilot.inventory, pilot.inventory);
    assert_eq!(compatible.pilot.script_state, pilot.script_state);
    assert_eq!(
        serde_json::to_value(compatible.pilot.script_rng).unwrap(),
        serde_json::to_value(pilot.script_rng).unwrap()
    );
}

#[test]
#[ignore = "requires installed original catalog and completed PNG/WAV mod packages"]
fn real_catalog_700_tick_balance_and_coexistence_report() {
    let package = Path::new(env!("CARGO_MANIFEST_DIR"));
    let catalog = Catalog::open(
        std::env::var_os("RAPTOR_TEST_DATA")
            .map(std::path::PathBuf::from)
            .unwrap_or_else(|| package.join("data")),
    )
    .unwrap();
    let base = Registry::base(&catalog).unwrap();
    let enabled = [PACKAGES[0], PACKAGES[1], "ion_lance", "lightning_cannon"].map(String::from);
    // Freeze only the packages under observation, so unrelated authors can work
    // while this slow original-data integration test scans and builds packages.
    fn copy_tree(from: &Path, to: &Path) {
        fs::create_dir_all(to).unwrap();
        for entry in fs::read_dir(from).unwrap() {
            let entry = entry.unwrap();
            if entry.file_type().unwrap().is_dir() {
                copy_tree(&entry.path(), &to.join(entry.file_name()));
            } else {
                fs::copy(entry.path(), to.join(entry.file_name())).unwrap();
            }
        }
    }
    let frozen = tempfile::tempdir().unwrap();
    for id in &enabled {
        copy_tree(&package.join("mods").join(id), &frozen.path().join(id));
    }
    let discovery = modding::discover(frozen.path());
    let mut active = ActiveMods::build(&base, &discovery, &enabled, Some(&catalog)).unwrap();
    range(&mut active.registry);
    attach_range_script(&mut active);
    let scenes: Vec<(&str, Vec<(&str, i32, i32)>)> = vec![
        ("aligned_air", vec![("air", 144, 80)]),
        ("aligned_ground", vec![("ground", 144, 80)]),
        ("off_axis_air", vec![("air", 220, 80)]),
        ("off_axis_ground", vec![("ground", 220, 80)]),
        (
            "aligned_column",
            vec![
                ("ground", 144, 104),
                ("air", 144, 64),
                ("ground", 144, 24),
                ("air", 144, 0),
            ],
        ),
        (
            "ground_cluster",
            vec![
                ("ground", 144, 80),
                ("ground", 154, 80),
                ("ground", 169, 80),
                ("ground", 179, 80),
                ("ground", 181, 80),
                ("air", 144, 80),
            ],
        ),
    ];
    let mut rows = Vec::new();
    for item in [
        "iron_coast_railburst:equipment",
        "iron_coast_depth_charge:equipment",
        "ion_lance:equipment",
        "lightning_cannon:equipment",
        "base:forward_guns",
        "base:death_ray",
        "base:forward_laser",
    ] {
        for combo in [false, true] {
            if combo && item.starts_with("base:") {
                continue;
            }
            for (scene, targets) in &scenes {
                active
                    .scripts
                    .restore((Default::default(), Default::default()));
                let mut world = world(item, &active.registry);
                world.player.selected = active.registry.items[&ContentId::from(item)]
                    .special
                    .then(|| item.into());
                if combo {
                    world.player.inventory.insert("base:forward_guns".into(), 1);
                }
                let entities = spawn(&mut world, &active, targets);
                for _ in 0..700 {
                    step(&mut world, &mut active, true);
                }
                assert_eq!(world.outcome, Outcome::Playing);
                assert_eq!(world.player.shield, 100);
                let damage = damage(&world, &entities);
                rows.push(json!({"item":item,"price":active.registry.items[&ContentId::from(item)].price,"scene":scene,"with_forward_guns":combo,"ticks":700,"seconds":30,"damage":damage,"group_dps":damage.iter().sum::<i32>() as f64/30.0}));
            }
        }
    }
    let report = json!({"fixture_health":HEALTH,"target_size":[32,32],"difficulty":2,"rate":"70/3 Hz","rows":rows});
    if let Some(path) = std::env::var_os("IRON_COAST_STAGE2_BALANCE_REPORT") {
        fs::write(path, serde_json::to_vec_pretty(&report).unwrap()).unwrap();
    }
    println!("{report}");
}
