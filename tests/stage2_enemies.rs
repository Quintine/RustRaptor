//! Three independent Stage 2 shared enemy packages; synthetic asset tests run everywhere.
use raptor_replica::{
    content::{ContentId, ContentPack, Registry},
    modding::{self, ActiveMods, Command},
    persistence::Pilot,
    simulation::{Input, World},
};
use serde_json::json;
use std::{fs, path::Path};
const IDS: [&str; 3] = [
    "iron_coast_stage2_interceptor",
    "iron_coast_stage2_siege",
    "iron_coast_stage2_skimmer",
];
fn base() -> Registry {
    let mut r = Registry::default();
    let p:ContentPack=serde_json::from_value(json!({"weapons":[
        {"id":"base:projectile_forward_guns","name":"Guns","damage":1,"speed":8,"cooldown":2,"behavior":"straight","target":"all"},
        {"id":"base:air_probe","name":"Air probe","damage":5,"speed":0,"cooldown":1,"behavior":"straight","target":"air"},
        {"id":"base:ground_probe","name":"Ground probe","damage":5,"speed":0,"cooldown":1,"behavior":"straight","target":"ground"}],
        "items":[{"id":"base:forward_guns","name":"Guns","price":0,"weapon":"base:projectile_forward_guns"},{"id":"base:energy","name":"Shield","price":0,"max_count":100}],
        "missions":[{"id":"base:sector_1_wave_1","name":"Synthetic shared enemies range","duration":10000,"auto_complete":false}]})).unwrap();
    r.apply(p, "base").unwrap();
    r.validate().unwrap();
    r
}
fn fixture(parent: &Path, id: &str) {
    let source = Path::new(env!("CARGO_MANIFEST_DIR")).join("mods").join(id);
    let dest = parent.join(id);
    for sub in ["scripts", "art", "audio"] {
        fs::create_dir_all(dest.join(sub)).unwrap();
    }
    for file in ["mod.toml", "content.json", "scripts/ai.rhai"] {
        fs::copy(source.join(file), dest.join(file)).unwrap();
    }
    if source.join("scripts/gun.rhai").exists() {
        fs::copy(
            source.join("scripts/gun.rhai"),
            dest.join("scripts/gun.rhai"),
        )
        .unwrap();
    }
    let content: ContentPack =
        serde_json::from_slice(&fs::read(source.join("content.json")).unwrap()).unwrap();
    for a in content
        .enemies
        .iter()
        .filter_map(|d| d.art.as_ref())
        .chain(content.weapons.iter().filter_map(|d| d.art.as_ref()))
    {
        for (path, scale) in [
            (a.png.as_ref().unwrap(), 1),
            (a.hd_png.as_ref().unwrap(), 2),
        ] {
            let mut im =
                image::RgbaImage::new(a.logical_width * a.frames * scale, a.logical_height * scale);
            for frame in 0..a.frames {
                for y in scale..(a.logical_height - 1) * scale {
                    for x in scale..(a.logical_width - 1) * scale {
                        im.put_pixel(
                            frame * a.logical_width * scale + x,
                            y,
                            image::Rgba([94, 105, 113, 255]),
                        );
                    }
                }
            }
            im.save(dest.join(path)).unwrap();
        }
    }
    let mut wav = b"RIFF".to_vec();
    wav.extend(40_u32.to_le_bytes());
    wav.extend(b"WAVEfmt ");
    wav.extend(16_u32.to_le_bytes());
    wav.extend(1_u16.to_le_bytes());
    wav.extend(1_u16.to_le_bytes());
    wav.extend(22050_u32.to_le_bytes());
    wav.extend(44100_u32.to_le_bytes());
    wav.extend(2_u16.to_le_bytes());
    wav.extend(16_u16.to_le_bytes());
    wav.extend(b"data");
    wav.extend(4_u32.to_le_bytes());
    wav.extend([0; 4]);
    for s in content.sounds {
        fs::write(dest.join(s.file), &wav).unwrap();
    }
}
fn active(ids: &[&str]) -> (tempfile::TempDir, ActiveMods) {
    let temp = tempfile::tempdir().unwrap();
    for id in ids {
        fixture(temp.path(), id);
    }
    let discovery = modding::discover(temp.path());
    assert!(discovery.errors.is_empty(), "{:?}", discovery.errors);
    let a = ActiveMods::build(
        &base(),
        &discovery,
        &ids.iter().map(|s| s.to_string()).collect::<Vec<_>>(),
        None,
    )
    .unwrap();
    (temp, a)
}
fn world(a: &ActiveMods) -> World {
    let mut p = Pilot::default();
    p.credits = 0;
    let mut w = World::new(&p.mission, &p, &a.registry).unwrap();
    w.player.shield = 100;
    w
}
fn spawn(w: &mut World, a: &ActiveMods, id: &str, x: i32, y: i32) -> u64 {
    w.spawn(
        &ContentId::new(format!("{id}:unit")).unwrap(),
        x,
        y,
        &a.registry,
    )
    .unwrap()
}
#[test]
fn stage2_packages_activate_independently_and_coexist_with_stage1() {
    for id in IDS {
        let (_t, a) = active(&[id]);
        assert_eq!(a.pins.len(), 1);
        assert_eq!(a.registry.enemies.len(), 1);
        assert_eq!(a.registry.sounds.len(), 3);
        assert_eq!(a.registry.weapons.len(), 5);
        assert!(a.registry.overrides.is_empty());
    }
    let (_t, a) = active(&[
        IDS[0],
        IDS[1],
        IDS[2],
        "iron_coast_scout",
        "iron_coast_turret",
        "iron_coast_boss",
    ]);
    assert_eq!(a.pins.len(), 6);
    assert_eq!(a.registry.enemies.len(), 6);
    assert!(a.registry.overrides.is_empty());
}
#[test]
fn stage2_engine_cooldowns_produce_finite_bursts_and_warnings() {
    for (idx, id) in IDS.iter().enumerate() {
        let (_t, mut a) = active(&[*id]);
        let mut w = world(&a);
        w.player.x = 240;
        spawn(&mut w, &a, id, 100, 0);
        let mut shots = Vec::new();
        let mut warnings = Vec::new();
        for tick in 0..200 {
            let e = &mut w.enemies[0];
            e.x = 100;
            e.y = 0;
            w.step(Input::default(), &a.registry, &mut a.scripts)
                .unwrap();
            let new = w
                .projectiles
                .iter()
                .filter(|p| p.age == 0)
                .collect::<Vec<_>>();
            if !new.is_empty() {
                assert!(new.iter().all(|p| p.hostile
                    && p.weapon.0 == format!("{id}:projectile")
                    && p.vy >= 1
                    && p.vx.abs() <= 3));
                shots.push((tick, new.len()));
            }
            if w.mod_sounds.iter().any(|s| s.0 == format!("{id}:warning")) {
                warnings.push(tick);
            }
            assert_eq!(w.enemies.len(), 1, "AI must never spawn extra enemies");
            assert!(w.projectiles.len() < 32);
        }
        let expected = match idx {
            0 => vec![
                (1, 1),
                (5, 1),
                (9, 1),
                (71, 1),
                (75, 1),
                (79, 1),
                (141, 1),
                (145, 1),
                (149, 1),
            ],
            1 => vec![(10, 2), (97, 2), (184, 2)],
            _ => vec![(6, 2), (88, 2), (170, 2)],
        };
        assert_eq!(shots, expected, "{id}");
        assert_eq!(
            warnings,
            match idx {
                0 => vec![],
                1 => vec![0, 87, 174],
                _ => vec![0, 82, 164],
            },
            "{id}"
        );
    }
}
#[test]
fn stage2_movement_has_distinct_bounded_patterns_and_units_escape_without_rewards() {
    for (idx, id) in IDS.iter().enumerate() {
        let (_t, mut a) = active(&[*id]);
        let mut w = world(&a);
        w.player.x = 0;
        spawn(&mut w, &a, id, 150, -24);
        let mut left = false;
        let mut right = false;
        let mut stopped = false;
        for _ in 0..400 {
            w.step(Input::default(), &a.registry, &mut a.scripts)
                .unwrap();
            if w.enemies.is_empty() {
                break;
            }
            let e = &w.enemies[0];
            left |= e.vx < 0;
            right |= e.vx > 0;
            stopped |= e.vx == 0;
            assert!(e.x >= 6 && e.x + e.width <= 314);
            assert!((1..=2).contains(&e.vy));
        }
        assert!(w.enemies.is_empty(), "{id} should leave naturally");
        assert_eq!(w.player.credits, 0);
        assert!(!w.objectives.contains_key(&format!("{id}:defeated")));
        if idx != 1 {
            assert!(left && right, "{id} must weave in both directions");
        } else {
            assert!(stopped && (left || right));
        }
    }
}
#[test]
fn stage2_air_ground_filtering_and_siege_damage_disable_second_shell() {
    for (idx, id) in IDS.iter().enumerate() {
        for ground in [false, true] {
            let (_t, mut a) = active(&[*id]);
            let mut w = world(&a);
            spawn(&mut w, &a, id, 120, 40);
            let initial = w.enemies[0].health;
            w.apply_commands(
                &[Command::Projectile {
                    weapon: if ground {
                        "base:ground_probe"
                    } else {
                        "base:air_probe"
                    }
                    .into(),
                    x: 128,
                    y: 48,
                    vx: 0,
                    vy: 0,
                    hostile: false,
                }],
                &a.registry,
            )
            .unwrap();
            w.step(Input::default(), &a.registry, &mut a.scripts)
                .unwrap();
            assert_eq!(
                w.enemies[0].health,
                initial - if ground == (idx != 0) { 5 } else { 0 },
                "{id} ground={ground}"
            );
        }
    }
    let (_t, mut a) = active(&[IDS[1]]);
    let mut w = world(&a);
    spawn(&mut w, &a, IDS[1], 120, 0);
    w.enemies[0].health = 24;
    for tick in 0..=10 {
        w.enemies[0].y = 0;
        w.step(Input::default(), &a.registry, &mut a.scripts)
            .unwrap();
        if tick == 10 {
            assert_eq!(w.projectiles.iter().filter(|p| p.age == 0).count(), 1);
        }
    }
}
#[test]
fn stage2_deaths_reward_count_once_and_replayed_entity_ids_reset_guards() {
    let (_t, mut a) = active(&IDS);
    for _ in 0..3 {
        let mut w = world(&a);
        for (idx, id) in IDS.iter().enumerate() {
            let entity = spawn(&mut w, &a, id, 24 + idx as i32 * 92, 0);
            w.apply_commands(
                &[Command::Damage {
                    entity,
                    amount: 100000,
                }],
                &a.registry,
            )
            .unwrap();
        }
        // on_spawn is queued before on_death even when every entity is already gone.
        w.step(Input::default(), &a.registry, &mut a.scripts)
            .unwrap();
        assert_eq!(w.player.credits, 460);
        assert!(w.enemies.is_empty());
        for id in IDS {
            assert_eq!(w.objectives.get(&format!("{id}:defeated")), Some(&1));
            assert!(w.mod_sounds.iter().any(|s| s.0 == format!("{id}:death")));
        }
        w.step(Input::default(), &a.registry, &mut a.scripts)
            .unwrap();
        assert_eq!(w.player.credits, 460);
        assert!(w.mod_sounds.is_empty());
    }
}
#[test]
fn stage2_rng_and_full_world_state_continue_identically_after_serialization() {
    let (_t, mut a) = active(&IDS);
    let (_u, mut b) = active(&IDS);
    let mut x = world(&a);
    x.player.x = 0;
    for (idx, id) in IDS.iter().enumerate() {
        spawn(&mut x, &a, id, 60 + idx as i32 * 75, -24);
    }
    let mut y = x.clone();
    for _ in 0..93 {
        x.step(Input::default(), &a.registry, &mut a.scripts)
            .unwrap();
        y.step(Input::default(), &b.registry, &mut b.scripts)
            .unwrap();
        assert_eq!(x.digest(), y.digest());
        assert_eq!(a.scripts.checkpoints(), b.scripts.checkpoints());
    }
    y = serde_json::from_slice(&serde_json::to_vec(&x).unwrap()).unwrap();
    b.scripts.restore(a.scripts.checkpoints());
    for _ in 0..210 {
        x.step(Input::default(), &a.registry, &mut a.scripts)
            .unwrap();
        y.step(Input::default(), &b.registry, &mut b.scripts)
            .unwrap();
        assert_eq!(
            serde_json::to_value(&x).unwrap(),
            serde_json::to_value(&y).unwrap()
        );
        assert_eq!(a.scripts.checkpoints(), b.scripts.checkpoints());
    }
}
#[test]
fn stage2_death_history_and_escaped_unit_state_are_bounded() {
    for id in IDS {
        let (_t, mut a) = active(&[id]);
        let mut w = world(&a);
        for _ in 0..260 {
            let entity = spawn(&mut w, &a, id, 100, 0);
            w.apply_commands(
                &[Command::Damage {
                    entity,
                    amount: 100000,
                }],
                &a.registry,
            )
            .unwrap();
            w.step(Input::default(), &a.registry, &mut a.scripts)
                .unwrap();
        }
        assert_eq!(w.objectives.get(&format!("{id}:defeated")), Some(&260));
        let states = a.scripts.checkpoints().0;
        let s = &states[&format!("{id}/scripts/ai.rhai")];
        assert!(s["dead"].as_object().unwrap().len() <= 128);
        assert!(s["dead_order"].as_array().unwrap().len() <= 128);
        assert!(s["units"].as_object().unwrap().is_empty());
        assert!(serde_json::to_vec(s).unwrap().len() < 16000);
    }
}

#[test]
fn stage2_shipped_art_is_aligned_and_every_sound_reaches_the_real_mixer() {
    use raptor_replica::{audio::Mixer, sound::SoundBank};
    use sha2::{Digest, Sha256};
    let root = Path::new(env!("CARGO_MANIFEST_DIR"));
    let mut registry = base();
    for id in IDS {
        let dir = root.join("mods").join(id);
        let pack: ContentPack =
            serde_json::from_slice(&fs::read(dir.join("content.json")).unwrap()).unwrap();
        registry.apply(pack, id).unwrap();
        registry.asset_roots.insert(id.to_string(), dir.clone());
        let qa: serde_json::Value =
            serde_json::from_slice(&fs::read(dir.join("art-qa.json")).unwrap()).unwrap();
        for frame in qa["frames"].as_array().unwrap() {
            let kind = frame["kind"].as_str().unwrap();
            for (mode, scale) in [("sd", 1), ("hd", 8)] {
                let bytes = fs::read(dir.join(format!("art/{kind}-{mode}.png"))).unwrap();
                let image = image::load_from_memory(&bytes).unwrap().into_rgba8();
                let (w, h) = image.dimensions();
                assert_eq!(
                    [w, h],
                    [
                        frame["logical_canvas"][0].as_u64().unwrap() as u32 * scale,
                        frame["logical_canvas"][1].as_u64().unwrap() as u32 * scale
                    ]
                );
                assert_eq!(
                    format!("{:x}", Sha256::digest(&bytes)),
                    frame[format!("{mode}_sha256")].as_str().unwrap()
                );
                assert!(image.pixels().any(|p| p[3] >= 128));
                assert!(image.pixels().any(|p| p[3] == 0));
                for (x, y, p) in image.enumerate_pixels() {
                    if p[3] >= 128 {
                        assert!(
                            x > 0 && y > 0 && x + 1 < w && y + 1 < h,
                            "{id}:{kind}:{mode} clipped"
                        );
                    }
                }
            }
            let raw = fs::read(dir.join(format!("art/{kind}-generated-v1.png"))).unwrap();
            assert_eq!(
                format!("{:x}", Sha256::digest(&raw)),
                frame["raw_sha256"].as_str().unwrap()
            );
        }
    }
    registry.validate().unwrap();
    let mut bank = SoundBank::default();
    let mut genmidi = b"#OPL_II#".to_vec();
    genmidi.resize(8 + 175 * 36, 0);
    for id in IDS {
        for cue in ["shot", "warning", "death"] {
            let sound: ContentId = format!("{id}:{cue}").as_str().into();
            let sample = bank.mod_sample(&registry, &sound).unwrap();
            assert_eq!(sample.rate, 22050);
            assert!(sample.data.len() >= 2000);
            assert!(sample.data.iter().any(|s| *s != 128));
            let mut mixer = Mixer::new(44100, &genmidi).unwrap();
            bank.queue_mod(&registry, &mut mixer, &sound).unwrap();
            let mut output = vec![0i16; 44100 * 2];
            mixer.mix(&mut output);
            assert!(
                output.iter().any(|s| *s != 0),
                "{sound} was silent at real queue/mix path"
            );
            assert!(
                output.iter().all(|s| *s != i16::MAX && *s != i16::MIN),
                "{sound} clipped"
            );
        }
    }
}

#[test]
fn stage2_invisible_or_passed_units_never_warn_or_fire_from_muzzle_coordinates() {
    for (idx, id) in IDS.iter().enumerate() {
        let width = if idx == 0 { 24 } else { 32 };
        for (x, y, player_y) in [
            (-8, 20, 170),
            (320 - width + 4, 20, 170),
            (100, -6, 170),
            (100, 190, 170),
            (100, 80, 80),
        ] {
            let (_t, mut a) = active(&[*id]);
            let mut w = world(&a);
            w.player.x = 0;
            w.player.y = player_y;
            spawn(&mut w, &a, id, x, y);
            for _ in 0..16 {
                w.enemies[0].x = x;
                w.enemies[0].y = y;
                w.step(Input::default(), &a.registry, &mut a.scripts)
                    .unwrap();
                assert!(
                    w.projectiles.is_empty(),
                    "{id} invisible/passed x{x},y{y} fired"
                );
                assert!(
                    w.mod_sounds.is_empty(),
                    "{id} invisible/passed x{x},y{y} warned"
                );
            }
        }
    }
}
