//! Meaningful callback checks without original assets or desktop services.
#[cfg(test)]
mod tests {
    use raptor_replica::modding::{Command, ScriptRuntime};
    use serde_json::{Value, json};

    const OWNER: &str = "iron_coast_boss_5";
    const SCRIPT: &str = "scripts/ai.rhai";
    const KEY: &str = "iron_coast_boss_5/scripts/ai.rhai";

    fn runtime() -> ScriptRuntime {
        let mut scripts = ScriptRuntime::new();
        scripts
            .add(OWNER, SCRIPT, include_str!("../../scripts/ai.rhai"))
            .unwrap();
        scripts
    }

    fn event(entity: u64, tick: u64) -> Value {
        json!({"entity":entity,"tick":tick,"x":112,"y":24,"health":160,
            "entities":[{"entity":1,"health":160},{"entity":2,"health":160}],
            "objectives":{}})
    }

    fn invoke(scripts: &mut ScriptRuntime, hook: &str, event: &Value) -> Vec<Command> {
        scripts.begin_tick();
        scripts.invoke(OWNER, SCRIPT, hook, event, 1024).unwrap()
    }

    #[test]
    fn warnings_precede_the_staggered_54_tick_attack_cycle() {
        let mut scripts = runtime();
        invoke(&mut scripts, "on_spawn", &event(1, 0));
        let mut warnings = vec![];
        let mut shots = vec![];
        for tick in 1..=120 {
            let commands = invoke(&mut scripts, "on_tick", &event(1, tick));
            for command in commands {
                match command {
                    Command::PlaySound { sound } if sound.ends_with(":warning") => {
                        warnings.push(tick)
                    }
                    Command::Projectile {
                        weapon,
                        vx,
                        vy,
                        hostile,
                        ..
                    } => {
                        assert!(hostile);
                        assert_eq!(vy, 4);
                        shots.push((tick, weapon, vx));
                    }
                    Command::Complete | Command::Fail => {
                        panic!("boss must not decide mission outcome")
                    }
                    _ => {}
                }
            }
        }
        assert_eq!(warnings, [36, 90]);
        assert_eq!(
            shots.iter().map(|x| x.0).collect::<Vec<_>>(),
            [48, 54, 60, 102, 108, 114]
        );
        assert_eq!(
            shots.iter().map(|x| x.2).collect::<Vec<_>>(),
            [-2, 0, 2, -2, 0, 2]
        );
        assert!(shots[1].1.ends_with(":mortar"));
        assert_eq!(scripts.states[KEY]["units"]["1"]["shots"], 6);
    }

    #[test]
    fn simultaneous_enemies_keep_independent_serializable_clocks_and_cleanup() {
        let mut scripts = runtime();
        invoke(&mut scripts, "on_spawn", &event(1, 0));
        invoke(&mut scripts, "on_spawn", &event(2, 0));
        for tick in 1..=70 {
            invoke(&mut scripts, "on_tick", &event(1, tick));
            if tick <= 20 {
                invoke(&mut scripts, "on_tick", &event(2, tick));
            }
        }
        let serialized = serde_json::to_vec(&scripts.states).unwrap();
        let restored: std::collections::BTreeMap<String, Value> =
            serde_json::from_slice(&serialized).unwrap();
        assert_eq!(restored[KEY]["units"]["1"]["age"], 70);
        assert_eq!(restored[KEY]["units"]["2"]["age"], 20);
        let mut death = event(1, 71);
        death["objectives"] = json!({"iron_coast_boss_5:defeated":2});
        let commands = invoke(&mut scripts, "on_death", &death);
        assert!(commands.iter().any(|command| matches!(command,
            Command::Objective { key, value:3 } if key == "iron_coast_boss_5:defeated")));
        assert!(scripts.states[KEY]["units"].get("1").is_none());
        assert_eq!(scripts.states[KEY]["units"]["2"]["age"], 20);
        assert_eq!(scripts.states[KEY]["destroyed"], 1);
        // A new mission may reuse entity IDs; its attack age must begin at zero.
        invoke(&mut scripts, "on_spawn", &event(2, 0));
        assert_eq!(scripts.states[KEY]["units"]["2"]["age"], 0);
    }

    #[test]
    fn removed_or_lethally_hit_enemies_emit_no_ghost_commands() {
        let mut scripts = runtime();
        invoke(&mut scripts, "on_spawn", &event(1, 0));
        let before = scripts.states.clone();
        let mut dead = event(1, 48);
        dead["health"] = json!(0);
        assert!(invoke(&mut scripts, "on_tick", &dead).is_empty());
        dead["health"] = json!(160);
        dead["entities"] = json!([]);
        assert!(invoke(&mut scripts, "on_tick", &dead).is_empty());
        assert!(invoke(&mut scripts, "on_spawn", &dead).is_empty());
        assert_eq!(scripts.states, before);
    }

    #[test]
    fn entrance_and_patrol_turns_preserve_the_y24_band() {
        let mut scripts = runtime();
        let mut e = event(1, 0);
        e["y"] = json!(-24);
        let commands = invoke(&mut scripts, "on_tick", &e);
        assert!(matches!(
            commands[0],
            Command::Velocity {
                entity: 1,
                vx: 0,
                vy: 2
            }
        ));
        e["y"] = json!(24);
        e["x"] = json!(144);
        let commands = invoke(&mut scripts, "on_tick", &e);
        assert!(
            commands
                .iter()
                .any(|c| matches!(c, Command::Velocity { vx: -1, vy: 0, .. }))
        );
        assert!(
            commands
                .iter()
                .any(|c| matches!(c, Command::Move { y: 24, .. }))
        );
        e["x"] = json!(80);
        let commands = invoke(&mut scripts, "on_tick", &e);
        assert!(
            commands
                .iter()
                .any(|c| matches!(c, Command::Velocity { vx: 1, vy: 0, .. }))
        );
    }

    #[test]
    fn real_simulation_keeps_the_boss_alive_until_damage_and_counts_death_once() {
        use raptor_replica::{
            content::{ContentPack, Registry},
            modding::{self, ActiveMods},
            persistence::Pilot,
            simulation::{Input, Outcome, World},
        };
        let pack: ContentPack = serde_json::from_value(json!({
            "weapons":[{"id":"base:test_gun","name":"Fixture gun","damage":1,"speed":8,"cooldown":2,"behavior":"straight","target":"all"}],
            "items":[{"id":"base:forward_guns","name":"Fixture guns","price":0,"max_count":1,"weapon":"base:test_gun"},
                {"id":"base:energy","name":"Shield","price":10000,"max_count":100}],
            "missions":[{"id":"base:sector_1_wave_1","name":"Boss validation","duration":2,"auto_complete":false}]
        })).unwrap();
        let mut base = Registry::default();
        base.apply(pack, "base").unwrap();
        base.validate().unwrap();
        let mods = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .unwrap()
            .parent()
            .unwrap();
        let discovery = modding::discover(mods);
        let mut active = ActiveMods::build(&base, &discovery, &[OWNER.into()], None).unwrap();
        let pilot = Pilot::default();
        let mut world =
            World::new(&"base:sector_1_wave_1".into(), &pilot, &active.registry).unwrap();
        world.player.x = 0;
        world
            .apply_commands(
                &[Command::Spawn {
                    enemy: format!("{OWNER}:unit"),
                    x: 112,
                    y: -24,
                }],
                &active.registry,
            )
            .unwrap();
        let mut warning_count = 0;
        let mut shot_count = 0;
        for _ in 0..600 {
            world
                .step(Input::default(), &active.registry, &mut active.scripts)
                .unwrap();
            warning_count += world
                .mod_sounds
                .iter()
                .filter(|s| s.0.ends_with(":warning"))
                .count();
            shot_count += world
                .mod_sounds
                .iter()
                .filter(|s| s.0.ends_with(":shot"))
                .count();
        }
        assert_eq!(
            world.enemies.len(),
            1,
            "timer and scrolling cannot retire the boss"
        );
        assert_eq!(world.outcome, Outcome::Playing);
        assert_eq!(world.enemies[0].y, 24);
        assert!((80..=144).contains(&world.enemies[0].x));
        assert!(warning_count >= 10 && shot_count >= 30);
        assert!(!world.objectives.contains_key("iron_coast_boss_5:defeated"));
        let entity = world.enemies[0].entity;
        world
            .apply_commands(
                &[Command::Damage {
                    entity,
                    amount: 160,
                }],
                &active.registry,
            )
            .unwrap();
        world
            .step(Input::default(), &active.registry, &mut active.scripts)
            .unwrap();
        assert!(world.enemies.is_empty());
        assert_eq!(world.objectives["iron_coast_boss_5:defeated"], 1);
        assert_eq!(world.player.credits, pilot.credits + 1800);
        assert!(world.mod_sounds.iter().any(|s| s.0.ends_with(":death")));
        assert!(
            active.scripts.states[KEY]["units"]
                .get(entity.to_string())
                .is_none()
        );
        for _ in 0..80 {
            world
                .step(Input::default(), &active.registry, &mut active.scripts)
                .unwrap();
            assert!(!world.mod_sounds.iter().any(|s| s.0.ends_with(":shot")));
        }
        assert_eq!(world.objectives["iron_coast_boss_5:defeated"], 1);
        assert_eq!(
            world.outcome,
            Outcome::Playing,
            "boss never completes a mission itself"
        );
    }
}
