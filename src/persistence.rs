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
        #[cfg(windows)]
        return Self::windows_from_env(|name| std::env::var_os(name));
        #[cfg(not(windows))]
        Self::unix_from_env(|name| std::env::var_os(name))
    }
    #[cfg(any(not(windows), test))]
    fn unix_from_env(mut env: impl FnMut(&str) -> Option<std::ffi::OsString>) -> Result<Self> {
        let home = PathBuf::from(env("HOME").context("HOME is unset")?);
        let mut dir = |name: &str, fallback: &str| {
            env(name)
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
    #[cfg(any(windows, test))]
    fn windows_from_env(mut env: impl FnMut(&str) -> Option<std::ffi::OsString>) -> Result<Self> {
        let mut dir = |name: &str| {
            env(name)
                .filter(|value| !value.is_empty())
                .map(PathBuf::from)
        };
        let profile = dir("USERPROFILE");
        // Respect redirected application-data folders. A normal Windows login
        // provides these variables; USERPROFILE also supports stripped-down
        // launch environments without relying on Unix HOME or XDG variables.
        let roaming = dir("APPDATA")
            .or_else(|| profile.as_ref().map(|p| p.join("AppData/Roaming")))
            .context("APPDATA and USERPROFILE are unset; cannot locate Windows saves")?;
        let local = dir("LOCALAPPDATA")
            .or_else(|| profile.as_ref().map(|p| p.join("AppData/Local")))
            .context("LOCALAPPDATA and USERPROFILE are unset; cannot locate Windows cache")?;
        Ok(Self {
            data: roaming.join("RaptorReplica"),
            config: roaming.join("RaptorReplica"),
            cache: local.join("RaptorReplica/cache"),
            // The legacy SDL_GetPrefPath("", "Raptor") location on Windows.
            legacy: roaming.join("Raptor"),
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
            height: 720,
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
                ("special", "Z"),
                ("cycle", "Left Alt"),
                ("bomb", "Space"),
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
            toml::from_str(&fs::read_to_string(&path)?)?
        } else {
            Self::import_ini(&paths.legacy.join("SETUP.INI"))?
        };
        c.migrate_default_bindings(path.exists());
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
        // Missing INI keys inherit the original engine's keyboard defaults.
        // After import, migrate only an unchanged legacy action trio.
        for (action, key) in [
            ("special", "Left Alt"),
            ("cycle", "Space"),
            ("bomb", "Right Shift"),
        ] {
            config.bindings.insert(action.into(), key.into());
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
        config.migrate_default_bindings(false);
        Ok(config)
    }
    fn migrate_default_bindings(&mut self, rust_config: bool) {
        let matches =
            |action: &str, key: &str| self.bindings.get(action).is_some_and(|value| value == key);
        if matches("cycle", "Space")
            && matches("special", "Left Alt")
            && (matches("bomb", "Right Shift") || rust_config && matches("bomb", "B"))
        {
            self.bindings.insert("cycle".into(), "Left Alt".into());
            self.bindings.insert("bomb".into(), "Space".into());
            // Keep unrelated custom keys; choose a free item-use key if the
            // pilot already assigned Z to movement or firing.
            let special = ["Z", "X", "C", "V", "E", "F"]
                .into_iter()
                .find(|key| {
                    !self
                        .bindings
                        .iter()
                        .any(|(action, bound)| action != "special" && bound.as_str() == *key)
                })
                .unwrap_or("Z");
            self.bindings.insert("special".into(), special.into());
        }
    }
}
fn legacy_scancode(n: i32) -> Option<&'static str> {
    Some(match n {
        0 | 255 => "unbound",
        72 => "Up",
        80 => "Down",
        75 => "Left",
        77 => "Right",
        29 => "Left Ctrl",
        56 => "Left Alt",
        57 => "Space",
        42 => "Left Shift",
        54 => "Right Shift",
        1 => "Escape",
        2 => "1",
        3 => "2",
        4 => "3",
        5 => "4",
        6 => "5",
        7 => "6",
        8 => "7",
        9 => "8",
        10 => "9",
        11 => "0",
        12 => "-",
        14 => "Backspace",
        15 => "Tab",
        17 => "W",
        30 => "A",
        31 => "S",
        32 => "D",
        16 => "Q",
        18 => "E",
        19 => "R",
        20 => "T",
        21 => "Y",
        22 => "U",
        23 => "I",
        24 => "O",
        25 => "P",
        33 => "F",
        34 => "G",
        35 => "H",
        36 => "J",
        37 => "K",
        38 => "L",
        43 => "\\",
        44 => "Z",
        45 => "X",
        46 => "C",
        47 => "V",
        48 => "B",
        49 => "N",
        50 => "M",
        28 => "Return",
        58 => "CapsLock",
        59 => "F1",
        60 => "F2",
        61 => "F3",
        62 => "F4",
        63 => "F5",
        64 => "F6",
        65 => "F7",
        66 => "F8",
        67 => "F9",
        68 => "F10",
        87 => "F11",
        88 => "F12",
        70 => "ScrollLock",
        71 | 0xe047 => "Home",
        79 | 0xe04f => "End",
        73 | 0xe049 => "PageUp",
        81 | 0xe051 => "PageDown",
        82 | 0xe052 => "Insert",
        83 | 0xe053 => "Delete",
        0xe038 => "Right Alt",
        0xe010 | 0xe01d => "Right Ctrl",
        0xe01c => "Keypad Enter",
        0xe048 => "Up",
        0xe050 => "Down",
        0xe04b => "Left",
        0xe04d => "Right",
        _ => return None,
    })
}
#[cfg(test)]
mod binding_tests {
    use super::*;
    fn paths(root: &Path) -> Paths {
        Paths {
            data: root.join("data"),
            config: root.join("config"),
            cache: root.join("cache"),
            legacy: root.join("legacy"),
        }
    }
    #[test]
    fn default_controls_use_space_bombs_and_alt_cycling_with_a_separate_item_key() {
        let config = Config::default();
        assert_eq!(config.bindings["bomb"], "Space");
        assert_eq!(config.bindings["cycle"], "Left Alt");
        assert_eq!(config.bindings["special"], "Z");
        assert_eq!(config.bindings["fire"], "Left Ctrl");
        assert_eq!(
            config
                .bindings
                .values()
                .collect::<std::collections::BTreeSet<_>>()
                .len(),
            config.bindings.len()
        );
    }
    #[test]
    fn loading_known_earlier_default_trios_preserves_other_custom_settings() {
        for bomb in ["Right Shift", "B"] {
            let dir = tempfile::tempdir().unwrap();
            let paths = paths(dir.path());
            let mut old = Config::default();
            old.bindings.insert("cycle".into(), "Space".into());
            old.bindings.insert("special".into(), "Left Alt".into());
            old.bindings.insert("bomb".into(), bomb.into());
            old.bindings.insert("up".into(), "W".into());
            old.bindings.insert("fire".into(), "Right Ctrl".into());
            old.scale = 2;
            old.music_volume = 31;
            old.save(&paths).unwrap();
            let source = fs::read(paths.config.join("config.toml")).unwrap();
            let migrated = Config::load(&paths).unwrap();
            assert_eq!(migrated.bindings["cycle"], "Left Alt");
            assert_eq!(migrated.bindings["bomb"], "Space");
            assert_eq!(migrated.bindings["special"], "Z");
            assert_eq!(migrated.bindings["up"], "W");
            assert_eq!(migrated.bindings["fire"], "Right Ctrl");
            assert_eq!((migrated.scale, migrated.music_volume), (2, 31));
            assert_eq!(fs::read(paths.config.join("config.toml")).unwrap(), source);
            migrated.save(&paths).unwrap();
            assert_eq!(Config::load(&paths).unwrap().bindings, migrated.bindings);
        }
    }
    #[test]
    fn customized_action_trios_are_not_migrated() {
        for (action, key) in [("cycle", "Q"), ("special", "E"), ("bomb", "C")] {
            let dir = tempfile::tempdir().unwrap();
            let paths = paths(dir.path());
            let mut config = Config::default();
            for (a, k) in [
                ("cycle", "Space"),
                ("special", "Left Alt"),
                ("bomb", "Right Shift"),
            ] {
                config.bindings.insert(a.into(), k.into());
            }
            config.bindings.insert(action.into(), key.into());
            config.save(&paths).unwrap();
            assert_eq!(Config::load(&paths).unwrap().bindings, config.bindings);
        }
    }
    #[test]
    fn migration_avoids_a_custom_binding_on_the_new_item_key() {
        let mut config = Config::default();
        for (a, k) in [
            ("cycle", "Space"),
            ("special", "Left Alt"),
            ("bomb", "B"),
            ("fire", "Z"),
        ] {
            config.bindings.insert(a.into(), k.into());
        }
        config.migrate_default_bindings(true);
        assert_eq!(config.bindings["fire"], "Z");
        assert_eq!(config.bindings["special"], "X");
    }
    #[test]
    fn legacy_custom_shift_and_letter_controls_import_without_default_migration() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("SETUP.INI");
        let source = b"[Keyboard]\nChangeSp=42\nFireSp=44\nMegaFire=57\nMoveUp=17\n";
        fs::write(&path, source).unwrap();
        let config = Config::import_ini(&path).unwrap();
        assert_eq!(config.bindings["cycle"], "Left Shift");
        assert_eq!(config.bindings["special"], "Z");
        assert_eq!(config.bindings["bomb"], "Space");
        assert_eq!(config.bindings["up"], "W");
        assert_eq!(fs::read(&path).unwrap(), source);
    }
    #[test]
    fn custom_legacy_b_bomb_and_disabled_special_are_preserved() {
        let dir = tempfile::tempdir().unwrap();
        let paths = paths(dir.path());
        fs::create_dir_all(&paths.legacy).unwrap();
        let path = paths.legacy.join("SETUP.INI");
        fs::write(&path, b"[Keyboard]\nMegaFire=48\n").unwrap();
        let config = Config::load(&paths).unwrap();
        assert_eq!(config.bindings["bomb"], "B");
        assert_eq!(config.bindings["cycle"], "Space");
        assert_eq!(config.bindings["special"], "Left Alt");
        fs::write(&path, b"[Keyboard]\nFireSp=0\n").unwrap();
        assert_eq!(Config::load(&paths).unwrap().bindings["special"], "unbound");
    }
    #[cfg(feature = "desktop")]
    #[test]
    fn imported_legacy_keys_use_valid_sdl_names() {
        for code in (1..=88).chain([
            0xe038, 0xe010, 0xe01d, 0xe01c, 0xe048, 0xe050, 0xe04b, 0xe04d, 0xe047, 0xe04f, 0xe049,
            0xe051, 0xe052, 0xe053,
        ]) {
            if let Some(name) = legacy_scancode(code) {
                assert!(
                    sdl2::keyboard::Scancode::from_name(name).is_some(),
                    "invalid SDL key {name}"
                );
            }
        }
    }
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
        // Release the temporary handle before replacement. rename replaces an
        // existing destination on Windows as well as Unix; never remove the
        // previous save first or retry by copying over it.
        drop(file);
        fs::rename(&temp, path)
            .with_context(|| format!("cannot atomically replace {}", path.display()))?;
        // Directory handles opened by ordinary File::open cannot be synced on
        // Windows. The file itself was synced before its name was committed.
        #[cfg(unix)]
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
    /// Unequipped original modules in inventory order. The equipped module's
    /// charge remains inventory[base:super_shield] for version-one compatibility.
    #[serde(default)]
    pub super_shield_reserves: Vec<u32>,
    #[serde(default)]
    pub shield_recharge_ticks: u32,
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

/// Differences the player can explicitly accept when loading a valid save.
/// Missing content remains stored in the pilot until its package is restored.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SaveMismatch {
    MissingMod(ModPin),
    ChangedMod {
        saved: ModPin,
        active: ModPin,
    },
    ChangedLoadOrder {
        saved: Vec<String>,
        active: Vec<String>,
    },
    MissingItem(ContentId),
    ChangedItemCapacity {
        id: ContentId,
        saved: u32,
        available: u32,
    },
    ChangedShieldCapacity {
        saved: u32,
        available: u32,
    },
    UnavailableSelectedItem(ContentId),
    MissingMission(ContentId),
    MissingCompletedMission(ContentId),
}
impl std::fmt::Display for SaveMismatch {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::MissingMod(pin) => write!(
                f,
                "Save requires mod {} {}; enable the matching mods in the Mods screen, or keep its saved content unavailable for now",
                pin.id, pin.version
            ),
            Self::ChangedMod { saved, active } => {
                let reason = match (saved.version != active.version, saved.hash != active.hash) {
                    (true, true) => "version and content changed",
                    (true, false) => "version changed",
                    (false, true) => "content changed",
                    (false, false) => "package changed",
                };
                write!(
                    f,
                    "Mod {}: saved {}, active {} ({reason})",
                    saved.id, saved.version, active.version
                )
            }
            Self::ChangedLoadOrder { saved, active } => write!(
                f,
                "Required mod load order changed: saved {}; active {}",
                saved.join(", "),
                active.join(", ")
            ),
            Self::MissingItem(id) => write!(
                f,
                "saved item {id} is unavailable; it will remain in the pilot"
            ),
            Self::ChangedItemCapacity {
                id,
                saved,
                available,
            } => write!(
                f,
                "Item {id}: saved quantity {saved} exceeds current capacity {available}; saved quantity will be retained"
            ),
            Self::ChangedShieldCapacity { saved, available } => write!(
                f,
                "Saved reserve shield charge {saved} exceeds current capacity {available}; saved charge will be retained"
            ),
            Self::UnavailableSelectedItem(id) => {
                write!(f, "Equipped item {id} is unavailable as a selectable item")
            }
            Self::MissingMission(id) => write!(
                f,
                "Save mission {id} is unavailable; choose an available mission in the hangar"
            ),
            Self::MissingCompletedMission(id) => write!(
                f,
                "Completed mission {id} is unavailable; its progression will be retained"
            ),
        }
    }
}
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct SaveCompatibility {
    pub issues: Vec<SaveMismatch>,
}
impl SaveCompatibility {
    pub fn is_compatible(&self) -> bool {
        self.issues.is_empty()
    }
    pub fn messages(&self) -> Vec<String> {
        self.issues.iter().map(ToString::to_string).collect()
    }
}
#[derive(Debug, Clone)]
pub struct PilotLoad {
    pub pilot: Pilot,
    pub compatibility: SaveCompatibility,
}
impl PilotLoad {
    /// Call only after the player accepts the reported compatibility changes.
    pub fn confirm_load(self) -> Pilot {
        self.pilot
    }
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
            super_shield_reserves: vec![],
            shield_recharge_ticks: 0,
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
        self.advance_mission(registry)?;
        self.validate(registry, &self.mods)
    }
    pub fn complete_mission_tolerant(&mut self, registry: &Registry) -> Result<()> {
        self.advance_mission(registry)?;
        self.validate_tolerant(registry)
    }
    fn advance_mission(&mut self, registry: &Registry) -> Result<()> {
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
                    let unavailable = self
                        .inventory
                        .iter()
                        .filter(|(id, _)| !registry.items.contains_key(*id))
                        .map(|(id, count)| (id.clone(), *count))
                        .collect::<BTreeMap<_, _>>();
                    let unavailable_selected = self
                        .selected
                        .as_ref()
                        .filter(|id| unavailable.contains_key(*id))
                        .cloned();
                    self.inventory = [("base:forward_guns".into(), 1), ("base:energy".into(), 75)]
                        .into_iter()
                        .collect();
                    self.inventory.extend(unavailable);
                    self.selected = unavailable_selected;
                    self.super_shield_reserves.clear();
                    self.shield_recharge_ticks = 0;
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
        } else if let Some(next) = registry
            .campaigns
            .values()
            .find(|campaign| campaign.missions.contains(&self.mission))
            .and_then(|campaign| {
                campaign
                    .missions
                    .iter()
                    .position(|id| id == &self.mission)
                    .and_then(|position| campaign.missions.get(position + 1))
            })
        {
            // Campaign order supplies progression without replacing mission
            // definitions, their asset owners or their saved script identities.
            self.mission = next.clone();
        }
        Ok(())
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
        let loaded = Self::inspect_load(path, registry, pins)?;
        ensure!(
            loaded.compatibility.is_compatible(),
            "{}",
            loaded.compatibility.messages().join("; ")
        );
        Ok(loaded.pilot)
    }
    pub fn validate(&self, registry: &Registry, pins: &[ModPin]) -> Result<()> {
        self.validate_tolerant(registry)?;
        let compatibility = self.compatibility_report(registry, pins);
        ensure!(
            compatibility.is_compatible(),
            "{}",
            compatibility.messages().join("; ")
        );
        Ok(())
    }
    /// Read and inspect without changing the save. Compatibility differences
    /// require an explicit user decision; malformed saves remain hard errors.
    pub fn inspect_load(path: &Path, registry: &Registry, pins: &[ModPin]) -> Result<PilotLoad> {
        let pilot: Self = serde_json::from_slice(&fs::read(path)?)?;
        pilot.validate_tolerant(registry)?;
        let compatibility = pilot.compatibility_report(registry, pins);
        Ok(PilotLoad {
            pilot,
            compatibility,
        })
    }
    /// Validate save structure while retaining content that is currently absent
    /// or changed. Runtime registry lookups decide which equipment can be used.
    pub fn validate_tolerant(&self, _registry: &Registry) -> Result<()> {
        let p = self;
        ensure!(p.version == 1, "unsupported save version {}", p.version);
        ensure!(
            p.difficulty <= 3 && p.inventory_slots() <= 20 && p.shield_recharge_ticks <= 96,
            "invalid pilot difficulty/inventory"
        );
        // No valid API-v1 definition can exceed this quantity. Keep the same
        // global bound even when its particular item definition is missing.
        ensure!(
            p.inventory
                .values()
                .chain(&p.super_shield_reserves)
                .all(|count| *count <= 1_000_000),
            "saved inventory quantity exceeds API limit"
        );
        ensure!(
            p.super_shield_reserves.is_empty()
                || p.inventory
                    .contains_key(&ContentId::from("base:super_shield")),
            "reserve shields require an equipped module"
        );
        p.mission.validate().context("invalid saved mission ID")?;
        for id in p.inventory.keys() {
            id.validate().context("invalid saved item ID")?;
        }
        if let Some(id) = &p.selected {
            ensure!(
                p.inventory.get(id).is_some_and(|n| *n > 0),
                "equipped item {id} is not owned"
            );
        }
        for id in &p.completed {
            id.validate().context("invalid completed mission ID")?;
        }
        let mut mod_ids = std::collections::BTreeSet::new();
        for pin in &p.mods {
            ensure!(mod_ids.insert(&pin.id), "duplicate saved mod {}", pin.id);
            ensure!(
                !pin.id.is_empty()
                    && pin.id.len() <= 128
                    && pin
                        .id
                        .chars()
                        .all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || "_-".contains(c))
                    && !pin.version.is_empty()
                    && pin.version.len() <= 128
                    && !pin.hash.is_empty()
                    && pin.hash.len() <= 256,
                "invalid saved mod pin {}",
                pin.id
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
        ensure!(
            serde_json::to_vec(&p.script_rng)?.len() <= 4 * 1024 * 1024,
            "saved script RNG exceeds limit"
        );
        Ok(())
    }
    pub fn compatibility_report(&self, registry: &Registry, pins: &[ModPin]) -> SaveCompatibility {
        let mut issues = vec![];
        for saved in &self.mods {
            match pins.iter().find(|active| active.id == saved.id) {
                None => issues.push(SaveMismatch::MissingMod(saved.clone())),
                Some(active) if active != saved => issues.push(SaveMismatch::ChangedMod {
                    saved: saved.clone(),
                    active: active.clone(),
                }),
                _ => {}
            }
        }
        let saved_order: Vec<_> = self
            .mods
            .iter()
            .filter(|saved| pins.iter().any(|active| active.id == saved.id))
            .map(|saved| saved.id.clone())
            .collect();
        let active_order: Vec<_> = pins
            .iter()
            .filter(|active| self.mods.iter().any(|saved| saved.id == active.id))
            .map(|active| active.id.clone())
            .collect();
        if saved_order != active_order {
            issues.push(SaveMismatch::ChangedLoadOrder {
                saved: saved_order,
                active: active_order,
            });
        }
        if !registry.missions.contains_key(&self.mission) {
            issues.push(SaveMismatch::MissingMission(self.mission.clone()));
        }
        for (id, count) in &self.inventory {
            match registry.items.get(id) {
                None => issues.push(SaveMismatch::MissingItem(id.clone())),
                Some(item) if *count > item.max_count => {
                    issues.push(SaveMismatch::ChangedItemCapacity {
                        id: id.clone(),
                        saved: *count,
                        available: item.max_count,
                    })
                }
                _ => {}
            }
        }
        if let Some(item) = registry.items.get(&ContentId::from("base:super_shield")) {
            if let Some(charge) = self
                .super_shield_reserves
                .iter()
                .copied()
                .find(|charge| *charge > item.max_count)
            {
                issues.push(SaveMismatch::ChangedShieldCapacity {
                    saved: charge,
                    available: item.max_count,
                });
            }
        }
        if let Some(id) = &self.selected {
            if !registry.items.get(id).is_some_and(|item| item.special) {
                issues.push(SaveMismatch::UnavailableSelectedItem(id.clone()));
            }
        }
        for id in &self.completed {
            if !registry.missions.contains_key(id) {
                issues.push(SaveMismatch::MissingCompletedMission(id.clone()));
            }
        }
        SaveCompatibility { issues }
    }
    /// Capture active runtime data without discarding state or pins belonging
    /// to disabled packages. Active package order and hashes become current;
    /// unavailable package pins remain recorded for future restoration.
    pub fn merge_runtime_snapshot(
        &mut self,
        pins: &[ModPin],
        states: &BTreeMap<String, serde_json::Value>,
        rng: &BTreeMap<String, crate::simulation::LegacyRng>,
    ) {
        let missing: Vec<_> = self
            .mods
            .iter()
            .filter(|saved| !pins.iter().any(|active| active.id == saved.id))
            .cloned()
            .collect();
        self.mods = pins.to_vec();
        self.mods.extend(missing);
        self.script_state.extend(states.clone());
        self.script_rng.extend(rng.clone());
    }
    pub fn buy(&mut self, id: &ContentId, registry: &Registry) -> Result<()> {
        let item = registry.items.get(id).context("unknown shop item")?;
        ensure!(self.credits >= item.price, "not enough credits");
        if id.0 == "base:super_shield" {
            ensure!(
                self.item_count(id) < 5,
                "ship already carries five super-shield modules"
            );
            ensure!(self.inventory_slots() < 20, "ship inventory is full");
            self.credits -= item.price;
            if self.inventory.contains_key(id) {
                self.super_shield_reserves.push(item.initial_count);
            } else {
                self.inventory.insert(id.clone(), item.initial_count);
            }
            return Ok(());
        }
        let count = self.inventory.get(id).copied().unwrap_or(0);
        ensure!(count < item.max_count, "item capacity reached");
        ensure!(
            self.inventory.contains_key(id) || self.inventory_slots() < 20,
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
            id.0 != "base:forward_guns",
            "essential ship equipment cannot be sold"
        );
        if id.0 == "base:super_shield" {
            let charge = self.inventory.get(id).context("item is not owned")?;
            ensure!(
                *charge >= item.initial_count,
                "only a fully charged equipped super-shield module can be sold"
            );
            self.credits = self.credits.saturating_add(item.price / 2);
            if self.super_shield_reserves.is_empty() {
                self.inventory.remove(id);
            } else {
                self.inventory
                    .insert(id.clone(), self.super_shield_reserves.remove(0));
            }
            return Ok(());
        }
        if id.0 == "base:energy" {
            let count = self.inventory.get_mut(id).context("item is not owned")?;
            ensure!(
                *count > item.initial_count,
                "retain at least some normal shield energy"
            );
            *count -= item.initial_count;
            self.credits = self.credits.saturating_add(item.price / 2);
            return Ok(());
        }
        let count = self.inventory.get_mut(id).context("item is not owned")?;
        ensure!(*count > 0, "item is not owned");
        *count -= 1;
        self.credits = self.credits.saturating_add(item.resale_price());
        if *count == 0 {
            self.inventory.remove(id);
            if self.selected.as_ref() == Some(id) {
                self.selected = None;
            }
        }
        Ok(())
    }
    /// Actual owned quantity, distinct from original shield charge units.
    pub fn item_count(&self, id: &ContentId) -> u32 {
        if id.0 == "base:super_shield" {
            self.inventory.contains_key(id) as u32 + self.super_shield_reserves.len() as u32
        } else {
            self.inventory.get(id).copied().unwrap_or(0)
        }
    }
    pub fn inventory_slots(&self) -> usize {
        self.inventory.len() + self.super_shield_reserves.len()
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
        let mut shields = vec![];
        let mut equipped = None;
        for r in body.chunks_exact(24).take(count as usize) {
            let count = crate::assets::i32_at(r, 8)?;
            let typ = crate::assets::i32_at(r, 12)?;
            ensure!(count >= 0, "negative legacy item count");
            let item = registry
                .items
                .values()
                .find(|i| i.legacy == Some(typ as u32))
                .context("unknown legacy item")?;
            if typ == 15 {
                let inuse = crate::assets::i32_at(r, 20)?;
                ensure!(
                    (0..=1).contains(&inuse),
                    "invalid legacy shield equipment flag"
                );
                if inuse != 0 {
                    ensure!(
                        equipped.is_none(),
                        "multiple equipped legacy shield modules"
                    );
                    equipped = Some(shields.len());
                }
                shields.push(count as u32);
            } else {
                p.inventory.insert(item.id.clone(), count as u32);
            }
            if typ == special {
                p.selected = Some(item.id.clone());
            }
        }
        if !shields.is_empty() {
            let active = shields.remove(equipped.unwrap_or(0));
            p.inventory.insert("base:super_shield".into(), active);
            p.super_shield_reserves = shields;
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
    fn environment(values: &[(&str, &str)]) -> impl FnMut(&str) -> Option<std::ffi::OsString> {
        let values = values
            .iter()
            .map(|(key, value)| (key.to_string(), std::ffi::OsString::from(value)))
            .collect::<BTreeMap<_, _>>();
        move |key| values.get(key).cloned()
    }
    #[test]
    fn windows_paths_respect_redirected_data_folders_without_home() {
        let paths = Paths::windows_from_env(environment(&[
            ("APPDATA", "redirected-roaming"),
            ("LOCALAPPDATA", "redirected-local"),
            ("HOME", "unused-unix-home"),
            ("XDG_DATA_HOME", "unused-xdg-data"),
            ("XDG_CONFIG_HOME", "unused-xdg-config"),
            ("XDG_CACHE_HOME", "unused-xdg-cache"),
        ]))
        .unwrap();
        let roaming = Path::new("redirected-roaming");
        assert_eq!(paths.data, roaming.join("RaptorReplica"));
        assert_eq!(paths.config, roaming.join("RaptorReplica"));
        assert_eq!(paths.mods(), roaming.join("RaptorReplica/mods"));
        assert_eq!(
            paths.save_path(3),
            roaming.join("RaptorReplica/pilot-0003.json")
        );
        assert_eq!(paths.legacy, roaming.join("Raptor"));
        assert_eq!(
            paths.cache,
            Path::new("redirected-local").join("RaptorReplica/cache")
        );
    }
    #[test]
    fn windows_paths_fall_back_to_unicode_user_profile() {
        let profile = "profile-Quintine-é-雪";
        let paths = Paths::windows_from_env(environment(&[("USERPROFILE", profile)])).unwrap();
        let profile = Path::new(profile);
        assert_eq!(paths.data, profile.join("AppData/Roaming/RaptorReplica"));
        assert_eq!(paths.config, paths.data);
        assert_eq!(
            paths.cache,
            profile.join("AppData/Local/RaptorReplica/cache")
        );
        assert_eq!(paths.legacy, profile.join("AppData/Roaming/Raptor"));
    }
    #[test]
    fn windows_missing_or_empty_application_paths_fall_back_independently() {
        let paths = Paths::windows_from_env(environment(&[
            ("USERPROFILE", "profile"),
            ("APPDATA", "roaming-redirect"),
            ("LOCALAPPDATA", ""),
        ]))
        .unwrap();
        assert_eq!(
            paths.data,
            Path::new("roaming-redirect").join("RaptorReplica")
        );
        assert_eq!(
            paths.cache,
            Path::new("profile").join("AppData/Local/RaptorReplica/cache")
        );
        let paths = Paths::windows_from_env(environment(&[
            ("USERPROFILE", "profile"),
            ("APPDATA", ""),
            ("LOCALAPPDATA", "local-redirect"),
        ]))
        .unwrap();
        assert_eq!(
            paths.data,
            Path::new("profile").join("AppData/Roaming/RaptorReplica")
        );
        assert_eq!(
            paths.cache,
            Path::new("local-redirect").join("RaptorReplica/cache")
        );
    }
    #[test]
    fn windows_missing_profile_has_an_actionable_error() {
        let error = Paths::windows_from_env(environment(&[("HOME", "unix-home")])).unwrap_err();
        assert!(error.to_string().contains("APPDATA and USERPROFILE"));
        let error = Paths::windows_from_env(environment(&[("APPDATA", "roaming")])).unwrap_err();
        assert!(error.to_string().contains("LOCALAPPDATA and USERPROFILE"));
    }
    #[test]
    fn unix_paths_keep_home_and_xdg_behavior() {
        let paths = Paths::unix_from_env(environment(&[("HOME", "unix-home")])).unwrap();
        let home = Path::new("unix-home");
        assert_eq!(paths.data, home.join(".local/share/RaptorReplica"));
        assert_eq!(paths.config, home.join(".config/RaptorReplica"));
        assert_eq!(paths.cache, home.join(".cache/RaptorReplica"));
        assert_eq!(paths.legacy, home.join(".local/share/Raptor"));
        let paths = Paths::unix_from_env(environment(&[
            ("HOME", "unix-home"),
            ("XDG_DATA_HOME", "custom-data"),
            ("XDG_CONFIG_HOME", "custom-config"),
            ("XDG_CACHE_HOME", "custom-cache"),
        ]))
        .unwrap();
        assert_eq!(paths.data, Path::new("custom-data").join("RaptorReplica"));
        assert_eq!(
            paths.config,
            Path::new("custom-config").join("RaptorReplica")
        );
        assert_eq!(paths.cache, Path::new("custom-cache").join("RaptorReplica"));
        assert!(Paths::unix_from_env(environment(&[("APPDATA", "roaming")])).is_err());
    }
    #[test]
    fn writes_replace_atomically() {
        let tmp = tempfile::tempdir().unwrap();
        let p = tmp.path().join("save.json");
        atomic_write(&p, b"first").unwrap();
        atomic_write(&p, b"second").unwrap();
        assert_eq!(fs::read(p).unwrap(), b"second");
        assert_eq!(fs::read_dir(tmp.path()).unwrap().count(), 1);
    }
    #[test]
    fn replacement_failure_preserves_the_destination_and_cleans_the_temporary() {
        let tmp = tempfile::tempdir().unwrap();
        let p = tmp.path().join("save.json");
        fs::create_dir(&p).unwrap();
        let sentinel = p.join("keep-original");
        fs::write(&sentinel, b"original contents").unwrap();
        let error = atomic_write(&p, b"new save").unwrap_err();
        assert!(error.to_string().contains("cannot atomically replace"));
        assert_eq!(fs::read(sentinel).unwrap(), b"original contents");
        assert_eq!(fs::read_dir(tmp.path()).unwrap().count(), 1);
    }
    #[test]
    fn temporary_name_collision_and_unicode_backup_are_preserved() {
        let tmp = tempfile::tempdir().unwrap();
        let p = tmp.path().join("pilot-é-雪.json");
        let stale = tmp
            .path()
            .join(format!(".pilot-é-雪.json.{}.0.tmp", std::process::id()));
        fs::write(&stale, b"interrupted write").unwrap();
        atomic_write(&p, b"original pilot").unwrap();
        let backup = tmp.path().join("pilot-é-雪.original.json");
        atomic_write(&backup, &fs::read(&p).unwrap()).unwrap();
        atomic_write(&p, b"updated pilot").unwrap();
        assert_eq!(fs::read(&p).unwrap(), b"updated pilot");
        assert_eq!(fs::read(&backup).unwrap(), b"original pilot");
        assert_eq!(fs::read(&stale).unwrap(), b"interrupted write");
        assert_eq!(fs::read_dir(tmp.path()).unwrap().count(), 3);
    }
    #[cfg(windows)]
    #[test]
    fn locked_windows_save_is_never_deleted_before_replacement() {
        use std::os::windows::fs::OpenOptionsExt;
        let tmp = tempfile::tempdir().unwrap();
        let p = tmp.path().join("save.json");
        atomic_write(&p, b"original pilot").unwrap();
        let locked = OpenOptions::new()
            .read(true)
            .share_mode(0)
            .open(&p)
            .unwrap();
        assert!(atomic_write(&p, b"updated pilot").is_err());
        assert!(p.exists());
        assert_eq!(fs::read_dir(tmp.path()).unwrap().count(), 1);
        drop(locked);
        assert_eq!(fs::read(&p).unwrap(), b"original pilot");
        atomic_write(&p, b"updated pilot").unwrap();
        assert_eq!(fs::read(&p).unwrap(), b"updated pilot");
    }
}
