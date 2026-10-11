//! Original-catalog standalone mission acceptance. Starter guns only; no package/pilot changes.
use raptor_replica::{
    assets::{Catalog, Sprite, TRANSPARENT},
    audio::Mixer,
    content::{self, ContentPack, Registry},
    modding::{self, ActiveMods, ScriptRuntime},
    persistence::Pilot,
    render::{Canvas, draw_world_lightning_arcs, nearest},
    simulation::{Input, Outcome, World},
    sound::SoundBank,
};
use serde_json::json;
use std::{
    collections::{BTreeMap, BTreeSet},
    io::Write,
    path::{Path, PathBuf},
};
fn namespaces(stage: u32) -> (String, String) {
    (
        format!("iron_coast_stage2_mission_{stage}"),
        format!("iron_coast_stage2_boss_{stage}"),
    )
}
fn active(root: &Path, stage: u32) -> ActiveMods {
    let catalog = Catalog::open(root.join("data")).unwrap();
    let base = Registry::base(&catalog).unwrap();
    let (owner, boss) = namespaces(stage);
    let ids = vec![
        owner,
        boss,
        "iron_coast_stage2_interceptor".into(),
        if stage == 3 {
            "iron_coast_stage2_siege".into()
        } else {
            "iron_coast_stage2_skimmer".into()
        },
        "iron_coast_stage2_music".into(),
    ];
    let discovery = modding::discover(&root.join("mods"));
    let active = ActiveMods::build(&base, &discovery, &ids, Some(&catalog)).unwrap();
    assert_eq!(active.pins.len(), 5);
    active
}
fn pilot(stage: u32, shield: u32, credits: u32, difficulty: u32) -> Pilot {
    let mut pilot = Pilot::default();
    pilot.mission = format!("iron_coast_stage2_mission_{stage}:mission_0{stage}")
        .as_str()
        .into();
    pilot.difficulty = difficulty;
    pilot.credits = credits;
    pilot.inventory.insert("base:energy".into(), shield);
    pilot
}
fn input(world: &World, registry: &Registry) -> Input {
    let prefix = format!("{}:", world.mission.0.split_once(':').unwrap().0);
    let target = world
        .enemies
        .iter()
        .filter(|e| e.health > 0 && e.y >= 0 && e.y < 145)
        .min_by_key(|e| {
            let def = &registry.enemies[&e.definition];
            (
                if e.definition.0.starts_with(&prefix) {
                    0
                } else if def.boss {
                    1
                } else if def.ground {
                    2
                } else {
                    3
                },
                e.entity,
            )
        });
    let goal = target
        .map(|e| e.x + e.width / 2 - 16)
        .unwrap_or(144)
        .clamp(5, 282);
    Input {
        fire: true,
        absolute: Some([world.player.x + (goal - world.player.x).clamp(-4, 4), 160]),
        ..Input::default()
    }
}
fn observe(
    world: &World,
    seen: &mut BTreeSet<String>,
    moving: &mut BTreeSet<String>,
    positions: &mut BTreeMap<u64, (i32, i32)>,
) {
    for e in &world.enemies {
        if e.definition.0.starts_with("base:enemy_") {
            seen.insert(e.definition.0.clone());
            if let Some(prior) = positions.insert(e.entity, (e.x, e.y)) {
                if prior != (e.x, e.y) {
                    moving.insert(e.definition.0.clone());
                }
            }
        }
    }
}
fn restored_runtime(root: &Path, active: &ActiveMods) -> ScriptRuntime {
    let discovery = modding::discover(&root.join("mods"));
    let mut result = ScriptRuntime::new();
    for pin in &active.pins {
        let package = &discovery.mods[&pin.id];
        for script in &package.manifest.scripts {
            result
                .add(
                    &pin.id,
                    script,
                    &std::fs::read_to_string(package.root.join(script)).unwrap(),
                )
                .unwrap();
        }
    }
    result.restore(active.scripts.checkpoints());
    result
}
fn fit(sprite: &Sprite, width: usize, height: usize) -> Sprite {
    let mut out = Sprite::blank(width, height);
    for y in 0..height {
        for x in 0..width {
            out.pixels[y * width + x] = sprite.pixels
                [(y * sprite.height / height) * sprite.width + x * sprite.width / width];
        }
    }
    out
}
fn load(
    catalog: &Catalog,
    registry: &Registry,
    id: &str,
    art: &content::Art,
    frame: u32,
    hd: bool,
    scale: usize,
) -> Sprite {
    let owner = &registry.owners[&id.into()];
    let raw = content::art_sprite_variant(catalog, registry, owner, art, frame, hd).unwrap();
    let result = fit(
        &raw,
        art.logical_width as usize * scale,
        art.logical_height as usize * scale,
    );
    assert!(
        result
            .pixels
            .iter()
            .all(|p| *p < 240 || *p == TRANSPARENT || art.asset.is_some())
    );
    result
}
fn ppm(path: &Path, canvas: &Canvas, palette: &[[u8; 3]; 256]) {
    let mut file = std::fs::File::create(path).unwrap();
    write!(
        file,
        "P6\n{} {}\n255\n",
        canvas.image.width, canvas.image.height
    )
    .unwrap();
    for p in &canvas.image.pixels {
        let rgb = if *p == TRANSPARENT {
            [0, 0, 0]
        } else {
            palette[*p as usize]
        };
        file.write_all(&rgb).unwrap();
    }
}
fn capture(root: &Path, stage: u32, world: &World, registry: &Registry) {
    let catalog = Catalog::open(root.join("data")).unwrap();
    let palette = catalog.palette().unwrap();
    let mission = &registry.missions[&world.mission];
    let rows = mission.layout.len() / mission.columns as usize;
    let offset = 200 - rows as i32 * 32 + world.scroll;
    let out = root
        .parent()
        .unwrap()
        .join(".reference/iron-coast-3-stage2/captures");
    std::fs::create_dir_all(&out).unwrap();
    for (name, scale, hd) in [("sd", 1, false), ("hd", 4, true)] {
        let mut canvas = Canvas::new(scale);
        canvas.clear(0);
        for (row, tiles) in mission.layout.chunks(mission.columns as usize).enumerate() {
            let y = offset + row as i32 * 32;
            if y <= -32 || y >= 200 {
                continue;
            }
            for (col, index) in tiles.iter().enumerate() {
                let tile = &mission.tiles[*index];
                let sprite = load(
                    &catalog,
                    registry,
                    &world.mission.0,
                    &tile.art,
                    0,
                    hd,
                    scale,
                );
                canvas.blit(
                    &sprite,
                    (16 + col as i32 * 32) * scale as i32,
                    y * scale as i32,
                );
            }
        }
        for ground in [true, false] {
            for enemy in &world.enemies {
                let def = &registry.enemies[&enemy.definition];
                if def.ground != ground || enemy.health <= 0 {
                    continue;
                }
                if let Some(art) = &def.art {
                    let sprite = load(
                        &catalog,
                        registry,
                        &enemy.definition.0,
                        art,
                        enemy.art_frame,
                        hd,
                        scale,
                    );
                    canvas.blit(&sprite, enemy.x * scale as i32, enemy.y * scale as i32);
                }
            }
        }
        for shot in &world.projectiles {
            if let Some(art) = registry.weapons[&shot.weapon].art.as_ref() {
                let sprite = load(&catalog, registry, &shot.weapon.0, art, shot.age, hd, scale);
                canvas.blit(&sprite, shot.x * scale as i32, shot.y * scale as i32);
            }
        }
        let player = catalog
            .sprite(catalog.id("LPLAYER_PIC").unwrap() + world.player.bank as u32)
            .unwrap();
        canvas.blit(
            &nearest(&player, scale),
            world.player.x * scale as i32,
            world.player.y * scale as i32,
        );
        draw_world_lightning_arcs(&mut canvas, world, &palette, 1.0);
        ppm(
            &out.join(format!("stage{stage}-tick{}-{name}.ppm", world.tick)),
            &canvas,
            &palette,
        );
    }
}
fn main() {
    let root = PathBuf::from(std::env::args().nth(1).expect("pass RustRaptor root"));
    let stage: u32 = std::env::args().nth(2).unwrap().parse().unwrap();
    let (owner, boss) = namespaces(stage);
    let mission = format!("{owner}:mission_0{stage}");
    let target = format!("{owner}:target");
    let target_counter = format!("{owner}:targets_destroyed");
    let boss_counter = format!("{boss}:defeated");
    let bonus = if stage == 3 { 14500 } else { 16500 };
    let arrival = if stage == 3 { 2100 } else { 2250 };
    let mut active = active(&root, stage);
    let mut reports = vec![];
    // The exact shared dependencies have real scripts/artwork/music, no fixture replacements.
    for (shield, credits, difficulty) in [
        (75, 10_000, 0),
        (75, 10_000, 1),
        (75, 10_000, 2),
        (75, 10_000, 3),
        (100, 0, 2),
    ] {
        let pilot = pilot(stage, shield, credits, difficulty);
        let mut world = World::new(&mission.as_str().into(), &pilot, &active.registry).unwrap();
        let mut seen = BTreeSet::new();
        let mut moving = BTreeSet::new();
        let mut positions = BTreeMap::new();
        let mut min_shield = shield as i32;
        let mut sounds = BTreeSet::new();
        let mut continuation = None;
        let mut detail_captures = BTreeSet::new();
        for _ in 0..4500 {
            let commands = input(&world, &active.registry);
            world
                .step(commands, &active.registry, &mut active.scripts)
                .unwrap();
            min_shield = min_shield.min(world.player.shield);
            observe(&world, &mut seen, &mut moving, &mut positions);
            sounds.extend(world.mod_sounds.iter().map(|s| s.0.clone()));
            if difficulty == 2
                && shield == 75
                && [300, 1200, arrival + 75, arrival + 120].contains(&world.tick)
            {
                capture(&root, stage, &world, &active.registry);
            }
            if difficulty == 2 && shield == 75 {
                let phase = world
                    .objectives
                    .get(&format!("{boss}:phase"))
                    .copied()
                    .unwrap_or(0);
                for cue in ["warning", "shot"] {
                    if world
                        .mod_sounds
                        .iter()
                        .any(|s| s.0 == format!("{boss}:{cue}"))
                        && detail_captures.insert(format!("{cue}-{phase}"))
                    {
                        capture(&root, stage, &world, &active.registry);
                    }
                }
            }
            if world.tick == 1200 {
                continuation = Some((world.clone(), restored_runtime(&root, &active)));
            } else if let Some((ref mut other, ref mut scripts)) = continuation {
                other.step(commands, &active.registry, scripts).unwrap();
                assert_eq!(world.digest(), other.digest());
                assert_eq!(world.objectives, other.objectives);
                assert_eq!(active.scripts.checkpoints(), scripts.checkpoints());
            }
            if world.outcome != Outcome::Playing {
                break;
            }
        }
        assert_eq!(
            world.outcome,
            Outcome::Complete,
            "difficulty{difficulty} tick{} shield{} {:?}",
            world.tick,
            world.player.shield,
            world.objectives
        );
        assert!(world.tick >= arrival && world.tick <= 3300);
        assert_eq!(world.objectives[&target_counter], 4);
        assert_eq!(world.objectives[&boss_counter], 1);
        assert_eq!(world.objectives[&format!("{owner}:complete")], 1);
        assert_eq!(world.objectives[&format!("{owner}:debrief")], 1);
        assert!(!seen.is_empty());
        assert_eq!(
            seen, moving,
            "all genuine classic definitions must be observed moving"
        );
        assert!(sounds.contains(&format!("{owner}:victory")));
        assert!(sounds.contains(&format!("{boss}:warning")));
        let end = world.player.credits;
        world
            .step(Input::default(), &active.registry, &mut active.scripts)
            .unwrap();
        assert_eq!(world.player.credits, end);
        reports.push(json!({"initial_shield":shield,"initial_credits":credits,"difficulty":difficulty,"tick":world.tick,"shield":world.player.shield,"minimum_shield":min_shield,"credits":end,"native_seen_and_moving":seen,"objectives":world.objectives,"mod_sound_cues":sounds}));
        println!(
            "stage{stage} difficulty{difficulty} initial{shield}/{credits}: win tick{} shield{} min{min_shield} credits{end}",
            world.tick, world.player.shield
        );
    }
    // Deliberately refrain from shooting. Health controlled ONLY to inspect survivors after duration.
    let mut held = World::new(
        &mission.as_str().into(),
        &pilot(stage, 75, 10_000, 2),
        &active.registry,
    )
    .unwrap();
    for _ in 0..4500 {
        held.player.shield = 100;
        held.step(
            Input {
                absolute: Some([5, 160]),
                ..Input::default()
            },
            &active.registry,
            &mut active.scripts,
        )
        .unwrap();
        if held.tick == 1800 {
            capture(&root, stage, &held, &active.registry);
        }
    }
    assert_eq!(held.outcome, Outcome::Playing);
    let targets = held
        .enemies
        .iter()
        .filter(|e| e.definition.0 == target && e.health > 0)
        .collect::<Vec<_>>();
    assert_eq!(targets.len(), 4);
    assert!(
        targets
            .iter()
            .all(|e| e.y == 60 && e.x >= 16 && e.x + e.width <= 304)
    );
    let bosses = held
        .enemies
        .iter()
        .filter(|e| e.definition.0 == format!("{boss}:unit") && e.health > 0)
        .collect::<Vec<_>>();
    assert_eq!(bosses.len(), 1);
    assert_eq!(bosses[0].y, 24);
    assert_eq!(held.objectives[&target_counter], 0);
    assert_eq!(held.objectives[&boss_counter], 0);
    // Mission start resets stale state; a full inventory has 18 unarmed synthetic test items.
    let items = (0..18)
        .map(|n| json!({"id":format!("fixture:slot_{n}"),"name":format!("Slot{n}"),"price":0}))
        .collect::<Vec<_>>();
    let pack: ContentPack = serde_json::from_value(json!({"items":items})).unwrap();
    active.registry.apply(pack, "fixture").unwrap();
    let mut full = pilot(stage, 75, 10_000, 2);
    for n in 0..18 {
        full.inventory
            .insert(format!("fixture:slot_{n}").as_str().into(), 1);
    }
    assert_eq!(full.inventory_slots(), 20);
    let before = full.inventory.clone();
    let mut flight = World::new(&mission.as_str().into(), &full, &active.registry).unwrap();
    flight
        .step(Input::default(), &active.registry, &mut active.scripts)
        .unwrap();
    assert_eq!(flight.player.inventory, before);
    assert_eq!(flight.objectives[&target_counter], 0);
    assert_eq!(flight.objectives[&boss_counter], 0);
    for _ in 0..4500 {
        flight
            .step(
                input(&flight, &active.registry),
                &active.registry,
                &mut active.scripts,
            )
            .unwrap();
        if flight.outcome != Outcome::Playing {
            break;
        }
    }
    assert_eq!(flight.outcome, Outcome::Complete);
    assert_eq!(flight.player.inventory.len(), 20);
    for (id, count) in before {
        if id.0 != "base:energy" {
            assert_eq!(flight.player.inventory.get(&id), Some(&count));
        }
    }
    let full_report = json!({"slots":20,"tick":flight.tick,"shield":flight.player.shield,"credits":flight.player.credits,"equipment_preserved":true});
    // Controlled callback gating: boss alone, then only3targets cannot complete; time cannot bypass.
    let mut gate = World::new(&mission.as_str().into(), &full, &active.registry).unwrap();
    gate.step(Input::default(), &active.registry, &mut active.scripts)
        .unwrap();
    gate.tick = arrival + 200;
    gate.spawn_cursor = active.registry.missions[&mission.as_str().into()]
        .spawns
        .len();
    gate.objectives.insert(boss_counter.clone(), 1);
    gate.objectives.insert(target_counter.clone(), 3);
    gate.step(Input::default(), &active.registry, &mut active.scripts)
        .unwrap();
    assert_eq!(gate.outcome, Outcome::Playing);
    assert_eq!(gate.player.credits, 10_000);
    gate.objectives.insert(target_counter.clone(), 4);
    gate.step(Input::default(), &active.registry, &mut active.scripts)
        .unwrap();
    assert_eq!(gate.outcome, Outcome::Complete);
    assert_eq!(gate.player.credits, 10_000 + bonus);
    gate.step(Input::default(), &active.registry, &mut active.scripts)
        .unwrap();
    assert_eq!(gate.player.credits, 10_000 + bonus);
    // Real resolver+native mixer for every authored cue; bounded unsigned decoded PCM and stereo output.
    let catalog = Catalog::open(root.join("data")).unwrap();
    let instruments = catalog.named("GENMIDI_OP2").unwrap();
    let mut bank = SoundBank::default();
    let mut audio = vec![];
    for (id, definition) in &active.registry.sounds {
        if !id.0.starts_with(&owner) && !id.0.starts_with(&boss) {
            continue;
        }
        let sample = bank.mod_sample(&active.registry, id).unwrap();
        assert_eq!(sample.rate, 22050);
        assert!(sample.data.iter().any(|s| *s != 128));
        let mut mixer = Mixer::new(44100, &instruments).unwrap();
        mixer.fx_volume = 127;
        bank.queue_mod(&active.registry, &mut mixer, id).unwrap();
        let mut pcm = vec![0; 44100 * 2];
        mixer.mix(&mut pcm);
        assert!(pcm.iter().any(|v| *v != 0));
        let peak = pcm.iter().map(|v| (*v as i32).abs()).max().unwrap();
        assert!(peak < 32767);
        audio.push(json!({"id":id.0,"file":definition.file,"decoded_samples":sample.data.len(),"mixed_stereo_peak":peak}));
    }
    let report = json!({"mission":mission,"playthroughs":reports,"full_inventory":full_report,"retention":{"tick":4500,"targets":4,"boss":1,"outcome":"playing","shield_controlled_only_here":true},"deterministic_resume_from_tick":1200,"gated_completion_and_once_bonus":true,"audio":audio,"capture_scope":"actual Rust PNG palette conversion and indexed Canvas from real World states; desktop Host live screenshots handled independently"});
    std::fs::write(
        root.join("mods")
            .join(owner)
            .join("validation/acceptance.json"),
        serde_json::to_string_pretty(&report).unwrap() + "\n",
    )
    .unwrap();
    println!(
        "retention4500/restart/full20/once-bonus/deterministic saved state+RNG/mixed WAVs: passed"
    );
}
