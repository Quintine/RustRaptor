//! Palette-indexed rendering. Filters copy colors, never blend palette entries.
use crate::assets::{Sprite, TRANSPARENT};
use anyhow::{Result, ensure};
use sha2::{Digest, Sha256};
use std::{collections::BTreeMap, fs, path::PathBuf};

/// Original tiny gun rounds and sparse final ground-explosion embers lose
/// important pixels under edge filtering; preserve their exact pixel area.
pub fn prefers_nearest(asset: u32) -> bool {
    matches!(asset, 0x101c3..=0x101c6 | 0x10178..=0x1018d)
}

pub fn upscale(sprite: &Sprite, factor: usize) -> Result<Sprite> {
    ensure!(
        matches!(factor, 1 | 2 | 3 | 4),
        "scale must be 1, 2, 3 or 4"
    );
    ensure!(
        sprite.width > 0
            && sprite.height > 0
            && sprite.pixels.len() == sprite.width * sprite.height,
        "invalid indexed image"
    );
    ensure!(
        sprite.width as u64 * sprite.height as u64 * (factor * factor) as u64 <= 16_777_216,
        "derived image exceeds pixel limit"
    );
    if factor == 1 {
        return Ok(sprite.clone());
    }
    if factor == 4 {
        return upscale(&upscale(sprite, 2)?, 2);
    }
    let mut out = Sprite::blank(sprite.width * factor, sprite.height * factor);
    for y in 0..sprite.height {
        for x in 0..sprite.width {
            let sample = |dx: isize, dy: isize| {
                sprite.pixels[(y as isize + dy).clamp(0, sprite.height as isize - 1) as usize
                    * sprite.width
                    + (x as isize + dx).clamp(0, sprite.width as isize - 1) as usize]
            };
            let [a, b, c, d, e, f, g, h, i] = [
                sample(-1, -1),
                sample(0, -1),
                sample(1, -1),
                sample(-1, 0),
                sample(0, 0),
                sample(1, 0),
                sample(-1, 1),
                sample(0, 1),
                sample(1, 1),
            ];
            let p = if factor == 2 {
                if b != h && d != f {
                    [
                        if d == b { d } else { e },
                        if b == f { f } else { e },
                        if d == h { d } else { e },
                        if h == f { f } else { e },
                        e,
                        e,
                        e,
                        e,
                        e,
                    ]
                } else {
                    [e; 9]
                }
            } else if b != h && d != f {
                [
                    if d == b { d } else { e },
                    if (d == b && e != c) || (b == f && e != a) {
                        b
                    } else {
                        e
                    },
                    if b == f { f } else { e },
                    if (d == b && e != g) || (d == h && e != a) {
                        d
                    } else {
                        e
                    },
                    e,
                    if (b == f && e != i) || (h == f && e != c) {
                        f
                    } else {
                        e
                    },
                    if d == h { d } else { e },
                    if (d == h && e != i) || (h == f && e != g) {
                        h
                    } else {
                        e
                    },
                    if h == f { f } else { e },
                ]
            } else {
                [e; 9]
            };
            for dy in 0..factor {
                for dx in 0..factor {
                    out.pixels[(y * factor + dy) * out.width + x * factor + dx] =
                        p[dy * factor + dx];
                }
            }
        }
    }
    Ok(out)
}
pub fn nearest(sprite: &Sprite, factor: usize) -> Sprite {
    let mut out = Sprite::blank(sprite.width * factor, sprite.height * factor);
    for y in 0..out.height {
        for x in 0..out.width {
            out.pixels[y * out.width + x] = sprite.pixels[(y / factor) * sprite.width + x / factor];
        }
    }
    out
}

/// Original VGA light/dark lookup. Inputs are six-bit RGB components, not SDL
/// eight-bit colors. GFX_Remap uses Manhattan distance and the last equal match.
pub fn legacy_light_table(palette: &[[u8; 3]; 256], level: i32) -> [u8; 256] {
    std::array::from_fn(|index| {
        let target = palette[index].map(|component| (component as i32 + level).clamp(0, 63));
        let mut best = 0;
        let mut distance = i32::MAX;
        for (candidate, color) in palette.iter().enumerate() {
            let difference: i32 = (0..3)
                .map(|channel| (color[channel] as i32 - target[channel]).abs())
                .sum();
            if difference <= distance {
                best = candidate as u8;
                distance = difference;
            }
        }
        best
    })
}

/// SHADOW_GAdd / GFX_ShadeShape: preserve native mask spans at offset (-3,+4).
pub fn shade_ground_shadow(canvas: &mut Canvas, mask: &Sprite, x: f32, y: f32, table: &[u8; 256]) {
    let scaled = nearest(mask, canvas.scale);
    canvas.shade(
        &scaled,
        ((x - 3.0) * canvas.scale as f32).round() as i32,
        ((y + 4.0) * canvas.scale as f32).round() as i32,
        table,
    );
}

fn shadow_project(coordinate: i32, center: i32) -> i32 {
    // GFX_3DPoint: view=(160,100,1000), objectZ=1280, distance=200.
    // Keep division before arithmetic shift; negative coordinates round down
    // after the original signed integer division.
    ((((coordinate as i64 - center as i64) * (200 << 11)) / 280) >> 11) as i32 + center
}

/// SHADOW_Draw's projected horizontal spans, with duplicate projected rows
/// suppressed. Fractional positions translate the indexed mask smoothly on the
/// high-resolution canvas; integer positions retain the original projection.
pub fn shade_air_shadow(canvas: &mut Canvas, mask: &Sprite, x: f32, y: f32, table: &[u8; 256]) {
    let base_x = x.floor() as i32 - 10;
    let base_y = y.floor() as i32 + 20;
    let fraction_x = (x - x.floor()) * (5.0 / 7.0);
    let fraction_y = (y - y.floor()) * (5.0 / 7.0);
    let scale = canvas.scale as f32;
    let mut previous_row = None;
    for row in 0..mask.height {
        let source = &mask.pixels[row * mask.width..(row + 1) * mask.width];
        if source.iter().all(|pixel| *pixel == TRANSPARENT) {
            continue;
        }
        let projected_y = shadow_project(base_y + row as i32, 100);
        if previous_row == Some(projected_y) {
            continue;
        }
        previous_row = Some(projected_y);
        let top = ((projected_y as f32 + fraction_y) * scale).round() as i32;
        let bottom = ((projected_y as f32 + 1.0 + fraction_y) * scale).round() as i32;
        let mut column = 0;
        while column < mask.width {
            if source[column] == TRANSPARENT {
                column += 1;
                continue;
            }
            let start = column;
            while column < mask.width && source[column] != TRANSPARENT {
                column += 1;
            }
            let left = ((shadow_project(base_x + start as i32, 160) as f32 + fraction_x) * scale)
                .round() as i32;
            let right =
                ((shadow_project(base_x + column as i32 - 1, 160) as f32 + 1.0 + fraction_x)
                    * scale)
                    .round() as i32;
            for yy in top.max(0)..bottom.min(canvas.image.height as i32) {
                for xx in left.max(0)..right.min(canvas.image.width as i32) {
                    let pixel =
                        &mut canvas.image.pixels[yy as usize * canvas.image.width + xx as usize];
                    if *pixel < 256 {
                        *pixel = table[*pixel as usize] as u16;
                    }
                }
            }
        }
    }
}
pub struct SpriteCache {
    memory: BTreeMap<String, Sprite>,
    root: Option<PathBuf>,
}
impl SpriteCache {
    pub fn new(root: Option<PathBuf>) -> Self {
        Self {
            memory: BTreeMap::new(),
            root,
        }
    }
    pub fn get(&mut self, sprite: &Sprite, factor: usize, pixelated: bool) -> Result<&Sprite> {
        let mut hash = Sha256::new();
        hash.update(b"raptor-scale-v1");
        hash.update(sprite.width.to_le_bytes());
        hash.update(sprite.height.to_le_bytes());
        hash.update([factor as u8, pixelated as u8]);
        for p in &sprite.pixels {
            hash.update(p.to_le_bytes());
        }
        let key = format!("{:x}", hash.finalize());
        if !self.memory.contains_key(&key) {
            let saved = self
                .root
                .as_ref()
                .and_then(|r| fs::read(r.join(format!("{key}.json"))).ok())
                .and_then(|b| serde_json::from_slice::<Sprite>(&b).ok())
                .filter(|s| {
                    s.width == sprite.width * factor
                        && s.height == sprite.height * factor
                        && s.pixels.len() == s.width * s.height
                        && s.pixels.iter().all(|p| *p <= TRANSPARENT)
                });
            let scaled = if let Some(s) = saved {
                s
            } else if pixelated {
                nearest(sprite, factor)
            } else {
                upscale(sprite, factor)?
            };
            if let Some(root) = &self.root {
                fs::create_dir_all(root)?;
                if !root.join(format!("{key}.json")).exists() {
                    crate::persistence::atomic_write(
                        &root.join(format!("{key}.json")),
                        &serde_json::to_vec(&scaled)?,
                    )?;
                }
            }
            if self
                .memory
                .values()
                .map(|s| s.pixels.len() * 2)
                .sum::<usize>()
                + scaled.pixels.len() * 2
                > 128 * 1024 * 1024
            {
                self.memory.clear();
            }
            self.memory.insert(key.clone(), scaled);
        }
        Ok(&self.memory[&key])
    }
}
pub struct Canvas {
    pub image: Sprite,
    pub scale: usize,
}
impl Canvas {
    pub fn new(scale: usize) -> Self {
        Self {
            image: Sprite {
                width: 320 * scale,
                height: 200 * scale,
                pixels: vec![0; 320 * 200 * scale * scale],
            },
            scale,
        }
    }
    pub fn clear(&mut self, color: u16) {
        self.image.pixels.fill(color)
    }
    pub fn blit(&mut self, sprite: &Sprite, x: i32, y: i32) {
        for sy in 0..sprite.height {
            let yy = y + sy as i32;
            if yy < 0 || yy >= self.image.height as i32 {
                continue;
            }
            for sx in 0..sprite.width {
                let xx = x + sx as i32;
                if xx < 0 || xx >= self.image.width as i32 {
                    continue;
                }
                let c = sprite.pixels[sy * sprite.width + sx];
                if c != TRANSPARENT {
                    self.image.pixels[yy as usize * self.image.width + xx as usize] = c;
                }
            }
        }
    }
    pub fn rect(&mut self, x: i32, y: i32, w: i32, h: i32, color: u16) {
        let s = self.scale as i32;
        for yy in (y * s).max(0)..((y + h) * s).min(self.image.height as i32) {
            for xx in (x * s).max(0)..((x + w) * s).min(self.image.width as i32) {
                self.image.pixels[yy as usize * self.image.width + xx as usize] = color;
            }
        }
    }
    pub fn shade(&mut self, mask: &Sprite, x: i32, y: i32, table: &[u8; 256]) {
        for sy in 0..mask.height {
            let yy = y + sy as i32;
            if yy < 0 || yy >= self.image.height as i32 {
                continue;
            }
            for sx in 0..mask.width {
                let xx = x + sx as i32;
                if xx < 0
                    || xx >= self.image.width as i32
                    || mask.pixels[sy * mask.width + sx] == TRANSPARENT
                {
                    continue;
                }
                let p = &mut self.image.pixels[yy as usize * self.image.width + xx as usize];
                if *p < 256 {
                    *p = table[*p as usize] as u16;
                }
            }
        }
    }
    pub fn rgba(&self, palette: &[[u8; 3]; 256], scanlines: bool) -> Vec<u8> {
        let mut out = vec![0; self.image.pixels.len() * 4];
        for (i, p) in self.image.pixels.iter().enumerate() {
            let color = palette[(*p).min(255) as usize];
            let dark = scanlines && (i / self.image.width) % (self.scale * 3) == self.scale * 2;
            for j in 0..3 {
                out[i * 4 + j] = if dark { color[j] / 2 } else { color[j] };
            }
            out[i * 4 + 3] = 255;
        }
        out
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn uniform_image_unchanged() {
        let s = Sprite {
            width: 2,
            height: 2,
            pixels: vec![9; 4],
        };
        for n in [2, 3, 4] {
            assert!(upscale(&s, n).unwrap().pixels.iter().all(|p| *p == 9));
        }
    }
    #[test]
    fn scale_four_is_two_passes() {
        let s = Sprite {
            width: 3,
            height: 3,
            pixels: vec![0, 1, 0, 1, 1, 0, 0, 0, TRANSPARENT],
        };
        assert_eq!(
            upscale(&s, 4).unwrap(),
            upscale(&upscale(&s, 2).unwrap(), 2).unwrap()
        );
    }
    #[test]
    fn scale_three_guard_preserves_cross() {
        let s = Sprite {
            width: 3,
            height: 3,
            pixels: vec![1, 2, 3, 4, 5, 4, 6, 2, 7],
        };
        let out = upscale(&s, 3).unwrap();
        for y in 3..6 {
            for x in 3..6 {
                assert_eq!(out.pixels[y * 9 + x], 5)
            }
        }
    }
    #[test]
    fn clipped_transparency() {
        let mut c = Canvas::new(1);
        c.clear(3);
        c.blit(
            &Sprite {
                width: 2,
                height: 1,
                pixels: vec![8, TRANSPARENT],
            },
            -1,
            0,
        );
        assert_eq!(c.image.pixels[0], 3);
    }
}

pub struct BitmapFont {
    height: usize,
    glyphs: Vec<Option<Sprite>>,
    widths: Vec<usize>,
}
// Mod labels are UTF-8; catalog bitmap fonts have only 256 glyphs. Keep width
// measurement and drawing on the same normalized character stream.
fn bitmap_chars(text: &str) -> impl Iterator<Item = u8> + '_ {
    text.chars().flat_map(|character| {
        match character {
            '\u{2010}'..='\u{2015}' | '\u{2212}' => [Some(b'-'), None, None],
            '\u{2018}' | '\u{2019}' => [Some(b'\''), None, None],
            '\u{201c}' | '\u{201d}' => [Some(b'"'), None, None],
            '\u{2026}' => [Some(b'.'), Some(b'.'), Some(b'.')],
            '\u{00a0}' => [Some(b' '), None, None],
            character if character.is_control() => [Some(b' '), None, None],
            character if (character as u32) <= 255 => [Some(character as u8), None, None],
            _ => [Some(b'?'), None, None],
        }
        .into_iter()
        .flatten()
    })
}
impl BitmapFont {
    pub fn decode(bytes: &[u8]) -> Result<Self> {
        let height = crate::assets::i32_at(bytes, 0)?;
        ensure!(
            (1..=64).contains(&height) && bytes.len() >= 772,
            "invalid bitmap font"
        );
        let mut glyphs = Vec::new();
        let mut widths = Vec::new();
        for ch in 0..256 {
            let offset = crate::assets::i16_at(bytes, 4 + ch * 2)?;
            let width = bytes[516 + ch] as usize;
            widths.push(width);
            if offset < 0 || width == 0 {
                glyphs.push(None);
                continue;
            }
            let start = 772 + offset as usize;
            let len = width * height as usize;
            let data = bytes
                .get(start..start + len)
                .ok_or_else(|| anyhow::anyhow!("truncated font glyph {ch}"))?;
            glyphs.push(Some(Sprite {
                width,
                height: height as usize,
                pixels: data
                    .iter()
                    .map(|v| if *v == 0 { TRANSPARENT } else { *v as u16 })
                    .collect(),
            }));
        }
        Ok(Self {
            height: height as usize,
            glyphs,
            widths,
        })
    }
    pub fn text(&self, canvas: &mut Canvas, x: i32, y: i32, text: &str, color: u16) {
        let mut cursor = x;
        for ch in bitmap_chars(text) {
            if let Some(g) = &self.glyphs[ch as usize] {
                let mut glyph = g.clone();
                for p in &mut glyph.pixels {
                    if *p != TRANSPARENT {
                        *p = if color > TRANSPARENT {
                            color
                        } else {
                            (*p + color.saturating_sub(1)).min(255)
                        };
                    }
                }
                canvas.blit(
                    &nearest(&glyph, canvas.scale),
                    cursor * canvas.scale as i32,
                    y * canvas.scale as i32,
                );
            }
            cursor += self.widths[ch as usize] as i32 + 1;
            if cursor > (canvas.image.width / canvas.scale) as i32 - 6 {
                break;
            }
        }
    }
    /// Logical pixel width, including the same one-pixel glyph spacing as `text`.
    pub fn text_width(&self, text: &str) -> usize {
        bitmap_chars(text)
            .map(|byte| self.widths[byte as usize] + 1)
            .sum()
    }
    pub fn height(&self) -> usize {
        self.height
    }
}

#[cfg(test)]
mod font_label_tests {
    use super::*;
    #[test]
    fn unicode_mod_punctuation_draws_and_measures_like_supported_glyphs() {
        let font = BitmapFont {
            height: 1,
            glyphs: (0..256)
                .map(|index| {
                    Some(Sprite {
                        width: 1,
                        height: 1,
                        pixels: vec![index as u16],
                    })
                })
                .collect(),
            widths: vec![1; 256],
        };
        let mut unicode = Canvas::new(2);
        let mut ascii = Canvas::new(2);
        let label = "Iron Coast — ‘Stormwall’…";
        let normalized = "Iron Coast - 'Stormwall'...";
        font.text(&mut unicode, 4, 4, label, 1);
        font.text(&mut ascii, 4, 4, normalized, 1);
        assert_eq!(unicode.image.pixels, ascii.image.pixels);
        assert_eq!(font.text_width(label), font.text_width(normalized));
        assert_eq!(font.text_width("未知"), font.text_width("??"));
    }
}
