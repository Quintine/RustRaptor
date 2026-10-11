//! Package-local real callback and World lifecycle acceptance; no production mutation.
use raptor_replica::{
    content::{ContentPack, Registry},
    modding::{self, ActiveMods, Command, ScriptRuntime},
    persistence::Pilot,
    simulation::{Input, World},
};
use serde_json::{Value, json};
use std::path::Path;
fn runtime(package: &Path, owner: &str) -> ScriptRuntime {
    let mut ai = ScriptRuntime::new();
    ai.add(
        owner,
        "scripts/ai.rhai",
        &std::fs::read_to_string(package.join("scripts/ai.rhai")).unwrap(),
    )
    .unwrap();
    ai
}
fn event(id: u64, x: i32, y: i32, hp: i32) -> Value {
    json!({"entity":id,"x":x,"y":y,"health":hp,"tick":999,"player_x":144,"player_y":160,"entities":[{"entity":id,"health":hp}],"objectives":{}})
}
fn call(ai: &mut ScriptRuntime, owner: &str, hook: &str, event: Value) -> Vec<Command> {
    ai.invoke(owner, "scripts/ai.rhai", hook, &event, 303)
        .unwrap()
}
fn lethal_spawn(package: &Path, owner: &str, reward: u32) {
    let unit = format!("{owner}:unit");
    let objective = format!("{owner}:defeated");
    let mut base = Registry::default();
    let content:ContentPack=serde_json::from_value(json!({"weapons":[{"id":"base:projectile_forward_guns","name":"Forward Guns","damage":1,"speed":8,"cooldown":2,"behavior":"straight","target":"all"}],"items":[{"id":"base:forward_guns","name":"Forward Guns","price":0,"weapon":"base:projectile_forward_guns"},{"id":"base:energy","name":"Shield","price":0,"max_count":100}],"missions":[{"id":"base:sector_1_wave_1","name":"Spawn lifecycle regression","duration":500,"auto_complete":false,"spawns":[{"tick":0,"enemy":unit,"x":108,"y":120}]}]})).unwrap();
    base.apply(content, "base").unwrap();
    let discovery = modding::discover(package.parent().unwrap());
    let mut active = ActiveMods::build(&base, &discovery, &[owner.into()], None).unwrap();
    active
        .registry
        .enemies
        .get_mut(&unit.as_str().into())
        .unwrap()
        .health = 1;
    let mut pilot = Pilot::default();
    pilot.difficulty = 2;
    pilot.credits = 0;
    let mut old_id = None;
    for n in 0..3 {
        let mut world = World::new(&pilot.mission, &pilot, &active.registry).unwrap();
        world
            .step(
                Input {
                    fire: true,
                    absolute: Some([144, 160]),
                    ..Input::default()
                },
                &active.registry,
                &mut active.scripts,
            )
            .unwrap();
        assert!(
            world.enemies.iter().all(|e| e.health <= 0),
            "projectile must kill during spawn-step before queued on_spawn"
        );
        assert!(world.projectiles.is_empty());
        assert!(
            world.mod_sounds.is_empty(),
            "dead arrival must not warn/fire"
        );
        world
            .step(Input::default(), &active.registry, &mut active.scripts)
            .unwrap();
        assert!(
            world.enemies.is_empty(),
            "ground death is collected next tick"
        );
        assert_eq!(
            world.objectives.get(&objective),
            Some(&1),
            "reused entity lifecycle {n}"
        );
        assert_eq!(world.player.credits, reward);
        assert!(world.projectiles.is_empty());
        assert_eq!(
            world.mod_sounds,
            vec![format!("{owner}:death").as_str().into()]
        );
        let cp = active.scripts.checkpoints();
        let key = format!("{owner}/scripts/ai.rhai");
        let state = &cp.0[&key];
        let keys = state["dead"]
            .as_object()
            .unwrap()
            .keys()
            .collect::<Vec<_>>();
        assert_eq!(keys.len(), 1);
        if let Some(ref old) = old_id {
            assert_eq!(old, keys[0]);
        } else {
            old_id = Some(keys[0].clone());
        }
        assert!(state["units"].as_object().unwrap().is_empty());
        world
            .step(Input::default(), &active.registry, &mut active.scripts)
            .unwrap();
        assert_eq!(world.player.credits, reward);
        assert_eq!(world.objectives.get(&objective), Some(&1));
        let mut restored = runtime(package, owner);
        restored.restore(cp);
        active.scripts = restored;
    }
}

fn real_difficulty_phases(package: &Path, owner: &str, max_hp: i32) {
    let unit = format!("{owner}:unit");
    let phase = format!("{owner}:phase");
    let mut base = Registry::default();
    let content:ContentPack=serde_json::from_value(json!({"items":[{"id":"base:energy","name":"Shield","price":0,"max_count":100}],"missions":[{"id":"base:sector_1_wave_1","name":"Actual difficulty health contract","duration":500,"auto_complete":false,"spawns":[{"tick":0,"enemy":unit,"x":108,"y":24}]}]})).unwrap();
    base.apply(content, "base").unwrap();
    let discovery = modding::discover(package.parent().unwrap());
    let mut active = ActiveMods::build(&base, &discovery, &[owner.into()], None).unwrap();
    for difficulty in 0..=3 {
        let mut pilot = Pilot::default();
        pilot.difficulty = difficulty;
        let mut world = World::new(&pilot.mission, &pilot, &active.registry).unwrap();
        let expected = if difficulty <= 1 { max_hp / 2 } else { max_hp };
        for _ in 0..3 {
            world
                .step(
                    Input {
                        absolute: Some([5, 160]),
                        ..Input::default()
                    },
                    &active.registry,
                    &mut active.scripts,
                )
                .unwrap();
        }
        assert_eq!(world.enemies[0].health, expected);
        assert_eq!(world.objectives.get(&phase), Some(&1));
        let key = format!("{owner}/scripts/ai.rhai");
        assert_eq!(
            active.scripts.checkpoints().0[&key]["units"][world.enemies[0].entity.to_string()]["max_health"],
            json!(expected)
        );
        world.enemies[0].health = expected / 2;
        for _ in 0..80 {
            world
                .step(
                    Input {
                        absolute: Some([5, 160]),
                        ..Input::default()
                    },
                    &active.registry,
                    &mut active.scripts,
                )
                .unwrap();
        }
        assert_eq!(world.objectives.get(&phase), Some(&2));
        assert!(world.enemies[0].health > 0);
        println!(
            "real World difficulty{difficulty}: spawnHP{expected}, phase1 at arrival then phase2 at {}/half; no missing spawn health",
            expected / 2
        );
    }
}

fn main() {
    let path = std::env::args().nth(1).expect("pass own package");
    let package = Path::new(&path);
    let owner = package.file_name().unwrap().to_str().unwrap();
    let stage = if owner.ends_with('3') { 3 } else { 4 };
    let max_hp = if stage == 3 { 240 } else { 280 };
    for (hp, period, count) in [
        (max_hp, if stage == 3 { 72 } else { 76 }, 2),
        (
            max_hp / 2,
            if stage == 3 { 60 } else { 64 },
            if stage == 3 { 3 } else { 4 },
        ),
    ] {
        let mut ai = runtime(package, owner);
        call(&mut ai, owner, "on_spawn", event(1, 108, -72, max_hp));
        for _ in 0..20 {
            assert!(
                !call(&mut ai, owner, "on_tick", event(1, 108, -72, hp))
                    .iter()
                    .any(|c| matches!(c, Command::Projectile { .. } | Command::PlaySound { .. }))
            );
        }
        let mut warnings = vec![];
        let mut volleys = vec![];
        for tick in 1..=period * 2 {
            let commands = call(&mut ai, owner, "on_tick", event(1, 108, 24, hp));
            if commands.iter().any(
                |c| matches!(c,Command::PlaySound{sound} if sound==&format!("{owner}:warning")),
            ) {
                warnings.push(tick);
                assert_eq!(
                    commands
                        .iter()
                        .filter(|c| matches!(c, Command::Arc { ticks: 8, .. }))
                        .count(),
                    2
                );
            }
            let projectiles = commands
                .iter()
                .filter(|c| matches!(c, Command::Projectile { .. }))
                .collect::<Vec<_>>();
            if !projectiles.is_empty() {
                assert_eq!(projectiles.len(), count);
                for p in projectiles {
                    if let Command::Projectile {
                        weapon,
                        y,
                        vy,
                        hostile,
                        ..
                    } = p
                    {
                        assert_eq!(weapon, &format!("{owner}:shell"));
                        assert_eq!(
                            (*y, *vy, *hostile),
                            if stage == 3 {
                                (86, 3, true)
                            } else {
                                (78, 4, true)
                            }
                        );
                    }
                }
                volleys.push(tick);
            }
        }
        assert_eq!(warnings, vec![1, 1 + period]);
        assert_eq!(volleys, vec![15, 15 + period]);
        let max_x = if stage == 3 { 156 } else { 148 };
        let min_x = if stage == 3 { 60 } else { 68 };
        for (x, negative) in [(max_x, true), (min_x, false)] {
            let c = call(&mut ai, owner, "on_tick", event(1, x, 24, hp));
            assert!(c.iter().any(|c| matches!(c, Command::Move { y: 24, .. }))); /* warning pauses are allowed; direction inspected after next warning */
            for _ in 0..16 {
                let c = call(&mut ai, owner, "on_tick", event(1, x, 24, hp));
                if c.iter()
                    .any(|c| matches!(c,Command::Velocity{vx,..} if *vx!=0))
                {
                    assert!(c.iter().any(|c|matches!(c,Command::Velocity{vx,vy:0,..} if if negative{*vx<0}else{*vx>0})));
                    break;
                }
            }
        }
        call(&mut ai, owner, "on_spawn", event(2, 108, 24, hp));
        assert!(
            !call(&mut ai, owner, "on_tick", event(2, 108, 24, hp))
                .iter()
                .any(|c| matches!(c, Command::Projectile { .. }))
        );
        let mut restored = runtime(package, owner);
        restored.restore(ai.checkpoints());
        for _ in 0..133 {
            assert_eq!(
                serde_json::to_value(call(&mut ai, owner, "on_tick", event(1, 108, 24, hp)))
                    .unwrap(),
                serde_json::to_value(call(&mut restored, owner, "on_tick", event(1, 108, 24, hp)))
                    .unwrap()
            );
        }
        assert!(call(&mut ai, owner, "on_tick", event(1, 108, 24, 0)).is_empty());
        let mut missing = event(1, 108, 24, hp);
        missing["entities"] = json!([]);
        assert!(call(&mut ai, owner, "on_tick", missing).is_empty());
        let death = call(&mut ai, owner, "on_death", event(1, 108, 24, 0));
        assert!(death.iter().any(
            |c| matches!(c,Command::Objective{key,value:1} if key==&format!("{owner}:defeated"))
        ));
        assert!(
            !death
                .iter()
                .any(|c| matches!(c, Command::Complete | Command::Credits { .. }))
        );
        assert!(call(&mut ai, owner, "on_death", event(1, 108, 24, 0)).is_empty());
        let mut second = event(2, 108, 24, 0);
        second["objectives"] = json!({format!("{owner}:defeated"):1});
        assert!(call(&mut ai, owner, "on_death", second).iter().any(
            |c| matches!(c,Command::Objective{key,value:2} if key==&format!("{owner}:defeated"))
        ));
        println!(
            "{owner}: health {hp}, period {period}, volley {count}, warning14 ticks; arrival, bounds, two entities, checkpoint, absent/dead guard and once-only death passed"
        );
    }
    real_difficulty_phases(package, owner, max_hp);
    lethal_spawn(package, owner, if stage == 3 { 2400 } else { 2800 });
    println!(
        "real World lethal queued-spawn, saved-state reused ID and exact reward across three replays: passed"
    );
}
