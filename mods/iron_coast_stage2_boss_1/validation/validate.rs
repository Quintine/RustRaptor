//! Actual API/World integration; all captured original art stays outside packages.
use anyhow::{Result, ensure};
use raptor_replica::{
    assets::{Catalog, Sprite},
    content::{ContentId, ContentPack, Registry, art_sprite_variant},
    modding::{self, ActiveMods, Command},
    persistence::Pilot,
    render::{self, Canvas},
    simulation::{Input, Outcome, World},
    sound,
};
use serde_json::{Value, json};
use std::{
    collections::{BTreeMap, BTreeSet},
    fs,
    path::{Path, PathBuf},
};
fn id(s: &str) -> ContentId {
    s.into()
}
fn build(
    base: &Registry,
    mods: &Path,
    enabled: &[String],
    catalog: Option<&Catalog>,
) -> Result<ActiveMods> {
    ActiveMods::build(base, &modding::discover(mods), enabled, catalog)
}
fn input(world: &World, required: &str, boss: &str) -> Input {
    let target = world
        .enemies
        .iter()
        .filter(|e| e.health > 0 && e.y >= 0 && e.y < 140)
        .find(|e| e.definition.0 == required)
        .or_else(|| {
            world
                .enemies
                .iter()
                .find(|e| e.definition.0 == boss && e.health > 0)
        })
        .or_else(|| {
            world
                .enemies
                .iter()
                .filter(|e| e.health > 0 && e.y >= 0 && e.y < 130)
                .min_by_key(|e| (e.x - world.player.x).abs())
        });
    let desired = target.map(|e| e.x + e.width / 2 - 16).unwrap_or(144);
    Input {
        fire: true,
        absolute: Some([
            world.player.x + (desired - world.player.x).clamp(-4, 4),
            160,
        ]),
        ..Input::default()
    }
}
fn ppm(path: &Path, im: &Sprite, palette: &[[u8; 3]; 256]) -> Result<()> {
    let mut bytes = format!("P6\n{} {}\n255\n", im.width, im.height).into_bytes();
    for c in &im.pixels {
        bytes.extend_from_slice(if *c < 256 {
            &palette[*c as usize]
        } else {
            &[18, 22, 28]
        });
    }
    fs::write(path, bytes)?;
    Ok(())
}
fn capture(
    catalog: &Catalog,
    active: &ActiveMods,
    world: &World,
    out: &Path,
    label: &str,
) -> Result<()> {
    fs::create_dir_all(out)?;
    let palette = catalog.palette()?;
    let mission = &active.registry.missions[&world.mission];
    let owner = active
        .registry
        .owners
        .get(&world.mission)
        .map(String::as_str)
        .unwrap_or("base");
    for hd in [false, true] {
        let scale = if hd { 4 } else { 1 };
        let mut c = Canvas::new(scale);
        c.clear(0);
        if !mission.tiles.is_empty() {
            let row = (world.tick as usize / 16)
                % mission.layout.len().div_ceil(mission.columns as usize);
            for gy in 0..7 {
                for gx in 0..mission.columns as usize {
                    let k = ((row + gy) * mission.columns as usize + gx) % mission.layout.len();
                    let tile = &mission.tiles[mission.layout[k] as usize];
                    let s = art_sprite_variant(catalog, &active.registry, owner, &tile.art, 0, hd)?;
                    let s = raptor_replica::terrain_hd::logical_sprite(&s, 32 * scale, 32 * scale)?;
                    c.blit(&s, (gx * 32 * scale) as i32, (gy * 32 * scale) as i32);
                }
            }
        }
        for e in &world.enemies {
            let def = &active.registry.enemies[&e.definition];
            if let Some(art) = &def.art {
                let owner = active
                    .registry
                    .owners
                    .get(&e.definition)
                    .map(String::as_str)
                    .unwrap_or("base");
                let s = art_sprite_variant(catalog, &active.registry, owner, art, 0, hd)?;
                let s = raptor_replica::terrain_hd::logical_sprite(
                    &s,
                    art.logical_width as usize * scale,
                    art.logical_height as usize * scale,
                )?;
                c.blit(&s, e.x * scale as i32, e.y * scale as i32);
            }
        }
        for p in &world.projectiles {
            if let Some(def) = active.registry.weapons.get(&p.weapon) {
                if let Some(art) = &def.art {
                    let owner = active
                        .registry
                        .owners
                        .get(&p.weapon)
                        .map(String::as_str)
                        .unwrap_or("base");
                    let s = art_sprite_variant(catalog, &active.registry, owner, art, 0, hd)?;
                    let s = raptor_replica::terrain_hd::logical_sprite(
                        &s,
                        art.logical_width as usize * scale,
                        art.logical_height as usize * scale,
                    )?;
                    c.blit(&s, p.x * scale as i32, p.y * scale as i32);
                }
            }
        }
        let player =
            catalog.sprite(catalog.id("LPLAYER_PIC")? + world.player.bank.clamp(0, 6) as u32)?;
        let player = render::nearest(&player, scale);
        c.blit(
            &player,
            world.player.x * scale as i32,
            world.player.y * scale as i32,
        );
        ppm(
            &out.join(format!("{label}-{}.ppm", if hd { "hd4" } else { "sd1" })),
            &c.image,
            &palette,
        )?;
    }
    Ok(())
}
fn bosses(base: &Registry, mods: &Path, catalog: &Catalog) -> Result<Value> {
    let mut rows = vec![];
    for n in [1, 2] {
        let owner = format!("iron_coast_stage2_boss_{n}");
        let unit = format!("{owner}:unit");
        let objective = format!("{owner}:defeated");
        let mut active = build(base, mods, &[owner.clone()], Some(catalog))?;
        let def = &active.registry.enemies[&id(&unit)];
        ensure!(def.ground && def.boss && def.legacy.is_none());
        active.registry.apply(serde_json::from_value::<ContentPack>(json!({"missions":[{"id":"base:stage2_boss_fixture","name":"Boss integration fixture","duration":6000,"auto_complete":false,"spawns":[{"tick":0,"enemy":unit,"x":96,"y":-80}]}]}))?,"base")?;
        let mut p = Pilot::default();
        p.mission = id("base:stage2_boss_fixture");
        p.inventory.insert(id("base:energy"), 75);
        let mut w = World::new(&p.mission, &p, &active.registry)?;
        let mut cues = BTreeSet::new();
        let mut minimum_health = i32::MAX;
        for _ in 0..2200 {
            w.step(input(&w, "", &unit), &active.registry, &mut active.scripts)?;
            for s in &w.mod_sounds {
                cues.insert(s.0.clone());
            }
            for e in &w.enemies {
                minimum_health = minimum_health.min(e.health);
            }
            if w.objectives.get(&objective) == Some(&1) {
                break;
            }
        }
        ensure!(
            w.objectives.get(&objective) == Some(&1),
            "boss{n} not killed {:?} tick{} health{}",
            w.outcome,
            w.tick,
            w.player.shield
        );
        ensure!(w.player.shield > 0);
        ensure!(cues.contains(&format!("{owner}:death")));
        let snapshot = active.scripts.checkpoints();
        let at = w.digest();
        w.step(Input::default(), &active.registry, &mut active.scripts)?;
        ensure!(w.objectives[&objective] == 1);
        rows.push(json!({"boss":unit,"tick":w.tick,"shield":w.player.shield,"minimum_observed_health":minimum_health,"cues":cues,"digest_before_extra_step":at,"serialized_script_state_bytes":serde_json::to_vec(&snapshot.0)?.len()}));
        // Duplicate dead callback cannot pay objective again; prior life cursor removed.
        active.scripts.begin_tick();
        let commands = active.scripts.invoke(
            &owner,
            "scripts/ai.rhai",
            "on_death",
            &json!({"entity":1,"x":96,"y":20,"entities":[],"objectives":{objective.clone():1}}),
            0,
        )?;
        ensure!(commands.is_empty());
        // A queued early-killed spawn must register exactly its death, never emit movement/sound.
        active.scripts.begin_tick();
        let event = json!({"entity":900,"x":96,"y":20,"entities":[],"objectives":{}});
        ensure!(
            active
                .scripts
                .invoke(&owner, "scripts/ai.rhai", "on_spawn", &event, 0)?
                .is_empty()
        );
        active.scripts.begin_tick();
        let commands = active
            .scripts
            .invoke(&owner, "scripts/ai.rhai", "on_death", &event, 0)?;
        ensure!(
            commands
                .iter()
                .any(|c| matches!(c,Command::Objective{key,value}if key==&objective&&*value==1))
        );
    }
    Ok(json!({"standalone_real_world_bosses":rows,"early_spawn_death_and_duplicate_death":true}))
}
fn missions(base: &Registry, mods: &Path, catalog: &Catalog, output: &Path) -> Result<Value> {
    let mut report = vec![];
    for n in [1, 2] {
        let owner = format!("iron_coast_stage2_mission_{n}");
        let boss = format!("iron_coast_stage2_boss_{n}");
        let required = format!(
            "iron_coast_stage2_{}",
            if n == 1 { "siege" } else { "skimmer" }
        );
        let mission = format!("{owner}:mission_0{n}");
        let enabled = vec![
            "iron_coast_stage2_music".into(),
            "iron_coast_stage2_interceptor".into(),
            required.clone(),
            boss.clone(),
            owner.clone(),
        ];
        let count = if n == 1 { 3 } else { 4 };
        let mut runs = vec![];
        for case in 0..7 {
            let difficulty = match case {
                4 => 0,
                5 => 1,
                6 => 3,
                _ => 2,
            };
            let full = case == 2;
            let purchased = case == 3;
            let mut case_enabled = enabled.clone();
            if purchased {
                case_enabled.extend([
                    "iron_coast_railburst".into(),
                    "iron_coast_depth_charge".into(),
                ]);
            }
            let mut active = build(base, mods, &case_enabled, Some(catalog))?;
            let mut p = Pilot::default();
            p.mission = id(&mission);
            p.difficulty = difficulty;
            let initial_shield = if case == 1 { 100 } else { 75 };
            p.inventory.insert(id("base:energy"), initial_shield);
            p.credits = if case == 1 { 0 } else { 10000 };
            if purchased {
                for weapon in [
                    "iron_coast_railburst:equipment",
                    "iron_coast_depth_charge:equipment",
                ] {
                    p.credits += active.registry.items[&id(weapon)].price;
                    p.buy(&id(weapon), &active.registry)?;
                }
                p.selected = Some(id(if n == 1 {
                    "iron_coast_railburst:equipment"
                } else {
                    "iron_coast_depth_charge:equipment"
                }));
            }
            let initial_credits = p.credits;
            if full {
                for (id, item) in &active.registry.items {
                    if p.inventory_slots() >= 20 {
                        break;
                    }
                    if item.legacy == Some(16) || item.legacy == Some(17) || item.consumable {
                        continue;
                    }
                    p.inventory.insert(id.clone(), item.initial_count);
                }
                ensure!(p.inventory_slots() == 20);
            }
            let inventory = p.inventory.clone();
            eprintln!(
                "mission{n}: case{case} difficulty{difficulty} full{full} purchased{purchased} starting"
            );
            let mut w = World::new(&p.mission, &p, &active.registry)?;
            let mut cues = BTreeSet::new();
            let mut native = BTreeMap::new();
            let mut moving = BTreeSet::new();
            let mut checkpoint = None;
            let mut captures = BTreeSet::new();
            for _ in 0..5000 {
                w.step(
                    input(&w, &(required.clone() + ":unit"), &(boss.clone() + ":unit")),
                    &active.registry,
                    &mut active.scripts,
                )?;
                for s in &w.mod_sounds {
                    cues.insert(s.0.clone());
                }
                for e in &w.enemies {
                    if e.definition.0.starts_with("base:enemy_") {
                        ensure!(active.registry.enemies[&e.definition].legacy.is_some());
                        let old = native.entry(e.entity).or_insert((e.x, e.y));
                        if *old != (e.x, e.y) {
                            moving.insert(e.definition.0.clone());
                        }
                    }
                }
                if case == 0 && [500, 1600, 2000, 2350, 2500].contains(&w.tick) {
                    capture(
                        catalog,
                        &active,
                        &w,
                        output,
                        &format!("mission{n}-tick{}", w.tick),
                    )?;
                    captures.insert(w.tick);
                }
                if w.tick == 1000 {
                    checkpoint = Some((w.clone(), active.scripts.checkpoints()));
                }
                if w.outcome != Outcome::Playing {
                    break;
                }
            }
            ensure!(
                w.outcome == Outcome::Complete,
                "mission{n} full{full} {:?} tick{} shield{} objectives{:?}",
                w.outcome,
                w.tick,
                w.player.shield,
                w.objectives
            );
            ensure!(
                w.objectives[&(required.clone() + ":defeated")] == count
                    && w.objectives[&(boss.clone() + ":defeated")] == 1
            );
            ensure!(w.objectives[&(owner.clone() + ":debrief")] == 1);
            ensure!(w.player.shield > 0);
            ensure!(moving.len() == 3, "all native classes observed moving");
            if full {
                for (item, count) in &inventory {
                    if item.0 != "base:energy" && item.0 != "base:super_shield" {
                        ensure!(
                            w.player.inventory.get(item) == Some(count),
                            "inventory preservation:{item}"
                        );
                    }
                }
            }
            if purchased {
                ensure!(
                    w.player
                        .inventory
                        .get(&id("iron_coast_railburst:equipment"))
                        == Some(&1)
                        && w.player
                            .inventory
                            .get(&id("iron_coast_depth_charge:equipment"))
                            == Some(&1),
                    "owned gear preserved"
                );
            }
            let final_tick = w.tick;
            let final_digest = w.digest();
            let final_scripts = serde_json::to_value(active.scripts.checkpoints())?;
            let earned = w.player.credits;
            w.step(Input::default(), &active.registry, &mut active.scripts)?;
            ensure!(w.player.credits == earned, "reward repeated");
            let (mut resumed, states) = checkpoint.unwrap();
            let mut resumed_active = build(base, mods, &case_enabled, Some(catalog))?;
            resumed_active
                .scripts
                .restore(serde_json::from_slice(&serde_json::to_vec(&states)?)?);
            while resumed.tick < final_tick {
                resumed.step(
                    input(
                        &resumed,
                        &(required.clone() + ":unit"),
                        &(boss.clone() + ":unit"),
                    ),
                    &resumed_active.registry,
                    &mut resumed_active.scripts,
                )?;
            }
            ensure!(
                resumed.digest() == final_digest
                    && serde_json::to_value(resumed_active.scripts.checkpoints())? == final_scripts,
                "state/RNG continuation deterministic"
            );
            // Restart reuses same script state but all mission goals/cursors must reset.
            let mut restart = World::new(&p.mission, &p, &active.registry)?;
            restart.step(Input::default(), &active.registry, &mut active.scripts)?;
            ensure!(
                restart.objectives[&(required.clone() + ":defeated")] == 0
                    && restart.objectives[&(boss.clone() + ":defeated")] == 0
                    && restart.objectives[&(owner.clone() + ":complete")] == 0
            );
            runs.push(json!({"difficulty":difficulty,"full20_inventory":full,"purchased_new_gear":purchased,"initial_shield":initial_shield,"initial_credits":initial_credits,"tick":final_tick,"shield":w.player.shield,"credits":earned,"credit_gain":earned-initial_credits,"objectives":w.objectives,"native_classes_moving":moving,"cues":cues,"captures":captures,"digest":final_digest,"serialized_state_rng_round_trip_identical":true,"replay_reset":true,"reward_once":true}));
            fs::write(
                output.join(format!("mission{n}-progress.json")),
                serde_json::to_vec_pretty(&runs)?,
            )?;
            eprintln!(
                "mission{n}: case{case} difficulty{difficulty} passed tick{final_tick} shield{} credits{earned}",
                w.player.shield
            );
        }
        // Authentic objective callback gating; no elapsed timeout can complete.
        let mut active = build(base, mods, &enabled, Some(catalog))?;
        let mut p = Pilot::default();
        p.mission = id(&mission);
        let mut w = World::new(&p.mission, &p, &active.registry)?;
        w.step(Input::default(), &active.registry, &mut active.scripts)?;
        w.objectives.insert(boss.clone() + ":defeated", 1);
        w.objectives
            .insert(required.clone() + ":defeated", count - 1);
        w.step(Input::default(), &active.registry, &mut active.scripts)?;
        ensure!(w.outcome == Outcome::Playing);
        w.objectives.insert(required.clone() + ":defeated", count);
        w.step(Input::default(), &active.registry, &mut active.scripts)?;
        ensure!(
            w.outcome == Outcome::Complete
                && w.player.credits == if n == 1 { 24000 } else { 32000 }
        );
        // This persistence-only fixture suppresses pilot death. It is separate
        // from every ordinary-loadout balance result above, which uses actual
        // purchased/registered health and unmodified gameplay damage.
        let mut late = World::new(&p.mission, &p, &active.registry)?;
        // Use the hardest difficulty for the persistence stress fixture.
        late.difficulty = 3;
        for _ in 0..5000 {
            // Normal original pickups can replace a shield value. Restore
            // this explicit fixture buffer each step, rather than treating
            // it as a persistent piece of gameplay equipment.
            late.player.shield = 10000;
            late.step(Input::default(), &active.registry, &mut active.scripts)?;
        }
        ensure!(
            late.outcome == Outcome::Playing,
            "late persistence fixture: {:?} tick{} shield{} objectives{:?}",
            late.outcome,
            late.tick,
            late.player.shield,
            late.objectives
        );
        let required_alive = late
            .enemies
            .iter()
            .filter(|e| {
                e.definition.0 == required.clone() + ":unit"
                    && e.health > 0
                    && e.y >= 0
                    && e.y < 140
            })
            .count();
        ensure!(
            required_alive == count as usize,
            "required convoys remain reachable"
        );
        ensure!(
            late.enemies
                .iter()
                .any(|e| { e.definition.0 == boss.clone() + ":unit" && e.health > 0 && e.y == 20 }),
            "boss must remain until actual death"
        );
        let definition = &active.registry.missions[&p.mission];
        let map_height = definition.layout.len() / definition.columns as usize * 32;
        ensure!(
            late.scroll as usize + 200 < map_height,
            "late fight has terrain coverage"
        );
        report.push(json!({"mission":mission,"enabled_packages":enabled,"required_deaths":count,"runs":runs,"missing_one_required_death_blocks_victory":true,"late_fight_fixture":{"tick":late.tick,"scroll":late.scroll,"reachable_required_units":required_alive,"boss_remains":true,"playing_beyond_declared_duration":true,"terrain_rows":map_height/32,"terrain_covered":true,"scope":"Persistence-only difficulty3 fixture restoring shield10000 before each step to suppress pilot death; ordinary balance runs above have no health/damage cheats."}}));
    }
    Ok(
        json!({"missions":report,"strategy":"Held Fire; mouseposition moves≤4 logicalpx/tick, y160, aim at required living convoy centers then boss then ordinary visible enemies. No damage/shield/credit cheats or loans.","capture_scope":"Actual PNG loader, native palette, World entity positions, Canvas.blit; simplified terrain row sampler/headless diagnostics, not liveSDL/Host capture."}),
    )
}

fn difficulty_phases(base: &Registry, mods: &Path, catalog: &Catalog) -> Result<Value> {
    let mut rows = vec![];
    for n in [1, 2] {
        for difficulty in 0..4 {
            let owner = format!("iron_coast_stage2_boss_{n}");
            let unit = format!("{owner}:unit");
            let mut active = build(base, mods, &[owner.clone()], Some(catalog))?;
            active.registry.apply(serde_json::from_value::<ContentPack>(json!({"missions":[{"id":"base:stage2_phase_fixture","name":"Phase fixture","duration":6000,"auto_complete":false,"spawns":[{"tick":0,"enemy":unit,"x":96,"y":-80}]}]}))?,"base")?;
            let mut p = Pilot::default();
            p.mission = id("base:stage2_phase_fixture");
            p.difficulty = difficulty;
            let mut w = World::new(&p.mission, &p, &active.registry)?;
            for _ in 0..70 {
                w.step(Input::default(), &active.registry, &mut active.scripts)?;
            }
            let e = w.enemies.first().unwrap();
            let key = e.entity.to_string();
            let maximum = e.health;
            let statekey = format!("{owner}/scripts/ai.rhai");
            ensure!(
                active.scripts.states[&statekey]["maximums"][&key] == maximum
                    && active.scripts.states[&statekey]["phases"][&key] == 1,
                "difficulty{difficulty} must start phase1"
            );
            w.enemies[0].health = maximum / 2 + 1;
            w.step(Input::default(), &active.registry, &mut active.scripts)?;
            ensure!(active.scripts.states[&statekey]["phases"][&key] == 1);
            w.enemies[0].health = maximum / 2;
            w.step(Input::default(), &active.registry, &mut active.scripts)?;
            ensure!(
                active.scripts.states[&statekey]["phases"][&key] == 2
                    && active.scripts.states[&statekey]["ages"][&key] == 1
            );
            rows.push(json!({"boss":unit,"difficulty":difficulty,"actual_spawn_max_health":maximum,"initial_phase":1,"half_health_phase":2,"phase_timer_reset":true}));
        }
    }
    Ok(
        json!({"all4_difficulties":rows,"fixture_scope":"Health boundary mutation tests only; ordinary boss/mission outcomes use unmodified damage gameplay."}),
    )
}
fn audio(
    base: &Registry,
    mods: &Path,
    catalog: &Catalog,
    enabled: &[String],
    output: &Path,
) -> Result<Value> {
    let active = build(base, mods, enabled, Some(catalog))?;
    let mut bank = sound::SoundBank::default();
    let mut rows = vec![];
    fs::create_dir_all(output)?;
    for (id, _) in &active.registry.sounds {
        if !id.0.starts_with("iron_coast_stage2_") {
            continue;
        }
        let mut mixer = raptor_replica::audio::Mixer::new(22050, &catalog.named("GENMIDI_OP2")?)?;
        mixer.fx_volume = 127;
        mixer.music_volume = 0;
        mixer.start_capture(2)?;
        bank.queue_mod(&active.registry, &mut mixer, id)?;
        let mut samples = vec![0i16; 22050 * 4];
        mixer.mix(&mut samples);
        let peak = samples.iter().map(|v| i32::from(*v).abs()).max().unwrap();
        ensure!(peak > 0, "audible cue:{id}");
        let capture = mixer.take_capture().unwrap();
        fs::write(
            output.join(format!("{}.wav", id.0.replace(':', "-"))),
            sound::encode_capture(&capture)?,
        )?;
        let mut muted = raptor_replica::audio::Mixer::new(22050, &catalog.named("GENMIDI_OP2")?)?;
        muted.fx_volume = 0;
        muted.music_volume = 0;
        bank.queue_mod(&active.registry, &mut muted, id)?;
        let mut quiet = vec![0i16; 22050 * 4];
        muted.mix(&mut quiet);
        ensure!(quiet.iter().all(|v| *v == 0), "mute:{id}");
        rows.push(json!({"sound":id,"mixed_peak":peak,"fx_mute_zero":true}));
    }
    Ok(
        json!({"mixer":"Native SoundBank/Mixer with original GENMIDI,2s PCM capture each cue; no live audio device claim","sounds":rows}),
    )
}

fn main() -> Result<()> {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../../..")
        .canonicalize()?;
    let catalog = Catalog::open(root.join("data"))?;
    let base = Registry::base(&catalog)?;
    let mods = root.join("mods");
    let output = root.join(".reference/iron-coast-stage2-authoring/runtime");
    fs::create_dir_all(&output)?;
    let only_boss = std::env::args().any(|s| s == "--boss-only");
    let mut report = json!({"bosses":bosses(&base,&mods,&catalog)?,"difficulty_phase_checks":difficulty_phases(&base,&mods,&catalog)?});
    if !only_boss {
        report["mission_acceptance"] = missions(&base, &mods, &catalog, &output)?;
        report["combined_audio"] = audio(
            &base,
            &mods,
            &catalog,
            &[
                "iron_coast_stage2_boss_1".into(),
                "iron_coast_stage2_boss_2".into(),
                "iron_coast_stage2_mission_1".into(),
                "iron_coast_stage2_mission_2".into(),
                "iron_coast_stage2_interceptor".into(),
                "iron_coast_stage2_siege".into(),
                "iron_coast_stage2_skimmer".into(),
                "iron_coast_stage2_music".into(),
            ],
            &output.join("audio"),
        )?;
    }
    report["boss_audio"] = audio(
        &base,
        &mods,
        &catalog,
        &[
            "iron_coast_stage2_boss_1".into(),
            "iron_coast_stage2_boss_2".into(),
        ],
        &output.join("audio"),
    )?;
    for n in [1, 2] {
        let owner = format!("iron_coast_stage2_boss_{n}");
        let active = build(&base, &mods, &[owner], Some(&catalog))?;
        for (id, s) in &active.registry.sounds {
            if id.0.starts_with("iron_coast_stage2_boss_") {
                let p = active
                    .registry
                    .asset_roots
                    .get(id.0.split_once(':').unwrap().0)
                    .unwrap()
                    .join(&s.file);
                let decoded = sound::decode(&fs::read(p)?)?;
                ensure!(!decoded.data.is_empty());
            }
        }
    }
    fs::write(
        output.join(if only_boss {
            "boss-acceptance.json"
        } else {
            "acceptance.json"
        }),
        serde_json::to_vec_pretty(&report)?,
    )?;
    println!("{}", serde_json::to_string_pretty(&report)?);
    Ok(())
}
