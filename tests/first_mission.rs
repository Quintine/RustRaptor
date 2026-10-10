//! Opt-in ordinary-input victory check against the installed original catalog.
use raptor_replica::{
    assets::{Catalog, decode_demo},
    content::Registry,
    modding::ScriptRuntime,
    persistence::Pilot,
    simulation::{Input, Outcome, World},
};
use serde_json::json;
use std::{
    collections::BTreeMap,
    fs,
    io::{BufWriter, Write},
    path::PathBuf,
};

const MISSION: &str = "base:sector_1_wave_1";
const ORIGINAL_FLYBY_SOUND: u32 = 129;

#[derive(Debug, serde::Serialize)]
struct DepartureObservation {
    tick: u64,
    timer: Option<u32>,
    x: i32,
    y: i32,
    draw_player: bool,
    control_paused: bool,
    sounds: Vec<u32>,
}

fn target_x(world: &World, registry: &Registry) -> i32 {
    let center = world.player.x + 16;
    world
        .enemies
        .iter()
        .filter(|e| e.health > 0 && e.y + e.height > 0 && e.y < world.player.y)
        .min_by_key(|e| {
            let def = &registry.enemies[&e.definition];
            (
                !def.boss,
                (e.x + e.width / 2 - center).abs() + (160 - e.y).max(0) / 3,
            )
        })
        .map_or(160, |e| {
            // Lead the current observed motion by the forward projectile's travel time.
            let travel = ((world.player.y - e.y - e.height / 2) / 8).clamp(0, 24);
            (e.x + e.width / 2 + (e.x - e.px).clamp(-4, 4) * travel).clamp(21, 298)
        })
}

fn controller(world: &World, registry: &Registry) -> Input {
    let aim = target_x(world, registry);
    if world.enemies.is_empty() && !world.projectiles.iter().any(|p| p.hostile) {
        return Input {
            fire: true,
            ..Input::default()
        };
    }
    let mut best = None;
    for dy in [0, -1, 1] {
        for dx in [0, -1, 1] {
            let input = Input {
                dx,
                dy,
                fire: true,
                ..Input::default()
            };
            // These are disposable predictions. The actual world changes only
            // through normal keyboard movement and the held fire button.
            let mut prediction = world.clone();
            let mut scripts = ScriptRuntime::new();
            for future in 0..12 {
                let projected = if future < 3 {
                    input
                } else {
                    Input {
                        fire: true,
                        ..Input::default()
                    }
                };
                prediction.step(projected, registry, &mut scripts).unwrap();
            }
            let lost = (world.player.shield + world.player.super_shield
                - prediction.player.shield
                - prediction.player.super_shield)
                .max(0) as i64;
            let position = prediction.player.x + 16 + prediction.player.vx * 2;
            let mut cost = lost * 1_000_000
                + (position - aim).abs() as i64 * 80
                + (160 - prediction.player.y).abs() as i64 * 6;
            if prediction.outcome == Outcome::Failed {
                cost += 1_000_000_000;
            }
            for p in prediction.projectiles.iter().filter(|p| p.hostile) {
                let distance = (p.x - prediction.player.x - 16)
                    .abs()
                    .max((p.y - prediction.player.y - 16).abs());
                cost += (40 - distance).max(0) as i64 * 30;
            }
            let gained = prediction
                .player
                .credits
                .saturating_sub(world.player.credits);
            cost -= gained as i64;
            if best.as_ref().is_none_or(|(previous, _)| cost < *previous) {
                best = Some((cost, input));
            }
        }
    }
    best.unwrap().1
}

fn demo(frames: &[[u8; 12]]) -> Vec<u8> {
    assert!(frames.len() <= i16::MAX as usize);
    let mut data = vec![0_u8; 12];
    data[8..10].copy_from_slice(&(frames.len() as i16).to_le_bytes());
    for frame in frames {
        data.extend_from_slice(frame);
    }
    let (sector, wave, decoded) = decode_demo(&data).unwrap();
    assert_eq!((sector, wave, decoded.len()), (0, 0, frames.len()));
    data
}

#[test]
#[ignore = "requires locally installed original data; ordinary-input first mission victory"]
fn original_first_mission_is_won_with_a_fresh_pilot() {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let path = std::env::var_os("RAPTOR_TEST_DATA")
        .map(PathBuf::from)
        .unwrap_or_else(|| root.join("data"));
    let catalog = Catalog::open(&path).unwrap();
    let registry = Registry::base(&catalog).unwrap();
    let reference = root.join(".reference");
    fs::create_dir_all(&reference).unwrap();
    for difficulty in [1, 2] {
        let pilot = Pilot {
            difficulty,
            ..Pilot::default()
        };
        pilot.validate(&registry, &[]).unwrap();
        let mut world = World::new(&MISSION.into(), &pilot, &registry).unwrap();
        let mut scripts = ScriptRuntime::new();
        let mut bosses = BTreeMap::new();
        let mut visible_bosses = BTreeMap::new();
        let mut killed = BTreeMap::new();
        // A removed entity with positive prior health is not credited as a
        // kill. This is conservative around same-step collision deaths.
        let mut positive_retirements = BTreeMap::new();
        let mut frames = Vec::new();
        let mut controls = Vec::new();
        let mut observations = Vec::new();
        let mut snapshots = Vec::new();
        let mut departure = Vec::new();
        for _ in 0..12_000 {
            if world.outcome != Outcome::Playing {
                break;
            }
            let input = controller(&world, &registry);
            let prior: Vec<_> = world
                .enemies
                .iter()
                .map(|e| (e.entity, e.definition.clone(), e.health))
                .collect();
            let before = world.player.shield;
            let before_credits = world.player.credits;
            let before_timer = world.end_timer;
            world.step(input, &registry, &mut scripts).unwrap();
            if world.end_timer.is_some() || before_timer.is_some() {
                departure.push(DepartureObservation {
                    tick: world.tick,
                    timer: world.end_timer,
                    x: world.player.x,
                    y: world.player.y,
                    draw_player: world.draw_player,
                    control_paused: world.control_paused,
                    sounds: world.sounds.clone(),
                });
            }
            for e in &world.enemies {
                if registry.enemies[&e.definition].boss {
                    bosses
                        .entry(e.entity)
                        .or_insert_with(|| (e.definition.clone(), world.tick));
                    if e.health > 0
                        && e.y + e.height > 0
                        && e.y < 200
                        && e.x + e.width > 0
                        && e.x < 320
                    {
                        visible_bosses.entry(e.entity).or_insert(world.tick);
                    }
                }
            }
            for (entity, definition, health) in prior {
                if !world.enemies.iter().any(|e| e.entity == entity) {
                    if health <= 0 {
                        let reward = registry.enemies[&definition].reward;
                        if bosses.contains_key(&entity) {
                            assert!(
                                world.player.credits >= before_credits + reward,
                                "original boss death did not award its reward"
                            );
                        }
                        killed.insert(entity, json!({"definition":definition,"tick":world.tick,"last_health":health,"reward":reward}));
                    } else {
                        positive_retirements.insert(entity, (definition, health));
                    }
                }
            }
            let mut frame = [0_u8; 12];
            frame[0] = u8::from(input.fire);
            frame[1] = u8::from(input.cycle);
            frame[2] = u8::from(input.bomb);
            frame[4..6].copy_from_slice(&(world.player.x as i16).to_le_bytes());
            frame[6..8].copy_from_slice(&(world.player.y as i16).to_le_bytes());
            frame[8..10].copy_from_slice(&(world.player.bank as i16).to_le_bytes());
            frames.push(frame);
            controls.push(json!({"tick":world.tick,"dx":input.dx,"dy":input.dy,"fire":input.fire}));
            snapshots.push(world.reference_state(&registry));
            if world.tick % 100 == 0
                || before != world.player.shield
                || world.outcome != Outcome::Playing
            {
                observations.push(json!({"tick":world.tick,"x":world.player.x,"y":world.player.y,"shield":world.player.shield,"credits":world.player.credits,"enemies":world.enemies.iter().map(|e| json!({"entity":e.entity,"id":e.definition,"health":e.health,"x":e.x,"y":e.y})).collect::<Vec<_>>()}));
            }
        }
        let cue = departure
            .iter()
            .find(|observation| observation.timer == Some(40))
            .expect("successful original mission skipped its departure cue");
        let report = json!({"mission":MISSION,"initial_pilot":pilot,"difficulty":difficulty,"ticks":world.tick,"demo_recorded_steps":cue.tick,"outcome":world.outcome,"shield":world.player.shield,"credits":world.player.credits,"spawns":world.spawn_cursor,"total_spawns":registry.missions[&world.mission].spawns.len(),"bosses":bosses,"bosses_first_visible":visible_bosses,"killed":killed,"positive_health_retirements":positive_retirements,"departure":departure,"observations":observations});
        let name = format!("first-mission-fresh-difficulty-{difficulty}");
        // The original DEMO_Think records before the stats-stage forced exit
        // movement. End-of-step coordinates are equivalent until timer40.
        // Keep this legacy recording to that boundary; the keyboard log below
        // independently reproduces the complete ordinary departure.
        let recorded = demo(&frames[..cue.tick as usize]);
        fs::write(reference.join(format!("{name}.dem")), &recorded).unwrap();
        fs::write(
            reference.join(format!("{name}-controls.json")),
            serde_json::to_vec(&controls).unwrap(),
        )
        .unwrap();
        fs::write(
            reference.join(format!("{name}-report.json")),
            serde_json::to_vec_pretty(&report).unwrap(),
        )
        .unwrap();
        let mut trace =
            BufWriter::new(fs::File::create(reference.join(format!("{name}.jsonl"))).unwrap());
        for snapshot in &snapshots {
            writeln!(&mut trace, "{snapshot}").unwrap();
        }
        trace.flush().unwrap();
        eprintln!(
            "First original mission difficulty {difficulty}: {:?}, {} steps, shield {}, credits {}, bosses {:?}, confirmed kills {}, positive-health retirements {}",
            world.outcome,
            world.tick,
            world.player.shield,
            world.player.credits,
            bosses,
            killed.len(),
            positive_retirements.len()
        );
        assert_eq!(world.outcome, Outcome::Complete, "{report}");
        let mission = &registry.missions[&world.mission];
        assert_eq!(world.spawn_cursor, mission.spawns.len());
        let expected_bosses = mission
            .spawns
            .iter()
            .filter(|spawn| {
                registry.enemies[&spawn.enemy].boss
                    && match spawn.difficulty {
                        3 => true,
                        4 => difficulty >= 2,
                        5 => difficulty >= 3,
                        _ => false,
                    }
            })
            .count();
        assert!(
            expected_bosses > 0,
            "catalog did not contain an original boss"
        );
        assert_eq!(
            bosses.len(),
            expected_bosses,
            "some original bosses never appeared"
        );
        assert_eq!(
            visible_bosses.len(),
            bosses.len(),
            "some bosses never entered the playfield alive"
        );
        assert!(
            bosses.keys().all(|entity| killed.contains_key(entity)),
            "an original boss escaped alive: {report}"
        );
        assert!(
            world.player.credits > pilot.credits,
            "victory must award original rewards"
        );
        assert!(cue.sounds.contains(&ORIGINAL_FLYBY_SOUND));
        assert!(cue.control_paused);
        let remaining_24 = departure
            .iter()
            .find(|observation| observation.timer == Some(24))
            .expect("successful original mission skipped its departure animation");
        assert!(
            remaining_24.draw_player,
            "a surviving pilot was hidden like a dead pilot"
        );
        assert!(
            world.player.y < 0,
            "surviving pilot never flew off the top of the screen"
        );
        // Legacy playback must preserve every snapshot through the boss kill
        // and flyby cue, before automatic departure changes the record phase.
        let (_, _, replay) = decode_demo(&recorded).unwrap();
        let mut replay_world = World::new(&MISSION.into(), &pilot, &registry).unwrap();
        let mut replay_scripts = ScriptRuntime::new();
        for (frame, expected) in replay.into_iter().zip(&snapshots) {
            replay_world
                .step(
                    Input {
                        fire: frame.buttons[0],
                        cycle: frame.buttons[1],
                        bomb: frame.buttons[2],
                        absolute: Some([frame.x as i32, frame.y as i32]),
                        demo_bank: Some(frame.bank as i32),
                        ..Input::default()
                    },
                    &registry,
                    &mut replay_scripts,
                )
                .unwrap();
            assert_eq!(
                replay_world.reference_state(&registry),
                *expected,
                "recorded first-mission input diverged at step {}",
                replay_world.tick
            );
        }
        assert_eq!(replay_world.tick, cue.tick);
        assert_eq!(replay_world.end_timer, Some(40));
        assert!(replay_world.enemies.is_empty());
        // The keyboard log is also independently decoded and replayed. Unlike
        // the original demo format, it includes ordinary departure movement.
        let keyboard: Vec<serde_json::Value> = serde_json::from_slice(
            &fs::read(reference.join(format!("{name}-controls.json"))).unwrap(),
        )
        .unwrap();
        let mut keyboard_world = World::new(&MISSION.into(), &pilot, &registry).unwrap();
        let mut keyboard_scripts = ScriptRuntime::new();
        assert_eq!(keyboard.len(), snapshots.len());
        for (control, expected) in keyboard.into_iter().zip(snapshots) {
            keyboard_world
                .step(
                    Input {
                        dx: control["dx"].as_i64().unwrap() as i32,
                        dy: control["dy"].as_i64().unwrap() as i32,
                        fire: control["fire"].as_bool().unwrap(),
                        ..Input::default()
                    },
                    &registry,
                    &mut keyboard_scripts,
                )
                .unwrap();
            assert_eq!(
                keyboard_world.reference_state(&registry),
                expected,
                "keyboard recording diverged at step {}",
                keyboard_world.tick
            );
        }
        assert_eq!(keyboard_world.outcome, Outcome::Complete);
    }
}
