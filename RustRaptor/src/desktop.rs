//! SDL host, interpolated scene presentation and local game menus.
use crate::{
    assets::{Catalog, Sprite},
    audio::{Mixer, MusScore},
    cinematics::{Cinematic, Kind as MovieKind},
    content::{Art, ContentId, Registry, art_sprite_variant},
    hd::HdAssets,
    modding::{self, ActiveMods, Discovery},
    persistence::{Config, Paths, Pilot},
    render::{
        BitmapFont, Canvas, SpriteCache, legacy_light_table, nearest, prefers_nearest,
        shade_air_shadow, shade_ground_shadow, upscale,
    },
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
    Hangar,
    Extras,
    PilotForm,
    Missions,
    Shop,
    ShopDetails,
    Inventory,
    Mods,
    Options,
    Game,
    Pause,
    Results,
    Help,
    Credits,
    Pilots,
    LegacyPilots,
    ConfirmDisable,
    Diagnostics,
    Bindings,
    Cinematic,
}
struct PilotForm {
    name: String,
    callsign: String,
    portrait: usize,
    original_portrait: Option<i32>,
    difficulty: u32,
    creating: bool,
    return_to: Screen,
    field: Option<usize>,
    replace_on_input: bool,
}
/// Display latches advance with simulation steps, including frames skipped by
/// the renderer. They never change gameplay state or consume the game's RNG.
struct HudState {
    tick: u64,
    shield: i32,
    blink: bool,
    damage_flashes: u8,
    sweep: u8,
}
impl HudState {
    fn new(world: &World) -> Self {
        Self {
            tick: world.tick,
            shield: world.player.shield,
            blink: true,
            damage_flashes: 0,
            sweep: 0,
        }
    }
    fn observe(&mut self, world: &World, registry: &Registry) {
        if self.tick == world.tick {
            return;
        }
        if world.tick < self.tick {
            *self = Self::new(world);
            return;
        }
        if world.player.shield <= 10 {
            if world.tick % 8 == 0 {
                self.blink = !self.blink;
                if self.blink {
                    self.damage_flashes = self.damage_flashes.saturating_sub(1);
                }
            }
            if world.player.shield < self.shield && world.player.super_shield < 1 {
                self.damage_flashes = 2;
            }
        }
        if world
            .player
            .inventory
            .get(&ContentId::from("base:detect"))
            .is_some_and(|n| *n > 0)
            && boss_shield_percent(world, registry) == 0
        {
            self.sweep = (self.sweep + 1) % 50;
        }
        self.shield = world.player.shield;
        self.tick = world.tick;
    }
}
fn boss_shield_percent(world: &World, registry: &Registry) -> i32 {
    let mut total = 0_i64;
    let mut count = 0;
    for enemy in &world.enemies {
        let definition = &registry.enemies[&enemy.definition];
        // ENEMY_GetBaseDamage checks the boss center reaching the screen.
        if definition.boss && enemy.y + enemy.height / 2 >= 0 {
            total += enemy.health.max(0) as i64 * 100 / definition.health.max(1) as i64;
            count += 1;
        }
    }
    if count == 0 {
        0
    } else {
        (total / count).clamp(0, 100) as i32
    }
}
fn hud_shield_bar(canvas: &mut Canvas, x: i32, amount: i32) {
    // RAP_DisplayShieldLevel uses a nine-color run with a 16.16 accumulator.
    let increment = (9_u32 << 16) / 100;
    for level in 0..100_u32 {
        let color = if (level as i32) < amount.clamp(0, 100) {
            74 - ((level * increment) >> 16) as u16
        } else {
            0
        };
        canvas.rect(x, 199 - level as i32 * 2, 4, 1, color);
    }
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
    diagnostic_mod: Option<String>,
    diagnostic_return: Screen,
    pending_disable: Option<crate::mod_selection::DisablePlan>,
    world: Option<World>,
    cinematic: Option<Cinematic>,
    movie_return: Screen,
    screen: Screen,
    previous: Screen,
    selected: usize,
    shop_selling: bool,
    shop_detail_item: Option<ContentId>,
    pilot_form: Option<PilotForm>,
    pilot_slots: Vec<(usize, String)>,
    message: String,
    font: BitmapFont,
    cache: SpriteCache,
    raw: BTreeMap<u32, Sprite>,
    mod_art: BTreeMap<String, Sprite>,
    palette: [[u8; 3]; 256],
    shadow_table: [u8; 256],
    air_shadow_table: [u8; 256],
    hud_state: HudState,
    audio: Option<AudioDevice<Mixer>>,
    sound_bank: crate::sound::SoundBank,
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
        let vga_palette = palette.map(|color| color.map(|component| component >> 2));
        let shadow_table = legacy_light_table(&vga_palette, -9);
        let air_shadow_table = legacy_light_table(&vga_palette, -6);
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
            diagnostic_mod: None,
            diagnostic_return: Screen::Main,
            pending_disable: None,
            world: None,
            cinematic: None,
            movie_return: Screen::Main,
            screen: Screen::Main,
            previous: Screen::Main,
            selected: 0,
            shop_selling: false,
            shop_detail_item: None,
            pilot_form: None,
            pilot_slots: vec![],
            message,
            font,
            cache,
            raw: BTreeMap::new(),
            mod_art: BTreeMap::new(),
            palette,
            shadow_table,
            air_shadow_table,
            hud_state: HudState {
                tick: 0,
                shield: 100,
                blink: true,
                damage_flashes: 0,
                sweep: 0,
            },
            audio: None,
            sound_bank: crate::sound::SoundBank::default(),
            desired_music: None,
            clock: Clock::default(),
        })
    }
    fn go(&mut self, screen: Screen) {
        self.screen = screen;
        self.selected = 0;
        if screen == Screen::Shop {
            self.shop_selling = false;
        }
        if screen == Screen::Pilots {
            self.pilot_slots = self
                .slots()
                .into_iter()
                .map(|slot| {
                    let path = self.paths.save_path(slot);
                    let identity = std::fs::metadata(&path)
                        .ok()
                        .filter(|meta| meta.len() <= 1_048_576)
                        .and_then(|_| std::fs::read(path).ok())
                        .and_then(|bytes| serde_json::from_slice::<serde_json::Value>(&bytes).ok())
                        .and_then(|value| {
                            Some(format!(
                                "{} / {}",
                                value["callsign"].as_str()?,
                                value["name"].as_str()?
                            ))
                        })
                        .unwrap_or_else(|| "unavailable - select for details".into());
                    (slot, format!("{slot:04}: {identity}"))
                })
                .collect();
        }
    }
    fn save_config(&self) -> Result<()> {
        if self.read_only {
            return Ok(());
        }
        self.config.save(&self.paths)
    }
    fn save(&mut self) -> Result<()> {
        self.require_pilot()?;
        if self.read_only {
            return Ok(());
        }
        self.edit_pilot(|_, _| Ok(()))?;
        Ok(())
    }
    fn save_pilot_action(&mut self) -> Result<()> {
        anyhow::ensure!(!self.read_only, "Saving is disabled in preview mode");
        self.require_pilot()?;
        self.check_saved_slot()?;
        if self.world.is_some() {
            // Saving from Pause retains the last hangar inventory/progression
            // and its script snapshot, never half-completed mission state.
            let mut candidate = self.pilot.clone();
            candidate.validate(&self.active.registry, &self.active.pins)?;
            candidate.mods = self.active.pins.clone();
            candidate.save(&self.paths.save_path(self.slot))?;
            self.pilot = candidate;
        } else {
            self.save()?;
        }
        self.message = if self.world.is_some() {
            format!(
                "Saved {0} / {1:04}: hangar state only",
                self.pilot.callsign, self.slot
            )
        } else {
            format!("Saved {0} / slot {1:04}", self.pilot.callsign, self.slot)
        };
        self.play_ui_sound("FX_BONUS");
        Ok(())
    }
    fn hangar(&mut self) {
        self.go(Screen::Hangar);
        self.music("HANGAR_MUS");
    }
    fn music(&mut self, name: &str) {
        self.desired_music = self.catalog.id(name).ok();
        let score = self.catalog.named(name).and_then(|b| MusScore::decode(&b));
        if let (Some(device), Ok(score)) = (&mut self.audio, score) {
            device.lock().play_with_fade(score, true, true);
        }
    }
    fn play_ui_sound(&mut self, name: &str) {
        let Some(device) = &mut self.audio else {
            return;
        };
        let result = crate::sound::ui_event(name).and_then(|event| {
            let sample = self.sound_bank.original(&self.catalog, event.asset)?;
            device
                .lock()
                .sample(sample, event.pan, event.pitch, event.volume, event.priority);
            Ok(())
        });
        if let Err(error) = result {
            self.message = format!("Audio cue unavailable: {error:#}");
        }
    }
    fn start(&mut self, id: ContentId) -> Result<()> {
        self.require_pilot()?;
        self.pilot.mission = id.clone();
        self.pilot.difficulty = self.config.difficulty;
        self.active.scripts.states = self.pilot.script_state.clone();
        self.active.scripts.rng = self.pilot.script_rng.clone();
        self.world = Some(World::new(&id, &self.pilot, &self.active.registry)?);
        self.hud_state = HudState::new(self.world.as_ref().unwrap());
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
        let mut ids: Vec<_> = self
            .active
            .registry
            .items
            .values()
            .filter(|i| i.legacy.is_none_or(|n| n < 18))
            .map(|i| i.id.clone())
            .collect();
        ids.sort_by_key(|id| {
            (
                self.active.registry.items[id].legacy.unwrap_or(u32::MAX),
                id.clone(),
            )
        });
        ids
    }
    fn inventory_ids(&self) -> Vec<ContentId> {
        owned_items(&self.pilot, &self.active.registry)
    }
    fn shop_ids(&self) -> Vec<ContentId> {
        if self.shop_selling {
            self.inventory_ids()
                .into_iter()
                .filter(|id| sellable(id))
                .collect()
        } else {
            self.items()
        }
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
                "Return to hangar",
                "New pilot",
                "Load / import pilot",
                "Options",
                "Mods",
                "Help / credits",
                "Watch intro",
                "Quit",
            ]
            .into_iter()
            .map(str::to_string)
            .collect(),
            Screen::Hangar => [
                "Fly mission",
                "Select mission",
                "Supply room / shop",
                "Inventory / equipment",
                "Save pilot",
                "Edit pilot ID",
                "Exit hangar",
            ]
            .into_iter()
            .map(str::to_string)
            .collect(),
            Screen::Extras => ["Flight controls", "Credits", "Return to main menu"]
                .into_iter()
                .map(str::to_string)
                .collect(),
            Screen::PilotForm => self
                .pilot_form
                .as_ref()
                .map(|form| {
                    let mut rows = vec![
                        format!(
                            "Name: {}{}",
                            form.name,
                            if form.field == Some(0) { "_" } else { "" }
                        ),
                        format!(
                            "Callsign: {}{}",
                            form.callsign,
                            if form.field == Some(1) { "_" } else { "" }
                        ),
                        format!("ID picture: {} / 4 (change)", form.portrait + 1),
                    ];
                    if form.creating {
                        rows.push(format!(
                            "Difficulty: {} (change)",
                            ["Training", "Rookie", "Veteran", "Elite"][form.difficulty as usize]
                        ));
                    }
                    rows.push(if form.creating {
                        "Create pilot and enter hangar".into()
                    } else {
                        "Save pilot ID".into()
                    });
                    rows.push("Cancel".into());
                    rows
                })
                .unwrap_or_default(),
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
            Screen::Shop => std::iter::once(if self.shop_selling {
                "Mode: SELL (switch)".into()
            } else {
                "Mode: BUY (switch)".into()
            })
            .chain(self.shop_ids().iter().map(|id| {
                let i = &self.active.registry.items[id];
                format!(
                    "{}  ${}  x{}",
                    i.name,
                    if self.shop_selling {
                        i.resale_price()
                    } else {
                        i.price
                    },
                    self.pilot.item_count(id)
                )
            }))
            .collect(),
            Screen::Inventory => self
                .inventory_ids()
                .iter()
                .map(|id| {
                    let i = &self.active.registry.items[id];
                    let n = self.pilot.item_count(id);
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
                .collect(),
            Screen::ShopDetails => self
                .shop_detail_item
                .as_ref()
                .and_then(|id| self.shop_info(id).ok())
                .map(|info| {
                    info.full_lines()
                        .into_iter()
                        .flat_map(|line| wrap_text(&self.font, &line, 274))
                        .collect()
                })
                .unwrap_or_default(),
            Screen::Pilots => ["Create new pilot".into(), "Import legacy pilot".into()]
                .into_iter()
                .chain(self.pilot_slots.iter().map(|(_, label)| label.clone()))
                .collect(),
            Screen::LegacyPilots => self
                .legacy_slots()
                .iter()
                .map(|path| {
                    format!(
                        "Import {}",
                        path.file_name().unwrap_or_default().to_string_lossy()
                    )
                })
                .collect(),
            Screen::ConfirmDisable => [
                "Yes, disable these mods".into(),
                "Cancel - keep enabled".into(),
            ]
            .into_iter()
            .chain(
                self.pending_disable
                    .iter()
                    .flat_map(|plan| plan.removed.iter())
                    .map(|id| {
                        self.discovery
                            .mods
                            .get(id)
                            .map(|installed| {
                                format!(
                                    "Disable: {} {}",
                                    installed.manifest.name, installed.manifest.version
                                )
                            })
                            .unwrap_or_else(|| format!("Disable: {id}"))
                    }),
            )
            .collect(),
            Screen::Diagnostics => self.diagnostics(),
            Screen::Bindings => ACTIONS
                .iter()
                .map(|action| format!("{}: {}", action, binding_label(&self.config, action)))
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
                "Save settings".into(),
                "Return".into(),
            ],
            Screen::Pause => vec![
                "Resume",
                "Options",
                "Mods",
                "Save pilot (hangar state)",
                "Return to main menu",
            ]
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
                "{error}. Restore matching mods, load a compatible pilot, or choose New pilot to create a separate pilot."
            ));
        }
        self.pilot
            .validate(&self.active.registry, &self.active.pins)
    }
    fn slots(&self) -> Vec<usize> {
        let mut slots = std::fs::read_dir(&self.paths.data)
            .into_iter()
            .flatten()
            .filter_map(|entry| {
                let entry = entry.ok()?;
                if !entry.file_type().ok()?.is_file() {
                    return None;
                }
                let name = entry.file_name();
                let name = name.to_str()?;
                let number = name.strip_prefix("pilot-")?.strip_suffix(".json")?;
                (number.len() == 4 && number.bytes().all(|b| b.is_ascii_digit()))
                    .then(|| number.parse::<usize>().ok())
                    .flatten()
                    .filter(|slot| *slot < 1000)
            })
            .collect::<Vec<_>>();
        slots.sort_unstable();
        slots
    }
    fn legacy_slots(&self) -> Vec<PathBuf> {
        let mut slots = std::fs::read_dir(&self.paths.legacy)
            .into_iter()
            .flatten()
            .filter_map(|entry| {
                let entry = entry.ok()?;
                if !entry.file_type().ok()?.is_file() {
                    return None;
                }
                let name = entry.file_name();
                let name = name.to_str()?;
                let number = name.strip_prefix("CHAR")?.strip_suffix(".FIL")?;
                (number.len() == 4 && number.bytes().all(|b| b.is_ascii_digit()))
                    .then(|| entry.path())
            })
            .collect::<Vec<_>>();
        slots.sort();
        slots
    }
    fn unused_slot(&self) -> Result<usize> {
        (0..1000)
            .find(|n| std::fs::symlink_metadata(self.paths.save_path(*n)).is_err())
            .context("all pilot slots are occupied")
    }
    fn new_pilot(&mut self) -> Result<()> {
        self.create_pilot("Pilot".into(), "RAPTOR".into(), 0)
    }
    fn create_pilot(&mut self, name: String, callsign: String, portrait: usize) -> Result<()> {
        let slot = self.unused_slot()?;
        let mut pilot = Pilot {
            name,
            callsign,
            credits: 10000,
            mods: self.active.pins.clone(),
            difficulty: self.config.difficulty,
            legacy_progress: Some(crate::persistence::LegacyProgress {
                portrait: portrait_asset_id(portrait),
                sector: 0,
                waves: [0; 3],
                difficulties: [
                    self.config.difficulty,
                    self.config.difficulty,
                    self.config.difficulty,
                    2,
                ],
                training: self.config.difficulty == 0,
                training_completed: self.config.difficulty != 0,
            }),
            ..Pilot::default()
        };
        pilot.inventory.insert("base:energy".into(), 75);
        pilot.validate(&self.active.registry, &self.active.pins)?;
        if !self.read_only {
            pilot.save(&self.paths.save_path(slot))?;
        }
        self.slot = slot;
        self.pilot = pilot;
        self.pilot_error = None;
        self.active.scripts.states.clear();
        self.active.scripts.rng.clear();
        self.message = format!("New pilot in slot {slot:04}");
        Ok(())
    }
    fn begin_pilot_form(&mut self, creating: bool) -> Result<()> {
        anyhow::ensure!(
            self.world.is_none(),
            "Return to the hangar before editing a pilot"
        );
        if !creating {
            self.require_pilot()?;
        }
        let return_to = self.screen;
        self.pilot_form = Some(PilotForm {
            name: if creating {
                String::new()
            } else {
                self.pilot.name.clone()
            },
            callsign: if creating {
                String::new()
            } else {
                self.pilot.callsign.clone()
            },
            portrait: self
                .pilot
                .legacy_progress
                .as_ref()
                .map_or(0, |p| portrait_index(p.portrait)),
            original_portrait: if creating {
                None
            } else {
                self.pilot
                    .legacy_progress
                    .as_ref()
                    .map(|progress| progress.portrait)
            },
            difficulty: self.config.difficulty,
            creating,
            return_to,
            field: Some(0),
            replace_on_input: true,
        });
        self.go(Screen::PilotForm);
        self.message = "Enter name and callsign; ENTER advances".into();
        Ok(())
    }
    fn type_pilot_text(&mut self, text: &str) {
        let Some(form) = &mut self.pilot_form else {
            return;
        };
        let Some(field) = form.field else {
            return;
        };
        let value = if field == 0 {
            &mut form.name
        } else {
            &mut form.callsign
        };
        let text = text
            .chars()
            .filter(|ch| ch.is_ascii() && !ch.is_ascii_control())
            .collect::<String>();
        if text.is_empty() {
            return;
        }
        if form.replace_on_input {
            value.clear();
            form.replace_on_input = false;
        }
        let available = (if field == 0 { 20_usize } else { 12 }).saturating_sub(value.len());
        value.extend(text.chars().take(available));
    }
    fn pilot_field_key(&mut self, key: Keycode) -> bool {
        let Some(form) = &mut self.pilot_form else {
            return false;
        };
        let Some(field) = form.field else {
            return false;
        };
        match key {
            Keycode::Backspace => {
                let value = if field == 0 {
                    &mut form.name
                } else {
                    &mut form.callsign
                };
                if form.replace_on_input {
                    value.clear();
                } else {
                    value.pop();
                }
                form.replace_on_input = false;
            }
            Keycode::Delete => {
                if field == 0 {
                    form.name.clear();
                } else {
                    form.callsign.clear();
                }
                form.replace_on_input = false;
            }
            Keycode::Return | Keycode::Tab => {
                form.field = (field == 0).then_some(1);
                self.selected = if field == 0 {
                    1
                } else if form.creating {
                    4
                } else {
                    3
                };
                form.replace_on_input = true;
            }
            Keycode::Escape | Keycode::Up | Keycode::Down => return false,
            _ => {}
        }
        true
    }
    fn cancel_pilot_form(&mut self) {
        let return_to = self
            .pilot_form
            .take()
            .map_or(Screen::Main, |form| form.return_to);
        self.go(return_to);
        self.message = "Pilot ID unchanged".into();
    }
    fn commit_pilot_form(&mut self) -> Result<()> {
        let form = self.pilot_form.as_ref().context("pilot form is not open")?;
        let name = form.name.trim().to_string();
        let callsign = form.callsign.trim().to_string();
        let creating = form.creating;
        let portrait = form.portrait;
        let stored_portrait = form
            .original_portrait
            .filter(|original| portrait_index(*original) == portrait)
            .unwrap_or_else(|| portrait_asset_id(portrait));
        let difficulty = form.difficulty;
        anyhow::ensure!(!name.is_empty(), "Enter the pilot's name");
        anyhow::ensure!(!callsign.is_empty(), "Enter a callsign");
        anyhow::ensure!(
            name.len() <= 20 && callsign.len() <= 12,
            "Name permits 20 characters; callsign permits 12"
        );
        if creating {
            let previous_difficulty = self.config.difficulty;
            self.config.difficulty = difficulty;
            if let Err(error) = self.create_pilot(name, callsign, portrait) {
                self.config.difficulty = previous_difficulty;
                return Err(error);
            }
        } else {
            self.edit_pilot(|pilot, _| {
                pilot.name = name;
                pilot.callsign = callsign;
                let progress =
                    pilot
                        .legacy_progress
                        .get_or_insert(crate::persistence::LegacyProgress {
                            portrait: 0,
                            sector: 0,
                            waves: [0; 3],
                            difficulties: [pilot.difficulty; 4],
                            training: pilot.difficulty == 0,
                            training_completed: false,
                        });
                progress.portrait = stored_portrait;
                Ok(())
            })?;
            self.message = "Pilot ID saved".into();
        }
        self.pilot_form = None;
        self.hangar();
        Ok(())
    }
    fn import_pilot(&mut self, path: &std::path::Path) -> Result<()> {
        let slot = self.unused_slot()?;
        let mut pilot = Pilot::import_legacy(path, &self.active.registry)?;
        pilot.mods = self.active.pins.clone();
        pilot.validate(&self.active.registry, &self.active.pins)?;
        if !self.read_only {
            pilot.save(&self.paths.save_path(slot))?;
        }
        restore_scripts(&mut self.active.scripts, &pilot);
        self.pilot = pilot;
        self.config.difficulty = self.pilot.difficulty;
        self.slot = slot;
        self.pilot_error = None;
        self.message = format!("Imported {} into slot {slot:04}", self.pilot.callsign);
        self.hangar();
        Ok(())
    }
    fn edit_pilot(&mut self, edit: impl FnOnce(&mut Pilot, &Registry) -> Result<()>) -> Result<()> {
        self.require_pilot()?;
        self.check_saved_slot()?;
        let mut candidate = self.pilot.clone();
        edit(&mut candidate, &self.active.registry)?;
        candidate.script_state = self.active.scripts.states.clone();
        candidate.script_rng = self.active.scripts.rng.clone();
        candidate.validate(&self.active.registry, &self.active.pins)?;
        candidate.mods = self.active.pins.clone();
        if !self.read_only {
            candidate.save(&self.paths.save_path(self.slot))?;
        }
        self.pilot = candidate;
        Ok(())
    }
    fn check_saved_slot(&self) -> Result<()> {
        let path = self.paths.save_path(self.slot);
        if std::fs::symlink_metadata(&path).is_ok() {
            Pilot::load(&path, &self.active.registry, &self.active.pins)
                .with_context(|| format!("Existing pilot slot {:04} is unavailable; load matching mods or create a separate pilot", self.slot))?;
        }
        Ok(())
    }
    fn diagnostics(&self) -> Vec<String> {
        let mut lines = vec![self.message.clone()];
        if let Some(mod_id) = &self.diagnostic_mod {
            if let Some(installed) = self.discovery.mods.get(mod_id) {
                let manifest = &installed.manifest;
                lines.push(format!(
                    "{} {} / API {}",
                    manifest.name, manifest.version, manifest.api_version
                ));
                lines.push(manifest.description.clone());
                lines.extend(dependency_lines(manifest, &self.discovery, &self.pending));
                lines.push(format!(
                    "Conflicts: {}",
                    if manifest.conflicts.is_empty() {
                        "none".into()
                    } else {
                        manifest.conflicts.join(", ")
                    }
                ));
            }
        }
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
    fn open_diagnostics(&mut self) {
        self.diagnostic_mod = if self.screen == Screen::Mods && self.selected >= 2 {
            self.mod_ids().get(self.selected - 2).cloned()
        } else {
            None
        };
        self.diagnostic_return = self.screen;
        self.go(Screen::Diagnostics);
        self.play_ui_sound("FX_SWEP");
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
        self.sound_bank.clear_mods();
        self.mod_art.clear();
        if self.pilot_error.is_some() {
            self.message = "Mods applied; restore saved mods or choose Load / New pilot".into();
        } else {
            self.message = "Mods applied".into();
        }
        Ok(())
    }
    fn activate(&mut self) -> Result<bool> {
        match self.screen {
            Screen::Main => match self.selected {
                0 => {
                    self.require_pilot()?;
                    self.hangar();
                }
                1 => self.begin_pilot_form(true)?,
                2 => self.go(Screen::Pilots),
                3 => {
                    self.previous = Screen::Main;
                    self.go(Screen::Options);
                }
                4 => self.go(Screen::Mods),
                5 => self.go(Screen::Extras),
                6 => self.show_movie(MovieKind::Intro, Screen::Main)?,
                7 => return Ok(false),
                _ => {}
            },
            Screen::Hangar => match self.selected {
                0 => self.start(self.pilot.mission.clone())?,
                1 => self.go(Screen::Missions),
                2 => {
                    self.go(Screen::Shop);
                    self.play_ui_sound("FX_DOOR");
                }
                3 => self.go(Screen::Inventory),
                4 => self.save_pilot_action()?,
                5 => self.begin_pilot_form(false)?,
                6 => self.return_main()?,
                _ => {}
            },
            Screen::Extras => match self.selected {
                0 => self.go(Screen::Help),
                1 => self.go(Screen::Credits),
                2 => self.return_main()?,
                _ => {}
            },
            Screen::PilotForm => match self.selected {
                0 | 1 => {
                    if let Some(form) = &mut self.pilot_form {
                        form.field = Some(self.selected);
                        form.replace_on_input = true;
                    }
                }
                2 => {
                    if let Some(form) = &mut self.pilot_form {
                        form.portrait = (form.portrait + 1) % 4;
                        form.field = None;
                    }
                }
                _ => {
                    let creating = self.pilot_form.as_ref().is_some_and(|form| form.creating);
                    if creating && self.selected == 3 {
                        if let Some(form) = &mut self.pilot_form {
                            form.difficulty = (form.difficulty + 1) % 4;
                            form.field = None;
                        }
                    } else if self.selected == if creating { 4 } else { 3 } {
                        self.commit_pilot_form()?;
                    } else if self.selected == if creating { 5 } else { 4 } {
                        self.cancel_pilot_form();
                    }
                }
            },
            Screen::Missions => {
                if let Some(id) = self.missions().get(self.selected) {
                    self.start(id.clone())?;
                }
            }
            Screen::Pilots => {
                if self.selected == 0 {
                    self.begin_pilot_form(true)?;
                } else if self.selected == 1 {
                    self.go(Screen::LegacyPilots);
                    if self.legacy_slots().is_empty() {
                        self.message =
                            format!("No CHARxxxx.FIL pilots in {}", self.paths.legacy.display());
                    }
                } else if let Some(slot) = self
                    .pilot_slots
                    .get(self.selected - 2)
                    .map(|(slot, _)| *slot)
                {
                    let p = Pilot::load(
                        &self.paths.save_path(slot),
                        &self.active.registry,
                        &self.active.pins,
                    )?;
                    restore_scripts(&mut self.active.scripts, &p);
                    self.pilot = p;
                    self.config.difficulty = self.pilot.difficulty;
                    self.slot = slot;
                    self.pilot_error = None;
                    self.message = format!("Loaded pilot slot {slot:04}");
                    self.hangar();
                }
            }
            Screen::LegacyPilots => {
                if let Some(path) = self.legacy_slots().get(self.selected).cloned() {
                    self.import_pilot(&path)?;
                }
            }
            Screen::Shop => {
                if self.selected == 0 {
                    self.toggle_shop_mode();
                } else if let Some(id) = self.shop_ids().get(self.selected - 1).cloned() {
                    let selling = self.shop_selling;
                    self.edit_pilot(|pilot, registry| {
                        if selling {
                            pilot.sell(&id, registry)
                        } else {
                            pilot.buy(&id, registry)
                        }
                    })?;
                    self.selected = self.selected.min(self.rows().len().saturating_sub(1));
                    self.message = if selling {
                        "Sale complete"
                    } else {
                        "Purchase complete"
                    }
                    .into();
                    self.play_ui_sound("FX_BONUS");
                }
            }
            Screen::Inventory => {
                if let Some(id) = self.inventory_ids().get(self.selected).cloned() {
                    if self
                        .active
                        .registry
                        .items
                        .get(&id)
                        .is_some_and(|i| i.special)
                    {
                        self.edit_pilot(|pilot, _| {
                            pilot.selected = Some(id);
                            Ok(())
                        })?;
                        self.message = "Weapon equipped".into();
                    } else {
                        self.message = "Primary equipment is always active".into();
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
                    if self.pending.contains(&id) {
                        let plan =
                            crate::mod_selection::plan_disable(&self.discovery, &self.pending, &id);
                        if plan.removed.len() == 1 {
                            self.pending = plan.enabled;
                            self.message = format!("Deselected {id}. Choose Apply selections");
                            self.selected = self
                                .mod_ids()
                                .iter()
                                .position(|selected| selected == &id)
                                .unwrap_or(0)
                                + 2;
                        } else {
                            self.pending_disable = Some(plan);
                            self.go(Screen::ConfirmDisable);
                            self.selected = 1; // Default to keeping the enabled selection.
                        }
                    } else {
                        let enabled =
                            crate::mod_selection::plan_enable(&self.discovery, &self.pending, &id)?;
                        let added = enabled
                            .iter()
                            .filter(|id| !self.pending.contains(id))
                            .cloned()
                            .collect::<Vec<_>>();
                        self.pending = enabled;
                        self.selected = self
                            .mod_ids()
                            .iter()
                            .position(|selected| selected == &id)
                            .unwrap_or(0)
                            + 2;
                        self.message =
                            format!("Selected {}. Choose Apply selections", added.join(", "));
                    }
                }
            }
            Screen::ConfirmDisable => {
                if self.selected == 0 {
                    if let Some(plan) = self.pending_disable.take() {
                        self.pending = plan.enabled;
                        self.message = format!(
                            "Deselected {}. Choose Apply selections",
                            plan.removed.join(", ")
                        );
                    }
                    self.go(Screen::Mods);
                } else if self.selected == 1 {
                    self.pending_disable = None;
                    self.message = "Mod selection unchanged".into();
                    self.go(Screen::Mods);
                }
            }
            Screen::Options => {
                if self.selected == 11 {
                    self.go(Screen::Bindings);
                } else if self.selected == 13 {
                    anyhow::ensure!(!self.read_only, "Saving is disabled in preview mode");
                    self.save_config()?;
                    self.message = "Settings saved".into();
                } else if self.selected == 14 {
                    self.back()?;
                } else {
                    adjust_option(&mut self.config, self.selected, 1);
                }
            }
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
                3 => self.save_pilot_action()?,
                4 => self.return_main()?,
                _ => {}
            },
            Screen::Results => {
                self.return_main()?;
                self.hangar();
            }
            _ => {}
        }
        Ok(true)
    }
    fn choose(&mut self) -> Result<bool> {
        let result = self.activate();
        self.play_ui_sound(if result.is_ok() {
            "FX_SWEP"
        } else {
            "FX_WARNING"
        });
        result
    }
    fn move_selection(&mut self, delta: i32) {
        if self.screen == Screen::PilotForm {
            if let Some(form) = &mut self.pilot_form {
                form.field = None;
            }
        }
        let next = (self.selected as i64 + i64::from(delta))
            .clamp(0, self.rows().len().saturating_sub(1) as i64) as usize;
        if next != self.selected {
            self.selected = next;
            self.play_ui_sound("FX_SWEP");
        }
    }
    fn adjust(&mut self, direction: i32) {
        if self.screen == Screen::PilotForm && self.selected == 3 {
            if let Some(form) = &mut self.pilot_form {
                if form.creating {
                    form.difficulty =
                        (form.difficulty as i32 + direction.signum()).rem_euclid(4) as u32;
                    self.play_ui_sound("FX_SWEP");
                }
            }
        } else if self.screen == Screen::Options {
            if adjust_option(&mut self.config, self.selected, direction) {
                self.play_ui_sound("FX_SWEP");
            }
        } else if self.screen == Screen::Mods && self.selected >= 2 {
            if let Some(id) = self.mod_ids().get(self.selected - 2) {
                if let Some(n) = self.pending.iter().position(|m| m == id) {
                    let next = if direction < 0 {
                        n.saturating_sub(1)
                    } else {
                        (n + 1).min(self.pending.len() - 1)
                    };
                    if next != n {
                        self.pending.swap(n, next);
                        // Keep the selected mod under the cursor as the order changes.
                        self.selected = next + 2;
                        self.play_ui_sound("FX_SWEP");
                    }
                }
            }
        }
    }
    fn sell_inventory(&mut self) -> Result<()> {
        if let Some(id) = self.inventory_ids().get(self.selected).cloned() {
            self.edit_pilot(|pilot, registry| pilot.sell(&id, registry))?;
            self.selected = self.selected.min(self.rows().len().saturating_sub(1));
            self.message = "Sale complete".into();
        }
        Ok(())
    }
    fn open_shop_details(&mut self) {
        if let Some(id) = self
            .selected
            .checked_sub(1)
            .and_then(|index| self.shop_ids().get(index).cloned())
        {
            self.shop_detail_item = Some(id);
            self.go(Screen::ShopDetails);
            self.play_ui_sound("FX_SWEP");
        }
    }
    fn toggle_shop_mode(&mut self) {
        let item = self
            .selected
            .checked_sub(1)
            .and_then(|index| self.shop_ids().get(index).cloned());
        self.shop_selling = !self.shop_selling;
        self.selected = item
            .and_then(|item| {
                self.shop_ids()
                    .iter()
                    .position(|candidate| candidate == &item)
            })
            .map_or(0, |index| index + 1);
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
            Screen::ShopDetails => {
                let selling = self.shop_selling;
                self.go(Screen::Shop);
                self.shop_selling = selling;
                self.selected = self
                    .shop_detail_item
                    .as_ref()
                    .and_then(|id| self.shop_ids().iter().position(|candidate| candidate == id))
                    .map_or(0, |index| index + 1);
            }
            Screen::ConfirmDisable => {
                self.pending_disable = None;
                self.message = "Mod selection unchanged".into();
                self.go(Screen::Mods);
            }
            Screen::Cinematic => self.finish_movie(),
            Screen::PilotForm => self.cancel_pilot_form(),
            Screen::Game => self.go(Screen::Pause),
            Screen::Pause => self.go(Screen::Game),
            Screen::Options => {
                self.save_config()?;
                self.go(self.previous)
            }
            Screen::Mods if self.world.is_some() => self.go(Screen::Pause),
            Screen::Diagnostics => self.go(self.diagnostic_return),
            Screen::Bindings => {
                self.awaiting_binding = None;
                self.save_config()?;
                self.go(Screen::Options);
            }
            Screen::Results => {
                self.return_main()?;
                self.hangar();
            }
            Screen::LegacyPilots => self.go(Screen::Pilots),
            Screen::Missions | Screen::Shop | Screen::Inventory => self.hangar(),
            Screen::Help | Screen::Credits => self.go(Screen::Extras),
            _ => {
                self.go(Screen::Main);
                self.music("MAINMENU_MUS");
            }
        }
        self.play_ui_sound("FX_SWEP");
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
                    match self.sound_bank.original(&self.catalog, event.asset) {
                        Ok(sample) => audio.lock().sample(
                            sample,
                            event.pan,
                            event.pitch,
                            event.volume,
                            event.priority,
                        ),
                        Err(error) => {
                            self.message = format!("Cinematic sound unavailable: {error:#}")
                        }
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
            // SDL cycle/bomb inputs are non-repeating button-down pulses. Release
            // their simulation latches after delivery so a second genuine tap
            // on the next step is accepted. World::step still debounces held
            // inputs supplied directly by demos and headless controllers.
            if input.cycle {
                w.cycle_held = false;
            }
            if input.bomb {
                w.bomb_held = false;
            }
            self.hud_state.observe(w, &self.active.registry);
            input.cycle = false;
            input.bomb = false;
            self.queued_cycle = false;
            self.queued_bomb = false;
            if let Some(audio) = &mut self.audio {
                for event in &w.sound_events {
                    match self.sound_bank.original(&self.catalog, event.asset) {
                        Ok(sample) => audio.lock().sample(
                            sample,
                            event.pan,
                            event.pitch,
                            event.volume,
                            event.priority,
                        ),
                        Err(error) => {
                            self.message = format!("Mission sound unavailable: {error:#}")
                        }
                    }
                }
                if w.player.shield <= 10 && self.hud_state.blink && w.end_timer.is_none() {
                    let event = crate::sound::ui_event("FX_WARNING")?;
                    match self.sound_bank.original(&self.catalog, event.asset) {
                        Ok(sample) => audio.lock().sample(
                            sample,
                            event.pan,
                            event.pitch,
                            event.volume,
                            event.priority,
                        ),
                        Err(error) => {
                            self.message = format!("Shield warning unavailable: {error:#}")
                        }
                    }
                }
                for id in &w.mod_sounds {
                    match self.sound_bank.mod_sample(&self.active.registry, id) {
                        Ok(sample) => {
                            let event = &self.active.registry.sounds[id];
                            audio.lock().sample(
                                sample,
                                event.pan,
                                event.pitch,
                                event.volume,
                                event.priority as i32,
                            );
                        }
                        Err(error) => self.message = format!("Mod sound unavailable: {error:#}"),
                    }
                }
            }
            if w.outcome != Outcome::Playing {
                let outcome = w.outcome;
                let mission = w.mission.clone();
                let mut pilot = w.pilot(&self.pilot);
                if outcome == Outcome::Complete {
                    pilot.complete_mission(&self.active.registry)?;
                    self.edit_pilot(move |candidate, _| {
                        *candidate = pilot;
                        Ok(())
                    })?;
                    self.config.difficulty = self.pilot.difficulty;
                    // The pilot is committed. A settings failure must not
                    // retry progression against an already advanced pilot.
                    self.message = match self.save_config() {
                        Ok(()) => "Mission complete - pilot saved".into(),
                        Err(error) => format!("Pilot saved; settings save failed: {error:#}"),
                    };
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
                        self.message = format!("{}; cinematic unavailable: {e:#}", self.message);
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
            let pixelated = art.nearest
                || art
                    .asset
                    .is_some_and(|id| prefers_nearest(id + frame % art.frames));
            self.cache.get(&sprite, canvas.scale, pixelated)?.clone()
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
    fn shadow(
        &mut self,
        canvas: &mut Canvas,
        art: &Art,
        owner: &str,
        frame: u32,
        x: f32,
        y: f32,
        ground: bool,
    ) -> Result<()> {
        // Original masks retain their native canvas even when HD art is enabled.
        // Mod masks use the supplied SD artwork and explicit logical dimensions.
        let source = if let Some(asset) = art.asset {
            self.raw(asset + frame % art.frames)?
        } else {
            art_sprite_variant(
                &self.catalog,
                &self.active.registry,
                owner,
                art,
                frame,
                false,
            )?
        };
        let mask = if (source.width, source.height)
            == (art.logical_width as usize, art.logical_height as usize)
        {
            source
        } else {
            let mut logical =
                Sprite::blank(art.logical_width as usize, art.logical_height as usize);
            for row in 0..logical.height {
                for column in 0..logical.width {
                    logical.pixels[row * logical.width + column] =
                        source.pixels[(row * source.height / logical.height) * source.width
                            + column * source.width / logical.width];
                }
            }
            logical
        };
        if ground {
            shade_ground_shadow(canvas, &mask, x, y, &self.shadow_table);
        } else {
            shade_air_shadow(canvas, &mask, x, y, &self.air_shadow_table);
        }
        Ok(())
    }
    fn projectiles(
        &mut self,
        canvas: &mut Canvas,
        world: &World,
        hostile: bool,
        alpha: f32,
    ) -> Result<()> {
        for p in world.projectiles.iter().filter(|p| p.hostile == hostile) {
            let def = self.active.registry.weapons[&p.weapon].clone();
            let x = p.px as f32 + (p.x - p.px) as f32 * alpha;
            let y = p.py as f32 + (p.y - p.py) as f32 * alpha;
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
                        None => self
                            .cache
                            .get(&original, canvas.scale, prefers_nearest(asset + frame))?
                            .clone(),
                    };
                    canvas.blit(
                        &sprite,
                        (x * canvas.scale as f32).round() as i32,
                        (y * canvas.scale as f32).round() as i32,
                    );
                }
            } else if matches!(def.behavior, crate::content::WeaponBehavior::Beam) {
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
        Ok(())
    }
    fn effects(
        &mut self,
        canvas: &mut Canvas,
        world: &World,
        ground: bool,
        alpha: f32,
    ) -> Result<()> {
        for effect in world.effects.iter().filter(|e| e.ground == ground) {
            let (asset, frames) = effect.kind.artwork();
            let frame = effect.age.saturating_sub(1).min(frames - 1);
            let original = self.raw(asset + frame)?;
            let hd = if self.config.hd_mode {
                self.hd.sprite(asset + frame, canvas.scale, &self.palette)?
            } else {
                None
            };
            let sprite = match hd {
                Some(sprite) => sprite,
                None => self
                    .cache
                    .get(&original, canvas.scale, prefers_nearest(asset + frame))?
                    .clone(),
            };
            let x = effect.px as f32 + (effect.x - effect.px) as f32 * alpha
                - original.width as f32 / 2.0;
            let y = effect.py as f32 + (effect.y - effect.py) as f32 * alpha
                - original.height as f32 / 2.0;
            canvas.blit(
                &sprite,
                (x * canvas.scale as f32).round() as i32,
                (y * canvas.scale as f32).round() as i32,
            );
        }
        Ok(())
    }
    fn shop_info(&self, id: &ContentId) -> Result<ShopInfo> {
        shop_info(
            &self.pilot,
            &self.active.registry,
            id,
            self.require_pilot().err().map(|error| format!("{error:#}")),
        )
    }
    fn shop_panel(&mut self, canvas: &mut Canvas) -> Result<()> {
        canvas.rect(164, 43, 138, 126, closest(&self.palette, [15, 24, 42]));
        canvas.rect(164, 43, 1, 126, 100);
        let Some(id) = self
            .selected
            .checked_sub(1)
            .and_then(|index| self.shop_ids().get(index).cloned())
        else {
            for (index, line) in wrap_text(&self.font, "Choose BUY or SELL, then select equipment to view its image, price and flight behavior. Click this panel or press D/X for full details.", 126).iter().enumerate() {
                self.font.text(canvas, 172, 51 + index as i32 * 10, line, 100);
            }
            return Ok(());
        };
        let info = self.shop_info(&id)?;
        for (index, line) in wrap_text(&self.font, &info.name, 126)
            .iter()
            .take(2)
            .enumerate()
        {
            self.font.text(canvas, 172, 45 + index as i32 * 8, line, 50);
        }
        if let Some(art) = self.active.registry.items[&id].art.clone() {
            let owner = self
                .active
                .registry
                .owners
                .get(&id)
                .cloned()
                .unwrap_or_else(|| "base".into());
            // Render with the original logical canvas first so the normal SD/HD
            // asset path and transparency rules remain intact in this preview.
            let mut preview = Canvas {
                image: Sprite::blank(
                    art.logical_width as usize * canvas.scale,
                    art.logical_height as usize * canvas.scale,
                ),
                scale: canvas.scale,
            };
            self.art(&mut preview, &art, &owner, 0, 0.0, 0.0)?;
            let factor = (40.0 / art.logical_width as f32).min(32.0 / art.logical_height as f32);
            let width = (art.logical_width as f32 * factor).round().max(1.0) as usize;
            let height = (art.logical_height as f32 * factor).round().max(1.0) as usize;
            let mut thumbnail = Sprite::blank(width * canvas.scale, height * canvas.scale);
            for y in 0..thumbnail.height {
                for x in 0..thumbnail.width {
                    thumbnail.pixels[y * thumbnail.width + x] =
                        preview.image.pixels[(y * preview.image.height / thumbnail.height)
                            * preview.image.width
                            + x * preview.image.width / thumbnail.width];
                }
            }
            canvas.blit(
                &thumbnail,
                (172 + (40 - width as i32) / 2) * canvas.scale as i32,
                (64 + (32 - height as i32) / 2) * canvas.scale as i32,
            );
        } else {
            self.font.text(canvas, 172, 77, "NO IMAGE", 100);
        }
        for (y, text) in [
            (64, info.kind.to_string()),
            (73, format!("Buy ${}", info.price)),
            (82, format!("Sell ${}", info.resale)),
            (91, format!("Owned {}", info.owned)),
        ] {
            self.font.text(
                canvas,
                216,
                y,
                &fit_text(&self.font, &text, 82),
                if y == 64 { 50 } else { 100 },
            );
        }
        for (index, line) in info.stats.iter().take(4).enumerate() {
            self.font.text(
                canvas,
                172,
                104 + index as i32 * 8,
                &fit_text(&self.font, line, 126),
                100,
            );
        }
        for (index, line) in wrap_text(&self.font, &info.description, 126)
            .iter()
            .take(2)
            .enumerate()
        {
            self.font
                .text(canvas, 172, 136 + index as i32 * 8, line, 100);
        }
        let status = if self.shop_selling {
            format!("SELL: {}", info.sell)
        } else {
            format!("BUY: {}", info.buy)
        };
        for (index, line) in wrap_text(&self.font, &status, 126)
            .iter()
            .take(2)
            .enumerate()
        {
            self.font.text(
                canvas,
                172,
                154 + index as i32 * 8,
                line,
                if status.ends_with("Ready") { 50 } else { 34 },
            );
        }
        Ok(())
    }
    fn menu_portrait(
        &mut self,
        canvas: &mut Canvas,
        portrait: usize,
        x: i32,
        y: i32,
    ) -> Result<()> {
        let name = ["WMALEID_PIC", "BMALEID_PIC", "WFMALEID_PIC", "BFMALEID_PIC"][portrait.min(3)];
        if let Ok(id) = self.catalog.id(name) {
            let image = self.raw(id)?;
            canvas.blit(
                &nearest(&image, canvas.scale),
                x * canvas.scale as i32,
                y * canvas.scale as i32,
            );
        }
        Ok(())
    }
    fn classic_menu(&mut self, canvas: &mut Canvas) -> Result<()> {
        let panel = closest(&self.palette, [10, 15, 32]);
        let edge = closest(&self.palette, [70, 95, 115]);
        canvas.rect(12, 42, 144, 126, panel);
        canvas.rect(12, 42, 144, 1, edge);
        canvas.rect(12, 167, 144, 1, edge);
        self.font.text(canvas, 22, 49, "PILOT ID", 50);
        let portrait = self
            .pilot
            .legacy_progress
            .as_ref()
            .map_or(0, |p| portrait_index(p.portrait));
        self.menu_portrait(canvas, portrait, 22, 62)?;
        self.font.text(
            canvas,
            70,
            63,
            &fit_text(&self.font, &self.pilot.callsign, 80),
            50,
        );
        for (index, line) in wrap_text(&self.font, &self.pilot.name, 80)
            .iter()
            .take(2)
            .enumerate()
        {
            self.font.text(canvas, 70, 74 + index as i32 * 9, line, 100);
        }
        self.font.text(
            canvas,
            22,
            110,
            &format!("CREDITS: ${}", self.pilot.credits),
            100,
        );
        self.font.text(canvas, 22, 123, "NEXT MISSION", 50);
        let mission = self
            .active
            .registry
            .missions
            .get(&self.pilot.mission)
            .map(|m| m.name.clone())
            .unwrap_or_else(|| self.pilot.mission.0.clone());
        for (index, line) in wrap_text(&self.font, &mission, 124)
            .iter()
            .take(2)
            .enumerate()
        {
            self.font
                .text(canvas, 22, 134 + index as i32 * 9, line, 100);
        }
        self.font.text(
            canvas,
            22,
            157,
            &format!(
                "SLOT {:04} / {}",
                self.slot,
                ["TRAIN", "ROOKIE", "VETERAN", "ELITE"][self.config.difficulty as usize]
            ),
            100,
        );
        for (index, label) in self.rows().iter().enumerate() {
            let y = 42 + index as i32 * 16;
            canvas.rect(164, y, 136, 15, panel);
            canvas.rect(
                164,
                y,
                136,
                1,
                if index == self.selected { 50 } else { edge },
            );
            canvas.rect(164, y + 14, 136, 1, edge);
            let asset = if self.screen == Screen::Main {
                match index {
                    0 => Some("MENU7_PIC"),
                    3 => Some("MENU4_PIC"),
                    7 => Some("MENU8_PIC"),
                    _ => None,
                }
            } else {
                None
            };
            let native = asset.and_then(|name| self.catalog.id(name).ok());
            if let Some(asset) = native {
                let image = self.raw(asset)?;
                canvas.blit(
                    &nearest(&image, canvas.scale),
                    164 * canvas.scale as i32,
                    y * canvas.scale as i32,
                );
            } else {
                self.font.text(
                    canvas,
                    172,
                    y + 5,
                    &fit_text(&self.font, label, 124),
                    if index == self.selected { 50 } else { 100 },
                );
            }
            if index == self.selected {
                // Native button art must not cover the selection indicator.
                canvas.rect(164, y, 136, 1, 50);
                canvas.rect(164, y + 1, 3, 13, 50);
            }
        }
        Ok(())
    }
    fn hud_asset(&mut self, canvas: &mut Canvas, asset: u32, x: i32, y: i32) -> Result<()> {
        let original = self.raw(asset)?;
        let sprite = self.cache.get(&original, canvas.scale, true)?;
        canvas.blit(sprite, x * canvas.scale as i32, y * canvas.scale as i32);
        Ok(())
    }
    fn hud_weapon(&mut self, canvas: &mut Canvas, item: &ContentId) -> Result<()> {
        let definition = &self.active.registry.items[item];
        let Some(art) = definition.art.clone() else {
            return Ok(());
        };
        let owner = self.active.registry.owners[item].clone();
        let source = if let Some(asset) = art
            .asset
            .filter(|_| !(self.config.hd_mode && art.hd_png.is_some()))
        {
            self.raw(asset)?
        } else {
            art_sprite_variant(
                &self.catalog,
                &self.active.registry,
                &owner,
                &art,
                0,
                self.config.hd_mode,
            )?
        };
        // Original equipment icons keep their native canvas. Mod equipment
        // fits the same slot, including its transparent margins and HD detail.
        let logical_w = art.logical_width as usize;
        let logical_h = art.logical_height as usize;
        let shrink = (18.0 / logical_w as f32)
            .min(18.0 / logical_h as f32)
            .min(1.0);
        let width = ((logical_w as f32 * shrink).round() as usize).max(1) * canvas.scale;
        let height = ((logical_h as f32 * shrink).round() as usize).max(1) * canvas.scale;
        let mut icon = Sprite::blank(width, height);
        for y in 0..height {
            for x in 0..width {
                icon.pixels[y * width + x] = source.pixels
                    [(y * source.height / height) * source.width + x * source.width / width];
            }
        }
        canvas.blit(&icon, 286 * canvas.scale as i32, 2 * canvas.scale as i32);
        Ok(())
    }
    fn hud(&mut self, canvas: &mut Canvas, world: &World) -> Result<()> {
        canvas.rect(0, 0, 16, 200, 0);
        canvas.rect(304, 0, 16, 200, 0);
        hud_shield_bar(canvas, 8, world.player.super_shield);
        hud_shield_bar(canvas, 308, world.player.shield);
        // RAP_PrintNum's dollar glyph, one-pixel gap and eight-pixel digits.
        self.hud_asset(canvas, 0x1000f, 119, 2)?;
        for (position, digit) in format!("{:08}", world.player.credits).bytes().enumerate() {
            self.hud_asset(
                canvas,
                0x10005 + (digit - b'0') as u32,
                128 + position as i32 * 8,
                2,
            )?;
        }
        if let Some(item) = &world.player.selected {
            if world.player.inventory.get(item).is_some_and(|n| *n > 0) {
                self.hud_weapon(canvas, item)?;
            }
        }
        // Equipped charge and reserve modules are distinct inventory units.
        if world
            .player
            .inventory
            .contains_key(&ContentId::from("base:super_shield"))
        {
            for module in 0..=world.player.super_shield_reserves.len() {
                self.hud_asset(canvas, 0x102e0, 18 + module as i32 * 13, 1)?;
            }
        }
        let bombs = world
            .player
            .inventory
            .get(&ContentId::from("base:mega_bomb"))
            .copied()
            .unwrap_or(0);
        for index in 0..bombs.min(7) {
            self.hud_asset(canvas, 0x102df, 18 + index as i32 * 13, 186)?;
        }
        if bombs > 7 {
            self.font
                .text(canvas, 18 + 7 * 13, 189, &format!("+{}", bombs - 7), 68);
        }
        if world
            .player
            .inventory
            .get(&ContentId::from("base:detect"))
            .is_some_and(|n| *n > 0)
        {
            let level = boss_shield_percent(world, &self.active.registry);
            if level > 0 {
                canvas.rect(109, 191, 102, 8, 74);
                canvas.rect(110, 192, level, 6, 68);
            } else {
                canvas.rect(110 + self.hud_state.sweep as i32, 190, 1, 3, 68);
                canvas.rect(209 - self.hud_state.sweep as i32, 190, 1, 3, 68);
            }
        }
        if world.player.shield <= 10 && self.hud_state.blink {
            if self.hud_state.damage_flashes > 0 {
                let width = self.raw(0x10011)?.width as i32;
                self.hud_asset(canvas, 0x10011, (320 - width) / 2, 173)?;
            }
            let width = self.raw(0x10010)?.width as i32;
            self.hud_asset(canvas, 0x10010, (320 - width) / 2, 182)?;
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
        for ground in [true, false] {
            let mut shadows = 0;
            for e in &world.enemies {
                let def = self.active.registry.enemies[&e.definition].clone();
                if def.ground != ground
                    || def
                        .legacy
                        .as_ref()
                        .is_some_and(|legacy| legacy.fields[11] == 0)
                {
                    continue;
                }
                if shadows >= if ground { 25 } else { 50 } {
                    break;
                }
                if let Some(art) = def.art {
                    let owner = self.active.registry.owners[&e.definition].clone();
                    self.shadow(
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
                        ground,
                    )?;
                    shadows += 1;
                }
            }
            if !ground && shadows < 50 && world.draw_player {
                let mask = self.raw(player_frame)?;
                shade_air_shadow(
                    canvas,
                    &mask,
                    interp(world.player.x, world.player.px),
                    interp(world.player.y, world.player.py),
                    &self.air_shadow_table,
                );
            }
            if !ground {
                self.effects(canvas, &world, true, alpha)?;
            }
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
        self.projectiles(canvas, &world, false, alpha)?;
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
        if world.draw_player {
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
        }
        self.effects(canvas, &world, false, alpha)?;
        self.projectiles(canvas, &world, true, alpha)?;
        self.hud(canvas, &world)?;
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
        let classic = matches!(self.screen, Screen::Main | Screen::Hangar);
        canvas.rect(
            12,
            8,
            296,
            if classic { 31 } else { 184 },
            closest(&self.palette, [10, 15, 32]),
        );
        if classic {
            canvas.rect(12, 170, 296, 21, closest(&self.palette, [10, 15, 32]));
        }
        canvas.rect(12, 8, 296, 1, 100);
        canvas.rect(12, 191, 296, 1, 100);
        let title = match self.screen {
            Screen::Main => "RAPTOR / RUST",
            Screen::Hangar => "HANGAR",
            Screen::Extras => "HELP / CREDITS",
            Screen::PilotForm => {
                if self.pilot_form.as_ref().is_some_and(|form| form.creating) {
                    "REGISTER NEW PILOT"
                } else {
                    "EDIT PILOT ID"
                }
            }
            Screen::Missions => "MISSION SELECT",
            Screen::Shop => {
                if self.shop_selling {
                    "HANGAR / SHOP - SELL"
                } else {
                    "HANGAR / SHOP - BUY"
                }
            }
            Screen::ShopDetails => "EQUIPMENT DETAILS",
            Screen::Inventory => "INVENTORY / EQUIPMENT",
            Screen::Mods => "MOD MANAGER",
            Screen::Options => "OPTIONS",
            Screen::Pause => "PAUSED",
            Screen::Results => "FLIGHT REPORT",
            Screen::Help => "FLIGHT CONTROLS",
            Screen::Credits => "CREDITS",
            Screen::Pilots => "LOAD PILOT",
            Screen::LegacyPilots => "IMPORT LEGACY PILOT",
            Screen::ConfirmDisable => "ARE YOU SURE?",
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
        let shop = self.screen == Screen::Shop;
        let first = self.selected.saturating_sub(8);
        for (index, row) in rows
            .iter()
            .enumerate()
            .skip(first)
            .take(if classic { 0 } else { 10 })
        {
            let y = 46 + (index - first) as i32 * 11;
            if index == self.selected {
                canvas.rect(
                    20,
                    y - 2,
                    if shop {
                        140
                    } else if card.is_some() {
                        126
                    } else if self.screen == Screen::PilotForm {
                        214
                    } else {
                        280
                    },
                    10,
                    closest(&self.palette, [25, 45, 65]),
                );
            }
            self.font.text(
                &mut canvas,
                24,
                y,
                &if shop {
                    fit_text(&self.font, row, 132)
                } else if card.is_some() {
                    row.chars().take(20).collect::<String>()
                } else {
                    fit_text(
                        &self.font,
                        row,
                        if self.screen == Screen::PilotForm {
                            204
                        } else {
                            272
                        },
                    )
                },
                if index == self.selected { 50 } else { 100 },
            );
        }
        if classic {
            self.classic_menu(&mut canvas)?;
        }
        if self.screen == Screen::PilotForm {
            if let Some(form) = &self.pilot_form {
                let portrait = form.portrait;
                self.menu_portrait(&mut canvas, portrait, 252, 46)?;
            }
            for (index, line) in [
                "Name: up to 20 characters",
                "Callsign: up to 12 characters",
                "ENTER advances to the next field",
                "Choose Create / Save to finish",
                "Cancel or ESC preserves the current pilot",
            ]
            .iter()
            .enumerate()
            {
                self.font
                    .text(&mut canvas, 24, 112 + index as i32 * 10, line, 100);
            }
        }
        if let Some((mut art, owner)) = card {
            let height = (150 * art.logical_height / art.logical_width).min(108);
            art.logical_width = 150;
            art.logical_height = height;
            self.art(&mut canvas, &art, &owner, 0, 154.0, 52.0)?;
        }
        if shop {
            self.shop_panel(&mut canvas)?;
        }
        if self.screen == Screen::Mods {
            if self.selected >= 2 {
                if let Some(id) = self.mod_ids().get(self.selected - 2) {
                    let m = &self.discovery.mods[id];
                    let dependencies =
                        dependency_lines(&m.manifest, &self.discovery, &self.pending);
                    let summary = dependencies
                        .first()
                        .cloned()
                        .unwrap_or_else(|| "Dependencies: none".into());
                    self.font.text(
                        &mut canvas,
                        22,
                        160,
                        &summary.chars().take(52).collect::<String>(),
                        100,
                    );
                }
            }
            self.font.text(
                &mut canvas,
                22,
                171,
                "ENTER toggle/apply  <> priority  D/X details",
                50,
            );
        } else if self.screen == Screen::Help {
            let key = |action: &str| binding_label(&self.config, action);
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
                "Shop: choose BUY / SELL, then an item".into(),
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
            let hint = match self.screen {
                Screen::Options => "LEFT/RIGHT adjust  ENTER change  ESC back",
                Screen::Main | Screen::Hangar => "UP/DOWN choose  ENTER/A accept  ESC/B back",
                Screen::PilotForm => "Type ID  ENTER next  ESC cancel",
                Screen::Pause => "Save Pilot stores hangar state, not the flight",
                Screen::Shop if self.shop_selling => {
                    "ENTER sell  TAB/Y mode  D/X details  ESC back"
                }
                Screen::Shop => "ENTER buy  TAB/Y mode  D/X details  ESC back",
                Screen::ShopDetails => "UP/DOWN scroll  ESC back to shop",
                Screen::Inventory => "ENTER equip  S sell  ESC back",
                Screen::LegacyPilots => "ENTER import to a new Rust slot  ESC back",
                Screen::ConfirmDisable => "Dependents shown above. ESC cancels",
                _ => "ENTER/A choose  ESC/B back",
            };
            self.font.text(&mut canvas, 22, 171, hint, 50);
        }
        if !self.message.is_empty() {
            self.font.text(
                &mut canvas,
                22,
                181,
                &fit_text(&self.font, &self.message, 276),
                34,
            );
        }
        Ok(canvas)
    }
}
const ACTIONS: [&str; 8] = [
    "up", "down", "left", "right", "fire", "special", "cycle", "bomb",
];
fn portrait_asset_id(index: usize) -> i32 {
    [0x10116, 0x10119, 0x10117, 0x10118][index.min(3)]
}
fn portrait_index(value: i32) -> usize {
    match value {
        0..=3 => value as usize,
        0x10116 => 0,
        0x10119 => 1,
        0x10117 => 2,
        0x10118 => 3,
        _ => 0,
    }
}
fn owned_items(pilot: &Pilot, registry: &Registry) -> Vec<ContentId> {
    let mut ids: Vec<_> = pilot
        .inventory
        .iter()
        .filter(|(id, _)| pilot.item_count(id) > 0 && registry.items.contains_key(*id))
        .map(|(id, _)| id.clone())
        .collect();
    ids.sort_by_key(|id| (registry.items[id].legacy.unwrap_or(u32::MAX), id.clone()));
    ids
}
fn sellable(id: &ContentId) -> bool {
    id.0 != "base:forward_guns"
}
struct ShopInfo {
    name: String,
    description: String,
    kind: &'static str,
    price: u32,
    resale: u32,
    owned: u32,
    slots: usize,
    stats: Vec<String>,
    buy: String,
    sell: String,
    usage: &'static str,
}
impl ShopInfo {
    fn full_lines(&self) -> Vec<String> {
        let mut lines = vec![
            self.name.clone(),
            self.kind.into(),
            format!("Buy ${} / resale ${}", self.price, self.resale),
            format!(
                "Owned {} / inventory {} of 20 slots",
                self.owned, self.slots
            ),
        ];
        lines.extend(self.stats.clone());
        lines.push(self.description.clone());
        lines.push(self.usage.into());
        lines.push(format!("BUY: {}", self.buy));
        lines.push(format!("SELL: {}", self.sell));
        lines
    }
}
fn shop_info(
    pilot: &Pilot,
    registry: &Registry,
    id: &ContentId,
    blocked: Option<String>,
) -> Result<ShopInfo> {
    use crate::content::{Target, WeaponBehavior};
    let item = registry.items.get(id).context("unknown shop item")?;
    let (kind, usage) = if item.legacy == Some(11) {
        (
            "BOMB",
            "Press the bound Mega bomb control. Each blast consumes one bomb.",
        )
    } else if item.consumable {
        (
            "CONSUMABLE",
            if item.special {
                "Select this item in Inventory and use the Special control; effects may be scripted."
            } else {
                "Used by its pickup or scripted behavior; see the item description."
            },
        )
    } else if item.special {
        (
            "SELECTABLE",
            if item.weapon.is_some() {
                "Equip in Inventory or cycle specials in flight; fire using Fire or Special."
            } else {
                "Equip in Inventory or cycle specials in flight; activate using Special."
            },
        )
    } else if item.weapon.is_some() {
        (
            "ALWAYS EQUIPPED",
            "Fires together with the forward guns while owned; no selection needed.",
        )
    } else {
        ("PASSIVE", "Active while owned; no weapon selection needed.")
    };
    let mut stats = Vec::new();
    if let Some(weapon) = item
        .weapon
        .as_ref()
        .and_then(|weapon| registry.weapons.get(weapon))
    {
        stats.push(format!(
            "Targets: {}",
            match weapon.target {
                Target::Air => "air",
                Target::Ground => "ground",
                Target::All => "air + ground",
            }
        ));
        stats.push(if weapon.legacy == Some(10) {
            "Damage 1; drains guns".into()
        } else {
            format!("Damage {} / hit", weapon.damage)
        });
        stats.push(format!(
            "Cycle {} ticks ({:.2}/s)",
            weapon.cooldown,
            70.0 / (3.0 * f64::from(weapon.cooldown.max(1)))
        ));
        let behavior = match weapon.behavior {
            WeaponBehavior::Straight => "Straight",
            WeaponBehavior::Homing => "Homing",
            WeaponBehavior::Beam => "Beam",
            WeaponBehavior::Spread => "Spread",
            WeaponBehavior::Bomb => "Blast",
            WeaponBehavior::EnergyGrab => "Disables guns",
        };
        stats.push(format!(
            "{}{}",
            behavior,
            if weapon.script.is_some() {
                " / scripted"
            } else {
                ""
            }
        ));
    } else if id.0 == "base:super_shield" {
        stats.push(format!("Modules {} / 5", pilot.item_count(id)));
        stats.push(format!(
            "Active charge {}",
            pilot.inventory.get(id).copied().unwrap_or(0)
        ));
        stats.push(format!("Fresh charge {}", item.initial_count));
        stats.push("Reserves equip in order".into());
    } else {
        stats.push(format!("Capacity {}", item.max_count));
        stats.push(format!("Purchase adds {}", item.initial_count));
        if item.shield != 0 {
            stats.push(format!("Energy effect {:+}", item.shield));
        }
        if item.credits != 0 {
            stats.push(format!("Credit effect {:+}", item.credits));
        }
        if item.script.is_some() {
            stats.push("Scripted item effects".into());
        }
    }
    let eligibility = |selling: bool| {
        if let Some(error) = &blocked {
            return error.clone();
        }
        let mut candidate = pilot.clone();
        let result = if selling {
            candidate.sell(id, registry)
        } else {
            candidate.buy(id, registry)
        };
        result
            .err()
            .map_or_else(|| "Ready".into(), |error| format!("{error:#}"))
    };
    Ok(ShopInfo {
        name: item.name.clone(),
        description: if item.description.trim().is_empty() {
            usage.into()
        } else {
            item.description.clone()
        },
        kind,
        price: item.price,
        resale: item.resale_price(),
        owned: pilot.item_count(id),
        slots: pilot.inventory_slots(),
        stats,
        buy: eligibility(false),
        sell: eligibility(true),
        usage,
    })
}
fn fit_text(font: &BitmapFont, text: &str, width: usize) -> String {
    if font.text_width(text) <= width {
        return text.into();
    }
    let mut clipped = String::new();
    for ch in text.chars() {
        let next = format!("{clipped}{ch}...");
        if font.text_width(&next) > width {
            break;
        }
        clipped.push(ch);
    }
    clipped.push_str("...");
    clipped
}
fn wrap_text(font: &BitmapFont, text: &str, width: usize) -> Vec<String> {
    let mut lines = Vec::new();
    let mut line = String::new();
    for word in text.split_whitespace() {
        let joined = if line.is_empty() {
            word.to_string()
        } else {
            format!("{line} {word}")
        };
        if font.text_width(&joined) <= width {
            line = joined;
            continue;
        }
        if !line.is_empty() {
            lines.push(std::mem::take(&mut line));
        }
        for ch in word.chars() {
            if font.text_width(&format!("{line}{ch}")) > width && !line.is_empty() {
                lines.push(std::mem::take(&mut line));
            }
            line.push(ch);
        }
    }
    if !line.is_empty() {
        lines.push(line);
    }
    lines
}
fn menu_row_at(screen: Screen, selected: usize, rows: usize, x: i32, y: i32) -> Option<usize> {
    if matches!(screen, Screen::Main | Screen::Hangar) {
        if !(164..300).contains(&x) || !(42..170).contains(&y) {
            return None;
        }
        let selection = ((y - 42) / 16) as usize;
        return (selection < rows).then_some(selection);
    }
    let right = if screen == Screen::Shop { 160 } else { 300 };
    if !(20..right).contains(&x) || !(44..154).contains(&y) {
        return None;
    }
    let selection = selected.saturating_sub(8) + ((y - 44) / 11) as usize;
    (selection < rows).then_some(selection)
}
fn dependency_lines(
    manifest: &modding::Manifest,
    discovery: &Discovery,
    selected: &[String],
) -> Vec<String> {
    if manifest.dependencies.is_empty() {
        return vec!["Dependencies: none".into()];
    }
    manifest
        .dependencies
        .iter()
        .map(|(id, requirement)| {
            let status = if let Some(installed) = discovery.mods.get(id) {
                let matches = semver::VersionReq::parse(requirement)
                    .ok()
                    .zip(semver::Version::parse(&installed.manifest.version).ok())
                    .is_some_and(|(requirement, version)| requirement.matches(&version));
                format!(
                    "installed {} {}",
                    installed.manifest.version,
                    if !matches {
                        "VERSION MISMATCH"
                    } else if selected.contains(id) {
                        "enabled"
                    } else {
                        "DISABLED"
                    }
                )
            } else {
                "MISSING".into()
            };
            format!("Requires {id} {requirement}: {status}")
        })
        .collect()
}
fn step_volume(value: u8, direction: i32) -> u8 {
    if direction < 0 {
        if value == 0 {
            127
        } else {
            value.saturating_sub(16)
        }
    } else if value >= 127 {
        0
    } else {
        value.saturating_add(16).min(127)
    }
}
fn adjust_option(config: &mut Config, selected: usize, direction: i32) -> bool {
    if direction == 0 {
        return false;
    }
    let direction = direction.signum();
    let cycle = |value: i32, length: i32| (value + direction).rem_euclid(length);
    match selected {
        0 => config.scale = (cycle(config.scale as i32 - 1, 4) + 1) as usize,
        1 => config.scanlines = !config.scanlines,
        2 => config.fullscreen = !config.fullscreen,
        3 => config.borderless = !config.borderless,
        4 => config.aspect_correct = !config.aspect_correct,
        5 => config.music_volume = step_volume(config.music_volume, direction),
        6 => config.fx_volume = step_volume(config.fx_volume, direction),
        7 => {
            let controls = ["keyboard", "mouse", "controller"];
            let current = controls
                .iter()
                .position(|control| *control == config.control)
                .unwrap_or(0);
            config.control = controls[cycle(current as i32, 3) as usize].into();
        }
        8 => config.difficulty = cycle(config.difficulty as i32, 4) as u32,
        9 => {
            (config.width, config.height) = if (config.width, config.height) == (1280, 960) {
                (1920, 1080)
            } else {
                (1280, 960)
            };
        }
        10 => config.hd_mode = !config.hd_mode,
        12 => config.fx_channels = (cycle(config.fx_channels as i32 - 1, 8) + 1) as usize,
        _ => return false,
    }
    true
}
fn binding_matches(config: &Config, action: &str, key: Option<Scancode>) -> bool {
    key.is_some_and(|key| binding_keys(config, action).contains(&key))
}
fn binding_keys(config: &Config, action: &str) -> Vec<Scancode> {
    let primary = config
        .bindings
        .get(action)
        .and_then(|value| Scancode::from_name(value));
    let mut keys = primary.into_iter().collect::<Vec<_>>();
    if action == "cycle" && primary == Some(Scancode::LAlt) {
        // The default cycle control accepts either Alt or Shift, while a
        // customized action keeps ownership of any explicitly assigned key.
        for alias in [Scancode::RAlt, Scancode::LShift, Scancode::RShift] {
            if !config
                .bindings
                .iter()
                .any(|(other, value)| other != "cycle" && Scancode::from_name(value) == Some(alias))
            {
                keys.push(alias);
            }
        }
    }
    keys
}
fn binding_label(config: &Config, action: &str) -> String {
    let keys = binding_keys(config, action);
    if keys
        == [
            Scancode::LAlt,
            Scancode::RAlt,
            Scancode::LShift,
            Scancode::RShift,
        ]
    {
        "Alt / Shift".into()
    } else if keys.is_empty() {
        config
            .bindings
            .get(action)
            .cloned()
            .unwrap_or_else(|| "unbound".into())
    } else {
        keys.into_iter()
            .map(Scancode::name)
            .collect::<Vec<_>>()
            .join(" / ")
    }
}
#[cfg(test)]
mod binding_tests {
    use super::*;
    #[test]
    fn both_alt_and_shift_cycle_without_using_bombs_or_consumables() {
        let config = Config::default();
        assert_eq!(binding_label(&config, "cycle"), "Alt / Shift");
        for key in [
            Scancode::LAlt,
            Scancode::RAlt,
            Scancode::LShift,
            Scancode::RShift,
        ] {
            assert!(binding_matches(&config, "cycle", Some(key)));
            assert!(!binding_matches(&config, "bomb", Some(key)));
            assert!(!binding_matches(&config, "special", Some(key)));
        }
        assert!(binding_matches(&config, "bomb", Some(Scancode::Space)));
        assert!(!binding_matches(&config, "cycle", Some(Scancode::Space)));
        assert!(binding_matches(&config, "special", Some(Scancode::Z)));
        assert!(!binding_matches(&config, "cycle", None));
    }
    #[test]
    fn cycling_aliases_respect_custom_shift_bindings_and_custom_cycle_keys() {
        let mut config = Config::default();
        config.bindings.insert("fire".into(), "Right Shift".into());
        config.bindings.insert("bomb".into(), "Left Shift".into());
        assert!(binding_matches(&config, "fire", Some(Scancode::RShift)));
        assert!(binding_matches(&config, "bomb", Some(Scancode::LShift)));
        assert!(!binding_matches(&config, "cycle", Some(Scancode::RShift)));
        assert!(!binding_matches(&config, "cycle", Some(Scancode::LShift)));
        assert!(binding_matches(&config, "cycle", Some(Scancode::RAlt)));
        config.bindings.insert("cycle".into(), "Q".into());
        assert!(binding_matches(&config, "cycle", Some(Scancode::Q)));
        for key in [
            Scancode::LAlt,
            Scancode::RAlt,
            Scancode::LShift,
            Scancode::RShift,
        ] {
            assert!(!binding_matches(&config, "cycle", Some(key)));
        }
    }
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
    benchmark: bool,
) -> Result<()> {
    let setup_start = Instant::now();
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
    let audio_capture = std::env::var_os("RAPTOR_AUDIO_CAPTURE").map(PathBuf::from);
    match sdl.audio() {
        Ok(audio) => {
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
                    if let Err(error) = host.sound_bank.preload_originals(&host.catalog) {
                        host.message = format!("Original sound cache unavailable: {error:#}");
                    }
                    {
                        let mut mixer = device.lock();
                        mixer.set_fx_channels(host.config.fx_channels);
                        mixer.music_volume = host.config.music_volume;
                        mixer.fx_volume = host.config.fx_volume;
                        if audio_capture.is_some() {
                            let seconds = std::env::var("RAPTOR_AUDIO_CAPTURE_SECONDS")
                                .ok()
                                .map(|s| s.parse::<u32>())
                                .transpose()?
                                .unwrap_or(15);
                            mixer.start_capture(seconds)?;
                        }
                    }
                    device.resume();
                    host.audio = Some(device)
                }
                Err(e) => host.message = format!("Audio unavailable: {e}"),
            }
        }
        Err(error) => host.message = format!("Audio unavailable: {error}"),
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
    let setup_ms = setup_start.elapsed().as_secs_f64() * 1000.0;
    let mut work_times = Vec::new();
    let mut frame_times = Vec::new();
    let mut count = 0u32;
    let mut cycle = false;
    let mut bomb = false;
    let mut quit = false;
    let mut text_input_active = false;
    while !quit {
        let frame_start = Instant::now();
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
                            Button::DPadUp => host.move_selection(-1),
                            Button::DPadDown => host.move_selection(1),
                            Button::DPadLeft => host.adjust(-1),
                            Button::DPadRight => host.adjust(1),
                            Button::X if host.screen == Screen::Shop => host.open_shop_details(),
                            Button::Y if host.screen == Screen::Shop => {
                                host.toggle_shop_mode();
                                host.play_ui_sound("FX_SWEP");
                            }
                            Button::X if host.screen == Screen::Mods => host.open_diagnostics(),
                            Button::A => match host.choose() {
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
                    host.move_selection(y.saturating_neg());
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
                    if host.screen == Screen::PilotForm
                        && (252..292).contains(&xx)
                        && (46..86).contains(&yy)
                    {
                        host.selected = 2;
                        if let Err(error) = host.choose() {
                            host.message = error.to_string();
                        }
                        continue;
                    }
                    if host.screen == Screen::Shop
                        && (164..302).contains(&xx)
                        && (43..169).contains(&yy)
                    {
                        host.open_shop_details();
                        continue;
                    }
                    if host.screen == Screen::Mods
                        && (20..300).contains(&xx)
                        && (158..178).contains(&yy)
                    {
                        host.open_diagnostics();
                        continue;
                    }
                    if let Some(selection) =
                        menu_row_at(host.screen, host.selected, host.rows().len(), xx, yy)
                    {
                        host.selected = selection;
                        match host.choose() {
                            Ok(r) => quit = !r,
                            Err(e) => host.message = format!("{e:#}"),
                        }
                    }
                }
                Event::TextInput { text, .. } if host.screen == Screen::PilotForm => {
                    host.type_pilot_text(&text);
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
                    if host.screen == Screen::PilotForm
                        && host
                            .pilot_form
                            .as_ref()
                            .is_some_and(|form| form.field.is_some())
                    {
                        if key == Keycode::Escape {
                            if let Err(error) = host.back() {
                                host.message = error.to_string();
                            }
                            continue;
                        }
                        if host.pilot_field_key(key) {
                            continue;
                        }
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
                        Keycode::Up => host.move_selection(-1),
                        Keycode::Down => host.move_selection(1),
                        Keycode::Return => match host.choose() {
                            Ok(r) => quit = !r,
                            Err(e) => host.message = format!("{e:#}"),
                        },
                        Keycode::D if host.screen == Screen::Shop => host.open_shop_details(),
                        Keycode::Tab if host.screen == Screen::Shop => {
                            host.toggle_shop_mode();
                            host.play_ui_sound("FX_SWEP");
                        }
                        Keycode::D
                            if !matches!(
                                host.screen,
                                Screen::ConfirmDisable | Screen::PilotForm
                            ) =>
                        {
                            host.open_diagnostics()
                        }
                        Keycode::N
                            if host.world.is_none()
                                && !matches!(
                                    host.screen,
                                    Screen::ConfirmDisable | Screen::PilotForm
                                ) =>
                        {
                            if let Err(e) = host.begin_pilot_form(true) {
                                host.play_ui_sound("FX_WARNING");
                                host.message = e.to_string();
                            } else {
                                host.play_ui_sound("FX_SWEP");
                            }
                        }
                        Keycode::S if host.screen == Screen::Inventory => {
                            if let Err(e) = host.sell_inventory() {
                                host.play_ui_sound("FX_WARNING");
                                host.message = e.to_string();
                            } else {
                                host.play_ui_sound("FX_SWEP");
                            }
                        }
                        Keycode::Left => host.adjust(-1),
                        Keycode::Right => host.adjust(1),
                        _ => {}
                    }
                }
                _ => {}
            }
        }
        let editing = host.screen == Screen::PilotForm
            && host
                .pilot_form
                .as_ref()
                .is_some_and(|form| form.field.is_some());
        if editing != text_input_active {
            let input = canvas.window().subsystem().text_input();
            if editing {
                input.start();
            } else {
                input.stop();
            }
            text_input_active = editing;
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
            binding_keys(&host.config, action)
                .into_iter()
                .any(|key| keyboard.is_scancode_pressed(key))
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
        let work_ms = frame_start.elapsed().as_secs_f64() * 1000.0;
        canvas.present();
        if benchmark && count >= 5 && !frames.is_some_and(|n| count + 1 >= n) {
            work_times.push(work_ms);
            frame_times.push(frame_start.elapsed().as_secs_f64() * 1000.0);
        }
        count += 1;
        if frames.is_some_and(|n| count >= n) {
            quit = true;
        }
        if frames.is_some() {
            std::thread::sleep(Duration::from_millis(1));
        }
    }
    if benchmark && !work_times.is_empty() {
        let (output_width, output_height) = canvas.output_size().map_err(|e| anyhow!(e))?;
        work_times.sort_by(f64::total_cmp);
        frame_times.sort_by(f64::total_cmp);
        let percentile = |values: &[f64], p: usize| values[(values.len() - 1) * p / 100];
        println!(
            "benchmark renderer={} size={}x{} scale={} hd={} startup_ms={setup_ms:.2} samples={} work_p50_ms={:.2} work_p95_ms={:.2} frame_p50_ms={:.2} frame_p95_ms={:.2}",
            canvas.info().name,
            output_width,
            output_height,
            host.config.scale,
            host.config.hd_mode,
            work_times.len(),
            percentile(&work_times, 50),
            percentile(&work_times, 95),
            percentile(&frame_times, 50),
            percentile(&frame_times, 95)
        );
    }
    if frames.is_none() {
        host.config.save(&host.paths)?;
    }
    if let Some(path) = audio_capture {
        let audio = host
            .audio
            .as_mut()
            .context("audio capture requires an available SDL output device")?;
        audio.pause();
        let capture = audio
            .lock()
            .take_capture()
            .context("audio capture was not started")?;
        let nonzero = capture.samples.iter().filter(|&&s| s != 0).count();
        println!(
            "Audio capture: rate={} frames={} nonzero_samples={} file={}",
            capture.rate,
            capture.samples.len() / 2,
            nonzero,
            path.display()
        );
        std::fs::write(path, crate::sound::encode_capture(&capture)?)?;
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    fn ui_fixture() -> (tempfile::TempDir, Host) {
        let dir = tempfile::tempdir().unwrap();
        let catalog_root = dir.path().join("catalog");
        std::fs::create_dir(&catalog_root).unwrap();
        std::fs::write(catalog_root.join("PALETTE_DAT"), [0; 768]).unwrap();
        let mut font = vec![0; 772];
        font[..4].copy_from_slice(&1i32.to_le_bytes());
        std::fs::write(catalog_root.join("SYSTEM_FNT"), font).unwrap();
        std::fs::write(
            catalog_root.join("INDEX"),
            "1 768 PALETTE_DAT\n2 772 SYSTEM_FNT\n",
        )
        .unwrap();
        let paths = Paths {
            data: dir.path().join("saves"),
            config: dir.path().join("config"),
            cache: dir.path().join("cache"),
            legacy: dir.path().join("legacy"),
        };
        let pack = serde_json::from_value(serde_json::json!({
            "items": [
                {"id":"base:forward_guns","name":"Guns","price":0,"legacy":0},
                {"id":"base:empty","name":"Depleted","price":10,"special":true,"legacy":1},
                {"id":"base:fixture","name":"Fixture special","price":40,"special":true,"legacy":2},
                {"id":"base:energy","name":"Energy","price":0,"max_count":100,"legacy":16}
            ],
            "missions":[{"id":"base:sector_1_wave_1","name":"UI fixture","duration":100}]
        }))
        .unwrap();
        let mut registry = Registry::default();
        registry.apply(pack, "base").unwrap();
        let host = Host::new(
            Catalog::open(catalog_root).unwrap(),
            registry,
            paths,
            dir.path().join("mods"),
            false,
        )
        .unwrap();
        (dir, host)
    }
    fn game_input_fixture() -> (tempfile::TempDir, Host) {
        let (dir, mut host) = ui_fixture();
        let pack = serde_json::from_value(serde_json::json!({
            "weapons": [{"id":"base:input_bomb","name":"Input bomb","damage":1,"speed":2,"cooldown":1,"behavior":"straight","target":"all"}],
            "items": [
                {"id":"base:cycle_a","name":"Special A","price":1,"special":true},
                {"id":"base:cycle_b","name":"Special B","price":1,"special":true},
                {"id":"base:mega_bomb","name":"Bomb","price":1,"max_count":5,"consumable":true,"weapon":"base:input_bomb"}
            ]
        })).unwrap();
        host.active.registry.apply(pack, "base").unwrap();
        host.pilot.inventory = [
            ("base:energy".into(), 100),
            ("base:cycle_a".into(), 1),
            ("base:cycle_b".into(), 1),
            ("base:mega_bomb".into(), 3),
        ]
        .into();
        host.pilot.selected = Some("base:cycle_a".into());
        host.world =
            Some(World::new(&host.pilot.mission, &host.pilot, &host.active.registry).unwrap());
        host.screen = Screen::Game;
        (dir, host)
    }
    #[test]
    fn desktop_action_pulses_accept_consecutive_real_taps() {
        let (_dir, mut host) = game_input_fixture();
        let tap = Input {
            cycle: true,
            bomb: true,
            ..Input::default()
        };
        host.update(tap, 43_000_000).unwrap();
        let world = host.world.as_ref().unwrap();
        assert_eq!(world.tick, 1);
        assert_eq!(world.player.selected, Some("base:cycle_b".into()));
        assert_eq!(world.player.inventory[&"base:mega_bomb".into()], 2);
        host.update(tap, 43_000_000).unwrap();
        let world = host.world.as_ref().unwrap();
        assert_eq!(world.tick, 2);
        assert_eq!(world.player.selected, Some("base:cycle_a".into()));
        assert_eq!(world.player.inventory[&"base:mega_bomb".into()], 1);
        assert_eq!(world.projectiles.len(), 2);
    }
    #[test]
    fn desktop_action_pulses_wait_for_a_step_and_are_delivered_once() {
        let (_dir, mut host) = game_input_fixture();
        host.update(
            Input {
                cycle: true,
                bomb: true,
                ..Input::default()
            },
            0,
        )
        .unwrap();
        let world = host.world.as_ref().unwrap();
        assert_eq!(world.tick, 0);
        assert_eq!(world.player.selected, Some("base:cycle_a".into()));
        assert_eq!(world.player.inventory[&"base:mega_bomb".into()], 3);
        assert!(host.queued_cycle && host.queued_bomb);
        host.update(Input::default(), 129_000_000).unwrap();
        let world = host.world.as_ref().unwrap();
        assert_eq!(world.tick, 3);
        assert_eq!(world.player.selected, Some("base:cycle_b".into()));
        assert_eq!(world.player.inventory[&"base:mega_bomb".into()], 2);
        assert_eq!(world.projectiles.len(), 1);
        assert!(!host.queued_cycle && !host.queued_bomb);
        host.update(Input::default(), 43_000_000).unwrap();
        assert_eq!(
            host.world.as_ref().unwrap().player.inventory[&"base:mega_bomb".into()],
            2
        );
    }
    #[test]
    fn direct_simulation_still_debounces_held_cycle_and_bomb_buttons() {
        let (_dir, mut host) = game_input_fixture();
        let world = host.world.as_mut().unwrap();
        let held = Input {
            cycle: true,
            bomb: true,
            ..Input::default()
        };
        for _ in 0..2 {
            world
                .step(held, &host.active.registry, &mut host.active.scripts)
                .unwrap();
        }
        assert_eq!(world.player.selected, Some("base:cycle_b".into()));
        assert_eq!(world.player.inventory[&"base:mega_bomb".into()], 2);
        world
            .step(
                Input::default(),
                &host.active.registry,
                &mut host.active.scripts,
            )
            .unwrap();
        world
            .step(held, &host.active.registry, &mut host.active.scripts)
            .unwrap();
        assert_eq!(world.player.selected, Some("base:cycle_a".into()));
        assert_eq!(world.player.inventory[&"base:mega_bomb".into()], 1);
    }
    fn install_dependency_fixture(host: &mut Host) {
        for (id, dependencies) in [
            ("dependency", ""),
            ("dependent", "[dependencies]\ndependency = \"^1.0\"\n"),
        ] {
            let root = host.mods_root.join(id);
            std::fs::create_dir_all(&root).unwrap();
            std::fs::write(root.join("mod.toml"), format!("id = \"{id}\"\nname = \"{id}\"\nversion = \"1.0.0\"\napi_version = 1\n{dependencies}")).unwrap();
            std::fs::write(root.join("content.json"), "{}").unwrap();
        }
        host.discovery = modding::discover(&host.mods_root);
        assert!(host.discovery.errors.is_empty());
    }
    #[test]
    fn main_and_hangar_expose_all_actions_without_scrolling_and_share_mouse_mapping() {
        let (_dir, mut host) = ui_fixture();
        assert_eq!(
            host.rows(),
            [
                "Return to hangar",
                "New pilot",
                "Load / import pilot",
                "Options",
                "Mods",
                "Help / credits",
                "Watch intro",
                "Quit"
            ]
        );
        for row in 0..host.rows().len() {
            assert_eq!(
                menu_row_at(
                    Screen::Main,
                    7,
                    host.rows().len(),
                    200,
                    47 + row as i32 * 16
                ),
                Some(row)
            );
        }
        assert_eq!(menu_row_at(Screen::Main, 0, 8, 40, 50), None);
        host.activate().unwrap();
        assert!(host.screen == Screen::Hangar);
        assert_eq!(host.rows()[4], "Save pilot");
        assert_eq!(host.rows().len(), 7);
        host.selected = 2;
        host.activate().unwrap();
        assert!(host.screen == Screen::Shop);
        host.back().unwrap();
        assert!(host.screen == Screen::Hangar);
        host.selected = 1;
        host.activate().unwrap();
        assert!(host.screen == Screen::Missions);
        host.back().unwrap();
        assert!(host.screen == Screen::Hangar);
        host.selected = 6;
        host.activate().unwrap();
        assert!(host.screen == Screen::Main);
    }
    #[test]
    fn registration_requires_identity_preserves_existing_slots_and_cancels_without_writes() {
        let (_dir, mut host) = ui_fixture();
        host.pilot.save(&host.paths.save_path(0)).unwrap();
        let original = std::fs::read(host.paths.save_path(0)).unwrap();
        let pilot_before = serde_json::to_value(&host.pilot).unwrap();
        host.selected = 1;
        host.activate().unwrap();
        assert!(host.screen == Screen::PilotForm);
        assert!(
            host.commit_pilot_form()
                .unwrap_err()
                .to_string()
                .contains("name")
        );
        host.type_pilot_text("Aria");
        assert!(host.pilot_field_key(Keycode::Return));
        host.type_pilot_text("ACE");
        host.back().unwrap();
        assert!(host.screen == Screen::Main);
        assert_eq!(serde_json::to_value(&host.pilot).unwrap(), pilot_before);
        assert_eq!(host.slots(), vec![0]);
        host.begin_pilot_form(true).unwrap();
        host.type_pilot_text("Aria");
        host.pilot_field_key(Keycode::Return);
        host.type_pilot_text("ACE");
        host.pilot_field_key(Keycode::Return);
        assert_eq!(host.selected, 4);
        host.selected = 3;
        host.adjust(-1);
        assert_eq!(host.pilot_form.as_ref().unwrap().difficulty, 1);
        assert_eq!(host.config.difficulty, 2);
        host.selected = 4;
        host.activate().unwrap();
        assert!(host.screen == Screen::Hangar);
        assert_eq!(host.slot, 1);
        assert_eq!(host.pilot.name, "Aria");
        assert_eq!(host.pilot.callsign, "ACE");
        assert_eq!(host.pilot.credits, 10_000);
        assert_eq!(host.pilot.inventory[&ContentId::from("base:energy")], 75);
        assert_eq!(host.config.difficulty, 1);
        assert_eq!(
            host.pilot.legacy_progress.as_ref().unwrap().difficulties,
            [1, 1, 1, 2]
        );
        let saved = Pilot::load(&host.paths.save_path(1), &host.active.registry, &[]).unwrap();
        assert_eq!(saved.callsign, "ACE");
        assert_eq!(std::fs::read(host.paths.save_path(0)).unwrap(), original);
        host.go(Screen::Pilots);
        assert!(host.rows()[3].contains("ACE / Aria"));
    }
    #[test]
    fn pilot_id_edit_has_bounded_text_and_saves_only_after_accepting() {
        let (_dir, mut host) = ui_fixture();
        host.pilot.save(&host.paths.save_path(0)).unwrap();
        let before = std::fs::read(host.paths.save_path(0)).unwrap();
        host.hangar();
        host.selected = 5;
        host.activate().unwrap();
        host.type_pilot_text("ABCDEFGHIJKLMNOPQRSTUVWXYZ\n");
        assert_eq!(host.pilot_form.as_ref().unwrap().name.len(), 20);
        host.pilot_field_key(Keycode::Backspace);
        assert_eq!(host.pilot_form.as_ref().unwrap().name.len(), 19);
        host.pilot_field_key(Keycode::Return);
        host.type_pilot_text("abcdefghijklmnop");
        assert_eq!(host.pilot_form.as_ref().unwrap().callsign.len(), 12);
        host.pilot_field_key(Keycode::Return);
        host.selected = 2;
        host.activate().unwrap();
        assert_eq!(std::fs::read(host.paths.save_path(0)).unwrap(), before);
        host.selected = 3;
        host.activate().unwrap();
        assert!(host.screen == Screen::Hangar);
        assert_eq!(
            host.pilot.legacy_progress.as_ref().unwrap().portrait,
            0x10119
        );
        assert_eq!(host.pilot.name, "ABCDEFGHIJKLMNOPQRS");
        assert_eq!(host.pilot.callsign, "abcdefghijkl");
        assert_ne!(std::fs::read(host.paths.save_path(0)).unwrap(), before);
        assert_eq!(host.slots(), vec![0]);
    }
    #[test]
    fn pilot_id_editor_maps_native_portraits_and_preserves_unchanged_representations() {
        for (index, native) in [0x10116, 0x10119, 0x10117, 0x10118].into_iter().enumerate() {
            for representation in [native, index as i32] {
                let (_dir, mut host) = ui_fixture();
                host.pilot.legacy_progress = Some(crate::persistence::LegacyProgress {
                    portrait: representation,
                    sector: 0,
                    waves: [0; 3],
                    difficulties: [2; 4],
                    training: false,
                    training_completed: true,
                });
                host.pilot.save(&host.paths.save_path(0)).unwrap();
                assert_eq!(portrait_index(representation), index);
                assert_eq!(portrait_asset_id(index), native);
                host.hangar();
                host.begin_pilot_form(false).unwrap();
                assert_eq!(host.pilot_form.as_ref().unwrap().portrait, index);
                host.commit_pilot_form().unwrap();
                assert_eq!(
                    host.pilot.legacy_progress.as_ref().unwrap().portrait,
                    representation
                );
                let saved =
                    Pilot::load(&host.paths.save_path(0), &host.active.registry, &[]).unwrap();
                assert_eq!(saved.legacy_progress.unwrap().portrait, representation);
            }
        }
    }
    #[test]
    fn intentional_save_creates_current_slot_and_blocks_incompatible_existing_save() {
        let (_dir, mut host) = ui_fixture();
        host.hangar();
        host.pilot.callsign = "ACE".into();
        host.pilot.credits = 4567;
        host.active.scripts.states.insert(
            "fixture:behavior.rhai".into(),
            serde_json::json!({"count":5}),
        );
        host.selected = 4;
        host.activate().unwrap();
        assert!(host.screen == Screen::Hangar);
        assert!(host.message.contains("Saved ACE"));
        let saved = Pilot::load(&host.paths.save_path(0), &host.active.registry, &[]).unwrap();
        assert_eq!(saved.credits, 4567);
        assert_eq!(saved.script_state["fixture:behavior.rhai"]["count"], 5);
        let mut incompatible = saved;
        incompatible.mods.push(modding::ModPin {
            id: "missing".into(),
            version: "1.0.0".into(),
            hash: "required".into(),
        });
        incompatible.save(&host.paths.save_path(0)).unwrap();
        let before = std::fs::read(host.paths.save_path(0)).unwrap();
        let pilot_before = serde_json::to_value(&host.pilot).unwrap();
        assert!(
            host.activate()
                .unwrap_err()
                .to_string()
                .contains("Existing pilot slot")
        );
        assert_eq!(std::fs::read(host.paths.save_path(0)).unwrap(), before);
        assert_eq!(serde_json::to_value(&host.pilot).unwrap(), pilot_before);
    }
    #[test]
    fn failed_save_keeps_pilot_and_pause_save_retains_hangar_script_snapshot() {
        let (_dir, mut host) = ui_fixture();
        host.pilot.script_state.insert(
            "fixture:behavior.rhai".into(),
            serde_json::json!({"count":2}),
        );
        host.world =
            Some(World::new(&host.pilot.mission, &host.pilot, &host.active.registry).unwrap());
        host.world.as_mut().unwrap().player.credits = 999_999;
        host.active.scripts.states.insert(
            "fixture:behavior.rhai".into(),
            serde_json::json!({"count":999}),
        );
        host.go(Screen::Pause);
        host.selected = 3;
        host.activate().unwrap();
        let saved = Pilot::load(&host.paths.save_path(0), &host.active.registry, &[]).unwrap();
        assert_eq!(saved.credits, host.pilot.credits);
        assert_ne!(saved.credits, host.world.as_ref().unwrap().player.credits);
        assert_eq!(saved.script_state["fixture:behavior.rhai"]["count"], 2);
        assert!(host.message.contains("hangar state only"));
        host.world = None;
        host.paths.data = host.paths.data.join("blocked");
        std::fs::write(&host.paths.data, "not a directory").unwrap();
        let before = serde_json::to_value(&host.pilot).unwrap();
        assert!(host.save().is_err());
        assert_eq!(serde_json::to_value(&host.pilot).unwrap(), before);
    }
    #[test]
    fn settings_have_a_visible_save_action_and_preserve_return_context() {
        let (_dir, mut host) = ui_fixture();
        host.previous = Screen::Main;
        host.go(Screen::Options);
        assert_eq!(host.rows()[13], "Save settings");
        host.config.fx_volume = 127;
        host.selected = 13;
        host.activate().unwrap();
        assert!(host.screen == Screen::Options);
        assert_eq!(Config::load(&host.paths).unwrap().fx_volume, 127);
        assert_eq!(host.message, "Settings saved");
        host.selected = 14;
        host.activate().unwrap();
        assert!(host.screen == Screen::Main);
    }
    #[test]
    fn diagnostics_preserve_options_return_target_and_do_not_create_binding_loops() {
        let (_dir, mut host) = ui_fixture();
        for origin in [Screen::Main, Screen::Pause] {
            host.previous = origin;
            host.go(Screen::Options);
            host.open_diagnostics();
            host.back().unwrap();
            assert!(host.screen == Screen::Options);
            host.back().unwrap();
            assert!(host.screen == origin);
            host.go(Screen::Options);
            host.selected = 11;
            host.activate().unwrap();
            host.open_diagnostics();
            host.back().unwrap();
            assert!(host.screen == Screen::Bindings);
            host.back().unwrap();
            assert!(host.screen == Screen::Options);
            host.back().unwrap();
            assert!(host.screen == origin);
        }
    }
    #[test]
    fn inventory_actions_follow_visible_owned_rows() {
        let (_dir, mut host) = ui_fixture();
        host.pilot.inventory.insert("base:empty".into(), 0);
        host.pilot.inventory.insert("base:fixture".into(), 1);
        host.pilot.inventory.insert("base:missing".into(), 1);
        host.go(Screen::Inventory);
        assert_eq!(
            host.inventory_ids(),
            vec![
                ContentId::from("base:forward_guns"),
                "base:fixture".into(),
                "base:energy".into()
            ]
        );
        assert!(host.rows()[1].starts_with("Fixture special"));
        host.selected = 1;
        let before = host.pilot.inventory.clone();
        assert!(host.activate().is_err()); // Unavailable saved equipment still blocks edits.
        assert_eq!(host.pilot.inventory, before);
        host.pilot
            .inventory
            .remove(&ContentId::from("base:missing"));
        host.activate().unwrap();
        assert_eq!(host.pilot.selected, Some("base:fixture".into()));
        host.sell_inventory().unwrap();
        assert_eq!(host.pilot.credits, 20);
        assert_eq!(host.pilot.selected, None);
        assert!(host.rows()[1].starts_with("Energy"));
    }
    #[test]
    fn volume_options_reach_mute_and_maximum_in_both_directions() {
        let mut config = Config::default();
        for expected in [101, 117, 127, 0] {
            assert!(adjust_option(&mut config, 5, 1));
            assert_eq!(config.music_volume, expected);
        }
        for expected in [69, 53, 37, 21, 5, 0, 127] {
            assert!(adjust_option(&mut config, 6, -1));
            assert_eq!(config.fx_volume, expected);
        }
        config.scale = 1;
        adjust_option(&mut config, 0, -1);
        assert_eq!(config.scale, 4);
        config.fx_channels = 1;
        adjust_option(&mut config, 12, -1);
        assert_eq!(config.fx_channels, 8);
        assert!(!adjust_option(&mut config, 11, 1)); // Bindings opens a separate screen.
    }
    #[test]
    fn shop_sale_is_accessible_and_failed_save_keeps_pilot_unchanged() {
        let (_dir, mut host) = ui_fixture();
        host.pilot.inventory.insert("base:fixture".into(), 1);
        host.go(Screen::Shop);
        host.activate().unwrap(); // Visible buy/sell mode entry.
        assert!(host.shop_selling);
        assert_eq!(
            host.shop_ids(),
            vec![ContentId::from("base:fixture"), "base:energy".into()]
        );
        host.selected = 1;
        std::fs::write(&host.paths.data, "blocked save directory").unwrap();
        let before = serde_json::to_value(&host.pilot).unwrap();
        assert!(host.activate().is_err());
        assert_eq!(serde_json::to_value(&host.pilot).unwrap(), before);
        std::fs::remove_file(&host.paths.data).unwrap();
        host.activate().unwrap();
        assert_eq!(host.pilot.credits, 20);
        assert_eq!(host.shop_ids(), vec![ContentId::from("base:energy")]);
    }
    #[test]
    fn legacy_import_uses_a_separate_free_slot_and_retains_original_files() {
        let (_dir, mut host) = ui_fixture();
        host.pilot.callsign = "EXISTING".into();
        host.pilot.save(&host.paths.save_path(0)).unwrap();
        let existing = std::fs::read(host.paths.save_path(0)).unwrap();
        let mut header = vec![0u8; 88];
        header[20..28].copy_from_slice(b"IMPORTED");
        header[36..40].copy_from_slice(&1234i32.to_le_bytes());
        header[40..44].copy_from_slice(&(-1i32).to_le_bytes());
        let key = b"CASTLE";
        let mut index = 25 % key.len();
        let mut previous = key[index];
        let source = header
            .into_iter()
            .map(|clear| {
                let byte = clear.wrapping_add(key[index]).wrapping_add(previous);
                previous = byte;
                index = (index + 1) % key.len();
                byte
            })
            .collect::<Vec<_>>();
        std::fs::create_dir(&host.paths.legacy).unwrap();
        let path = host.paths.legacy.join("CHAR0007.FIL");
        std::fs::write(&path, &source).unwrap();
        host.import_pilot(&path).unwrap();
        assert_eq!(host.slot, 1);
        assert_eq!(host.pilot.callsign, "IMPORTED");
        assert_eq!(host.pilot.credits, 1234);
        assert_eq!(std::fs::read(path).unwrap(), source);
        assert_eq!(std::fs::read(host.paths.save_path(0)).unwrap(), existing);
        assert_eq!(
            Pilot::load(&host.paths.save_path(1), &host.active.registry, &[])
                .unwrap()
                .callsign,
            "IMPORTED"
        );
        assert_eq!(host.slots(), vec![0, 1]);
    }
    #[test]
    fn selecting_a_mod_selects_its_installed_dependency_without_applying() {
        let (_dir, mut host) = ui_fixture();
        install_dependency_fixture(&mut host);
        host.go(Screen::Mods);
        host.selected = host
            .mod_ids()
            .iter()
            .position(|id| id == "dependent")
            .unwrap()
            + 2;
        host.activate().unwrap();
        assert_eq!(host.pending, vec!["dependency", "dependent"]);
        assert!(host.active.pins.is_empty());
        assert!(host.config.enabled_mods.is_empty());
        assert!(
            dependency_lines(
                &host.discovery.mods["dependent"].manifest,
                &host.discovery,
                &host.pending
            )[0]
            .contains("installed 1.0.0 enabled")
        );
    }
    #[test]
    fn disabling_a_required_mod_needs_confirmation_and_back_preserves_selection() {
        let (_dir, mut host) = ui_fixture();
        install_dependency_fixture(&mut host);
        host.pending = vec!["dependency".into(), "dependent".into()];
        host.active = ActiveMods::build(
            &host.base,
            &host.discovery,
            &host.pending,
            Some(&host.catalog),
        )
        .unwrap();
        host.pilot.mods = host.active.pins.clone();
        host.config.enabled_mods = host.pending.clone();
        host.world =
            Some(World::new(&host.pilot.mission, &host.pilot, &host.active.registry).unwrap());
        let active_pins = host.active.pins.clone();
        host.go(Screen::Mods);
        host.selected = 2;
        host.activate().unwrap();
        assert!(host.screen == Screen::ConfirmDisable);
        assert_eq!(host.selected, 1); // Cancel is initially selected.
        assert_eq!(host.pending, vec!["dependency", "dependent"]);
        assert_eq!(host.pending_disable.as_ref().unwrap().removed.len(), 2);
        host.back().unwrap();
        assert_eq!(host.pending, vec!["dependency", "dependent"]);
        host.selected = 2;
        host.activate().unwrap();
        host.activate().unwrap(); // The selected Cancel action also preserves both packages.
        assert_eq!(host.pending, vec!["dependency", "dependent"]);
        host.selected = 2;
        host.activate().unwrap();
        host.selected = 0;
        host.activate().unwrap();
        assert!(host.pending.is_empty());
        assert_eq!(host.active.pins, active_pins); // Mission content stays active until main menu.
        assert_eq!(host.config.enabled_mods, vec!["dependency", "dependent"]);
        assert!(host.world.is_some());
        assert!(host.pending_disable.is_none());
        assert!(host.screen == Screen::Mods);
    }
    #[test]
    fn missing_dependency_selection_fails_without_changing_pending_mods() {
        let (_dir, mut host) = ui_fixture();
        install_dependency_fixture(&mut host);
        host.discovery.mods.remove("dependency");
        host.go(Screen::Mods);
        host.selected = 2;
        let error = host.activate().unwrap_err().to_string();
        assert!(error.contains("dependency"));
        assert!(host.pending.is_empty());
        assert!(host.active.pins.is_empty());
        assert!(host.screen == Screen::Mods);
    }
    #[test]
    fn shop_information_uses_registry_roles_targets_prices_and_trigger_cadence() {
        let (_dir, mut host) = ui_fixture();
        let weapon: crate::content::WeaponDef = serde_json::from_value(serde_json::json!({
            "id":"base:fixture_shot","name":"Fixture projectile","damage":4,"speed":8,"cooldown":9,"behavior":"homing","target":"ground","script":"behavior.rhai"
        })).unwrap();
        host.active
            .registry
            .weapons
            .insert(weapon.id.clone(), weapon);
        let item = host
            .active
            .registry
            .items
            .get_mut(&ContentId::from("base:fixture"))
            .unwrap();
        item.weapon = Some("base:fixture_shot".into());
        item.description = "A controlled test weapon.".into();
        host.pilot.credits = 40;
        let before = serde_json::to_value(&host.pilot).unwrap();
        let info = host.shop_info(&"base:fixture".into()).unwrap();
        assert_eq!(info.kind, "SELECTABLE");
        assert_eq!((info.price, info.resale, info.owned), (40, 20, 0));
        assert_eq!(info.description, "A controlled test weapon.");
        assert_eq!(
            info.stats,
            vec![
                "Targets: ground",
                "Damage 4 / hit",
                "Cycle 9 ticks (2.59/s)",
                "Homing / scripted"
            ]
        );
        assert_eq!(info.buy, "Ready");
        assert!(info.sell.contains("not owned"));
        assert_eq!(serde_json::to_value(&host.pilot).unwrap(), before); // Eligibility only previews an edit.
        host.active
            .registry
            .items
            .get_mut(&ContentId::from("base:fixture"))
            .unwrap()
            .special = false;
        assert_eq!(
            host.shop_info(&"base:fixture".into()).unwrap().kind,
            "ALWAYS EQUIPPED"
        );
        host.active
            .registry
            .items
            .get_mut(&ContentId::from("base:fixture"))
            .unwrap()
            .consumable = true;
        assert_eq!(
            host.shop_info(&"base:fixture".into()).unwrap().kind,
            "CONSUMABLE"
        );
        host.active
            .registry
            .weapons
            .get_mut(&ContentId::from("base:fixture_shot"))
            .unwrap()
            .legacy = Some(10);
        assert_eq!(
            host.shop_info(&"base:fixture".into()).unwrap().stats[1],
            "Damage 1; drains guns"
        );
    }
    #[test]
    fn shop_reports_super_shield_modules_separately_from_active_charge() {
        let (_dir, mut host) = ui_fixture();
        let item: crate::content::ItemDef = serde_json::from_value(serde_json::json!({
            "id":"base:super_shield","name":"Super Shield","price":1000,"initial_count":100,"max_count":100,"legacy":15
        })).unwrap();
        host.active.registry.items.insert(item.id.clone(), item);
        host.pilot.inventory.insert("base:super_shield".into(), 40);
        host.pilot.super_shield_reserves = vec![100, 75];
        host.pilot.credits = 1000;
        let info = host.shop_info(&"base:super_shield".into()).unwrap();
        assert_eq!(info.owned, 3);
        assert_eq!(info.slots, 5);
        assert_eq!(info.stats[0], "Modules 3 / 5");
        assert_eq!(info.stats[1], "Active charge 40");
        assert_eq!(info.buy, "Ready");
        assert!(info.sell.contains("fully charged"));
        host.pilot.inventory.insert("base:super_shield".into(), 0);
        assert!(
            host.inventory_ids()
                .contains(&ContentId::from("base:super_shield"))
        );
        assert_eq!(
            host.shop_info(&"base:super_shield".into()).unwrap().owned,
            3
        );
    }
    #[test]
    fn shop_detail_navigation_preserves_item_mode_and_blocks_preview_purchase_clicks() {
        let (_dir, mut host) = ui_fixture();
        host.pilot.inventory.insert("base:fixture".into(), 1);
        host.go(Screen::Shop);
        host.activate().unwrap();
        host.selected = 1;
        let before = serde_json::to_value(&host.pilot).unwrap();
        host.open_shop_details();
        assert!(host.screen == Screen::ShopDetails);
        assert!(host.rows().iter().any(|line| line.contains("resale")));
        host.back().unwrap();
        assert!(host.screen == Screen::Shop);
        assert!(host.shop_selling);
        assert_eq!(host.selected, 1);
        assert_eq!(serde_json::to_value(&host.pilot).unwrap(), before);
        assert_eq!(menu_row_at(Screen::Shop, 1, 20, 170, 60), None);
        assert_eq!(menu_row_at(Screen::Shop, 1, 20, 159, 60), Some(1));
        assert_eq!(menu_row_at(Screen::Shop, 1, 20, 40, 154), None);
        assert_eq!(menu_row_at(Screen::Main, 1, 8, 200, 60), Some(1));
    }
    #[test]
    #[ignore = "requires original catalog; writes ignored menu usability captures"]
    fn classic_main_hangar_registration_and_explicit_save_visual_capture() {
        let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR"));
        let catalog = Catalog::open(root.parent().unwrap().join("data")).unwrap();
        let registry = Registry::base(&catalog).unwrap();
        let temp = tempfile::tempdir().unwrap();
        let paths = Paths {
            data: temp.path().join("saves"),
            config: temp.path().join("config"),
            cache: temp.path().join("cache"),
            legacy: temp.path().join("legacy"),
        };
        let mut host =
            Host::new(catalog, registry, paths, temp.path().join("mods"), false).unwrap();
        host.config.scale = 4;
        let output = root.parent().unwrap().join(".reference/ui-menu");
        std::fs::create_dir_all(&output).unwrap();
        let capture = |host: &mut Host, name: &str| {
            let before = serde_json::to_value(&host.pilot).unwrap();
            let canvas = host.draw().unwrap();
            image::save_buffer(
                output.join(format!("{name}.png")),
                &canvas.rgba(&host.palette, false),
                canvas.image.width as u32,
                canvas.image.height as u32,
                image::ColorType::Rgba8,
            )
            .unwrap();
            assert_eq!(serde_json::to_value(&host.pilot).unwrap(), before);
        };
        for (selected, name) in [
            (0, "main-classic"),
            (3, "main-options-selected"),
            (7, "main-quit-selected"),
        ] {
            host.selected = selected;
            let canvas = host.draw().unwrap();
            assert_eq!(
                canvas.image.pixels[(43 + selected * 16) * 4 * canvas.image.width + 164 * 4],
                50
            );
            capture(&mut host, name);
        }
        host.selected = 1;
        host.activate().unwrap();
        host.type_pilot_text("Aria");
        host.pilot_field_key(Keycode::Return);
        host.type_pilot_text("ACE");
        capture(&mut host, "register-pilot");
        host.pilot_field_key(Keycode::Return);
        host.activate().unwrap();
        host.message.clear();
        host.selected = 4;
        capture(&mut host, "hangar-save-visible");
        host.activate().unwrap();
        assert!(host.paths.save_path(host.slot).exists());
        capture(&mut host, "save-confirmation");
        host.selected = 5;
        host.activate().unwrap();
        capture(&mut host, "edit-pilot-id");
        host.back().unwrap();
        host.go(Screen::Pilots);
        host.message.clear();
        assert!(host.rows()[2].contains("ACE / Aria"));
        capture(&mut host, "pilot-load-import");
        host.previous = Screen::Main;
        host.go(Screen::Options);
        host.message.clear();
        host.selected = 13;
        capture(&mut host, "settings-save");
        host.start(host.pilot.mission.clone()).unwrap();
        host.go(Screen::Pause);
        host.message.clear();
        host.selected = 3;
        capture(&mut host, "pause-save-hangar-state");
    }
    #[test]
    #[ignore = "requires local original catalog and supplied mod PNGs; writes ignored shop captures"]
    fn shop_original_and_mod_art_details_capture_without_editing_pilots() {
        let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR"));
        let catalog_root = std::env::var_os("RAPTOR_TEST_DATA")
            .map(PathBuf::from)
            .unwrap_or_else(|| root.parent().unwrap().join("data"));
        let catalog = Catalog::open(catalog_root).unwrap();
        let registry = Registry::base(&catalog).unwrap();
        let temp = tempfile::tempdir().unwrap();
        let paths = Paths {
            data: temp.path().join("saves"),
            config: temp.path().join("config"),
            cache: temp.path().join("cache"),
            legacy: temp.path().join("legacy"),
        };
        let mut host = Host::new(catalog, registry, paths, root.join("mods"), true).unwrap();
        let enabled = [
            "pulse_cannon".into(),
            "seeker_swarm".into(),
            "ion_lance".into(),
        ];
        host.active =
            ActiveMods::build(&host.base, &host.discovery, &enabled, Some(&host.catalog)).unwrap();
        host.pilot.credits = 4_000_000;
        host.config.scale = 4;
        let output = root.parent().unwrap().join(".reference/ui-shop");
        std::fs::create_dir_all(&output).unwrap();
        let capture = |host: &mut Host, name: &str| {
            host.message.clear();
            let before = serde_json::to_value(&host.pilot).unwrap();
            let canvas = host.draw().unwrap();
            let rgba = canvas.rgba(&host.palette, false);
            image::save_buffer(
                output.join(format!("{name}.png")),
                &rgba,
                canvas.image.width as u32,
                canvas.image.height as u32,
                image::ColorType::Rgba8,
            )
            .unwrap();
            assert_eq!(serde_json::to_value(&host.pilot).unwrap(), before);
            assert!(!host.paths.data.exists());
            rgba
        };
        for (legacy, name) in [
            (1, "original-plasma"),
            (5, "original-air-missile"),
            (9, "original-ground-bomb"),
        ] {
            let id = host
                .active
                .registry
                .items
                .values()
                .find(|item| item.legacy == Some(legacy))
                .unwrap()
                .id
                .clone();
            host.go(Screen::Shop);
            host.selected = host
                .shop_ids()
                .iter()
                .position(|candidate| candidate == &id)
                .unwrap()
                + 1;
            let info = host.shop_info(&id).unwrap();
            assert!(!info.description.is_empty());
            assert_eq!(info.buy, "Ready");
            capture(&mut host, name);
        }
        for namespace in ["pulse_cannon", "seeker_swarm", "ion_lance"] {
            let id = ContentId::from(format!("{namespace}:equipment").as_str());
            host.go(Screen::Shop);
            host.selected = host
                .shop_ids()
                .iter()
                .position(|candidate| candidate == &id)
                .unwrap()
                + 1;
            assert!(
                host.active.registry.items[&id]
                    .art
                    .as_ref()
                    .unwrap()
                    .hd_png
                    .is_some()
            );
            assert!(!host.shop_info(&id).unwrap().description.is_empty());
            host.config.hd_mode = false;
            let sd = capture(&mut host, &format!("{namespace}-sd"));
            host.config.hd_mode = true;
            let hd = capture(&mut host, &format!("{namespace}-hd"));
            assert_ne!(
                sd, hd,
                "supplied SD and HD equipment previews should differ"
            );
            host.open_shop_details();
            capture(&mut host, &format!("{namespace}-full-details"));
        }
        let id = ContentId::from("base:super_shield");
        host.pilot.inventory.insert(id.clone(), 40);
        host.pilot.super_shield_reserves = vec![100, 100];
        host.go(Screen::Shop);
        host.shop_selling = true;
        host.selected = host
            .shop_ids()
            .iter()
            .position(|candidate| candidate == &id)
            .unwrap()
            + 1;
        assert_eq!(host.shop_info(&id).unwrap().owned, 3);
        assert!(host.shop_info(&id).unwrap().sell.contains("fully charged"));
        capture(&mut host, "super-shield-partial-resale");
        println!("Shop captures: {}", output.display());
    }
    #[test]
    fn disabling_a_single_unneeded_mod_toggles_without_confirmation() {
        let (_dir, mut host) = ui_fixture();
        install_dependency_fixture(&mut host);
        host.pending = vec!["dependency".into()];
        host.go(Screen::Mods);
        host.selected = 2;
        host.activate().unwrap();
        assert!(host.pending.is_empty());
        assert!(host.pending_disable.is_none());
        assert!(host.screen == Screen::Mods);
        assert!(host.active.pins.is_empty());
    }
    #[test]
    fn disabling_a_dependent_lists_its_unused_dependency_before_removal() {
        let (_dir, mut host) = ui_fixture();
        install_dependency_fixture(&mut host);
        host.pending = vec!["dependency".into(), "dependent".into()];
        host.go(Screen::Mods);
        host.selected = host
            .mod_ids()
            .iter()
            .position(|id| id == "dependent")
            .unwrap()
            + 2;
        host.activate().unwrap();
        assert!(host.screen == Screen::ConfirmDisable);
        let removed = &host.pending_disable.as_ref().unwrap().removed;
        assert!(removed.iter().any(|id| id == "dependency"));
        assert!(removed.iter().any(|id| id == "dependent"));
        assert_eq!(host.pending, vec!["dependency", "dependent"]);
        host.selected = 0;
        host.activate().unwrap();
        assert!(host.pending.is_empty());
    }
    #[test]
    fn hud_shield_ramp_matches_native_fixed_point_colors_and_clear_rows() {
        for scale in [1, 2, 3, 4] {
            for amount in [-1, 0, 10, 50, 100, 120] {
                let mut canvas = Canvas::new(scale);
                canvas.clear(37);
                hud_shield_bar(&mut canvas, 308, amount);
                let mut accumulator = 0_u32;
                for level in 0..100 {
                    let expected = if level < amount.clamp(0, 100) {
                        74 - (accumulator >> 16) as u16
                    } else {
                        0
                    };
                    for y in (199 - level * 2) as usize * scale..(200 - level * 2) as usize * scale
                    {
                        for x in 308 * scale..312 * scale {
                            assert_eq!(canvas.image.pixels[y * canvas.image.width + x], expected);
                        }
                    }
                    accumulator += (9 << 16) / 100;
                }
                assert_eq!(
                    canvas.image.pixels[199 * scale * canvas.image.width + 307 * scale],
                    37
                );
                assert_eq!(
                    canvas.image.pixels[198 * scale * canvas.image.width + 308 * scale],
                    37
                );
                assert_eq!(
                    canvas
                        .image
                        .pixels
                        .iter()
                        .filter(|&&p| (66..=74).contains(&p))
                        .count(),
                    amount.clamp(0, 100) as usize * 4 * scale * scale
                );
            }
        }
    }
    #[test]
    fn hud_warning_latches_follow_steps_and_ignore_repeated_render_observations() {
        let (registry, pilot) = fixture();
        let mut world = World::new(&pilot.mission, &pilot, &registry).unwrap();
        let mut state = HudState::new(&world);
        let before = world.rng.seed;
        world.player.shield = 9;
        for tick in 1..=32 {
            world.tick = tick;
            state.observe(&world, &registry);
            let snapshot = (state.blink, state.damage_flashes, state.sweep);
            for _ in 0..5 {
                state.observe(&world, &registry);
            }
            assert_eq!((state.blink, state.damage_flashes, state.sweep), snapshot);
            assert_eq!(state.blink, (tick / 8) % 2 == 0);
            assert_eq!(
                state.damage_flashes,
                if tick < 16 {
                    2
                } else if tick < 32 {
                    1
                } else {
                    0
                }
            );
        }
        assert_eq!(world.rng.seed, before);
        world.player.shield = 50;
        for tick in 33..=48 {
            world.tick = tick;
            state.observe(&world, &registry);
        }
        assert!(
            state.blink,
            "healthy shields leave the low-energy blink latch alone"
        );
    }
    #[test]
    fn hud_detector_averages_visible_boss_health_and_respects_owned_equipment() {
        let (mut registry, pilot) = fixture();
        for (id, health) in [("test:boss_a", 100), ("test:boss_b", 200)] {
            let enemy: crate::content::EnemyDef = serde_json::from_value(serde_json::json!({
                "id":id,"name":id,"health":health,"boss":true
            }))
            .unwrap();
            registry.enemies.insert(enemy.id.clone(), enemy);
        }
        let mut world = World::new(&pilot.mission, &pilot, &registry).unwrap();
        world
            .spawn(&"test:boss_a".into(), 100, -17, &registry)
            .unwrap();
        world.enemies[0].health = 50;
        assert_eq!(boss_shield_percent(&world, &registry), 0);
        world.enemies[0].y = -16;
        assert_eq!(boss_shield_percent(&world, &registry), 50);
        world
            .spawn(&"test:boss_b".into(), 100, 40, &registry)
            .unwrap();
        world.enemies[1].health = 50;
        assert_eq!(boss_shield_percent(&world, &registry), 37);
        let mut state = HudState::new(&world);
        world.tick = 1;
        state.observe(&world, &registry);
        assert_eq!(state.sweep, 0, "detector is unavailable without equipment");
        world.player.inventory.insert("base:detect".into(), 1);
        world.enemies.clear();
        world.tick = 2;
        state.observe(&world, &registry);
        assert_eq!(state.sweep, 1);
        state.observe(&world, &registry);
        assert_eq!(state.sweep, 1);
        for tick in 3..=51 {
            world.tick = tick;
            state.observe(&world, &registry);
        }
        assert_eq!(state.sweep, 0);
    }
    #[test]
    #[ignore = "requires local original catalog; writes ignored gameplay HUD captures"]
    fn hud_original_art_and_mod_icons_keep_native_slots_and_simulation_unchanged() {
        let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR"));
        let catalog = Catalog::open(root.parent().unwrap().join("data")).unwrap();
        let registry = Registry::base(&catalog).unwrap();
        let temp = tempfile::tempdir().unwrap();
        let paths = Paths {
            data: temp.path().join("saves"),
            config: temp.path().join("config"),
            cache: temp.path().join("cache"),
            legacy: temp.path().join("legacy"),
        };
        let mut host = Host::new(catalog, registry, paths, temp.path().join("mods"), true).unwrap();
        host.config.scale = 4;
        host.pilot = Pilot::demo(1, &host.active.registry).unwrap();
        let mission = host.pilot.mission.clone();
        host.start(mission).unwrap();
        let mut world = host.world.take().unwrap();
        world.player.credits = 12345678;
        world.player.shield = 50;
        let selected = host
            .active
            .registry
            .items
            .values()
            .find(|item| item.legacy == Some(5))
            .unwrap()
            .id
            .clone();
        world.player.selected = Some(selected.clone());
        world.player.super_shield_reserves = vec![31, 100];
        host.hud_state = HudState::new(&world);
        let snapshot = serde_json::to_value(&world).unwrap();
        let mut canvas = Canvas::new(4);
        canvas.clear(37);
        host.hud(&mut canvas, &world).unwrap();
        let digits: Vec<_> = (0..11)
            .map(|digit| host.catalog.sprite(0x10005 + digit).unwrap())
            .collect();
        let mut expected = Canvas::new(4);
        expected.clear(37);
        expected.blit(&nearest(&digits[10], 4), 119 * 4, 2 * 4);
        for (position, digit) in "12345678".bytes().enumerate() {
            expected.blit(
                &nearest(&digits[(digit - b'0') as usize], 4),
                (128 + position as i32 * 8) * 4,
                2 * 4,
            );
        }
        for y in 2 * 4..10 * 4 {
            for x in 119 * 4..192 * 4 {
                assert_eq!(
                    canvas.image.pixels[y * canvas.image.width + x],
                    expected.image.pixels[y * expected.image.width + x]
                );
            }
        }
        assert_eq!(serde_json::to_value(&world).unwrap(), snapshot);
        let original_icon = host.active.registry.items[&selected]
            .art
            .as_ref()
            .unwrap()
            .asset
            .unwrap();
        let native = host.catalog.sprite(original_icon).unwrap();
        for y in 0..native.height * 4 {
            for x in 0..native.width * 4 {
                let pixel = native.pixels[y / 4 * native.width + x / 4];
                assert_eq!(
                    canvas.image.pixels[(2 * 4 + y) * canvas.image.width + 286 * 4 + x],
                    if pixel == crate::assets::TRANSPARENT {
                        37
                    } else {
                        pixel
                    }
                );
            }
        }
        // Supplied SD/HD artwork uses its registry owner and fits the native
        // 18px equipment slot, rather than painting over the right shield bar.
        let mut supplied = image::RgbaImage::new(24, 24);
        let rgb = host.palette[245];
        for y in 4..20 {
            for x in 4..20 {
                supplied.put_pixel(x, y, image::Rgba([rgb[0], rgb[1], rgb[2], 255]));
            }
        }
        supplied.save(temp.path().join("equipment.png")).unwrap();
        image::imageops::resize(&supplied, 192, 192, image::imageops::FilterType::Nearest)
            .save(temp.path().join("equipment-hd.png"))
            .unwrap();
        let pack:crate::content::ContentPack = serde_json::from_value(serde_json::json!({
            "items":[{"id":"hud:equipment","name":"Supplied HUD icon","price":0,
                "art":{"png":"equipment.png","hd_png":"equipment-hd.png","logical_width":24,"logical_height":24}}]
        })).unwrap();
        host.active.registry.apply(pack, "hud").unwrap();
        host.active
            .registry
            .asset_roots
            .insert("hud".into(), temp.path().to_owned());
        for hd in [false, true] {
            host.config.hd_mode = hd;
            let mut mod_icon = Canvas::new(4);
            mod_icon.clear(37);
            host.hud_weapon(&mut mod_icon, &"hud:equipment".into())
                .unwrap();
            assert!(mod_icon.image.pixels.iter().any(|&pixel| pixel != 37));
            for (index, &pixel) in mod_icon.image.pixels.iter().enumerate() {
                if pixel != 37 {
                    assert!((286 * 4..304 * 4).contains(&(index % mod_icon.image.width)));
                    assert!((2 * 4..20 * 4).contains(&(index / mod_icon.image.width)));
                }
            }
        }
        host.config.hd_mode = false;
        host.world = Some(world.clone());
        let output = root.parent().unwrap().join(".reference/ui");
        std::fs::create_dir_all(&output).unwrap();
        let mut normal = Canvas::new(4);
        host.scene(&mut normal).unwrap();
        image::save_buffer(
            output.join("hud-full-original.png"),
            &normal.rgba(&host.palette, false),
            normal.image.width as u32,
            normal.image.height as u32,
            image::ColorType::Rgba8,
        )
        .unwrap();
        world.tick = 1;
        world.player.shield = 9;
        world.player.super_shield = 0;
        world.player.super_shield_reserves.clear();
        world
            .player
            .inventory
            .remove(&ContentId::from("base:super_shield"));
        host.hud_state.observe(&world, &host.active.registry);
        assert_eq!(host.hud_state.damage_flashes, 2);
        host.world = Some(world);
        let mut critical = Canvas::new(4);
        host.scene(&mut critical).unwrap();
        image::save_buffer(
            output.join("hud-critical-original.png"),
            &critical.rgba(&host.palette, false),
            critical.image.width as u32,
            critical.image.height as u32,
            image::ColorType::Rgba8,
        )
        .unwrap();
        assert!(!host.paths.save_path(0).exists());
    }
    #[test]
    fn failed_victory_save_can_retry_without_advancing_training_twice() {
        let (_dir, mut host) = ui_fixture();
        let mission: crate::content::MissionDef = serde_json::from_value(serde_json::json!({
            "id":"base:sector_1_wave_4", "name":"Training graduation", "duration":100,
            "legacy_map":42
        }))
        .unwrap();
        host.active
            .registry
            .missions
            .insert(mission.id.clone(), mission);
        host.pilot.mission = "base:sector_1_wave_4".into();
        host.pilot.difficulty = 0;
        host.pilot.credits = 6_000;
        host.config.difficulty = 0;
        let before = serde_json::to_value(&host.pilot).unwrap();
        let mut world =
            World::new(&host.pilot.mission, &host.pilot, &host.active.registry).unwrap();
        world.player.credits = 12_345;
        world.outcome = Outcome::Complete;
        host.world = Some(world);
        host.screen = Screen::Game;
        std::fs::write(&host.paths.data, "blocked save directory").unwrap();
        assert!(host.update(Input::default(), 43_000_000).is_err());
        assert_eq!(serde_json::to_value(&host.pilot).unwrap(), before);
        assert_eq!(host.config.difficulty, 0);
        assert_eq!(host.world.as_ref().unwrap().outcome, Outcome::Complete);
        std::fs::remove_file(&host.paths.data).unwrap();
        host.update(Input::default(), 43_000_000).unwrap();
        let saved =
            Pilot::load(&host.paths.save_path(host.slot), &host.active.registry, &[]).unwrap();
        assert_eq!(saved.mission.0, "base:sector_1_wave_1");
        assert_eq!(saved.difficulty, 1);
        assert_eq!(saved.credits, 10_000);
        assert_eq!(saved.inventory[&"base:energy".into()], 75);
        assert!(saved.legacy_progress.as_ref().unwrap().training_completed);
        assert_eq!(
            saved.completed,
            vec![ContentId::from("base:sector_1_wave_4")]
        );
        assert_eq!(host.config.difficulty, 1);
        assert!(host.screen == Screen::Results);
    }
    #[test]
    fn committed_victory_is_not_reprocessed_when_only_settings_save_fails() {
        let (_dir, mut host) = ui_fixture();
        let mut world =
            World::new(&host.pilot.mission, &host.pilot, &host.active.registry).unwrap();
        world.player.credits = 1_234;
        world.outcome = Outcome::Complete;
        host.world = Some(world);
        host.screen = Screen::Game;
        std::fs::write(&host.paths.config, "blocked settings directory").unwrap();
        host.update(Input::default(), 43_000_000).unwrap();
        assert!(host.screen == Screen::Results);
        assert!(host.message.contains("settings save failed"));
        assert_eq!(host.pilot.credits, 1_234);
        assert_eq!(host.pilot.completed.len(), 1);
        let saved =
            Pilot::load(&host.paths.save_path(host.slot), &host.active.registry, &[]).unwrap();
        assert_eq!(saved.credits, 1_234);
        let before = serde_json::to_value(&host.pilot).unwrap();
        host.update(Input::default(), 43_000_000).unwrap();
        assert_eq!(serde_json::to_value(&host.pilot).unwrap(), before);
    }
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
