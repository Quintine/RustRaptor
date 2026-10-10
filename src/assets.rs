//! Checked decoders for the loose catalog and the original little-endian assets.
use anyhow::{Context, Result, bail, ensure};
use serde::{Deserialize, Serialize};
use std::{
    collections::{BTreeMap, HashMap},
    fs,
    path::{Component, Path, PathBuf},
};

pub const TRANSPARENT: u16 = 256;
#[derive(Debug, Clone)]
pub struct Entry {
    pub id: u32,
    pub size: usize,
    pub path: PathBuf,
}
#[derive(Debug, Clone)]
pub struct Catalog {
    pub root: PathBuf,
    pub entries: BTreeMap<u32, Entry>,
    names: BTreeMap<String, u32>,
}
pub fn contained(root: &Path, relative: &Path) -> Result<PathBuf> {
    ensure!(
        !relative.is_absolute()
            && relative
                .components()
                .all(|c| matches!(c, Component::Normal(_))),
        "asset path must stay inside its root: {}",
        relative.display()
    );
    let root = root.canonicalize().context("asset root does not exist")?;
    let path = root
        .join(relative)
        .canonicalize()
        .with_context(|| format!("missing asset {}", relative.display()))?;
    ensure!(path.starts_with(&root), "asset symlink escapes its root");
    Ok(path)
}
impl Catalog {
    pub fn open(root: impl AsRef<Path>) -> Result<Self> {
        let root = root.as_ref().to_path_buf();
        let index = fs::read_to_string(root.join("INDEX"))?;
        let mut entries = BTreeMap::new();
        let mut names = BTreeMap::new();
        for (line_no, line) in index.lines().enumerate() {
            if line.trim().is_empty() {
                continue;
            }
            let fields: Vec<_> = line.split_whitespace().collect();
            ensure!(
                fields.len() == 3,
                "INDEX line {}: expected id, size, path",
                line_no + 1
            );
            let id = u32::from_str_radix(fields[0], 16)?;
            let size = fields[1].parse::<usize>()?;
            ensure!(size <= 64 * 1024 * 1024, "asset exceeds 64 MiB");
            let path = PathBuf::from(fields[2]);
            contained(&root, &path)?;
            ensure!(
                entries
                    .insert(
                        id,
                        Entry {
                            id,
                            size,
                            path: path.clone()
                        }
                    )
                    .is_none(),
                "duplicate asset id {id:x}"
            );
            let name = path
                .file_name()
                .context("missing asset name")?
                .to_string_lossy()
                .to_ascii_uppercase();
            names.entry(name).or_insert(id);
        }
        ensure!(!entries.is_empty(), "empty catalog");
        Ok(Self {
            root,
            entries,
            names,
        })
    }
    pub fn id(&self, name: &str) -> Result<u32> {
        self.names
            .get(&name.to_ascii_uppercase())
            .copied()
            .with_context(|| format!("missing asset {name}"))
    }
    pub fn read(&self, id: u32) -> Result<Vec<u8>> {
        let entry = self
            .entries
            .get(&id)
            .with_context(|| format!("unknown asset {id:x}"))?;
        let data = fs::read(contained(&self.root, &entry.path)?)?;
        ensure!(
            data.len() == entry.size,
            "asset {id:x}: INDEX size {} != actual {}",
            entry.size,
            data.len()
        );
        Ok(data)
    }
    pub fn named(&self, name: &str) -> Result<Vec<u8>> {
        self.read(self.id(name)?)
    }
    pub fn sprite(&self, id: u32) -> Result<Sprite> {
        Sprite::decode(&self.read(id)?).with_context(|| format!("sprite {id:x}"))
    }
    pub fn verify(&self) -> Result<usize> {
        for id in self.entries.keys() {
            self.read(*id)?;
        }
        Ok(self.entries.len())
    }
    pub fn palette(&self) -> Result<[[u8; 3]; 256]> {
        decode_palette(&self.named("PALETTE_DAT")?)
    }
}
pub fn i32_at(data: &[u8], off: usize) -> Result<i32> {
    let end = off.checked_add(4).context("32-bit field offset overflow")?;
    Ok(i32::from_le_bytes(
        data.get(off..end)
            .context("truncated 32-bit field")?
            .try_into()?,
    ))
}
pub fn i16_at(data: &[u8], off: usize) -> Result<i16> {
    let end = off.checked_add(2).context("16-bit field offset overflow")?;
    Ok(i16::from_le_bytes(
        data.get(off..end)
            .context("truncated 16-bit field")?
            .try_into()?,
    ))
}
pub fn decode_palette(data: &[u8]) -> Result<[[u8; 3]; 256]> {
    ensure!(data.len() == 768, "palette must contain 768 bytes");
    Ok(std::array::from_fn(|i| {
        std::array::from_fn(|j| {
            let x = data[i * 3 + j];
            (x.min(63) << 2) | (x.min(63) >> 4)
        })
    }))
}
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Sprite {
    pub width: usize,
    pub height: usize,
    pub pixels: Vec<u16>,
}
impl Sprite {
    pub fn blank(width: usize, height: usize) -> Self {
        Self {
            width,
            height,
            pixels: vec![TRANSPARENT; width * height],
        }
    }
    pub fn decode(data: &[u8]) -> Result<Self> {
        let typ = i32_at(data, 0)?;
        let width = i32_at(data, 12)?;
        let height = i32_at(data, 16)?;
        ensure!(
            (1..=4096).contains(&width)
                && (1..=4096).contains(&height)
                && width as i64 * height as i64 <= 1_048_576,
            "invalid sprite dimensions {width}x{height}"
        );
        let mut out = Self::blank(width as usize, height as usize);
        match typ {
            1 => {
                let bytes = data
                    .get(20..20 + out.pixels.len())
                    .context("truncated raw picture")?;
                for (dst, src) in out.pixels.iter_mut().zip(bytes) {
                    *dst = *src as u16;
                }
            }
            0 => {
                let mut off = 20;
                let mut runs = 0;
                loop {
                    let x = i32_at(data, off)?;
                    let y = i32_at(data, off + 4)?;
                    let dest = i32_at(data, off + 8)?;
                    let len = i32_at(data, off + 12)?;
                    off += 16;
                    if dest == -1 {
                        break;
                    }
                    ensure!(
                        x >= 0
                            && y >= 0
                            && len > 0
                            && x.checked_add(len).is_some_and(|n| n <= width)
                            && y < height,
                        "invalid sprite span"
                    );
                    let bytes = data
                        .get(off..off + len as usize)
                        .context("truncated sprite span")?;
                    let start = y as usize * out.width + x as usize;
                    for (dst, src) in out.pixels[start..start + len as usize]
                        .iter_mut()
                        .zip(bytes)
                    {
                        *dst = *src as u16;
                    }
                    off += len as usize;
                    runs += 1;
                    ensure!(runs <= out.pixels.len(), "too many sprite spans");
                }
            }
            _ => bail!("unsupported picture type {typ}"),
        }
        Ok(out)
    }
    pub fn png(path: &Path, palette: &[[u8; 3]; 256]) -> Result<Self> {
        let mut reader = image::ImageReader::open(path)?.with_guessed_format()?;
        ensure!(
            reader.format() == Some(image::ImageFormat::Png),
            "mod artwork must be PNG"
        );
        let mut limits = image::Limits::default();
        limits.max_image_width = Some(4096);
        limits.max_image_height = Some(4096);
        limits.max_alloc = Some(64 * 1024 * 1024);
        reader.limits(limits);
        let image = reader.decode()?.into_rgba8();
        ensure!(
            image.width() <= 4096
                && image.height() <= 4096
                && image.width() as u64 * image.height() as u64 <= 4_194_304,
            "PNG exceeds 4096px"
        );
        let mut out = Self::blank(image.width() as usize, image.height() as usize);
        // Palette art repeats colors extensively. Cache by RGB (alpha is handled
        // separately) so terrain atlases do not search 256 entries per pixel.
        let mut colors = HashMap::<[u8; 3], u16>::new();
        for (dst, p) in out.pixels.iter_mut().zip(image.pixels()) {
            if p[3] < 128 {
                continue;
            }
            *dst = *colors.entry([p[0], p[1], p[2]]).or_insert_with(|| {
                palette
                    .iter()
                    .enumerate()
                    .min_by_key(|(_, c)| {
                        (0..3)
                            .map(|j| (p[j] as i32 - c[j] as i32).pow(2))
                            .sum::<i32>()
                    })
                    .unwrap()
                    .0 as u16
            });
        }
        Ok(out)
    }
}
#[derive(Debug, Clone)]
pub struct LegacyMap {
    pub tiles: Vec<(u16, u16)>,
    pub spawns: Vec<LegacySpawn>,
}
#[derive(Debug, Clone)]
pub struct LegacySpawn {
    pub link: i32,
    pub library: usize,
    pub x: i32,
    pub row: i32,
    pub game: usize,
    pub difficulty: i32,
}
impl LegacyMap {
    pub fn decode(data: &[u8]) -> Result<Self> {
        let size = i32_at(data, 0)?;
        let off = i32_at(data, 4)?;
        let count = i32_at(data, 8)?;
        ensure!(
            size >= 5412 && size as usize == data.len() && off == 5412 && count >= 0,
            "invalid map header"
        );
        ensure!(
            (count as usize) < 65536 && 5412 + count as usize * 24 <= data.len(),
            "truncated map spawns"
        );
        let mut tiles = Vec::new();
        for i in 0..1350 {
            let off = 12 + i * 4;
            let flat = i16_at(data, off)?;
            let game = i16_at(data, off + 2)?;
            ensure!(
                flat >= 0 && (0..4).contains(&game),
                "invalid tile reference"
            );
            tiles.push((flat as u16, game as u16));
        }
        let mut spawns = Vec::new();
        for i in 0..count as usize {
            let o = 5412 + i * 24;
            let lib = i32_at(data, o + 4)?;
            let game = i32_at(data, o + 16)?;
            ensure!(lib >= 0 && (0..4).contains(&game), "invalid enemy library");
            spawns.push(LegacySpawn {
                link: i32_at(data, o)?,
                library: lib as usize,
                x: i32_at(data, o + 8)?,
                row: i32_at(data, o + 12)?,
                game: game as usize,
                difficulty: i32_at(data, o + 20)?,
            });
        }
        Ok(Self { tiles, spawns })
    }
}
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LegacyEnemy {
    pub name: String,
    pub fields: Vec<i32>,
    pub shoot_type: Vec<i16>,
    pub engine_x: Vec<i16>,
    pub engine_y: Vec<i16>,
    pub engine_width: Vec<i16>,
    pub gun_x: Vec<i16>,
    pub gun_y: Vec<i16>,
    pub flight_x: Vec<i16>,
    pub flight_y: Vec<i16>,
}
impl LegacyEnemy {
    pub const SIZE: usize = 528;
    pub fn library(data: &[u8]) -> Result<Vec<Self>> {
        ensure!(data.len() % Self::SIZE == 0, "truncated enemy library");
        data.chunks_exact(Self::SIZE)
            .map(|record| {
                let name =
                    String::from_utf8(record[..16].split(|x| *x == 0).next().unwrap().to_vec())?;
                let fields = (0..26)
                    .map(|i| i32_at(record, 16 + i * 4))
                    .collect::<Result<Vec<_>>>()?;
                let shorts = |offset: usize, count: usize| -> Result<Vec<i16>> {
                    (0..count).map(|i| i16_at(record, offset + i * 2)).collect()
                };
                ensure!(
                    (0..=30).contains(&fields[19]) && (0..=24).contains(&fields[22]),
                    "invalid enemy path or guns"
                );
                Ok(Self {
                    name,
                    fields,
                    shoot_type: shorts(120, 24)?,
                    engine_x: shorts(168, 24)?,
                    engine_y: shorts(216, 24)?,
                    engine_width: shorts(264, 24)?,
                    gun_x: shorts(312, 24)?,
                    gun_y: shorts(360, 24)?,
                    flight_x: shorts(408, 30)?,
                    flight_y: shorts(468, 30)?,
                })
            })
            .collect()
    }
}
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct DemoFrame {
    pub buttons: [bool; 4],
    pub x: i16,
    pub y: i16,
    pub bank: i16,
}
pub fn decode_demo(data: &[u8]) -> Result<(usize, usize, Vec<DemoFrame>)> {
    ensure!(data.len() >= 12 && data.len() % 12 == 0, "truncated demo");
    let count = i16_at(data, 8)?;
    ensure!(
        count >= 0 && count as usize * 12 <= data.len(),
        "invalid demo frame count"
    );
    let sector = i16_at(data, 4)?;
    let wave = i16_at(data, 6)?;
    ensure!(
        (0..3).contains(&sector) && (0..9).contains(&wave),
        "invalid demo mission"
    );
    let frames = data[12..]
        .chunks_exact(12)
        .take(count as usize)
        .map(|f| {
            Ok(DemoFrame {
                buttons: std::array::from_fn(|i| f[i] != 0),
                x: i16_at(f, 4)?,
                y: i16_at(f, 6)?,
                bank: i16_at(f, 8)?,
            })
        })
        .collect::<Result<_>>()?;
    Ok((sector as usize, wave as usize, frames))
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn truncation_is_an_error() {
        for n in 0..20 {
            assert!(Sprite::decode(&vec![0; n]).is_err());
        }
    }
    #[test]
    fn raw_picture() {
        let mut b = Vec::new();
        for x in [1i32, 0, 0, 2, 1] {
            b.extend(x.to_le_bytes())
        }
        b.extend([0, 7]);
        assert_eq!(Sprite::decode(&b).unwrap().pixels, vec![0, 7]);
    }
    #[test]
    fn span_outside_canvas_rejected() {
        let mut b = Vec::new();
        for x in [0i32, 0, 0, 2, 1, 1, 0, 1, 2] {
            b.extend(x.to_le_bytes())
        }
        b.extend([3, 4]);
        assert!(Sprite::decode(&b).is_err());
    }
}
