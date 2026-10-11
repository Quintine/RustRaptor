//! Real native lethal-collision stress with retained serializable Rhai state.
use raptor_replica::{
    assets::Catalog,
    content::{ContentPack, Registry},
    modding::{self, ActiveMods, Discovery, ScriptRuntime},
    persistence::Pilot,
    simulation::{Input, Projectile, World},
};
use serde_json::{Value, json};
use std::{
    collections::{BTreeMap, BTreeSet},
    path::PathBuf,
};
type Result<T> = std::result::Result<T, Box<dyn std::error::Error>>;
fn closure(d: &Discovery, id: &str, out: &mut BTreeSet<String>) {
    if !out.insert(id.into()) {
        return;
    }
    for dep in d.mods[id].manifest.dependencies.keys() {
        closure(d, dep, out);
    }
}
fn input() -> Input {
    Input {
        absolute: Some([282, 160]),
        ..Input::default()
    }
}
fn pilot(difficulty: u32) -> Pilot {
    let mut p = Pilot::default();
    p.difficulty = difficulty;
    p.credits = 10000;
    p.inventory.insert("base:energy".into(), 75);
    p
}
fn restore(active: &mut ActiveMods, discovery: &Discovery, enabled: &[String]) -> Result<()> {
    let cp = active.scripts.checkpoints();
    let encoded = serde_json::to_vec(&cp)?;
    let mut scripts = ScriptRuntime::new();
    for owner in enabled {
        for path in &discovery.mods[owner].manifest.scripts {
            scripts.add(
                owner,
                path,
                &std::fs::read_to_string(discovery.mods[owner].root.join(path))?,
            )?;
        }
    }
    scripts.restore(serde_json::from_slice(&encoded)?);
    active.scripts = scripts;
    Ok(())
}
fn event(id: u64, hp: i32, key: &str, count: i32) -> Value {
    json!({"entity":id,"x":88,"y":24,"health":hp,"tick":999,"player_x":282,"player_y":160,"entities":[{"entity":id,"health":hp}],"objectives":{key:count}})
}
fn guard(active: &ActiveMods, key: &str) -> usize {
    let state = &active.scripts.states[key];
    let dead = state["dead"].as_object().unwrap();
    let fifo = state["dead_order"].as_array().unwrap();
    assert!(dead.len() <= 128);
    assert!(fifo.len() <= 128);
    assert_eq!(dead.len(), fifo.len());
    let unique = fifo
        .iter()
        .map(|v| v.as_str().unwrap())
        .collect::<BTreeSet<_>>();
    assert_eq!(unique.len(), fifo.len());
    assert_eq!(
        dead.keys().map(|v| v.as_str()).collect::<BTreeSet<_>>(),
        unique
    );
    if let Some(units) = state.get("units") {
        assert!(units.as_object().unwrap().is_empty());
    }
    serde_json::to_vec(state).unwrap().len()
}
fn kill(
    active: &mut ActiveMods,
    unit: &str,
    id: u64,
    objective: &str,
    reward: u32,
    target: bool,
    difficulty: u32,
) -> Result<World> {
    let mut w = World::new(
        &"review:retained".into(),
        &pilot(difficulty),
        &active.registry,
    )?;
    w.next_entity = id;
    let y = if target { 60 } else { 24 };
    w.projectiles.push(Projectile {
        entity: 500000,
        weapon: "review:lethal".into(),
        x: 90,
        y: y + 6,
        px: 90,
        py: y + 6,
        vx: 0,
        vy: 0,
        hostile: false,
        age: 0,
        legacy: None,
        legacy_enemy: None,
    });
    for _ in 0..3 {
        w.step(input(), &active.registry, &mut active.scripts)?;
    }
    assert!(w.enemies.is_empty(), "{unit} survived");
    assert_eq!(w.objectives.get(objective), Some(&1));
    assert_eq!(w.player.credits, 10000 + reward);
    assert_eq!(w.player.shield, if target { 87 } else { 75 });
    w.step(input(), &active.registry, &mut active.scripts)?;
    assert_eq!(w.objectives.get(objective), Some(&1));
    assert_eq!(w.player.credits, 10000 + reward);
    Ok(w)
}
fn phase_warnings(active: &mut ActiveMods, owner: &str, key: &str) -> Result<Vec<Value>> {
    let warning = format!("{owner}:warning");
    let objective = format!("{owner}:phase");
    let mut rows = vec![];
    for difficulty in 0..=3 {
        let mut w = World::new(
            &"review:retained".into(),
            &pilot(difficulty),
            &active.registry,
        )?;
        w.next_entity = 95000 + difficulty as u64;
        let mut high_warnings = vec![];
        while high_warnings.len() < 2 {
            assert!(w.tick < 100);
            w.step(input(), &active.registry, &mut active.scripts)?;
            if w.mod_sounds.iter().any(|s| s.0 == warning) {
                high_warnings.push(w.tick);
            }
            w.projectiles.retain(|p| !p.hostile);
        }
        let entity = w.enemies[0].entity;
        let max_hp = w.enemies[0].health;
        w.enemies[0].health = max_hp / 2;
        // Exercise the upgrade path for a saved pre-latch live entity as well.
        if difficulty == 0 {
            active.scripts.states.get_mut(key).unwrap()["units"][entity.to_string()]
                .as_object_mut()
                .unwrap()
                .remove("phase");
        }
        let mut new_warning = 0;
        let mut release = 0;
        for offset in 0..=14 {
            w.step(input(), &active.registry, &mut active.scripts)?;
            let warnings = w.mod_sounds.iter().filter(|s| s.0 == warning).count();
            let shots = w
                .projectiles
                .iter()
                .filter(|p| p.hostile && p.age == 0)
                .count();
            if offset == 0 {
                assert_eq!(warnings, 1);
                new_warning = w.tick;
                assert_eq!(w.objectives.get(&objective), Some(&2));
            } else {
                assert_eq!(warnings, 0);
            }
            if offset < 14 {
                assert_eq!(shots, 0, "new health phase fired before full warning");
            } else {
                assert_eq!(shots, if owner.ends_with('3') { 3 } else { 4 });
                release = w.tick;
            }
            w.projectiles.retain(|p| !p.hostile);
        }
        assert_eq!(release - new_warning, 14);
        println!(
            "{owner} actual difficulty{difficulty}: health transition after high warning{}; new warning{new_warning} release{release}, full14ticks",
            high_warnings[1]
        );
        rows.push(json!({"difficulty":difficulty,"actual_spawn_health":max_hp,"high_phase_warnings":high_warnings,"phase2_warning":new_warning,"phase2_release":release,"new_phase_warning_ticks":release-new_warning,"old_phase_latch_absent":difficulty==0}));
    }
    Ok(rows)
}
fn main() -> Result<()> {
    let package = PathBuf::from(std::env::args().nth(1).expect("pass own package"));
    let package = package.canonicalize()?;
    let owner = package.file_name().unwrap().to_str().unwrap();
    let target = owner.contains("mission");
    let hook = if target {
        "scripts/target.rhai"
    } else {
        "scripts/ai.rhai"
    };
    let key = format!("{owner}/{hook}");
    let unit = format!("{owner}:{}", if target { "target" } else { "unit" });
    let objective = format!(
        "{owner}:{}",
        if target {
            "targets_destroyed"
        } else {
            "defeated"
        }
    );
    let root = package.parent().unwrap().parent().unwrap();
    let cat = Catalog::open(&root.join("data"))?;
    let mut base = Registry::base(&cat)?;
    let content: ContentPack = serde_json::from_value(
        json!({"missions":[{"id":"review:retained","name":"Test-only retained collision fixture","duration":10000,"auto_complete":false,"spawns":[{"tick":0,"enemy":unit,"x":88,"y":if target{60}else{24}}]}],"weapons":[{"id":"review:lethal","name":"Test-only stationary lethal projectile","damage":10000,"speed":0,"cooldown":1,"target":"all","behavior":"straight"}]}),
    )?;
    base.apply(content, "review")?;
    let discovery = modding::discover(&root.join("mods"));
    let mut enabled = BTreeSet::new();
    closure(&discovery, owner, &mut enabled);
    let enabled = enabled.into_iter().collect::<Vec<_>>();
    let mut a = ActiveMods::build(&base, &discovery, &enabled, Some(&cat))?;
    let reward = a.registry.enemies[&unit.as_str().into()].reward;
    let phase_transitions = if target {
        vec![]
    } else {
        phase_warnings(&mut a, owner, &key)?
    };
    let mut max_bytes = 0;
    for life in 0..1205u64 {
        let id = if life >= 1200 { 10000 } else { 10000 + life };
        let world = kill(&mut a, &unit, id, &objective, reward, target, 2)?;
        let commands =
            a.scripts
                .invoke(owner, hook, "on_death", &event(id, 0, &objective, 1), 303)?;
        assert!(commands.is_empty(), "duplicate death emitted commands");
        assert_eq!(world.player.credits, 10000 + reward);
        max_bytes = max_bytes.max(guard(&a, &key));
        if life % 137 == 0 {
            restore(&mut a, &discovery, &enabled)?;
        }
        if life % 128 == 0 || life == 1204 {
            println!(
                "{owner} retained native kills={}; statebytes={} retired={}",
                life + 1,
                guard(&a, &key),
                a.scripts.states[&key]["dead"].as_object().unwrap().len()
            );
        }
    }
    // Earlier pre-FIFO checkpoints migrate within the real engine limits. This
    // includes a death flag for the entity killed before queued on_spawn executes.
    let old_dead = (0..960)
        .map(|n| (format!("{}", 60000 + n), json!(true)))
        .collect::<BTreeMap<_, _>>();
    a.scripts
        .states
        .insert(key.clone(), json!({"dead":old_dead,"units":{}}));
    restore(&mut a, &discovery, &enabled)?;
    kill(&mut a, &unit, 60001, &objective, reward, target, 2)?;
    assert_eq!(a.scripts.states[&key]["dead"]["60001"], json!(true));
    guard(&a, &key);
    let migrated_state_bytes = serde_json::to_vec(&a.scripts.states[&key])?.len();
    for difficulty in 0..=3 {
        kill(
            &mut a,
            &unit,
            70000 + difficulty as u64,
            &objective,
            reward,
            target,
            difficulty,
        )?;
        guard(&a, &key);
    }
    // Two live same-definition entities keep separate state; abandoned-world
    // entity clocks are discarded at the next actual spawn instead of accumulating.
    let mut abandoned_peak = 0;
    if !target {
        for life in 0..1205u64 {
            let mut w = World::new(&"review:retained".into(), &pilot(2), &a.registry)?;
            w.next_entity = 80000 + life;
            w.step(input(), &a.registry, &mut a.scripts)?;
            assert_eq!(w.enemies.len(), 1);
            assert_eq!(
                a.scripts.states[&key]["units"].as_object().unwrap().len(),
                1
            );
            abandoned_peak = abandoned_peak.max(serde_json::to_vec(&a.scripts.states[&key])?.len());
        }
        let mut e1 = event(90000, 240, &objective, 0);
        e1["entities"] = json!([{"entity":90000,"health":240}]);
        a.scripts.invoke(owner, hook, "on_spawn", &e1, 303)?;
        for _ in 0..20 {
            a.scripts.invoke(owner, hook, "on_tick", &e1, 303)?;
        }
        let age = a.scripts.states[&key]["units"]["90000"]["age"].clone();
        let mut e2 = event(90001, 240, &objective, 0);
        e2["entities"] = json!([{"entity":90000,"health":240},{"entity":90001,"health":240}]);
        a.scripts.invoke(owner, hook, "on_spawn", &e2, 303)?;
        assert_eq!(a.scripts.states[&key]["units"]["90000"]["age"], age);
        assert_eq!(a.scripts.states[&key]["units"]["90001"]["age"], 0);
    }
    let report = json!({"fixture":"actual bundled Catalog; test-only stationary lethal projectile; native World collision, death, reward and retained ScriptRuntime","owner":owner,"unit":unit,"actual_native_collision_lives":1205,"distinct_ids":1200,"reused_id_lives":5,"checkpoint_json_roundtrips":9,"maximum_death_state_bytes":max_bytes,"actual_phase_transition_warnings":phase_transitions,"retired_guard_capacity":128,"duplicate_callback_commands":0,"reward_per_life":reward,"target_shield_restore":if target {12}else{0},"legacy_960_guard_migration":true,"migration_state_bytes":migrated_state_bytes,"difficulty_kills":[0,1,2,3],"abandoned_live_replays":if target {0}else{1205},"maximum_abandoned_state_bytes":abandoned_peak,"two_live_clocks_retained":!target,"enabled":enabled,"package_pins_at_execution":a.pins,"scope":"callback lifecycle/bounded-state proof, not mission combat balance"});
    std::fs::write(
        package.join("validation/retained-state.json"),
        serde_json::to_vec_pretty(&report)?,
    )?;
    println!(
        "{owner}: all actual collision/reward, migration, deduplication, retained-state and abandoned-live checks passed"
    );
    Ok(())
}
