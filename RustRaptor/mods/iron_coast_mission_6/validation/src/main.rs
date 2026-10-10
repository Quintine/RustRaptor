use raptor_replica::{
    assets::Catalog,
    content::{ContentPack, Registry},
    modding::{self, ActiveMods},
    persistence::Pilot,
    simulation::{Input, Outcome, World},
};
use serde_json::{Value, json};
use std::{fs, path::PathBuf};

const MISSION: &str = "iron_coast_mission_6:mission_06";
const MODS: [&str; 8] = [
    "iron_coast_scout",
    "iron_coast_turret",
    "iron_coast_boss_6",
    "iron_coast_music",
    "pulse_cannon",
    "seeker_swarm",
    "ion_lance",
    "iron_coast_mission_6",
];

fn base(catalog: &Catalog) -> Registry {
    let mut registry = Registry::base(catalog).unwrap();
    let mut value = json!({"items":[]});
    for n in 0..20 {
        value["items"].as_array_mut().unwrap().push(json!({"id":format!("fixture:filler_{n}"),"name":"Neutral saved equipment","price":0,"max_count":1}));
    }
    let pack: ContentPack = serde_json::from_value(value).unwrap();
    registry.apply(pack, "fixture").unwrap();
    registry.validate().unwrap();
    registry
}

fn active() -> ActiveMods {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..");
    let discovery = modding::discover(&root);
    let enabled = MODS.iter().map(|id| id.to_string()).collect::<Vec<_>>();
    let data = std::env::var_os("RAPTOR_TEST_DATA")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../../../data"));
    let catalog = Catalog::open(data).unwrap();
    ActiveMods::build(&base(&catalog), &discovery, &enabled, Some(&catalog)).unwrap()
}

fn play(active: &mut ActiveMods, shield: u32, credits: u32, difficulty: u32, full: bool) -> Value {
    active.scripts.restore(Default::default());
    let mut pilot = Pilot {
        credits,
        difficulty,
        ..Pilot::default()
    };
    pilot.inventory.insert("base:energy".into(), shield);
    if full {
        let mut filler = 0;
        while pilot.inventory_slots() < 20 {
            pilot
                .inventory
                .insert(format!("fixture:filler_{filler}").as_str().into(), 1);
            filler += 1;
        }
    }
    let original = pilot.inventory.clone();
    let mut world = World::new(&MISSION.into(), &pilot, &active.registry).unwrap();
    let mut maximum_enemies = 0;
    for _ in 0..5000 {
        // A controlled mouse-like run: bounded lateral movement, always firing,
        // aim first at the enemy closest to the player, keep the bottom lane.
        let desired_x = world
            .enemies
            .iter()
            .filter(|enemy| enemy.health > 0 && enemy.y >= 0)
            .max_by_key(|enemy| enemy.y)
            .map(|enemy| enemy.x + enemy.width / 2 - 16)
            .unwrap_or(144);
        let x = world.player.x + (desired_x - world.player.x).clamp(-4, 4);
        let input = Input {
            fire: true,
            cycle: world.tick == 1,
            absolute: Some([x, 160]),
            ..Input::default()
        };
        world
            .step(input, &active.registry, &mut active.scripts)
            .unwrap();
        maximum_enemies = maximum_enemies.max(world.enemies.len());
        if world.outcome != Outcome::Playing {
            break;
        }
    }
    assert_eq!(
        world.outcome,
        Outcome::Complete,
        "tick={} shield={} turrets={:?} bosses={:?}",
        world.tick,
        world.player.shield,
        world.objectives.get("iron_coast_turret:defeated"),
        world.objectives.get("iron_coast_boss_6:defeated")
    );
    assert_eq!(world.objectives["iron_coast_turret:defeated"], 6);
    assert_eq!(world.objectives["iron_coast_boss_6:defeated"], 2);
    assert_eq!(world.objectives["iron_coast_mission_6:complete"], 1);
    assert!(
        !world
            .player
            .inventory
            .contains_key(&"ion_lance:equipment".into())
    );
    if full {
        for (id, count) in &original {
            if id.0 != "base:energy" {
                assert_eq!(world.player.inventory.get(id), Some(count));
            }
        }
        assert_eq!(world.player.inventory.len(), 20);
    }
    let final_credits = world.player.credits;
    world
        .step(Input::default(), &active.registry, &mut active.scripts)
        .unwrap();
    assert_eq!(world.player.credits, final_credits);
    println!(
        "Controlled run complete: difficulty={difficulty} starting_shield={shield} tick={} ending_shield={}",
        world.tick, world.player.shield
    );
    json!({"full_inventory_no_loan":full,"starting_shield":shield,"starting_credits":credits,"difficulty":difficulty,
           "outcome":"complete","tick":world.tick,"seconds":world.tick as f64 * 3.0 / 70.0,
           "ending_shield":world.player.shield,"ending_credits":world.player.credits,
           "maximum_enemies":maximum_enemies,"turrets_defeated":6,"cruisers_defeated":2,
           "loan_returned":true,"reward_paid_once":true})
}

fn full_inventory(active: &mut ActiveMods) {
    for reserves in [0, 4] {
        active.scripts.restore(Default::default());
        let mut pilot = Pilot::default();
        if reserves > 0 {
            pilot.inventory.insert("base:super_shield".into(), 100);
            pilot.super_shield_reserves = vec![100; reserves];
        }
        let mut filler = 0;
        while pilot.inventory_slots() < 20 {
            pilot
                .inventory
                .insert(format!("fixture:filler_{filler}").as_str().into(), 1);
            filler += 1;
        }
        let mut world = World::new(&MISSION.into(), &pilot, &active.registry).unwrap();
        world
            .step(Input::default(), &active.registry, &mut active.scripts)
            .unwrap();
        assert_eq!(world.player.inventory, pilot.inventory);
        assert_eq!(
            world.player.super_shield_reserves,
            pilot.super_shield_reserves
        );
        assert!(
            !active.scripts.states["iron_coast_mission_6/scripts/mission.rhai"]["loaned"]
                .as_bool()
                .unwrap()
        );
    }
}

fn mandatory_batteries_stay_reachable(active: &mut ActiveMods) {
    active.scripts.restore(Default::default());
    let pilot = Pilot {
        inventory: [
            ("base:energy".into(), 100),
            ("base:super_shield".into(), 100),
        ]
        .into(),
        super_shield_reserves: vec![100; 4],
        ..Pilot::default()
    };
    let mut world = World::new(&MISSION.into(), &pilot, &active.registry).unwrap();
    let mut positions = std::collections::BTreeMap::new();
    let mut moving = std::collections::BTreeSet::new();
    for _ in 0..1400 {
        world
            .step(
                Input {
                    absolute: Some([280, 160]),
                    ..Input::default()
                },
                &active.registry,
                &mut active.scripts,
            )
            .unwrap();
        for enemy in &world.enemies {
            if enemy.definition.0.starts_with("base:enemy_") {
                assert!(active.registry.enemies[&enemy.definition].legacy.is_some());
                let key = (enemy.definition.0.clone(), enemy.entity);
                if let Some(previous) = positions.insert(key.clone(), (enemy.x, enemy.y)) {
                    if previous != (enemy.x, enemy.y) {
                        moving.insert(enemy.definition.0.clone());
                    }
                }
            }
        }
        if world.outcome != Outcome::Playing {
            break;
        }
    }
    assert!(
        moving.len() >= 4,
        "Native loop/sweep movement must remain visible: {moving:?}"
    );
    assert_eq!(world.outcome, Outcome::Playing);
    let turrets = world
        .enemies
        .iter()
        .filter(|enemy| enemy.definition.0 == "iron_coast_turret:unit")
        .collect::<Vec<_>>();
    assert_eq!(turrets.len(), 6);
    assert!(
        turrets
            .iter()
            .all(|enemy| enemy.y <= 80 && enemy.health > 0)
    );
}

fn state_resets_and_owned_lance_survives(active: &mut ActiveMods) {
    active.scripts.restore(Default::default());
    for _ in 0..2 {
        let mut pilot = Pilot::default();
        pilot.inventory.insert("ion_lance:equipment".into(), 1);
        let mut world = World::new(&MISSION.into(), &pilot, &active.registry).unwrap();
        world
            .step(Input::default(), &active.registry, &mut active.scripts)
            .unwrap();
        assert_eq!(world.objectives["iron_coast_turret:defeated"], 0);
        assert_eq!(world.objectives["iron_coast_boss_6:defeated"], 0);
        world.tick = 2350;
        world
            .objectives
            .insert("iron_coast_turret:defeated".into(), 6);
        world
            .objectives
            .insert("iron_coast_boss_6:defeated".into(), 2);
        world
            .step(Input::default(), &active.registry, &mut active.scripts)
            .unwrap();
        assert_eq!(world.outcome, Outcome::Complete);
        assert_eq!(world.player.inventory[&"ion_lance:equipment".into()], 1);
        assert!(
            !active.scripts.states["iron_coast_mission_6/scripts/mission.rhai"]["loaned"]
                .as_bool()
                .unwrap()
        );
    }
}

fn failure_returns_loan(active: &mut ActiveMods) {
    for owned in [false, true] {
        active.scripts.restore(Default::default());
        let mut pilot = Pilot::default();
        if owned {
            pilot.inventory.insert("ion_lance:equipment".into(), 1);
        }
        let mut world = World::new(&MISSION.into(), &pilot, &active.registry).unwrap();
        world
            .step(Input::default(), &active.registry, &mut active.scripts)
            .unwrap();
        world
            .apply_commands(
                &[modding::Command::Damage {
                    entity: 0,
                    amount: 100000,
                }],
                &active.registry,
            )
            .unwrap();
        world
            .step(Input::default(), &active.registry, &mut active.scripts)
            .unwrap();
        assert_eq!(world.outcome, Outcome::Failed);
        assert_eq!(world.objectives["iron_coast_mission_6:debrief"], 0);
        assert_eq!(
            world
                .player
                .inventory
                .contains_key(&"ion_lance:equipment".into()),
            owned
        );
    }
}

fn main() {
    let mut active = active();
    failure_returns_loan(&mut active);
    println!("Failed sorties return only the loan and preserve owned Ion Lance");
    full_inventory(&mut active);
    println!("Full 20-slot inventory and physical shield module preservation passed");
    mandatory_batteries_stay_reachable(&mut active);
    println!("All six mandatory batteries remain reachable after scrolling passed");
    state_resets_and_owned_lance_survives(&mut active);
    println!("Restart reset and owned Ion Lance preservation passed");
    let runs = [(75, 10_000), (100, 0)]
        .into_iter()
        .flat_map(|(shield, credits)| (0..=3).map(move |difficulty| (shield, credits, difficulty)))
        .map(|(shield, credits, difficulty)| play(&mut active, shield, credits, difficulty, false))
        .collect::<Vec<_>>();
    let full_run = play(&mut active, 75, 10_000, 2, true);
    let report = json!({"fixture":"Actual original catalog/native enemies, shipped mod PNG/WAV files and production deterministic simulation; neutral fixture items fill the no-loan inventory",
        "run_count":runs.len()+1,"runs":runs,"full_inventory_run":full_run,"full_inventory_and_shield_reserves":true,"mandatory_batteries_remain_reachable":true,"classic_native_movement_observed":true,"restart_state_reset":true,"owned_weapon_preserved":true,"failure_loan_cleanup":true});
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../validation-results.json");
    fs::write(path, serde_json::to_string_pretty(&report).unwrap() + "\n").unwrap();
    println!("{}", serde_json::to_string_pretty(&report).unwrap());
}
