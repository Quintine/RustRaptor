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
pub struct HdAssets {
    root: PathBuf,
    disk_cache: Option<PathBuf>,
    replacements: BTreeMap<u32, Replacement>,
    png_info: BTreeMap<PathBuf, PngInfo>,
    atlases: LruCache<[u8; 32], RgbaImage>,
    rgba: LruCache<[u8; 32], RgbaImage>,
    scaled: LruCache<([u8; 32], usize, [u8; 32]), Sprite>,
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
            let (width, height) = frame_dimensions(&frame, &info)?;
            let key = Self::frame_key(&frame, &info, requires_alpha);
            if let Some(rgba) = self.rgba.get(&key) {
                return Ok((key, rgba.clone()));
            }
            let target_width = width.min(frame.logical_width * 4);
            let target_height = height.min(frame.logical_height * 4);
            if let Some(rgba) =
                self.read_disk_cache(&key, target_width, target_height, requires_alpha)
            {
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
                if let Some(sprite) = self.scaled.get(&(key, scale, palette_key)).cloned() {
                    self.replacements.get_mut(&id).unwrap().validated = true;
                    return Ok(Some(sprite));
                }
            }
        }
        let Some((key, rgba)) = self.rgba_frame(id)? else {
            return Ok(None);
        };
        let scaled_key = (key, scale, palette_key);
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
            if pixel[3] < 128 {
                continue;
            }
            let rgb = [pixel[0], pixel[1], pixel[2]];
            let logical =
                (index / width / scale) * frame.logical_width as usize + (index % width / scale);
            let source_label = replacement
                .source_labels
                .as_ref()
                .map_or(0, |labels| labels[logical]);
            *destination = *colors
                .entry((rgb, source_label))
                .or_insert_with(|| closest(palette, rgb, source_label));
        }
        self.scaled
            .insert(scaled_key, sprite.clone(), sprite.pixels.len() * 2);
        Ok(Some(sprite))
    }
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
fn frame_dimensions(frame: &Frame, png: &PngInfo) -> Result<(u32, u32)> {
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
        width as u64 * frame.logical_height as u64 == height as u64 * frame.logical_width as u64,
        "HD frame aspect must match the original canvas"
    );
    ensure!(
        width as u64 >= frame.logical_width as u64 * 2
            && height as u64 >= frame.logical_height as u64 * 2,
        "HD artwork must supply at least twice the logical resolution"
    );
    Ok((width, height))
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
}
