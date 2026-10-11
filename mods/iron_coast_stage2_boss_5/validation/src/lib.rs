//! Independent portable behavior checks for the two complete encounters.
#[cfg(test)]
mod tests {
    use raptor_replica::{
        content::{ContentPack, Registry},
        modding::{self, ActiveMods, Command, ScriptRuntime},
        persistence::Pilot,
        simulation::{Input, Outcome, World},
    };
    use serde_json::{Value, json};
    use std::path::PathBuf;

    fn mods() -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..")
    }
    fn owner(number: u32, kind: &str) -> String {
        format!("iron_coast_stage2_{kind}_{number}")
    }
    fn runtime(number: u32, kind: &str, script: &str) -> ScriptRuntime {
        let mut runtime = ScriptRuntime::new();
        let package = owner(number, kind);
        let source = std::fs::read_to_string(mods().join(&package).join(script)).unwrap();
        runtime.add(&package, script, &source).unwrap();
        runtime
    }
    fn invoke(
        runtime: &mut ScriptRuntime,
        number: u32,
        kind: &str,
        script: &str,
        hook: &str,
        event: &Value,
    ) -> Vec<Command> {
        runtime.begin_tick();
        runtime
            .invoke(&owner(number, kind), script, hook, event, 1024)
            .unwrap()
    }
    fn event(number: u32, entity: u64, tick: u64) -> Value {
        let health = if number == 5 { 300 } else { 360 };
        json!({"entity":entity,"tick":tick,"x":104,"y":24,"health":health,"player_x":144,"player_y":160,
            "entities":[{"entity":1,"health":health,"definition":format!("{}:unit",owner(number,"boss"))},
                        {"entity":2,"health":health,"definition":format!("{}:unit",owner(number,"boss"))}],"objectives":{}})
    }

    #[test]
    fn both_bosses_have_warned_staggered_attacks_and_no_ghost_commands() {
        for number in [5, 6] {
            let mut scripts = runtime(number, "boss", "scripts/ai.rhai");
            invoke(
                &mut scripts,
                number,
                "boss",
                "scripts/ai.rhai",
                "on_spawn",
                &event(number, 1, 0),
            );
            let mut warnings = vec![];
            let mut shots = vec![];
            for tick in 1..=200 {
                let mut e = event(number, 1, tick);
                e["health"] = json!(50); // Also exercise the aimed low-health cannon.
                let commands = invoke(
                    &mut scripts,
                    number,
                    "boss",
                    "scripts/ai.rhai",
                    "on_tick",
                    &e,
                );
                assert!(commands.len() <= 4);
                for command in commands {
                    match command {
                        Command::PlaySound { sound } if sound.ends_with(":warning") => {
                            warnings.push(tick)
                        }
                        Command::Projectile {
                            hostile, vx, vy, ..
                        } => {
                            assert!(hostile);
                            assert!((-2..=2).contains(&vx));
                            assert!((3..=4).contains(&vy));
                            shots.push(tick);
                        }
                        Command::Complete
                        | Command::Fail
                        | Command::GiveItem { .. }
                        | Command::ConsumeItem { .. } => {
                            panic!("boss must not alter mission outcome or inventory")
                        }
                        _ => {}
                    }
                }
            }
            let (period, warn, left, right, core) = if number == 5 {
                (84, 36, 50, 58, 66)
            } else {
                (96, 44, 60, 72, 84)
            };
            assert_eq!(
                warnings,
                (0..3)
                    .map(|i| i * period + warn)
                    .filter(|t| *t <= 200)
                    .collect::<Vec<_>>()
            );
            assert_eq!(
                shots,
                (0..3)
                    .flat_map(|i| [i * period + left, i * period + right, i * period + core])
                    .filter(|t| *t <= 200)
                    .collect::<Vec<_>>()
            );
            let saved = scripts.checkpoints();
            let mut restored = runtime(number, "boss", "scripts/ai.rhai");
            restored.restore(saved);
            let e = event(number, 1, 201);
            let a = invoke(
                &mut scripts,
                number,
                "boss",
                "scripts/ai.rhai",
                "on_tick",
                &e,
            );
            let b = invoke(
                &mut restored,
                number,
                "boss",
                "scripts/ai.rhai",
                "on_tick",
                &e,
            );
            assert_eq!(
                serde_json::to_value(a).unwrap(),
                serde_json::to_value(b).unwrap()
            );
            assert_eq!(scripts.states, restored.states);
            let before = scripts.states.clone();
            let mut gone = event(number, 1, 202);
            gone["entities"] = json!([]);
            assert!(
                invoke(
                    &mut scripts,
                    number,
                    "boss",
                    "scripts/ai.rhai",
                    "on_tick",
                    &gone
                )
                .is_empty()
            );
            assert_eq!(scripts.states, before);
            let mut dead = event(number, 1, 203);
            dead["health"] = json!(0);
            assert!(
                invoke(
                    &mut scripts,
                    number,
                    "boss",
                    "scripts/ai.rhai",
                    "on_tick",
                    &dead
                )
                .is_empty()
            );
        }
    }

    #[test]
    fn reused_instances_start_with_fresh_clocks_and_simultaneous_ones_are_preserved() {
        for number in [5, 6] {
            let mut scripts = runtime(number, "boss", "scripts/ai.rhai");
            for entity in [1, 2] {
                invoke(
                    &mut scripts,
                    number,
                    "boss",
                    "scripts/ai.rhai",
                    "on_spawn",
                    &event(number, entity, 0),
                );
            }
            for tick in 1..=40 {
                invoke(
                    &mut scripts,
                    number,
                    "boss",
                    "scripts/ai.rhai",
                    "on_tick",
                    &event(number, 1, tick),
                );
            }
            let key = format!("{}/scripts/ai.rhai", owner(number, "boss"));
            assert_eq!(scripts.states[&key]["units"]["1"]["age"], 40);
            assert_eq!(scripts.states[&key]["units"]["2"]["age"], 0);
            let mut restarted = event(number, 1, 0);
            restarted["entities"].as_array_mut().unwrap().truncate(1);
            invoke(
                &mut scripts,
                number,
                "boss",
                "scripts/ai.rhai",
                "on_spawn",
                &restarted,
            );
            assert_eq!(scripts.states[&key]["units"]["1"]["age"], 0);
            assert!(scripts.states[&key]["units"].get("2").is_none());
        }
    }

    #[test]
    fn mission_death_gates_pay_once_reset_every_flag_and_never_mutate_inventory() {
        for number in [5, 6] {
            let mut scripts = runtime(number, "mission", "scripts/mission.rhai");
            let package = owner(number, "mission");
            let mut e = json!({"tick":0,"objectives":{},"success":true});
            let start = invoke(
                &mut scripts,
                number,
                "mission",
                "scripts/mission.rhai",
                "on_mission_start",
                &e,
            );
            for suffix in [
                "targets_destroyed",
                "complete",
                "field_repair",
                "debrief",
                "hazard_lane",
            ] {
                assert!(start.iter().any(|c|matches!(c,Command::Objective{key,value:0} if key==&format!("{package}:{suffix}"))));
            }
            e["tick"] = json!(3501);
            let commands = invoke(
                &mut scripts,
                number,
                "mission",
                "scripts/mission.rhai",
                "on_tick",
                &e,
            );
            assert!(
                !commands.iter().any(|c| matches!(c, Command::Complete)),
                "duration alone cannot complete a mission"
            );
            e["objectives"] = json!({format!("{package}:targets_destroyed"):if number==5 {2}else{3},format!("{}:defeated",owner(number,"boss")):1});
            let reward = invoke(
                &mut scripts,
                number,
                "mission",
                "scripts/mission.rhai",
                "on_tick",
                &e,
            );
            assert_eq!(
                reward
                    .iter()
                    .filter(|c| matches!(c, Command::Complete))
                    .count(),
                1
            );
            assert_eq!(reward.iter().filter(|c|matches!(c,Command::Credits{amount} if *amount==if number==5 {26000}else{32000})).count(),1);
            let second = invoke(
                &mut scripts,
                number,
                "mission",
                "scripts/mission.rhai",
                "on_tick",
                &e,
            );
            assert!(
                !second
                    .iter()
                    .any(|c| matches!(c, Command::Complete | Command::Credits { .. }))
            );
            for c in start.iter().chain(reward.iter()).chain(second.iter()) {
                assert!(!matches!(
                    c,
                    Command::GiveItem { .. } | Command::ConsumeItem { .. }
                ));
            }
            invoke(
                &mut scripts,
                number,
                "mission",
                "scripts/mission.rhai",
                "on_mission_end",
                &e,
            );
            invoke(
                &mut scripts,
                number,
                "mission",
                "scripts/mission.rhai",
                "on_mission_start",
                &e,
            );
            let key = format!("{package}/scripts/mission.rhai");
            assert_eq!(
                scripts.states[&key],
                json!({"complete":false,"repair":false,"boss_warning":false})
            );
        }
    }

    fn base() -> Registry {
        let mut base = Registry::default();
        let pack:ContentPack=serde_json::from_value(json!({
            "weapons":[{"id":"base:test_gun","name":"Fixture gun","damage":1,"speed":8,"cooldown":2,"behavior":"straight","target":"all"}],
            "items":[{"id":"base:forward_guns","name":"Fixture guns","price":0,"max_count":1,"weapon":"base:test_gun"},{"id":"base:energy","name":"Shield","price":10000,"max_count":100}],
            "missions":[{"id":"base:sector_1_wave_1","name":"Persistence fixture","duration":2,"auto_complete":false}]
        })).unwrap();
        base.apply(pack, "base").unwrap();
        base.validate().unwrap();
        base
    }

    #[test]
    fn real_simulation_persists_bosses_then_pays_actual_death_reward_once() {
        let discovery = modding::discover(&mods());
        for number in [5, 6] {
            let package = owner(number, "boss");
            let mut active =
                ActiveMods::build(&base(), &discovery, &[package.clone()], None).unwrap();
            for difficulty in 0..=3 {
                active.scripts.restore(Default::default());
                let pilot = Pilot {
                    difficulty,
                    ..Pilot::default()
                };
                let mut world =
                    World::new(&"base:sector_1_wave_1".into(), &pilot, &active.registry).unwrap();
                world.player.x = 0;
                world
                    .apply_commands(
                        &[Command::Spawn {
                            enemy: format!("{package}:unit"),
                            x: 104,
                            y: -24,
                        }],
                        &active.registry,
                    )
                    .unwrap();
                let maximum = world.enemies[0].health;
                assert_eq!(
                    maximum,
                    if difficulty <= 1 {
                        if number == 5 { 150 } else { 180 }
                    } else {
                        if number == 5 { 300 } else { 360 }
                    }
                );
                let mut warnings = 0;
                let mut shots = 0;
                let mut core_seen = false;
                for _ in 0..300 {
                    world
                        .step(Input::default(), &active.registry, &mut active.scripts)
                        .unwrap();
                    warnings += world
                        .mod_sounds
                        .iter()
                        .filter(|s| s.0.ends_with(":warning"))
                        .count();
                    shots += world
                        .mod_sounds
                        .iter()
                        .filter(|s| s.0.ends_with(":shot"))
                        .count();
                    core_seen |= world
                        .projectiles
                        .iter()
                        .any(|p| p.weapon.0.ends_with(":core"));
                }
                assert!(
                    !core_seen,
                    "difficulty{difficulty}: full-health boss must not begin in its second phase"
                );
                let entity = world.enemies[0].entity;
                world
                    .apply_commands(
                        &[Command::Damage {
                            entity,
                            amount: maximum / 2,
                        }],
                        &active.registry,
                    )
                    .unwrap();
                for _ in 0..300 {
                    world
                        .step(Input::default(), &active.registry, &mut active.scripts)
                        .unwrap();
                    warnings += world
                        .mod_sounds
                        .iter()
                        .filter(|s| s.0.ends_with(":warning"))
                        .count();
                    shots += world
                        .mod_sounds
                        .iter()
                        .filter(|s| s.0.ends_with(":shot"))
                        .count();
                    core_seen |= world
                        .projectiles
                        .iter()
                        .any(|p| p.weapon.0.ends_with(":core"));
                }
                assert!(
                    core_seen,
                    "difficulty{difficulty}: real half-health damage must unlock aimed core cannon"
                );
                assert_eq!(world.outcome, Outcome::Playing);
                assert_eq!(world.enemies.len(), 1);
                assert_eq!(world.enemies[0].y, 24);
                assert!(warnings >= 5 && shots >= 10);
                let entity = world.enemies[0].entity;
                world
                    .apply_commands(
                        &[Command::Damage {
                            entity,
                            amount: if number == 5 { 300 } else { 360 },
                        }],
                        &active.registry,
                    )
                    .unwrap();
                world
                    .step(Input::default(), &active.registry, &mut active.scripts)
                    .unwrap();
                assert!(world.enemies.is_empty());
                assert_eq!(world.objectives[&format!("{package}:defeated")], 1);
                assert_eq!(
                    world.player.credits,
                    pilot.credits + if number == 5 { 6000 } else { 7500 }
                );
                assert!(world.mod_sounds.iter().any(|s| s.0.ends_with(":death")));
                for _ in 0..120 {
                    world
                        .step(Input::default(), &active.registry, &mut active.scripts)
                        .unwrap();
                    assert!(!world.mod_sounds.iter().any(|s| s.0.ends_with(":shot")));
                }
                assert_eq!(world.objectives[&format!("{package}:defeated")], 1);
                assert_eq!(world.outcome, Outcome::Playing);
            }
        }
    }
}
