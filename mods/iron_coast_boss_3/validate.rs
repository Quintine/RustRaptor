//! Package-local callback acceptance probe; compile against raptor_replica and serde_json.
use raptor_replica::{
    content::{ContentPack, Registry},
    modding::{self, ActiveMods, Command, ScriptRuntime},
    persistence::Pilot,
    simulation::{Input, World},
};
use serde_json::{Value, json};
use std::path::Path;

const OWNER: &str = "iron_coast_boss_3";
const SCRIPT: &str = "scripts/ai.rhai";

fn runtime(path: &Path) -> ScriptRuntime {
    let mut result = ScriptRuntime::new();
    result
        .add(
            OWNER,
            SCRIPT,
            &std::fs::read_to_string(path.join(SCRIPT)).unwrap(),
        )
        .unwrap();
    result
}

fn event(entity: u64, x: i32, y: i32, health: i32) -> Value {
    json!({"entity":entity, "x":x, "y":y, "health":health, "tick":999,
        "entities":[{"entity":entity,"health":health}],"objectives":{}})
}

fn call(runtime: &mut ScriptRuntime, hook: &str, event: Value) -> Vec<Command> {
    runtime.invoke(OWNER, SCRIPT, hook, &event, 303).unwrap()
}

fn queued_spawn_replay(package: &Path) {
    let mut base = Registry::default();
    let content: ContentPack = serde_json::from_value(json!({
        "weapons":[{"id":"base:projectile_forward_guns","name":"Forward Guns","damage":1,"speed":8,"cooldown":2,"behavior":"straight","target":"all"}],
        "items":[{"id":"base:forward_guns","name":"Forward Guns","price":0,"weapon":"base:projectile_forward_guns"},
            {"id":"base:energy","name":"Shield","price":0,"max_count":100}],
        "missions":[{"id":"base:sector_1_wave_1","name":"Spawn lifecycle collision regression","duration":500,"auto_complete":false,
            "spawns":[{"tick":0,"enemy":"iron_coast_boss_3:unit","x":112,"y":120}]}]
    })).unwrap();
    base.apply(content, "base").unwrap();
    let discovery = modding::discover(package.parent().unwrap());
    let mut active = ActiveMods::build(&base, &discovery, &[OWNER.to_string()], None).unwrap();
    // A real collision during advance kills this fragile boss before dispatch.
    // Its on_spawn callback is queued before on_death, and both see no live boss.
    active
        .registry
        .enemies
        .get_mut(&"iron_coast_boss_3:unit".into())
        .unwrap()
        .health = 1;
    let mut pilot = Pilot::default();
    pilot.difficulty = 2;
    pilot.credits = 0;
    let mut reused_id = None;
    for replay in 0..3 {
        let mut world = World::new(&pilot.mission, &pilot, &active.registry).unwrap();
        world
            .step(
                Input {
                    absolute: Some([144, 160]),
                    ..Input::default()
                },
                &active.registry,
                &mut active.scripts,
            )
            .unwrap();
        assert!(
            world.enemies.is_empty(),
            "collision must remove the boss before dispatch"
        );
        assert_eq!(
            world.objectives.get("iron_coast_boss_3:defeated"),
            Some(&1),
            "replay {replay} must count its new lifecycle"
        );
        assert_eq!(
            world.player.credits, 1800,
            "exactly one engine reward per lifecycle"
        );
        let checkpoints = active.scripts.checkpoints();
        let state = &checkpoints.0["iron_coast_boss_3/scripts/ai.rhai"];
        let ids = state["dead"]
            .as_object()
            .unwrap()
            .keys()
            .collect::<Vec<_>>();
        assert_eq!(ids.len(), 1);
        if let Some(ref previous) = reused_id {
            assert_eq!(previous, ids[0]);
        } else {
            reused_id = Some(ids[0].clone());
        }
        assert!(state["units"].as_object().unwrap().is_empty());
        assert!(world.projectiles.is_empty(), "dead spawn must not shoot");
        assert_eq!(world.mod_sounds, vec!["iron_coast_boss_3:death".into()]);
        world
            .step(Input::default(), &active.registry, &mut active.scripts)
            .unwrap();
        assert_eq!(world.player.credits, 1800);
        assert_eq!(world.objectives.get("iron_coast_boss_3:defeated"), Some(&1));
        // Reconstruct the runtime from saved state exactly as a pilot load does.
        let mut restored = runtime(package);
        restored.restore(checkpoints);
        active.scripts = restored;
    }
}

fn main() {
    let path = std::env::args().nth(1).expect("pass package directory");
    let path = Path::new(&path);
    let mut ai = runtime(path);
    call(&mut ai, "on_spawn", event(1, 112, -64, 160));
    for _ in 0..20 {
        let commands = call(&mut ai, "on_tick", event(1, 112, -64, 160));
        assert!(
            !commands
                .iter()
                .any(|c| matches!(c, Command::Projectile { .. } | Command::PlaySound { .. }))
        );
    }
    let mut warnings = Vec::new();
    let mut volleys = Vec::new();
    for tick in 1..=108 {
        let commands = call(&mut ai, "on_tick", event(1, 112, 24, 160));
        if commands
            .iter()
            .any(|c| matches!(c,Command::PlaySound{sound} if sound=="iron_coast_boss_3:warning"))
        {
            warnings.push(tick);
        }
        let shells = commands
            .iter()
            .filter_map(|c| match c {
                Command::Projectile {
                    weapon,
                    x,
                    y,
                    vx,
                    vy,
                    hostile,
                } => {
                    assert_eq!(weapon, "iron_coast_boss_3:projectile");
                    assert_eq!((*y, *vy, *hostile), (78, 4, true));
                    Some((*x, *vx))
                }
                _ => None,
            })
            .collect::<Vec<_>>();
        if !shells.is_empty() {
            volleys.push((tick, shells));
        }
    }
    assert_eq!(warnings, vec![45, 99]);
    assert_eq!(
        volleys,
        vec![
            (54, vec![(147, 0), (147, 1)]),
            (108, vec![(173, 0), (173, -1)])
        ]
    );
    assert!(
        call(&mut ai, "on_tick", event(1, 144, 24, 160))
            .iter()
            .any(|c| matches!(c, Command::Velocity { vx: -1, vy: 0, .. }))
    );
    assert!(
        call(&mut ai, "on_tick", event(1, 80, 24, 160))
            .iter()
            .any(|c| matches!(c, Command::Velocity { vx: 1, vy: 0, .. }))
    );
    // A second boss starts a separate clock and cannot inherit the first gun phase.
    call(&mut ai, "on_spawn", event(2, 112, 24, 160));
    assert!(
        !call(&mut ai, "on_tick", event(2, 112, 24, 160))
            .iter()
            .any(|c| matches!(c, Command::Projectile { .. }))
    );
    let mut restored = runtime(path);
    restored.restore(ai.checkpoints());
    for _ in 0..111 {
        assert_eq!(
            serde_json::to_value(call(&mut ai, "on_tick", event(1, 112, 24, 160))).unwrap(),
            serde_json::to_value(call(&mut restored, "on_tick", event(1, 112, 24, 160))).unwrap()
        );
    }
    // A dead or absent entity cannot move or fire. Death reports once and never wins a mission itself.
    assert!(call(&mut ai, "on_tick", event(1, 112, 24, 0)).is_empty());
    let mut missing = event(1, 112, 24, 160);
    missing["entities"] = json!([]);
    assert!(call(&mut ai, "on_tick", missing).is_empty());
    let death = call(&mut ai, "on_death", event(1, 112, 24, 0));
    assert!(
        death.iter().any(
            |c| matches!(c,Command::Objective{key,value:1} if key=="iron_coast_boss_3:defeated")
        )
    );
    assert!(
        !death
            .iter()
            .any(|c| matches!(c, Command::Complete | Command::Credits { .. }))
    );
    assert!(call(&mut ai, "on_death", event(1, 112, 24, 0)).is_empty());
    let mut second = event(2, 112, 24, 0);
    second["objectives"] = json!({"iron_coast_boss_3:defeated":1});
    assert!(
        call(&mut ai, "on_death", second).iter().any(
            |c| matches!(c,Command::Objective{key,value:2} if key=="iron_coast_boss_3:defeated")
        )
    );
    queued_spawn_replay(path);
    println!(
        "Saltbreaker: arrival/patrol, two-shell alternating volleys, nine-step warnings, independent entities, checkpoint replay, dead-unit safety and exact death objectives passed"
    );
    println!(
        "Real World lethal collision before queued spawn: three restored-state replays reuse the same entity ID and each count and reward exactly once"
    );
}
