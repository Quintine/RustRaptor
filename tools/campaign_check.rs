//! Opt-in original-catalog campaign inspection harness.
//!
//! This is coverage, not a gameplay parity proof or an ordinary player victory.
//! The fixture owns the original arsenal, fires continuously, aims horizontally
//! at visible enemies, cycles specials every 180 steps and uses five mega bombs.
//! Before each step, shields are replenished to the original 100+100 maxima.
//! No enemies, definitions, damage, spawn timings, RNG or outcomes are modified.
//!
//! Used by tests/campaigns.rs. To compile as a local reporting CLI, pass the built
//! raptor_replica and anyhow rlibs to rustc --extern, with
//! -L dependency=target/release/deps. See docs/campaign-validation.md.
use raptor_replica::{
    assets::Catalog,
    content::{ContentId, Registry},
    modding::ScriptRuntime,
    persistence::Pilot,
    simulation::{Input, Outcome, World},
};
use std::{collections::BTreeSet, path::Path};

#[derive(Debug)]
pub struct WaveReport {
    pub mission: ContentId,
    pub difficulty: u32,
    pub ticks: u64,
    pub outcome: Outcome,
    pub visited_spawns: usize,
    pub total_spawns: usize,
    pub enabled_spawns: usize,
    pub expected_bosses: usize,
    pub bosses_seen: usize,
    pub bosses_killed: usize,
    pub bosses_left_alive: usize,
    pub shield_replenishments: usize,
    pub credits: u32,
    pub digest: String,
    pub remaining: Vec<String>,
}
impl WaveReport {
    pub fn completed(&self) -> bool {
        self.outcome == Outcome::Complete
    }
    pub fn csv(&self) -> String {
        format!(
            "{},{},{},{:?},{}/{},{},{},{},{},{},{},{},{},{}",
            self.mission,
            self.difficulty,
            self.ticks,
            self.outcome,
            self.visited_spawns,
            self.total_spawns,
            self.enabled_spawns,
            self.expected_bosses,
            self.bosses_seen,
            self.bosses_killed,
            self.bosses_left_alive,
            self.shield_replenishments,
            self.credits,
            self.remaining.len(),
            self.digest
        )
    }
}

pub fn csv_header() -> &'static str {
    "mission,difficulty,ticks,outcome,visited_spawns,eligible_spawns,expected_bosses,seen_bosses,killed_bosses,left_alive,replenishments,credits,remaining_enemies,state_digest"
}

pub fn catalog_registry(path: &Path) -> anyhow::Result<(Catalog, Registry)> {
    let catalog = Catalog::open(path)?;
    let registry = Registry::base(&catalog)?;
    Ok((catalog, registry))
}
fn enabled(difficulty: u32, level: u32) -> bool {
    match level {
        3 => true,
        4 => difficulty >= 2,
        5 => difficulty >= 3,
        _ => false,
    }
}
pub fn arsenal_pilot(mission: ContentId, difficulty: u32, registry: &Registry) -> Pilot {
    let mut pilot = Pilot {
        mission,
        difficulty,
        credits: 10000,
        inventory: Default::default(),
        ..Pilot::default()
    };
    for item in registry
        .items
        .values()
        .filter(|i| i.legacy.is_some_and(|id| id <= 17))
    {
        let count = match item.legacy.unwrap() {
            11 => 5,
            15 | 16 => 100,
            _ => 1,
        };
        pilot
            .inventory
            .insert(item.id.clone(), count.min(item.max_count));
    }
    pilot.selected = Some("base:forward_laser".into());
    pilot
}
pub fn run_wave(
    registry: &Registry,
    sector: u32,
    wave: u32,
    difficulty: u32,
    maximum: u64,
) -> anyhow::Result<WaveReport> {
    let mission: ContentId = format!("base:sector_{sector}_wave_{wave}").as_str().into();
    let pilot = arsenal_pilot(mission.clone(), difficulty, registry);
    pilot.validate(registry, &[])?;
    let definition = &registry.missions[&mission];
    let eligible: Vec<_> = definition
        .spawns
        .iter()
        .filter(|s| enabled(difficulty, s.difficulty))
        .collect();
    let expected_bosses = eligible
        .iter()
        .filter(|s| registry.enemies[&s.enemy].boss)
        .count();
    let mut world = World::new(&mission, &pilot, registry)?;
    let mut scripts = ScriptRuntime::new();
    let mut bosses = BTreeSet::new();
    let mut killed = BTreeSet::new();
    let mut left_alive = BTreeSet::new();
    let mut replenishments = 0;
    for tick in 0..maximum {
        if world.outcome != Outcome::Playing {
            break;
        }
        if world.player.shield < 100 || world.player.super_shield < 100 {
            replenishments += 1;
        }
        // Explicit inspection assistance. Do not infer normal-player survival.
        world.player.shield = 100;
        world.player.super_shield = 100;
        let target = world
            .enemies
            .iter()
            .filter(|e| e.health > 0 && e.y + e.height > 0 && e.y < 160)
            .min_by_key(|e| {
                (
                    !registry.enemies[&e.definition].boss,
                    (e.x + e.width / 2 - (world.player.x + 16)).abs(),
                )
            });
        let x = target
            .map_or_else(
                || {
                    let phase = (tick % 240) as i32;
                    20 + if phase < 120 {
                        phase * 2
                    } else {
                        (240 - phase) * 2
                    }
                },
                |e| e.x + e.width / 2 - 16,
            )
            .clamp(5, 282);
        let prior: Vec<_> = world
            .enemies
            .iter()
            .filter(|e| registry.enemies[&e.definition].boss)
            .map(|e| (e.entity, e.health))
            .collect();
        world.step(
            Input {
                absolute: Some([x, 160]),
                fire: true,
                cycle: tick % 180 == 0 && tick > 0,
                bomb: tick % 480 == 240,
                ..Input::default()
            },
            registry,
            &mut scripts,
        )?;
        for e in &world.enemies {
            if registry.enemies[&e.definition].boss {
                bosses.insert(e.entity);
            }
        }
        for (entity, health) in prior {
            if !world.enemies.iter().any(|e| e.entity == entity) {
                if health <= 0 {
                    killed.insert(entity);
                } else {
                    left_alive.insert(entity);
                }
            }
        }
    }
    Ok(WaveReport {
        mission,
        difficulty,
        ticks: world.tick,
        outcome: world.outcome.clone(),
        visited_spawns: world.spawn_cursor,
        total_spawns: definition.spawns.len(),
        enabled_spawns: eligible.len(),
        expected_bosses,
        bosses_seen: bosses.len(),
        bosses_killed: killed.len(),
        bosses_left_alive: left_alive.len(),
        shield_replenishments: replenishments,
        credits: world.player.credits,
        digest: world.digest(),
        remaining: world
            .enemies
            .iter()
            .map(|e| {
                format!(
                    "{}@{},{} health={} move={},{}-> {},{}",
                    e.definition,
                    e.x,
                    e.y,
                    e.health,
                    e.movement.x,
                    e.movement.y,
                    e.movement.tx,
                    e.movement.ty
                )
            })
            .collect(),
    })
}

#[allow(dead_code)]
fn main() -> anyhow::Result<()> {
    let args: Vec<_> = std::env::args().skip(1).collect();
    let root = args
        .first()
        .map(|s| Path::new(s))
        .unwrap_or_else(|| Path::new("data"));
    let filter = args.get(1).map(|s| s.parse::<u32>()).transpose()?;
    let (_catalog, registry) = catalog_registry(root)?;
    println!("{}", csv_header());
    let mut incomplete = 0;
    for difficulty in 0..=3 {
        if filter.is_some_and(|d| d != difficulty) {
            continue;
        }
        for sector in 1..=3 {
            for wave in 1..=9 {
                let report = run_wave(&registry, sector, wave, difficulty, 12000)?;
                println!("{}", report.csv());
                if !report.completed() {
                    incomplete += 1;
                    eprintln!("Unfinished: {:?}", report);
                }
            }
        }
    }
    anyhow::ensure!(
        incomplete == 0,
        "{incomplete} fixture missions did not finish"
    );
    Ok(())
}
