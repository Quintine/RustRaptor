//! SDL-independent fixed-step simulation and checked mod command application.
use crate::{
    content::{ContentId, Registry, Target, WeaponBehavior},
    modding::{Command, ScriptRuntime},
    persistence::Pilot,
};
use anyhow::{Context, Result, ensure};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

pub const TICK_NUMERATOR: u64 = 3;
pub const TICK_DENOMINATOR: u64 = 70;
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct LegacyRng {
    pub seed: i32,
}
impl LegacyRng {
    pub fn new(seed: i32) -> Self {
        Self { seed }
    }
    pub fn next_value(&mut self) -> i32 {
        self.seed = self.seed.wrapping_mul(1103515245).wrapping_add(12345);
        (self.seed >> 16) & 0x7fff
    }
}
#[derive(Debug, Clone, Copy, Default, Serialize, Deserialize)]
pub struct Input {
    pub dx: i32,
    pub dy: i32,
    pub fire: bool,
    pub special: bool,
    pub cycle: bool,
    pub bomb: bool,
    pub absolute: Option<[i32; 2]>,
    pub demo_bank: Option<i32>,
}
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct LineMove {
    pub x: i32,
    pub y: i32,
    pub tx: i32,
    pub ty: i32,
    pub dx: i32,
    pub dy: i32,
    pub ax: i32,
    pub ay: i32,
    pub error: i32,
    pub remaining: i32,
    pub done: bool,
}
impl LineMove {
    pub fn new(x: i32, y: i32, tx: i32, ty: i32) -> Self {
        let dx = (tx - x).abs();
        let dy = (ty - y).abs();
        let mut m = Self {
            x,
            y,
            tx,
            ty,
            dx,
            dy,
            ax: if tx < x { -1 } else { 1 },
            ay: if ty < y { -1 } else { 1 },
            error: if dx >= dy { -(dy >> 1) } else { dx >> 1 },
            remaining: dx.max(dy) + 1,
            done: false,
        };
        if dx == 0 && dy == 0 {
            m.done = true;
        }
        m
    }
    pub fn initial(&mut self) {
        if self.remaining == 0 {
            self.done = true;
            return;
        }
        self.point();
        self.remaining -= 1;
    }
    fn point(&mut self) {
        if self.dx >= self.dy {
            self.x += self.ax;
            self.error += self.dy;
            if self.error > 0 {
                self.y += self.ay;
                self.error -= self.dx;
            }
        } else {
            self.y += self.ay;
            self.error += self.dx;
            if self.error > 0 {
                self.x += self.ax;
                self.error -= self.dy;
            }
        }
    }
    pub fn advance_shot(&mut self, speed: i32) {
        // MoveSobj crosses the endpoint before marking done; enemies instead stop at it.
        for _ in 0..speed.max(0) {
            self.remaining -= 1;
            self.point();
        }
        if self.remaining < 1 {
            self.done = true;
        }
    }
    pub fn advance(&mut self, speed: i32) -> i32 {
        if self.done {
            return speed;
        }
        let mut left = speed;
        while left > 0 {
            left -= 1;
            self.remaining -= 1;
            if self.remaining == 0 {
                self.done = true;
                return left;
            }
            if self.dx >= self.dy {
                self.x += self.ax;
                self.error += self.dy;
                if self.error > 0 {
                    self.y += self.ay;
                    self.error -= self.dx;
                }
            } else {
                self.y += self.ay;
                self.error += self.dx;
                if self.error > 0 {
                    self.x += self.ax;
                    self.error -= self.dy;
                }
            }
        }
        left
    }
}
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Player {
    pub x: i32,
    pub y: i32,
    pub px: i32,
    pub py: i32,
    pub bank: i32,
    pub shield: i32,
    pub super_shield: i32,
    pub credits: u32,
    pub inventory: BTreeMap<ContentId, u32>,
    pub selected: Option<ContentId>,
    pub vx: i32,
    pub vy: i32,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Enemy {
    pub entity: u64,
    pub definition: ContentId,
    pub x: i32,
    pub y: i32,
    pub px: i32,
    pub py: i32,
    pub sx: i32,
    pub sy: i32,
    pub width: i32,
    pub height: i32,
    pub health: i32,
    pub age: u32,
    pub cooldown: u32,
    pub path_index: usize,
    pub reversed: bool,
    pub movement: LineMove,
    pub frame: u32,
    pub art_frame: u32,
    pub animation_on: bool,
    pub animation_frames: u32,
    pub multi: u32,
    pub frame_timer: i32,
    pub countdown: i32,
    pub shoot_on: bool,
    pub shootagain: i32,
    pub shootcount: i32,
    pub shootflag: i32,
    pub kami: u32,
    pub vx: i32,
    pub vy: i32,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LegacyProjectile {
    pub movement: LineMove,
    pub speed: i32,
    pub frame: u32,
    pub art_frame: u32,
    pub delay: bool,
    pub hit: bool,
    pub start: [i32; 2],
}
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EnemyProjectile {
    pub movement: LineMove,
    pub kind: i16,
    pub asset: u32,
    pub frames: u32,
    pub frame: u32,
    pub art_frame: u32,
    pub speed: i32,
    pub maximum_speed: i32,
    pub damage: i32,
    pub position: usize,
    pub enemy: u64,
    pub gun: usize,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Projectile {
    pub entity: u64,
    pub weapon: ContentId,
    pub x: i32,
    pub y: i32,
    pub px: i32,
    pub py: i32,
    pub vx: i32,
    pub vy: i32,
    pub hostile: bool,
    pub age: u32,
    pub legacy: Option<LegacyProjectile>,
    pub legacy_enemy: Option<EnemyProjectile>,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Pickup {
    pub entity: u64,
    pub item: ContentId,
    pub x: i32,
    pub y: i32,
    pub legacy: Option<LegacyPickup>,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LegacyPickup {
    pub x: i32,
    pub y: i32,
    pub position: usize,
    pub frame: u32,
    pub art_frame: u32,
    pub countdown: Option<u32>,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Effect {
    pub x: i32,
    pub y: i32,
    pub age: u32,
}
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub enum Outcome {
    Playing,
    Complete,
    Failed,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SoundEvent {
    pub asset: u32,
    pub pan: i32,
    pub pitch: i32,
    pub volume: i32,
    pub priority: i32,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TerrainDelay {
    pub position: usize,
    pub frames: i32,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct World {
    pub tick: u64,
    pub mission: ContentId,
    pub player: Player,
    pub enemies: Vec<Enemy>,
    pub projectiles: Vec<Projectile>,
    pub pickups: Vec<Pickup>,
    pub effects: Vec<Effect>,
    pub terrain_health: Vec<i32>,
    pub terrain_dead: Vec<bool>,
    pub terrain_settled: Vec<bool>,
    pub terrain_delays: Vec<TerrainDelay>,
    pub rng: LegacyRng,
    pub difficulty: u32,
    pub outcome: Outcome,
    pub end_timer: Option<u32>,
    pub scroll: i32,
    pub objectives: BTreeMap<String, i32>,
    pub sounds: Vec<u32>,
    pub sound_events: Vec<SoundEvent>,
    pub mod_sounds: Vec<ContentId>,
    pub cooldowns: BTreeMap<ContentId, u32>,
    pub next_entity: u64,
    pub spawn_cursor: usize,
    pub cycle_held: bool,
    pub bomb_held: bool,
    pub palette_blue: bool,
    pub special_held: bool,
    pub player_flash: bool,
    #[serde(skip)]
    pub events: Vec<HookEvent>,
}
#[derive(Debug, Clone)]
pub struct HookEvent {
    pub content: ContentId,
    pub hook: &'static str,
    pub event: serde_json::Value,
}
impl World {
    pub fn new(mission: &ContentId, pilot: &Pilot, registry: &Registry) -> Result<Self> {
        let m = registry.missions.get(mission).context("unknown mission")?;
        let energy = pilot
            .inventory
            .get(&ContentId::from("base:energy"))
            .copied()
            .unwrap_or(100) as i32;
        let wave = mission
            .0
            .rsplit('_')
            .next()
            .and_then(|s| s.parse::<i32>().ok())
            .unwrap_or(1)
            - 1;
        let mut out = Self {
            tick: 0,
            mission: mission.clone(),
            player: Player {
                x: 144,
                y: 160,
                px: 144,
                py: 160,
                bank: 3,
                shield: energy.clamp(1, 100),
                super_shield: pilot
                    .inventory
                    .get(&ContentId::from("base:super_shield"))
                    .copied()
                    .unwrap_or(0)
                    .min(100) as i32,
                credits: pilot.credits,
                inventory: pilot.inventory.clone(),
                selected: pilot.selected.clone(),
                vx: 0,
                vy: 0,
            },
            enemies: vec![],
            projectiles: vec![],
            pickups: vec![],
            effects: vec![],
            terrain_health: m.layout.iter().map(|i| m.tiles[*i].health).collect(),
            terrain_dead: vec![false; m.layout.len()],
            terrain_settled: vec![false; m.layout.len()],
            terrain_delays: vec![],
            rng: LegacyRng::new(wave << 10),
            difficulty: pilot.difficulty,
            outcome: Outcome::Playing,
            end_timer: None,
            scroll: 0,
            objectives: BTreeMap::new(),
            sounds: vec![],
            sound_events: vec![],
            mod_sounds: vec![],
            cooldowns: BTreeMap::new(),
            next_entity: 1,
            spawn_cursor: 0,
            cycle_held: false,
            bomb_held: false,
            palette_blue: false,
            special_held: false,
            player_flash: false,
            events: vec![],
        };
        out.event(
            mission.clone(),
            "on_mission_start",
            serde_json::json!({"tick":0}),
        );
        Ok(out)
    }
    pub fn pilot(&self, prior: &Pilot) -> Pilot {
        let mut p = prior.clone();
        p.credits = self.player.credits;
        p.inventory = self.player.inventory.clone();
        p.inventory
            .insert("base:energy".into(), self.player.shield.max(1) as u32);
        if p.inventory
            .contains_key(&ContentId::from("base:super_shield"))
        {
            p.inventory.insert(
                "base:super_shield".into(),
                self.player.super_shield.max(0) as u32,
            );
        }
        p.selected = self.player.selected.clone();
        p.mission = self.mission.clone();
        p
    }
    fn entity(&mut self) -> u64 {
        let n = self.next_entity;
        self.next_entity += 1;
        n
    }
    fn event(&mut self, content: ContentId, hook: &'static str, event: serde_json::Value) {
        self.events.push(HookEvent {
            content,
            hook,
            event,
        });
    }
    pub fn spawn(&mut self, id: &ContentId, x: i32, y: i32, registry: &Registry) -> Result<u64> {
        let e = registry.enemies.get(id).context("unknown enemy")?;
        ensure!(self.enemies.len() < 4096, "enemy capacity exceeded");
        let entity = self.entity();
        let (w, h) = e
            .art
            .as_ref()
            .map(|a| (a.logical_width as i32, a.logical_height as i32))
            .unwrap_or((32, 32));
        let f = e.legacy.as_ref().map(|l| &l.fields);
        let x = match f.map(|f| f[21]) {
            Some(4) => x + w,
            Some(5) => x - w,
            _ => x,
        };
        let sx = x;
        let sy = if f.is_some() { 100 - h / 2 } else { y };
        let first = e.path.first().copied().unwrap_or([0, 300]);
        let mut movement = LineMove::new(x, y, sx + first[0], sy + first[1]);
        if f.is_some() && !e.ground {
            movement.initial();
        }
        let health = if e.boss && self.difficulty <= 1 {
            e.health - (e.health >> 1)
        } else {
            e.health
        };
        self.enemies.push(Enemy {
            entity,
            definition: id.clone(),
            x,
            y,
            px: x,
            py: y,
            sx,
            sy,
            width: w,
            height: h,
            health,
            age: 0,
            cooldown: 0,
            path_index: 1,
            reversed: false,
            movement,
            frame: 0,
            art_frame: 0,
            animation_on: f.is_none_or(|f| f[10] != 1),
            animation_frames: f.map_or(1, |f| if f[10] == 2 { f[9] } else { f[7] }.max(1) as u32),
            multi: 0,
            frame_timer: f.map_or(0, |f| f[6]),
            countdown: f.map_or(0, |f| f[8] - y),
            shoot_on: false,
            shootagain: -1,
            shootcount: f.map_or(1, |f| {
                if e.boss && self.difficulty <= 1 {
                    f[16] - (f[16] >> 2)
                } else {
                    f[16]
                }
            }),
            shootflag: f.map_or(0, |f| f[15]),
            kami: 0,
            vx: 0,
            vy: 0,
        });
        self.event(
            id.clone(),
            "on_spawn",
            serde_json::json!({"entity":entity,"x":x,"y":y}),
        );
        Ok(entity)
    }
    fn projectile(
        &mut self,
        id: &ContentId,
        x: i32,
        y: i32,
        vx: i32,
        vy: i32,
        hostile: bool,
    ) -> Result<()> {
        ensure!(
            self.projectiles.len() < 8192,
            "projectile capacity exceeded"
        );
        let entity = self.entity();
        self.projectiles.push(Projectile {
            entity,
            weapon: id.clone(),
            x,
            y,
            px: x,
            py: y,
            vx,
            vy,
            hostile,
            age: 0,
            legacy: None,
            legacy_enemy: None,
        });
        Ok(())
    }
    pub fn step(
        &mut self,
        input: Input,
        registry: &Registry,
        scripts: &mut ScriptRuntime,
    ) -> Result<()> {
        if self.outcome != Outcome::Playing {
            return Ok(());
        }
        scripts.begin_tick();
        let checkpoint = self.clone();
        let script_checkpoint = scripts.checkpoints();
        let result = self
            .advance(input, registry)
            .and_then(|_| self.dispatch(registry, scripts));
        if let Err(err) = result {
            *self = checkpoint;
            scripts.restore(script_checkpoint);
            return Err(err);
        }
        Ok(())
    }
    fn advance(&mut self, input: Input, registry: &Registry) -> Result<()> {
        self.sounds.clear();
        self.sound_events.clear();
        self.mod_sounds.clear();
        self.player_flash = false;
        self.player.px = self.player.x;
        self.player.py = self.player.y;
        if let Some([x, y]) = input.absolute {
            self.player.x = x.clamp(5, 282);
            self.player.y = y.clamp(0, 160);
        } else {
            self.player.vx = accelerate(self.player.vx, input.dx, 10);
            self.player.vy = accelerate(self.player.vy, input.dy, 8);
            self.player.x = (self.player.x + self.player.vx).clamp(5, 282);
            self.player.y = (self.player.y + self.player.vy).clamp(0, 160);
        }
        let delta = ((self.player.x - self.player.px).abs() >> 2).min(3);
        if let Some(bank) = input.demo_bank {
            self.player.bank = bank.clamp(0, 6);
        } else if self.player.x < self.player.px {
            if self.player.bank < 3 + delta {
                self.player.bank += 1;
            }
        } else if self.player.x > self.player.px {
            if self.player.bank > 3 - delta {
                self.player.bank -= 1;
            }
        } else {
            self.player.bank += (3 - self.player.bank).signum();
        }
        if input.fire {
            let mut weapons: Vec<_> = self
                .player
                .inventory
                .iter()
                .filter_map(|(id, n)| {
                    if *n > 0 {
                        registry
                            .items
                            .get(id)
                            .filter(|i| !i.special && i.legacy != Some(11))
                            .and_then(|i| i.weapon.clone())
                    } else {
                        None
                    }
                })
                .chain(
                    self.player
                        .selected
                        .as_ref()
                        .and_then(|id| registry.items.get(id))
                        .and_then(|i| i.weapon.clone()),
                )
                .collect();
            weapons.sort_by_key(|id| (registry.weapons[id].legacy.unwrap_or(u32::MAX), id.clone()));
            // Original primary weapons fire in numeric order, followed by the selected special.
            if let Some(selected) = self
                .player
                .selected
                .as_ref()
                .and_then(|id| registry.items.get(id))
                .and_then(|i| i.weapon.as_ref())
            {
                weapons.retain(|id| id != selected);
                weapons.push(selected.clone());
            }
            for id in weapons {
                self.fire(&id, registry)?;
            }
        }
        if input.special {
            if let Some(id) = self.player.selected.clone() {
                if let Some(item) = registry.items.get(&id) {
                    if let Some(weapon) = item.weapon.as_ref() {
                        self.fire(weapon, registry)?;
                    } else if !self.special_held
                        && self.player.inventory.get(&id).copied().unwrap_or(0) > 0
                    {
                        if item.consumable {
                            *self.player.inventory.get_mut(&id).unwrap() -= 1;
                            if self.player.inventory[&id] == 0 {
                                self.player.selected = None;
                            }
                        }
                        self.player.shield = (self.player.shield + item.shield).clamp(0, 100);
                        self.player.credits = self.player.credits.saturating_add(item.credits);
                        self.event(id,"on_use",serde_json::json!({"entity":0,"x":self.player.x,"y":self.player.y,"tick":self.tick}));
                    }
                }
            }
        }
        self.special_held = input.special;
        if input.cycle && !self.cycle_held {
            let mut specials: Vec<_> = self
                .player
                .inventory
                .keys()
                .filter(|id| registry.items.get(*id).is_some_and(|i| i.special))
                .cloned()
                .collect();
            specials.sort_by_key(|id| (registry.items[id].legacy.unwrap_or(u32::MAX), id.clone()));
            if !specials.is_empty() {
                let next = self
                    .player
                    .selected
                    .as_ref()
                    .and_then(|id| specials.iter().position(|s| s == id))
                    .map_or(0, |i| (i + 1) % specials.len());
                self.player.selected = Some(specials[next].clone());
            }
        }
        self.cycle_held = input.cycle;
        if input.bomb && !self.bomb_held {
            let id = ContentId::from("base:mega_bomb");
            if self.player.inventory.get(&id).copied().unwrap_or(0) > 0 {
                if let Some(weapon) = registry.items.get(&id).and_then(|i| i.weapon.clone()) {
                    let before = self.projectiles.len();
                    self.fire(&weapon, registry)?;
                    if self.projectiles.len() > before {
                        *self.player.inventory.get_mut(&id).unwrap() -= 1;
                    }
                }
            }
        }
        self.bomb_held = input.bomb;
        self.scroll += 1;
        self.think_legacy_terrain(registry);
        let mission = &registry.missions[&self.mission];
        while self.spawn_cursor < mission.spawns.len()
            && mission.spawns[self.spawn_cursor].tick <= self.tick
        {
            let spawn = &mission.spawns[self.spawn_cursor];
            let enabled = if mission.legacy_map.is_some() {
                match spawn.difficulty {
                    3 => true,
                    4 => self.difficulty >= 2,
                    5 => self.difficulty >= 3,
                    _ => false,
                }
            } else {
                self.difficulty >= spawn.difficulty
            };
            if enabled {
                let (x, y) = if mission.legacy_map.is_some() {
                    let art = registry.enemies[&spawn.enemy].art.as_ref().unwrap();
                    (
                        spawn.x + 16 - art.logical_width as i32 / 2,
                        spawn.y - art.logical_height as i32 / 2,
                    )
                } else {
                    (spawn.x, spawn.y)
                };
                self.spawn(&spawn.enemy, x, y, registry)?;
            }
            self.spawn_cursor += 1;
        }
        // Ground/air enemy updates precede hostile shots, bonuses and player shots.
        let mut shots = Vec::new();
        let mut retired = Vec::new();
        let mut events = Vec::new();
        for enemy in &mut self.enemies {
            let def = &registry.enemies[&enemy.definition];
            enemy.px = enemy.x;
            enemy.py = enemy.y;
            enemy.age += 1;
            if enemy.vx != 0 || enemy.vy != 0 {
                enemy.x += enemy.vx;
                enemy.y += enemy.vy;
            } else if def.ground {
                enemy.y += 1;
                if let Some(l) = &def.legacy {
                    match l.fields[21] {
                        4 if enemy.y >= 0 => enemy.x -= def.speed,
                        5 if enemy.y >= 0 => enemy.x += def.speed,
                        _ => {}
                    }
                }
            } else {
                enemy.x = enemy.movement.x;
                enemy.y = enemy.movement.y;
                let left = enemy.movement.advance(def.speed);
                if enemy.movement.done && !def.path.is_empty() {
                    let count = def.path.len();
                    if enemy.path_index >= count {
                        if def.repeat {
                            enemy.reversed = true;
                            enemy.path_index = count.saturating_sub(1);
                        } else if def.legacy.as_ref().is_some_and(|l| l.fields[21] == 2)
                            && enemy.kami < 2
                        {
                            enemy.kami += 1;
                        } else {
                            retired.push(enemy.entity);
                        }
                    }
                    let target = if enemy.kami == 2 {
                        [self.player.x + 16 - enemy.sx, self.player.y + 16 - enemy.sy]
                    } else {
                        def.path[enemy.path_index.min(count - 1)]
                    };
                    enemy.movement = LineMove::new(
                        enemy.movement.tx,
                        enemy.movement.ty,
                        enemy.sx + target[0],
                        enemy.sy + target[1],
                    );
                    if def.legacy.is_some() {
                        enemy.movement.initial();
                    }
                    enemy.movement.advance(left);
                    if enemy.reversed {
                        enemy.path_index = enemy.path_index.saturating_sub(1);
                        let min = def
                            .legacy
                            .as_ref()
                            .map_or(0, |l| l.fields[20].max(0) as usize);
                        if enemy.path_index <= min {
                            enemy.reversed = false;
                        }
                    } else {
                        enemy.path_index += 1;
                    }
                } else if def.path.is_empty() {
                    enemy.y += def.speed;
                }
            }
            if let Some(l) = &def.legacy {
                update_legacy_animation(enemy, l);
            } else {
                enemy.frame = enemy.age / 3;
                enemy.art_frame = enemy.frame;
                enemy.shoot_on = true;
            }
            if enemy.shoot_on
                && (def.legacy.is_some()
                    || (enemy.health > 0 && enemy.y > -enemy.height && enemy.y < 200))
            {
                if let Some(weapon) = &def.weapon {
                    if let Some(l) = &def.legacy {
                        match enemy.shootagain {
                            -1 => {
                                enemy.shootflag -= 1;
                                if enemy.shootflag < 0 {
                                    enemy.shootflag = l.fields[3];
                                    for gun in 0..l.fields[22].max(0) as usize {
                                        shots.push((
                                            weapon.clone(),
                                            enemy.x + l.gun_x[gun] as i32,
                                            enemy.y + l.gun_y[gun] as i32,
                                            Some((l.shoot_type[gun], enemy.entity, def.speed, gun)),
                                        ));
                                        let sx = enemy.x + l.gun_x[gun] as i32;
                                        let sy = enemy.y + l.gun_y[gun] as i32;
                                        if (0..320).contains(&sx) && (0..200).contains(&sy) {
                                            play_legacy_sound(
                                                &mut self.rng,
                                                &mut self.sounds,
                                                &mut self.sound_events,
                                                match l.shoot_type[gun] {
                                                    4 => "FX_ENEMYMISSLE",
                                                    5 => "FX_ENEMYLASER",
                                                    7 => "FX_ENEMYPLASMA",
                                                    _ => "FX_ENEMYSHOT",
                                                },
                                            );
                                            position_sound(
                                                &mut self.sound_events,
                                                sx,
                                                sy,
                                                self.player.x + 16,
                                                self.player.y + 16,
                                            );
                                        }
                                    }
                                    enemy.shootcount -= 1;
                                    if enemy.shootcount < 1 {
                                        enemy.shootagain = l.fields[17];
                                    }
                                }
                            }
                            0 => {
                                enemy.shootagain = -1;
                                enemy.shootcount = l.fields[16];
                                enemy.shootflag = l.fields[3];
                            }
                            _ => enemy.shootagain -= 1,
                        }
                    } else if enemy.cooldown == 0 {
                        shots.push((
                            weapon.clone(),
                            enemy.x + enemy.width / 2,
                            enemy.y + enemy.height,
                            Some((-1, enemy.entity, def.speed, 0)),
                        ));
                        enemy.cooldown = def.cooldown;
                    } else {
                        enemy.cooldown -= 1;
                    }
                }
            }
            if def.ground
                && def.legacy.as_ref().is_some_and(|l| {
                    enemy.y > 211
                        || (l.fields[21] == 4 && enemy.x < -enemy.width / 2)
                        || (l.fields[21] == 5 && enemy.x > 335)
                })
            {
                retired.push(enemy.entity);
                continue;
            }
            if def.boss && enemy.health < 50 && (self.tick + 1) & 2 != 0 && def.legacy.is_some() {
                self.rng.next_value();
                self.rng.next_value();
            }
            if !def.ground && contains(enemy, self.player.x + 16, self.player.y + 16) {
                enemy.health -= 16;
                damage_player(
                    &mut self.player,
                    enemy.width.max(enemy.height) >> 2,
                    self.difficulty,
                    &mut self.rng,
                    &mut self.sounds,
                    &mut self.sound_events,
                );
                if def.legacy.is_some() {
                    self.rng.next_value();
                    self.rng.next_value();
                    play_legacy_sound(
                        &mut self.rng,
                        &mut self.sounds,
                        &mut self.sound_events,
                        "FX_CRASH",
                    );
                }
            }
            if enemy.health <= 0 {
                if let Some(legacy) = &def.legacy {
                    play_legacy_sound(
                        &mut self.rng,
                        &mut self.sounds,
                        &mut self.sound_events,
                        "FX_AIREXPLO",
                    );
                    position_sound(
                        &mut self.sound_events,
                        enemy.x + enemy.width / 2,
                        enemy.x + enemy.width / 2,
                        self.player.x + 16,
                        self.player.y + 16,
                    );
                    let random_count = match legacy.fields[2] {
                        2 | 6 => 2 * (enemy.width >> 4) * (enemy.height >> 4),
                        4 => 3,
                        5 => 3 * (enemy.width >> 4) * (enemy.height >> 4),
                        _ => 0,
                    };
                    for _ in 0..random_count {
                        self.rng.next_value();
                    }
                }
                self.player.credits = self.player.credits.saturating_add(def.reward);
                self.effects.push(Effect {
                    x: enemy.x + enemy.width / 2,
                    y: enemy.y + enemy.height / 2,
                    age: 0,
                });
                events.push(HookEvent {
                    content: enemy.definition.clone(),
                    hook: "on_death",
                    event: serde_json::json!({"entity":enemy.entity,"x":enemy.x,"y":enemy.y}),
                });
                let mut drops: Vec<_> = def.drop.iter().cloned().collect();
                if def.legacy.as_ref().is_some_and(|l| l.fields[2] == 8) {
                    drops.insert(0, ContentId::from("base:itembuy6"));
                }
                for drop in drops {
                    let legacy = if def.legacy.is_some() {
                        if self.pickups.len() >= 12
                            || (drop == ContentId::from("base:itembuy6")
                                && self.pickups.iter().filter(|p| p.item == drop).count() > 9)
                        {
                            continue;
                        }
                        let position = self.rng.next_value() as usize % 16;
                        Some(LegacyPickup {
                            x: enemy.x + 16,
                            y: enemy.y,
                            position,
                            frame: 0,
                            art_frame: 0,
                            countdown: None,
                        })
                    } else {
                        None
                    };
                    let id = self.next_entity;
                    self.next_entity += 1;
                    self.pickups.push(Pickup {
                        entity: id,
                        item: drop,
                        x: enemy.x,
                        y: enemy.y,
                        legacy,
                    });
                }
                retired.push(enemy.entity);
            } else if enemy.y > 240 || enemy.x < -enemy.width - 40 || enemy.x > 360 {
                retired.push(enemy.entity);
            }
            if !retired.contains(&enemy.entity) {
                events.push(HookEvent{content:enemy.definition.clone(),hook:"on_tick",event:serde_json::json!({"entity":enemy.entity,"x":enemy.x,"y":enemy.y,"health":enemy.health,"tick":self.tick,"player_x":self.player.x,"player_y":self.player.y})});
            }
        }
        self.events.extend(events);
        self.enemies.retain(|e| !retired.contains(&e.entity));
        for (id, x, y, legacy) in shots {
            if legacy.is_none_or(|(kind, _, _, _)| kind < 0)
                || ((0..320).contains(&x) && (0..200).contains(&y))
            {
                let entity = legacy.map_or(0, |(_, entity, _, _)| entity);
                self.event(id.clone(),"on_fire",serde_json::json!({"entity":entity,"x":x,"y":y,"hostile":true,"tick":self.tick}));
                if let Some(enemy) = self.enemies.iter().find(|e| e.entity == entity) {
                    let definition = enemy.definition.clone();
                    self.event(definition,"on_fire",serde_json::json!({"entity":entity,"weapon":id,"x":x,"y":y,"hostile":true,"tick":self.tick}));
                }
            }
            if let Some((kind, entity, speed, gun)) = legacy.filter(|(kind, _, _, _)| *kind >= 0) {
                self.enemy_projectile(&id, x, y, kind, entity, speed, gun)?;
                continue;
            }
            let speed = registry.weapons[&id].speed;
            let dx = self.player.x + 16 - x;
            let dy = self.player.y + 16 - y;
            let norm = dx.abs().max(dy.abs()).max(1);
            self.projectile(&id, x, y, dx * speed / norm, dy * speed / norm, true)?;
        }
        for cooldown in self.cooldowns.values_mut() {
            *cooldown = cooldown.saturating_sub(1);
        }
        let mut dead_shots = Vec::new();
        let mut hit_events = Vec::new();
        self.think_enemy_projectiles(registry)?;
        for p in self
            .projectiles
            .iter_mut()
            .filter(|p| p.hostile && p.legacy_enemy.is_none())
        {
            p.px = p.x;
            p.py = p.y;
            p.x += p.vx;
            p.y += p.vy;
            p.age += 1;
            if (p.x - (self.player.x + 16)).abs() < 10 && (p.y - (self.player.y + 16)).abs() < 10 {
                damage_player(
                    &mut self.player,
                    registry.weapons[&p.weapon].damage,
                    self.difficulty,
                    &mut self.rng,
                    &mut self.sounds,
                    &mut self.sound_events,
                );
                dead_shots.push(p.entity);
            }
        }
        let mut picked = Vec::new();
        for pickup in &mut self.pickups {
            let collision = if let Some(legacy) = &mut pickup.legacy {
                const X: [i32; 16] = [-1, 0, 1, 2, 3, 3, 3, 2, 1, 0, -1, -2, -3, -3, -3, -2];
                const Y: [i32; 16] = [-3, -3, -3, -2, -1, 0, 1, 2, 3, 3, 3, 2, 1, 0, -1, -2];
                legacy.art_frame = legacy.frame;
                pickup.x = legacy.x - 8 + X[legacy.position];
                pickup.y = legacy.y - 8 + Y[legacy.position];
                legacy.y += 1;
                if self.tick & 1 != 0 {
                    legacy.position = (legacy.position + 1) % 16;
                    legacy.frame = (legacy.frame + 1)
                        % registry.items[&pickup.item]
                            .art
                            .as_ref()
                            .map_or(1, |a| a.frames.max(1));
                }
                legacy.countdown.is_none()
                    && self.player.shield > 0
                    && legacy.x > self.player.x
                    && legacy.x < self.player.x + 32
                    && legacy.y > self.player.y
                    && legacy.y < self.player.y + 32
            } else {
                pickup.y += 1;
                (pickup.x - self.player.x).abs() < 24 && (pickup.y - self.player.y).abs() < 24
            };
            if collision {
                let item = &registry.items[&pickup.item];
                if item.credits == 0
                    && (self.player.inventory.contains_key(&pickup.item)
                        || self.player.inventory.len() < 20)
                {
                    let amount = self
                        .player
                        .inventory
                        .entry(pickup.item.clone())
                        .or_default();
                    *amount = amount
                        .saturating_add(item.initial_count)
                        .min(item.max_count);
                    if item.special && self.player.selected.is_none() {
                        self.player.selected = Some(pickup.item.clone());
                    }
                }
                if item.legacy == Some(15) {
                    self.player.super_shield = 100;
                } else {
                    self.player.shield = (self.player.shield + item.shield).min(100);
                }
                self.player.credits = self.player.credits.saturating_add(item.credits);
                if pickup.legacy.is_some() {
                    play_legacy_sound(
                        &mut self.rng,
                        &mut self.sounds,
                        &mut self.sound_events,
                        "FX_BONUS",
                    );
                }
                if item.credits > 0 && pickup.legacy.is_some() {
                    pickup.legacy.as_mut().unwrap().countdown = Some(50);
                } else {
                    picked.push(pickup.entity);
                }
                hit_events.push(HookEvent {
                    content: pickup.item.clone(),
                    hook: "on_pickup",
                    event: serde_json::json!({"entity":pickup.entity}),
                });
            }
            if let Some(legacy) = &mut pickup.legacy {
                if let Some(countdown) = &mut legacy.countdown {
                    *countdown = countdown.saturating_sub(1);
                    if *countdown == 0 {
                        picked.push(pickup.entity);
                    }
                }
                if legacy.y - 8 > 200 {
                    picked.push(pickup.entity);
                }
            }
        }
        self.pickups
            .retain(|p| p.y < 220 && !picked.contains(&p.entity));
        self.think_legacy_projectiles(registry)?;
        for p in self
            .projectiles
            .iter_mut()
            .filter(|p| !p.hostile && p.legacy.is_none())
        {
            p.px = p.x;
            p.py = p.y;
            p.age += 1;
            let weapon = &registry.weapons[&p.weapon];
            if matches!(weapon.behavior, WeaponBehavior::Homing) {
                if let Some(target) = self.enemies.iter().find(|e| {
                    e.health > 0
                        && target_matches(&weapon.target, registry.enemies[&e.definition].ground)
                }) {
                    p.vx = (target.x + target.width / 2 - p.x)
                        .clamp(-weapon.speed.abs(), weapon.speed.abs());
                }
            }
            p.x += p.vx;
            p.y += p.vy;
            if matches!(weapon.behavior, WeaponBehavior::Beam) {
                p.x = self.player.x + 16;
                for e in &mut self.enemies {
                    if target_matches(&weapon.target, registry.enemies[&e.definition].ground)
                        && p.x > e.x
                        && p.x < e.x + e.width
                        && e.y < self.player.y
                    {
                        e.health -= weapon.damage;
                        hit_events.push(HookEvent{content:e.definition.clone(),hook:"on_hit",event:serde_json::json!({"entity":e.entity,"projectile":p.entity,"weapon":p.weapon,"damage":weapon.damage,"x":p.x,"y":e.y,"health":e.health})});
                        hit_events.push(HookEvent{content:p.weapon.clone(),hook:"on_hit",event:serde_json::json!({"entity":e.entity,"projectile":p.entity,"damage":weapon.damage,"x":p.x,"y":e.y})});
                    }
                }
                if p.age > 1 {
                    dead_shots.push(p.entity);
                }
            } else if let Some(e) = self.enemies.iter_mut().find(|e| {
                e.health > 0
                    && target_matches(&weapon.target, registry.enemies[&e.definition].ground)
                    && contains(e, p.x, p.y)
            }) {
                e.health -= weapon.damage;
                hit_events.push(HookEvent{content:e.definition.clone(),hook:"on_hit",event:serde_json::json!({"entity":e.entity,"projectile":p.entity,"weapon":p.weapon,"damage":weapon.damage,"x":p.x,"y":p.y,"health":e.health})});
                hit_events.push(HookEvent{content:p.weapon.clone(),hook:"on_hit",event:serde_json::json!({"entity":e.entity,"projectile":p.entity,"damage":weapon.damage,"x":p.x,"y":p.y})});
                dead_shots.push(p.entity);
            } else if !matches!(weapon.target, Target::Air) {
                let col = (p.x - 16) / 32;
                let row = (p.y + mission.layout.len() as i32 / mission.columns.max(1) as i32 * 32
                    - 200
                    - self.scroll)
                    / 32;
                if col >= 0 && col < mission.columns as i32 && row >= 0 {
                    let pos = row as usize * mission.columns as usize + col as usize;
                    if pos < self.terrain_health.len()
                        && self.terrain_health[pos] > 0
                        && !self.terrain_dead[pos]
                    {
                        self.terrain_health[pos] -= weapon.damage;
                        dead_shots.push(p.entity);
                        if self.terrain_health[pos] <= 0 {
                            self.terrain_dead[pos] = true;
                            self.player.credits = self
                                .player
                                .credits
                                .saturating_add(mission.tiles[mission.layout[pos]].reward);
                            self.effects.push(Effect {
                                x: p.x,
                                y: p.y,
                                age: 0,
                            });
                        }
                    }
                }
            }
        }
        self.events.extend(hit_events);
        self.projectiles.retain(|p| {
            !dead_shots.contains(&p.entity)
                && (p.legacy.is_some()
                    || (p.x >= -32 && p.x <= 352 && p.y >= -64 && p.y <= 240 && p.age < 300))
        });
        for e in &mut self.effects {
            e.age += 1;
        }
        self.effects.retain(|e| e.age < 20);
        self.tick += 1;
        if self.player.shield <= 0 {
            self.outcome = Outcome::Failed;
        } else if mission.auto_complete {
            if mission.legacy_map.is_some() {
                // ENEMY_Remove starts the original 60-tick departure only
                // after the final spawn has been visited and all ships left.
                if self.spawn_cursor == mission.spawns.len() && self.enemies.is_empty() {
                    match self.end_timer {
                        None => self.end_timer = Some(60),
                        Some(0) => self.outcome = Outcome::Complete,
                        Some(n) => self.end_timer = Some(n - 1),
                    }
                }
            } else if self.tick >= mission.duration
                && self.spawn_cursor == mission.spawns.len()
                && self
                    .enemies
                    .iter()
                    .all(|e| !registry.enemies[&e.definition].boss)
            {
                self.outcome = Outcome::Complete;
            }
        }
        self.event(self.mission.clone(),"on_tick",serde_json::json!({"tick":self.tick,"player_x":self.player.x,"player_y":self.player.y,"enemies":self.enemies.len()}));
        if self.outcome != Outcome::Playing {
            self.event(
                self.mission.clone(),
                "on_mission_end",
                serde_json::json!({"success":self.outcome==Outcome::Complete,"tick":self.tick}),
            );
        }
        if mission.legacy_map.is_some() && self.tick >= 3 && self.tick % 2 == 1 {
            // Palette index 254 consumes the original shared RNG, even when no frame is rendered.
            self.palette_blue = self.rng.next_value() % 3 == 0;
        }
        Ok(())
    }
    fn fire(&mut self, id: &ContentId, registry: &Registry) -> Result<()> {
        let Some(w) = registry.weapons.get(id) else {
            return Ok(());
        };
        if self.cooldowns.get(id).copied().unwrap_or(0) > 0 {
            return Ok(());
        }
        self.cooldowns.insert(id.clone(), w.cooldown);
        if let Some(index) = w.legacy {
            if let Some(legacy) = crate::legacy_tables::weapons()
                .into_iter()
                .find(|w| w.index == index)
            {
                self.fire_legacy(id, &legacy, registry)?;
                return Ok(());
            }
        }
        let offsets = if w.offsets.is_empty() {
            vec![[0, 0]]
        } else {
            w.offsets.clone()
        };
        for [x, y] in offsets {
            self.projectile(
                id,
                self.player.x + 16 + x,
                self.player.y + y,
                0,
                -w.speed.max(1),
                false,
            )?;
        }
        self.event(
            id.clone(),
            "on_fire",
            serde_json::json!({"entity":0,"hostile":false,"x":self.player.x+16,"y":self.player.y,"tick":self.tick}),
        );
        Ok(())
    }
    fn enemy_projectile(
        &mut self,
        id: &ContentId,
        x: i32,
        y: i32,
        kind: i16,
        enemy: u64,
        enemy_speed: i32,
        gun: usize,
    ) -> Result<()> {
        if !(0..320).contains(&x)
            || !(0..200).contains(&y)
            || self
                .projectiles
                .iter()
                .filter(|p| p.legacy_enemy.is_some())
                .count()
                >= 80
        {
            return Ok(());
        }
        let (asset, frames, maximum_speed, damage, offset_y) = match kind {
            0 => (0x101d6, 2, 6, 1, 4),
            1..=3 => (0x101d6, 2, 6, 2, 4),
            4 => (0x101d4, 2, 10, 4, 0),
            5 => (0x10241, 4, 6, 12, 0),
            6 => (0x101d1, 2, 0, 16, 0),
            7 => (0x10251, 1, 10, 15, 0),
            8 => (0x1024d, 4, 6, 1, 4),
            _ => {
                return Err(anyhow::anyhow!(
                    "unknown original enemy projectile type {kind}"
                ));
            }
        };
        let start = [x - if kind == 6 { 0 } else { 4 }, y - offset_y];
        let mut target = [start[0], 200];
        let speed = match kind {
            0 | 8 => 1,
            1..=3 => 3,
            4 => enemy_speed + 1,
            5 => enemy_speed,
            6 => 150,
            7 => 8,
            _ => 1,
        };
        match kind {
            0 | 8 => target = [self.player.x + 16, self.player.y + 16],
            2 => target = [start[0] - 32, start[1] + 32],
            3 => target = [start[0] + 32, start[1] + 32],
            6 => target = [320, 200],
            _ => {}
        }
        let mut movement = LineMove::new(start[0], start[1], target[0], target[1]);
        movement.advance_shot(1);
        if !(0..320).contains(&movement.x) || !(0..200).contains(&movement.y) {
            return Ok(());
        }
        self.projectile(id, movement.x, movement.y, 0, 0, true)?;
        self.projectiles.last_mut().unwrap().legacy_enemy = Some(EnemyProjectile {
            movement,
            kind,
            asset,
            frames,
            frame: 0,
            art_frame: 0,
            speed,
            maximum_speed,
            damage,
            position: if kind == 6 {
                self.rng.next_value() as usize % 16
            } else {
                0
            },
            enemy,
            gun,
        });
        Ok(())
    }
    fn think_enemy_projectiles(&mut self, registry: &Registry) -> Result<()> {
        const X: [i32; 16] = [-1, 0, 1, 2, 3, 3, 3, 2, 1, 0, -1, -2, -3, -3, -3, -2];
        const Y: [i32; 16] = [-3, -3, -3, -2, -1, 0, 1, 2, 3, 3, 3, 2, 1, 0, -1, -2];
        let mut retired = Vec::new();
        for p in &mut self.projectiles {
            let Some(state) = p.legacy_enemy.as_mut() else {
                continue;
            };
            p.px = p.x;
            p.py = p.y;
            p.age += 1;
            state.art_frame = state.frame;
            state.frame += 1;
            if state.kind == 5 {
                if let Some(enemy) = self
                    .enemies
                    .iter()
                    .find(|e| e.entity == state.enemy)
                    .filter(|_| state.frame < state.frames)
                {
                    let legacy = registry.enemies[&enemy.definition].legacy.as_ref().unwrap();
                    p.x = enemy.x + legacy.gun_x[state.gun] as i32 - 4;
                    p.y = enemy.y + legacy.gun_y[state.gun] as i32;
                    state.movement.ty = 200;
                    if (p.x - self.player.x - 16).abs() < 16 && p.y < self.player.y + 16 {
                        state.movement.ty = self.player.y + 16 + self.rng.next_value() % 4 - 2;
                        damage_player(
                            &mut self.player,
                            state.damage,
                            self.difficulty,
                            &mut self.rng,
                            &mut self.sounds,
                            &mut self.sound_events,
                        );
                    }
                } else {
                    retired.push(p.entity);
                }
            } else {
                state.frame %= state.frames;
                if state.maximum_speed != 0 {
                    p.x = state.movement.x;
                    p.y = state.movement.y;
                    state.movement.advance_shot(state.speed);
                    if state.speed < state.maximum_speed {
                        state.speed += 1;
                    }
                } else {
                    state.speed -= 1;
                    if state.speed > 0 {
                        p.x = state.movement.x + X[state.position];
                        p.y = state.movement.y + Y[state.position];
                        state.movement.y += 1;
                        state.position = (state.position + 1) % 16;
                    } else {
                        retired.push(p.entity);
                    }
                }
                if !(0..320).contains(&p.x) || !(0..200).contains(&p.y) {
                    retired.push(p.entity);
                }
                if (p.x - self.player.x - 16).abs() < 16 && (p.y - self.player.y - 16).abs() < 16 {
                    damage_player(
                        &mut self.player,
                        state.damage,
                        self.difficulty,
                        &mut self.rng,
                        &mut self.sounds,
                        &mut self.sound_events,
                    );
                    retired.push(p.entity);
                }
            }
        }
        self.projectiles.retain(|p| !retired.contains(&p.entity));
        Ok(())
    }
    fn terrain_window(&self, registry: &Registry) -> (usize, i32) {
        let mission = &registry.missions[&self.mission];
        let rows = mission.layout.len() / mission.columns.max(1) as usize;
        let initial = rows.saturating_sub(8);
        let wraps = if self.scroll <= 56 {
            0
        } else {
            1 + (self.scroll - 57) / 32
        };
        (
            initial.saturating_sub(wraps as usize),
            -56 + self.scroll - wraps * 32,
        )
    }
    fn terrain_damage_neighbors(&mut self, position: usize, damage: i32, registry: &Registry) {
        let mission = &registry.missions[&self.mission];
        let columns = mission.columns.max(1) as usize;
        let column = position % columns;
        let neighbors = [
            if column > 0 {
                position.checked_sub(1)
            } else {
                None
            },
            position.checked_sub(columns),
            if column + 1 < columns {
                Some(position + 1)
            } else {
                None
            },
        ];
        for position in neighbors.into_iter().flatten() {
            if position < mission.layout.len()
                && mission.tiles[mission.layout[position]].destroyed.is_some()
                && !self.terrain_dead[position]
            {
                self.terrain_health[position] -= damage;
            }
        }
    }
    fn think_legacy_terrain(&mut self, registry: &Registry) {
        let mission = &registry.missions[&self.mission];
        if mission.legacy_map.is_none() || mission.layout.is_empty() {
            return;
        }
        let columns = mission.columns.max(1) as usize;
        let (row, y) = self.terrain_window(registry);
        let start = row * columns;
        let end = (start + 8 * columns).min(mission.layout.len());
        for position in start..end {
            if self.terrain_health[position] < 0 && !self.terrain_dead[position] {
                let x = 16 + (position % columns) as i32 * 32;
                let y = y + ((position - start) / columns) as i32 * 32;
                play_legacy_sound(
                    &mut self.rng,
                    &mut self.sounds,
                    &mut self.sound_events,
                    "FX_GEXPLO",
                );
                position_sound(
                    &mut self.sound_events,
                    x + 16,
                    y + 16,
                    self.player.x + 16,
                    self.player.y + 16,
                );
                self.terrain_damage_neighbors(position, 5, registry);
                self.player.credits = self
                    .player
                    .credits
                    .saturating_add(mission.tiles[mission.layout[position]].reward);
                self.terrain_delays.push(TerrainDelay {
                    position,
                    frames: 10,
                });
                self.effects.push(Effect {
                    x: x + 16,
                    y: y + 16,
                    age: 0,
                });
                // TILE_Explode changes its collision item immediately. Artwork waits
                // for the delayed explosion and its second chain-damage pass.
                self.terrain_dead[position] = true;
            }
        }
        let delays = std::mem::take(&mut self.terrain_delays);
        for mut delay in delays {
            if delay.position.saturating_sub(start) > 8 * columns {
                continue;
            }
            if delay.frames < 0 {
                self.rng.next_value(); // Ground sparkle horizontal offset.
                self.terrain_damage_neighbors(delay.position, 20, registry);
                self.terrain_settled[delay.position] = true;
            } else {
                delay.frames -= 1;
                self.terrain_delays.push(delay);
            }
        }
    }
    fn think_legacy_projectiles(&mut self, registry: &Registry) -> Result<()> {
        let mut retired = Vec::new();
        let libs = crate::legacy_tables::weapons();
        for n in 0..self.projectiles.len() {
            let mut p = self.projectiles[n].clone();
            let Some(mut state) = p.legacy.take() else {
                continue;
            };
            if p.hostile {
                continue;
            }
            let weapon = &registry.weapons[&p.weapon];
            let Some(lib) = libs.iter().find(|l| Some(l.index) == weapon.legacy) else {
                continue;
            };
            p.px = p.x;
            p.py = p.y;
            p.age += 1;
            state.art_frame = state.frame;
            if lib.beam == 1 && p.age > 1 {
                retired.push(p.entity);
                continue;
            }
            let (half_width, half_height) = weapon
                .art
                .as_ref()
                .map(|a| (a.logical_width as i32 / 2, a.logical_height as i32 / 2))
                .unwrap_or((0, 0));
            p.x = state.movement.x - if lib.beam == 1 { 0 } else { half_width };
            p.y = state.movement.y
                - if lib.beam == 0 && lib.moving {
                    half_height
                } else {
                    0
                };
            // The original S_BEAM damage pass tests the uncorrected launch
            // column, then applies player-follow offsets to presentation.
            if lib.beam == 2 {
                for enemy in &mut self.enemies {
                    if p.x > enemy.x
                        && p.x < enemy.x + enemy.width - 1
                        && enemy.y < self.player.y + 16
                        && enemy.y > -30
                    {
                        enemy.health -= weapon.damage;
                        if enemy.health != -1 {
                            state.movement.ty = enemy.y + enemy.height / 2;
                            break;
                        }
                    }
                }
            }
            if lib.follow_x {
                p.x += self.player.x + 16 - state.start[0];
            }
            if lib.follow_y {
                p.y += self.player.y + 16 - state.start[1];
            }
            let mut skip_collision = false;
            if lib.moving && (p.y + 16 < 0 || p.x < 0 || p.x > 320 || p.y > 200) {
                state.movement.done = true;
                skip_collision = true;
            }
            if !skip_collision && !state.delay {
                if state.speed < lib.maxspeed {
                    state.speed += 1;
                }
                state.frame += 1;
                if state.frame >= lib.frames {
                    if lib.moving {
                        state.frame = lib.startframe;
                    } else {
                        state.movement.done = true;
                        skip_collision = true;
                    }
                }
            }
            if state.hit {
                state.movement.done = true;
                skip_collision = true;
            }
            // A plotted shot tests its endpoint before retiring, even if MoveSobj
            // marked it done in the preceding step.
            if !skip_collision && !lib.effect {
                let enemy = self
                    .enemies
                    .iter_mut()
                    .filter(|e| visible(e))
                    .take(30)
                    .find(|e| {
                        let ground = registry.enemies[&e.definition].ground;
                        contains(e, p.x, p.y)
                            && match lib.target {
                                1 => !ground,
                                2 | 4 => ground,
                                _ => true,
                            }
                    });
                if let Some(enemy) = enemy {
                    let damage = if lib.target == 4 { 5 } else { weapon.damage };
                    enemy.health -= damage;
                    if self.difficulty == 0 && matches!(lib.target, 1 | 2) {
                        enemy.health -= damage;
                    }
                    state.hit = true;
                    if matches!(lib.target, 0 | 1 | 3) {
                        self.rng.next_value();
                    }
                    let entity = enemy.entity;
                    let enemy_id = enemy.definition.clone();
                    let health = enemy.health;
                    self.event(enemy_id,"on_hit",serde_json::json!({"entity":entity,"projectile":p.entity,"weapon":p.weapon,"damage":damage,"x":p.x,"y":p.y,"health":health}));
                    self.event(p.weapon.clone(),"on_hit",serde_json::json!({"entity":entity,"projectile":p.entity,"damage":damage,"x":p.x,"y":p.y}));
                } else if matches!(lib.target, 0 | 2 | 4) {
                    let mission = &registry.missions[&self.mission];
                    let col = (p.x - 16).div_euclid(32);
                    let row = (p.y
                        + mission.layout.len() as i32 / mission.columns.max(1) as i32 * 32
                        - 200
                        - self.scroll)
                        .div_euclid(32);
                    if col >= 0 && col < mission.columns as i32 && row >= 0 {
                        let pos = row as usize * mission.columns as usize + col as usize;
                        if pos < self.terrain_health.len()
                            && mission.tiles[mission.layout[pos]].destroyed.is_some()
                            && !self.terrain_dead[pos]
                        {
                            self.terrain_health[pos] -= weapon.damage;
                            if lib.target != 4 {
                                self.rng.next_value();
                            }
                            state.movement.done = true;
                        }
                    }
                }
            }
            if state.movement.done {
                if state.delay {
                    state.delay = false;
                    state.movement = LineMove::new(
                        state.movement.x,
                        state.movement.y,
                        state.movement.x + self.rng.next_value() % 32 - 16,
                        0,
                    );
                } else if lib.index == 11 {
                    for enemy in &mut self.enemies {
                        enemy.health -= weapon.damage;
                    }
                    for (health, dead) in self.terrain_health.iter_mut().zip(&self.terrain_dead) {
                        if !dead {
                            *health -= weapon.damage;
                        }
                    }
                    retired.extend(
                        self.projectiles
                            .iter()
                            .filter(|p| p.hostile)
                            .map(|p| p.entity),
                    );
                    retired.push(p.entity);
                    continue;
                } else if lib.index != 5 {
                    retired.push(p.entity);
                    continue;
                }
            }
            if lib.moving {
                if lib.plot {
                    state.movement.advance_shot(state.speed);
                } else {
                    state.movement.y -= state.speed;
                    if state.movement.y < 0 {
                        state.movement.done = true;
                        state.hit = true;
                    }
                }
            }
            p.legacy = Some(state);
            self.projectiles[n] = p;
        }
        self.projectiles.retain(|p| !retired.contains(&p.entity));
        Ok(())
    }
    fn fire_legacy(
        &mut self,
        id: &ContentId,
        lib: &crate::legacy_tables::LegacyWeapon,
        registry: &Registry,
    ) -> Result<()> {
        use crate::legacy_tables::{O_GUN1, O_GUN2, O_GUN3};
        if self
            .projectiles
            .iter()
            .filter(|p| !p.hostile && p.legacy.is_some())
            .count()
            >= 70
        {
            return Ok(());
        }
        let center = [self.player.x + 16, self.player.y + 16];
        let bank = self.player.bank.clamp(0, 6) as usize;
        let mut start = center;
        let mut offsets = vec![0];
        let mut target = [center[0], 0];
        let mut initial_frame = None;
        match lib.index {
            0 => {
                self.player_flash = true;
                play_legacy_sound(
                    &mut self.rng,
                    &mut self.sounds,
                    &mut self.sound_events,
                    "FX_GUN",
                );
                offsets = vec![O_GUN1[bank], -O_GUN1[bank] - 1];
            }
            1 => play_legacy_sound(
                &mut self.rng,
                &mut self.sounds,
                &mut self.sound_events,
                "FX_GUN",
            ),
            2 => {
                self.player_flash = true;
                play_legacy_sound(
                    &mut self.rng,
                    &mut self.sounds,
                    &mut self.sound_events,
                    "FX_GUN",
                );
                offsets = vec![O_GUN3[bank], -O_GUN3[bank]];
            }
            3 => {
                play_legacy_sound(
                    &mut self.rng,
                    &mut self.sounds,
                    &mut self.sound_events,
                    "FX_MISSLE",
                );
                offsets = vec![0, 0];
            }
            4 | 5 => {
                let candidates: Vec<_> = self
                    .enemies
                    .iter()
                    .enumerate()
                    .filter(|(_, e)| {
                        visible(e) && (lib.index == 4 || !registry.enemies[&e.definition].ground)
                    })
                    .map(|(n, _)| n)
                    .collect();
                if candidates.is_empty() {
                    if lib.index == 5 {
                        play_legacy_sound(
                            &mut self.rng,
                            &mut self.sounds,
                            &mut self.sound_events,
                            "FX_NOSHOOT",
                        );
                    }
                    return Ok(());
                }
                let pos = candidates[self.rng.next_value() as usize % candidates.len()];
                play_legacy_sound(
                    &mut self.rng,
                    &mut self.sounds,
                    &mut self.sound_events,
                    if lib.index == 5 {
                        "FX_TURRET"
                    } else {
                        "FX_GUN"
                    },
                );
                if lib.index == 4 {
                    initial_frame = Some(self.rng.next_value() as u32 % lib.frames);
                }
                let enemy = &mut self.enemies[pos];
                if lib.index == 4 {
                    target = [
                        self.rng.next_value() % enemy.width + enemy.x - 1,
                        self.rng.next_value() % enemy.height + enemy.height / 2 + enemy.y - 1,
                    ];
                } else {
                    enemy.health -= lib.damage;
                    start = [
                        self.rng.next_value() % enemy.width + enemy.movement.x - 1,
                        self.rng.next_value() % enemy.height + enemy.movement.y - 1,
                    ];
                    target = center;
                }
            }
            6..=8 => {
                play_legacy_sound(
                    &mut self.rng,
                    &mut self.sounds,
                    &mut self.sound_events,
                    if lib.index == 6 {
                        "FX_GUN"
                    } else {
                        "FX_MISSLE"
                    },
                );
                offsets = vec![O_GUN2[bank], -O_GUN2[bank]];
            }
            9 => play_legacy_sound(
                &mut self.rng,
                &mut self.sounds,
                &mut self.sound_events,
                "FX_MISSLE",
            ),
            10 => {
                play_legacy_sound(
                    &mut self.rng,
                    &mut self.sounds,
                    &mut self.sound_events,
                    "FX_GUN",
                );
                start[0] -= 4;
            }
            11 => {
                play_legacy_sound(
                    &mut self.rng,
                    &mut self.sounds,
                    &mut self.sound_events,
                    "FX_GUN",
                );
                target = [160, 75];
            }
            12 => play_legacy_sound(
                &mut self.rng,
                &mut self.sounds,
                &mut self.sound_events,
                "FX_PULSE",
            ),
            13 => {
                play_legacy_sound(
                    &mut self.rng,
                    &mut self.sounds,
                    &mut self.sound_events,
                    "FX_LASER",
                );
                offsets = vec![O_GUN3[bank], -O_GUN3[bank]];
                target[1] = -24;
            }
            14 => {
                play_legacy_sound(
                    &mut self.rng,
                    &mut self.sounds,
                    &mut self.sound_events,
                    "FX_LASER",
                );
                start[1] -= 24;
                target[1] = -24;
            }
            _ => {}
        }
        for (shot_number, offset) in offsets.into_iter().enumerate() {
            if self
                .projectiles
                .iter()
                .filter(|p| !p.hostile && p.legacy.is_some())
                .count()
                >= 70
            {
                break;
            }
            let x = start[0] + offset;
            let y = start[1];
            let frame = if lib.index <= 1 {
                self.rng.next_value() as u32 % lib.frames.max(1)
            } else {
                initial_frame.unwrap_or(0)
            };
            let mut target = target;
            if lib.index == 3 {
                target = [
                    x + if shot_number == 0 {
                        self.rng.next_value() % 16 + 10
                    } else {
                        -self.rng.next_value() % 16 - 10
                    },
                    y + 5,
                ];
            } else if lib.index != 4 && lib.index != 5 && lib.index != 11 {
                target[0] = x;
            }
            self.projectile(id, x, y, 0, -lib.speed, false)?;
            self.projectiles.last_mut().unwrap().legacy = Some(LegacyProjectile {
                movement: LineMove::new(x, y, target[0], target[1]),
                speed: lib.speed,
                frame,
                art_frame: frame,
                delay: lib.delay,
                hit: false,
                start: center,
            });
        }
        self.event(
            id.clone(),
            "on_fire",
            serde_json::json!({"entity":0,"hostile":false,"x":center[0],"y":center[1],"tick":self.tick}),
        );
        Ok(())
    }
    fn dispatch(&mut self, registry: &Registry, scripts: &mut ScriptRuntime) -> Result<()> {
        let mut processed = 0usize;
        while !self.events.is_empty() {
            let events = std::mem::take(&mut self.events);
            processed += events.len();
            ensure!(
                processed <= 8192,
                "too many cascading script events in one tick"
            );
            for event in events {
                let script = if matches!(event.hook, "on_use" | "on_pickup") {
                    registry
                        .items
                        .get(&event.content)
                        .and_then(|v| v.script.as_ref())
                } else {
                    registry
                        .weapons
                        .get(&event.content)
                        .and_then(|v| v.script.as_ref())
                        .or_else(|| {
                            registry
                                .enemies
                                .get(&event.content)
                                .and_then(|v| v.script.as_ref())
                        })
                        .or_else(|| {
                            registry
                                .missions
                                .get(&event.content)
                                .and_then(|v| v.script.as_ref())
                        })
                        .or_else(|| {
                            registry
                                .items
                                .get(&event.content)
                                .and_then(|v| v.script.as_ref())
                        })
                };
                if let Some(path) = script {
                    let owner = &registry.owners[&event.content];
                    let mut e = event.event;
                    e["entities"] = serde_json::to_value(&self.enemies)?;
                    e["player"] = serde_json::to_value(&self.player)?;
                    e["objectives"] = serde_json::to_value(&self.objectives)?;
                    e["projectiles"] = serde_json::to_value(&self.projectiles)?;
                    e["pickups"] = serde_json::to_value(&self.pickups)?;
                    if e.get("tick").is_none() {
                        e["tick"] = self.tick.into();
                    }
                    let commands = scripts.invoke(owner, path, event.hook, &e, self.rng.seed)?;
                    self.apply_commands(&commands, registry)?;
                }
            }
        }
        Ok(())
    }
    pub fn apply_commands(&mut self, commands: &[Command], registry: &Registry) -> Result<()> {
        let mut candidate = self.clone();
        for command in commands {
            candidate.command(command, registry)?;
        }
        *self = candidate;
        Ok(())
    }
    fn command(&mut self, c: &Command, registry: &Registry) -> Result<()> {
        match c {
            Command::Spawn { enemy, x, y } => {
                ensure!(
                    x.unsigned_abs() <= 32768 && y.unsigned_abs() <= 32768,
                    "spawn position exceeds world bounds"
                );
                self.spawn(&ContentId::new(enemy)?, *x, *y, registry)?;
            }
            Command::Projectile {
                weapon,
                x,
                y,
                vx,
                vy,
                hostile,
            } => {
                let id = ContentId::new(weapon)?;
                ensure!(
                    registry.weapons.contains_key(&id)
                        && vx.unsigned_abs() <= 128
                        && vy.unsigned_abs() <= 128
                        && x.unsigned_abs() <= 32768
                        && y.unsigned_abs() <= 32768,
                    "invalid projectile command"
                );
                self.projectile(&id, *x, *y, *vx, *vy, *hostile)?;
            }
            Command::Damage { entity, amount } => {
                ensure!((0..=100000).contains(amount), "invalid damage");
                if *entity == 0 {
                    damage_player(
                        &mut self.player,
                        *amount,
                        self.difficulty,
                        &mut self.rng,
                        &mut self.sounds,
                        &mut self.sound_events,
                    );
                } else {
                    let e = self
                        .enemies
                        .iter_mut()
                        .find(|e| e.entity == *entity)
                        .context("damage target does not exist")?;
                    e.health -= amount;
                    let definition = e.definition.clone();
                    let health = e.health;
                    self.event(definition,"on_hit",serde_json::json!({"entity":entity,"damage":amount,"health":health,"scripted":true,"tick":self.tick}));
                }
            }
            Command::Despawn { entity } => {
                ensure!(
                    self.enemies.iter().any(|e| e.entity == *entity)
                        || self.projectiles.iter().any(|e| e.entity == *entity),
                    "despawn target does not exist"
                );
                self.enemies.retain(|e| e.entity != *entity);
                self.projectiles.retain(|e| e.entity != *entity);
            }
            Command::Move { entity, x, y } => {
                ensure!(
                    x.unsigned_abs() <= 32768 && y.unsigned_abs() <= 32768,
                    "invalid position"
                );
                let e = self
                    .enemies
                    .iter_mut()
                    .find(|e| e.entity == *entity)
                    .context("move target does not exist")?;
                let dx = *x - e.x;
                let dy = *y - e.y;
                e.x = *x;
                e.y = *y;
                e.sx += dx;
                e.sy += dy;
                e.movement = LineMove::new(*x, *y, e.movement.tx + dx, e.movement.ty + dy);
            }
            Command::Velocity { entity, vx, vy } => {
                ensure!(
                    vx.unsigned_abs() <= 128 && vy.unsigned_abs() <= 128,
                    "invalid velocity"
                );
                let e = self
                    .enemies
                    .iter_mut()
                    .find(|e| e.entity == *entity)
                    .context("velocity target does not exist")?;
                e.vx = *vx;
                e.vy = *vy;
            }
            Command::GiveItem { item, count } => {
                let id = ContentId::new(item)?;
                let def = registry.items.get(&id).context("unknown item")?;
                ensure!(
                    self.player.inventory.contains_key(&id) || self.player.inventory.len() < 20,
                    "inventory capacity exceeded"
                );
                let amount = self.player.inventory.entry(id).or_default();
                *amount = amount.saturating_add(*count).min(def.max_count);
            }
            Command::ConsumeItem { item, count } => {
                let amount = self
                    .player
                    .inventory
                    .get_mut(&ContentId::new(item)?)
                    .context("item is not owned")?;
                ensure!(*amount >= *count, "insufficient item quantity");
                *amount -= count;
            }
            Command::Credits { amount } => {
                self.player.credits = self.player.credits.saturating_add_signed(*amount);
            }
            Command::Shield { amount } => {
                ensure!(amount.unsigned_abs() <= 100000, "invalid shield adjustment");
                self.player.shield = (self.player.shield + amount).clamp(0, 100);
            }
            Command::Effect { x, y } => {
                ensure!(self.effects.len() < 4096, "too many effects");
                self.effects.push(Effect {
                    x: *x,
                    y: *y,
                    age: 0,
                });
            }
            Command::Sound { asset } => {
                self.sounds.push(*asset);
                self.sound_events.push(SoundEvent {
                    asset: *asset,
                    pan: 127,
                    pitch: 128,
                    volume: 127,
                    priority: 1,
                });
            }
            Command::Objective { key, value } => {
                ensure!(
                    key.len() <= 128
                        && (self.objectives.contains_key(key) || self.objectives.len() < 1024),
                    "invalid objective key"
                );
                self.objectives.insert(key.clone(), *value);
            }
            Command::PlaySound { sound } => {
                let id = ContentId::new(sound)?;
                ensure!(
                    registry.sounds.contains_key(&id),
                    "sound {id} is unavailable"
                );
                ensure!(self.mod_sounds.len() < 1024, "too many sounds in one tick");
                self.mod_sounds.push(id);
            }
            Command::Complete => {
                if self.outcome == Outcome::Playing {
                    self.outcome = Outcome::Complete;
                    self.event(
                        self.mission.clone(),
                        "on_mission_end",
                        serde_json::json!({"success":true,"tick":self.tick}),
                    );
                }
            }
            Command::Fail => {
                if self.outcome == Outcome::Playing {
                    self.outcome = Outcome::Failed;
                    self.event(
                        self.mission.clone(),
                        "on_mission_end",
                        serde_json::json!({"success":false,"tick":self.tick}),
                    );
                }
            }
        }
        Ok(())
    }
    pub fn digest(&self) -> String {
        use sha2::{Digest, Sha256};
        format!(
            "{:x}",
            Sha256::digest(serde_json::to_vec(self).expect("world serialization"))
        )
    }
    pub fn projectile_asset(p: &Projectile, registry: &Registry) -> Option<u32> {
        p.legacy_enemy.as_ref().map(|s| s.asset).or_else(|| {
            registry.weapons[&p.weapon]
                .art
                .as_ref()
                .and_then(|a| a.asset)
        })
    }
    pub fn reference_state(&self, registry: &Registry) -> serde_json::Value {
        serde_json::json!({"tick":self.tick,"rng":self.rng.seed,"player":[self.player.x,self.player.y,self.player.bank,self.player.shield,self.player.super_shield,self.player.credits],"enemies":self.enemies.iter().map(|e|serde_json::json!([registry.enemies[&e.definition].art.as_ref().and_then(|a|a.asset).unwrap_or(0),e.x,e.y,e.health,e.frame,e.movement.x,e.movement.y])).collect::<Vec<_>>(),"projectiles":self.projectiles.iter().filter(|p|p.hostile).chain(self.projectiles.iter().filter(|p|!p.hostile)).map(|p|serde_json::json!([Self::projectile_asset(p,registry).map(i64::from).unwrap_or(-1),p.x,p.y,p.hostile as u32])).collect::<Vec<_>>()})
    }
}
fn update_legacy_animation(enemy: &mut Enemy, lib: &crate::assets::LegacyEnemy) {
    let f = &lib.fields;
    enemy.art_frame = enemy.frame;
    if f[7] > 1 {
        if enemy.frame_timer < 1 {
            enemy.frame_timer = f[6];
            if enemy.animation_on {
                enemy.frame += 1;
                if enemy.frame >= enemy.animation_frames {
                    enemy.frame = enemy.frame.saturating_sub(f[9].max(0) as u32);
                    match f[10] {
                        1 => {
                            enemy.animation_on = false;
                            enemy.shoot_on = true;
                        }
                        2 => match enemy.multi {
                            1 => {
                                enemy.animation_frames = f[7].max(1) as u32;
                                enemy.multi = 2;
                            }
                            2 => enemy.shoot_on = true,
                            _ => {}
                        },
                        _ => {}
                    }
                }
            }
        } else {
            enemy.frame_timer -= 1;
        }
        if enemy.countdown < 1 {
            match f[10] {
                0 => enemy.shoot_on = true,
                1 => enemy.animation_on = true,
                2 if enemy.multi == 0 => enemy.multi = 1,
                _ => {}
            }
        } else {
            enemy.countdown -= f[18];
        }
    } else if enemy.countdown < 1 {
        enemy.countdown = -1;
        enemy.shoot_on = true;
    } else {
        enemy.countdown -= f[18];
    }
}
fn visible(e: &Enemy) -> bool {
    e.y + e.height > 0 && e.y < 200 && e.x + e.width > 0 && e.x < 320
}
fn play_legacy_sound(
    rng: &mut LegacyRng,
    sounds: &mut Vec<u32>,
    events: &mut Vec<SoundEvent>,
    name: &str,
) {
    if let Some(sound) = crate::legacy_tables::sounds()
        .into_iter()
        .find(|s| s.name == name)
    {
        let pitch = sound.pitch
            + if sound.random {
                rng.next_value() % 40 - 20
            } else {
                0
            };
        sounds.push(sound.asset);
        events.push(SoundEvent {
            asset: sound.asset,
            pan: 127,
            pitch,
            volume: sound.volume,
            priority: sound.priority,
        });
    }
}
fn position_sound(events: &mut [SoundEvent], x: i32, y: i32, player_x: i32, player_y: i32) {
    if let Some(event) = events.last_mut() {
        let dx = x - player_x;
        let dy = y - player_y;
        event.pan = (dx + 127).clamp(1, 255);
        let dx = dx.abs();
        let dy = dy.abs();
        let distance = dx + dy - dx.min(dy) / 2;
        let volume = if distance < 40 {
            127
        } else if distance > 500 {
            1
        } else {
            127 - (distance - 40) * 127 / 460
        };
        event.volume = event.volume * volume / 127;
    }
}
fn accelerate(v: i32, direction: i32, cap: i32) -> i32 {
    match direction.signum() {
        -1 => (if v >= 0 { -1 } else { v } - 1).max(-cap),
        1 => (if v <= 0 { 1 } else { v } + 1).min(cap),
        _ => v / 2,
    }
}
fn damage_player(
    p: &mut Player,
    damage: i32,
    difficulty: u32,
    rng: &mut LegacyRng,
    sounds: &mut Vec<u32>,
    events: &mut Vec<SoundEvent>,
) {
    let damage = if difficulty == 0 && damage > 1 {
        damage >> 1
    } else {
        damage
    };
    let super_id = ContentId::from("base:super_shield");
    if p.inventory.contains_key(&super_id) {
        // Original super shields absorb the whole hit, even when it exhausts them.
        // A zero-charge shield remains equipped until another hit removes it.
        p.super_shield -= damage;
        play_legacy_sound(rng, sounds, events, "FX_SHIT");
        if p.super_shield < 0 {
            p.super_shield = 0;
            p.inventory.remove(&super_id);
        }
    } else {
        p.shield = (p.shield - damage).max(0);
        play_legacy_sound(rng, sounds, events, "FX_HIT");
    }
}
fn target_matches(t: &Target, ground: bool) -> bool {
    match t {
        Target::All => true,
        Target::Air => !ground,
        Target::Ground => ground,
    }
}
fn contains(e: &Enemy, x: i32, y: i32) -> bool {
    x > e.x && x < e.x + e.width - 1 && y > e.y && y < e.y + e.height - 1
}
/// Accumulate exact rational time without rounding the original 3/70-second tick.
#[derive(Default)]
pub struct Clock {
    units: u128,
}
impl Clock {
    pub fn advance(&mut self, nanos: u64) -> usize {
        self.units += nanos as u128 * 70;
        let steps = self.units / 3_000_000_000;
        self.units %= 3_000_000_000;
        steps as usize
    }
    pub fn alpha(&self) -> f32 {
        self.units as f32 / 3_000_000_000.0
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn rng_wraps_like_legacy() {
        let mut r = LegacyRng::new(1);
        assert_eq!(
            (0..5).map(|_| r.next_value()).collect::<Vec<_>>(),
            vec![16838, 5758, 10113, 17515, 31051]
        );
    }
    #[test]
    fn clock_is_independent_of_frame_rate() {
        for hz in [30, 60, 144] {
            let mut c = Clock::default();
            let mut ticks = 0;
            let mut previous = 0;
            for frame in 1..=hz * 3 {
                let now = frame as u64 * 1_000_000_000 / hz as u64;
                ticks += c.advance(now - previous);
                previous = now;
            }
            assert_eq!(ticks, 70);
        }
    }
    #[test]
    fn line_reaches_target() {
        let mut m = LineMove::new(0, 0, 10, 7);
        for _ in 0..20 {
            m.advance(1);
        }
        assert_eq!((m.x, m.y), (10, 7));
    }
}
