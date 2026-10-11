//! Real-catalog acceptance and indexed-art proof; never touches user profiles.
use raptor_replica::{
    assets::{Catalog, Sprite, TRANSPARENT},
    audio::Mixer,
    content::{ContentPack, Registry, art_sprite_variant},
    modding::{self, ActiveMods, Command},
    persistence::Pilot,
    simulation::{Input, Outcome, World},
    sound,
};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::{
    collections::{BTreeMap, BTreeSet},
    fs,
    path::{Path, PathBuf},
};

fn root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../..")
}
fn owner(n: u32, kind: &str) -> String {
    format!("iron_coast_stage2_{kind}_{n}")
}
fn sha(path: &Path) -> String {
    format!("{:x}", Sha256::digest(fs::read(path).unwrap()))
}
fn base(catalog: &Catalog) -> Registry {
    let mut registry = Registry::base(catalog).unwrap();
    let pack:ContentPack=serde_json::from_value(json!({"items":(0..20).map(|n|json!({"id":format!("fixture:filler_{n}"),"name":"Neutral full-slot fixture","price":0,"max_count":1})).collect::<Vec<_>>()})).unwrap();
    registry.apply(pack, "fixture").unwrap();
    registry.validate().unwrap();
    registry
}
fn active(n: u32, catalog: &Catalog) -> ActiveMods {
    let mut enabled = vec![
        owner(n, "mission"),
        owner(n, "boss"),
        "iron_coast_stage2_music".into(),
        "iron_coast_stage2_siege".into(),
    ];
    enabled.push(
        if n == 5 {
            "iron_coast_stage2_interceptor"
        } else {
            "iron_coast_stage2_skimmer"
        }
        .into(),
    );
    let discovery = modding::discover(&root().join("mods"));
    ActiveMods::build(&base(catalog), &discovery, &enabled, Some(catalog)).unwrap()
}
fn input(world: &World) -> Input {
    let desired = world
        .enemies
        .iter()
        .filter(|e| e.health > 0 && e.y >= 0)
        .max_by_key(|e| e.y)
        .map(|e| e.x + e.width / 2 - 16)
        .unwrap_or(144);
    Input {
        fire: true,
        absolute: Some([
            world.player.x + (desired - world.player.x).clamp(-4, 4),
            160,
        ]),
        ..Input::default()
    }
}
fn play(
    n: u32,
    active: &mut ActiveMods,
    shield: u32,
    credits: u32,
    difficulty: u32,
    full: bool,
) -> Value {
    active.scripts.restore(Default::default());
    let mut pilot = Pilot {
        credits,
        difficulty,
        ..Pilot::default()
    };
    pilot.inventory.insert("base:energy".into(), shield);
    if full {
        for i in 0..20 {
            if pilot.inventory_slots() >= 20 {
                break;
            }
            pilot
                .inventory
                .insert(format!("fixture:filler_{i}").as_str().into(), 1);
        }
    }
    let inventory = pilot.inventory.clone();
    let mission = owner(n, "mission");
    let boss = owner(n, "boss");
    let mut world = World::new(
        &format!("{mission}:mission_{n:02}").as_str().into(),
        &pilot,
        &active.registry,
    )
    .unwrap();
    let mut previous = BTreeMap::new();
    let mut moving = BTreeSet::new();
    let mut digests = Vec::new();
    let mut damage = 0;
    let mut sounds = 0;
    let mut max_enemies = 0;
    for _ in 0..5000 {
        let before = world.player.shield;
        world
            .step(input(&world), &active.registry, &mut active.scripts)
            .unwrap();
        damage += (before - world.player.shield).max(0);
        sounds += world.mod_sounds.len();
        max_enemies = max_enemies.max(world.enemies.len());
        for e in &world.enemies {
            if e.definition.0.starts_with("base:enemy_") {
                assert!(active.registry.enemies[&e.definition].legacy.is_some());
                if let Some(old) = previous.insert((e.definition.clone(), e.entity), (e.x, e.y)) {
                    if old != (e.x, e.y) {
                        moving.insert(e.definition.0.clone());
                    }
                }
            }
        }
        digests.push(world.digest());
        if world.outcome != Outcome::Playing {
            break;
        }
    }
    assert_eq!(
        world.outcome,
        Outcome::Complete,
        "mission{n} difficulty{difficulty}: tick{} shield{} objectives{:?}",
        world.tick,
        world.player.shield,
        world.objectives
    );
    assert!(
        (2300..=3500).contains(&world.tick),
        "completion pacing outside intended window: {}",
        world.tick
    );
    assert!(
        !moving.is_empty(),
        "native classic enemies must be observed moving"
    );
    assert_eq!(
        world.objectives[&format!("{mission}:targets_destroyed")],
        if n == 5 { 2 } else { 3 }
    );
    assert_eq!(world.objectives[&format!("{boss}:defeated")], 1);
    assert_eq!(world.objectives[&format!("{mission}:complete")], 1);
    assert_eq!(world.objectives[&format!("{mission}:debrief")], 1);
    for (id, count) in inventory {
        if id.0 != "base:energy" {
            assert_eq!(world.player.inventory.get(&id), Some(&count));
        }
    }
    let final_credits = world.player.credits;
    world
        .step(Input::default(), &active.registry, &mut active.scripts)
        .unwrap();
    assert_eq!(world.player.credits, final_credits);
    json!({"starting_shield":shield,"starting_credits":credits,"difficulty":difficulty,"full_20_slots":full,"tick":world.tick,
        "ending_shield":world.player.shield,"ending_credits":world.player.credits,"observed_damage":damage,"mod_sound_events":sounds,
        "max_enemies":max_enemies,"moving_native_definitions":moving,"objectives":world.objectives,"digest":world.digest(),
        "input_policy":"Forward guns only, always Fire, bottom y160, closest visible enemy aim with max4 horizontal pixels per tick",
        "step_digest_sha256":format!("{:x}",Sha256::digest(digests.join("\n")))})
}
fn preserved_full_slots(n: u32, active: &mut ActiveMods) {
    for reserves in [0, 4] {
        active.scripts.restore(Default::default());
        let mut pilot = Pilot::default();
        pilot.inventory.insert("base:energy".into(), 75);
        if reserves > 0 {
            pilot.inventory.insert("base:super_shield".into(), 100);
            pilot.super_shield_reserves = vec![100; reserves];
        }
        for i in 0..20 {
            if pilot.inventory_slots() >= 20 {
                break;
            }
            pilot
                .inventory
                .insert(format!("fixture:filler_{i}").as_str().into(), 1);
        }
        assert_eq!(pilot.inventory_slots(), 20);
        let mut world = World::new(
            &format!("{}:mission_{n:02}", owner(n, "mission"))
                .as_str()
                .into(),
            &pilot,
            &active.registry,
        )
        .unwrap();
        world
            .step(Input::default(), &active.registry, &mut active.scripts)
            .unwrap();
        assert_eq!(world.player.inventory, pilot.inventory);
        assert_eq!(
            world.player.super_shield_reserves,
            pilot.super_shield_reserves
        );
    }
}
fn reset_after_failure(n: u32, active: &mut ActiveMods) {
    active.scripts.restore(Default::default());
    let pilot = Pilot::default();
    let name = owner(n, "mission");
    for run in 0..2 {
        let mut world = World::new(
            &format!("{name}:mission_{n:02}").as_str().into(),
            &pilot,
            &active.registry,
        )
        .unwrap();
        world
            .step(Input::default(), &active.registry, &mut active.scripts)
            .unwrap();
        for suffix in [
            "targets_destroyed",
            "complete",
            "field_repair",
            "debrief",
            "hazard_lane",
        ] {
            assert_eq!(world.objectives[&format!("{name}:{suffix}")], 0);
        }
        if run == 0 {
            world
                .apply_commands(
                    &[Command::Damage {
                        entity: 0,
                        amount: 1000,
                    }],
                    &active.registry,
                )
                .unwrap();
            world
                .step(Input::default(), &active.registry, &mut active.scripts)
                .unwrap();
            assert_eq!(world.outcome, Outcome::Failed);
        }
    }
}
fn pending_targets(n: u32, active: &mut ActiveMods) -> Value {
    active.scripts.restore(Default::default());
    let mut pilot = Pilot::default();
    pilot.inventory.insert("base:super_shield".into(), 100);
    pilot.super_shield_reserves = vec![100; 8];
    let mut world = World::new(
        &format!("{}:mission_{n:02}", owner(n, "mission"))
            .as_str()
            .into(),
        &pilot,
        &active.registry,
    )
    .unwrap();
    for _ in 0..5700 {
        world
            .step(
                Input {
                    absolute: Some([0, 160]),
                    ..Input::default()
                },
                &active.registry,
                &mut active.scripts,
            )
            .unwrap();
    }
    assert_eq!(world.outcome, Outcome::Playing);
    let targets = world
        .enemies
        .iter()
        .filter(|e| e.definition.0 == format!("{}:target", owner(n, "mission")))
        .collect::<Vec<_>>();
    assert_eq!(targets.len(), if n == 5 { 2 } else { 3 });
    assert!(
        targets
            .iter()
            .all(|e| e.health > 0 && e.y == 28 && (0..288).contains(&e.x))
    );
    let boss = world
        .enemies
        .iter()
        .find(|e| e.definition.0 == format!("{}:unit", owner(n, "boss")))
        .unwrap();
    assert_eq!(boss.y, 24);
    json!({"tick":world.tick,"outcome":"playing","targets":targets.iter().map(|e|json!({"x":e.x,"y":e.y,"health":e.health})).collect::<Vec<_>>(),"boss":{"x":boss.x,"y":boss.y,"health":boss.health}})
}
fn rgba(sprite: &Sprite, palette: &[[u8; 3]; 256]) -> image::RgbaImage {
    let mut pixels = Vec::with_capacity(sprite.pixels.len() * 4);
    for index in &sprite.pixels {
        if *index == TRANSPARENT {
            pixels.extend([0, 0, 0, 0]);
        } else {
            pixels.extend([
                palette[*index as usize][0],
                palette[*index as usize][1],
                palette[*index as usize][2],
                255,
            ]);
        }
    }
    image::RgbaImage::from_raw(sprite.width as u32, sprite.height as u32, pixels).unwrap()
}
fn art_audio(n: u32, active: &ActiveMods, catalog: &Catalog, out: &Path) -> Value {
    let palette = catalog.palette().unwrap();
    let mut paths = Vec::new();
    let mut sound_checks = Vec::new();
    for kind in ["boss", "mission"] {
        let package = owner(n, kind);
        let dir = out.join(&package);
        fs::create_dir_all(&dir).unwrap();
        let id = if kind == "boss" {
            format!("{package}:unit")
        } else {
            format!("{package}:mission_{n:02}")
        };
        let art = active.registry.art(&id.as_str().into()).unwrap();
        for hd in [false, true] {
            let sprite =
                art_sprite_variant(catalog, &active.registry, &package, art, 0, hd).unwrap();
            let file = dir.join(if hd {
                "indexed-hd.png"
            } else {
                "indexed-sd.png"
            });
            rgba(&sprite, &palette).save(&file).unwrap();
            paths.push(json!({"file":file,"sha256":sha(&file),"width":sprite.width,"height":sprite.height,"reserved_indices":sprite.pixels.iter().filter(|p|(240..=255).contains(*p)).count()}));
        }
        if kind == "mission" {
            let m = &active.registry.missions[&id.as_str().into()];
            for hd in [false, true] {
                let size = if hd { 128 } else { 32 };
                let mut joined = image::RgbaImage::new(9 * size, 18 * size);
                for (i, tile) in m.tiles.iter().enumerate() {
                    let s =
                        art_sprite_variant(catalog, &active.registry, &package, &tile.art, 0, hd)
                            .unwrap();
                    image::imageops::replace(
                        &mut joined,
                        &rgba(&s, &palette),
                        (i % 9) as i64 * size as i64,
                        (i / 9) as i64 * size as i64,
                    );
                }
                let file = dir.join(if hd {
                    "terrain-indexed-hd.png"
                } else {
                    "terrain-indexed-sd.png"
                });
                joined.save(&file).unwrap();
                paths.push(json!({"file":file,"sha256":sha(&file),"unique_tiles":m.tiles.len(),"width":joined.width(),"height":joined.height()}));
            }
        }
        for (id, definition) in &active.registry.sounds {
            if active.registry.owners[id] == package {
                let path = active.registry.asset_roots[&package].join(&definition.file);
                let sample = sound::decode(&fs::read(&path).unwrap()).unwrap();
                let mut mixer = Mixer::new(48000, &catalog.named("GENMIDI_OP2").unwrap()).unwrap();
                mixer.music_volume = 0;
                mixer.sample(
                    sample,
                    128,
                    128,
                    definition.volume as i32,
                    definition.priority as i32,
                );
                let mut buffer = vec![0_i16; 48000 * 2];
                mixer.mix(&mut buffer);
                let nonzero = buffer.iter().filter(|p| **p != 0).count();
                assert!(nonzero > 32);
                let peak = buffer.iter().map(|s| s.unsigned_abs()).max().unwrap();
                assert!(peak < 32767);
                sound_checks.push(json!({"id":id,"wav_sha256":sha(&path),"nonzero_stereo_samples":nonzero,"mixer_peak":peak}));
            }
        }
    }
    json!({"actual_indexed_outputs":paths,"actual_mixer_cues":sound_checks,"renderer":"Current Rust art_sprite_variant/Sprite::png, original ordinary palette, no inferred SDL live-scene coverage"})
}
fn main() {
    let catalog = Catalog::open(root().join("data")).unwrap();
    let out = root().join(".reference/iron-coast-stage2-56-acceptance");
    fs::create_dir_all(&out).unwrap();
    let only_art = std::env::args().any(|a| a == "--art-only");
    let mut reports = Vec::new();
    for n in [5, 6] {
        let mut active = active(n, &catalog);
        let visual = art_audio(n, &active, &catalog, &out);
        if only_art {
            reports.push(json!({"mission":n,"visual_audio":visual}));
            continue;
        }
        preserved_full_slots(n, &mut active);
        reset_after_failure(n, &mut active);
        let mut runs = Vec::new();
        for (shield, credits, difficulty, full) in [
            (75, 10000, 2, false),
            (100, 0, 2, true),
            (75, 10000, 0, false),
            (75, 10000, 1, false),
            (100, 0, 3, false),
        ] {
            runs.push(play(n, &mut active, shield, credits, difficulty, full));
        }
        let repeated = play(n, &mut active, 75, 10000, 2, false);
        assert_eq!(
            runs[0]["step_digest_sha256"],
            repeated["step_digest_sha256"]
        );
        assert_eq!(runs[0]["digest"], repeated["digest"]);
        let pending = pending_targets(n, &mut active);
        reports.push(json!({"mission":n,"runs":runs,"exact_replay":true,"full20_plus4_reserves_preserved":true,"failed_attempt_restart_reset":true,"mandatory_targets_after_duration":pending,"visual_audio":visual,"pins":active.pins}));
    }
    let path = out.join(if only_art {
        "visual-audio.json"
    } else {
        "acceptance.json"
    });
    fs::write(&path, serde_json::to_vec_pretty(&reports).unwrap()).unwrap();
    println!("{}", path.display());
}
