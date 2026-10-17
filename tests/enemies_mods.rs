//! Enemy package tests use synthetic PNG/WAV fixtures, never original/generated art.
use raptor_replica::{
    content::{ContentId, ContentPack, Registry},
    modding::{self, ActiveMods, Command},
    persistence::Pilot,
    simulation::{Input, Outcome, World},
};
use serde_json::json;
use std::{fs, path::Path};

const ENEMIES: [&str; 3] = ["iron_coast_scout", "iron_coast_turret", "iron_coast_boss"];

fn base() -> Registry {
    let mut registry = Registry::default();
    let pack: ContentPack = serde_json::from_value(json!({
        "weapons": [{"id":"base:projectile_forward_guns", "name":"Forward Guns",
            "damage":1,"speed":8,"cooldown":2,"behavior":"straight","target":"all",
            "offsets":[[-8,0],[8,0]]}],
        "items":[{"id":"base:forward_guns","name":"Forward Guns","price":0,
            "weapon":"base:projectile_forward_guns"},
            {"id":"base:energy","name":"Shield","price":0,"max_count":100}],
        "missions":[{"id":"base:sector_1_wave_1","name":"Synthetic Range","duration":5000}]
    }))
    .unwrap();
    registry.apply(pack, "base").unwrap();
    registry.validate().unwrap();
    registry
}

fn wav() -> Vec<u8> {
    let mut data = b"RIFF".to_vec();
    data.extend(40_u32.to_le_bytes());
    data.extend(b"WAVEfmt ");
    data.extend(16_u32.to_le_bytes());
    data.extend(1_u16.to_le_bytes());
    data.extend(1_u16.to_le_bytes());
    data.extend(22050_u32.to_le_bytes());
    data.extend(44100_u32.to_le_bytes());
    data.extend(2_u16.to_le_bytes());
    data.extend(16_u16.to_le_bytes());
    data.extend(b"data");
    data.extend(4_u32.to_le_bytes());
    data.extend([0, 0, 0, 0]);
    data
}

fn install_fixture(root: &Path, id: &str) {
    let source = Path::new(env!("CARGO_MANIFEST_DIR")).join("mods").join(id);
    let output = root.join(id);
    fs::create_dir_all(output.join("scripts")).unwrap();
    fs::create_dir_all(output.join("art")).unwrap();
    fs::create_dir_all(output.join("audio")).unwrap();
    for name in ["mod.toml", "content.json", "scripts/ai.rhai"] {
        fs::copy(source.join(name), output.join(name)).unwrap();
    }
    let content: ContentPack =
        serde_json::from_slice(&fs::read(source.join("content.json")).unwrap()).unwrap();
    for art in content
        .enemies
        .iter()
        .filter_map(|e| e.art.as_ref())
        .chain(content.weapons.iter().filter_map(|w| w.art.as_ref()))
    {
        for (path, scale) in [
            (art.png.as_ref().unwrap(), 1),
            (art.hd_png.as_ref().unwrap(), 2),
        ] {
            let mut image = image::RgbaImage::new(
                art.logical_width * art.frames * scale,
                art.logical_height * scale,
            );
            for frame in 0..art.frames {
                for y in scale..(art.logical_height - 1) * scale {
                    for x in scale..(art.logical_width - 1) * scale {
                        image.put_pixel(
                            frame * art.logical_width * scale + x,
                            y,
                            image::Rgba([80, 90, 100, 255]),
                        );
                    }
                }
            }
            image.save(output.join(path)).unwrap();
        }
    }
    for sound in content.sounds {
        fs::write(output.join(sound.file), wav()).unwrap();
    }
}

fn active(ids: &[&str]) -> (tempfile::TempDir, ActiveMods) {
    let temp = tempfile::tempdir().unwrap();
    for id in ids {
        install_fixture(temp.path(), id);
    }
    let discovered = modding::discover(temp.path());
    assert!(discovered.errors.is_empty(), "{:?}", discovered.errors);
    let selected: Vec<String> = ids.iter().map(|id| id.to_string()).collect();
    let active = ActiveMods::build(&base(), &discovered, &selected, None).unwrap();
    (temp, active)
}

fn world(active: &ActiveMods) -> World {
    World::new(
        &ContentId::from("base:sector_1_wave_1"),
        &Pilot::default(),
        &active.registry,
    )
    .unwrap()
}

#[test]
fn all_enemy_packages_validate_independently_and_together() {
    for id in ENEMIES {
        let (_temp, a) = active(&[id]);
        assert_eq!(a.pins.len(), 1);
        assert_eq!(a.registry.enemies.len(), 1);
        assert!(
            a.registry
                .weapons
                .contains_key(&ContentId::new(format!("{id}:projectile")).unwrap())
        );
        assert_eq!(
            a.registry.sounds.len(),
            if id == "iron_coast_boss" { 3 } else { 2 }
        );
        assert_eq!(
            a.registry.enemies[&ContentId::new(format!("{id}:unit")).unwrap()]
                .script
                .as_deref(),
            Some("scripts/ai.rhai")
        );
    }
    let (_temp, a) = active(&ENEMIES);
    assert_eq!(a.pins.len(), 3);
    assert_eq!(a.registry.enemies.len(), 3);
    assert!(a.registry.overrides.is_empty());
}

#[test]
fn scout_enters_attacks_once_and_exits_without_kill_rewards() {
    // Each approach has one lateral leg, rather than the old endless weave.
    for (x, direction) in [(120, 1), (200, -1)] {
        let (_temp, mut a) = active(&["iron_coast_scout"]);
        let mut w = world(&a);
        w.player.x = 0;
        w.spawn(&"iron_coast_scout:unit".into(), x, -24, &a.registry)
            .unwrap();
        let mut speeds = std::collections::BTreeSet::new();
        let mut lateral = false;
        let mut aimed_left = false;
        for _ in 0..200 {
            w.step(Input::default(), &a.registry, &mut a.scripts)
                .unwrap();
            for p in w.projectiles.iter().filter(|p| p.age == 0 && p.hostile) {
                aimed_left |= p.vx < 0;
            }
            w.projectiles.clear(); // Isolate the approach, not player survival.
            let Some(e) = w.enemies.first() else { break };
            speeds.insert(e.vy);
            lateral |= e.vx.signum() == direction;
        }
        assert_eq!(speeds, [1, 2, 3].into_iter().collect());
        assert!(lateral && aimed_left);
        assert!(
            w.enemies.is_empty(),
            "the scout must finish its attack pass"
        );
        assert_eq!(w.player.credits, 0);
        assert!(!w.objectives.contains_key("iron_coast_scout:defeated"));
    }
}

#[test]
fn light_enemies_do_not_fire_when_the_actor_is_not_fully_visible() {
    for id in ["iron_coast_scout", "iron_coast_turret"] {
        // Partially offscreen, above the viewport, and below the attack window.
        // Keep x inside the natural-exit boundary so the same actor is observed.
        for (x, y) in [(-1, 40), (40, -40), (40, 180)] {
            let (_temp, mut a) = active(&[id]);
            let mut w = world(&a);
            w.spawn(&format!("{id}:unit").as_str().into(), x, y, &a.registry)
                .unwrap();
            for _ in 0..80 {
                w.enemies[0].x = x;
                w.enemies[0].y = y;
                // Movement precedes the refreshed actor snapshot. Hold the
                // fixture outside so its prior velocity cannot carry it into view.
                w.enemies[0].vx = 0;
                w.enemies[0].vy = 0;
                w.step(Input::default(), &a.registry, &mut a.scripts)
                    .unwrap();
                assert!(
                    w.projectiles.is_empty(),
                    "{id} fired outside its attack window"
                );
                assert!(
                    !w.mod_sounds
                        .iter()
                        .any(|sound| sound.0 == format!("{id}:shot"))
                );
            }
        }
    }
}

#[test]
fn turret_scrolls_with_terrain_and_aims_at_player() {
    let (_temp, mut a) = active(&["iron_coast_turret"]);
    let mut w = world(&a);
    w.player.x = 0;
    w.spawn(
        &ContentId::from("iron_coast_turret:unit"),
        220,
        0,
        &a.registry,
    )
    .unwrap();
    let mut sounds = 0;
    for _ in 0..80 {
        w.step(Input::default(), &a.registry, &mut a.scripts)
            .unwrap();
        sounds += w
            .mod_sounds
            .iter()
            .filter(|id| id.0 == "iron_coast_turret:shot")
            .count();
    }
    assert_eq!((w.enemies[0].x, w.enemies[0].y), (220, 80));
    assert!(a.registry.enemies[&w.enemies[0].definition].ground);
    assert_eq!(sounds, 1);
    assert!(
        w.projectiles
            .iter()
            .any(|p| p.hostile && p.vx < 0 && p.vy >= 0)
    );
}

#[test]
fn boss_telegraphs_three_patterns_and_recovers_on_screen_at_every_difficulty() {
    for difficulty in 0..4 {
        let (_temp, mut a) = active(&["iron_coast_boss"]);
        let mut w = world(&a);
        w.difficulty = difficulty;
        w.player.x = 0;
        w.spawn(&"iron_coast_boss:unit".into(), 112, -64, &a.registry)
            .unwrap();
        let mut directions = std::collections::BTreeSet::new();
        let mut warnings = Vec::new();
        let mut shots = Vec::new();
        for tick in 0..500 {
            w.step(Input::default(), &a.registry, &mut a.scripts)
                .unwrap();
            assert_eq!(w.outcome, Outcome::Playing);
            assert_eq!(w.enemies.len(), 1, "boss retired at {tick}");
            let e = &w.enemies[0];
            assert_eq!((e.width, e.height), (84, 56));
            if tick > 46 {
                assert_eq!(e.y, 24);
                assert!((32..=204).contains(&e.x));
                directions.insert(e.vx.signum());
            }
            if w.mod_sounds.contains(&"iron_coast_boss:warning".into()) {
                warnings.push(tick);
                assert_eq!(e.vx, 0, "warning is a stationary hit window");
                assert!(!w.lightning_arcs.is_empty());
            }
            let bullets: Vec<_> = w
                .projectiles
                .iter()
                .filter(|p| p.age == 0 && p.hostile)
                .collect();
            if w.mod_sounds.contains(&"iron_coast_boss:shot".into()) {
                assert_eq!(tick - warnings.last().unwrap(), 18 - difficulty * 2);
                assert_eq!(e.vx, 0);
                let pattern = shots.len() % 3;
                assert_eq!(bullets.len(), [3, 2, 1][pattern]);
                if pattern == 0 {
                    assert_eq!(bullets.iter().map(|p| p.vx).collect::<Vec<_>>(), [-1, 0, 1]);
                } else if pattern == 1 {
                    assert!(bullets.iter().all(|p| p.vx == 0));
                } else {
                    assert!(
                        bullets[0].vx < 0,
                        "aimed pattern follows the locked left lane"
                    );
                }
                assert!(
                    bullets
                        .iter()
                        .all(|p| p.vy == if difficulty >= 2 { 4 } else { 3 })
                );
                shots.push(tick);
            } else {
                assert!(bullets.is_empty(), "no untelegraphed salvo");
            }
            w.projectiles.clear(); // Separate clock/pattern coverage from the starter-gun survival test.
        }
        assert_eq!(directions, [-1, 0, 1].into_iter().collect());
        assert!(shots.len() >= 4);
        assert!(
            warnings
                .windows(2)
                .all(|pair| pair[1] - pair[0] == 96 - difficulty * 6)
        );
    }
}

#[test]
fn boss_can_be_defeated_with_starter_guns_without_healing() {
    let (_temp, mut a) = active(&["iron_coast_boss"]);
    let mut w = world(&a);
    w.player.x = 128;
    w.spawn(
        &ContentId::from("iron_coast_boss:unit"),
        112,
        -64,
        &a.registry,
    )
    .unwrap();
    let mut defeated_at = None;
    for tick in 0..600 {
        w.step(
            Input {
                fire: true,
                ..Input::default()
            },
            &a.registry,
            &mut a.scripts,
        )
        .unwrap();
        if w.objectives.get("iron_coast_boss:defeated") == Some(&1) {
            defeated_at = Some(tick);
            break;
        }
        assert_eq!(w.outcome, Outcome::Playing, "starter pilot died at{tick}");
    }
    assert!(
        defeated_at.is_some(),
        "boss cannot be killed with starter guns"
    );
    assert!(w.enemies.is_empty());
    assert!(w.player.shield > 0);
    assert_eq!(w.player.credits, 1800);
    assert!(
        w.mod_sounds
            .contains(&ContentId::from("iron_coast_boss:death"))
    );
}

#[test]
fn death_rewards_objectives_and_sounds_are_emitted_exactly_once() {
    let (_temp, mut a) = active(&ENEMIES);
    let mut w = world(&a);
    for (index, id) in ENEMIES.iter().enumerate() {
        let unit = ContentId::new(format!("{id}:unit")).unwrap();
        let entity = w
            .spawn(&unit, 30 + index as i32 * 100, 0, &a.registry)
            .unwrap();
        w.apply_commands(
            &[Command::Damage {
                entity,
                amount: 100000,
            }],
            &a.registry,
        )
        .unwrap();
    }
    w.step(Input::default(), &a.registry, &mut a.scripts)
        .unwrap();
    assert!(w.enemies.is_empty());
    assert_eq!(w.player.credits, 75 + 120 + 1800);
    for id in ENEMIES {
        assert_eq!(w.objectives.get(&format!("{id}:defeated")), Some(&1));
        assert!(
            w.mod_sounds
                .contains(&ContentId::new(format!("{id}:death")).unwrap())
        );
    }
    let previous = w.player.credits;
    w.step(Input::default(), &a.registry, &mut a.scripts)
        .unwrap();
    assert_eq!(w.player.credits, previous);
    assert!(w.mod_sounds.is_empty());
}

#[test]
fn enemy_scripts_replay_identically_and_restore_serialized_state() {
    let (_temp, mut first) = active(&ENEMIES);
    let (_other, mut second) = active(&ENEMIES);
    let mut a = world(&first);
    for (index, id) in ENEMIES.iter().enumerate() {
        a.spawn(
            &ContentId::new(format!("{id}:unit")).unwrap(),
            60 + index as i32 * 30,
            -24,
            &first.registry,
        )
        .unwrap();
    }
    a.player.x = 0;
    let mut b = a.clone();
    for _ in 0..75 {
        a.step(Input::default(), &first.registry, &mut first.scripts)
            .unwrap();
        b.step(Input::default(), &second.registry, &mut second.scripts)
            .unwrap();
        assert_eq!(a.digest(), b.digest());
        assert_eq!(first.scripts.checkpoints(), second.scripts.checkpoints());
    }
    let snapshot = serde_json::to_vec(&a).unwrap();
    b = serde_json::from_slice(&snapshot).unwrap();
    let checkpoint = first.scripts.checkpoints();
    second.scripts.restore(checkpoint);
    for _ in 0..25 {
        a.step(Input::default(), &first.registry, &mut first.scripts)
            .unwrap();
        b.step(Input::default(), &second.registry, &mut second.scripts)
            .unwrap();
        assert_eq!(a.digest(), b.digest());
    }
}

#[test]
fn mission_defeat_counts_reset_while_persistent_script_statistics_continue() {
    let (_temp, mut a) = active(&ENEMIES);
    for id in ENEMIES {
        let unit = ContentId::new(format!("{id}:unit")).unwrap();
        let mut first = world(&a);
        for _ in 0..2 {
            let entity = first.spawn(&unit, 20, 0, &a.registry).unwrap();
            first
                .step(Input::default(), &a.registry, &mut a.scripts)
                .unwrap();
            first
                .apply_commands(
                    &[Command::Damage {
                        entity,
                        amount: 100000,
                    }],
                    &a.registry,
                )
                .unwrap();
            first
                .step(Input::default(), &a.registry, &mut a.scripts)
                .unwrap();
        }
        assert_eq!(first.objectives.get(&format!("{id}:defeated")), Some(&2));
        let mut next = world(&a);
        let entity = next.spawn(&unit, 20, 0, &a.registry).unwrap();
        next.step(Input::default(), &a.registry, &mut a.scripts)
            .unwrap();
        next.apply_commands(
            &[Command::Damage {
                entity,
                amount: 100000,
            }],
            &a.registry,
        )
        .unwrap();
        next.step(Input::default(), &a.registry, &mut a.scripts)
            .unwrap();
        assert_eq!(next.objectives.get(&format!("{id}:defeated")), Some(&1));
        let state = a.scripts.checkpoints().0;
        assert_eq!(state[&format!("{id}/scripts/ai.rhai")]["destroyed"], 3);
        // The next tick must not resurrect or fire on behalf of a dead actor.
        next.step(Input::default(), &a.registry, &mut a.scripts)
            .unwrap();
        assert!(next.enemies.is_empty());
        assert!(next.projectiles.is_empty());
        assert_eq!(next.objectives[&format!("{id}:defeated")], 1);
    }
}

#[test]
fn shipped_enemy_assets_are_valid_and_aligned() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("mods");
    let selected: Vec<_> = ENEMIES.iter().map(|id| id.to_string()).collect();
    let discovery = modding::discover(&root);
    ActiveMods::build(&base(), &discovery, &selected, None).unwrap();
    for id in ENEMIES {
        let content: ContentPack =
            serde_json::from_slice(&fs::read(root.join(id).join("content.json")).unwrap()).unwrap();
        let art = content.enemies[0].art.as_ref().unwrap();
        for path in [art.png.as_ref().unwrap(), art.hd_png.as_ref().unwrap()] {
            let image = image::open(root.join(id).join(path)).unwrap().into_rgba8();
            assert_eq!(
                image.width() / art.frames * art.logical_height,
                image.height() * art.logical_width
            );
            for frame in 0..art.frames {
                let width = image.width() / art.frames;
                for x in frame * width..(frame + 1) * width {
                    assert!(image.get_pixel(x, 0)[3] < 128);
                    assert!(image.get_pixel(x, image.height() - 1)[3] < 128);
                }
                for y in 0..image.height() {
                    assert!(image.get_pixel(frame * width, y)[3] < 128);
                    assert!(image.get_pixel((frame + 1) * width - 1, y)[3] < 128);
                }
            }
        }
    }
}
