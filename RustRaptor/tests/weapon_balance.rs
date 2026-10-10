//! Local balance observations against original weapons in the real registry.
//! Targets are fixtures; no original artwork or data is required by CI.
use raptor_replica::{
    assets::Catalog,
    content::{ContentId, ContentPack, Registry},
    modding::{self, ActiveMods},
    persistence::Pilot,
    simulation::{Input, Outcome, World},
};
use serde_json::{Value, json};
use std::{fs, path::Path};

const COMBAT_MODS: [&str; 6] = [
    "pulse_cannon",
    "seeker_swarm",
    "ion_lance",
    "iron_coast_scout",
    "iron_coast_turret",
    "iron_coast_boss",
];
const TICKS: usize = 700;
const HEALTH: i32 = 1_000_000;
const WEAPONS: [&str; 15] = [
    "base:forward_guns",
    "base:plasma_guns",
    "base:micro_missile",
    "base:air_missile",
    "base:grd_missile",
    "base:dumb_missile",
    "base:mini_gun",
    "base:missile_pods",
    "base:turret",
    "base:pulse_cannon",
    "base:death_ray",
    "base:forward_laser",
    "pulse_cannon:equipment",
    "seeker_swarm:equipment",
    "ion_lance:equipment",
];
fn fixture(active: &mut ActiveMods) {
    let pack: ContentPack = serde_json::from_value(json!({
        "missions":[{"id":"balance:range","name":"Weapon range","duration":10000,"auto_complete":false}],
        "enemies":[
            {"id":"balance:air","name":"Air target","health":HEALTH,"speed":0},
            {"id":"balance:ground","name":"Ground target","health":HEALTH,"speed":0,"ground":true,"script":"ground.rhai"}
        ]
    })).unwrap();
    active.registry.apply(pack, "balance").unwrap();
    active
        .scripts
        .add(
            "balance",
            "ground.rhai",
            r#"
        // Ground actors normally scroll one logical pixel each tick. Reset
        // this range target after collision processing; weapons are unmodified.
        fn on_tick(event,state,random) {
            #{commands:[#{op:"move",entity:event.entity,x:event.x,y:event.y-1}],state:state}
        }
    "#,
        )
        .unwrap();
}
fn observe(
    active: &mut ActiveMods,
    item: &str,
    scene: &str,
    targets: &[(&str, i32, i32)],
    with_forward_guns: bool,
) -> Value {
    active
        .scripts
        .restore((Default::default(), Default::default()));
    let id = ContentId::from(item);
    let mut inventory = [(id.clone(), 1), ("base:energy".into(), 100)]
        .into_iter()
        .collect::<std::collections::BTreeMap<_, _>>();
    if with_forward_guns {
        inventory.insert("base:forward_guns".into(), 1);
    }
    let pilot = Pilot {
        mission: "balance:range".into(),
        difficulty: 2,
        inventory,
        selected: active.registry.items[&id].special.then_some(id.clone()),
        ..Pilot::default()
    };
    let mut world = World::new(&pilot.mission, &pilot, &active.registry).unwrap();
    let entities: Vec<_> = targets
        .iter()
        .map(|(kind, x, y)| {
            world
                .spawn(
                    &format!("balance:{kind}").as_str().into(),
                    *x,
                    *y,
                    &active.registry,
                )
                .unwrap()
        })
        .collect();
    for _ in 0..TICKS {
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
    assert_eq!(world.outcome, Outcome::Playing);
    assert_eq!(
        world.player.shield, 100,
        "range targets should not harm the pilot"
    );
    let damage: Vec<_> = entities
        .iter()
        .map(|entity| {
            let target = world
                .enemies
                .iter()
                .find(|e| e.entity == *entity)
                .expect("range target retired");
            assert!(target.health > 0);
            assert_eq!(
                target.y,
                targets[entities.iter().position(|e| e == entity).unwrap()].2
            );
            HEALTH - target.health
        })
        .collect();
    json!({"item":item,"scene":scene,"price":active.registry.items[&id].price,
        "ticks":TICKS,"seconds":TICKS as f64 * 3.0/70.0,"with_forward_guns":with_forward_guns,
        "damage":damage,"damage_per_second":damage.iter().map(|d| *d as f64/(TICKS as f64*3.0/70.0)).collect::<Vec<_>>()})
}

#[test]
#[ignore = "requires original untracked catalog; reports controlled stationary-target balance, not campaign difficulty"]
fn original_and_mod_weapons_report_controlled_damage_locally() {
    let package = Path::new(env!("CARGO_MANIFEST_DIR"));
    let root = std::env::var_os("RAPTOR_TEST_DATA")
        .map(std::path::PathBuf::from)
        .unwrap_or_else(|| package.join("../data"));
    let catalog = Catalog::open(root).unwrap();
    let base = Registry::base(&catalog).unwrap();
    let discovery = modding::discover(&package.join("mods"));
    let enabled = COMBAT_MODS.map(String::from);
    let mut active = ActiveMods::build(&base, &discovery, &enabled, Some(&catalog)).unwrap();
    fixture(&mut active);
    let mut rows = Vec::new();
    for item in WEAPONS {
        for (scene, targets) in [
            ("aligned_air", vec![("air", 144, 80)]),
            ("aligned_ground", vec![("ground", 144, 80)]),
            ("off_axis_air", vec![("air", 220, 80)]),
            ("off_axis_ground", vec![("ground", 220, 80)]),
            ("column", vec![("air", 144, 96), ("ground", 144, 40)]),
            (
                "cluster",
                vec![("air", 144, 80), ("ground", 144, 80), ("air", 154, 80)],
            ),
        ] {
            let result = observe(&mut active, item, scene, &targets, false);
            println!("{result}");
            rows.push(result);
        }
    }
    for item in [
        "base:plasma_guns",
        "base:micro_missile",
        "pulse_cannon:equipment",
    ] {
        rows.push(observe(
            &mut active,
            item,
            "aligned_air",
            &[("air", 144, 80)],
            true,
        ));
        rows.push(observe(
            &mut active,
            item,
            "aligned_ground",
            &[("ground", 144, 80)],
            true,
        ));
    }
    let report = json!({"difficulty":2,"rate":"70/3 Hz","target_size":[32,32],
        "target_health":HEALTH,"fire_steps":TICKS,"rows":rows});
    if let Some(path) = std::env::var_os("RAPTOR_BALANCE_REPORT") {
        fs::write(path, serde_json::to_vec_pretty(&report).unwrap()).unwrap();
    }
    let row = |item: &str, scene: &str| {
        report["rows"]
            .as_array()
            .unwrap()
            .iter()
            .find(|r| r["item"] == item && r["scene"] == scene && r["with_forward_guns"] == false)
            .unwrap()
    };
    assert!(
        row("seeker_swarm:equipment", "off_axis_air")["damage"][0]
            .as_i64()
            .unwrap()
            > 0
    );
    assert!(
        row("seeker_swarm:equipment", "off_axis_ground")["damage"][0]
            .as_i64()
            .unwrap()
            > 0
    );
    let column = row("ion_lance:equipment", "column")["damage"]
        .as_array()
        .unwrap();
    assert!(column.iter().all(|d| d.as_i64().unwrap() > 0));
    assert_eq!(
        column[0], column[1],
        "ion beam should damage both column targets equally"
    );
    assert_eq!(row("ion_lance:equipment", "off_axis_air")["damage"][0], 0);
}
