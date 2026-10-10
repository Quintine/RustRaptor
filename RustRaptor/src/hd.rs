//! Opt-in remaster artwork tied to the original asset ID and animation canvas.
//! Missing or rejected frames fall back to the original crisp sprite.
use crate::assets::{Catalog, Sprite, contained};
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
    path::{Path, PathBuf},
};

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
    rgba: RgbaImage,
}
#[derive(Default)]
pub struct HdAssets {
    replacements: BTreeMap<u32, Replacement>,
    scaled: BTreeMap<(u32, usize), Sprite>,
    pub diagnostics: Vec<String>,
}
impl HdAssets {
    pub fn load(root: &Path, catalog: &Catalog) -> Self {
        let mut result = Self::default();
        if !root.exists() {
            return result;
        }
        match result.read(root, catalog) {
            Ok(()) => {}
            Err(e) => {
                // Reject the complete pack if its sequence metadata is invalid.
                result.replacements.clear();
                result
                    .diagnostics
                    .push(format!("HD pack {}: {e:#}", root.display()));
            }
        }
        result
    }
    fn read(&mut self, root: &Path, catalog: &Catalog) -> Result<()> {
        let bytes = fs::read(contained(root, Path::new("hd.json"))?)?;
        ensure!(bytes.len() <= 256 * 1024, "HD metadata exceeds 256 KiB");
        let manifest: Manifest = serde_json::from_slice(&bytes)?;
        ensure!(
            manifest.format_version == 1,
            "unsupported HD artwork format {}",
            manifest.format_version
        );
        ensure!(manifest.sequences.len() <= 512, "too many HD sequences");
        let mut ids = BTreeMap::new();
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
                ensure!(self.replacements.len() < 4096, "too many HD frames");
                match Self::read_frame(root, catalog, id, frame) {
                    Ok(replacement) => {
                        if self
                            .replacements
                            .values()
                            .map(|r| r.rgba.as_raw().len())
                            .sum::<usize>()
                            + replacement.rgba.as_raw().len()
                            > 128 * 1024 * 1024
                        {
                            self.diagnostics.push(format!(
                                "HD {id:05x}: pack exceeds 128 MiB artwork budget; using original"
                            ));
                        } else {
                            self.replacements.insert(id, replacement);
                        }
                    }
                    Err(e) => self.diagnostics.push(format!(
                        "HD {} frame {} ({id:05x}): {e:#}; using original",
                        sequence.name, frame.frame
                    )),
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
    fn read_frame(root: &Path, catalog: &Catalog, id: u32, frame: &Frame) -> Result<Replacement> {
        let source = catalog.read(id)?;
        let original = Sprite::decode(&source)?;
        validate_frame(frame, &original, &source)?;
        let path = contained(root, &frame.file)?;
        ensure!(
            fs::metadata(&path)?.len() <= 32 * 1024 * 1024,
            "HD PNG exceeds 32 MiB"
        );
        let mut reader = ImageReader::open(path)?.with_guessed_format()?;
        ensure!(
            reader.format() == Some(image::ImageFormat::Png),
            "HD artwork must be PNG"
        );
        let mut limits = image::Limits::default();
        limits.max_image_width = Some(4096);
        limits.max_image_height = Some(4096);
        limits.max_alloc = Some(64 * 1024 * 1024);
        reader.limits(limits);
        let mut rgba = reader.decode()?.into_rgba8();
        ensure!(
            rgba.width() as u64 * rgba.height() as u64 <= 4_194_304,
            "HD PNG exceeds pixel limit"
        );
        if let Some([x, y, width, height]) = frame.crop {
            ensure!(
                width > 0
                    && height > 0
                    && x.checked_add(width).is_some_and(|n| n <= rgba.width())
                    && y.checked_add(height).is_some_and(|n| n <= rgba.height()),
                "HD atlas crop exceeds its PNG"
            );
            rgba = imageops::crop_imm(&rgba, x, y, width, height).to_image();
        }
        ensure!(
            rgba.width() as u64 * frame.logical_height as u64
                == rgba.height() as u64 * frame.logical_width as u64,
            "HD frame aspect must match the original canvas"
        );
        ensure!(
            rgba.width() >= frame.logical_width * 2 && rgba.height() >= frame.logical_height * 2,
            "HD artwork must supply at least twice the logical resolution"
        );
        ensure!(
            rgba.pixels().any(|p| p[3] == 0),
            "HD frame needs a transparent background"
        );
        ensure!(
            rgba.pixels().any(|p| p[3] >= 128),
            "HD frame has no visible pixels"
        );
        Ok(Replacement {
            frame: frame.clone(),
            rgba,
        })
    }
    pub fn coverage(&self) -> usize {
        self.replacements.len()
    }
    /// Return already detailed artwork at the canvas resolution; never run ScaleNx on it.
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
        let Some(replacement) = self.replacements.get(&id) else {
            return Ok(None);
        };
        if !self.scaled.contains_key(&(id, scale)) {
            let width = replacement.frame.logical_width as usize * scale;
            let height = replacement.frame.logical_height as usize * scale;
            let resized = imageops::resize(
                &replacement.rgba,
                width as u32,
                height as u32,
                FilterType::Lanczos3,
            );
            let mut sprite = Sprite::blank(width, height);
            let mut colors = BTreeMap::new();
            for (destination, pixel) in sprite.pixels.iter_mut().zip(resized.pixels()) {
                if pixel[3] < 128 {
                    continue;
                }
                let key = [pixel[0], pixel[1], pixel[2]];
                *destination = *colors.entry(key).or_insert_with(|| closest(palette, key));
            }
            if self
                .scaled
                .values()
                .map(|s| s.pixels.len() * 2)
                .sum::<usize>()
                + sprite.pixels.len() * 2
                > 64 * 1024 * 1024
            {
                self.scaled.clear();
            }
            self.scaled.insert((id, scale), sprite);
        }
        Ok(self.scaled.get(&(id, scale)).cloned())
    }
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
fn closest(palette: &[[u8; 3]; 256], rgb: [u8; 3]) -> u16 {
    palette
        .iter()
        .enumerate()
        .min_by_key(|(_, c)| {
            (0..3)
                .map(|j| (c[j] as i32 - rgb[j] as i32).pow(2))
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
        let mut art = HdAssets::default();
        art.replacements.insert(
            1,
            Replacement {
                frame: frame(source),
                rgba,
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
}
