//! Versioned, namespaced content shared by the base game and mods.
use crate::assets::{Catalog, LegacyEnemy, LegacyMap, Sprite};
use anyhow::{Context, Result, ensure};
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};
use std::{collections::BTreeMap, path::PathBuf};

pub const API_VERSION: u32 = 1;
#[derive(
    Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize, JsonSchema,
)]
#[serde(transparent)]
pub struct ContentId(pub String);
impl ContentId {
    pub fn new(value: impl Into<String>) -> Result<Self> {
        let id = Self(value.into());
        id.validate()?;
        Ok(id)
    }
    pub fn validate(&self) -> Result<()> {
        let (ns, name) = self
            .0
            .split_once(':')
            .context("content IDs require namespace:name")?;
        ensure!(
            !ns.is_empty()
                && !name.is_empty()
                && !name.contains(':')
                && self.0.len() <= 128
                && self
                    .0
                    .chars()
                    .all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || ":_-/.".contains(c)),
            "invalid content ID {}",
            self.0
        );
        Ok(())
    }
}
impl From<&str> for ContentId {
    fn from(s: &str) -> Self {
        Self(s.into())
    }
}
impl std::fmt::Display for ContentId {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        self.0.fmt(f)
    }
}
#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct Art {
    pub asset: Option<u32>,
    pub png: Option<String>,
    #[serde(default)]
    pub hd_png: Option<String>,
    pub logical_width: u32,
    pub logical_height: u32,
    #[serde(default = "one")]
    pub frames: u32,
    #[serde(default)]
    pub nearest: bool,
}
fn one() -> u32 {
    1
}
fn yes() -> bool {
    true
}
fn shield() -> i32 {
    100
}
fn speed() -> i32 {
    2
}
fn rate() -> u32 {
    10
}
#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum Target {
    Air,
    Ground,
    All,
}
#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(rename_all = "snake_case")]
pub enum WeaponBehavior {
    Straight,
    Homing,
    Beam,
    Spread,
    Bomb,
    EnergyGrab,
}
#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct WeaponDef {
    pub id: ContentId,
    pub name: String,
    pub damage: i32,
    pub speed: i32,
    pub cooldown: u32,
    pub behavior: WeaponBehavior,
    pub target: Target,
    #[serde(default)]
    pub art: Option<Art>,
    #[serde(default)]
    pub offsets: Vec<[i32; 2]>,
    #[serde(default)]
    pub script: Option<String>,
    #[serde(default)]
    pub legacy: Option<u32>,
}
#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct ItemDef {
    pub id: ContentId,
    pub name: String,
    /// Optional shop information, up to 4096 UTF-8 bytes.
    #[serde(default)]
    pub description: String,
    pub price: u32,
    #[serde(default = "one")]
    pub max_count: u32,
    #[serde(default = "one")]
    pub initial_count: u32,
    #[serde(default)]
    pub weapon: Option<ContentId>,
    #[serde(default)]
    pub shield: i32,
    #[serde(default)]
    pub credits: u32,
    #[serde(default)]
    pub consumable: bool,
    #[serde(default)]
    pub special: bool,
    #[serde(default)]
    pub art: Option<Art>,
    #[serde(default)]
    pub script: Option<String>,
    #[serde(default)]
    pub legacy: Option<u32>,
}
impl ItemDef {
    /// Sales remove one ordinary unit, or one original shield refill/module.
    pub fn resale_price(&self) -> u32 {
        if matches!(self.id.0.as_str(), "base:energy" | "base:super_shield") {
            self.price / 2
        } else {
            self.price / self.initial_count.max(1) / 2
        }
    }
}
#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct EnemyDef {
    pub id: ContentId,
    pub name: String,
    #[serde(default = "shield")]
    pub health: i32,
    #[serde(default = "speed")]
    pub speed: i32,
    #[serde(default)]
    pub reward: u32,
    #[serde(default)]
    pub ground: bool,
    #[serde(default)]
    pub boss: bool,
    #[serde(default = "rate")]
    pub cooldown: u32,
    #[serde(default)]
    pub path: Vec<[i32; 2]>,
    #[serde(default)]
    pub repeat: bool,
    #[serde(default)]
    pub weapon: Option<ContentId>,
    #[serde(default)]
    pub drop: Option<ContentId>,
    #[serde(default)]
    pub art: Option<Art>,
    #[serde(default)]
    pub script: Option<String>,
    #[serde(skip)]
    #[schemars(skip)]
    pub legacy: Option<LegacyEnemy>,
}
#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct SpawnDef {
    pub tick: u64,
    pub enemy: ContentId,
    pub x: i32,
    pub y: i32,
    #[serde(default)]
    pub difficulty: u32,
}
#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct TileDef {
    pub art: Art,
    #[serde(default)]
    pub health: i32,
    #[serde(default)]
    pub reward: u32,
    #[serde(default)]
    pub destroyed: Option<Art>,
}
#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct MissionDef {
    pub id: ContentId,
    pub name: String,
    #[serde(default)]
    pub art: Option<Art>,
    pub duration: u64,
    #[serde(default = "yes")]
    pub auto_complete: bool,
    #[serde(default)]
    pub spawns: Vec<SpawnDef>,
    #[serde(default)]
    pub tiles: Vec<TileDef>,
    #[serde(default)]
    pub columns: u32,
    #[serde(default)]
    pub layout: Vec<usize>,
    #[serde(default)]
    pub next: Option<ContentId>,
    #[serde(default)]
    pub music: Option<u32>,
    /// Package music registry ID. Mutually exclusive with legacy `music`.
    #[serde(default)]
    pub music_track: Option<ContentId>,
    #[serde(default)]
    pub script: Option<String>,
    #[serde(default)]
    pub legacy_map: Option<u32>,
}
#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct CampaignDef {
    pub id: ContentId,
    pub name: String,
    #[serde(default)]
    pub art: Option<Art>,
    pub missions: Vec<ContentId>,
}
#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct SoundDef {
    pub id: ContentId,
    pub name: String,
    pub file: String,
    #[serde(default = "sound_volume")]
    pub volume: i32,
    #[serde(default = "sound_volume")]
    pub pan: i32,
    #[serde(default = "sound_pitch")]
    pub pitch: i32,
    #[serde(default = "one")]
    pub priority: u32,
}
#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct MusicDef {
    pub id: ContentId,
    pub name: String,
    /// Package-local checked MUS score, played through original GENMIDI FM.
    pub file: String,
    #[serde(default = "yes")]
    pub looping: bool,
}
fn sound_volume() -> i32 {
    127
}
fn sound_pitch() -> i32 {
    128
}
#[derive(Debug, Clone, Default, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct ContentPack {
    #[serde(default)]
    pub music: Vec<MusicDef>,
    #[serde(default)]
    pub sounds: Vec<SoundDef>,
    #[serde(default)]
    pub weapons: Vec<WeaponDef>,
    #[serde(default)]
    pub items: Vec<ItemDef>,
    #[serde(default)]
    pub enemies: Vec<EnemyDef>,
    #[serde(default)]
    pub missions: Vec<MissionDef>,
    #[serde(default)]
    pub campaigns: Vec<CampaignDef>,
    #[serde(default)]
    pub overrides: Vec<ContentId>,
}
#[derive(Debug, Clone, Default)]
pub struct Registry {
    pub music: BTreeMap<ContentId, MusicDef>,
    pub sounds: BTreeMap<ContentId, SoundDef>,
    pub weapons: BTreeMap<ContentId, WeaponDef>,
    pub items: BTreeMap<ContentId, ItemDef>,
    pub enemies: BTreeMap<ContentId, EnemyDef>,
    pub missions: BTreeMap<ContentId, MissionDef>,
    pub campaigns: BTreeMap<ContentId, CampaignDef>,
    pub owners: BTreeMap<ContentId, String>,
    pub asset_roots: BTreeMap<String, PathBuf>,
    pub overrides: Vec<String>,
}
impl Registry {
    pub fn apply(&mut self, pack: ContentPack, owner: &str) -> Result<()> {
        let mut candidate = self.clone();
        candidate.apply_inner(pack, owner)?;
        *self = candidate;
        Ok(())
    }
    fn apply_inner(&mut self, pack: ContentPack, owner: &str) -> Result<()> {
        let overrides: std::collections::BTreeSet<_> = pack.overrides.into_iter().collect();
        let mut supplied = std::collections::BTreeSet::new();
        macro_rules! insert {
            ($values:expr,$map:ident) => {
                for value in $values {
                    value.id.validate()?;
                    ensure!(
                        supplied.insert(value.id.clone()),
                        "duplicate definition {}",
                        value.id
                    );
                    let exists = self.owners.contains_key(&value.id);
                    ensure!(
                        !exists || self.$map.contains_key(&value.id),
                        "override cannot change content type: {}",
                        value.id
                    );
                    ensure!(
                        exists == overrides.contains(&value.id),
                        "{}: {} requires an explicit override and override targets must exist",
                        owner,
                        value.id
                    );
                    if !exists {
                        ensure!(
                            value.id.0.starts_with(&format!("{owner}:")),
                            "{} does not belong to namespace {owner}",
                            value.id
                        );
                    }
                    if exists {
                        self.overrides.push(format!(
                            "{}: {} -> {owner}",
                            value.id, self.owners[&value.id]
                        ));
                    }
                    self.owners.insert(value.id.clone(), owner.into());
                    self.$map.insert(value.id.clone(), value);
                }
            };
        }
        insert!(pack.weapons, weapons);
        insert!(pack.items, items);
        insert!(pack.enemies, enemies);
        insert!(pack.missions, missions);
        insert!(pack.campaigns, campaigns);
        insert!(pack.sounds, sounds);
        insert!(pack.music, music);
        ensure!(
            overrides.is_subset(&supplied),
            "override has no replacement definition"
        );
        Ok(())
    }
    pub fn validate(&self) -> Result<()> {
        let label = |name: &str, script: &Option<String>| -> Result<()> {
            ensure!(
                !name.trim().is_empty() && name.len() <= 128,
                "content name must contain 1–128 bytes"
            );
            ensure!(
                script
                    .as_ref()
                    .is_none_or(|s| !s.is_empty() && s.len() <= 4096),
                "invalid script path length"
            );
            Ok(())
        };
        let art = |a: &Option<Art>| -> Result<()> {
            if let Some(a) = a {
                ensure!(
                    a.logical_width > 0
                        && a.logical_height > 0
                        && a.logical_width <= 4096
                        && a.logical_height <= 4096
                        && a.frames > 0
                        && a.frames <= 256
                        && (a.logical_width as u64 * a.logical_height as u64) <= 1_048_576,
                    "invalid artwork dimensions/frames"
                );
                ensure!(
                    a.asset.is_some() != a.png.is_some(),
                    "art requires exactly one of asset or png"
                );
                ensure!(
                    a.png
                        .as_ref()
                        .is_none_or(|p| !p.is_empty() && p.len() <= 4096),
                    "invalid artwork path length"
                );
                ensure!(
                    a.hd_png
                        .as_ref()
                        .is_none_or(|p| !p.is_empty() && p.len() <= 4096),
                    "invalid HD artwork path length"
                );
                ensure!(
                    a.asset
                        .is_none_or(|id| id.checked_add(a.frames - 1).is_some()),
                    "art animation asset ID overflow"
                );
            }
            Ok(())
        };
        for w in self.weapons.values() {
            label(&w.name, &w.script)?;
            ensure!(
                w.damage > 0
                    && w.damage <= 100000
                    && w.cooldown > 0
                    && w.speed.unsigned_abs() <= 128
                    && w.offsets.len() <= 64,
                "invalid weapon {}",
                w.id
            );
            ensure!(
                w.offsets
                    .iter()
                    .flatten()
                    .all(|n| n.unsigned_abs() <= 32768),
                "weapon offset outside world bounds"
            );
            ensure!(
                w.legacy.is_none_or(|n| n < 15),
                "invalid original projectile ID"
            );
            art(&w.art)?;
        }
        for i in self.items.values() {
            label(&i.name, &i.script)?;
            ensure!(
                i.description.len() <= 4096,
                "item {} description exceeds 4096 bytes",
                i.id
            );
            ensure!(
                i.max_count > 0
                    && i.max_count <= 1_000_000
                    && i.initial_count > 0
                    && i.initial_count <= i.max_count,
                "invalid item {}",
                i.id
            );
            ensure!(
                i.shield.unsigned_abs() <= 100000 && i.legacy.is_none_or(|n| n < 24),
                "invalid item effects/original ID"
            );
            if let Some(w) = &i.weapon {
                ensure!(
                    self.weapons.contains_key(w),
                    "item {} references missing weapon {w}",
                    i.id
                );
            }
            art(&i.art)?;
        }
        for e in self.enemies.values() {
            label(&e.name, &e.script)?;
            ensure!(
                e.health > 0
                    && e.health <= 100000
                    && e.cooldown > 0
                    && e.speed.unsigned_abs() <= 128
                    && e.path.len() <= 1024,
                "invalid enemy {}",
                e.id
            );
            ensure!(
                e.path.iter().flatten().all(|v| v.unsigned_abs() <= 32768),
                "enemy path outside world bounds"
            );
            if let Some(w) = &e.weapon {
                ensure!(
                    self.weapons.contains_key(w),
                    "enemy {} references missing weapon {w}",
                    e.id
                );
            }
            if let Some(i) = &e.drop {
                ensure!(
                    self.items.contains_key(i),
                    "enemy {} references missing drop {i}",
                    e.id
                );
            }
            art(&e.art)?;
        }
        for m in self.missions.values() {
            label(&m.name, &m.script)?;
            ensure!(
                m.music.is_none() || m.music_track.is_none(),
                "mission {} cannot select both music and music_track",
                m.id
            );
            if let Some(track) = &m.music_track {
                ensure!(
                    self.music.contains_key(track),
                    "mission {} references missing music track {track}",
                    m.id
                );
            }
            art(&m.art)?;
            ensure!(
                m.duration > 0
                    && m.duration <= 1_000_000
                    && m.spawns.len() <= 100000
                    && m.tiles.len() <= 65536
                    && m.layout.len() <= 2_000_000,
                "invalid mission {}",
                m.id
            );
            if !m.layout.is_empty() {
                ensure!(
                    (1..=128).contains(&m.columns)
                        && m.layout.len() % m.columns as usize == 0
                        && m.layout.iter().all(|i| *i < m.tiles.len()),
                    "invalid mission terrain {}",
                    m.id
                );
            }
            for tile in &m.tiles {
                ensure!(
                    (if m.legacy_map.is_some() { -32768 } else { 0 }..=100000)
                        .contains(&tile.health),
                    "invalid terrain health"
                );
                art(&Some(tile.art.clone()))?;
                art(&tile.destroyed)?;
            }
            ensure!(
                m.spawns.windows(2).all(|w| w[0].tick <= w[1].tick),
                "mission {} spawns must be sorted by tick",
                m.id
            );
            for s in &m.spawns {
                ensure!(
                    s.tick <= 1_000_000
                        && s.difficulty <= if m.legacy_map.is_some() { 5 } else { 3 },
                    "invalid spawn tick/difficulty"
                );
                ensure!(
                    s.x.unsigned_abs() <= 32768 && s.y.unsigned_abs() <= 32768,
                    "spawn coordinate outside world bounds"
                );
                ensure!(
                    self.enemies.contains_key(&s.enemy),
                    "mission {} references missing enemy {}",
                    m.id,
                    s.enemy
                );
            }
            if let Some(next) = &m.next {
                ensure!(
                    self.missions.contains_key(next),
                    "missing next mission {next}"
                );
            }
        }
        for c in self.campaigns.values() {
            label(&c.name, &None)?;
            art(&c.art)?;
            ensure!(c.missions.len() <= 100000, "campaign exceeds mission limit");
            ensure!(!c.missions.is_empty(), "empty campaign {}", c.id);
            for m in &c.missions {
                ensure!(
                    self.missions.contains_key(m),
                    "campaign {} references missing mission {m}",
                    c.id
                );
            }
        }
        for sound in self.sounds.values() {
            label(&sound.name, &None)?;
            ensure!(
                !sound.file.is_empty()
                    && sound.file.len() <= 4096
                    && (0..=127).contains(&sound.volume)
                    && (0..=255).contains(&sound.pan)
                    && (0..=255).contains(&sound.pitch)
                    && sound.priority <= 100000,
                "invalid sound definition {}",
                sound.id
            );
        }
        for music in self.music.values() {
            label(&music.name, &None)?;
            let path = std::path::Path::new(&music.file);
            ensure!(
                !music.file.is_empty()
                    && music.file.len() <= 512
                    && !path.is_absolute()
                    && path
                        .components()
                        .all(|component| matches!(component, std::path::Component::Normal(_)))
                    && path
                        .extension()
                        .is_some_and(|extension| extension.eq_ignore_ascii_case("mus")),
                "music {} requires a package-local .mus file without parent traversal",
                music.id
            );
        }
        Ok(())
    }
    pub fn base(catalog: &Catalog) -> Result<Self> {
        let mut reg = Self::default();
        let mut pack = ContentPack::default();
        for o in crate::legacy_tables::objects() {
            let id = ContentId::from(o.id);
            let weapon = if o.index < 15 {
                Some(ContentId(format!(
                    "base:projectile_{}",
                    o.id.strip_prefix("base:").unwrap()
                )))
            } else {
                None
            };
            let art = if o.asset > 0 {
                let s = catalog.sprite(o.asset)?;
                Some(Art {
                    asset: Some(o.asset),
                    png: None,
                    hd_png: None,
                    logical_width: s.width as u32,
                    logical_height: s.height as u32,
                    frames: o.frames.max(1),
                    nearest: false,
                })
            } else {
                None
            };
            pack.items.push(ItemDef {
                id: id.clone(),
                name: o.name.into(),
                description: match o.index {
                    0 => "Paired forward guns. Fire automatically with the main fire control and strike air or ground targets.",
                    1 => "Twin plasma guns. An always-equipped upgrade that fires alongside the forward guns at airborne targets.",
                    2 => "Automatic micro missiles. Fire alongside the forward guns and seek airborne or ground enemies.",
                    3 => "Selectable unguided missile launcher. Direct its forward shots at airborne or ground targets.",
                    4 => "Selectable rapid-fire cannon. A concentrated stream of rounds for air and ground targets.",
                    5 => "Selectable tracking turret. Instantly aims its gunfire at airborne targets; it cannot damage ground targets.",
                    6 => "Selectable missile pods. Launch a spread of missiles against airborne targets.",
                    7 => "Selectable air-to-air missiles. Seek airborne enemies; they cannot damage ground targets.",
                    8 => "Selectable air-to-ground missiles. Seek ground targets; they cannot damage aircraft.",
                    9 => "Selectable ground bomb. Damages ground targets and neighboring destructible terrain.",
                    10 => "Selectable Energy Grab. Drains susceptible airborne enemies and suppresses their weapons.",
                    11 => "One-use Mega Bomb. The bomb control damages visible enemies and terrain and clears hostile shots.",
                    12 => "Selectable pulse cannon. A powerful forward energy weapon for air and ground targets.",
                    13 => "Selectable forward laser. A high-end forward energy beam for airborne and ground targets.",
                    14 => "Selectable Death Ray. Tracks airborne or ground targets with an energy beam.",
                    15 => "Extra shielding with 100 charge per module. The equipped module absorbs hits first; a reserve replaces it when destroyed.",
                    16 => "Restores 25 energy. With normal energy full, a smaller recharge goes to the equipped super shield.",
                    17 => "Always-equipped damage detector. Shows a scanning target-health display during flight.",
                    _ => "Valuable salvage collected during a mission for credits.",
                }.into(),
                price: o.cost,
                max_count: o.max_count.max(1),
                initial_count: o.initial_count,
                weapon,
                shield: if o.index == 16 {
                    25
                } else if o.index == 15 {
                    100
                } else {
                    0
                },
                credits: if o.index >= 18 { o.cost } else { 0 },
                consumable: o.index == 11,
                special: o.special,
                art,
                script: None,
                legacy: Some(o.index),
            });
        }
        for w in crate::legacy_tables::weapons() {
            let sprite = if w.asset > 0 {
                Some(catalog.sprite(w.asset)?)
            } else {
                None
            };
            pack.weapons.push(WeaponDef {
                id: ContentId(format!(
                    "base:projectile_{}",
                    w.id.strip_prefix("base:").unwrap()
                )),
                name: w.name.into(),
                damage: w.damage.max(1),
                speed: w.speed,
                cooldown: w.cooldown.max(1),
                behavior: match w.index {
                    4 | 8 | 7 | 2 => WeaponBehavior::Homing,
                    5 | 12 | 13 | 14 => WeaponBehavior::Beam,
                    9 | 11 => WeaponBehavior::Bomb,
                    10 => WeaponBehavior::EnergyGrab,
                    6 => WeaponBehavior::Spread,
                    _ => WeaponBehavior::Straight,
                },
                // Describe effective gameplay, including native firing/beam
                // exceptions to the historical hit-type metadata.
                target: if w.index == 5 {
                    Target::Air
                } else if w.index == 13 {
                    Target::All
                } else {
                    match w.target {
                        1 | 5 => Target::Air,
                        2 | 4 => Target::Ground,
                        _ => Target::All,
                    }
                },
                art: sprite.map(|sprite| Art {
                    asset: Some(w.asset),
                    png: None,
                    hd_png: None,
                    logical_width: sprite.width as u32,
                    logical_height: sprite.height as u32,
                    frames: w.frames.max(1),
                    nearest: false,
                }),
                offsets: if w.index == 0 {
                    vec![[-13, 0], [13, 0]]
                } else {
                    vec![[0, 0]]
                },
                script: None,
                legacy: Some(w.index),
            });
        }
        pack.weapons.push(WeaponDef {
            id: "base:enemy_bullet".into(),
            name: "Enemy cannon".into(),
            damage: 3,
            speed: 4,
            cooldown: 12,
            behavior: WeaponBehavior::Straight,
            target: Target::All,
            art: Some(Art {
                asset: Some(0x101d6),
                png: None,
                hd_png: None,
                logical_width: 8,
                logical_height: 8,
                frames: 2,
                nearest: false,
            }),
            offsets: vec![[0, 0]],
            script: None,
            legacy: None,
        });
        for game in 0..4 {
            let Ok(bytes) = catalog.named(&format!("SPRITE{}_ITM", game + 1)) else {
                continue;
            };
            for (n, legacy) in LegacyEnemy::library(&bytes)?.into_iter().enumerate() {
                let Ok(asset) = catalog.id(&legacy.name) else {
                    continue;
                };
                let Ok(s) = catalog.sprite(asset) else {
                    continue;
                };
                let f = &legacy.fields;
                pack.enemies.push(EnemyDef {
                    id: ContentId(format!("base:enemy_{game}_{n}")),
                    name: legacy.name.clone(),
                    health: f[13].max(1),
                    speed: f[18].clamp(0, 128),
                    reward: f[14].max(0) as u32,
                    ground: f[21] >= 3,
                    boss: f[12] != 0,
                    cooldown: f[3].max(1) as u32,
                    path: legacy
                        .flight_x
                        .iter()
                        .zip(&legacy.flight_y)
                        .take(f[19].max(0) as usize)
                        .map(|(x, y)| [*x as i32, *y as i32])
                        .collect(),
                    repeat: f[21] == 0,
                    weapon: if f[22] > 0 {
                        Some("base:enemy_bullet".into())
                    } else {
                        None
                    },
                    drop: pack
                        .items
                        .iter()
                        .find(|i| i.legacy == Some(f[1] as u32))
                        .map(|i| i.id.clone()),
                    art: Some(Art {
                        asset: Some(asset),
                        png: None,
                        hd_png: None,
                        logical_width: s.width as u32,
                        logical_height: s.height as u32,
                        frames: f[7].max(1) as u32,
                        nearest: false,
                    }),
                    script: None,
                    legacy: Some(legacy),
                });
            }
        }
        for sector in 1..=3 {
            let mut missions = Vec::new();
            for wave in 1..=9 {
                let Ok(id) = catalog.id(&format!("MAP{wave}G{sector}_MAP")) else {
                    continue;
                };
                let map = LegacyMap::decode(&catalog.read(id)?)?;
                let mut spawns = Vec::new();
                let mut group_row = None;
                for s in &map.spawns {
                    let row = *group_row.get_or_insert(s.row);
                    let eid = ContentId(format!("base:enemy_{}_{}", s.game, s.library));
                    if pack.enemies.iter().any(|e| e.id == eid) {
                        spawns.push(SpawnDef {
                            tick: if row >= 139 {
                                0
                            } else {
                                (56 + (138 - row) * 32) as u64
                            },
                            enemy: eid,
                            x: 16 + s.x * 32,
                            y: (if row >= 139 { -136 } else { -112 }) - (row - s.row) * 32,
                            difficulty: s.difficulty.max(0) as u32,
                        });
                    }
                    if s.link == 1 || s.link == -1 {
                        group_row = None;
                    }
                }
                spawns.sort_by_key(|s| s.tick);
                let mut tiles = Vec::new();
                let mut layout = Vec::new();
                let mut lookup = BTreeMap::new();
                for (flat, game) in map.tiles {
                    let key = (flat, game);
                    let pos = if let Some(p) = lookup.get(&key) {
                        *p
                    } else {
                        let start = catalog.id(&format!("STARTG{}TILES", game + 1))? + 1;
                        let lib = catalog.named(&format!("FLATSG{}_ITM", game + 1))?;
                        let o = flat as usize * 8;
                        let destroyed = crate::assets::i32_at(&lib, o)?;
                        let health = crate::assets::i16_at(&lib, o + 4)?;
                        let bounty = crate::assets::i16_at(&lib, o + 6)?;
                        let make = |asset| Art {
                            asset: Some(asset),
                            png: None,
                            hd_png: None,
                            logical_width: 32,
                            logical_height: 32,
                            frames: 1,
                            nearest: false,
                        };
                        let n = tiles.len();
                        tiles.push(TileDef {
                            art: make(start + flat as u32),
                            health: if destroyed != flat as i32 {
                                health as i32
                            } else {
                                0
                            },
                            reward: bounty.max(0) as u32,
                            destroyed: if destroyed != flat as i32 {
                                Some(make(start + destroyed as u32))
                            } else {
                                None
                            },
                        });
                        lookup.insert(key, n);
                        n
                    };
                    layout.push(pos);
                }
                let mid = ContentId(format!("base:sector_{sector}_wave_{wave}"));
                missions.push(mid.clone());
                pack.missions.push(MissionDef {
                    id: mid,
                    name: format!("Sector {sector} / Wave {wave}"),
                    art: None,
                    duration: 4700,
                    auto_complete: true,
                    spawns,
                    tiles,
                    columns: 9,
                    layout,
                    next: if wave < 9 {
                        Some(ContentId(format!("base:sector_{sector}_wave_{}", wave + 1)))
                    } else {
                        None
                    },
                    music: catalog
                        .id(&format!(
                            "RAP{}_MUS",
                            [
                                [8, 2, 4, 7, 6, 2, 3, 4, 6],
                                [3, 2, 4, 8, 6, 2, 8, 1, 6],
                                [8, 4, 1, 7, 6, 2, 3, 4, 6],
                            ][sector - 1][wave - 1]
                        ))
                        .ok(),
                    music_track: None,
                    script: None,
                    legacy_map: Some(id),
                });
            }
            if !missions.is_empty() {
                pack.campaigns.push(CampaignDef {
                    id: ContentId(format!("base:sector_{sector}")),
                    name: ["Bravo Sector", "Tango Sector", "Outer Regions"][sector - 1].into(),
                    art: None,
                    missions,
                });
            }
        }
        reg.apply(pack, "base")?;
        reg.validate()?;
        Ok(reg)
    }
    pub fn art(&self, id: &ContentId) -> Option<&Art> {
        self.enemies
            .get(id)
            .and_then(|e| e.art.as_ref())
            .or_else(|| self.items.get(id).and_then(|e| e.art.as_ref()))
            .or_else(|| self.weapons.get(id).and_then(|e| e.art.as_ref()))
            .or_else(|| self.missions.get(id).and_then(|e| e.art.as_ref()))
            .or_else(|| self.campaigns.get(id).and_then(|e| e.art.as_ref()))
    }
}
pub fn art_sprite(
    catalog: &Catalog,
    registry: &Registry,
    owner: &str,
    art: &Art,
    frame: u32,
) -> Result<Sprite> {
    art_sprite_variant(catalog, registry, owner, art, frame, false)
}
pub fn art_sprite_variant(
    catalog: &Catalog,
    registry: &Registry,
    owner: &str,
    art: &Art,
    frame: u32,
    hd: bool,
) -> Result<Sprite> {
    ensure!(art.frames > 0, "art animation must have frames");
    let png = if hd {
        art.hd_png.as_ref().or(art.png.as_ref())
    } else {
        art.png.as_ref()
    };
    if let Some(id) = art.asset.filter(|_| !(hd && art.hd_png.is_some())) {
        catalog.sprite(
            id.checked_add(frame % art.frames)
                .context("art asset ID overflow")?,
        )
    } else {
        let root = registry
            .asset_roots
            .get(owner)
            .context("unknown artwork owner")?;
        let path =
            crate::assets::contained(root, std::path::Path::new(png.context("missing PNG")?))?;
        let sprite = Sprite::png(&path, &catalog.palette()?)?;
        ensure!(
            sprite.width % art.frames as usize == 0,
            "PNG strip width must be divisible by frame count"
        );
        let width = sprite.width / art.frames as usize;
        let x = (frame % art.frames) as usize * width;
        let mut out = Sprite::blank(width, sprite.height);
        for y in 0..out.height {
            out.pixels[y * width..(y + 1) * width].copy_from_slice(
                &sprite.pixels[y * sprite.width + x..y * sprite.width + x + width],
            );
        }
        Ok(out)
    }
}
