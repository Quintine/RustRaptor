//! Opt-in remaster artwork tied to the original asset ID and animation canvas.
//! Runtime loading checks source metadata first, then decodes artwork on demand.
//! Rejected frames fall back to the original crisp sprite, with a diagnostic.
use crate::assets::{Catalog, Sprite, TRANSPARENT, contained};
use anyhow::{Context, Result, ensure};
use image::{
    ImageReader, RgbaImage,
    imageops::{self, FilterType},
};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    collections::BTreeMap,
    fs,
    io::{Cursor, Read, Write},
    path::{Path, PathBuf},
    time::SystemTime,
};

const MAX_METADATA_BYTES: u64 = 8 * 1024 * 1024;
const MAX_SEQUENCES: usize = 8192;
const MAX_FRAMES: usize = 16384;
const CACHE_BYTES: usize = 32 * 1024 * 1024;
const MAX_SOURCE_LABEL_BYTES: usize = 32 * 1024 * 1024;
const DISK_CACHE_BYTES: u64 = 512 * 1024 * 1024;
const MAX_PNG_BYTES: u64 = 32 * 1024 * 1024;
const MAX_PNG_PIXELS: u64 = 4_194_304;
const CACHE_MAGIC: &[u8; 8] = b"RRHD0002";
const CACHE_HEADER: usize = 80;
const KERNEL_VERSION: &[u8] = b"raptor-hd-lanczos3-rgba-v1";

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Manifest {
    pub format_version: u32,
    pub name: String,
    #[serde(default)]
    pub description: String,
    pub sequences: Vec<Sequence>,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Sequence {
    pub name: String,
    pub base_asset: u32,
    pub frame_count: u32,
    pub frames: Vec<Frame>,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Frame {
    pub frame: u32,
    pub file: PathBuf,
    pub logical_width: u32,
    pub logical_height: u32,
    /// Anchor relative to the original canvas. Version 1 requires [0, 0].
    pub origin: [i32; 2],
    /// Exact original catalog payload, so changes cannot quietly misalign art.
    pub source_sha256: String,
    /// Optional pixel rectangle [x, y, width, height] in an atlas PNG.
    #[serde(default)]
    pub crop: Option<[u32; 4]>,
    /// Explicit, independently reviewed gameplay-only source250..255 alpha
    /// coverage. Does not assign reserved labels to ordinary source cells.
    #[serde(default, skip_serializing_if = "is_false")]
    pub preserve_reserved_coverage: bool,
    /// Up to64 sorted unique [x,y] ordinary original cells, sampled from
    /// untouched resident RGBA with nearest only at gameplay scale1.
    /// Other cells/scales and static palettes retain their existing sampler.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub native_nearest_cues: Vec<[u32; 2]>,
}
fn is_false(value: &bool) -> bool {
    !*value
}
struct Replacement {
    frame: Frame,
    requires_alpha: bool,
    /// None means every source location is ordinary. Special locations retain
    /// their original cycling group or exact glow/flash label.
    source_labels: Option<Vec<u8>>,
    validated: bool,
    rejected: bool,
}
#[derive(Clone)]
struct PngInfo {
    size: u64,
    modified: Option<SystemTime>,
    digest: [u8; 32],
    width: u32,
    height: u32,
}
struct CacheEntry<V> {
    value: V,
    bytes: usize,
    used: u64,
}
struct LruCache<K, V> {
    entries: BTreeMap<K, CacheEntry<V>>,
    bytes: usize,
    limit: usize,
    clock: u64,
}
impl<K: Ord + Clone, V> LruCache<K, V> {
    fn new(limit: usize) -> Self {
        Self {
            entries: BTreeMap::new(),
            bytes: 0,
            limit,
            clock: 0,
        }
    }
    fn get(&mut self, key: &K) -> Option<&V> {
        self.clock = self.clock.wrapping_add(1);
        let entry = self.entries.get_mut(key)?;
        entry.used = self.clock;
        Some(&entry.value)
    }
    fn insert(&mut self, key: K, value: V, bytes: usize) {
        if let Some(old) = self.entries.remove(&key) {
            self.bytes -= old.bytes;
        }
        if bytes > self.limit {
            return;
        }
        while self.bytes + bytes > self.limit {
            let Some(oldest) = self
                .entries
                .iter()
                .min_by_key(|(_, entry)| entry.used)
                .map(|(key, _)| key.clone())
            else {
                break;
            };
            self.bytes -= self.entries.remove(&oldest).unwrap().bytes;
        }
        self.clock = self.clock.wrapping_add(1);
        self.bytes += bytes;
        self.entries.insert(
            key,
            CacheEntry {
                value,
                bytes,
                used: self.clock,
            },
        );
    }
}
/// Decoded validation and metadata registration are deliberately separate.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ValidationReport {
    pub registered: usize,
    pub validated: usize,
    pub rejected: usize,
}
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct CacheStats {
    pub atlas_bytes: usize,
    pub rgba_bytes: usize,
    pub indexed_bytes: usize,
    pub indexed_entries: usize,
    pub png_decodes: usize,
    pub disk_hits: usize,
    pub disk_writes: usize,
    pub source_label_bytes: usize,
}
#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
enum PalettePolicy {
    SourceClasses,
    Static,
}
pub struct HdAssets {
    root: PathBuf,
    disk_cache: Option<PathBuf>,
    replacements: BTreeMap<u32, Replacement>,
    png_info: BTreeMap<PathBuf, PngInfo>,
    atlases: LruCache<[u8; 32], RgbaImage>,
    rgba: LruCache<[u8; 32], RgbaImage>,
    scaled: LruCache<([u8; 32], usize, [u8; 32], PalettePolicy), Sprite>,
    png_decodes: usize,
    disk_hits: usize,
    disk_writes: usize,
    disk_bytes: Option<u64>,
    disk_limit: u64,
    metadata_rejected: usize,
    source_label_bytes: usize,
    pub diagnostics: Vec<String>,
}
impl Default for HdAssets {
    fn default() -> Self {
        Self {
            root: PathBuf::new(),
            disk_cache: None,
            replacements: BTreeMap::new(),
            png_info: BTreeMap::new(),
            atlases: LruCache::new(CACHE_BYTES),
            rgba: LruCache::new(CACHE_BYTES),
            scaled: LruCache::new(CACHE_BYTES),
            png_decodes: 0,
            disk_hits: 0,
            disk_writes: 0,
            disk_bytes: None,
            disk_limit: DISK_CACHE_BYTES,
            metadata_rejected: 0,
            source_label_bytes: 0,
            diagnostics: Vec::new(),
        }
    }
}
impl HdAssets {
    /// Validate every supplied PNG/crop immediately, using bounded caches.
    /// This is intended for validation tools and tests, rather than startup.
    pub fn load(root: &Path, catalog: &Catalog) -> Self {
        let mut result = Self::load_lazy(root, catalog, None);
        result.validate_all();
        result
    }
    /// Register source-checked frames without retaining or decoding all artwork.
    /// PNG validation happens on first use; `validated_count` reports progress.
    /// An optional private profile cache stores checksum-checked derived RGBA.
    pub fn load_lazy(root: &Path, catalog: &Catalog, cache_dir: Option<&Path>) -> Self {
        let mut result = Self::default();
        if !root.exists() {
            return result;
        }
        result.root = root.to_path_buf();
        result.disk_cache = cache_dir.map(Path::to_path_buf);
        if let Err(e) = result.read(root, catalog) {
            // Invalid sequence metadata rejects the complete pack atomically.
            result.replacements.clear();
            result.diagnostics.clear();
            result
                .diagnostics
                .push(format!("HD pack {}: {e:#}", root.display()));
        }
        result
    }
    fn read(&mut self, root: &Path, catalog: &Catalog) -> Result<()> {
        let path = contained(root, Path::new("hd.json"))?;
        ensure!(
            fs::metadata(&path)?.len() <= MAX_METADATA_BYTES,
            "HD metadata exceeds 8 MiB"
        );
        let bytes = bounded_read(&path, MAX_METADATA_BYTES)?;
        let manifest: Manifest = serde_json::from_slice(&bytes)?;
        ensure!(
            manifest.format_version == 1,
            "unsupported HD artwork format {}",
            manifest.format_version
        );
        ensure!(
            manifest.sequences.len() <= MAX_SEQUENCES,
            "too many HD sequences"
        );
        let mut ids = BTreeMap::new();
        // Check the entire structural manifest before accepting any frames.
        for sequence in &manifest.sequences {
            ensure!(
                (1..=512).contains(&sequence.frame_count),
                "invalid frame count for {}",
                sequence.name
            );
            ensure!(
                sequence.frames.len() <= sequence.frame_count as usize,
                "too many supplied frames for {}",
                sequence.name
            );
            for frame in &sequence.frames {
                ensure!(
                    frame.frame < sequence.frame_count,
                    "{}: frame {} outside sequence",
                    sequence.name,
                    frame.frame
                );
                let id = sequence
                    .base_asset
                    .checked_add(frame.frame)
                    .context("HD asset ID overflow")?;
                ensure!(ids.insert(id, ()).is_none(), "duplicate HD asset {id:05x}");
                ensure!(ids.len() <= MAX_FRAMES, "too many HD frames");
            }
        }
        for sequence in &manifest.sequences {
            for frame in &sequence.frames {
                let id = sequence.base_asset + frame.frame;
                let prepared = (|| -> Result<Replacement> {
                    let source = catalog.read(id)?;
                    let original = Sprite::decode(&source)?;
                    validate_frame(frame, &original, &source)?;
                    // Check containment now and again whenever artwork is read.
                    let path = contained(root, &frame.file)?;
                    ensure!(
                        fs::metadata(path)?.len() <= MAX_PNG_BYTES,
                        "HD PNG exceeds 32 MiB"
                    );
                    let source_labels = if original.pixels.iter().any(|p| (240..=255).contains(p)) {
                        Some(
                            original
                                .pixels
                                .iter()
                                .map(|p| if (240..=255).contains(p) { *p as u8 } else { 0 })
                                .collect::<Vec<_>>(),
                        )
                    } else {
                        None
                    };
                    let label_bytes = source_labels.as_ref().map_or(0, Vec::len);
                    ensure!(
                        self.source_label_bytes + label_bytes <= MAX_SOURCE_LABEL_BYTES,
                        "HD source palette labels exceed 32 MiB"
                    );
                    self.source_label_bytes += label_bytes;
                    Ok(Replacement {
                        frame: frame.clone(),
                        requires_alpha: original.pixels.contains(&TRANSPARENT),
                        source_labels,
                        validated: false,
                        rejected: false,
                    })
                })();
                match prepared {
                    Ok(replacement) => {
                        self.replacements.insert(id, replacement);
                    }
                    Err(e) => {
                        self.metadata_rejected += 1;
                        self.diagnostics.push(format!(
                            "HD {} frame {} ({id:05x}): {e:#}; using original",
                            sequence.name, frame.frame
                        ));
                    }
                }
            }
            if sequence.frames.len() != sequence.frame_count as usize {
                self.diagnostics.push(format!(
                    "HD {}: {} of {} frames supplied; uncovered frames use original artwork",
                    sequence.name,
                    sequence.frames.len(),
                    sequence.frame_count
                ));
            }
        }
        Ok(())
    }
    fn png(&mut self, file: &Path) -> Result<(PathBuf, PngInfo)> {
        let path = contained(&self.root, file)?;
        let metadata = fs::metadata(&path)?;
        ensure!(metadata.len() <= MAX_PNG_BYTES, "HD PNG exceeds 32 MiB");
        let modified = metadata.modified().ok();
        if let Some(info) = self.png_info.get(&path) {
            if info.size == metadata.len() && info.modified.is_some() && info.modified == modified {
                return Ok((path.clone(), info.clone()));
            }
        }
        let bytes = bounded_read(&path, MAX_PNG_BYTES)?;
        let mut reader = ImageReader::new(Cursor::new(&bytes)).with_guessed_format()?;
        ensure!(
            reader.format() == Some(image::ImageFormat::Png),
            "HD artwork must be PNG"
        );
        reader.limits(image_limits());
        let (width, height) = reader.into_dimensions()?;
        ensure!(
            width > 0
                && height > 0
                && width <= 4096
                && height <= 4096
                && width as u64 * height as u64 <= MAX_PNG_PIXELS,
            "HD PNG exceeds pixel limit"
        );
        let info = PngInfo {
            size: bytes.len() as u64,
            modified,
            digest: Sha256::digest(&bytes).into(),
            width,
            height,
        };
        self.png_info.insert(path.clone(), info.clone());
        Ok((path, info))
    }
    fn frame_key(frame: &Frame, info: &PngInfo, requires_alpha: bool) -> [u8; 32] {
        let mut digest = Sha256::new();
        digest.update(KERNEL_VERSION);
        let (width, height) = frame
            .crop
            .map(|[_, _, width, height]| (width, height))
            .unwrap_or((info.width, info.height));
        if !exact_aspect(width, height, frame.logical_width, frame.logical_height) {
            // Only the new rounded opaque path needs a new validation identity.
            // Existing exact-aspect cache keys and raster bytes stay unchanged.
            digest.update(b"full-frame-opaque-rounding-v1");
        }
        digest.update(info.digest);
        digest.update(frame.source_sha256.as_bytes());
        digest.update(frame.logical_width.to_le_bytes());
        digest.update(frame.logical_height.to_le_bytes());
        for value in frame.origin {
            digest.update(value.to_le_bytes());
        }
        digest.update([u8::from(requires_alpha), u8::from(frame.crop.is_some())]);
        if let Some(crop) = frame.crop {
            for value in crop {
                digest.update(value.to_le_bytes());
            }
        }
        // Preserve exact legacy disk/indexed cache keys when both policies are
        // absent/default. Every opt-in has a distinct, versioned namespace.
        if frame.preserve_reserved_coverage || !frame.native_nearest_cues.is_empty() {
            digest.update(b"raptor-hd-frame-presentation-policy-v1");
            digest.update([u8::from(frame.preserve_reserved_coverage)]);
            digest.update((frame.native_nearest_cues.len() as u32).to_le_bytes());
            for cue in &frame.native_nearest_cues {
                for coordinate in cue {
                    digest.update(coordinate.to_le_bytes());
                }
            }
        }
        digest.finalize().into()
    }
    fn rgba_frame(&mut self, id: u32) -> Result<Option<([u8; 32], RgbaImage)>> {
        let Some(record) = self.replacements.get(&id) else {
            return Ok(None);
        };
        if record.rejected {
            return Ok(None);
        }
        let frame = record.frame.clone();
        let requires_alpha = record.requires_alpha;
        let result = (|| -> Result<([u8; 32], RgbaImage)> {
            let (path, info) = self.png(&frame.file)?;
            let (width, height) = frame_dimensions(&frame, &info, requires_alpha)?;
            let requires_opaque =
                !exact_aspect(width, height, frame.logical_width, frame.logical_height);
            let key = Self::frame_key(&frame, &info, requires_alpha);
            if let Some(rgba) = self.rgba.get(&key) {
                return Ok((key, rgba.clone()));
            }
            let target_width = width.min(frame.logical_width * 4);
            let target_height = height.min(frame.logical_height * 4);
            if let Some(rgba) = self.read_disk_cache(
                &key,
                target_width,
                target_height,
                requires_alpha,
                requires_opaque,
            ) {
                self.disk_hits += 1;
                self.rgba.insert(key, rgba.clone(), rgba.as_raw().len());
                return Ok((key, rgba));
            }
            let mut rgba = if let Some(atlas) = self.atlases.get(&info.digest) {
                cropped_frame(atlas, frame.crop)
            } else {
                let bytes = bounded_read(&path, MAX_PNG_BYTES)?;
                ensure!(
                    bytes.len() as u64 <= MAX_PNG_BYTES
                        && <[u8; 32]>::from(Sha256::digest(&bytes)) == info.digest,
                    "HD PNG changed while loading"
                );
                let mut reader = ImageReader::new(Cursor::new(bytes)).with_guessed_format()?;
                ensure!(
                    reader.format() == Some(image::ImageFormat::Png),
                    "HD artwork must be PNG"
                );
                reader.limits(image_limits());
                let atlas = reader.decode()?.into_rgba8();
                ensure!(
                    atlas.width() == info.width && atlas.height() == info.height,
                    "HD PNG changed while loading"
                );
                self.png_decodes += 1;
                let rgba = cropped_frame(&atlas, frame.crop);
                let bytes = atlas.as_raw().len();
                self.atlases.insert(info.digest, atlas, bytes);
                rgba
            };
            validate_rgba(&rgba, requires_alpha)?;
            // Check every original PNG pixel before resampling can round a tiny
            // alpha defect back to 255. Full-frame selection retains all pixels.
            validate_opaque_rounding(&rgba, requires_opaque)?;
            // Keep at most the highest usable 4x resolution, never generator originals.
            if rgba.width() > target_width || rgba.height() > target_height {
                rgba = imageops::resize(&rgba, target_width, target_height, FilterType::Lanczos3);
            }
            validate_rgba(&rgba, requires_alpha)?;
            self.write_disk_cache(&key, &rgba);
            self.rgba.insert(key, rgba.clone(), rgba.as_raw().len());
            Ok((key, rgba))
        })();
        match result {
            Ok(frame) => {
                self.replacements.get_mut(&id).unwrap().validated = true;
                Ok(Some(frame))
            }
            Err(error) => {
                self.replacements.get_mut(&id).unwrap().rejected = true;
                self.diagnostics
                    .push(format!("HD {id:05x}: {error:#}; using original"));
                Ok(None)
            }
        }
    }
    fn cache_path(&self, key: &[u8; 32]) -> Option<PathBuf> {
        self.disk_cache
            .as_ref()
            .map(|root| root.join(format!("{}.rgba", hex_digest(key))))
    }
    fn read_disk_cache(
        &mut self,
        key: &[u8; 32],
        width: u32,
        height: u32,
        requires_alpha: bool,
        requires_opaque: bool,
    ) -> Option<RgbaImage> {
        let path = self.cache_path(key)?;
        if !path.exists() {
            return None;
        }
        let read = (|| -> Result<RgbaImage> {
            let root = self.disk_cache.as_ref().unwrap();
            let path = contained(root, path.file_name().context("cache filename")?.as_ref())?;
            let expected = width as u64 * height as u64 * 4;
            ensure!(
                expected <= MAX_PNG_PIXELS * 4,
                "derived cache exceeds pixel limit"
            );
            ensure!(
                fs::metadata(&path)?.len() == CACHE_HEADER as u64 + expected,
                "derived cache size mismatch"
            );
            let bytes = bounded_read(&path, CACHE_HEADER as u64 + expected)?;
            ensure!(
                bytes.len() == CACHE_HEADER + expected as usize,
                "derived cache changed while reading"
            );
            ensure!(&bytes[..8] == CACHE_MAGIC, "derived cache version mismatch");
            ensure!(
                u32::from_le_bytes(bytes[8..12].try_into()?) == width
                    && u32::from_le_bytes(bytes[12..16].try_into()?) == height,
                "derived cache dimensions mismatch"
            );
            ensure!(&bytes[16..48] == key, "derived cache key mismatch");
            ensure!(
                Sha256::digest(&bytes[CACHE_HEADER..]).as_slice() == &bytes[48..80],
                "derived cache checksum mismatch"
            );
            let rgba = RgbaImage::from_raw(width, height, bytes[CACHE_HEADER..].to_vec())
                .context("derived cache image dimensions")?;
            validate_rgba(&rgba, requires_alpha)?;
            validate_opaque_rounding(&rgba, requires_opaque)?;
            Ok(rgba)
        })();
        match read {
            Ok(rgba) => Some(rgba),
            Err(error) => {
                self.diagnostics.push(format!(
                    "HD derived cache {}: {error:#}; rebuilding",
                    path.display()
                ));
                // Removing a symlink removes the link itself, never its target.
                let _ = fs::remove_file(path);
                self.disk_bytes = None;
                None
            }
        }
    }
    fn write_disk_cache(&mut self, key: &[u8; 32], rgba: &RgbaImage) {
        let Some(path) = self.cache_path(key) else {
            return;
        };
        let write = (|| -> Result<()> {
            let root = self.disk_cache.as_ref().unwrap();
            fs::create_dir_all(root)?;
            let root = root.canonicalize()?;
            let destination = root.join(path.file_name().context("cache filename")?);
            let bytes = CACHE_HEADER as u64 + rgba.as_raw().len() as u64;
            let old_bytes = fs::symlink_metadata(&destination)
                .ok()
                .filter(|metadata| metadata.is_file())
                .map_or(0, |metadata| metadata.len());
            self.prune_disk_cache(&root, &destination, bytes, old_bytes)?;
            let temporary = root.join(format!(
                ".{}-{}-{}.tmp",
                hex_digest(key),
                std::process::id(),
                self.disk_writes
            ));
            let mut file = fs::OpenOptions::new()
                .write(true)
                .create_new(true)
                .open(&temporary)?;
            let result = (|| -> Result<()> {
                file.write_all(CACHE_MAGIC)?;
                file.write_all(&rgba.width().to_le_bytes())?;
                file.write_all(&rgba.height().to_le_bytes())?;
                file.write_all(key)?;
                file.write_all(&Sha256::digest(rgba.as_raw()))?;
                file.write_all(rgba.as_raw())?;
                drop(file);
                fs::rename(&temporary, destination)?;
                self.disk_bytes =
                    Some(self.disk_bytes.unwrap_or(0).saturating_sub(old_bytes) + bytes);
                Ok(())
            })();
            if result.is_err() {
                let _ = fs::remove_file(&temporary);
            }
            result
        })();
        // Cache availability must never disable correctly decoded artwork.
        if write.is_ok() {
            self.disk_writes += 1;
        }
    }
    fn prune_disk_cache(
        &mut self,
        root: &Path,
        destination: &Path,
        new_bytes: u64,
        old_bytes: u64,
    ) -> Result<()> {
        ensure!(
            new_bytes <= self.disk_limit,
            "derived frame exceeds disk cache budget"
        );
        // Most writes need no directory walk. Recheck periodically and whenever full.
        if let Some(bytes) = self.disk_bytes {
            if self.disk_writes % 64 != 0
                && bytes.saturating_sub(old_bytes) + new_bytes <= self.disk_limit
            {
                return Ok(());
            }
        }
        let mut files = Vec::new();
        let mut bytes = 0_u64;
        for entry in fs::read_dir(root)? {
            let entry = entry?;
            let name = entry.file_name();
            let name = name.to_string_lossy();
            if name.len() != 69
                || !name.ends_with(".rgba")
                || !name.as_bytes()[..64]
                    .iter()
                    .all(|byte| byte.is_ascii_hexdigit())
                || !entry.file_type()?.is_file()
            {
                continue;
            }
            let metadata = entry.metadata()?;
            bytes = bytes.saturating_add(metadata.len());
            files.push((
                metadata.modified().unwrap_or(SystemTime::UNIX_EPOCH),
                entry.path(),
                metadata.len(),
            ));
        }
        files.sort_by(|left, right| (&left.0, &left.1).cmp(&(&right.0, &right.1)));
        for (_, path, size) in files {
            if bytes.saturating_sub(old_bytes) + new_bytes <= self.disk_limit {
                break;
            }
            if path == destination {
                continue;
            }
            if fs::remove_file(path).is_ok() {
                bytes = bytes.saturating_sub(size);
            }
        }
        self.disk_bytes = Some(bytes);
        ensure!(
            bytes.saturating_sub(old_bytes) + new_bytes <= self.disk_limit,
            "derived disk cache budget unavailable"
        );
        Ok(())
    }
    /// Frames with valid catalog identity and file containment, including pending PNGs.
    pub fn registered_count(&self) -> usize {
        self.replacements
            .values()
            .filter(|frame| !frame.rejected)
            .count()
    }
    /// Frames whose complete PNG, crop, transparency and dimensions were checked.
    pub fn validated_count(&self) -> usize {
        self.replacements
            .values()
            .filter(|frame| frame.validated && !frame.rejected)
            .count()
    }
    /// Compatibility alias for decoded, accepted coverage. Lazy registration alone is not coverage.
    pub fn coverage(&self) -> usize {
        self.validated_count()
    }
    pub fn validate_all(&mut self) -> ValidationReport {
        let ids: Vec<_> = self.replacements.keys().copied().collect();
        for id in ids {
            let _ = self.rgba_frame(id);
        }
        ValidationReport {
            registered: self.registered_count(),
            validated: self.validated_count(),
            rejected: self.metadata_rejected
                + self
                    .replacements
                    .values()
                    .filter(|frame| frame.rejected)
                    .count(),
        }
    }
    pub fn cache_stats(&self) -> CacheStats {
        CacheStats {
            atlas_bytes: self.atlases.bytes,
            rgba_bytes: self.rgba.bytes,
            indexed_bytes: self.scaled.bytes,
            indexed_entries: self.scaled.entries.len(),
            png_decodes: self.png_decodes,
            disk_hits: self.disk_hits,
            disk_writes: self.disk_writes,
            source_label_bytes: self.source_label_bytes,
        }
    }
    /// Return detailed artwork at canvas resolution; never run ScaleNx on it.
    /// Indexed caches include palette identity, so fades/cycling cannot reuse stale colors.
    pub fn sprite(
        &mut self,
        id: u32,
        scale: usize,
        palette: &[[u8; 3]; 256],
    ) -> Result<Option<Sprite>> {
        self.sprite_with_policy(id, scale, palette, PalettePolicy::SourceClasses)
    }
    /// Standalone cards use all 256 colors of their own unfaded static palette.
    /// Gameplay cycling/flash classes do not apply; fades happen at presentation.
    pub fn sprite_static_palette(
        &mut self,
        id: u32,
        scale: usize,
        palette: &[[u8; 3]; 256],
    ) -> Result<Option<Sprite>> {
        self.sprite_with_policy(id, scale, palette, PalettePolicy::Static)
    }
    fn sprite_with_policy(
        &mut self,
        id: u32,
        scale: usize,
        palette: &[[u8; 3]; 256],
        policy: PalettePolicy,
    ) -> Result<Option<Sprite>> {
        ensure!(
            (1..=4).contains(&scale),
            "HD presentation scale must be 1..4"
        );
        let palette_key: [u8; 32] = Sha256::digest(palette.as_flattened()).into();
        // Common repeated draws should only copy the final indexed canvas.
        if let Some(record) = self.replacements.get(&id).filter(|record| !record.rejected) {
            let frame = record.frame.clone();
            let requires_alpha = record.requires_alpha;
            if let Ok((_, info)) = self.png(&frame.file) {
                let key = Self::frame_key(&frame, &info, requires_alpha);
                if let Some(sprite) = self.scaled.get(&(key, scale, palette_key, policy)).cloned() {
                    self.replacements.get_mut(&id).unwrap().validated = true;
                    return Ok(Some(sprite));
                }
            }
        }
        let Some((key, rgba)) = self.rgba_frame(id)? else {
            return Ok(None);
        };
        let scaled_key = (key, scale, palette_key, policy);
        let replacement = self.replacements.get(&id).unwrap();
        let frame = &replacement.frame;
        let width = frame.logical_width as usize * scale;
        let height = frame.logical_height as usize * scale;
        let resized = imageops::resize(&rgba, width as u32, height as u32, FilterType::Lanczos3);
        let mut sprite = Sprite::blank(width, height);
        let mut colors = BTreeMap::new();
        for (index, (destination, pixel)) in
            sprite.pixels.iter_mut().zip(resized.pixels()).enumerate()
        {
            let pixel = if policy == PalettePolicy::SourceClasses
                && scale == 1
                && !frame.native_nearest_cues.is_empty()
                && frame
                    .native_nearest_cues
                    .binary_search(&[(index % width) as u32, (index / width) as u32])
                    .is_ok()
            {
                // Exact nearest sample center, using integer ratios to avoid
                // temporary canvases/float boundary rounding. No RGB remap.
                let x = ((2 * (index % width) as u64 + 1) * rgba.width() as u64
                    / (2 * frame.logical_width as u64)) as u32;
                let y = ((2 * (index / width) as u64 + 1) * rgba.height() as u64
                    / (2 * frame.logical_height as u64)) as u32;
                rgba.get_pixel(x, y)
            } else {
                pixel
            };
            let logical =
                (index / width / scale) * frame.logical_width as usize + (index % width / scale);
            let source_label = if policy == PalettePolicy::SourceClasses {
                replacement
                    .source_labels
                    .as_ref()
                    .map_or(0, |labels| labels[logical])
            } else {
                0
            };
            if pixel[3] < 128 {
                // Require meaningful existing alpha support in the bounded
                // resident logical cell; missing/mostly empty artwork remains
                // transparent. This guard is not source-fidelity approval.
                let supported = policy == PalettePolicy::SourceClasses
                    && frame.preserve_reserved_coverage
                    && (250..=255).contains(&source_label)
                    && reserved_cell_supported(&rgba, frame, logical);
                if !supported {
                    continue;
                }
            }
            let rgb = [pixel[0], pixel[1], pixel[2]];
            *destination = *colors
                .entry((rgb, source_label))
                .or_insert_with(|| match policy {
                    PalettePolicy::SourceClasses => closest(palette, rgb, source_label),
                    PalettePolicy::Static => closest_in_range(palette, rgb, 0..256),
                });
        }
        self.scaled
            .insert(scaled_key, sprite.clone(), sprite.pixels.len() * 2);
        Ok(Some(sprite))
    }
}
/// At most 5x5 samples: resident RGBA is capped at4x logical dimensions.
/// Fractional cell edges support valid non-integral2x..4x source canvases.
/// Both mean alpha and alpha>=128 area must cover at least half the cell.
fn reserved_cell_supported(rgba: &RgbaImage, frame: &Frame, logical: usize) -> bool {
    let sx = rgba.width() as f64 / frame.logical_width as f64;
    let sy = rgba.height() as f64 / frame.logical_height as f64;
    let x = logical % frame.logical_width as usize;
    let y = logical / frame.logical_width as usize;
    let (x0, x1, y0, y1) = (
        x as f64 * sx,
        ((x + 1) as f64 * sx).min(rgba.width() as f64),
        y as f64 * sy,
        ((y + 1) as f64 * sy).min(rgba.height() as f64),
    );
    let mut alpha = 0.0;
    let mut covered = 0.0;
    for yy in y0.floor() as u32..y1.ceil() as u32 {
        for xx in x0.floor() as u32..x1.ceil() as u32 {
            let weight = (x1.min(xx as f64 + 1.0) - x0.max(xx as f64)).max(0.0)
                * (y1.min(yy as f64 + 1.0) - y0.max(yy as f64)).max(0.0);
            let a = rgba.get_pixel(xx, yy)[3];
            alpha += weight * a as f64;
            if a >= 128 {
                covered += weight;
            }
        }
    }
    alpha >= 128.0 * sx * sy && covered >= 0.5 * sx * sy
}
fn bounded_read(path: &Path, limit: u64) -> Result<Vec<u8>> {
    let file = fs::File::open(path)?;
    let size = file.metadata()?.len();
    ensure!(size <= limit, "file exceeds {limit} byte limit");
    let mut bytes = Vec::with_capacity(size as usize);
    file.take(limit + 1).read_to_end(&mut bytes)?;
    ensure!(
        bytes.len() as u64 <= limit,
        "file grew beyond {limit} byte limit"
    );
    Ok(bytes)
}
fn cropped_frame(atlas: &RgbaImage, crop: Option<[u32; 4]>) -> RgbaImage {
    if let Some([x, y, width, height]) = crop {
        imageops::crop_imm(atlas, x, y, width, height).to_image()
    } else {
        atlas.clone()
    }
}
fn image_limits() -> image::Limits {
    let mut limits = image::Limits::default();
    limits.max_image_width = Some(4096);
    limits.max_image_height = Some(4096);
    limits.max_alloc = Some(64 * 1024 * 1024);
    limits
}
fn exact_aspect(width: u32, height: u32, logical_width: u32, logical_height: u32) -> bool {
    width as u128 * logical_height as u128 == height as u128 * logical_width as u128
}
/// A common scale must fit both integer dimensions with less than half a pixel
/// of rounding on each axis. Strict inequality excludes an overlap consisting
/// only of conflicting half-way ties (for example, a square PNG with unequal axes).
fn integer_rounded_aspect(
    width: u32,
    height: u32,
    logical_width: u32,
    logical_height: u32,
) -> bool {
    if width == 0 || height == 0 || logical_width == 0 || logical_height == 0 {
        return false;
    }
    let a = width as u128 * logical_height as u128;
    let b = height as u128 * logical_width as u128;
    2 * a.abs_diff(b) < logical_width as u128 + logical_height as u128
}
fn frame_dimensions(frame: &Frame, png: &PngInfo, requires_alpha: bool) -> Result<(u32, u32)> {
    let (width, height) = if let Some([x, y, width, height]) = frame.crop {
        ensure!(
            width > 0
                && height > 0
                && x.checked_add(width).is_some_and(|n| n <= png.width)
                && y.checked_add(height).is_some_and(|n| n <= png.height),
            "HD atlas crop exceeds its PNG"
        );
        (width, height)
    } else {
        (png.width, png.height)
    };
    ensure!(
        exact_aspect(width, height, frame.logical_width, frame.logical_height)
            || (!requires_alpha
                && width == png.width
                && height == png.height
                && integer_rounded_aspect(
                    width,
                    height,
                    frame.logical_width,
                    frame.logical_height,
                )),
        "HD frame aspect must match the original canvas; only a full opaque frame may use subpixel integer rounding"
    );
    ensure!(
        width as u64 >= frame.logical_width as u64 * 2
            && height as u64 >= frame.logical_height as u64 * 2,
        "HD artwork must supply at least twice the logical resolution"
    );
    Ok((width, height))
}
fn validate_opaque_rounding(rgba: &RgbaImage, requires_opaque: bool) -> Result<()> {
    ensure!(
        !requires_opaque || rgba.pixels().all(|pixel| pixel[3] == 255),
        "HD integer-aspect rounding requires a fully opaque source and PNG"
    );
    Ok(())
}
fn validate_rgba(rgba: &RgbaImage, requires_alpha: bool) -> Result<()> {
    ensure!(
        !requires_alpha || rgba.pixels().any(|p| p[3] == 0),
        "HD frame needs a transparent background matching its original"
    );
    ensure!(
        rgba.pixels().any(|p| p[3] >= 128),
        "HD frame has no visible pixels"
    );
    Ok(())
}
fn validate_frame(frame: &Frame, original: &Sprite, source: &[u8]) -> Result<()> {
    ensure!(
        frame.logical_width as usize == original.width
            && frame.logical_height as usize == original.height,
        "HD logical dimensions must equal original {}x{}",
        original.width,
        original.height
    );
    ensure!(
        frame.native_nearest_cues.len() <= 64,
        "native nearest cue list exceeds64 cells"
    );
    ensure!(
        frame.native_nearest_cues.windows(2).all(|w| w[0] < w[1]),
        "native nearest cues must be sorted and unique"
    );
    ensure!(
        frame.native_nearest_cues.is_empty() || !original.pixels.contains(&TRANSPARENT),
        "native nearest cues are limited to opaque original gameplay canvases"
    );
    for &[x, y] in &frame.native_nearest_cues {
        ensure!(
            x < frame.logical_width && y < frame.logical_height,
            "native nearest cue outside original logical canvas"
        );
        ensure!(
            original.pixels[y as usize * original.width + x as usize] < 240,
            "native nearest cue must be an ordinary original source cell"
        );
    }
    ensure!(
        frame.origin == [0, 0],
        "HD format 1 preserves the original top-left anchor [0, 0]"
    );
    ensure!(
        frame.source_sha256 == format!("{:x}", Sha256::digest(source)),
        "original source hash changed; regenerate or review this frame"
    );
    Ok(())
}
fn hex_digest(key: &[u8; 32]) -> String {
    key.iter().map(|byte| format!("{byte:02x}")).collect()
}
fn closest(palette: &[[u8; 3]; 256], rgb: [u8; 3], source_label: u8) -> u16 {
    let range = match source_label {
        240..=244 => 240..245,
        245..=249 => 245..250,
        250..=255 => return source_label as u16,
        _ => 0..240,
    };
    closest_in_range(palette, rgb, range)
}
fn closest_in_range(palette: &[[u8; 3]; 256], rgb: [u8; 3], range: std::ops::Range<usize>) -> u16 {
    palette
        .iter()
        .enumerate()
        .filter(|(index, _)| range.contains(index))
        .min_by_key(|(_, color)| {
            (0..3)
                .map(|j| (color[j] as i32 - rgb[j] as i32).pow(2))
                .sum::<i32>()
        })
        .unwrap()
        .0 as u16
}
#[cfg(test)]
mod tests {
    use super::*;
    use crate::assets::TRANSPARENT;
    fn frame(source: &[u8]) -> Frame {
        Frame {
            frame: 0,
            file: "ship.png".into(),
            logical_width: 2,
            logical_height: 2,
            origin: [0, 0],
            source_sha256: format!("{:x}", Sha256::digest(source)),
            crop: None,
            preserve_reserved_coverage: false,
            native_nearest_cues: Vec::new(),
        }
    }
    #[test]
    fn metadata_cannot_change_original_canvas_or_anchor() {
        let source = b"source";
        let original = Sprite::blank(2, 2);
        let mut f = frame(source);
        assert!(validate_frame(&f, &original, source).is_ok());
        f.logical_width = 3;
        assert!(validate_frame(&f, &original, source).is_err());
        f.logical_width = 2;
        f.origin = [1, 0];
        assert!(validate_frame(&f, &original, source).is_err());
        f.origin = [0, 0];
        assert!(validate_frame(&f, &original, b"changed").is_err());
    }
    #[test]
    fn detailed_art_preserves_canvas_and_transparency_without_filtering_twice() {
        let source = b"source";
        let mut rgba = RgbaImage::new(8, 8);
        for y in 2..6 {
            for x in 2..6 {
                rgba.put_pixel(x, y, image::Rgba([255, 0, 0, 255]));
            }
        }
        let dir = tempfile::tempdir().unwrap();
        rgba.save(dir.path().join("ship.png")).unwrap();
        let mut art = HdAssets {
            root: dir.path().to_path_buf(),
            ..HdAssets::default()
        };
        art.replacements.insert(
            1,
            Replacement {
                frame: frame(source),
                requires_alpha: true,
                source_labels: None,
                validated: false,
                rejected: false,
            },
        );
        let mut palette = [[0; 3]; 256];
        palette[100] = [255, 0, 0];
        let s = art.sprite(1, 4, &palette).unwrap().unwrap();
        assert_eq!((s.width, s.height), (8, 8));
        assert_eq!(s.pixels[0], TRANSPARENT);
        assert_eq!(s.pixels[3 * 8 + 3], 100);
        assert!(art.sprite(2, 4, &palette).unwrap().is_none());
    }
    fn fixture() -> (tempfile::TempDir, Catalog, Manifest) {
        let dir = tempfile::tempdir().unwrap();
        let mut source = Vec::new();
        for n in [1_i32, 0, 0, 2, 2] {
            source.extend(n.to_le_bytes());
        }
        source.extend([1, 2, 3, 4]);
        fs::write(dir.path().join("source"), &source).unwrap();
        fs::write(
            dir.path().join("INDEX"),
            format!("00001 {} source\n", source.len()),
        )
        .unwrap();
        fs::create_dir(dir.path().join("hd")).unwrap();
        let mut png = RgbaImage::new(8, 8);
        for y in 2..6 {
            for x in 2..6 {
                png.put_pixel(x, y, image::Rgba([100, 20, 20, 255]));
            }
        }
        png.save(dir.path().join("hd/ship.png")).unwrap();
        let manifest = Manifest {
            format_version: 1,
            name: "Fixture".into(),
            description: String::new(),
            sequences: vec![Sequence {
                name: "ship".into(),
                base_asset: 1,
                frame_count: 2,
                frames: vec![frame(&source)],
            }],
        };
        let catalog = Catalog::open(dir.path()).unwrap();
        (dir, catalog, manifest)
    }
    fn pack(dir: &Path, catalog: &Catalog, manifest: &Manifest) -> HdAssets {
        fs::write(
            dir.join("hd/hd.json"),
            serde_json::to_vec(manifest).unwrap(),
        )
        .unwrap();
        HdAssets::load(&dir.join("hd"), catalog)
    }
    #[test]
    fn hd_colors_keep_source_animation_classes_at_every_scale() {
        let (dir, catalog, mut manifest) = fixture();
        let rgb = [255, 100, 30];
        RgbaImage::from_pixel(8, 8, image::Rgba([rgb[0], rgb[1], rgb[2], 255]))
            .save(dir.path().join("hd/ship.png"))
            .unwrap();
        let mut palette = [[0; 3]; 256];
        palette[7] = [240, 90, 30];
        palette[244] = rgb;
        palette[245] = rgb;
        palette[251] = rgb;
        let mut ordinary = pack(dir.path(), &catalog, &manifest);
        for scale in 1..=4 {
            let sprite = ordinary.sprite(1, scale, &palette).unwrap().unwrap();
            assert!(
                sprite.pixels.iter().all(|pixel| *pixel == 7),
                "static highlights must not acquire water, fire or blink indices"
            );
        }
        assert_eq!(ordinary.cache_stats().source_label_bytes, 0);

        let mut source = fs::read(dir.path().join("source")).unwrap();
        source[20..24].copy_from_slice(&[5, 242, 247, 253]);
        fs::write(dir.path().join("source"), &source).unwrap();
        manifest.sequences[0].frames[0].source_sha256 = format!("{:x}", Sha256::digest(&source));
        let mut animated = pack(dir.path(), &catalog, &manifest);
        for scale in 1..=4 {
            let sprite = animated.sprite(1, scale, &palette).unwrap().unwrap();
            for y in 0..sprite.height {
                for x in 0..sprite.width {
                    assert_eq!(
                        sprite.pixels[y * sprite.width + x],
                        [7, 244, 245, 253][(y / scale) * 2 + x / scale],
                        "palette class changed at scale {scale}, ({x},{y})"
                    );
                }
            }
        }
        assert_eq!(animated.cache_stats().source_label_bytes, 4);
        assert!(animated.cache_stats().source_label_bytes <= MAX_SOURCE_LABEL_BYTES);
    }
    #[test]
    fn static_card_palettes_use_all_colors_without_crossing_gameplay_cache_policy() {
        let (dir, catalog, mut manifest) = fixture();
        let rgb = [255, 100, 30];
        RgbaImage::from_pixel(8, 8, image::Rgba([rgb[0], rgb[1], rgb[2], 255]))
            .save(dir.path().join("hd/ship.png"))
            .unwrap();
        let mut source = fs::read(dir.path().join("source")).unwrap();
        source[20..24].copy_from_slice(&[5, 242, 247, 253]);
        fs::write(dir.path().join("source"), &source).unwrap();
        manifest.sequences[0].frames[0].source_sha256 = format!("{:x}", Sha256::digest(&source));
        let mut assets = pack(dir.path(), &catalog, &manifest);
        let mut palette = [[0; 3]; 256];
        for index in [7, 243, 247] {
            palette[index] = [240, 90, 30];
        }
        palette[251] = rgb;
        for scale in 1..=4 {
            for static_palette in [true, false, true] {
                let sprite = if static_palette {
                    assets.sprite_static_palette(1, scale, &palette)
                } else {
                    assets.sprite(1, scale, &palette)
                }
                .unwrap()
                .unwrap();
                for y in 0..sprite.height {
                    for x in 0..sprite.width {
                        assert_eq!(
                            sprite.pixels[y * sprite.width + x],
                            if static_palette {
                                251
                            } else {
                                [7, 243, 247, 253][(y / scale) * 2 + x / scale]
                            },
                            "palette policy collision: static={static_palette}, scale={scale}"
                        );
                    }
                }
            }
        }
        let before = assets.cache_stats();
        assert_eq!(before.indexed_entries, 8);
        assert_eq!(before.png_decodes, 1);
        palette[251] = [0; 3];
        palette[252] = rgb;
        assert!(
            assets
                .sprite_static_palette(1, 4, &palette)
                .unwrap()
                .unwrap()
                .pixels
                .iter()
                .all(|pixel| *pixel == 252)
        );
        let after = assets.cache_stats();
        assert_eq!(after.indexed_entries, 9);
        assert_eq!(after.png_decodes, before.png_decodes);
        assert_eq!(after.rgba_bytes, before.rgba_bytes);
        assert_eq!(after.disk_writes, before.disk_writes);
    }
    #[test]
    fn source_checked_pack_reports_partial_coverage_and_rejects_changed_data() {
        let (dir, catalog, mut manifest) = fixture();
        let assets = pack(dir.path(), &catalog, &manifest);
        assert_eq!(assets.coverage(), 1);
        assert!(assets.diagnostics[0].contains("1 of 2 frames"));
        manifest.sequences[0].frames[0].source_sha256 = "changed".into();
        let assets = pack(dir.path(), &catalog, &manifest);
        assert_eq!(assets.coverage(), 0);
        assert!(
            assets
                .diagnostics
                .iter()
                .any(|m| m.contains("source hash changed"))
        );
    }
    #[test]
    fn invalid_atlas_and_path_cannot_escape_original_canvas() {
        let (dir, catalog, mut manifest) = fixture();
        manifest.sequences[0].frames[0].crop = Some([0, 0, 9, 8]);
        let assets = pack(dir.path(), &catalog, &manifest);
        assert_eq!(assets.coverage(), 0);
        assert!(
            assets
                .diagnostics
                .iter()
                .any(|m| m.contains("crop exceeds"))
        );
        manifest.sequences[0].frames[0].crop = None;
        manifest.sequences[0].frames[0].file = "../source".into();
        let assets = pack(dir.path(), &catalog, &manifest);
        assert_eq!(assets.coverage(), 0);
        assert!(assets.diagnostics.iter().any(|m| m.contains("stay inside")));
    }
    #[test]
    fn duplicate_sequence_ids_reject_pack_atomically() {
        let (dir, catalog, mut manifest) = fixture();
        let duplicate = manifest.sequences[0].clone();
        manifest.sequences.push(duplicate);
        let assets = pack(dir.path(), &catalog, &manifest);
        assert_eq!(assets.coverage(), 0);
        assert!(
            assets
                .diagnostics
                .iter()
                .any(|m| m.contains("duplicate HD asset"))
        );
    }
    #[test]
    fn missing_pack_is_clean_fallback() {
        let dir = tempfile::tempdir().unwrap();
        // Build a real minimal catalog so the public loading path is exercised.
        fs::write(dir.path().join("a"), []).unwrap();
        fs::write(dir.path().join("INDEX"), "00001 0 a\n").unwrap();
        let catalog = Catalog::open(dir.path()).unwrap();
        let art = HdAssets::load(&dir.path().join("missing"), &catalog);
        assert_eq!(art.coverage(), 0);
        assert!(art.diagnostics.is_empty());
    }
    #[test]
    fn opaque_originals_accept_opaque_hd_but_transparent_originals_require_alpha() {
        let (dir, catalog, manifest) = fixture();
        let png_path = dir
            .path()
            .join("hd")
            .join(&manifest.sequences[0].frames[0].file);
        image::RgbaImage::from_pixel(8, 8, image::Rgba([80, 100, 120, 255]))
            .save(&png_path)
            .unwrap();
        let source = catalog.read(manifest.sequences[0].base_asset).unwrap();
        let original = Sprite::decode(&source).unwrap();
        let assets = pack(dir.path(), &catalog, &manifest);
        if original.pixels.contains(&TRANSPARENT) {
            assert_eq!(assets.coverage(), 0);
        } else {
            assert_eq!(assets.coverage(), 1);
        }
        // A genuine span sprite must keep transparent negative space.
        let span = [0_i32, 0, 0, 2, 2, 0, 0, 0, 1]
            .into_iter()
            .flat_map(i32::to_le_bytes)
            .chain([7])
            .chain([0_i32, 0, -1, 0].into_iter().flat_map(i32::to_le_bytes))
            .collect::<Vec<_>>();
        std::fs::write(dir.path().join("source"), &span).unwrap();
        std::fs::write(
            dir.path().join("INDEX"),
            format!("00001 {} source\n", span.len()),
        )
        .unwrap();
        let catalog = Catalog::open(dir.path()).unwrap();
        let mut manifest = manifest;
        manifest.sequences[0].frames[0].source_sha256 = format!("{:x}", Sha256::digest(&span));
        let assets = pack(dir.path(), &catalog, &manifest);
        assert_eq!(assets.coverage(), 0);
        assert!(
            assets
                .diagnostics
                .iter()
                .any(|diagnostic| diagnostic.contains("transparent background"))
        );
    }
    fn lazy_pack(
        dir: &Path,
        catalog: &Catalog,
        manifest: &Manifest,
        cache: Option<&Path>,
    ) -> HdAssets {
        fs::write(
            dir.join("hd/hd.json"),
            serde_json::to_vec(manifest).unwrap(),
        )
        .unwrap();
        HdAssets::load_lazy(&dir.join("hd"), catalog, cache)
    }
    #[test]
    fn full_catalog_sized_pack_registers_and_validates_without_resident_growth() {
        let (dir, _, mut manifest) = fixture();
        let source = fs::read(dir.path().join("source")).unwrap();
        let count = 5753;
        fs::write(
            dir.path().join("INDEX"),
            (1..=count)
                .map(|id| format!("{id:05x} {} source\n", source.len()))
                .collect::<String>(),
        )
        .unwrap();
        let catalog = Catalog::open(dir.path()).unwrap();
        manifest.sequences = (1..=count)
            .map(|id| Sequence {
                name: format!("asset-{id}"),
                base_asset: id,
                frame_count: 1,
                frames: vec![frame(&source)],
            })
            .collect();
        let mut assets = lazy_pack(dir.path(), &catalog, &manifest, None);
        assert!(assets.diagnostics.is_empty());
        assert_eq!(assets.registered_count(), count as usize);
        assert_eq!(assets.coverage(), 0);
        assert_eq!(assets.cache_stats().png_decodes, 0);
        assets.sprite(5000, 4, &[[0; 3]; 256]).unwrap().unwrap();
        assert_eq!(assets.validated_count(), 1);
        let report = assets.validate_all();
        assert_eq!(
            report,
            ValidationReport {
                registered: count as usize,
                validated: count as usize,
                rejected: 0
            }
        );
        let stats = assets.cache_stats();
        assert_eq!(stats.png_decodes, 1);
        assert!(stats.atlas_bytes + stats.rgba_bytes + stats.indexed_bytes < 1024);
    }
    #[test]
    fn lazy_corrupt_png_falls_back_once_and_never_claims_decoded_coverage() {
        let (dir, catalog, manifest) = fixture();
        fs::write(dir.path().join("hd/ship.png"), b"corrupt png").unwrap();
        let mut assets = lazy_pack(dir.path(), &catalog, &manifest, None);
        assert_eq!(assets.registered_count(), 1);
        assert_eq!(assets.validated_count(), 0);
        assert!(assets.sprite(1, 4, &[[0; 3]; 256]).unwrap().is_none());
        let diagnostics = assets.diagnostics.len();
        assert!(assets.sprite(1, 4, &[[0; 3]; 256]).unwrap().is_none());
        assert_eq!(assets.diagnostics.len(), diagnostics);
        assert_eq!(assets.registered_count(), 0);
        assert_eq!(assets.coverage(), 0);
    }
    #[test]
    fn indexed_cache_tracks_palette_identity() {
        let (dir, catalog, manifest) = fixture();
        let mut assets = lazy_pack(dir.path(), &catalog, &manifest, None);
        let mut palette = [[0; 3]; 256];
        palette[100] = [100, 20, 20];
        assert_eq!(
            assets.sprite(1, 4, &palette).unwrap().unwrap().pixels[3 * 8 + 3],
            100
        );
        palette[100] = [0, 0, 0];
        palette[101] = [100, 20, 20];
        assert_eq!(
            assets.sprite(1, 4, &palette).unwrap().unwrap().pixels[3 * 8 + 3],
            101
        );
        assert_eq!(assets.cache_stats().indexed_entries, 2);
        assert_eq!(assets.cache_stats().png_decodes, 1);
    }
    #[test]
    fn megapixel_sources_keep_only_four_times_logical_rgba() {
        let (dir, catalog, manifest) = fixture();
        RgbaImage::from_pixel(1024, 1024, image::Rgba([100, 20, 20, 255]))
            .save(dir.path().join("hd/ship.png"))
            .unwrap();
        let mut assets = lazy_pack(dir.path(), &catalog, &manifest, None);
        let sprite = assets.sprite(1, 4, &[[0; 3]; 256]).unwrap().unwrap();
        assert_eq!((sprite.width, sprite.height), (8, 8));
        assert_eq!(assets.cache_stats().rgba_bytes, 8 * 8 * 4);
        assert!(assets.cache_stats().atlas_bytes <= CACHE_BYTES);
    }
    #[test]
    fn adjacent_atlas_frames_share_decode_across_lru_evictions() {
        let (dir, _, mut manifest) = fixture();
        let source = fs::read(dir.path().join("source")).unwrap();
        fs::write(
            dir.path().join("INDEX"),
            (1..=3)
                .map(|id| format!("{id:05x} {} source\n", source.len()))
                .collect::<String>(),
        )
        .unwrap();
        let catalog = Catalog::open(dir.path()).unwrap();
        let mut atlas = RgbaImage::new(24, 8);
        for frame in 0..3 {
            for y in 2..6 {
                for x in 2..6 {
                    atlas.put_pixel(
                        frame * 8 + x,
                        y,
                        image::Rgba([50 + frame as u8 * 50, 20, 20, 255]),
                    );
                }
            }
        }
        atlas.save(dir.path().join("hd/ship.png")).unwrap();
        manifest.sequences[0].frame_count = 3;
        manifest.sequences[0].frames = (0..3)
            .map(|index| {
                let mut frame = frame(&source);
                frame.frame = index;
                frame.crop = Some([index * 8, 0, 8, 8]);
                frame
            })
            .collect();
        let mut assets = lazy_pack(dir.path(), &catalog, &manifest, None);
        assets.rgba.limit = 8 * 8 * 4;
        assets.scaled.limit = 8 * 8 * 2;
        let mut palette = [[0; 3]; 256];
        for index in 0..3 {
            palette[100 + index] = [50 + index as u8 * 50, 20, 20];
        }
        for id in [1, 2, 3, 1] {
            let sprite = assets.sprite(id, 4, &palette).unwrap().unwrap();
            assert_eq!(sprite.pixels[3 * 8 + 3], 100 + id as u16 - 1);
            let stats = assets.cache_stats();
            assert!(stats.rgba_bytes <= 256 && stats.indexed_bytes <= 128);
        }
        assert_eq!(assets.cache_stats().png_decodes, 1);
        assert_eq!(assets.validated_count(), 3);
        assert_eq!(assets.cache_stats().indexed_entries, 1);
    }
    #[test]
    fn derived_cache_verifies_checksums_and_binds_png_and_source_identity() {
        let (dir, catalog, manifest) = fixture();
        let cache = dir.path().join("cache");
        let mut first = lazy_pack(dir.path(), &catalog, &manifest, Some(&cache));
        first.sprite(1, 4, &[[0; 3]; 256]).unwrap().unwrap();
        assert_eq!(first.cache_stats().disk_writes, 1);
        let cached = fs::read_dir(&cache)
            .unwrap()
            .next()
            .unwrap()
            .unwrap()
            .path();
        let mut bytes = fs::read(&cached).unwrap();
        *bytes.last_mut().unwrap() ^= 1;
        fs::write(&cached, bytes).unwrap();
        let mut second = lazy_pack(dir.path(), &catalog, &manifest, Some(&cache));
        second.sprite(1, 4, &[[0; 3]; 256]).unwrap().unwrap();
        assert!(
            second
                .diagnostics
                .iter()
                .any(|message| message.contains("checksum mismatch"))
        );
        assert_eq!(second.cache_stats().png_decodes, 1);
        let mut third = lazy_pack(dir.path(), &catalog, &manifest, Some(&cache));
        third.sprite(1, 4, &[[0; 3]; 256]).unwrap().unwrap();
        assert_eq!(third.cache_stats().png_decodes, 0);
        assert_eq!(third.cache_stats().disk_hits, 1);
        // New PNG contents must not reuse the previous derived frame.
        RgbaImage::from_pixel(8, 8, image::Rgba([10, 30, 80, 255]))
            .save(dir.path().join("hd/ship.png"))
            .unwrap();
        let mut fourth = lazy_pack(dir.path(), &catalog, &manifest, Some(&cache));
        fourth.sprite(1, 4, &[[0; 3]; 256]).unwrap().unwrap();
        assert_eq!(fourth.cache_stats().disk_hits, 0);
        assert_eq!(fourth.cache_stats().png_decodes, 1);
        assert_eq!(fs::read_dir(&cache).unwrap().count(), 2);
        // A reviewed new original payload creates a distinct cache identity.
        let mut changed_source = fs::read(dir.path().join("source")).unwrap();
        changed_source[20] = 9;
        fs::write(dir.path().join("source"), &changed_source).unwrap();
        let catalog = Catalog::open(dir.path()).unwrap();
        let mut changed_manifest = manifest.clone();
        changed_manifest.sequences[0].frames[0].source_sha256 =
            format!("{:x}", Sha256::digest(&changed_source));
        let mut fifth = lazy_pack(dir.path(), &catalog, &changed_manifest, Some(&cache));
        fifth.sprite(1, 4, &[[0; 3]; 256]).unwrap().unwrap();
        assert_eq!(fifth.cache_stats().disk_hits, 0);
        assert_eq!(fifth.cache_stats().png_decodes, 1);
        assert_eq!(fs::read_dir(&cache).unwrap().count(), 3);
        // An unreviewed changed original remains rejected while cache files exist.
        let mut invalid_manifest = manifest;
        invalid_manifest.sequences[0].frames[0].source_sha256 = "changed".into();
        let mut rejected = lazy_pack(dir.path(), &catalog, &invalid_manifest, Some(&cache));
        assert_eq!(rejected.registered_count(), 0);
        assert!(rejected.sprite(1, 4, &[[0; 3]; 256]).unwrap().is_none());
    }
    #[cfg(unix)]
    #[test]
    fn lazy_artwork_and_derived_cache_cannot_follow_escaping_symlinks() {
        use std::os::unix::fs::symlink;
        let (dir, catalog, manifest) = fixture();
        let outside = tempfile::tempdir().unwrap();
        let cache = dir.path().join("cache");
        let mut assets = lazy_pack(dir.path(), &catalog, &manifest, Some(&cache));
        assets.sprite(1, 4, &[[0; 3]; 256]).unwrap().unwrap();
        let cached = fs::read_dir(&cache)
            .unwrap()
            .next()
            .unwrap()
            .unwrap()
            .path();
        let outside_file = outside.path().join("must-stay");
        fs::write(&outside_file, b"original").unwrap();
        fs::remove_file(&cached).unwrap();
        symlink(&outside_file, &cached).unwrap();
        let mut again = lazy_pack(dir.path(), &catalog, &manifest, Some(&cache));
        again.sprite(1, 4, &[[0; 3]; 256]).unwrap().unwrap();
        assert_eq!(fs::read(&outside_file).unwrap(), b"original");
        assert!(
            again
                .diagnostics
                .iter()
                .any(|message| message.contains("symlink escapes"))
        );
        let artwork = dir.path().join("hd/ship.png");
        fs::remove_file(&artwork).unwrap();
        symlink(&outside_file, &artwork).unwrap();
        // Repeat draws must check containment before reusing their indexed cache.
        assert!(assets.sprite(1, 4, &[[0; 3]; 256]).unwrap().is_none());
        assert!(
            assets
                .diagnostics
                .iter()
                .any(|message| message.contains("symlink escapes"))
        );
    }
    #[test]
    fn lru_eviction_preserves_recently_used_entries() {
        let mut cache = LruCache::new(8);
        cache.insert(1, "first", 4);
        cache.insert(2, "second", 4);
        assert_eq!(cache.get(&1), Some(&"first"));
        cache.insert(3, "third", 4);
        assert_eq!(cache.get(&2), None);
        assert_eq!(cache.get(&1), Some(&"first"));
        assert_eq!(cache.get(&3), Some(&"third"));
        assert_eq!(cache.bytes, 8);
    }

    #[test]
    fn derived_disk_budget_evicts_only_generated_cache_files() {
        let (dir, catalog, manifest) = fixture();
        let cache = dir.path().join("cache");
        fs::create_dir(&cache).unwrap();
        fs::write(cache.join("leave-me.txt"), b"keep").unwrap();
        let mut assets = lazy_pack(dir.path(), &catalog, &manifest, Some(&cache));
        // Exactly one 8x8 derived RGBA frame plus its checked header fits.
        assets.disk_limit = (CACHE_HEADER + 8 * 8 * 4) as u64;
        assets.sprite(1, 4, &[[0; 3]; 256]).unwrap().unwrap();
        RgbaImage::from_pixel(8, 8, image::Rgba([11, 31, 81, 255]))
            .save(dir.path().join("hd/ship.png"))
            .unwrap();
        let mut updated = lazy_pack(dir.path(), &catalog, &manifest, Some(&cache));
        updated.disk_limit = assets.disk_limit;
        updated.sprite(1, 4, &[[0; 3]; 256]).unwrap().unwrap();
        let generated: Vec<_> = fs::read_dir(&cache)
            .unwrap()
            .map(Result::unwrap)
            .filter(|entry| {
                entry
                    .path()
                    .extension()
                    .is_some_and(|extension| extension == "rgba")
            })
            .collect();
        assert_eq!(generated.len(), 1);
        assert!(generated[0].metadata().unwrap().len() <= assets.disk_limit);
        assert_eq!(fs::read(cache.join("leave-me.txt")).unwrap(), b"keep");
        assert_eq!(updated.cache_stats().disk_writes, 1);
        assert!(
            updated
                .diagnostics
                .iter()
                .all(|message| !message.contains("derived cache"))
        );
    }
    #[test]
    #[ignore = "requires the local original catalog and generated HD artwork"]
    fn original_hd_pack_validates_with_bounded_residency() {
        let root = std::env::var_os("RAPTOR_TEST_DATA").expect("set RAPTOR_TEST_DATA");
        let catalog = Catalog::open(PathBuf::from(root)).unwrap();
        let mut assets = HdAssets::load_lazy(&catalog.root.join("hd"), &catalog, None);
        let registered = assets.registered_count();
        assert!(
            registered > 0,
            "local HD pack is missing or invalid: {:?}",
            assets.diagnostics
        );
        let report = assets.validate_all();
        assert_eq!(report.registered, registered, "{:?}", assets.diagnostics);
        assert_eq!(report.validated, registered, "{:?}", assets.diagnostics);
        assert_eq!(report.rejected, 0, "{:?}", assets.diagnostics);
        let palette = catalog.palette().unwrap();
        let ids: Vec<_> = assets.replacements.keys().copied().collect();
        for id in ids {
            for scale in 1..=4 {
                let sprite = assets.sprite(id, scale, &palette).unwrap().unwrap();
                let frame = &assets.replacements.get(&id).unwrap().frame;
                assert_eq!(
                    (sprite.width, sprite.height),
                    (
                        frame.logical_width as usize * scale,
                        frame.logical_height as usize * scale
                    )
                );
                assert!(sprite.pixels.iter().any(|pixel| *pixel != TRANSPARENT));
                let stats = assets.cache_stats();
                assert!(
                    stats.atlas_bytes <= CACHE_BYTES
                        && stats.rgba_bytes <= CACHE_BYTES
                        && stats.indexed_bytes <= CACHE_BYTES
                );
            }
        }
        println!(
            "HD checked {} frames at scales 1..4; cache stats {:?}",
            registered,
            assets.cache_stats()
        );
    }
    #[test]
    fn oversized_png_is_rejected_before_decode_or_resident_allocation() {
        let (dir, catalog, manifest) = fixture();
        RgbaImage::from_pixel(4097, 1, image::Rgba([100, 20, 20, 255]))
            .save(dir.path().join("hd/ship.png"))
            .unwrap();
        let mut assets = lazy_pack(dir.path(), &catalog, &manifest, None);
        assert!(assets.sprite(1, 4, &[[0; 3]; 256]).unwrap().is_none());
        assert_eq!(assets.cache_stats().png_decodes, 0);
        assert_eq!(assets.cache_stats().atlas_bytes, 0);
        assert_eq!(assets.cache_stats().rgba_bytes, 0);
        assert!(
            assets
                .diagnostics
                .iter()
                .any(|message| message.contains("limit") || message.contains("dimension"))
        );
    }
    fn aspect_info(width: u32, height: u32) -> PngInfo {
        PngInfo {
            size: 0,
            modified: None,
            digest: [0; 32],
            width,
            height,
        }
    }
    fn aspect_frame(width: u32, height: u32) -> Frame {
        let mut f = frame(b"synthetic source");
        f.logical_width = width;
        f.logical_height = height;
        f
    }
    #[test]
    fn opaque_full_frame_accepts_only_common_scale_integer_rounding() {
        let mut f = aspect_frame(320, 200);
        let info = aspect_info(1586, 992);
        assert_eq!(frame_dimensions(&f, &info, false).unwrap(), (1586, 992));
        f.crop = Some([0, 0, 1586, 992]);
        assert_eq!(frame_dimensions(&f, &info, false).unwrap(), (1586, 992));
        // Swapping both logical and artwork axes retains the same rule.
        let portrait = aspect_frame(200, 320);
        assert!(frame_dimensions(&portrait, &aspect_info(992, 1586), false).is_ok());
        // The PNG can be generated at any common scale, not just an integer one.
        assert!(frame_dimensions(&aspect_frame(8, 5), &aspect_info(17, 11), false).is_ok());
        for (width, height) in [
            (1280, 799),
            (1280, 801),
            (1587, 991),
            (1586, 993),
            (1024, 1024),
        ] {
            assert!(
                frame_dimensions(&aspect_frame(320, 200), &aspect_info(width, height), false)
                    .is_err()
            );
        }
        // Equal square axes cannot be rounded in conflicting directions at a tie.
        assert!(!integer_rounded_aspect(5, 6, 2, 2));
        assert!(!integer_rounded_aspect(0, 6, 2, 2));
        assert!(!integer_rounded_aspect(5, 6, 0, 2));
        // Arithmetic is bounded even for values beyond valid image dimensions.
        assert!(integer_rounded_aspect(
            u32::MAX,
            u32::MAX,
            u32::MAX,
            u32::MAX
        ));
        assert!(!integer_rounded_aspect(u32::MAX, 1, 1, u32::MAX));
    }
    #[test]
    fn rounded_exception_never_admits_transparent_sources_partial_crops_or_low_resolution() {
        let mut f = aspect_frame(320, 200);
        assert!(frame_dimensions(&f, &aspect_info(1586, 992), true).is_err());
        f.crop = Some([1, 0, 1586, 992]);
        assert!(frame_dimensions(&f, &aspect_info(1587, 992), false).is_err());
        f.crop = Some([0, 0, 1586, 992]);
        assert!(frame_dimensions(&f, &aspect_info(1600, 1000), false).is_err());
        // Exact-ratio atlas crops and transparent artwork keep existing semantics.
        f.crop = Some([8, 8, 1280, 800]);
        assert!(frame_dimensions(&f, &aspect_info(1600, 1000), true).is_ok());
        assert!(frame_dimensions(&aspect_frame(8, 5), &aspect_info(15, 10), false).is_err());
    }
    #[test]
    fn rounded_dimensions_generated_by_one_scale_are_accepted() {
        // Independent fixtures generated by conventional nearest-integer rounding
        // at 1/64 scale steps, including ties, portrait ratios and tiny canvases.
        let mut checked = 0;
        for logical_width in 1_u32..=16 {
            for logical_height in 1_u32..=16 {
                for scale_numerator in 128_u32..=1024 {
                    let width = (logical_width * scale_numerator + 32) / 64;
                    let height = (logical_height * scale_numerator + 32) / 64;
                    assert!(integer_rounded_aspect(
                        width,
                        height,
                        logical_width,
                        logical_height
                    ));
                    checked += 1;
                }
            }
        }
        assert_eq!(checked, 229632);
    }
    fn rectangular_opaque_fixture() -> (tempfile::TempDir, Catalog, Manifest) {
        let (dir, _, mut manifest) = fixture();
        let mut source = [1_i32, 0, 0, 8, 5]
            .into_iter()
            .flat_map(i32::to_le_bytes)
            .collect::<Vec<_>>();
        source.extend([7_u8; 40]);
        fs::write(dir.path().join("source"), &source).unwrap();
        fs::write(
            dir.path().join("INDEX"),
            format!("00001 {} source\n", source.len()),
        )
        .unwrap();
        let catalog = Catalog::open(dir.path()).unwrap();
        let f = &mut manifest.sequences[0].frames[0];
        f.logical_width = 8;
        f.logical_height = 5;
        f.source_sha256 = format!("{:x}", Sha256::digest(&source));
        manifest.sequences[0].frame_count = 1;
        RgbaImage::from_pixel(17, 11, image::Rgba([80, 100, 120, 255]))
            .save(dir.path().join("hd/ship.png"))
            .unwrap();
        (dir, catalog, manifest)
    }
    #[test]
    fn actual_rounded_png_loads_all_scales_and_warms_its_validated_disk_cache() {
        let (dir, catalog, manifest) = rectangular_opaque_fixture();
        let cache = dir.path().join("cache");
        let mut first = lazy_pack(dir.path(), &catalog, &manifest, Some(&cache));
        for scale in 1..=4 {
            let sprite = first.sprite(1, scale, &[[0; 3]; 256]).unwrap().unwrap();
            assert_eq!((sprite.width, sprite.height), (8 * scale, 5 * scale));
            assert!(sprite.pixels.iter().all(|pixel| *pixel != TRANSPARENT));
        }
        assert!(first.diagnostics.is_empty(), "{:?}", first.diagnostics);
        assert_eq!(first.cache_stats().png_decodes, 1);
        assert_eq!(first.cache_stats().disk_writes, 1);
        let mut warm = lazy_pack(dir.path(), &catalog, &manifest, Some(&cache));
        warm.sprite(1, 4, &[[0; 3]; 256]).unwrap().unwrap();
        assert_eq!(warm.cache_stats().disk_hits, 1);
        assert_eq!(warm.cache_stats().png_decodes, 0);
        assert!(warm.diagnostics.is_empty());
    }
    #[test]
    fn a_single_nonopaque_raw_pixel_cannot_be_hidden_by_resampling_or_a_warm_cache() {
        let (dir, catalog, manifest) = rectangular_opaque_fixture();
        let cache = dir.path().join("cache");
        let mut first = lazy_pack(dir.path(), &catalog, &manifest, Some(&cache));
        first.sprite(1, 4, &[[0; 3]; 256]).unwrap().unwrap();
        for alpha in [0, 128, 254] {
            // An isolated defect well above the four-times resident resolution.
            let mut raw = RgbaImage::from_pixel(161, 101, image::Rgba([80, 100, 120, 255]));
            raw.put_pixel(160, 100, image::Rgba([80, 100, 120, alpha]));
            raw.save(dir.path().join("hd/ship.png")).unwrap();
            let mut changed = lazy_pack(dir.path(), &catalog, &manifest, Some(&cache));
            assert!(changed.sprite(1, 4, &[[0; 3]; 256]).unwrap().is_none());
            assert_eq!(changed.cache_stats().disk_hits, 0);
            assert_eq!(changed.cache_stats().disk_writes, 0);
            assert!(
                changed
                    .diagnostics
                    .iter()
                    .any(|line| line.contains("fully opaque"))
            );
        }
    }
    #[test]
    fn checksum_valid_nonopaque_rounded_cache_is_rebuilt_from_original_png() {
        let (dir, catalog, manifest) = rectangular_opaque_fixture();
        let cache = dir.path().join("cache");
        let mut first = lazy_pack(dir.path(), &catalog, &manifest, Some(&cache));
        first.sprite(1, 4, &[[0; 3]; 256]).unwrap().unwrap();
        let path = fs::read_dir(&cache)
            .unwrap()
            .next()
            .unwrap()
            .unwrap()
            .path();
        let mut bytes = fs::read(&path).unwrap();
        bytes[CACHE_HEADER + 3] = 254;
        let checksum = Sha256::digest(&bytes[CACHE_HEADER..]);
        bytes[48..80].copy_from_slice(&checksum);
        fs::write(&path, bytes).unwrap();
        let mut changed = lazy_pack(dir.path(), &catalog, &manifest, Some(&cache));
        assert!(changed.sprite(1, 4, &[[0; 3]; 256]).unwrap().is_some());
        assert_eq!(changed.cache_stats().disk_hits, 0);
        assert_eq!(changed.cache_stats().png_decodes, 1);
        assert!(
            changed
                .diagnostics
                .iter()
                .any(|line| line.contains("fully opaque"))
        );
        let mut healed = lazy_pack(dir.path(), &catalog, &manifest, Some(&cache));
        healed.sprite(1, 4, &[[0; 3]; 256]).unwrap().unwrap();
        assert_eq!(healed.cache_stats().disk_hits, 1);
    }
    #[test]
    fn rounded_cache_identity_is_separate_and_exact_frame_keys_are_unchanged() {
        fn previous_key(frame: &Frame, info: &PngInfo, requires_alpha: bool) -> [u8; 32] {
            let mut digest = Sha256::new();
            digest.update(KERNEL_VERSION);
            digest.update(info.digest);
            digest.update(frame.source_sha256.as_bytes());
            digest.update(frame.logical_width.to_le_bytes());
            digest.update(frame.logical_height.to_le_bytes());
            for value in frame.origin {
                digest.update(value.to_le_bytes());
            }
            digest.update([u8::from(requires_alpha), u8::from(frame.crop.is_some())]);
            if let Some(crop) = frame.crop {
                for value in crop {
                    digest.update(value.to_le_bytes());
                }
            }
            digest.finalize().into()
        }
        let mut f = aspect_frame(320, 200);
        for info in [aspect_info(1600, 1000), aspect_info(1280, 800)] {
            for requires_alpha in [false, true] {
                assert_eq!(
                    HdAssets::frame_key(&f, &info, requires_alpha),
                    previous_key(&f, &info, requires_alpha)
                );
            }
        }
        f.crop = Some([10, 20, 1280, 800]);
        assert_eq!(
            HdAssets::frame_key(&f, &aspect_info(1600, 1000), false),
            previous_key(&f, &aspect_info(1600, 1000), false)
        );
        f.crop = Some([0, 0, 1586, 992]);
        assert_ne!(
            HdAssets::frame_key(&f, &aspect_info(1586, 992), false),
            previous_key(&f, &aspect_info(1586, 992), false)
        );
    }
}

#[cfg(test)]
mod policy_proposal_tests {
    use super::*;
    fn frame() -> Frame {
        Frame {
            frame: 0,
            file: "a.png".into(),
            logical_width: 2,
            logical_height: 2,
            origin: [0, 0],
            source_sha256: "00".into(),
            crop: None,
            preserve_reserved_coverage: false,
            native_nearest_cues: Vec::new(),
        }
    }
    fn assets(label: u8, mode: bool, rgba: RgbaImage) -> (tempfile::TempDir, HdAssets) {
        let dir = tempfile::tempdir().unwrap();
        rgba.save(dir.path().join("a.png")).unwrap();
        let mut f = frame();
        f.preserve_reserved_coverage = mode;
        let mut h = HdAssets {
            root: dir.path().to_path_buf(),
            ..HdAssets::default()
        };
        h.replacements.insert(
            1,
            Replacement {
                frame: f,
                requires_alpha: true,
                source_labels: Some(vec![label, 0, 0, 0]),
                validated: false,
                rejected: false,
            },
        );
        (dir, h)
    }
    fn feathered() -> RgbaImage {
        let mut raw = RgbaImage::new(8, 8);
        for y in 0..4 {
            for x in 1..4 {
                raw.put_pixel(x, y, image::Rgba([0, 220, 80, 255]));
            }
        }
        raw
    }
    #[test]
    fn reserved_opt_in_restores_supported_feathered_cell_at_every_scale() {
        let (_dir, mut h) = assets(253, true, feathered());
        for scale in 1..=4 {
            let s = h.sprite(1, scale, &[[0; 3]; 256]).unwrap().unwrap();
            for y in 0..scale {
                for x in 0..scale {
                    assert_eq!(s.pixels[y * s.width + x], 253);
                }
            }
            assert_eq!(*s.pixels.last().unwrap(), TRANSPARENT);
        }
    }
    #[test]
    fn default_keeps_alpha_cutoff_before_existing_source_labels() {
        let (_dir, mut h) = assets(253, false, feathered());
        let s = h.sprite(1, 4, &[[0; 3]; 256]).unwrap().unwrap();
        assert_eq!(s.pixels[0], TRANSPARENT);
        assert_eq!(s.pixels[1], 253);
    }
    #[test]
    fn opt_in_does_not_restore_missing_or_sparse_reserved_art() {
        for sparse in [false, true] {
            let mut raw = RgbaImage::new(8, 8);
            for y in 4..8 {
                for x in 4..8 {
                    raw.put_pixel(x, y, image::Rgba([240, 20, 30, 255]));
                }
            }
            if sparse {
                raw.put_pixel(3, 3, image::Rgba([0, 255, 0, 255]));
            }
            let (_dir, mut h) = assets(253, true, raw);
            for scale in 1..=4 {
                let s = h.sprite(1, scale, &[[0; 3]; 256]).unwrap().unwrap();
                assert_eq!(s.pixels[0], TRANSPARENT, "missing lamp was invented");
            }
        }
    }
    #[test]
    fn no_new_reserved_or_water_fire_coverage_at_non_flash_locations() {
        for label in [0, 239, 240, 244, 245, 249] {
            let (_dir, mut h) = assets(label, true, feathered());
            let s = h.sprite(1, 4, &[[0; 3]; 256]).unwrap().unwrap();
            assert_eq!(s.pixels[0], TRANSPARENT, "only250..255 may be preserved");
            assert!(s.pixels.iter().all(|&i| i == TRANSPARENT || i < 250));
        }
    }
    #[test]
    fn source_cue_policy_never_changes_static_palette_alpha() {
        let (_a, mut legacy) = assets(253, false, feathered());
        let (_b, mut policy) = assets(253, true, feathered());
        let mut p = [[0; 3]; 256];
        p[255] = [0, 220, 80];
        for scale in 1..=4 {
            assert_eq!(
                legacy
                    .sprite_static_palette(1, scale, &p)
                    .unwrap()
                    .unwrap()
                    .pixels,
                policy
                    .sprite_static_palette(1, scale, &p)
                    .unwrap()
                    .unwrap()
                    .pixels
            );
        }
    }
    #[test]
    fn legacy_frame_serialization_and_cache_identity_stay_exact() {
        let f = frame();
        let serialized = serde_json::to_value(&f).unwrap();
        assert!(serialized.get("preserve_reserved_coverage").is_none());
        assert!(serialized.get("native_nearest_cues").is_none());
        let round: Frame = serde_json::from_value(serialized).unwrap();
        assert!(!round.preserve_reserved_coverage);
        assert!(round.native_nearest_cues.is_empty());
        let info = PngInfo {
            size: 1,
            modified: None,
            digest: [19; 32],
            width: 8,
            height: 8,
        };
        // Old algorithm independently enumerated, with no policy namespace.
        let mut old = Sha256::new();
        old.update(KERNEL_VERSION);
        old.update(info.digest);
        old.update(f.source_sha256.as_bytes());
        old.update(f.logical_width.to_le_bytes());
        old.update(f.logical_height.to_le_bytes());
        for v in f.origin {
            old.update(v.to_le_bytes());
        }
        old.update([1, 0]);
        assert_eq!(
            HdAssets::frame_key(&f, &info, true),
            <[u8; 32]>::from(old.finalize())
        );
        let mut coverage = f.clone();
        coverage.preserve_reserved_coverage = true;
        let mut nearest = f.clone();
        nearest.native_nearest_cues = vec![[0, 0]];
        assert_ne!(
            HdAssets::frame_key(&f, &info, true),
            HdAssets::frame_key(&coverage, &info, true)
        );
        assert_ne!(
            HdAssets::frame_key(&coverage, &info, true),
            HdAssets::frame_key(&nearest, &info, true)
        );
        assert_ne!(
            HdAssets::frame_key(&nearest, &info, true),
            HdAssets::frame_key(&f, &info, true)
        );
    }
    #[test]
    fn native_nearest_is_restricted_to_opaque_original_canvas() {
        let mut f = frame();
        f.native_nearest_cues = vec![[0, 0]];
        let mut original = Sprite::blank(2, 2);
        original.pixels.fill(1);
        f.source_sha256 = format!("{:x}", Sha256::digest(b"data"));
        assert!(validate_frame(&f, &original, b"data").is_ok());
        original.pixels[0] = TRANSPARENT;
        assert!(validate_frame(&f, &original, b"data").is_err());
    }
    #[test]
    fn malformed_policy_metadata_fails_strictly() {
        let mut j = serde_json::to_value(frame()).unwrap();
        j["native_nearest_cues"] = "yes".into();
        assert!(serde_json::from_value::<Frame>(j).is_err());
        let mut j = serde_json::to_value(frame()).unwrap();
        j["preserve_reserved_coverage"] = "yes".into();
        assert!(serde_json::from_value::<Frame>(j).is_err());
    }
    #[test]
    fn fractional_resident_cell_guard_is_bounded_and_requires_majority_support() {
        let f = frame();
        let opaque = RgbaImage::from_pixel(5, 5, image::Rgba([1, 2, 3, 255]));
        for i in 0..4 {
            assert!(reserved_cell_supported(&opaque, &f, i));
        }
        let empty = RgbaImage::new(5, 5);
        for i in 0..4 {
            assert!(!reserved_cell_supported(&empty, &f, i));
        }
        let faint = RgbaImage::from_pixel(5, 5, image::Rgba([1, 2, 3, 127]));
        for i in 0..4 {
            assert!(!reserved_cell_supported(&faint, &f, i));
        }
    }
    #[test]
    fn fractional_last_cell_does_not_read_outside_resident_canvas() {
        let mut f = frame();
        f.logical_width = 56;
        f.logical_height = 40;
        let rgba = RgbaImage::from_pixel(219, 157, image::Rgba([1, 2, 3, 255]));
        for logical in 0..56 * 40 {
            assert!(reserved_cell_supported(&rgba, &f, logical));
        }
    }
    #[test]
    fn ordinary_cue_coordinates_reject_duplicates_order_reserved_bounds_and_excess() {
        let source = b"data";
        let mut f = frame();
        f.source_sha256 = format!("{:x}", Sha256::digest(source));
        let mut original = Sprite::blank(2, 2);
        original.pixels.fill(5);
        for cells in [
            vec![[0, 0], [0, 0]],
            vec![[1, 0], [0, 0]],
            vec![[2, 0]],
            vec![[0, 2]],
            vec![[0, 0]; 65],
        ] {
            f.native_nearest_cues = cells;
            assert!(validate_frame(&f, &original, source).is_err());
        }
        f.native_nearest_cues = vec![[0, 0]];
        for label in [240, 244, 245, 249, 250, 255, TRANSPARENT] {
            original.pixels[0] = label;
            assert!(validate_frame(&f, &original, source).is_err());
        }
        original.pixels[0] = 239;
        assert!(validate_frame(&f, &original, source).is_ok());
    }
    #[test]
    fn nearest_cue_cache_identity_includes_every_sorted_coordinate() {
        let info = PngInfo {
            size: 1,
            modified: None,
            digest: [19; 32],
            width: 8,
            height: 8,
        };
        let mut a = frame();
        a.native_nearest_cues = vec![[0, 0], [1, 0]];
        let mut b = a.clone();
        b.native_nearest_cues[1] = [1, 1];
        assert_ne!(
            HdAssets::frame_key(&a, &info, false),
            HdAssets::frame_key(&b, &info, false)
        );
    }
    #[test]
    fn hidden_bright_rgb_cannot_invent_alpha_for_a_missing_reserved_lamp() {
        let mut raw = RgbaImage::from_pixel(8, 8, image::Rgba([0, 255, 255, 0]));
        for y in 4..8 {
            for x in 4..8 {
                raw.put_pixel(x, y, image::Rgba([255, 20, 20, 255]));
            }
        }
        let (_dir, mut h) = assets(254, true, raw);
        for scale in 1..=4 {
            let s = h.sprite(1, scale, &[[0; 3]; 256]).unwrap().unwrap();
            assert_eq!(s.pixels[0], TRANSPARENT);
        }
    }
    #[test]
    fn native_ordinary_cue_reads_generated_rgb_without_changing_other_pixels_or_static_mode() {
        let dir = tempfile::tempdir().unwrap();
        let mut raw = RgbaImage::from_pixel(8, 8, image::Rgba([0, 0, 0, 255]));
        raw.put_pixel(2, 2, image::Rgba([255, 150, 30, 255]));
        raw.save(dir.path().join("a.png")).unwrap();
        let make = |cues| {
            let mut f = frame();
            f.native_nearest_cues = cues;
            let mut h = HdAssets {
                root: dir.path().to_path_buf(),
                ..HdAssets::default()
            };
            h.replacements.insert(
                1,
                Replacement {
                    frame: f,
                    requires_alpha: false,
                    source_labels: None,
                    validated: false,
                    rejected: false,
                },
            );
            h
        };
        let mut old = make(Vec::new());
        let mut cue = make(vec![[0, 0]]);
        let mut palette = [[0; 3]; 256];
        palette[7] = [255, 150, 30];
        palette[254] = [255, 150, 30];
        for scale in 1..=4 {
            let before = old.sprite(1, scale, &palette).unwrap().unwrap();
            let after = cue.sprite(1, scale, &palette).unwrap().unwrap();
            if scale == 1 {
                assert_eq!(before.pixels[0], 0);
                assert_eq!(after.pixels[0], 7);
                assert_eq!(&before.pixels[1..], &after.pixels[1..]);
            } else {
                assert_eq!(before.pixels, after.pixels);
            }
            assert_eq!(
                old.sprite_static_palette(1, scale, &palette)
                    .unwrap()
                    .unwrap()
                    .pixels,
                cue.sprite_static_palette(1, scale, &palette)
                    .unwrap()
                    .unwrap()
                    .pixels
            );
        }
        // A missing ordinary raw cue remains black; no original palette index
        // or color is copied into artwork by this policy.
        raw.put_pixel(2, 2, image::Rgba([0, 0, 0, 255]));
        raw.save(dir.path().join("a.png")).unwrap();
        let mut missing = make(vec![[0, 0]]);
        assert_eq!(
            missing.sprite(1, 1, &palette).unwrap().unwrap().pixels[0],
            0
        );
    }
}
