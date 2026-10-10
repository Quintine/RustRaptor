//! SDL host, interpolated scene presentation and local game menus.
use crate::{
    assets::{Catalog, Sprite},
    audio::{DigitalSample, Mixer, MusScore},
    cinematics::{Cinematic, Kind as MovieKind},
    content::{Art, ContentId, Registry, art_sprite_variant},
    hd::HdAssets,
    modding::{self, ActiveMods, Discovery},
    persistence::{Config, Paths, Pilot},
    render::{BitmapFont, Canvas, SpriteCache, nearest, upscale},
    simulation::{Clock, Input, Outcome, World},
};
use anyhow::{Context, Result, anyhow};
use sdl2::{
    audio::{AudioCallback, AudioDevice, AudioSpecDesired},
    controller::{Axis, Button},
    event::Event,
    keyboard::{Keycode, Scancode},
    pixels::PixelFormatEnum,
    rect::Rect,
    video::FullscreenType,
};
use std::{
    collections::BTreeMap,
    path::PathBuf,
    time::{Duration, Instant},
};

impl AudioCallback for Mixer {
    type Channel = i16;
    fn callback(&mut self, out: &mut [i16]) {
        self.mix(out)
    }
}
#[derive(Clone, Copy, PartialEq, Eq)]
enum Screen {
    Main,
    Missions,
    Shop,
    Inventory,
    Mods,
    Options,
    Game,
    Pause,
    Results,
    Help,
    Credits,
    Pilots,
    Diagnostics,
    Bindings,
    Cinematic,
}
struct Host {
    catalog: Catalog,
    base: Registry,
    active: ActiveMods,
    paths: Paths,
    mods_root: PathBuf,
    discovery: Discovery,
    config: Config,
    hd: HdAssets,
    read_only: bool,
    pending: Vec<String>,
    pilot: Pilot,
    slot: usize,
    pilot_error: Option<String>,
    queued_cycle: bool,
    queued_bomb: bool,
    awaiting_binding: Option<String>,
    world: Option<World>,
    cinematic: Option<Cinematic>,
    movie_return: Screen,
    screen: Screen,
    previous: Screen,
    selected: usize,
    message: String,
    font: BitmapFont,
    cache: SpriteCache,
    raw: BTreeMap<u32, Sprite>,
    mod_art: BTreeMap<String, Sprite>,
    palette: [[u8; 3]; 256],
    audio: Option<AudioDevice<Mixer>>,
    mod_audio: BTreeMap<ContentId, DigitalSample>,
    desired_music: Option<u32>,
    clock: Clock,
}
impl Host {
    fn new(
        catalog: Catalog,
        base: Registry,
        paths: Paths,
        mods_root: PathBuf,
        read_only: bool,
    ) -> Result<Self> {
        let config = Config::load(&paths)?;
        let discovery = modding::discover(&mods_root);
        let mut message = String::new();
        let mut active =
            match ActiveMods::build(&base, &discovery, &config.enabled_mods, Some(&catalog)) {
                Ok(a) => a,
                Err(e) => {
                    message = format!("Mod load failed: {e:#}");
                    ActiveMods::build(&base, &discovery, &[], Some(&catalog))?
                }
            };
        let mut pilot_error = None;
        let mut pilot = if paths.save_path(0).exists() {
            match Pilot::load(&paths.save_path(0), &active.registry, &active.pins) {
                Ok(p) => p,
                Err(e) => {
                    message = format!("Saved pilot unavailable: {e:#}");
                    pilot_error = Some(message.clone());
                    Pilot::default()
                }
            }
        } else {
            let legacy = paths.legacy.join("CHAR0000.FIL");
            if legacy.exists() {
                match Pilot::import_legacy(&legacy, &active.registry) {
                    Ok(p) => p,
                    Err(e) => {
                        message = format!("Legacy import failed: {e:#}");
                        Pilot::default()
                    }
                }
            } else {
                Pilot::default()
            }
        };
        if !paths.save_path(0).exists() {
            pilot.mods = active.pins.clone();
        }
        restore_scripts(&mut active.scripts, &pilot);
        let hd = HdAssets::load(&catalog.root.join("hd"), &catalog);
        let palette = catalog.palette()?;
        let font = BitmapFont::decode(&catalog.named("SYSTEM_FNT")?)?;
        let cache = SpriteCache::new(Some(paths.cache.join("sprites")));
        let pending = config.enabled_mods.clone();
        Ok(Self {
            catalog,
            base,
            active,
            paths,
            mods_root,
            discovery,
            config,
            hd,
            read_only,
            pending,
            pilot,
            slot: 0,
            pilot_error,
            queued_cycle: false,
            queued_bomb: false,
            awaiting_binding: None,
            world: None,
            cinematic: None,
            movie_return: Screen::Main,
            screen: Screen::Main,
            previous: Screen::Main,
            selected: 0,
            message,
            font,
            cache,
            raw: BTreeMap::new(),
            mod_art: BTreeMap::new(),
            palette,
            audio: None,
            mod_audio: BTreeMap::new(),
            desired_music: None,
            clock: Clock::default(),
        })
    }
    fn go(&mut self, screen: Screen) {
        self.screen = screen;
        self.selected = 0;
    }
    fn save_config(&self) -> Result<()> {
        if self.read_only {
            return Ok(());
        }
        self.config.save(&self.paths)
    }
    fn save(&mut self) -> Result<()> {
        if self.read_only {
            return Ok(());
        }
        self.require_pilot()?;
        self.pilot.script_state = self.active.scripts.states.clone();
        self.pilot.script_rng = self.active.scripts.rng.clone();
        self.pilot
            .validate(&self.active.registry, &self.active.pins)?;
        self.pilot.save(&self.paths.save_path(self.slot))?;
        self.save_config()
    }
    fn music(&mut self, name: &str) {
        self.desired_music = self.catalog.id(name).ok();
        let score = self.catalog.named(name).and_then(|b| MusScore::decode(&b));
        if let (Some(device), Ok(score)) = (&mut self.audio, score) {
            device.lock().play_with_fade(score, true, true);
        }
    }
    fn start(&mut self, id: ContentId) -> Result<()> {
        self.require_pilot()?;
        self.pilot.mission = id.clone();
        self.pilot.difficulty = self.config.difficulty;
        self.active.scripts.states = self.pilot.script_state.clone();
        self.active.scripts.rng = self.pilot.script_rng.clone();
        self.world = Some(World::new(&id, &self.pilot, &self.active.registry)?);
        if let Some(music) = self.active.registry.missions[&id].music {
            self.desired_music = Some(music);
            if let Ok(score) = self.catalog.read(music).and_then(|b| MusScore::decode(&b)) {
                if let Some(audio) = &mut self.audio {
                    audio.lock().play_with_fade(score, true, true);
                }
            }
        }
        self.clock = Clock::default();
        self.go(Screen::Game);
        Ok(())
    }
    fn show_movie(&mut self, kind: MovieKind, return_to: Screen) -> Result<()> {
        let movie = Cinematic::load(&self.catalog, kind)?;
        self.cinematic = Some(movie);
        self.movie_return = return_to;
        match kind {
            MovieKind::Intro => self.music("RINTRO_MUS"),
            MovieKind::Death => self.music("RAP5_MUS"),
            _ => {}
        }
        self.go(Screen::Cinematic);
        Ok(())
    }
    fn finish_movie(&mut self) {
        self.cinematic = None;
        self.go(self.movie_return);
        if self.screen == Screen::Main {
            self.music("MAINMENU_MUS");
        }
    }
    fn items(&self) -> Vec<ContentId> {
        self.active
            .registry
            .items
            .values()
            .filter(|i| i.legacy.is_none_or(|n| n < 18))
            .map(|i| i.id.clone())
            .collect()
    }
    fn missions(&self) -> Vec<ContentId> {
        let mut ids: Vec<_> = self
            .active
            .registry
            .campaigns
            .values()
            .flat_map(|c| c.missions.clone())
            .collect();
        let mut seen = std::collections::BTreeSet::new();
        ids.retain(|id| seen.insert(id.clone()));
        for id in self.active.registry.missions.keys() {
            if seen.insert(id.clone()) {
                ids.push(id.clone());
            }
        }
        ids
    }
    fn rows(&self) -> Vec<String> {
        match self.screen {
            Screen::Main => vec![
                "Continue / Hangar",
                "Select Mission",
                "Shop",
                "Inventory",
                "Mods",
                "Options",
                "Load Pilot",
                "Help",
                "Credits",
                "Watch intro",
                "Quit",
            ]
            .into_iter()
            .map(str::to_string)
            .collect(),
            Screen::Missions => self
                .missions()
                .iter()
                .map(|id| {
                    format!(
                        "{}{}",
                        if self.pilot.completed.contains(id) {
                            "+ "
                        } else {
                            "  "
                        },
                        self.active.registry.missions[id].name
                    )
                })
                .collect(),
            Screen::Shop => self
                .items()
                .iter()
                .map(|id| {
                    let i = &self.active.registry.items[id];
                    format!("{}  ${}", i.name, i.price)
                })
                .collect(),
            Screen::Inventory => self
                .pilot
                .inventory
                .iter()
                .filter_map(|(id, n)| {
                    self.active.registry.items.get(id).map(|i| {
                        format!(
                            "{} x{}{}",
                            i.name,
                            n,
                            if self.pilot.selected.as_ref() == Some(id) {
                                " [EQUIPPED]"
                            } else {
                                ""
                            }
                        )
                    })
                })
                .collect(),
            Screen::Pilots => self
                .slots()
                .iter()
                .map(|n| format!("Pilot slot {:04}", n))
                .collect(),
            Screen::Diagnostics => self.diagnostics(),
            Screen::Bindings => ACTIONS
                .iter()
                .map(|action| {
                    format!(
                        "{}: {}",
                        action,
                        self.config
                            .bindings
                            .get(*action)
                            .map(String::as_str)
                            .unwrap_or("unbound")
                    )
                })
                .chain(std::iter::once("Restore default bindings".into()))
                .collect(),
            Screen::Mods => {
                let mut r = vec!["Apply selections".into(), "Rescan installed mods".into()];
                let mut ids = self.pending.clone();
                for id in self.discovery.mods.keys() {
                    if !ids.contains(id) {
                        ids.push(id.clone());
                    }
                }
                for id in ids {
                    if let Some(m) = self.discovery.mods.get(&id) {
                        r.push(format!(
                            "[{}] {} {}",
                            if self.pending.contains(&id) { "X" } else { " " },
                            m.manifest.name,
                            m.manifest.version
                        ));
                    }
                }
                r
            }
            Screen::Options => vec![
                if self.config.scale == 1 {
                    "Sprite scale: original".into()
                } else {
                    format!("Sprite scale: {}x crisp", self.config.scale)
                },
                format!("Scanlines: {}", self.config.scanlines),
                format!("Fullscreen: {}", self.config.fullscreen),
                format!("Borderless: {}", self.config.borderless),
                format!("4:3 aspect: {}", self.config.aspect_correct),
                format!("Music volume: {}", self.config.music_volume),
                format!("Effects volume: {}", self.config.fx_volume),
                format!("Controls: {}", self.config.control),
                format!(
                    "Difficulty: {}",
                    ["Training", "Rookie", "Veteran", "Elite"][self.config.difficulty as usize]
                ),
                format!("Resolution: {}x{}", self.config.width, self.config.height),
                format!(
                    "HD art: {} ({} frames)",
                    if self.config.hd_mode { "on" } else { "off" },
                    self.hd.coverage()
                ),
                "Keyboard bindings".into(),
                format!("Effects channels: {}", self.config.fx_channels),
            ],
            Screen::Pause => vec!["Resume", "Options", "Mods", "Return to main menu"]
                .into_iter()
                .map(str::to_string)
                .collect(),
            Screen::Results => vec!["Return to hangar".into()],
            _ => vec![],
        }
    }
    fn mod_ids(&self) -> Vec<String> {
        let mut ids = self
            .pending
            .iter()
            .filter(|id| self.discovery.mods.contains_key(*id))
            .cloned()
            .collect::<Vec<_>>();
        for id in self.discovery.mods.keys() {
            if !ids.contains(id) {
                ids.push(id.clone());
            }
        }
        ids
    }
    fn require_pilot(&self) -> Result<()> {
        if let Some(error) = &self.pilot_error {
            return Err(anyhow!(
                "{error}. Restore matching mods, load a compatible pilot, or press N to create a separate pilot."
            ));
        }
        self.pilot
            .validate(&self.active.registry, &self.active.pins)
    }
    fn slots(&self) -> Vec<usize> {
        (0..1000)
            .filter(|n| self.paths.save_path(*n).is_file())
            .collect()
    }
    fn new_pilot(&mut self) -> Result<()> {
        let slot = (0..1000)
            .find(|n| !self.paths.save_path(*n).exists())
            .context("all pilot slots are occupied")?;
        self.slot = slot;
        self.pilot = Pilot {
            mods: self.active.pins.clone(),
            ..Pilot::default()
        };
        self.pilot_error = None;
        self.active.scripts.states.clear();
        self.active.scripts.rng.clear();
        self.message = format!("New pilot in slot {slot:04}");
        Ok(())
    }
    fn diagnostics(&self) -> Vec<String> {
        let mut lines = vec![self.message.clone()];
        if let Some(e) = &self.pilot_error {
            lines.push(e.clone());
        }
        lines.extend(self.discovery.errors.clone());
        lines.extend(self.hd.diagnostics.clone());
        lines.push(format!(
            "HD art coverage: {} supplied frames; remaining artwork uses original sprites",
            self.hd.coverage()
        ));
        lines.push(format!(
            "Active order: {}",
            self.active
                .pins
                .iter()
                .map(|m| m.id.clone())
                .collect::<Vec<_>>()
                .join(", ")
        ));
        lines.extend(self.active.registry.overrides.clone());
        for m in self.discovery.mods.values() {
            lines.push(format!(
                "{} {}: {}",
                m.manifest.id, m.manifest.version, m.manifest.description
            ));
            lines.push(format!(
                "Dependencies: {:?}; conflicts: {:?}",
                m.manifest.dependencies, m.manifest.conflicts
            ));
        }
        lines
            .into_iter()
            .flat_map(|s| {
                s.chars()
                    .collect::<Vec<_>>()
                    .chunks(52)
                    .map(|c| c.iter().collect::<String>())
                    .collect::<Vec<_>>()
            })
            .collect()
    }
    fn apply_mods(&mut self) -> Result<()> {
        let mut candidate = ActiveMods::build(
            &self.base,
            &self.discovery,
            &self.pending,
            Some(&self.catalog),
        )?;
        let mut config = self.config.clone();
        config.enabled_mods = self.pending.clone();
        if !self.read_only {
            config.save(&self.paths)?;
        }
        let saved = self.paths.save_path(self.slot);
        match pilot_for_mods(&saved, &self.pilot, &candidate.registry, &candidate.pins) {
            Ok(pilot) => {
                restore_scripts(&mut candidate.scripts, &pilot);
                self.pilot = pilot;
                self.pilot_error = None;
            }
            Err(e) => self.pilot_error = Some(format!("Pilot slot {:04}: {e:#}", self.slot)),
        }
        self.config = config;
        self.active = candidate;
        self.mod_audio.clear();
        self.mod_art.clear();
        if self.pilot_error.is_some() {
            self.message =
                "Mods applied; pilot requires its saved mods. D: details / N: new pilot".into();
        } else {
            self.message = "Mods applied".into();
        }
        Ok(())
    }
    fn activate(&mut self) -> Result<bool> {
        match self.screen {
            Screen::Main => match self.selected {
                0 => self.start(self.pilot.mission.clone())?,
                1 => self.go(Screen::Missions),
                2 => {
                    self.go(Screen::Shop);
                    self.music("HANGAR_MUS");
                }
                3 => self.go(Screen::Inventory),
                4 => self.go(Screen::Mods),
                5 => {
                    self.previous = Screen::Main;
                    self.go(Screen::Options)
                }
                6 => self.go(Screen::Pilots),
                7 => self.go(Screen::Help),
                8 => self.go(Screen::Credits),
                9 => self.show_movie(MovieKind::Intro, Screen::Main)?,
                10 => return Ok(false),
                _ => {}
            },
            Screen::Missions => {
                if let Some(id) = self.missions().get(self.selected) {
                    self.start(id.clone())?;
                }
            }
            Screen::Pilots => {
                if let Some(slot) = self.slots().get(self.selected).copied() {
                    let p = Pilot::load(
                        &self.paths.save_path(slot),
                        &self.active.registry,
                        &self.active.pins,
                    )?;
                    restore_scripts(&mut self.active.scripts, &p);
                    self.pilot = p;
                    self.slot = slot;
                    self.pilot_error = None;
                    self.message = format!("Loaded pilot slot {slot:04}");
                    self.go(Screen::Main);
                }
            }
            Screen::Shop => {
                self.require_pilot()?;
                if let Some(id) = self.items().get(self.selected) {
                    self.pilot.buy(id, &self.active.registry)?;
                    self.save()?;
                    self.message = "Purchase complete".into();
                }
            }
            Screen::Inventory => {
                self.require_pilot()?;
                if let Some(id) = self.pilot.inventory.keys().nth(self.selected).cloned() {
                    if self
                        .active
                        .registry
                        .items
                        .get(&id)
                        .is_some_and(|i| i.special)
                    {
                        self.pilot.selected = Some(id);
                        self.save()?;
                        self.message = "Weapon equipped".into();
                    }
                }
            }
            Screen::Mods => {
                if self.selected == 0 {
                    if self.world.is_some() {
                        self.config.enabled_mods = self.pending.clone();
                        self.save_config()?;
                        self.message = "Changes pending until the main menu".into();
                    } else {
                        self.apply_mods()?;
                    }
                } else if self.selected == 1 {
                    self.discovery = modding::discover(&self.mods_root);
                    self.message = self.discovery.errors.join("; ");
                } else if let Some(id) = self.mod_ids().get(self.selected - 2).cloned() {
                    if let Some(n) = self.pending.iter().position(|s| s == &id) {
                        self.pending.remove(n);
                    } else {
                        self.pending.push(id);
                    }
                }
            }
            Screen::Options => match self.selected {
                0 => self.config.scale = self.config.scale % 4 + 1,
                1 => self.config.scanlines = !self.config.scanlines,
                2 => self.config.fullscreen = !self.config.fullscreen,
                3 => self.config.borderless = !self.config.borderless,
                4 => self.config.aspect_correct = !self.config.aspect_correct,
                5 => self.config.music_volume = (self.config.music_volume + 16) % 128,
                6 => self.config.fx_volume = (self.config.fx_volume + 16) % 128,
                7 => {
                    self.config.control = match self.config.control.as_str() {
                        "keyboard" => "mouse",
                        "mouse" => "controller",
                        _ => "keyboard",
                    }
                    .into()
                }
                8 => self.config.difficulty = (self.config.difficulty + 1) % 4,
                9 => {
                    if self.config.width == 1280 {
                        self.config.width = 1920;
                        self.config.height = 1080
                    } else {
                        self.config.width = 1280;
                        self.config.height = 960
                    }
                }
                10 => self.config.hd_mode = !self.config.hd_mode,
                11 => self.go(Screen::Bindings),
                12 => self.config.fx_channels = self.config.fx_channels % 8 + 1,
                _ => {}
            },
            Screen::Bindings => {
                if let Some(action) = ACTIONS.get(self.selected) {
                    self.awaiting_binding = Some(action.to_string());
                    self.message = format!("Press a key for {action}; ESC cancels");
                } else {
                    self.config.bindings = Config::default().bindings;
                    self.save_config()?;
                    self.message = "Default bindings restored".into();
                }
            }
            Screen::Pause => match self.selected {
                0 => self.go(Screen::Game),
                1 => {
                    self.previous = Screen::Pause;
                    self.go(Screen::Options)
                }
                2 => self.go(Screen::Mods),
                3 => self.return_main()?,
                _ => {}
            },
            Screen::Results => self.return_main()?,
            _ => {}
        }
        Ok(true)
    }
    fn return_main(&mut self) -> Result<()> {
        self.world = None;
        self.clock = Clock::default();
        if self.pending
            != self
                .active
                .pins
                .iter()
                .map(|m| m.id.clone())
                .collect::<Vec<_>>()
        {
            if let Err(e) = self.apply_mods() {
                self.message = format!("Mod changes pending: {e:#}");
            }
        }
        self.go(Screen::Main);
        self.music("MAINMENU_MUS");
        Ok(())
    }
    fn back(&mut self) -> Result<()> {
        match self.screen {
            Screen::Cinematic => self.finish_movie(),
            Screen::Game => self.go(Screen::Pause),
            Screen::Pause => self.go(Screen::Game),
            Screen::Options => {
                self.save_config()?;
                self.go(self.previous)
            }
            Screen::Mods if self.world.is_some() => self.go(Screen::Pause),
            Screen::Diagnostics => self.go(self.previous),
            Screen::Bindings => {
                self.awaiting_binding = None;
                self.save_config()?;
                self.go(Screen::Options);
            }
            Screen::Results => self.return_main()?,
            _ => self.go(Screen::Main),
        }
        Ok(())
    }
    fn update(&mut self, input: Input, nanos: u64) -> Result<()> {
        if self.screen == Screen::Cinematic {
            let movie = self
                .cinematic
                .as_mut()
                .context("missing active cinematic")?;
            movie.advance(nanos)?;
            let sounds = std::mem::take(&mut movie.sounds);
            let finished = movie.finished();
            if let Some(audio) = &mut self.audio {
                for event in sounds {
                    if let Ok(sample) = self
                        .catalog
                        .read(event.asset)
                        .and_then(|b| DigitalSample::decode(&b))
                    {
                        audio.lock().sample(
                            sample,
                            event.pan,
                            event.pitch,
                            event.volume,
                            event.priority,
                        );
                    }
                }
            }
            if finished {
                self.finish_movie();
            }
            return Ok(());
        }
        if self.screen != Screen::Game {
            return Ok(());
        }
        self.queued_cycle |= input.cycle;
        self.queued_bomb |= input.bomb;
        let steps = self.clock.advance(nanos);
        let mut input = input;
        input.cycle = self.queued_cycle;
        input.bomb = self.queued_bomb;
        for _ in 0..steps {
            let w = self.world.as_mut().context("missing active mission")?;
            w.step(input, &self.active.registry, &mut self.active.scripts)?;
            input.cycle = false;
            input.bomb = false;
            self.queued_cycle = false;
            self.queued_bomb = false;
            if let Some(audio) = &mut self.audio {
                for event in &w.sound_events {
                    if let Ok(sample) = self
                        .catalog
                        .read(event.asset)
                        .and_then(|b| DigitalSample::decode(&b))
                    {
                        audio.lock().sample(
                            sample,
                            event.pan,
                            event.pitch,
                            event.volume,
                            event.priority,
                        );
                    }
                }
                for id in &w.mod_sounds {
                    let definition = self
                        .active
                        .registry
                        .sounds
                        .get(id)
                        .context("missing mod sound")?;
                    if !self.mod_audio.contains_key(id) {
                        let owner = &self.active.registry.owners[id];
                        let root = &self.active.registry.asset_roots[owner];
                        let path =
                            crate::assets::contained(root, std::path::Path::new(&definition.file))?;
                        let sample = crate::sound::decode(&std::fs::read(path)?)?;
                        if self.mod_audio.values().map(|s| s.data.len()).sum::<usize>()
                            + sample.data.len()
                            > 64 * 1024 * 1024
                        {
                            self.mod_audio.clear();
                        }
                        self.mod_audio.insert(id.clone(), sample);
                    }
                    audio.lock().sample(
                        self.mod_audio[id].clone(),
                        definition.pan,
                        definition.pitch,
                        definition.volume,
                        definition.priority as i32,
                    );
                }
            }
            if w.outcome != Outcome::Playing {
                let outcome = w.outcome;
                let mission = w.mission.clone();
                let mut pilot = w.pilot(&self.pilot);
                if outcome == Outcome::Complete {
                    pilot.complete_mission(&self.active.registry)?;
                    self.config.difficulty = pilot.difficulty;
                    self.pilot = pilot;
                    self.save()?;
                    self.message = "Mission complete".into();
                } else {
                    self.message = "Ship lost - previous hangar save retained".into();
                }
                let kind = if outcome == Outcome::Failed {
                    MovieKind::Death
                } else if mission.0.ends_with("_wave_9") {
                    let sector = mission
                        .0
                        .strip_prefix("base:sector_")
                        .and_then(|s| s.split('_').next())
                        .and_then(|s| s.parse::<u8>().ok())
                        .unwrap_or(1);
                    MovieKind::CampaignEnd(sector.saturating_sub(1))
                } else {
                    MovieKind::Landing
                };
                if mission.0.starts_with("base:") {
                    if let Err(e) = self.show_movie(kind, Screen::Results) {
                        self.message = format!("Cinematic unavailable: {e:#}");
                        self.go(Screen::Results);
                    }
                } else {
                    self.go(Screen::Results);
                }
                break;
            }
        }
        Ok(())
    }
    fn raw(&mut self, id: u32) -> Result<Sprite> {
        if let Some(s) = self.raw.get(&id) {
            return Ok(s.clone());
        }
        let s = self.catalog.sprite(id)?;
        self.raw.insert(id, s.clone());
        Ok(s)
    }
    fn art(
        &mut self,
        canvas: &mut Canvas,
        art: &Art,
        owner: &str,
        frame: u32,
        x: f32,
        y: f32,
    ) -> Result<()> {
        let key = if art.png.is_some() || art.hd_png.is_some() {
            Some(format!(
                "{owner}:{}:{frame}:{}:{}",
                serde_json::to_string(art)?,
                canvas.scale,
                self.config.hd_mode
            ))
        } else {
            None
        };
        if let Some(sprite) = key.as_ref().and_then(|k| self.mod_art.get(k)) {
            canvas.blit(
                sprite,
                (x * canvas.scale as f32).round() as i32,
                (y * canvas.scale as f32).round() as i32,
            );
            return Ok(());
        }
        if let Some(id) = art.asset {
            if self.config.hd_mode && art.hd_png.is_none() {
                if let Some(sprite) =
                    self.hd
                        .sprite(id + frame % art.frames, canvas.scale, &self.palette)?
                {
                    if sprite.width == art.logical_width as usize * canvas.scale
                        && sprite.height == art.logical_height as usize * canvas.scale
                    {
                        canvas.blit(
                            &sprite,
                            (x * canvas.scale as f32).round() as i32,
                            (y * canvas.scale as f32).round() as i32,
                        );
                        return Ok(());
                    }
                }
            }
        }
        let sprite = if let Some(id) = art
            .asset
            .filter(|_| !(self.config.hd_mode && art.hd_png.is_some()))
        {
            self.raw(id + frame % art.frames)?
        } else {
            art_sprite_variant(
                &self.catalog,
                &self.active.registry,
                owner,
                art,
                frame,
                self.config.hd_mode,
            )?
        };
        let scaled = if sprite.width == art.logical_width as usize
            && sprite.height == art.logical_height as usize
        {
            self.cache.get(&sprite, canvas.scale, art.nearest)?.clone()
        } else {
            let mut out = Sprite::blank(
                art.logical_width as usize * canvas.scale,
                art.logical_height as usize * canvas.scale,
            );
            for yy in 0..out.height {
                for xx in 0..out.width {
                    out.pixels[yy * out.width + xx] =
                        sprite.pixels[(yy * sprite.height / out.height) * sprite.width
                            + xx * sprite.width / out.width];
                }
            }
            out
        };
        canvas.blit(
            &scaled,
            (x * canvas.scale as f32).round() as i32,
            (y * canvas.scale as f32).round() as i32,
        );
        if let Some(key) = key {
            if self
                .mod_art
                .values()
                .map(|s| s.pixels.len() * 2)
                .sum::<usize>()
                + scaled.pixels.len() * 2
                > 128 * 1024 * 1024
            {
                self.mod_art.clear();
            }
            self.mod_art.insert(key, scaled);
        }
        Ok(())
    }
    fn scene(&mut self, canvas: &mut Canvas) -> Result<()> {
        let Some(world) = self.world.clone() else {
            return Ok(());
        };
        let mission = self.active.registry.missions[&world.mission].clone();
        let alpha = self.clock.alpha();
        let interp =
            |current: i32, previous: i32| previous as f32 + (current - previous) as f32 * alpha;
        // Compose a joined terrain layer with a two-pixel gutter before filtering.
        let mut terrain = Canvas::new(1);
        terrain.image = Sprite {
            width: 320,
            height: 204,
            pixels: vec![0; 320 * 204],
        };
        let rows = if mission.columns > 0 {
            mission.layout.len() / mission.columns as usize
        } else {
            0
        };
        let offset = 200 - rows as i32 * 32 + world.scroll;
        for (row, tiles) in mission
            .layout
            .chunks(mission.columns.max(1) as usize)
            .enumerate()
        {
            let y = offset + row as i32 * 32;
            if !(-34..202).contains(&y) {
                continue;
            }
            for (col, index) in tiles.iter().enumerate() {
                let n = row * mission.columns as usize + col;
                let tile = &mission.tiles[*index];
                let art = if if mission.legacy_map.is_some() {
                    world.terrain_settled[n]
                } else {
                    world.terrain_dead[n]
                } {
                    tile.destroyed.as_ref().unwrap_or(&tile.art)
                } else {
                    &tile.art
                };
                let owner = self.active.registry.owners[&world.mission].clone();
                let mut original = art.clone();
                original.hd_png = None;
                self.art(
                    &mut terrain,
                    &original,
                    &owner,
                    0,
                    16.0 + col as f32 * 32.0,
                    (y + 2) as f32,
                )?;
            }
        }
        let bg = upscale(&terrain.image, canvas.scale)?;
        let shift = if world.tick > 0 { alpha - 1.0 } else { 0.0 };
        canvas.blit(
            &bg,
            0,
            (-2.0 * canvas.scale as f32 + shift * canvas.scale as f32).round() as i32,
        );
        if self.config.hd_mode {
            // Keep detailed terrain on the presentation canvas. The joined
            // SD layer underneath supplies context and fallback at its edges.
            for (row, tiles) in mission
                .layout
                .chunks(mission.columns.max(1) as usize)
                .enumerate()
            {
                let y = offset + row as i32 * 32;
                if !(-34..202).contains(&y) {
                    continue;
                }
                for (col, index) in tiles.iter().enumerate() {
                    let n = row * mission.columns as usize + col;
                    let tile = &mission.tiles[*index];
                    let dead = if mission.legacy_map.is_some() {
                        world.terrain_settled[n]
                    } else {
                        world.terrain_dead[n]
                    };
                    let art = if dead {
                        tile.destroyed.as_ref().unwrap_or(&tile.art)
                    } else {
                        &tile.art
                    };
                    if art.hd_png.is_some() {
                        let owner = self.active.registry.owners[&world.mission].clone();
                        self.art(
                            canvas,
                            art,
                            &owner,
                            0,
                            16.0 + col as f32 * 32.0,
                            y as f32 + shift,
                        )?;
                    }
                }
            }
        }
        for ground in [true, false] {
            for e in &world.enemies {
                let def = self.active.registry.enemies[&e.definition].clone();
                if def.ground != ground {
                    continue;
                }
                if let Some(art) = def.art {
                    let owner = self.active.registry.owners[&e.definition].clone();
                    self.art(
                        canvas,
                        &art,
                        &owner,
                        if def.legacy.is_some() {
                            e.art_frame
                        } else {
                            e.frame
                        },
                        interp(e.x, e.px),
                        interp(e.y, e.py),
                    )?;
                }
            }
        }
        for p in &world.projectiles {
            let def = self.active.registry.weapons[&p.weapon].clone();
            let x = interp(p.x, p.px);
            let y = interp(p.y, p.py);
            if p.legacy.is_some() || p.legacy_enemy.is_some() {
                if let Some(asset) = World::projectile_asset(p, &self.active.registry) {
                    let frame = if let Some(shot) = &p.legacy_enemy {
                        shot.art_frame % shot.frames.max(1)
                    } else {
                        p.legacy.as_ref().map_or(0, |shot| shot.art_frame)
                    };
                    let original = self.raw(asset + frame)?;
                    let hd = if self.config.hd_mode {
                        self.hd.sprite(asset + frame, canvas.scale, &self.palette)?
                    } else {
                        None
                    };
                    let sprite = match hd {
                        Some(sprite) => sprite,
                        None => self.cache.get(&original, canvas.scale, false)?.clone(),
                    };
                    canvas.blit(
                        &sprite,
                        (x * canvas.scale as f32).round() as i32,
                        (y * canvas.scale as f32).round() as i32,
                    );
                }
                continue;
            }
            if matches!(def.behavior, crate::content::WeaponBehavior::Beam) {
                canvas.rect(x as i32, 0, 2, world.player.y, 255);
            } else if let Some(art) = def.art {
                let owner = self.active.registry.owners[&p.weapon].clone();
                self.art(
                    canvas,
                    &art,
                    &owner,
                    p.age / 2,
                    x - art.logical_width as f32 / 2.0,
                    y - art.logical_height as f32 / 2.0,
                )?;
            } else {
                canvas.rect(x as i32, y as i32, 2, 4, if p.hostile { 34 } else { 255 });
            }
        }
        let dark = matches!(
            world.mission.0.as_str(),
            "base:sector_2_wave_8" | "base:sector_3_wave_3"
        );
        let player = self.catalog.id(if dark {
            if world.player_flash {
                "FPLAYER_PIC"
            } else {
                "DPLAYER_PIC"
            }
        } else {
            "LPLAYER_PIC"
        })?;
        let player_frame = player + world.player.bank.clamp(0, 6) as u32;
        let s = self.raw(player_frame)?;
        let hd = if self.config.hd_mode {
            self.hd.sprite(player_frame, canvas.scale, &self.palette)?
        } else {
            None
        };
        let scaled = match hd {
            Some(sprite) => sprite,
            None => self.cache.get(&s, canvas.scale, false)?.clone(),
        };
        canvas.blit(
            &scaled,
            (interp(world.player.x, world.player.px) * canvas.scale as f32) as i32,
            (interp(world.player.y, world.player.py) * canvas.scale as f32) as i32,
        );
        for pickup in &world.pickups {
            if pickup
                .legacy
                .as_ref()
                .is_some_and(|legacy| legacy.countdown.is_some())
            {
                if let Ok(asset) = self.catalog.id("N$_PIC") {
                    let original = self.raw(asset)?;
                    let sprite = self.cache.get(&original, canvas.scale, false)?.clone();
                    canvas.blit(
                        &sprite,
                        pickup.x * canvas.scale as i32,
                        pickup.y * canvas.scale as i32,
                    );
                }
                continue;
            }
            if let Some(art) = self.active.registry.items[&pickup.item].art.clone() {
                let owner = self.active.registry.owners[&pickup.item].clone();
                self.art(
                    canvas,
                    &art,
                    &owner,
                    pickup
                        .legacy
                        .as_ref()
                        .map_or((world.tick / 3) as u32, |legacy| legacy.art_frame),
                    pickup.x as f32,
                    pickup.y as f32,
                )?;
            }
        }
        for effect in &world.effects {
            if let Ok(id) = self.catalog.id("AIRMED_BLK") {
                if let Ok(s) = self.raw(id + effect.age as u32 / 2) {
                    let scaled = self.cache.get(&s, canvas.scale, false)?.clone();
                    canvas.blit(
                        &scaled,
                        (effect.x - s.width as i32 / 2) * canvas.scale as i32,
                        (effect.y - s.height as i32 / 2) * canvas.scale as i32,
                    );
                }
            } else {
                canvas.rect(
                    effect.x - effect.age as i32 / 2,
                    effect.y - 2,
                    effect.age as i32 + 2,
                    4,
                    50,
                );
            }
        }
        // The original shield bars sit beside the playfield. A full-width
        // bottom panel would cover the player's engines at its initial y=160.
        canvas.rect(0, 0, 16, 200, 0);
        canvas.rect(304, 0, 16, 200, 0);
        for (x, amount) in [(8, world.player.super_shield), (308, world.player.shield)] {
            for level in 0..amount.clamp(0, 100) {
                canvas.rect(x, 199 - level * 2, 4, 1, (74 - level * 27 / 100) as u16);
            }
        }
        self.font.text(
            canvas,
            132,
            2,
            &format!("${:08}", world.player.credits),
            100,
        );
        Ok(())
    }
    fn draw(&mut self) -> Result<Canvas> {
        let mut canvas = Canvas::new(self.config.scale);
        canvas.clear(0);
        if let Some(movie) = &self.cinematic {
            canvas.blit(&nearest(&movie.image, canvas.scale), 0, 0);
            return Ok(canvas);
        }
        if self.world.is_some() {
            self.scene(&mut canvas)?;
            if self.screen == Screen::Game {
                return Ok(canvas);
            }
        } else if let Ok(id) = self.catalog.id("NEWMAIN_PIC") {
            let s = self.raw(id)?;
            canvas.blit(&nearest(&s, canvas.scale), 0, 0);
        }
        canvas.rect(12, 8, 296, 184, closest(&self.palette, [10, 15, 32]));
        canvas.rect(12, 8, 296, 1, 100);
        canvas.rect(12, 191, 296, 1, 100);
        let title = match self.screen {
            Screen::Main => "RAPTOR / RUST",
            Screen::Missions => "MISSION SELECT",
            Screen::Shop => "HANGAR / SHOP",
            Screen::Inventory => "INVENTORY / EQUIPMENT",
            Screen::Mods => "MOD MANAGER",
            Screen::Options => "OPTIONS",
            Screen::Pause => "PAUSED",
            Screen::Results => "FLIGHT REPORT",
            Screen::Help => "FLIGHT CONTROLS",
            Screen::Credits => "CREDITS",
            Screen::Pilots => "LOAD PILOT",
            Screen::Diagnostics => "MOD / SAVE DIAGNOSTICS",
            Screen::Bindings => "KEYBOARD BINDINGS",
            Screen::Cinematic => "",
            Screen::Game => "",
        };
        self.font.text(&mut canvas, 22, 17, title, 50);
        self.font.text(
            &mut canvas,
            22,
            29,
            &format!("PILOT {}  ${}", self.pilot.callsign, self.pilot.credits),
            100,
        );
        let rows = self.rows();
        let card = if self.screen == Screen::Missions {
            self.missions().get(self.selected).and_then(|id| {
                self.active.registry.missions[id]
                    .art
                    .clone()
                    .map(|art| (art, self.active.registry.owners[id].clone()))
            })
        } else {
            None
        };
        let first = self.selected.saturating_sub(8);
        for (index, row) in rows.iter().enumerate().skip(first).take(10) {
            let y = 46 + (index - first) as i32 * 11;
            if index == self.selected {
                canvas.rect(
                    20,
                    y - 2,
                    if card.is_some() { 126 } else { 280 },
                    10,
                    closest(&self.palette, [25, 45, 65]),
                );
            }
            self.font.text(
                &mut canvas,
                24,
                y,
                &if card.is_some() {
                    row.chars().take(20).collect::<String>()
                } else {
                    row.clone()
                },
                if index == self.selected { 50 } else { 100 },
            );
        }
        if let Some((mut art, owner)) = card {
            let height = (150 * art.logical_height / art.logical_width).min(108);
            art.logical_width = 150;
            art.logical_height = height;
            self.art(&mut canvas, &art, &owner, 0, 154.0, 52.0)?;
        }
        if self.screen == Screen::Mods {
            if self.selected >= 2 {
                if let Some(id) = self.mod_ids().get(self.selected - 2) {
                    let m = &self.discovery.mods[id];
                    self.font
                        .text(&mut canvas, 22, 160, &m.manifest.description, 100);
                }
            }
            self.font.text(
                &mut canvas,
                22,
                171,
                "ENTER toggle/apply  LEFT/RIGHT priority",
                50,
            );
        } else if self.screen == Screen::Help {
            let key = |action: &str| {
                self.config
                    .bindings
                    .get(action)
                    .map(String::as_str)
                    .unwrap_or("unbound")
            };
            for (n, line) in [
                format!(
                    "Move: {} / {} / {} / {}",
                    key("left"),
                    key("right"),
                    key("up"),
                    key("down")
                ),
                format!("Fire: {}  Special: {}", key("fire"), key("special")),
                format!("Cycle: {}  Mega bomb: {}", key("cycle"), key("bomb")),
                "ESC: pause   O: options".into(),
                "Mouse / controller selectable in Options".into(),
                "ENTER: choose   ESC: back".into(),
                "Shop: ENTER buy   Inventory: S sell".into(),
            ]
            .iter()
            .enumerate()
            {
                self.font
                    .text(&mut canvas, 24, 49 + n as i32 * 14, line, 100);
            }
        } else if self.screen == Screen::Credits {
            for (n, line) in [
                "Raptor: Cygnus Studios / Apogee",
                "Reconstructed engine: nukeykt / skynettx",
                "Rust replica: GPL v2 or later",
                "FM core: Nuked-OPL3 / Tony Gies",
                "Game assets: your original purchased copy",
            ]
            .iter()
            .enumerate()
            {
                self.font
                    .text(&mut canvas, 24, 52 + n as i32 * 16, line, 100);
            }
        } else {
            self.font.text(
                &mut canvas,
                22,
                171,
                "ENTER choose  ESC back  N new pilot  D details",
                50,
            );
        }
        if !self.message.is_empty() {
            self.font.text(&mut canvas, 22, 181, &self.message, 34);
        }
        Ok(canvas)
    }
}
const ACTIONS: [&str; 8] = [
    "up", "down", "left", "right", "fire", "special", "cycle", "bomb",
];
fn binding_matches(config: &Config, action: &str, key: Option<Scancode>) -> bool {
    key.is_some()
        && config
            .bindings
            .get(action)
            .and_then(|value| Scancode::from_name(value))
            == key
}
// A failed load uses a display placeholder; never validate that placeholder
// in place of the existing file when mods are changed.
fn pilot_for_mods(
    path: &std::path::Path,
    current: &Pilot,
    registry: &Registry,
    pins: &[modding::ModPin],
) -> Result<Pilot> {
    if path.exists() {
        Pilot::load(path, registry, pins)
    } else {
        current.validate(registry, pins)?;
        Ok(current.clone())
    }
}
fn restore_scripts(runtime: &mut modding::ScriptRuntime, pilot: &Pilot) {
    runtime.states = pilot.script_state.clone();
    runtime.rng = pilot.script_rng.clone();
}
fn mission_palette(base: &[[u8; 3]; 256], world: Option<&World>) -> [[u8; 3]; 256] {
    let mut palette = *base;
    let Some(world) = world else {
        return palette;
    };
    if world.tick < 3 {
        return palette;
    }
    let updates = (world.tick - 1) / 2;
    let water = (updates - (updates + 3) / 4) % 5;
    let fire = (updates / 2) % 5;
    for index in 0..5 {
        palette[240 + index] = base[240 + (index + water as usize) % 5];
        palette[245 + index] = base[245 + (index + fire as usize) % 5];
    }
    const GLOW: [u8; 20] = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1];
    for (index, phase) in [(250, 0_u64), (251, 8_u64)] {
        let amount = GLOW[((phase + updates - 1) % 20) as usize];
        palette[index] = base[index].map(|value| {
            let value = (value >> 2).saturating_sub(amount);
            (value << 2) | (value >> 4)
        });
    }
    if updates >= 2 {
        palette[if (updates / 2 - 1) % 2 == 0 { 252 } else { 253 }] = [0; 3];
    }
    if !world.palette_blue {
        palette[254] = [0; 3];
    }
    if (updates - 1) % 6 >= 3 {
        palette[255] = [0; 3];
    }
    palette
}
fn closest(palette: &[[u8; 3]; 256], rgb: [u8; 3]) -> u16 {
    palette
        .iter()
        .enumerate()
        .min_by_key(|(_, c)| {
            (0..3)
                .map(|i| (c[i] as i32 - rgb[i] as i32).pow(2))
                .sum::<i32>()
        })
        .unwrap()
        .0 as u16
}
fn viewport(w: u32, h: u32, aspect: bool) -> Rect {
    if aspect {
        let width = w.min(h * 4 / 3);
        let height = h.min(w * 3 / 4);
        Rect::new(
            ((w - width) / 2) as i32,
            ((h - height) / 2) as i32,
            width,
            height,
        )
    } else {
        Rect::new(0, 0, w, h)
    }
}
pub fn run(
    catalog: Catalog,
    base: Registry,
    paths: Paths,
    mods_root: PathBuf,
    frames: Option<u32>,
    screenshot: Option<PathBuf>,
    preview: Option<ContentId>,
    movie_preview: Option<MovieKind>,
) -> Result<()> {
    let mut host = Host::new(catalog, base, paths, mods_root, frames.is_some())?;
    if let Some(id) = preview {
        if frames.is_some() {
            host.new_pilot()?;
        }
        host.start(id)?;
    }
    if let Some(kind) = movie_preview {
        host.show_movie(kind, Screen::Main)?;
    }
    let sdl = sdl2::init().map_err(|e| anyhow!(e))?;
    let video = sdl.video().map_err(|e| anyhow!(e))?;
    let window = video
        .window(
            "RaptorReplica - Rust",
            host.config.width,
            host.config.height,
        )
        .position_centered()
        .resizable()
        .allow_highdpi()
        .build()?;
    let mut canvas = match window.into_canvas().accelerated().present_vsync().build() {
        Ok(c) => c,
        Err(_) => video
            .window(
                "RaptorReplica - Rust",
                host.config.width,
                host.config.height,
            )
            .resizable()
            .build()?
            .into_canvas()
            .software()
            .build()?,
    };
    let creator = canvas.texture_creator();
    let mut texture = creator.create_texture_streaming(
        PixelFormatEnum::RGBA32,
        (320 * host.config.scale) as u32,
        (200 * host.config.scale) as u32,
    )?;
    let mut applied = (0usize, false, false, 0u32, 0u32);
    let mut events = sdl.event_pump().map_err(|e| anyhow!(e))?;
    let controllers = sdl.game_controller().map_err(|e| anyhow!(e))?;
    let mut controller = (0..controllers.num_joysticks().unwrap_or(0))
        .filter(|index| controllers.is_game_controller(*index))
        .find_map(|index| controllers.open(index).ok());
    if let Ok(audio) = sdl.audio() {
        let genmidi = host.catalog.named("GENMIDI_OP2")?;
        let desired = AudioSpecDesired {
            freq: Some(44100),
            channels: Some(2),
            samples: Some(512),
        };
        match audio.open_playback(None, &desired, |spec| {
            Mixer::new(spec.freq as u32, &genmidi).expect("validated instrument table")
        }) {
            Ok(device) => {
                let mut device = device;
                device.lock().set_fx_channels(host.config.fx_channels);
                device.resume();
                host.audio = Some(device)
            }
            Err(e) => host.message = format!("Audio unavailable: {e}"),
        }
    }
    if let Some(music) = host.desired_music {
        if let Ok(score) = host.catalog.read(music).and_then(|b| MusScore::decode(&b)) {
            if let Some(audio) = &mut host.audio {
                audio.lock().play_with_fade(score, true, true);
            }
        }
    } else {
        host.music("MAINMENU_MUS");
    }
    let mut previous = Instant::now();
    let mut count = 0u32;
    let mut cycle = false;
    let mut bomb = false;
    let mut quit = false;
    while !quit {
        for event in events.poll_iter() {
            match event {
                Event::Quit { .. } => quit = true,
                Event::ControllerDeviceAdded { which, .. } => {
                    controller = controllers.open(which).ok();
                }
                Event::ControllerDeviceRemoved { which, .. } => {
                    if controller
                        .as_ref()
                        .is_some_and(|c| c.instance_id() == which)
                    {
                        controller = (0..controllers.num_joysticks().unwrap_or(0))
                            .filter(|index| controllers.is_game_controller(*index))
                            .find_map(|index| controllers.open(index).ok());
                    }
                }
                Event::ControllerButtonDown { button, .. } => {
                    if host.screen == Screen::Cinematic {
                        host.finish_movie();
                        continue;
                    }
                    if button == Button::Start {
                        if let Err(e) = host.back() {
                            host.message = e.to_string()
                        }
                    } else if host.screen != Screen::Game {
                        match button {
                            Button::DPadUp => host.selected = host.selected.saturating_sub(1),
                            Button::DPadDown => {
                                host.selected =
                                    (host.selected + 1).min(host.rows().len().saturating_sub(1))
                            }
                            Button::A => match host.activate() {
                                Ok(r) => quit = !r,
                                Err(e) => host.message = format!("{e:#}"),
                            },
                            Button::B => {
                                if let Err(e) = host.back() {
                                    host.message = e.to_string();
                                }
                            }
                            _ => {}
                        }
                    } else if button == Button::X {
                        cycle = true
                    } else if button == Button::Y {
                        bomb = true
                    }
                }
                Event::MouseWheel { y, .. } if host.screen != Screen::Game => {
                    if y > 0 {
                        host.selected = host.selected.saturating_sub(y as usize);
                    } else {
                        host.selected = host
                            .selected
                            .saturating_add(y.unsigned_abs() as usize)
                            .min(host.rows().len().saturating_sub(1));
                    }
                }
                Event::MouseButtonDown { x, y, .. } if host.screen != Screen::Game => {
                    if host.screen == Screen::Cinematic {
                        host.finish_movie();
                        continue;
                    }
                    let (w, h) = canvas.window().size();
                    let rect = viewport(w, h, host.config.aspect_correct);
                    let yy = (y - rect.y()) * 200 / rect.height() as i32;
                    let xx = (x - rect.x()) * 320 / rect.width() as i32;
                    if (20..300).contains(&xx) && (44..156).contains(&yy) {
                        let first = host.selected.saturating_sub(8);
                        let selection = first + ((yy - 44) / 11) as usize;
                        if selection < host.rows().len() {
                            host.selected = selection;
                            match host.activate() {
                                Ok(r) => quit = !r,
                                Err(e) => host.message = format!("{e:#}"),
                            }
                        }
                    }
                }
                Event::KeyDown {
                    keycode: Some(key),
                    scancode: physical_key,
                    keymod,
                    repeat: false,
                    ..
                } => {
                    if host.screen == Screen::Cinematic {
                        host.finish_movie();
                        continue;
                    }
                    if let Some(action) = host.awaiting_binding.take() {
                        if key == Keycode::Escape {
                            host.message = "Binding change cancelled".into();
                        } else if let Some(scancode) = physical_key {
                            host.config
                                .bindings
                                .insert(action.clone(), scancode.name().to_string());
                            host.message = format!("{action}: {}", scancode.name());
                            if let Err(e) = host.save_config() {
                                host.message = e.to_string();
                            }
                        }
                        continue;
                    }
                    if host.screen == Screen::Game
                        && ACTIONS
                            .iter()
                            .any(|action| binding_matches(&host.config, action, physical_key))
                    {
                        cycle |= binding_matches(&host.config, "cycle", physical_key);
                        bomb |= binding_matches(&host.config, "bomb", physical_key);
                        continue;
                    }
                    if key == Keycode::Return
                        && keymod
                            .intersects(sdl2::keyboard::Mod::LALTMOD | sdl2::keyboard::Mod::RALTMOD)
                    {
                        host.config.fullscreen = !host.config.fullscreen;
                        continue;
                    }
                    if key == Keycode::Escape || key == Keycode::P && host.screen == Screen::Game {
                        if let Err(e) = host.back() {
                            host.message = e.to_string()
                        }
                        continue;
                    }
                    if host.screen == Screen::Game {
                        match key {
                            Keycode::O => {
                                host.previous = Screen::Pause;
                                host.go(Screen::Options)
                            }
                            _ if binding_matches(&host.config, "cycle", physical_key) => {
                                cycle = true
                            }
                            _ if binding_matches(&host.config, "bomb", physical_key) => bomb = true,
                            _ => {}
                        }
                        continue;
                    }
                    match key {
                        Keycode::Up => host.selected = host.selected.saturating_sub(1),
                        Keycode::Down => {
                            host.selected =
                                (host.selected + 1).min(host.rows().len().saturating_sub(1))
                        }
                        Keycode::Return => match host.activate() {
                            Ok(r) => quit = !r,
                            Err(e) => host.message = format!("{e:#}"),
                        },
                        Keycode::D if host.world.is_none() => {
                            host.previous = host.screen;
                            host.go(Screen::Diagnostics);
                        }
                        Keycode::N if host.world.is_none() => {
                            if let Err(e) = host.new_pilot() {
                                host.message = e.to_string();
                            }
                        }
                        Keycode::S if host.screen == Screen::Inventory => {
                            if let Some(id) =
                                host.pilot.inventory.keys().nth(host.selected).cloned()
                            {
                                if let Err(e) = host
                                    .pilot
                                    .sell(&id, &host.active.registry)
                                    .and_then(|_| host.save())
                                {
                                    host.message = e.to_string()
                                }
                            }
                        }
                        Keycode::Left | Keycode::Right
                            if host.screen == Screen::Mods && host.selected >= 2 =>
                        {
                            if let Some(id) = host.mod_ids().get(host.selected - 2) {
                                if let Some(n) = host.pending.iter().position(|m| m == id) {
                                    let next = if key == Keycode::Left {
                                        n.saturating_sub(1)
                                    } else {
                                        (n + 1).min(host.pending.len() - 1)
                                    };
                                    host.pending.swap(n, next);
                                }
                            }
                        }
                        _ => {}
                    }
                }
                _ => {}
            }
        }
        let desired = (
            host.config.scale,
            host.config.fullscreen,
            host.config.borderless,
            host.config.width,
            host.config.height,
        );
        if desired != applied {
            if host.config.scale != applied.0 {
                texture = creator.create_texture_streaming(
                    PixelFormatEnum::RGBA32,
                    (320 * host.config.scale) as u32,
                    (200 * host.config.scale) as u32,
                )?;
            }
            if let Err(e) = canvas
                .window_mut()
                .set_fullscreen(if host.config.fullscreen {
                    FullscreenType::Desktop
                } else {
                    FullscreenType::Off
                })
            {
                host.message = e;
            }
            canvas.window_mut().set_bordered(!host.config.borderless);
            if !host.config.fullscreen {
                let _ = canvas
                    .window_mut()
                    .set_size(host.config.width, host.config.height);
            }
            applied = desired;
        }
        let now = Instant::now();
        let elapsed = now.duration_since(previous).as_nanos().min(250_000_000) as u64;
        let elapsed = if frames.is_some() {
            16_666_667
        } else {
            elapsed
        };
        previous = now;
        let keyboard = events.keyboard_state();
        let pressed = |action: &str| {
            host.config
                .bindings
                .get(action)
                .and_then(|key| Scancode::from_name(key))
                .is_some_and(|key| keyboard.is_scancode_pressed(key))
        };
        let mut input = Input {
            dx: pressed("right") as i32 - pressed("left") as i32,
            dy: pressed("down") as i32 - pressed("up") as i32,
            fire: pressed("fire") || frames.is_some() && host.screen == Screen::Game,
            special: pressed("special"),
            cycle,
            bomb,
            ..Input::default()
        };
        if host.config.control == "mouse" {
            let mouse = events.mouse_state();
            let (w, h) = canvas.window().size();
            let r = viewport(w, h, host.config.aspect_correct);
            input.absolute = Some([
                (mouse.x() - r.x()) * 320 / r.width() as i32 - 16,
                (mouse.y() - r.y()) * 200 / r.height() as i32 - 16,
            ]);
            input.fire = mouse.left();
            input.special = mouse.right();
        }
        if host.config.control == "controller" {
            if let Some(c) = &controller {
                input.dx = if i32::from(c.axis(Axis::LeftX)).abs() > 8000 {
                    c.axis(Axis::LeftX).signum() as i32
                } else {
                    0
                };
                input.dy = if i32::from(c.axis(Axis::LeftY)).abs() > 8000 {
                    c.axis(Axis::LeftY).signum() as i32
                } else {
                    0
                };
                if input.dx == 0 {
                    input.dx =
                        c.button(Button::DPadRight) as i32 - c.button(Button::DPadLeft) as i32;
                }
                if input.dy == 0 {
                    input.dy = c.button(Button::DPadDown) as i32 - c.button(Button::DPadUp) as i32;
                }
                input.fire = c.button(Button::A);
                input.special = c.button(Button::B);
            }
        }
        if let Err(e) = host.update(input, elapsed) {
            host.message = format!("Mission paused: {e:#}");
            host.go(Screen::Pause);
        }
        cycle = false;
        bomb = false;
        if let Some(audio) = &mut host.audio {
            let mut mixer = audio.lock();
            mixer.set_fx_channels(host.config.fx_channels);
            mixer.music_volume = host.config.music_volume;
            mixer.fx_volume = host.config.fx_volume;
        }
        let image = host.draw()?;
        let palette = if let Some(movie) = &host.cinematic {
            movie.palette(&host.palette)
        } else {
            mission_palette(&host.palette, host.world.as_ref())
        };
        let rgba = image.rgba(&palette, host.config.scanlines);
        texture.update(None, &rgba, image.image.width * 4)?;
        let (w, h) = canvas.output_size().map_err(|e| anyhow!(e))?;
        canvas.set_draw_color(sdl2::pixels::Color::BLACK);
        canvas.clear();
        canvas
            .copy(&texture, None, viewport(w, h, host.config.aspect_correct))
            .map_err(|e| anyhow!(e))?;
        if frames.is_some_and(|n| count + 1 >= n) {
            if let Some(path) = &screenshot {
                if let Some(parent) = path.parent() {
                    std::fs::create_dir_all(parent)?;
                }
                let presented = canvas
                    .read_pixels(None, PixelFormatEnum::RGBA32)
                    .map_err(|e| anyhow!(e))?;
                image::save_buffer(path, &presented, w, h, image::ColorType::Rgba8)?;
            }
        }
        canvas.present();
        count += 1;
        if frames.is_some_and(|n| count >= n) {
            quit = true;
        }
        if frames.is_some() {
            std::thread::sleep(Duration::from_millis(1));
        }
    }
    if frames.is_none() {
        host.config.save(&host.paths)?;
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn loading_a_pilot_restores_scripts_before_hangar_saves() {
        let (_, mut pilot) = fixture();
        pilot.script_state.insert(
            "weapon:behavior.rhai".into(),
            serde_json::json!({"shots": 42}),
        );
        pilot.script_rng.insert(
            "weapon:behavior.rhai".into(),
            crate::simulation::LegacyRng::new(731),
        );
        let mut runtime = modding::ScriptRuntime::new();
        restore_scripts(&mut runtime, &pilot);
        let mut resaved = pilot.clone();
        resaved.script_state = runtime.states.clone();
        resaved.script_rng = runtime.rng.clone();
        assert_eq!(resaved.script_state, pilot.script_state);
        assert_eq!(resaved.script_rng["weapon:behavior.rhai"].seed, 731);
        restore_scripts(&mut runtime, &Pilot::default());
        assert!(runtime.states.is_empty());
        assert!(runtime.rng.is_empty());
    }
    fn fixture() -> (Registry, Pilot) {
        let mut registry = Registry::default();
        let mut pilot = Pilot::default();
        pilot.inventory.clear();
        let mission: crate::content::MissionDef = serde_json::from_value(serde_json::json!({
            "id": pilot.mission, "name": "Save safety fixture", "duration": 100
        }))
        .unwrap();
        registry.missions.insert(mission.id.clone(), mission);
        (registry, pilot)
    }
    #[test]
    fn applying_mods_checks_saved_pilot_instead_of_display_placeholder() {
        let (registry, placeholder) = fixture();
        assert!(placeholder.validate(&registry, &[]).is_ok());
        let pin = modding::ModPin {
            id: "example".into(),
            version: "1.0.0".into(),
            hash: "required".into(),
        };
        let mut saved = placeholder.clone();
        saved.mods = vec![pin.clone()];
        saved.callsign = "SAVED PILOT".into();
        saved.credits = 4242;
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("pilot.json");
        saved.save(&path).unwrap();
        let before = std::fs::read(&path).unwrap();
        assert!(pilot_for_mods(&path, &placeholder, &registry, &[]).is_err());
        assert_eq!(std::fs::read(&path).unwrap(), before);
        let restored = pilot_for_mods(&path, &placeholder, &registry, &[pin]).unwrap();
        assert_eq!(restored.callsign, "SAVED PILOT");
        assert_eq!(restored.credits, 4242);
    }
    #[test]
    fn corrupt_existing_slot_cannot_be_replaced_by_valid_placeholder() {
        let (registry, placeholder) = fixture();
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("pilot.json");
        std::fs::write(&path, b"corrupt existing save").unwrap();
        assert!(pilot_for_mods(&path, &placeholder, &registry, &[]).is_err());
        assert_eq!(std::fs::read(&path).unwrap(), b"corrupt existing save");
        let unused = dir.path().join("unused.json");
        assert_eq!(
            pilot_for_mods(&unused, &placeholder, &registry, &[])
                .unwrap()
                .callsign,
            placeholder.callsign
        );
    }
    #[test]
    fn full_hd_window_retains_centered_four_three_viewport() {
        assert_eq!(viewport(1920, 1080, true), Rect::new(240, 0, 1440, 1080));
        assert_eq!(viewport(1920, 1080, false), Rect::new(0, 0, 1920, 1080));
    }
    #[test]
    fn palette_effects_do_not_consume_simulation_rng() {
        let (registry, pilot) = fixture();
        let mut world = World::new(&pilot.mission, &pilot, &registry).unwrap();
        world.tick = 7;
        world.palette_blue = false;
        let before = world.rng.seed;
        let base = [[255, 128, 64]; 256];
        let first = mission_palette(&base, Some(&world));
        assert_eq!(first, mission_palette(&base, Some(&world)));
        assert_eq!(world.rng.seed, before);
        assert_eq!(first[254], [0; 3]);
        world.palette_blue = true;
        assert_eq!(mission_palette(&base, Some(&world))[254], base[254]);
    }
}
