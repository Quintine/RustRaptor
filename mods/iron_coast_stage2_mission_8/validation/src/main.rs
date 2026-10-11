use raptor_replica::{
    assets::Catalog,
    content::{ContentPack, Registry},
    modding::{self, ActiveMods, Command},
    persistence::Pilot,
    simulation::{Input, Outcome, World},
};
use serde_json::{Value, json};
use std::{
    collections::{BTreeMap, BTreeSet},
    fs,
    path::PathBuf,
};
fn root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../../..")
        .canonicalize()
        .unwrap()
}
fn active(n: u32, boss_only: bool) -> ActiveMods {
    let catalog = Catalog::open(root().join("data")).unwrap();
    let mut base = Registry::base(&catalog).unwrap();
    let mut items = vec![];
    for i in 0..20 {
        items.push(json!({"id":format!("fixture:filler_{i}"),"name":"Neutral saved gear","price":0,"max_count":1}));
    }
    let mut pack: ContentPack = serde_json::from_value(json!({"items":items})).unwrap();
    if boss_only {
        pack.weapons.push(serde_json::from_value(json!({"id":"fixture:instant","name":"Regression-only stationary lethal projectile","damage":10000,"speed":0,"cooldown":100,"target":"all","behavior":"straight"})).unwrap());
        pack.missions.push(serde_json::from_value(json!({"id":"fixture:boss","name":"Controlled carrier encounter","duration":4000,"auto_complete":false,"spawns":[{"tick":1,"enemy":format!("iron_coast_stage2_boss_{n}:unit"),"x":88,"y":if n==7{-88}else{-112}}]})).unwrap());
    }
    base.apply(pack, "fixture").unwrap();
    let discovery = modding::discover(&root().join("mods"));
    let enabled = if boss_only {
        vec![format!("iron_coast_stage2_boss_{n}")]
    } else {
        vec![
            format!("iron_coast_stage2_mission_{n}"),
            format!("iron_coast_stage2_boss_{n}"),
            "iron_coast_stage2_interceptor".into(),
            "iron_coast_stage2_siege".into(),
            "iron_coast_stage2_skimmer".into(),
            "iron_coast_stage2_music".into(),
        ]
    };
    ActiveMods::build(&base, &discovery, &enabled, Some(&catalog)).unwrap()
}
fn pilot(shield: u32, credits: u32, difficulty: u32, full: bool) -> Pilot {
    let mut p = Pilot {
        credits,
        difficulty,
        ..Pilot::default()
    };
    p.inventory.insert("base:energy".into(), shield);
    if full {
        for i in 0..20 {
            if p.inventory_slots() >= 20 {
                break;
            }
            p.inventory
                .insert(format!("fixture:filler_{i}").as_str().into(), 1);
        }
    }
    p
}
fn input(w: &World) -> Input {
    let desired = w
        .enemies
        .iter()
        .filter(|e| e.health > 0 && e.y >= 0)
        .max_by_key(|e| e.y)
        .map(|e| e.x + e.width / 2 - 16)
        .unwrap_or(128);
    let center = w.player.x + 16;
    let threat = w
        .projectiles
        .iter()
        .filter(|p| p.hostile && p.y >= 136 && p.y <= 188 && (p.x + 4 - center).abs() < 24)
        .max_by_key(|p| p.y);
    let aim = if let Some(p) = threat {
        if p.x + 4 < center {
            w.player.x + 36
        } else {
            w.player.x - 36
        }
    } else {
        desired
    };
    Input {
        fire: true,
        absolute: Some([
            (w.player.x + (aim - w.player.x).clamp(-4, 4)).clamp(0, 256),
            160,
        ]),
        ..Input::default()
    }
}

fn run(a: &mut ActiveMods, n: u32, p: &Pilot, boss_only: bool) -> Value {
    a.scripts.restore(Default::default());
    let id = if boss_only {
        "fixture:boss".into()
    } else {
        format!("iron_coast_stage2_mission_{n}:mission_0{n}")
    };
    let mut w = World::new(&id.as_str().into(), p, &a.registry).unwrap();
    let mut peak = 0;
    let mut frames = BTreeSet::new();
    let mut classics = BTreeSet::new();
    let mut positions = BTreeMap::new();
    let mut moving = BTreeSet::new();
    let boss = format!("iron_coast_stage2_boss_{n}:unit");
    let death = format!("iron_coast_stage2_boss_{n}:defeated");
    let mut sounds = BTreeSet::new();
    for _ in 0..5200 {
        w.step(input(&w), &a.registry, &mut a.scripts).unwrap();
        peak = peak.max(w.enemies.len());
        for e in &w.enemies {
            if e.definition.0 == boss {
                frames.insert(e.art_frame);
                assert!(e.pinned_art_frame.is_some());
            }
            if e.definition.0.starts_with("base:enemy_") {
                assert!(a.registry.enemies[&e.definition].legacy.is_some());
                classics.insert(e.definition.0.clone());
                let k = (e.definition.0.clone(), e.entity);
                if let Some(old) = positions.insert(k, (e.x, e.y)) {
                    if old != (e.x, e.y) {
                        moving.insert(e.definition.0.clone());
                    }
                }
            }
        }
        for id in &w.mod_sounds {
            sounds.insert(id.0.clone());
        }
        if boss_only && w.objectives.get(&death).copied() == Some(1) {
            break;
        }
        if w.outcome != Outcome::Playing {
            break;
        }
    }
    if boss_only {
        assert_eq!(
            w.objectives.get(&death).copied(),
            Some(1),
            "boss{n} failed: tick{} shield{} {:?}",
            w.tick,
            w.player.shield,
            w.outcome
        );
        assert_eq!(w.outcome, Outcome::Playing);
    } else {
        assert_eq!(
            w.outcome,
            Outcome::Complete,
            "mission{n} failed: tick{} shield{} {:?}",
            w.tick,
            w.player.shield,
            w.objectives
        );
        assert_eq!(w.objectives[&death], 1);
        assert_eq!(
            w.objectives[&format!("iron_coast_stage2_mission_{n}:complete")],
            1
        );
        assert_eq!(
            w.objectives[&format!("iron_coast_stage2_mission_{n}:debrief")],
            1
        );
        assert_eq!(
            w.objectives["iron_coast_stage2_siege:defeated"],
            if n == 7 { 4 } else { 5 }
        );
        assert_eq!(
            w.objectives["iron_coast_stage2_skimmer:defeated"],
            if n == 7 { 3 } else { 4 }
        );
        assert!(classics.len() >= 4 && moving.len() >= 4);
    }
    assert_eq!(
        frames.len(),
        if n == 7 { 2 } else { 3 },
        "all carrier phases must appear: {frames:?}"
    );
    // Gameplay shield charge may change; equipment identities/counts stay intact.
    for (id, count) in &p.inventory {
        if id.0 != "base:energy" {
            assert_eq!(w.player.inventory.get(id), Some(count));
        }
    }
    assert_eq!(w.player.inventory.len(), p.inventory.len());
    assert_eq!(w.player.super_shield_reserves, p.super_shield_reserves);
    let credits = w.player.credits;
    for _ in 0..4 {
        w.step(Input::default(), &a.registry, &mut a.scripts)
            .unwrap();
    }
    assert_eq!(w.player.credits, credits);
    assert_eq!(w.objectives[&death], 1);
    json!({"mission":n,"boss_only":boss_only,"difficulty":p.difficulty,"initial_shield":p.inventory[&"base:energy".into()],"initial_credits":p.credits,"inventory_slots":p.inventory_slots(),"tick":w.tick-4,"outcome":format!("{:?}",w.outcome),"shield":w.player.shield,"credits":credits,"maximum_live_enemies":peak,"phase_frames":frames,"classic_ids":classics,"native_movement_ids":moving,"objectives":w.objectives,"sound_ids":sounds,"digest":w.digest(),"inventory_preserved":true,"rewards_once":true})
}
fn reachable(a: &mut ActiveMods, n: u32) {
    a.scripts.restore(Default::default());
    let mut p = pilot(100, 0, 0, false);
    p.inventory.insert("base:super_shield".into(), 100);
    p.super_shield_reserves = vec![100; 17];
    let mut w = World::new(
        &format!("iron_coast_stage2_mission_{n}:mission_0{n}")
            .as_str()
            .into(),
        &p,
        &a.registry,
    )
    .unwrap();
    for _ in 0..4050 {
        w.step(
            Input {
                absolute: Some([260, 160]),
                ..Input::default()
            },
            &a.registry,
            &mut a.scripts,
        )
        .unwrap();
        if w.outcome != Outcome::Playing {
            break;
        }
    }
    assert_eq!(
        w.outcome,
        Outcome::Playing,
        "elapsed duration may not grant victory"
    );
    assert_eq!(
        w.enemies
            .iter()
            .filter(|e| e.definition.0 == "iron_coast_stage2_siege:unit")
            .count(),
        if n == 7 { 4 } else { 5 }
    );
    assert_eq!(
        w.enemies
            .iter()
            .filter(|e| e.definition.0 == "iron_coast_stage2_skimmer:unit")
            .count(),
        if n == 7 { 3 } else { 4 }
    );
    assert_eq!(
        w.enemies
            .iter()
            .filter(|e| e.definition.0 == format!("iron_coast_stage2_boss_{n}:unit"))
            .count(),
        1
    );
    assert!(
        w.enemies
            .iter()
            .filter(|e| !e.definition.0.starts_with("base:"))
            .all(|e| e.y <= 80 && e.x >= 0 && e.x + e.width <= 288)
    );
}
fn replay(a: &mut ActiveMods, n: u32) {
    let p = pilot(75, 10000, 2, true);
    a.scripts.restore(Default::default());
    let mut w = World::new(
        &format!("iron_coast_stage2_mission_{n}:mission_0{n}")
            .as_str()
            .into(),
        &p,
        &a.registry,
    )
    .unwrap();
    let mut inputs = vec![];
    let mut digests = vec![];
    let mut continuation = vec![];
    let mut phases = BTreeSet::new();
    for i in 0..5200 {
        let ctl = input(&w);
        inputs.push(ctl);
        w.step(ctl, &a.registry, &mut a.scripts).unwrap();
        digests.push(w.digest());
        if let Some(enemy) = w
            .enemies
            .iter()
            .find(|e| e.definition.0 == format!("iron_coast_stage2_boss_{n}:unit"))
        {
            if phases.insert(enemy.art_frame) {
                continuation.push((
                    i,
                    w.clone(),
                    serde_json::to_vec(&a.scripts.checkpoints()).unwrap(),
                ));
            }
        }
        if w.outcome != Outcome::Playing {
            break;
        }
    }
    assert_eq!(w.outcome, Outcome::Complete);
    let expected = w.digest();
    a.scripts.restore(Default::default());
    let mut second = World::new(&w.mission, &p, &a.registry).unwrap();
    for (i, ctl) in inputs.iter().enumerate() {
        second.step(*ctl, &a.registry, &mut a.scripts).unwrap();
        assert_eq!(second.digest(), digests[i]);
    }
    assert_eq!(second.digest(), expected);
    assert_eq!(continuation.len(), if n == 7 { 2 } else { 3 });
    for (index, mut resumed, state) in continuation {
        a.scripts.restore(serde_json::from_slice(&state).unwrap());
        for ctl in &inputs[index + 1..] {
            resumed.step(*ctl, &a.registry, &mut a.scripts).unwrap();
        }
        assert_eq!(resumed.digest(), expected);
    }
    // Keep the previous script state deliberately: spawn/start callbacks reset it.
    let mut restarted = World::new(&w.mission, &p, &a.registry).unwrap();
    restarted
        .step(Input::default(), &a.registry, &mut a.scripts)
        .unwrap();
    assert_eq!(
        restarted.objectives[&format!("iron_coast_stage2_boss_{n}:defeated")],
        0
    );
    assert_eq!(restarted.objectives["iron_coast_stage2_siege:defeated"], 0);
    assert_eq!(
        restarted.objectives[&format!("iron_coast_stage2_mission_{n}:debrief")],
        0
    );
    restarted
        .apply_commands(
            &[Command::Damage {
                entity: 0,
                amount: 100000,
            }],
            &a.registry,
        )
        .unwrap();
    restarted
        .step(Input::default(), &a.registry, &mut a.scripts)
        .unwrap();
    assert_eq!(restarted.outcome, Outcome::Failed);
    assert_eq!(
        restarted.objectives[&format!("iron_coast_stage2_mission_{n}:complete")],
        0
    );
    for (id, count) in &p.inventory {
        if id.0 != "base:energy" {
            assert_eq!(restarted.player.inventory.get(id), Some(count));
        }
    }
}
fn carrier_callbacks(a: &mut ActiveMods, n: u32) {
    a.scripts.restore(Default::default());
    let owner = format!("iron_coast_stage2_boss_{n}");
    let script = "scripts/ai.rhai";
    let statekey = format!("{owner}/{script}");
    let id = format!("{owner}:unit");
    let hp = if n == 7 { 280 } else { 360 };
    let y = if n == 7 { 16 } else { 4 };
    let ev = |entity: u64, health: i32, count: i32| json!({"entity":entity,"tick":3000,"x":88,"y":y,"health":health,"entities":[{"entity":1,"health":hp,"definition":id},{"entity":2,"health":hp,"definition":id}],"objectives":{format!("{owner}:defeated"):count}});
    a.scripts.begin_tick();
    a.scripts
        .invoke(&owner, script, "on_spawn", &ev(1, hp, 0), 3)
        .unwrap();
    a.scripts
        .invoke(&owner, script, "on_spawn", &ev(2, hp, 0), 3)
        .unwrap();
    for age in 1..=if n == 7 { 84 } else { 96 } {
        a.scripts.begin_tick();
        let cmds = a
            .scripts
            .invoke(&owner, script, "on_tick", &ev(1, hp, 0), 3)
            .unwrap();
        let fire = cmds
            .iter()
            .filter(|c| matches!(c, Command::Projectile { .. }))
            .count();
        assert_eq!(
            fire,
            if age == if n == 7 { 84 } else { 96 } {
                if n == 7 { 3 } else { 4 }
            } else {
                0
            }
        );
        assert!(cmds.iter().all(|c| !matches!(
            c,
            Command::Effect { .. } | Command::Damage { .. } | Command::Complete
        )));
    }
    assert_eq!(a.scripts.states[&statekey]["units"]["1"]["volley"], 1);
    assert_eq!(a.scripts.states[&statekey]["units"]["2"]["volley"], 0);
    a.scripts.begin_tick();
    let cmds = a
        .scripts
        .invoke(&owner, script, "on_tick", &ev(1, hp / 3, 0), 3)
        .unwrap();
    let phase = if n == 7 { 1 } else { 2 };
    assert!(
        cmds.iter()
            .any(|c| matches!(c,Command::Animation{entity:1,frame:Some(f)} if *f==phase))
    );
    let checkpoint = a.scripts.checkpoints();
    let bytes = serde_json::to_vec(&checkpoint).unwrap();
    a.scripts.restore(serde_json::from_slice(&bytes).unwrap());
    assert_eq!(a.scripts.states[&statekey]["units"]["1"]["phase"], phase);
    a.scripts.begin_tick();
    let cmds = a
        .scripts
        .invoke(&owner, script, "on_death", &ev(1, 0, 0), 3)
        .unwrap();
    assert!(
        cmds.iter().any(
            |c| matches!(c,Command::Objective{key,value:1} if key==&format!("{owner}:defeated"))
        )
    );
    assert!(a.scripts.states[&statekey]["units"].get("1").is_none());
    assert!(a.scripts.states[&statekey]["units"].get("2").is_some());
    a.scripts.begin_tick();
    assert!(
        a.scripts
            .invoke(&owner, script, "on_death", &ev(1, 0, 1), 3)
            .unwrap()
            .is_empty()
    );
    // A killed-before-spawn entity still counts a real death and never fires.
    a.scripts.begin_tick();
    let mut immediate = ev(3, 0, 1);
    immediate["entities"] = json!([]);
    let cmds = a
        .scripts
        .invoke(&owner, script, "on_death", &immediate, 3)
        .unwrap();
    assert!(
        cmds.iter()
            .any(|c| matches!(c, Command::Objective { value: 2, .. }))
    );
    assert!(
        a.scripts
            .invoke(&owner, script, "on_spawn", &immediate, 3)
            .unwrap()
            .is_empty()
    );
    // Spawn prunes abandoned prior-world cursors while retaining current peers.
    a.scripts.begin_tick();
    let mut newworld = ev(4, hp, 0);
    newworld["entities"] = json!([{"entity":4,"health":hp,"definition":id}]);
    a.scripts
        .invoke(&owner, script, "on_spawn", &newworld, 3)
        .unwrap();
    assert_eq!(
        a.scripts.states[&statekey]["units"]
            .as_object()
            .unwrap()
            .len(),
        1
    );
}
fn repeated_early_kill(n: u32) {
    let mut a = active(n, true);
    for _ in 0..2 {
        let p = pilot(75, 10000, 2, false);
        let mut w = World::new(&"fixture:boss".into(), &p, &a.registry).unwrap();
        w.apply_commands(
            &[Command::Projectile {
                weapon: "fixture:instant".into(),
                x: 144,
                y: -20,
                vx: 0,
                vy: 0,
                hostile: false,
            }],
            &a.registry,
        )
        .unwrap();
        for _ in 0..3 {
            w.step(Input::default(), &a.registry, &mut a.scripts)
                .unwrap();
        }
        assert_eq!(
            w.objectives[&format!("iron_coast_stage2_boss_{n}:defeated")],
            1
        );
        assert_eq!(
            w.player.credits,
            p.credits + if n == 7 { 5000 } else { 9000 }
        );
        assert!(w.enemies.is_empty());
        w.step(Input::default(), &a.registry, &mut a.scripts)
            .unwrap();
        assert_eq!(
            w.objectives[&format!("iron_coast_stage2_boss_{n}:defeated")],
            1
        );
    }
}
fn audio_proof() {
    use raptor_replica::{
        audio::Mixer,
        sound::{SoundBank, encode_capture},
    };
    let catalog = Catalog::open(root().join("data")).unwrap();
    let genmidi = catalog.named("GENMIDI_OP2").unwrap();
    let rate = 32000;
    let mut all = vec![];
    let mut rows = vec![];
    let mut composite_capture = None;
    for n in [7, 8] {
        let mut registry = Registry::default();
        for kind in ["boss", "mission"] {
            let owner = format!("iron_coast_stage2_{kind}_{n}");
            let package = root().join("mods").join(&owner);
            let pack: ContentPack =
                serde_json::from_slice(&fs::read(package.join("content.json")).unwrap()).unwrap();
            registry
                .apply(
                    ContentPack {
                        sounds: pack.sounds,
                        ..ContentPack::default()
                    },
                    &owner,
                )
                .unwrap();
            registry.asset_roots.insert(owner, package);
        }
        registry.validate().unwrap();
        for (id, _) in registry.sounds.iter().filter(|(id, _)| {
            id.0.starts_with(&format!("iron_coast_stage2_boss_{n}:"))
                || id.0.starts_with(&format!("iron_coast_stage2_mission_{n}:"))
        }) {
            let mut bank = SoundBank::default();
            let mut mixer = Mixer::new(rate, &genmidi).unwrap();
            mixer.music_volume = 0;
            mixer.start_capture(2).unwrap();
            bank.queue_mod(&registry, &mut mixer, id).unwrap();
            let mut pcm = vec![0; rate as usize * 2 * 2];
            mixer.mix(&mut pcm);
            let capture = mixer.take_capture().unwrap();
            assert_eq!(capture.samples, pcm);
            if composite_capture.is_none() {
                composite_capture = Some(capture);
            }
            let peak = pcm.iter().map(|s| i32::from(*s).abs()).max().unwrap();
            let rms =
                (pcm.iter().map(|s| f64::from(*s).powi(2)).sum::<f64>() / pcm.len() as f64).sqrt();
            assert!(peak > 100 && peak < 32767 && rms > 20.0);
            let mut mute = Mixer::new(rate, &genmidi).unwrap();
            mute.fx_volume = 0;
            mute.music_volume = 0;
            bank.queue_mod(&registry, &mut mute, id).unwrap();
            let mut silent = vec![1; rate as usize * 2];
            mute.mix(&mut silent);
            assert!(silent.iter().all(|s| *s == 0));
            rows.push(json!({"sound":id.0,"actual_mixer_peak":peak,"actual_mixer_rms":rms,"muted_exact_zero":true}));
            all.extend(pcm);
        }
    }
    let dir = root()
        .parent()
        .unwrap()
        .join(".reference/iron-coast-stage2-finale");
    fs::write(dir.join("actual-mixer-all-cues.wav"), {
        let mut c = composite_capture.unwrap();
        c.samples = all;
        encode_capture(&c).unwrap()
    })
    .unwrap();
    fs::write(dir.join("actual-audio-proof.json"),serde_json::to_string_pretty(&json!({"sound_count":rows.len(),"mixer":"Production SoundBank::queue_mod + original digital Mixer, genuineGENMIDI table,32kHzstereo PCM","rows":rows,"live_sdl_claim":false})).unwrap()+"\n").unwrap();
    println!("Actual production mixer accepted all16 non-silent cues and exact FX mute");
}
fn main() {
    if std::env::args().any(|a| a == "--audio-only") {
        audio_proof();
        return;
    }
    if std::env::args().any(|a| a == "--list-classics") {
        let a = active(7, true);
        for n in [23, 24, 73, 74, 95, 96] {
            let id = format!("base:enemy_0_{n}");
            println!(
                "{}",
                serde_json::to_string_pretty(&a.registry.enemies[&id.as_str().into()]).unwrap()
            );
        }
        return;
    }
    let boss_only = std::env::args().any(|x| x == "--boss-only");
    let mut rows = vec![];
    for n in [7, 8] {
        repeated_early_kill(n);
        let mut a = active(n, boss_only);
        carrier_callbacks(&mut a, n);
        for d in 0..=3 {
            let p = pilot(75, 10000, d, false);
            rows.push(run(&mut a, n, &p, boss_only));
        }
        if !boss_only {
            rows.push(run(&mut a, n, &pilot(100, 0, 2, false), false));
            rows.push(run(&mut a, n, &pilot(75, 10000, 2, true), false));
            reachable(&mut a, n);
            replay(&mut a, n);
        }
    }
    let v = json!({"proof":"Actual original Catalog/native enemies, production World/Rhai, shipped PNG/WAV/MUS content; ordinary mouse movement capped 4px per tick, near-shot sidesteps at y136..188 and starter guns only","boss_only":boss_only,"runs":rows,"full_inventory":!boss_only,"mandatory_reachable_after4050_ticks":!boss_only,"auto_complete_disabled":!boss_only,"deterministic_every_step_replay":!boss_only,"boss_script_state_continuation":!boss_only,"restart_resets":!boss_only,"failure_preserves_equipment":!boss_only});
    let path = std::env::var_os("FINALE_REPORT")
        .map(PathBuf::from)
        .unwrap_or_else(|| {
            root()
                .parent()
                .unwrap()
                .join(".reference/iron-coast-stage2-finale/validation-results.json")
        });
    fs::write(path, serde_json::to_string_pretty(&v).unwrap() + "\n").unwrap();
    println!("{}", serde_json::to_string_pretty(&v).unwrap());
}
