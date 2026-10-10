//! Local mod discovery, dependency ordering and transactional script callbacks.
use crate::{
    assets::{Catalog, contained},
    content::{API_VERSION, ContentPack, Registry},
    simulation::LegacyRng,
};
use anyhow::{Context, Result, ensure};
use rhai::{
    AST, Dynamic, Engine, Scope,
    packages::{
        ArithmeticPackage, BasicArrayPackage, BasicFnPackage, BasicIteratorPackage,
        BasicMapPackage, BasicMathPackage, BasicStringPackage, BitFieldPackage, LogicPackage,
        MoreStringPackage, Package,
    },
};
use schemars::JsonSchema;
use semver::{Version, VersionReq};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    collections::{BTreeMap, BTreeSet},
    fs,
    path::{Path, PathBuf},
};
#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct Manifest {
    /// Unique lowercase namespace; `base` is reserved for the original game.
    pub id: String,
    /// Display name shown in the in-game manager.
    pub name: String,
    /// Semantic package version, saved together with a SHA-256 content hash.
    pub version: String,
    /// Exact supported content/script API major version.
    pub api_version: u32,
    #[serde(default)]
    pub description: String,
    /// Required mod IDs mapped to semantic version requirements.
    #[serde(default)]
    pub dependencies: BTreeMap<String, String>,
    /// IDs which cannot be enabled at the same time as this package.
    #[serde(default)]
    pub conflicts: Vec<String>,
    /// Relative path to the JSON content pack. Defaults to `content.json`.
    #[serde(default = "content_file")]
    pub content: String,
    /// Relative paths to every Rhai source referenced by this content pack.
    #[serde(default)]
    pub scripts: Vec<String>,
}
fn content_file() -> String {
    "content.json".into()
}
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ModPin {
    pub id: String,
    pub version: String,
    pub hash: String,
}
#[derive(Debug, Clone)]
pub struct InstalledMod {
    pub root: PathBuf,
    pub manifest: Manifest,
    pub hash: String,
}
#[derive(Debug, Default)]
pub struct Discovery {
    pub mods: BTreeMap<String, InstalledMod>,
    pub errors: Vec<String>,
    /// Directory inventoried by this snapshot, used to reject new duplicate packages.
    pub root: Option<PathBuf>,
}
const MAX_FILE_BYTES: u64 = 64 * 1024 * 1024;
const MAX_PACKAGE_BYTES: u64 = 256 * 1024 * 1024;
const MAX_FILES: usize = 10000;
const MAX_DEPTH: usize = 16;

fn namespace(id: &str) -> bool {
    !id.is_empty()
        && id.len() <= 64
        && id != "base"
        && id
            .chars()
            .all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || "_-".contains(c))
}
fn relative_path(value: &str) -> Result<()> {
    let path = Path::new(value);
    ensure!(
        !value.is_empty()
            && value.len() <= 512
            && !path.is_absolute()
            && path
                .components()
                .all(|c| matches!(c, std::path::Component::Normal(_))),
        "package paths must be relative and may not contain parent traversal: {value}"
    );
    Ok(())
}
fn read_package_file(root: &Path, relative: &Path) -> Result<Vec<u8>> {
    let path = contained(root, relative)?;
    let metadata = fs::symlink_metadata(&path)?;
    ensure!(metadata.is_file(), "package entry must be a regular file");
    ensure!(metadata.len() <= MAX_FILE_BYTES, "mod file exceeds 64 MiB");
    let data = fs::read(path)?;
    ensure!(
        data.len() as u64 <= MAX_FILE_BYTES,
        "mod file exceeds 64 MiB"
    );
    Ok(data)
}
fn load_package(path: &Path) -> Result<InstalledMod> {
    ensure!(
        fs::symlink_metadata(path)?.is_dir(),
        "mod folder must be a real directory"
    );
    let root = path.canonicalize()?;
    let mut files = Vec::new();
    let mut bytes = 0;
    walk(&root, &root, &mut files, &mut bytes, 0)?;
    files.sort();
    let manifest_data = read_package_file(&root, Path::new("mod.toml"))?;
    ensure!(
        manifest_data.len() <= 64 * 1024,
        "mod manifest exceeds 64 KiB"
    );
    let manifest: Manifest = toml::from_str(std::str::from_utf8(&manifest_data)?)?;
    ensure!(namespace(&manifest.id), "invalid/reserved mod namespace");
    ensure!(
        !manifest.name.trim().is_empty() && manifest.name.len() <= 128,
        "invalid mod display name"
    );
    ensure!(
        manifest.description.len() <= 4096,
        "mod description exceeds 4 KiB"
    );
    Version::parse(&manifest.version).context("invalid package version")?;
    ensure!(
        manifest.dependencies.len() <= 128 && manifest.conflicts.len() <= 128,
        "too many dependencies/conflicts"
    );
    for (dependency, version) in &manifest.dependencies {
        ensure!(
            namespace(dependency) && dependency != &manifest.id,
            "invalid/self dependency {dependency}"
        );
        VersionReq::parse(version)
            .with_context(|| format!("invalid version requirement for {dependency}"))?;
    }
    let conflicts: BTreeSet<_> = manifest.conflicts.iter().collect();
    ensure!(
        conflicts.len() == manifest.conflicts.len(),
        "duplicate conflict declaration"
    );
    for conflict in &manifest.conflicts {
        ensure!(
            namespace(conflict) && conflict != &manifest.id,
            "invalid/self conflict {conflict}"
        );
    }
    relative_path(&manifest.content)?;
    contained(&root, Path::new(&manifest.content))?;
    ensure!(
        manifest.scripts.len() <= 64,
        "too many scripts (maximum 64)"
    );
    let scripts: BTreeSet<_> = manifest.scripts.iter().collect();
    ensure!(
        scripts.len() == manifest.scripts.len(),
        "duplicate script declaration"
    );
    for script in &manifest.scripts {
        relative_path(script)?;
        contained(&root, Path::new(script))?;
    }
    let mut hash = Sha256::new();
    hash.update(b"raptor-mod-package-v1\0");
    for relative in files {
        let name = relative
            .to_str()
            .context("package filenames must be UTF-8")?;
        let data = read_package_file(&root, &relative)?;
        hash.update((name.len() as u64).to_le_bytes());
        hash.update(name.as_bytes());
        hash.update((data.len() as u64).to_le_bytes());
        hash.update(data);
    }
    Ok(InstalledMod {
        root,
        manifest,
        hash: format!("{:x}", hash.finalize()),
    })
}
pub fn discover(root: &Path) -> Discovery {
    let mut out = Discovery::default();
    out.root = Some(root.canonicalize().unwrap_or_else(|_| root.to_path_buf()));
    if !root.exists() {
        return out;
    }
    let entries = match fs::read_dir(root) {
        Ok(e) => e,
        Err(e) => {
            out.errors.push(e.to_string());
            return out;
        }
    };
    let mut entries: Vec<_> = entries.collect();
    entries.sort_by_key(|e| e.as_ref().ok().map(|e| e.path()));
    let mut ambiguous = BTreeSet::new();
    for entry in entries {
        let e = match entry {
            Ok(e) => e,
            Err(err) => {
                out.errors.push(format!("{}: {err}", root.display()));
                continue;
            }
        };
        let kind = match e.file_type() {
            Ok(kind) => kind,
            Err(err) => {
                out.errors.push(format!("{}: {err}", e.path().display()));
                continue;
            }
        };
        if kind.is_symlink() {
            out.errors.push(format!(
                "{}: mod folders may not be symlinks",
                e.path().display()
            ));
            continue;
        }
        if !kind.is_dir() {
            continue;
        }
        match load_package(&e.path()) {
            Ok(m) => {
                let id = m.manifest.id.clone();
                if ambiguous.contains(&id) || out.mods.contains_key(&id) {
                    out.errors.push(format!("duplicate installed mod {id}"));
                    ambiguous.insert(id.clone());
                    out.mods.remove(&id);
                } else {
                    out.mods.insert(id, m);
                }
            }
            Err(err) => out.errors.push(format!("{}: {err:#}", e.path().display())),
        }
    }
    out
}
fn walk(
    root: &Path,
    current: &Path,
    files: &mut Vec<PathBuf>,
    bytes: &mut u64,
    depth: usize,
) -> Result<()> {
    ensure!(
        depth <= MAX_DEPTH,
        "mod package directory depth exceeds {MAX_DEPTH}"
    );
    for e in fs::read_dir(current)? {
        let e = e?;
        let relative = e.path().strip_prefix(root)?.to_path_buf();
        ensure!(
            !e.file_type()?.is_symlink(),
            "mod packages may not contain symlinks"
        );
        if e.file_type()?.is_dir() {
            walk(root, &e.path(), files, bytes, depth + 1)?
        } else {
            ensure!(
                e.file_type()?.is_file(),
                "mod entries must be regular files"
            );
            ensure!(
                e.metadata()?.len() <= MAX_FILE_BYTES,
                "mod file exceeds 64 MiB"
            );
            *bytes = bytes
                .checked_add(e.metadata()?.len())
                .context("package size overflow")?;
            ensure!(*bytes <= MAX_PACKAGE_BYTES, "mod package exceeds 256 MiB");
            files.push(relative);
            ensure!(files.len() <= MAX_FILES, "mod package has too many files");
        }
    }
    Ok(())
}
pub fn order(discovery: &Discovery, enabled: &[String]) -> Result<Vec<String>> {
    let selected: BTreeSet<_> = enabled.iter().cloned().collect();
    ensure!(
        selected.len() == enabled.len(),
        "duplicate mod in load order"
    );
    let mut result = Vec::new();
    let mut visiting = BTreeSet::new();
    let mut done = BTreeSet::new();
    fn visit(
        id: &str,
        d: &Discovery,
        selected: &BTreeSet<String>,
        visiting: &mut BTreeSet<String>,
        done: &mut BTreeSet<String>,
        result: &mut Vec<String>,
    ) -> Result<()> {
        if done.contains(id) {
            return Ok(());
        }
        ensure!(visiting.insert(id.into()), "cyclic mod dependency at {id}");
        let m = d
            .mods
            .get(id)
            .with_context(|| format!("mod {id} is not installed"))?;
        ensure!(
            m.manifest.api_version == API_VERSION,
            "{id}: requires API {}, game provides {API_VERSION}",
            m.manifest.api_version
        );
        for (dep, requirement) in &m.manifest.dependencies {
            ensure!(selected.contains(dep), "{id} requires enabled mod {dep}");
            let v = &d
                .mods
                .get(dep)
                .with_context(|| format!("missing dependency {dep}"))?
                .manifest
                .version;
            ensure!(
                VersionReq::parse(requirement)?.matches(&Version::parse(v)?),
                "{id} requires {dep} {requirement}, installed {v}"
            );
            visit(dep, d, selected, visiting, done, result)?;
        }
        for conflict in &m.manifest.conflicts {
            ensure!(
                !selected.contains(conflict),
                "{id} conflicts with {conflict}"
            );
        }
        visiting.remove(id);
        done.insert(id.into());
        result.push(id.into());
        Ok(())
    }
    for id in enabled {
        visit(
            id,
            discovery,
            &selected,
            &mut visiting,
            &mut done,
            &mut result,
        )?;
    }
    Ok(result)
}
pub struct ActiveMods {
    pub registry: Registry,
    pub pins: Vec<ModPin>,
    pub scripts: ScriptRuntime,
}
impl ActiveMods {
    pub fn build(
        base: &Registry,
        discovery: &Discovery,
        enabled: &[String],
        catalog: Option<&Catalog>,
    ) -> Result<Self> {
        let mut registry = base.clone();
        let mut pins = Vec::new();
        let mut scripts = ScriptRuntime::new();
        let ordered = order(discovery, enabled)?;
        let refreshed = discovery.root.as_ref().map(|root| discover(root));
        for id in &ordered {
            let previous = &discovery.mods[id];
            if let Some(refreshed) = &refreshed {
                ensure!(
                    refreshed.mods.contains_key(id),
                    "{id}: package removed, invalid or duplicated since discovery; rescan the Mods screen ({})",
                    refreshed.errors.join("; ")
                );
            }
            let current = load_package(&previous.root).with_context(|| {
                format!("{id}: package changed or was removed; rescan the Mods screen")
            })?;
            ensure!(
                current.manifest.id == *id && current.hash == previous.hash,
                "{id}: package changed since discovery; rescan the Mods screen before applying"
            );
        }
        for id in &ordered {
            let m = &discovery.mods[id];
            let content: ContentPack = serde_json::from_slice(&read_package_file(
                &m.root,
                Path::new(&m.manifest.content),
            )?)
            .with_context(|| format!("{id}: invalid content"))?;
            registry.asset_roots.insert(id.clone(), m.root.clone());
            registry.apply(content, &id)?;
            for path in &m.manifest.scripts {
                let source = read_package_file(&m.root, Path::new(path))?;
                let source = std::str::from_utf8(&source)
                    .with_context(|| format!("{id}/{path}: source must be UTF-8"))?;
                scripts.add(&id, path, &source)?;
            }
            pins.push(ModPin {
                id: id.clone(),
                version: m.manifest.version.clone(),
                hash: m.hash.clone(),
            });
        }
        registry.validate()?;
        let validate_art = |owner: &str, art: &crate::content::Art| -> Result<()> {
            for png in art.png.iter().chain(art.hd_png.iter()) {
                let root = registry
                    .asset_roots
                    .get(owner)
                    .context("missing PNG root")?;
                let path = contained(root, Path::new(png))?;
                let palette = catalog
                    .map(|cat| cat.palette())
                    .transpose()?
                    .unwrap_or([[0; 3]; 256]);
                let sprite = crate::assets::Sprite::png(&path, &palette)?;
                ensure!(
                    sprite.width % art.frames as usize == 0,
                    "{owner}/{png}: PNG strip width must divide evenly into frames"
                );
                ensure!(
                    sprite.width / art.frames as usize * art.logical_height as usize
                        == sprite.height * art.logical_width as usize,
                    "{owner}/{png}: artwork canvas aspect differs from logical canvas"
                );
                if art.hd_png.as_ref() == Some(png) {
                    ensure!(
                        sprite.width / art.frames as usize >= 2 * art.logical_width as usize
                            && sprite.height >= 2 * art.logical_height as usize,
                        "{owner}/{png}: HD artwork needs at least twice the logical resolution"
                    );
                }
            }
            if let (Some(id), Some(cat)) = (art.asset, catalog) {
                for frame in 0..art.frames {
                    cat.sprite(id.checked_add(frame).context("asset ID overflow")?)?;
                }
            }
            Ok(())
        };
        for (id, owner) in &registry.owners {
            if owner == "base" {
                continue;
            }
            if let Some(art) = registry.art(id) {
                validate_art(owner, art)?;
            }
            if let Some(sound) = registry.sounds.get(id) {
                let root = registry
                    .asset_roots
                    .get(owner)
                    .context("missing sound root")?;
                let bytes = read_package_file(root, Path::new(&sound.file))?;
                crate::sound::decode(&bytes)
                    .with_context(|| format!("{owner}/{}: invalid sound", sound.file))?;
            }
            if let Some(music) = registry.music.get(id) {
                let root = registry
                    .asset_roots
                    .get(owner)
                    .context("missing music root")?;
                crate::sound::load_music(root, &music.file).with_context(|| {
                    format!("{owner}/{}: invalid music {}", music.file, music.id)
                })?;
            }
            if let Some(m) = registry.missions.get(id) {
                for tile in &m.tiles {
                    validate_art(owner, &tile.art)?;
                    if let Some(a) = &tile.destroyed {
                        validate_art(owner, a)?;
                    }
                }
            }
        }
        let validate_script = |owner: &str, path: &Option<String>| -> Result<()> {
            if let Some(path) = path {
                ensure!(
                    scripts.has(owner, path),
                    "{owner}: script {path} must appear in manifest.scripts"
                );
            }
            Ok(())
        };
        for (id, owner) in &registry.owners {
            if let Some(w) = registry.weapons.get(id) {
                validate_script(owner, &w.script)?;
            }
            if let Some(e) = registry.enemies.get(id) {
                validate_script(owner, &e.script)?;
            }
            if let Some(i) = registry.items.get(id) {
                validate_script(owner, &i.script)?;
            }
            if let Some(m) = registry.missions.get(id) {
                validate_script(owner, &m.script)?;
            }
        }
        for id in &ordered {
            ensure!(
                load_package(&discovery.mods[id].root)?.hash == discovery.mods[id].hash,
                "{id}: package changed while loading; rescan the Mods screen before applying"
            );
        }
        Ok(Self {
            registry,
            pins,
            scripts,
        })
    }
}
#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(tag = "op", rename_all = "snake_case", deny_unknown_fields)]
pub enum Command {
    /// Add an enemy at an integer position in the original logical canvas.
    Spawn {
        enemy: String,
        x: i32,
        y: i32,
    },
    Projectile {
        weapon: String,
        x: i32,
        y: i32,
        vx: i32,
        vy: i32,
        #[serde(default)]
        hostile: bool,
    },
    Damage {
        /// Enemy entity ID; zero addresses the player.
        entity: u64,
        amount: i32,
    },
    Despawn {
        entity: u64,
    },
    Move {
        /// Existing enemy entity ID.
        entity: u64,
        x: i32,
        y: i32,
    },
    Velocity {
        entity: u64,
        vx: i32,
        vy: i32,
    },
    GiveItem {
        item: String,
        count: u32,
    },
    ConsumeItem {
        item: String,
        count: u32,
    },
    Credits {
        amount: i32,
    },
    Shield {
        amount: i32,
    },
    Effect {
        x: i32,
        y: i32,
    },
    Sound {
        asset: u32,
    },
    PlaySound {
        sound: String,
    },
    Objective {
        /// Stable namespaced objective key, at most 128 bytes.
        key: String,
        value: i32,
    },
    Complete,
    Fail,
}
#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct HookResult {
    /// Transactional commands, applied in order only when the callback succeeds.
    #[serde(default)]
    pub commands: Vec<Command>,
    /// JSON-serializable state shared by callbacks in this script; maximum 64 KiB.
    #[serde(default)]
    pub state: serde_json::Value,
}
pub struct ScriptRuntime {
    engine: Engine,
    scripts: BTreeMap<(String, String), AST>,
    pub states: BTreeMap<String, serde_json::Value>,
    pub rng: BTreeMap<String, LegacyRng>,
    budget: std::sync::Arc<std::sync::atomic::AtomicI64>,
}
impl ScriptRuntime {
    pub fn new() -> Self {
        // Rhai's default StandardPackage includes wall-clock timestamps and native sleep.
        // Use an explicit package allowlist so timing cannot bypass operation limits,
        // including through dynamically created function pointers.
        let mut engine = Engine::new_raw();
        ArithmeticPackage::new().register_into_engine(&mut engine);
        BasicStringPackage::new().register_into_engine(&mut engine);
        BasicIteratorPackage::new().register_into_engine(&mut engine);
        BasicFnPackage::new().register_into_engine(&mut engine);
        BitFieldPackage::new().register_into_engine(&mut engine);
        LogicPackage::new().register_into_engine(&mut engine);
        BasicMathPackage::new().register_into_engine(&mut engine);
        BasicArrayPackage::new().register_into_engine(&mut engine);
        BasicMapPackage::new().register_into_engine(&mut engine);
        MoreStringPackage::new().register_into_engine(&mut engine);
        engine
            .set_max_operations(100000)
            .set_max_call_levels(32)
            .set_max_expr_depths(64, 32)
            .set_max_array_size(4096)
            .set_max_map_size(1024)
            .set_max_string_size(16384)
            .set_max_modules(0);
        engine.disable_symbol("eval");
        engine.disable_symbol("import");
        engine.on_print(|_| {});
        engine.on_debug(|_, _, _| {});
        let budget = std::sync::Arc::new(std::sync::atomic::AtomicI64::new(500000));
        let counter = budget.clone();
        engine.on_progress(move |_| {
            if counter.fetch_sub(1, std::sync::atomic::Ordering::Relaxed) <= 0 {
                Some(Dynamic::UNIT)
            } else {
                None
            }
        });
        Self {
            engine,
            scripts: BTreeMap::new(),
            states: BTreeMap::new(),
            rng: BTreeMap::new(),
            budget,
        }
    }
    pub fn begin_tick(&self) {
        self.budget
            .store(500000, std::sync::atomic::Ordering::Relaxed);
    }
    pub fn add(&mut self, owner: &str, path: &str, source: &str) -> Result<()> {
        ensure!(
            source.len() <= 1024 * 1024,
            "{owner}/{path}: script source exceeds 1 MiB"
        );
        let mut ast = self
            .engine
            .compile(source)
            .map_err(|e| anyhow::anyhow!("{owner}/{path}: {e}"))?;
        for function in ast.iter_functions() {
            if [
                "on_spawn",
                "on_tick",
                "on_fire",
                "on_hit",
                "on_death",
                "on_pickup",
                "on_use",
                "on_mission_start",
                "on_mission_end",
            ]
            .contains(&function.name)
            {
                ensure!(
                    function.params.len() == 3,
                    "{owner}/{path}::{}: callbacks require (event, state, random)",
                    function.name
                );
            }
        }
        ast.set_source(format!("{owner}/{path}"));
        self.scripts.insert((owner.into(), path.into()), ast);
        Ok(())
    }
    pub fn has(&self, owner: &str, path: &str) -> bool {
        self.scripts.contains_key(&(owner.into(), path.into()))
    }
    pub fn invoke(
        &mut self,
        owner: &str,
        path: &str,
        hook: &str,
        event: &serde_json::Value,
        seed: i32,
    ) -> Result<Vec<Command>> {
        let ast = self
            .scripts
            .get(&(owner.into(), path.into()))
            .with_context(|| format!("{owner}/{path}::{hook}: script is not loaded"))?;
        if !ast
            .iter_functions()
            .any(|f| f.name == hook && f.params.len() == 3)
        {
            return Ok(vec![]);
        }
        let key = format!("{owner}/{path}");
        let mut rng = *self.rng.get(&key).unwrap_or(&LegacyRng::new(seed));
        let random: Vec<i32> = (0..32).map(|_| rng.next_value()).collect();
        let state = self
            .states
            .get(&key)
            .cloned()
            .unwrap_or_else(|| serde_json::json!({}));
        let event = rhai::serde::to_dynamic(event.clone())?;
        let state = rhai::serde::to_dynamic(state)?;
        let random = rhai::serde::to_dynamic(random)?;
        let value = self
            .engine
            .call_fn::<Dynamic>(&mut Scope::new(), ast, hook, (event, state, random))
            .map_err(|e| anyhow::anyhow!("{owner}/{path}::{hook}: {e}"))?;
        let result: HookResult = rhai::serde::from_dynamic(&value)
            .map_err(|e| anyhow::anyhow!("{owner}/{path}::{hook}: invalid result: {e}"))?;
        ensure!(
            result.commands.len() <= 256,
            "{owner}/{path}::{hook}: callback emitted too many commands"
        );
        ensure!(
            serde_json::to_vec(&result.state)?.len() <= 65536,
            "{owner}/{path}::{hook}: callback state exceeds 64 KiB"
        );
        // World command validation is performed by the caller before committing these values.
        self.states.insert(key.clone(), result.state);
        self.rng.insert(key, rng);
        Ok(result.commands)
    }
    pub fn checkpoints(
        &self,
    ) -> (
        BTreeMap<String, serde_json::Value>,
        BTreeMap<String, LegacyRng>,
    ) {
        (self.states.clone(), self.rng.clone())
    }
    pub fn restore(
        &mut self,
        c: (
            BTreeMap<String, serde_json::Value>,
            BTreeMap<String, LegacyRng>,
        ),
    ) {
        self.states = c.0;
        self.rng = c.1;
    }
}
impl Default for ScriptRuntime {
    fn default() -> Self {
        Self::new()
    }
}
pub fn write_schemas(root: &Path) -> Result<()> {
    fs::create_dir_all(root)?;
    macro_rules! schema {
        ($name:expr,$ty:ty) => {
            crate::persistence::atomic_write(
                &root.join($name),
                &serde_json::to_vec_pretty(&schemars::schema_for!($ty))?,
            )?;
        };
    }
    schema!("mod-v1.json", Manifest);
    schema!("content-v1.json", ContentPack);
    schema!("hook-v1.json", HookResult);
    schema!("weapon-projectile-v1.json", crate::content::WeaponDef);
    schema!("item-v1.json", crate::content::ItemDef);
    schema!("enemy-v1.json", crate::content::EnemyDef);
    schema!("mission-v1.json", crate::content::MissionDef);
    schema!("campaign-v1.json", crate::content::CampaignDef);
    schema!("sound-v1.json", crate::content::SoundDef);
    schema!("music-v1.json", crate::content::MusicDef);
    Ok(())
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn bounded_script_and_state_rollback() {
        let mut rt = ScriptRuntime::new();
        rt.add("test", "bad.rhai", "fn on_tick(e,s,r) { while true {} }")
            .unwrap();
        assert!(
            rt.invoke("test", "bad.rhai", "on_tick", &serde_json::json!({}), 1)
                .is_err()
        );
        assert!(rt.states.is_empty());
    }
    #[test]
    fn script_can_emit_commands() {
        let mut rt = ScriptRuntime::new();
        rt.add("test","good.rhai","fn on_fire(e,s,r) { #{ commands: [#{ op: \"credits\", amount: 7 }], state: #{ calls: 1 } } }").unwrap();
        assert_eq!(
            rt.invoke("test", "good.rhai", "on_fire", &serde_json::json!({}), 1)
                .unwrap()
                .len(),
            1
        );
        assert_eq!(rt.states["test/good.rhai"]["calls"], 1);
    }
    #[test]
    fn io_is_not_exposed() {
        let mut rt = ScriptRuntime::new();
        rt.add(
            "test",
            "io.rhai",
            "fn on_tick(e,s,r){ read_file(\"/etc/passwd\") }",
        )
        .unwrap();
        assert!(
            rt.invoke("test", "io.rhai", "on_tick", &serde_json::json!({}), 1)
                .is_err()
        );
    }
}
