use crate::{
    content::{ContentId, Registry},
    modding::ModPin,
};
use anyhow::{Context, Result, ensure};
use serde::{Deserialize, Serialize};
use std::{
    collections::BTreeMap,
    fs::{self, OpenOptions},
    io::Write,
    path::{Path, PathBuf},
};

#[derive(Debug, Clone)]
pub struct Paths {
    pub data: PathBuf,
    pub config: PathBuf,
    pub cache: PathBuf,
    pub legacy: PathBuf,
}
impl Paths {
    pub fn discover() -> Result<Self> {
        let home = PathBuf::from(std::env::var_os("HOME").context("HOME is unset")?);
        let dir = |name: &str, fallback: &str| {
            std::env::var_os(name)
                .map(PathBuf::from)
                .unwrap_or_else(|| home.join(fallback))
        };
        Ok(Self {
            data: dir("XDG_DATA_HOME", ".local/share").join("RaptorReplica"),
            config: dir("XDG_CONFIG_HOME", ".config").join("RaptorReplica"),
            cache: dir("XDG_CACHE_HOME", ".cache").join("RaptorReplica"),
            legacy: home.join(".local/share/Raptor"),
        })
    }
    pub fn mods(&self) -> PathBuf {
        self.data.join("mods")
    }
    pub fn save_path(&self, slot: usize) -> PathBuf {
        self.data.join(format!("pilot-{slot:04}.json"))
    }
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct Config {
    pub hd_mode: bool,
    pub scale: usize,
    pub scanlines: bool,
    pub fullscreen: bool,
    pub borderless: bool,
    pub aspect_correct: bool,
    pub width: u32,
    pub height: u32,
    pub music_volume: u8,
    pub fx_volume: u8,
    pub fx_channels: usize,
    pub control: String,
    pub difficulty: u32,
    pub bindings: BTreeMap<String, String>,
    pub enabled_mods: Vec<String>,
}
impl Default for Config {
    fn default() -> Self {
        Self {
            hd_mode: false,
            scale: 4,
            scanlines: false,
            fullscreen: false,
            borderless: false,
            aspect_correct: true,
            width: 1280,
            height: 960,
            music_volume: 85,
            fx_volume: 85,
            fx_channels: 2,
            control: "keyboard".into(),
            difficulty: 2,
            bindings: [
                ("up", "Up"),
                ("down", "Down"),
                ("left", "Left"),
                ("right", "Right"),
                ("fire", "Left Ctrl"),
                ("special", "Left Alt"),
                ("cycle", "Space"),
                ("bomb", "Right Shift"),
            ]
            .into_iter()
            .map(|(k, v)| (k.into(), v.into()))
            .collect(),
            enabled_mods: vec![],
        }
    }
}
impl Config {
    pub fn load(paths: &Paths) -> Result<Self> {
        let path = paths.config.join("config.toml");
        let mut c = if path.exists() {
            toml::from_str(&fs::read_to_string(path)?)?
        } else {
            Self::import_ini(&paths.legacy.join("SETUP.INI"))?
        };
        ensure!(
            matches!(c.scale, 1 | 2 | 3 | 4)
                && c.width >= 320
                && c.height >= 200
                && c.width <= 7680
                && c.height <= 4320
                && (1..=8).contains(&c.fx_channels)
                && c.difficulty <= 3,
            "invalid video/difficulty settings"
        );
        c.music_volume = c.music_volume.min(127);
        c.fx_volume = c.fx_volume.min(127);
        Ok(c)
    }
    pub fn save(&self, paths: &Paths) -> Result<()> {
        atomic_write(
            &paths.config.join("config.toml"),
            toml::to_string_pretty(self)?.as_bytes(),
        )
    }
    pub fn import_ini(path: &Path) -> Result<Self> {
        let mut config = Self::default();
        if !path.exists() {
            return Ok(config);
        }
        let mut section = String::new();
        for line in fs::read_to_string(path)?.lines() {
            let line = line.trim();
            if line.starts_with('[') && line.ends_with(']') {
                section = line[1..line.len() - 1].to_ascii_lowercase();
                continue;
            }
            let Some((k, v)) = line.split_once('=') else {
                continue;
            };
            let k = k.trim().to_ascii_lowercase();
            let value = v.trim().parse::<i32>().unwrap_or(0);
            match (section.as_str(), k.as_str()) {
                ("video", "fullscreen") => config.fullscreen = value != 0,
                ("video", "borderless") => config.borderless = value != 0,
                ("video", "upscaler") => {
                    config.scale = if [2, 3, 4].contains(&value) {
                        value as usize
                    } else {
                        1
                    }
                }
                ("video", "scanlines") => config.scanlines = value != 0,
                ("video", "aspect_ratio_correct") => config.aspect_correct = value != 0,
                ("music", "volume") => config.music_volume = value.clamp(0, 127) as u8,
                ("soundfx", "volume") => config.fx_volume = value.clamp(0, 127) as u8,
                ("soundfx", "channels") => config.fx_channels = value.clamp(1, 8) as usize,
                ("setup", "control") => {
                    config.control = match value {
                        1 => "mouse",
                        2 => "controller",
                        _ => "keyboard",
                    }
                    .into()
                }
                ("keyboard", _) => {
                    let action = match k.as_str() {
                        "moveup" => "up",
                        "movedn" => "down",
                        "moveleft" => "left",
                        "moveright" => "right",
                        "fire" => "fire",
                        "firesp" => "special",
                        "changesp" => "cycle",
                        "megafire" => "bomb",
                        _ => continue,
                    };
                    if let Some(key) = legacy_scancode(value) {
                        config.bindings.insert(action.into(), key.into());
                    }
                }
                _ => {}
            }
        }
        Ok(config)
    }
}
fn legacy_scancode(n: i32) -> Option<&'static str> {
    Some(match n {
        72 => "Up",
        80 => "Down",
        75 => "Left",
        77 => "Right",
        29 => "Left Ctrl",
        56 => "Left Alt",
        57 => "Space",
        54 => "Right Shift",
        17 => "W",
        30 => "A",
        31 => "S",
        32 => "D",
        16 => "Q",
        18 => "E",
        28 => "Return",
        _ => return None,
    })
}
pub fn atomic_write(path: &Path, data: &[u8]) -> Result<()> {
    let parent = path.parent().context("output has no parent")?;
    fs::create_dir_all(parent)?;
    let mut n = 0u32;
    let (temp, mut file) = loop {
        let p = parent.join(format!(
            ".{}.{}.{}.tmp",
            path.file_name()
                .context("missing output name")?
                .to_string_lossy(),
            std::process::id(),
            n
        ));
        match OpenOptions::new().write(true).create_new(true).open(&p) {
            Ok(f) => break (p, f),
            Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists => n += 1,
            Err(e) => return Err(e.into()),
        }
    };
    let result = (|| -> Result<()> {
        file.write_all(data)?;
        file.sync_all()?;
        fs::rename(&temp, path)?;
        fs::File::open(parent)?.sync_all()?;
        Ok(())
    })();
    if result.is_err() {
        let _ = fs::remove_file(temp);
    }
    result
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct LegacyProgress {
    pub portrait: i32,
    pub sector: u32,
    pub waves: [u32; 3],
    pub difficulties: [u32; 4],
    pub training: bool,
    pub training_completed: bool,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Pilot {
    pub version: u32,
    pub name: String,
    pub callsign: String,
    pub credits: u32,
    pub difficulty: u32,
    pub inventory: BTreeMap<ContentId, u32>,
    pub selected: Option<ContentId>,
    pub completed: Vec<ContentId>,
    pub mission: ContentId,
    pub mods: Vec<ModPin>,
    pub script_state: BTreeMap<String, serde_json::Value>,
    #[serde(default)]
    pub script_rng: BTreeMap<String, crate::simulation::LegacyRng>,
    #[serde(default)]
    pub legacy_progress: Option<LegacyProgress>,
}
impl Default for Pilot {
    fn default() -> Self {
        Self {
            version: 1,
            name: "Pilot".into(),
            callsign: "RAPTOR".into(),
            credits: 0,
            difficulty: 2,
            inventory: [("base:forward_guns".into(), 1), ("base:energy".into(), 100)]
                .into_iter()
                .collect(),
            selected: None,
            completed: vec![],
            mission: "base:sector_1_wave_1".into(),
            mods: vec![],
            script_state: BTreeMap::new(),
            script_rng: BTreeMap::new(),
            legacy_progress: None,
        }
    }
}
impl Pilot {
    pub fn complete_mission(&mut self, registry: &Registry) -> Result<()> {
        let mission = registry
            .missions
            .get(&self.mission)
            .context("completed mission is unavailable")?;
        if !self.completed.contains(&self.mission) {
            self.completed.push(self.mission.clone());
        }
        let original = self
            .mission
            .0
            .strip_prefix("base:sector_")
            .and_then(|s| s.split_once("_wave_"))
            .and_then(|(s, w)| Some((s.parse::<usize>().ok()?, w.parse::<u32>().ok()?)))
            .filter(|(s, w)| (1..=3).contains(s) && (1..=9).contains(w));
        if let Some((sector, wave)) = original.filter(|_| mission.legacy_map.is_some()) {
            let sector = sector - 1;
            let mut progress = self.legacy_progress.clone().unwrap_or(LegacyProgress {
                portrait: 0,
                sector: sector as u32,
                waves: [0; 3],
                difficulties: [self.difficulty; 4],
                training: false,
                training_completed: false,
            });
            progress.difficulties[sector] = self.difficulty;
            let limit = if self.difficulty == 0 { 4 } else { 9 };
            if wave >= limit {
                if self.difficulty == 0 && !progress.training_completed {
                    // Original graduation resets the training ship and awards
                    // three 25-unit shields plus the initial 10,000 credits.
                    self.inventory = [("base:forward_guns".into(), 1), ("base:energy".into(), 75)]
                        .into_iter()
                        .collect();
                    self.selected = None;
                    self.credits = 10000;
                    progress.training_completed = true;
                    for difficulty in &mut progress.difficulties {
                        if *difficulty == 0 {
                            *difficulty = 1;
                        }
                    }
                }
                progress.difficulties[sector] = (self.difficulty + 1).min(3);
                progress.waves[sector] = 0;
                if limit == 4 {
                    progress.waves = [0; 3];
                    progress.sector = 0;
                } else {
                    progress.sector = ((sector + 1) % 3) as u32;
                }
            } else {
                progress.sector = sector as u32;
                progress.waves[sector] = wave;
            }
            let next_sector = progress.sector as usize;
            self.difficulty = progress.difficulties[next_sector];
            self.mission = ContentId(format!(
                "base:sector_{}_wave_{}",
                next_sector + 1,
                progress.waves[next_sector] + 1
            ));
            self.legacy_progress = Some(progress);
        } else if let Some(next) = &mission.next {
            self.mission = next.clone();
        }
        self.validate(registry, &self.mods)
    }
    pub fn demo(sector: usize, registry: &Registry) -> Result<Self> {
        let mut p = Self {
            difficulty: 3,
            credits: 10000,
            ..Self::default()
        };
        p.inventory.insert("base:detect".into(), 1);
        let equipment: &[(u32, u32)] = match sector {
            0 => &[(2, 1), (11, 1), (4, 1), (7, 1), (5, 1), (14, 1)],
            1 => &[(11, 4), (15, 100), (1, 1), (2, 1), (5, 1), (8, 1)],
            2 => &[(11, 4), (15, 100), (1, 1), (2, 1), (13, 1), (8, 1)],
            _ => anyhow::bail!("invalid demo sector"),
        };
        for (index, count) in equipment {
            let item = registry
                .items
                .values()
                .find(|i| i.legacy == Some(*index))
                .context("missing demo item")?;
            p.inventory.insert(item.id.clone(), *count);
        }
        if sector == 1 {
            p.credits += 0x50003;
        } else if sector == 2 {
            p.credits += 0xd5fff;
        }
        // DEMO_MakePlayer advances once after OBJS_Add selects the first
        // special weapon. Match that ordering rather than inventory sorting.
        p.selected = registry
            .items
            .values()
            .find(|i| i.legacy == Some([5, 8, 8][sector]))
            .map(|i| i.id.clone());
        Ok(p)
    }
    pub fn save(&self, path: &Path) -> Result<()> {
        atomic_write(path, &serde_json::to_vec_pretty(self)?)
    }
    pub fn load(path: &Path, registry: &Registry, pins: &[ModPin]) -> Result<Self> {
        let p: Self = serde_json::from_slice(&fs::read(path)?)?;
        p.validate(registry, pins)?;
        Ok(p)
    }
    pub fn validate(&self, registry: &Registry, pins: &[ModPin]) -> Result<()> {
        let p = self;
        ensure!(p.version == 1, "unsupported save version {}", p.version);
        ensure!(
            p.difficulty <= 3 && p.inventory.len() <= 20,
            "invalid pilot difficulty/inventory"
        );
        ensure!(
            p.mods == pins,
            "save requires these mod versions/content: {:?}; enable the matching mods in the Mods screen",
            p.mods
        );
        ensure!(
            registry.missions.contains_key(&p.mission),
            "save mission {} is unavailable",
            p.mission
        );
        for (id, count) in &p.inventory {
            ensure!(
                registry.items.contains_key(id),
                "saved item {id} is unavailable"
            );
            ensure!(
                *count <= registry.items[id].max_count,
                "saved quantity of {id} exceeds capacity"
            );
        }
        if let Some(id) = &p.selected {
            ensure!(
                p.inventory.get(id).is_some_and(|n| *n > 0)
                    && registry.items.get(id).is_some_and(|i| i.special),
                "equipped item {id} is unavailable"
            );
        }
        for id in &p.completed {
            ensure!(
                registry.missions.contains_key(id),
                "completed mission {id} is unavailable"
            );
        }
        if let Some(progress) = &p.legacy_progress {
            ensure!(
                progress.sector < 3
                    && progress.waves.iter().all(|w| *w < 9)
                    && progress.difficulties.iter().all(|d| *d < 4),
                "invalid saved campaign progression"
            );
        }
        ensure!(
            serde_json::to_vec(&p.script_state)?.len() <= 4 * 1024 * 1024,
            "saved script state exceeds limit"
        );
        Ok(())
    }
    pub fn buy(&mut self, id: &ContentId, registry: &Registry) -> Result<()> {
        let item = registry.items.get(id).context("unknown shop item")?;
        ensure!(self.credits >= item.price, "not enough credits");
        let count = self.inventory.get(id).copied().unwrap_or(0);
        ensure!(count < item.max_count, "item capacity reached");
        ensure!(
            count > 0 || self.inventory.len() < 20,
            "ship inventory is full"
        );
        self.credits -= item.price;
        self.inventory.insert(
            id.clone(),
            count.saturating_add(item.initial_count).min(item.max_count),
        );
        Ok(())
    }
    pub fn sell(&mut self, id: &ContentId, registry: &Registry) -> Result<()> {
        let item = registry.items.get(id).context("unknown shop item")?;
        ensure!(
            id.0 != "base:forward_guns" && id.0 != "base:energy",
            "essential ship equipment cannot be sold"
        );
        let count = self.inventory.get_mut(id).context("item is not owned")?;
        ensure!(*count > 0, "item is not owned");
        *count -= 1;
        self.credits = self.credits.saturating_add(item.price / 2);
        if *count == 0 {
            self.inventory.remove(id);
            if self.selected.as_ref() == Some(id) {
                self.selected = None;
            }
        }
        Ok(())
    }
    pub fn import_legacy(path: &Path, registry: &Registry) -> Result<Self> {
        let bytes = fs::read(path)?;
        ensure!(
            (88..=88 + 20 * 24).contains(&bytes.len()) && (bytes.len() - 88) % 24 == 0,
            "invalid legacy save length"
        );
        let head = decrypt(&bytes[..88], b"CASTLE");
        let body = decrypt(&bytes[88..], b"CASTLE");
        let val = |o| crate::assets::i32_at(&head, o);
        let count = val(60)?;
        ensure!(
            count >= 0 && count as usize <= (body.len() / 24),
            "truncated legacy inventory"
        );
        let sector = val(44)?;
        ensure!((0..3).contains(&sector), "invalid legacy sector");
        let wave = val(48 + sector as usize * 4)?;
        ensure!((0..9).contains(&wave), "invalid legacy wave");
        let difficulty = val(64 + sector as usize * 4)?;
        ensure!((0..4).contains(&difficulty), "invalid legacy difficulty");
        let waves = [val(48)?, val(52)?, val(56)?];
        let difficulties = [val(64)?, val(68)?, val(72)?, val(76)?];
        ensure!(
            waves.iter().all(|w| (0..9).contains(w)),
            "invalid legacy campaign progress"
        );
        ensure!(
            difficulties.iter().all(|d| (0..4).contains(d)),
            "invalid legacy campaign difficulty"
        );
        ensure!(
            [val(80)?, val(84)?].iter().all(|f| *f == 0 || *f == 1),
            "invalid legacy training flags"
        );
        let text = |r: std::ops::Range<usize>| {
            String::from_utf8_lossy(head[r].split(|b| *b == 0).next().unwrap()).into_owned()
        };
        let mut p = Self {
            name: text(0..20),
            callsign: text(20..32),
            credits: val(36)? as u32,
            difficulty: difficulty as u32,
            mission: ContentId(format!("base:sector_{}_wave_{}", sector + 1, wave + 1)),
            inventory: BTreeMap::new(),
            legacy_progress: Some(LegacyProgress {
                portrait: val(32)?,
                sector: sector as u32,
                waves: waves.map(|w| w as u32),
                difficulties: difficulties.map(|d| d as u32),
                training: val(80)? != 0,
                training_completed: val(84)? != 0,
            }),
            ..Self::default()
        };
        let special = val(40)?;
        for r in body.chunks_exact(24).take(count as usize) {
            let count = crate::assets::i32_at(r, 8)?;
            let typ = crate::assets::i32_at(r, 12)?;
            ensure!(count >= 0, "negative legacy item count");
            let item = registry
                .items
                .values()
                .find(|i| i.legacy == Some(typ as u32))
                .context("unknown legacy item")?;
            p.inventory.insert(item.id.clone(), count as u32);
            if typ == special {
                p.selected = Some(item.id.clone());
            }
        }
        for s in 0..3 {
            let w = val(48 + s * 4)?;
            for i in 1..=w {
                p.completed
                    .push(ContentId(format!("base:sector_{}_wave_{i}", s + 1)));
            }
        }
        p.validate(registry, &[])?;
        Ok(p)
    }
}
fn decrypt(bytes: &[u8], key: &[u8]) -> Vec<u8> {
    let mut index = 25 % key.len();
    let mut previous = key[index];
    bytes
        .iter()
        .map(|x| {
            let clear = x.wrapping_sub(key[index]).wrapping_sub(previous);
            previous = *x;
            index = (index + 1) % key.len();
            clear
        })
        .collect()
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn writes_replace_atomically() {
        let tmp = tempfile::tempdir().unwrap();
        let p = tmp.path().join("save.json");
        atomic_write(&p, b"first").unwrap();
        atomic_write(&p, b"second").unwrap();
        assert_eq!(fs::read(p).unwrap(), b"second");
        assert_eq!(fs::read_dir(tmp.path()).unwrap().count(), 1);
    }
}
