//! Actual engine/script acceptance. Original assets stay outside this package.
use anyhow::{Result, ensure};
use raptor_replica::{
    assets::Catalog,
    content::{ContentId, Registry},
    modding::{self, ActiveMods},
    persistence::Pilot,
    simulation::{Input, Outcome, World},
};
use serde_json::json;
use std::{
    collections::{BTreeMap, BTreeSet},
    path::PathBuf,
};
const MISSION: &str = "iron_coast_mission_2:mission_02";
const MODS: [&str; 8] = [
    "iron_coast_scout",
    "iron_coast_turret",
    "iron_coast_boss_2",
    "iron_coast_music",
    "pulse_cannon",
    "seeker_swarm",
    "ion_lance",
    "iron_coast_mission_2",
];
fn run(
    active: &mut ActiveMods,
    shield: i32,
    credits: u32,
    owned: bool,
    full: bool,
) -> Result<serde_json::Value> {
    eprintln!(
        "Run: initial shield {shield}, credits {credits}, owned pulse {owned}, full inventory {full}"
    );
    let mut pilot = Pilot::default();
    pilot.inventory.insert("base:energy".into(), shield as u32);
    pilot.credits = credits;
    pilot.mission = ContentId::new(MISSION)?;
    pilot.difficulty = 2;
    if owned {
        pilot.inventory.insert("pulse_cannon:equipment".into(), 1);
    }
    if full {
        for (id, item) in &active.registry.items {
            if pilot.inventory_slots() >= 20 {
                break;
            }
            if item.legacy == Some(16)
                || item.legacy == Some(17)
                || id.0 == "pulse_cannon:equipment"
            {
                continue;
            }
            pilot.inventory.insert(id.clone(), item.initial_count);
        }
        ensure!(
            pilot.inventory_slots() == 20,
            "full inventory fixture must use20 slots"
        );
    }
    let original = pilot.inventory.clone();
    let mut world = World::new(&pilot.mission, &pilot, &active.registry)?;
    let mut cues = BTreeSet::new();
    let mut seen = BTreeSet::new();
    let mut native_positions = BTreeMap::new();
    let mut native_moved = BTreeSet::new();
    for _ in 0..2300 {
        let x = world
            .enemies
            .iter()
            .find(|e| e.definition.0 == "iron_coast_mission_2:relay" && e.health > 0)
            .map(|e| e.x)
            .unwrap_or(144);
        world.step(
            Input {
                fire: true,
                absolute: Some([world.player.x + (x - world.player.x).clamp(-4, 4), 160]),
                ..Input::default()
            },
            &active.registry,
            &mut active.scripts,
        )?;
        for sound in &world.mod_sounds {
            cues.insert(sound.0.clone());
        }
        for enemy in &world.enemies {
            seen.insert(enemy.definition.0.clone());
            if enemy.definition.0.starts_with("base:enemy_") {
                ensure!(
                    active.registry.enemies[&enemy.definition].legacy.is_some(),
                    "native data remains native"
                );
                let entry = native_positions
                    .entry(enemy.entity)
                    .or_insert((enemy.x, enemy.y));
                if *entry != (enemy.x, enemy.y) {
                    native_moved.insert(enemy.definition.0.clone());
                }
            }
        }
        if world.outcome != Outcome::Playing {
            break;
        }
    }
    ensure!(
        world.outcome == Outcome::Complete,
        "run ended {:?} tick{} shield{} objectives{:?}",
        world.outcome,
        world.tick,
        world.player.shield,
        world.objectives
    );
    ensure!(
        world.objectives["iron_coast_mission_2:relays_disabled"] == 3,
        "all3 relays are required"
    );
    ensure!(world.objectives["iron_coast_mission_2:debrief"] == 1);
    ensure!(world.player.shield > 0);
    ensure!(
        world
            .player
            .inventory
            .contains_key(&"pulse_cannon:equipment".into())
            == owned,
        "loan returned, owned gun preserved"
    );
    if full {
        for (id, count) in &original {
            if id.0 != "base:energy" && id.0 != "base:super_shield" {
                ensure!(
                    world.player.inventory.get(id) == Some(count),
                    "full inventory equipment preserved: {id}"
                );
            }
        }
    }
    ensure!(
        native_moved.len() == 3,
        "all3 actual original enemies move before completion"
    );
    let before = world.player.credits;
    world.step(Input::default(), &active.registry, &mut active.scripts)?;
    ensure!(before == world.player.credits, "no repeated reward");
    Ok(
        json!({"shield_initial":shield,"credits_initial":credits,"owned_pulse":owned,"full_inventory":full,"tick":world.tick,"outcome":format!("{:?}",world.outcome),"shield_remaining":world.player.shield,"credits_final":world.player.credits,"credit_gain":world.player.credits-credits,"objectives":world.objectives,"seen_enemies":seen,"native_definitions_observed_moving":native_moved,"played_cues":cues,"digest":world.digest()}),
    )
}
fn main() -> Result<()> {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../../../..")
        .canonicalize()?;
    let data = std::env::args()
        .nth(1)
        .map(PathBuf::from)
        .unwrap_or(root.join("data"));
    let mods = root.join("RustRaptor/mods");
    let catalog = Catalog::open(data)?;
    let base = Registry::base(&catalog)?;
    let discovery = modding::discover(&mods);
    let enabled = MODS.iter().map(|s| s.to_string()).collect::<Vec<_>>();
    let mut active = ActiveMods::build(&base, &discovery, &enabled, Some(&catalog))?;
    let results = vec![
        run(&mut active, 75, 10000, false, false)?,
        run(&mut active, 100, 0, false, false)?,
        run(&mut active, 75, 10000, true, false)?,
        run(&mut active, 75, 10000, false, true)?,
    ];
    let mut gate = World::new(&MISSION.into(), &Pilot::default(), &active.registry)?;
    gate.step(Input::default(), &active.registry, &mut active.scripts)?;
    gate.objectives
        .insert("iron_coast_boss_2:defeated".into(), 1);
    gate.objectives
        .insert("iron_coast_mission_2:relays_disabled".into(), 2);
    gate.step(Input::default(), &active.registry, &mut active.scripts)?;
    ensure!(
        gate.outcome == Outcome::Playing,
        "boss alone or only2 relays cannot complete"
    );
    gate.objectives
        .insert("iron_coast_mission_2:relays_disabled".into(), 3);
    gate.step(Input::default(), &active.registry, &mut active.scripts)?;
    ensure!(
        gate.outcome == Outcome::Complete && gate.player.credits == 7500,
        "final objective awards7500 once"
    );
    gate.step(Input::default(), &active.registry, &mut active.scripts)?;
    ensure!(
        gate.player.credits == 7500,
        "repeated step cannot pay again"
    );
    println!(
        "{}",
        serde_json::to_string_pretty(
            &json!({"mission":MISSION,"strategy":"Held fire; y160; move at most 4 pixels/tick toward first living relay x, otherwise x144. No direct damage, shield or credit commands.","runs":results,"gating_checks":{"requires_three_relays_and_boss":true,"completion_reward_exactly_7500_once":true,"restart_state_reset":true}})
        )?
    );
    Ok(())
}
