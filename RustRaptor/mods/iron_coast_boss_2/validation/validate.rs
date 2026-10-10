//! Standalone mod acceptance without original copyrighted game data.
use anyhow::{Result, ensure};
use raptor_replica::{
    content::{ContentId, ContentPack, Registry},
    modding::{self, ActiveMods, Command, ScriptRuntime},
    persistence::Pilot,
    simulation::{Input, Outcome, Projectile, World},
};
use serde_json::{Value, json};
use std::path::PathBuf;
const OWNER: &str = "iron_coast_boss_2";
const SCRIPT: &str = "scripts/ai.rhai";
const STATE: &str = "iron_coast_boss_2/scripts/ai.rhai";
const OBJECTIVE: &str = "iron_coast_boss_2:defeated";

fn event(entity: u64, health: i32, x: i32, y: i32) -> Value {
    json!({"entity":entity,"health":health,"x":x,"y":y,"tick":900,
           "objectives":{},"entities":[{"entity":entity,"health":health,"x":x,"y":y}]})
}
fn invoke(runtime: &mut ScriptRuntime, hook: &str, event: Value) -> Result<Vec<Command>> {
    runtime.begin_tick();
    runtime.invoke(OWNER, SCRIPT, hook, &event, 31)
}
fn main() -> Result<()> {
    let mods = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .canonicalize()?;
    let mut base = Registry::default();
    let content: ContentPack = serde_json::from_value(json!({
      "weapons":[{"id":"base:projectile_forward_guns","name":"Forward guns","damage":1000,"speed":8,"cooldown":2,"behavior":"straight","target":"all"}],
      "items":[{"id":"base:forward_guns","name":"Forward guns","price":0,"weapon":"base:projectile_forward_guns"},
               {"id":"base:energy","name":"Shield","price":0,"max_count":100}],
      "missions":[{"id":"base:sector_1_wave_1","name":"Boss test","duration":10000,"auto_complete":false,
                   "spawns":[{"tick":1,"enemy":"iron_coast_boss_2:unit","x":112,"y":-64}]}]
    }))?;
    base.apply(content, "base")?;
    let discovery = modding::discover(&mods);
    let mut active = ActiveMods::build(&base, &discovery, &[OWNER.into()], None)?;
    let def = &active.registry.enemies[&ContentId::from("iron_coast_boss_2:unit")];
    ensure!(def.health == 160 && def.reward == 1800 && def.boss && def.speed == 0);
    let rt = &mut active.scripts;
    let mut cues = Vec::new();
    invoke(rt, "on_spawn", event(1, 160, 112, 24))?;
    let mut first = Vec::new();
    let mut second = Vec::new();
    for age in 1..=108 {
        let commands = invoke(rt, "on_tick", event(1, 160, 112, 24))?;
        for command in &commands {
            if let Command::PlaySound { sound } = command {
                cues.push((age, sound.clone()));
            }
        }
        let shots: Vec<_> = commands
            .iter()
            .filter_map(|command| {
                if let Command::Projectile {
                    x,
                    y,
                    vx,
                    vy,
                    hostile,
                    weapon,
                } = command
                {
                    Some((*x, *y, *vx, *vy, *hostile, weapon.clone()))
                } else {
                    None
                }
            })
            .collect();
        if age == 54 {
            first = shots;
        } else if age == 108 {
            second = shots;
        } else {
            ensure!(shots.is_empty(), "unexpected volley at age {age}");
        }
    }
    ensure!(first.len() == 2 && second.len() == 2 && first != second);
    ensure!(first.iter().all(|p| p.2 == 0 && p.3 == 4 && p.4));
    ensure!(second[0].2 == -1 && second[1].2 == 1);
    ensure!(
        cues == vec![
            (42, format!("{OWNER}:warning")),
            (54, format!("{OWNER}:shot")),
            (96, format!("{OWNER}:warning")),
            (108, format!("{OWNER}:shot"))
        ]
    );
    invoke(rt, "on_spawn", event(2, 160, 112, 24))?;
    ensure!(rt.states[STATE]["ages"]["2"] == 0);
    ensure!(
        invoke(rt, "on_death", event(1, 160, 112, 24))?.is_empty(),
        "living unit cannot register a death"
    );
    ensure!(
        invoke(rt, "on_tick", event(1, 0, 112, 24))?.is_empty(),
        "dead unit cannot fire or warn"
    );
    let mut death = event(1, 0, 112, 24);
    death["entities"] = json!([{"entity":2,"health":160}]);
    let commands = invoke(rt, "on_death", death.clone())?;
    ensure!(
        commands
            .iter()
            .any(|c| matches!(c,Command::Objective{key,value} if key==OBJECTIVE && *value==1))
    );
    ensure!(commands.iter().all(|c| !matches!(c, Command::Complete)));
    ensure!(
        invoke(rt, "on_death", death)?.is_empty(),
        "duplicate death cannot increment objective"
    );
    ensure!(rt.states[STATE]["ages"].get("1").is_none());
    ensure!(
        rt.states[STATE]["ages"]["2"] == 0,
        "another entity retains independent cursor"
    );
    let mut death2 = event(2, 0, 112, 24);
    death2["entities"] = json!([]);
    death2["objectives"] = json!({OBJECTIVE:1});
    let commands = invoke(rt, "on_death", death2)?;
    ensure!(
        commands
            .iter()
            .any(|c| matches!(c,Command::Objective{key,value} if key==OBJECTIVE && *value==2))
    );
    ensure!(rt.states[STATE]["ages"].as_object().unwrap().is_empty());
    ensure!(
        rt.states[STATE]["directions"]
            .as_object()
            .unwrap()
            .is_empty()
    );

    // Run actual engine hooks and command application; no scripted mission completion.
    active = ActiveMods::build(&base, &discovery, &[OWNER.into()], None)?;
    let pilot = Pilot::default();
    let mut world = World::new(&pilot.mission, &pilot, &active.registry)?;
    let mut actual_cues = std::collections::BTreeSet::new();
    for _ in 0..150 {
        world.step(Input::default(), &active.registry, &mut active.scripts)?;
        for cue in &world.mod_sounds {
            actual_cues.insert(cue.0.clone());
        }
    }
    ensure!(world.enemies.len() == 1 && world.enemies[0].y == 24);
    ensure!(world.enemies[0].x >= 79 && world.enemies[0].x <= 145);
    ensure!(
        actual_cues.contains("iron_coast_boss_2:warning")
            && actual_cues.contains("iron_coast_boss_2:shot")
    );
    let initial_credits = world.player.credits;
    world.enemies[0].health = 0;
    world.step(Input::default(), &active.registry, &mut active.scripts)?;
    ensure!(world.objectives[OBJECTIVE] == 1 && world.enemies.is_empty());
    ensure!(world.player.credits == initial_credits + 1800);
    ensure!(
        world.outcome == Outcome::Playing,
        "boss never completes the mission itself"
    );
    let shots = active.scripts.states[STATE]["shots"].clone();
    for _ in 0..120 {
        world.step(Input::default(), &active.registry, &mut active.scripts)?;
    }
    ensure!(world.objectives[OBJECTIVE] == 1 && active.scripts.states[STATE]["shots"] == shots);
    ensure!(
        active.scripts.states[STATE]["ages"]
            .as_object()
            .unwrap()
            .is_empty()
    );
    // A projectile can kill a scheduled spawn during advance, before on_spawn dispatch.
    // Use an actual stationary projectile inside the arriving boss silhouette.
    let mut early_active = ActiveMods::build(&base, &discovery, &[OWNER.into()], None)?;
    let mut early_world = World::new(&pilot.mission, &pilot, &early_active.registry)?;
    early_world.step(
        Input::default(),
        &early_active.registry,
        &mut early_active.scripts,
    )?;
    early_world.projectiles.push(Projectile {
        entity: 9000,
        weapon: ContentId::from("base:projectile_forward_guns"),
        x: 160,
        y: -40,
        px: 160,
        py: -40,
        vx: 0,
        vy: 0,
        hostile: false,
        age: 0,
        legacy: None,
        legacy_enemy: None,
    });
    early_world.step(
        Input::default(),
        &early_active.registry,
        &mut early_active.scripts,
    )?;
    ensure!(
        early_world.enemies.len() == 1 && early_world.enemies[0].health <= 0,
        "lethal projectile must kill the boss in its spawn step"
    );
    early_world.step(
        Input::default(),
        &early_active.registry,
        &mut early_active.scripts,
    )?;
    ensure!(
        early_world.objectives.get(OBJECTIVE) == Some(&1),
        "queued spawn-step kill must increment its actual-death objective"
    );
    ensure!(
        early_active.scripts.states[STATE]["ages"]
            .as_object()
            .unwrap()
            .is_empty()
    );
    // Reusing an entity ID in a new mission must count its new life, while another
    // death notification for that life must stay harmless.
    let rt = &mut early_active.scripts;
    invoke(rt, "on_spawn", event(1, 160, 112, 24))?;
    let mut reused = event(1, 0, 112, 24);
    reused["entities"] = json!([]);
    reused["objectives"] = json!({OBJECTIVE: 1});
    let reused_commands = invoke(rt, "on_death", reused.clone())?;
    ensure!(reused_commands.iter().any(|c| matches!(c,
        Command::Objective { key, value } if key == OBJECTIVE && *value == 2)));
    ensure!(invoke(rt, "on_death", reused)?.is_empty());
    println!(
        "{}",
        serde_json::to_string_pretty(&json!({
            "mod":OWNER,"package_validation":"passed; PNGs, sound decoding, manifest and script",
            "warning_ages":[42,96],"volley_ages":[54,108],"first_volley":first,"second_volley":second,
            "actual_engine_tick":world.tick,"death_objective":world.objectives[OBJECTIVE],
            "reward":world.player.credits-initial_credits,"outcome":format!("{:?}",world.outcome),
            "per_entity_state_cleanup":"passed","dead_or_repeated_callbacks":"no commands",
            "actual_cues":actual_cues,
            "queued_spawn_step_lethal_projectile":"passed",
            "reused_entity_id_new_life":"counts once"
        }))?
    );
    Ok(())
}
