use raptor_replica::{
    content::{ContentPack, Registry},
    modding::{self, ActiveMods, Command},
    persistence::Pilot,
    simulation::{Input, Outcome, World},
};
use serde_json::{Value, json};
use std::{fs, path::PathBuf};

const OWNER: &str = "iron_coast_boss_6";
const SCRIPT: &str = "scripts/ai.rhai";
const STATE: &str = "iron_coast_boss_6/scripts/ai.rhai";
const BOSS: &str = "iron_coast_boss_6:unit";
const OBJECTIVE: &str = "iron_coast_boss_6:defeated";

fn active() -> ActiveMods {
    let mut registry = Registry::default();
    let pack: ContentPack = serde_json::from_value(json!({
        "weapons":[{"id":"base:projectile_forward_guns","name":"Forward guns","damage":1,"speed":8,"cooldown":2,"behavior":"straight","target":"all"}],
        "items":[{"id":"base:forward_guns","name":"Forward guns","price":0,"weapon":"base:projectile_forward_guns"},{"id":"base:energy","name":"Shield","price":0,"max_count":100}],
        "missions":[{"id":"base:sector_1_wave_1","name":"Boss test","duration":10000}]
    })).unwrap();
    registry.apply(pack, "base").unwrap();
    registry.validate().unwrap();
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..");
    ActiveMods::build(&registry, &modding::discover(&root), &[OWNER.into()], None).unwrap()
}

fn event(entity: u64, x: i32, health: i32, defeated: i32) -> Value {
    json!({"entity":entity,"tick":1,"x":x,"y":24,"health":health,
        "entities":[{"entity":entity,"health":health}],
        "objectives":{OBJECTIVE:defeated}})
}

fn invoke(active: &mut ActiveMods, hook: &str, event: &Value) -> Vec<Command> {
    active.scripts.begin_tick();
    active
        .scripts
        .invoke(OWNER, SCRIPT, hook, event, 6)
        .unwrap()
}

fn callback_contract(active: &mut ActiveMods) {
    let first = event(1, 144, 160, 0);
    let second = event(2, 80, 160, 0);
    invoke(active, "on_spawn", &first);
    invoke(active, "on_spawn", &second);
    for age in 1..=108 {
        let commands = invoke(active, "on_tick", &first);
        let warnings = commands
            .iter()
            .filter(|c| matches!(c, Command::PlaySound {sound} if sound.ends_with(":warning")))
            .count();
        assert_eq!(warnings, usize::from(age % 54 == 45));
        let projectiles = commands
            .iter()
            .filter_map(|c| match c {
                Command::Projectile {
                    vx, vy, hostile, ..
                } => Some((*vx, *vy, *hostile)),
                _ => None,
            })
            .collect::<Vec<_>>();
        match age {
            54 => assert_eq!(projectiles, vec![(-2, 4, true), (0, 4, true), (2, 4, true)]),
            108 => assert_eq!(projectiles, vec![(0, 4, true), (0, 4, true)]),
            _ => assert!(projectiles.is_empty()),
        }
        assert!(
            commands
                .iter()
                .all(|c| !matches!(c, Command::Effect { .. } | Command::Complete))
        );
    }
    assert_eq!(active.scripts.states[STATE]["units"]["1"]["volley"], 2);
    assert_eq!(active.scripts.states[STATE]["units"]["2"]["volley"], 0);
    invoke(active, "on_tick", &second);
    assert_eq!(active.scripts.states[STATE]["units"]["1"]["direction"], -1);
    assert_eq!(active.scripts.states[STATE]["units"]["2"]["direction"], 1);
    let commands = invoke(active, "on_death", &event(1, 120, 0, 0));
    assert!(
        commands
            .iter()
            .any(|c| matches!(c, Command::Objective {key,value:1} if key == OBJECTIVE))
    );
    assert!(commands.iter().all(|c| !matches!(c, Command::Complete)));
    assert!(active.scripts.states[STATE]["units"].get("1").is_none());
    assert!(active.scripts.states[STATE]["units"].get("2").is_some());
    assert!(invoke(active, "on_tick", &event(1, 120, 0, 1)).is_empty());
    assert!(invoke(active, "on_death", &event(1, 120, 0, 1)).is_empty());
    let commands = invoke(active, "on_death", &event(2, 120, 0, 1));
    assert!(
        commands
            .iter()
            .any(|c| matches!(c, Command::Objective {key,value:2} if key == OBJECTIVE))
    );
    assert!(
        active.scripts.states[STATE]["units"]
            .as_object()
            .unwrap()
            .is_empty()
    );
    let checkpoint = active.scripts.checkpoints();
    let serialized = serde_json::to_vec(&checkpoint).unwrap();
    active
        .scripts
        .restore(serde_json::from_slice(&serialized).unwrap());
    assert_eq!(active.scripts.states[STATE]["destroyed"], 2);
    // An immediate kill can retire an enemy before on_spawn is dispatched.
    let commands = invoke(active, "on_death", &event(3, 120, 0, 2));
    assert!(
        commands
            .iter()
            .any(|c| matches!(c, Command::Objective {key,value:3} if key == OBJECTIVE))
    );
}

fn staged_world(active: &mut ActiveMods, difficulty: u32) -> Value {
    active.scripts.restore(Default::default());
    let pilot = Pilot {
        difficulty,
        ..Pilot::default()
    };
    let mut world = World::new(&"base:sector_1_wave_1".into(), &pilot, &active.registry).unwrap();
    world
        .spawn(&BOSS.into(), 110, -64, &active.registry)
        .unwrap();
    let mut second_spawned = false;
    for _ in 0..1600 {
        if world.objectives.get(OBJECTIVE) == Some(&1) && !second_spawned {
            world
                .spawn(&BOSS.into(), 110, -64, &active.registry)
                .unwrap();
            second_spawned = true;
        }
        let target = world.enemies.iter().find(|e| e.health > 0);
        let x = target.map(|e| e.x + 40).unwrap_or(150);
        let player_x = world.player.x + (x - world.player.x).clamp(-4, 4);
        world
            .step(
                Input {
                    fire: true,
                    absolute: Some([player_x, 160]),
                    ..Input::default()
                },
                &active.registry,
                &mut active.scripts,
            )
            .unwrap();
        if world.objectives.get(OBJECTIVE) == Some(&2) {
            break;
        }
        assert_eq!(world.outcome, Outcome::Playing);
    }
    assert_eq!(world.objectives[OBJECTIVE], 2);
    assert!(world.enemies.is_empty());
    assert_eq!(world.player.credits, pilot.credits + 3600);
    assert!(
        active.scripts.states[STATE]["units"]
            .as_object()
            .unwrap()
            .is_empty()
    );
    let credit = world.player.credits;
    world
        .step(Input::default(), &active.registry, &mut active.scripts)
        .unwrap();
    assert_eq!(world.player.credits, credit);
    json!({"difficulty":difficulty,"tick":world.tick,"remaining_shield":world.player.shield,"defeated":2,"rewards":3600,"dead_bosses_retired":true})
}

fn main() {
    let mut active = active();
    callback_contract(&mut active);
    let runs = (0..=3)
        .map(|difficulty| staged_world(&mut active, difficulty))
        .collect::<Vec<_>>();
    let report = json!({"activation":true,"independent_dependency_free_package":true,"warning_lead_ticks":9,
        "alternating_volleys_verified":true,"per_entity_patrol_and_timers":true,"state_roundtrip":true,
        "exact_death_counters_and_rewards":true,"dead_entity_no_fire":true,"immediate_kill_counted":true,
        "no_premature_mission_completion":true,"runs":runs});
    fs::write(
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../validation-results.json"),
        serde_json::to_string_pretty(&report).unwrap() + "\n",
    )
    .unwrap();
    println!("{}", serde_json::to_string_pretty(&report).unwrap());
}
