//! Contextual, indexed terrain remaster composition.
//!
//! The complete original terrain layer is filtered before replacements are
//! applied. Reviewed neighbors share detailed edge colors; mixed coverage
//! approaches original context, so a tile can be reused with different neighbors. Coordinates
//! include the original two-pixel scrolling gutter; interpolation is applied
//! once to the completed layer, rather than separately to individual tiles.
use crate::{
    assets::{Sprite, TRANSPARENT},
    content::{Art, TileDef},
};
use anyhow::{Result, ensure};
use std::collections::BTreeMap;

const LEVELS: usize = 16;
const UNSET: u16 = u16::MAX;
const MAX_PREPARED_PIXELS: usize = 320 * 268 * 16;
const MAX_PREPARED_KEY_BYTES: usize = 64 * 1024;

/// Use the native settled flag for native map debris. A hit does not replace
/// those tiles until the original destruction animation has completed.
pub fn selected_art(tile: &TileDef, legacy: bool, dead: bool, settled: bool) -> &Art {
    if if legacy { settled } else { dead } {
        tile.destroyed.as_ref().unwrap_or(&tile.art)
    } else {
        &tile.art
    }
}

/// Preserve a mod's logical canvas when its source PNG already has more detail.
/// This is only for the joined original layer, never the HD replacement.
pub fn logical_sprite(source: &Sprite, width: usize, height: usize) -> Result<Sprite> {
    ensure!(
        source.width > 0
            && source.height > 0
            && source.pixels.len() == source.width * source.height
            && width > 0
            && height > 0
            && width <= 4096
            && height <= 4096,
        "invalid terrain canvas"
    );
    if (source.width, source.height) == (width, height) {
        return Ok(source.clone());
    }
    let mut logical = Sprite::blank(width, height);
    for y in 0..height {
        for x in 0..width {
            logical.pixels[y * width + x] = source.pixels
                [(y * source.height / height) * source.width + x * source.width / width];
        }
    }
    Ok(logical)
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum OverlayResult {
    Applied,
    InvalidCanvas,
    NonOpaque,
    InvalidOriginalDetails,
}

pub struct Replacement {
    pub image: Sprite,
    /// Original logical position, including the scrolling gutter.
    pub position: [i32; 2],
    pub logical_size: [usize; 2],
}
pub struct RetainedOriginalPlacement {
    pub replacement_index: usize,
    pub details: crate::hd::OriginalDetailCells,
}
pub struct Composition {
    pub image: Sprite,
    pub results: Vec<OverlayResult>,
}

/// A bounded 2 MiB lookup of indexed edge transitions and one row-aligned
/// viewport strip. PNG/atlas caches belong to HdAssets; whole maps stay unloaded.
#[derive(Default)]
pub struct TerrainHd {
    palette: Option<[[u8; 3]; 256]>,
    transitions: Vec<u16>,
    prepared: Option<(Vec<u8>, Sprite)>,
}
impl TerrainHd {
    pub fn cache_bytes(&self) -> usize {
        self.transitions.len() * std::mem::size_of::<u16>()
    }

    pub fn prepared_bytes(&self) -> usize {
        self.prepared
            .as_ref()
            .map_or(0, |(key, image)| key.len() + image.pixels.len() * 2)
    }

    pub fn cached_layer(&self, key: &[u8]) -> Option<&Sprite> {
        self.prepared
            .as_ref()
            .filter(|(saved, _)| saved == key)
            .map(|(_, image)| image)
    }

    /// Retain one row-aligned viewport strip, never an entire mission map. Its
    /// key contains the selected art, active content hashes and render options.
    pub fn retain_layer(&mut self, key: Vec<u8>, image: Sprite) {
        if key.len() <= MAX_PREPARED_KEY_BYTES
            && image.pixels.len() <= MAX_PREPARED_PIXELS
            && image.pixels.len() == image.width.saturating_mul(image.height)
        {
            self.prepared = Some((key, image));
        } else {
            self.prepared = None;
        }
    }

    /// Resolve the visible set together. HD/HD neighbors share detailed edge
    /// colors; HD/original neighbors use the original contextual edge. This
    /// prevents a grid of low-resolution borders across fully remastered maps.
    pub fn compose(
        &mut self,
        context: &Sprite,
        replacements: &[Replacement],
        scale: usize,
        palette: &[[u8; 3]; 256],
    ) -> Composition {
        self.compose_retaining_original(context, replacements, &[], scale, palette)
    }
    /// Original detail is explicit metadata and is patched only into the FINAL
    /// layer. Pristine HD edge inputs and all unprotected samples stay unchanged.
    pub fn compose_retaining_original(&mut self, context: &Sprite,
        replacements: &[Replacement], retained: &[RetainedOriginalPlacement],
        scale: usize, palette: &[[u8; 3]; 256]) -> Composition {
        let mut image = context.clone();
        let mut results = Vec::with_capacity(replacements.len());
        let mut accepted = BTreeMap::new();
        for (index, tile) in replacements.iter().enumerate() {
            let result = validate(context, context, &tile.image, tile.logical_size, scale);
            if result == OverlayResult::Applied {
                accepted.insert((tile.position, tile.logical_size), index);
            }
            results.push(result);
        }
        if accepted.is_empty() {
            return Composition { image, results };
        }
        // Validate/project all accepted protected footprints before composition.
        // Conflicting ownership fails the entire opt-in context to Original;
        // default/no-retention composition remains exactly the old route.
        let mut protected = BTreeMap::new();
        let valid_details = retained.iter().all(|retention| {
            let Some(tile) = replacements.get(retention.replacement_index) else { return false };
            if accepted.get(&(tile.position, tile.logical_size)) != Some(&retention.replacement_index) { return true; }
            if retention.details.logical_size() != tile.logical_size { return false; }
            for &[x, y] in retention.details.cells() {
                if x as usize >= tile.logical_size[0] || y as usize >= tile.logical_size[1] { return false; }
                for dy in 0..scale { for dx in 0..scale {
                    let xx = (tile.position[0] as i64 + x as i64) * scale as i64 + dx as i64;
                    let yy = (tile.position[1] as i64 + y as i64) * scale as i64 + dy as i64;
                    if xx < 0 || yy < 0 || xx >= context.width as i64 || yy >= context.height as i64 { continue; }
                    let pixel = yy as usize * context.width + xx as usize;
                    if protected.insert(pixel, retention.replacement_index)
                        .is_some_and(|owner| owner != retention.replacement_index) { return false; }
                }}
            }
            true
        });
        if !valid_details {
            return Composition { image: context.clone(), results: vec![OverlayResult::InvalidOriginalDetails; replacements.len()] };
        }
        self.prepare_palette(palette);
        // Keep a pristine joined HD context. Every edge reads this same layer,
        // so the result cannot depend on the overlay order or previous blending.
        let mut detailed = context.clone();
        for (index, tile) in replacements.iter().enumerate() {
            if accepted.get(&(tile.position, tile.logical_size)) != Some(&index) {
                continue;
            }
            let [left, top] = tile
                .position
                .map(|value| value.saturating_mul(scale as i32));
            let start_x = (-(left as i64)).clamp(0, tile.image.width as i64) as usize;
            let end_x =
                (context.width as i64 - left as i64).clamp(0, tile.image.width as i64) as usize;
            let start_y = (-(top as i64)).clamp(0, tile.image.height as i64) as usize;
            let end_y =
                (context.height as i64 - top as i64).clamp(0, tile.image.height as i64) as usize;
            if start_x >= end_x || start_y >= end_y {
                continue;
            }
            for y in start_y..end_y {
                let destination = (top as i64 + y as i64) as usize * context.width
                    + (left as i64 + start_x as i64) as usize;
                let source = y * tile.image.width + start_x;
                let length = end_x - start_x;
                let originals = &context.pixels[destination..destination + length];
                let hd = &tile.image.pixels[source..source + length];
                let output = &mut detailed.pixels[destination..destination + length];
                if originals.iter().all(|color| *color < 240) && hd.iter().all(|color| *color < 240)
                {
                    output.copy_from_slice(hd);
                } else {
                    for ((output, original), hd) in output.iter_mut().zip(originals).zip(hd) {
                        if *original < TRANSPARENT {
                            *output = if *original < 240 && *hd < 240 {
                                *hd
                            } else {
                                self.transition(*original, *hd, LEVELS - 1, palette)
                            };
                        }
                    }
                }
            }
        }
        image.pixels.copy_from_slice(&detailed.pixels);
        for (index, tile) in replacements.iter().enumerate() {
            if accepted.get(&(tile.position, tile.logical_size)) != Some(&index) {
                continue;
            }
            let [left, top] = tile
                .position
                .map(|value| value.saturating_mul(scale as i32));
            let band = (2 * scale)
                .min(tile.image.width / 2)
                .min(tile.image.height / 2)
                .max(1);
            let edges = self.tile_edges(tile, &accepted, &detailed, context, scale, band, palette);
            let weights: [usize; 8] = std::array::from_fn(|distance| edge_weight(distance, band));
            for sy in 0..tile.image.height {
                let yy = top as i64 + sy as i64;
                if yy < 0 || yy >= context.height as i64 {
                    continue;
                }
                let inner_row = sy >= band && sy < tile.image.height - band;
                let first_end = if inner_row { band } else { tile.image.width };
                let second_start = if inner_row {
                    tile.image.width - band
                } else {
                    tile.image.width
                };
                // Interior pixels already came from the joined HD layer. Only
                // the two edge segments (or a top/bottom row) need blending.
                for sx in (0..first_end).chain(second_start..tile.image.width) {
                    let xx = left as i64 + sx as i64;
                    if xx < 0 || xx >= context.width as i64 {
                        continue;
                    }
                    let destination = yy as usize * context.width + xx as usize;
                    let original = context.pixels[destination];
                    if original >= TRANSPARENT {
                        continue;
                    }
                    let raw = detailed.pixels[destination];
                    let horizontal = if sx < band {
                        Some((0, sx))
                    } else if tile.image.width - sx - 1 < band {
                        Some((1, tile.image.width - sx - 1))
                    } else {
                        None
                    };
                    let vertical = if sy < band {
                        Some((2, sy))
                    } else if tile.image.height - sy - 1 < band {
                        Some((3, tile.image.height - sy - 1))
                    } else {
                        None
                    };
                    let (target, distance) =
                        if let (Some((hside, hdistance)), Some((vside, vdistance))) =
                            (horizontal, vertical)
                        {
                            let corner = (vside - 2) * 2 + hside;
                            (
                                edges.corners[corner]
                                    .color(hdistance, vdistance, band, original, raw, palette),
                                hdistance.min(vdistance),
                            )
                        } else if let Some((side, distance)) = horizontal {
                            (
                                edges.color(side, sy, distance, original, raw, palette),
                                distance,
                            )
                        } else {
                            let (side, distance) = vertical.unwrap();
                            (
                                edges.color(side, sx, distance, original, raw, palette),
                                distance,
                            )
                        };
                    image.pixels[destination] =
                        self.transition(target, raw, weights[distance], palette);
                }
            }
        }
        // AFTER all tile edges/corners: copy authentic joined Original context.
        // These samples were never read by shared_target/tile_edges.
        for pixel in protected.keys() { image.pixels[*pixel] = context.pixels[*pixel]; }
        Composition { image, results }
    }

    /// Overlay one full opaque logical tile on a previously joined/scaled layer.
    /// `context` is the unchanged original layer, even after adjacent overlays.
    /// The outermost subpixel remains exactly that context; a smooth transition
    /// reaches full HD detail two logical pixels inward, without a raw-pixel strip.
    pub fn overlay(
        &mut self,
        layer: &mut Sprite,
        context: &Sprite,
        replacement: &Sprite,
        position: [i32; 2],
        logical_size: [usize; 2],
        scale: usize,
        palette: &[[u8; 3]; 256],
    ) -> OverlayResult {
        let result = validate(layer, context, replacement, logical_size, scale);
        if result != OverlayResult::Applied {
            return result;
        }
        self.prepare_palette(palette);
        let [x, y] = position.map(|coordinate| coordinate.saturating_mul(scale as i32));
        let band = (2 * scale)
            .min(replacement.width / 2)
            .min(replacement.height / 2)
            .max(1);
        for sy in 0..replacement.height {
            let yy = y as i64 + sy as i64;
            if yy < 0 || yy >= layer.height as i64 {
                continue;
            }
            for sx in 0..replacement.width {
                let xx = x as i64 + sx as i64;
                if xx < 0 || xx >= layer.width as i64 {
                    continue;
                }
                let destination = yy as usize * layer.width + xx as usize;
                let original = context.pixels[destination];
                if original >= TRANSPARENT {
                    // Sparse/transparent terrain is not a full opaque replacement.
                    continue;
                }
                let hd = replacement.pixels[sy * replacement.width + sx];
                let distance = sx
                    .min(sy)
                    .min(replacement.width - sx - 1)
                    .min(replacement.height - sy - 1);
                let weight = edge_weight(distance, band);
                layer.pixels[destination] = self.transition(original, hd, weight, palette);
            }
        }
        OverlayResult::Applied
    }

    fn prepare_palette(&mut self, palette: &[[u8; 3]; 256]) {
        if self.palette.as_ref() != Some(palette) {
            self.palette = Some(*palette);
            self.transitions.resize(256 * 256 * LEVELS, UNSET);
            self.transitions.fill(UNSET);
        }
    }

    fn tile_edges(
        &mut self,
        tile: &Replacement,
        accepted: &BTreeMap<([i32; 2], [usize; 2]), usize>,
        detailed: &Sprite,
        context: &Sprite,
        scale: usize,
        band: usize,
        palette: &[[u8; 3]; 256],
    ) -> EdgeTargets {
        let [width, height] = tile.logical_size;
        let [left, top] = tile
            .position
            .map(|value| value.saturating_mul(scale as i32) as i64);
        let right = left + tile.image.width as i64;
        let bottom = top + tile.image.height as i64;
        let neighbor = |dx: i32, dy: i32| {
            accepted.contains_key(&(
                [
                    tile.position[0].saturating_add(dx.saturating_mul(width as i32)),
                    tile.position[1].saturating_add(dy.saturating_mul(height as i32)),
                ],
                tile.logical_size,
            ))
        };
        let adjacent = [
            neighbor(-1, 0),
            neighbor(1, 0),
            neighbor(0, -1),
            neighbor(0, 1),
        ];
        let sides = std::array::from_fn(|side| {
            if !adjacent[side] {
                return Vec::new();
            }
            let length = if side < 2 {
                tile.image.height
            } else {
                tile.image.width
            };
            // Pair pristine detail at each mirrored distance across the join.
            // Repeating only the outer edge's sample throughout this band
            // stretches fine grain into ribs even when the source art joins.
            (0..length * band)
                .map(|sample| {
                    let offset = sample / band;
                    let distance = (sample % band) as i64;
                    let points = match side {
                        0 => [
                            [left - 1 - distance, top + offset as i64],
                            [left + distance, top + offset as i64],
                        ],
                        1 => [
                            [right - 1 - distance, top + offset as i64],
                            [right + distance, top + offset as i64],
                        ],
                        2 => [
                            [left + offset as i64, top - 1 - distance],
                            [left + offset as i64, top + distance],
                        ],
                        _ => [
                            [left + offset as i64, bottom - 1 - distance],
                            [left + offset as i64, bottom + distance],
                        ],
                    };
                    self.shared_target(detailed, context, &points, palette)
                })
                .collect()
        });
        let corners = std::array::from_fn(|corner| {
            let hside = corner % 2;
            let vside = 2 + corner / 2;
            let dx = if hside == 0 { -1 } else { 1 };
            let dy = if vside == 2 { -1 } else { 1 };
            let complete = adjacent[hside] && adjacent[vside] && neighbor(dx, dy);
            let bx = if hside == 0 { left } else { right };
            let by = if vside == 2 { top } else { bottom };
            CornerTarget {
                complete,
                // The same distance-aware rule applies in both axes at four
                // HD tiles' intersection, avoiding a flat corner-color patch.
                targets: if complete {
                    (0..band * band)
                        .map(|sample| {
                            let dx = (sample % band) as i64;
                            let dy = (sample / band) as i64;
                            self.shared_target(
                                detailed,
                                context,
                                &[
                                    [bx - 1 - dx, by - 1 - dy],
                                    [bx + dx, by - 1 - dy],
                                    [bx - 1 - dx, by + dy],
                                    [bx + dx, by + dy],
                                ],
                                palette,
                            )
                        })
                        .collect()
                } else {
                    Vec::new()
                },
            }
        });
        EdgeTargets {
            band,
            adjacent,
            sides,
            corners,
        }
    }

    fn shared_target(
        &mut self,
        detailed: &Sprite,
        context: &Sprite,
        points: &[[i64; 2]],
        palette: &[[u8; 3]; 256],
    ) -> Option<(u16, u16)> {
        let mut values = [0_u16; 4];
        let mut first = None;
        for (point, [x, y]) in points.iter().enumerate() {
            if *x < 0 || *y < 0 || *x >= context.width as i64 || *y >= context.height as i64 {
                return None;
            }
            let index = *y as usize * context.width + *x as usize;
            let source = context.pixels[index];
            let detail = detailed.pixels[index];
            if source >= TRANSPARENT || detail >= TRANSPARENT {
                return None;
            }
            let first_source = *first.get_or_insert(source);
            if !same_material(source, first_source, palette) {
                return None;
            }
            values[point] = detail;
        }
        let top = self.transition(values[0], values[1], LEVELS / 2, palette);
        let target = if points.len() == 2 {
            top
        } else {
            let bottom = self.transition(values[2], values[3], LEVELS / 2, palette);
            self.transition(top, bottom, LEVELS / 2, palette)
        };
        Some((target, first.unwrap()))
    }

    fn transition(
        &mut self,
        original: u16,
        hd: u16,
        weight: usize,
        palette: &[[u8; 3]; 256],
    ) -> u16 {
        if weight == 0 || original == hd {
            return original;
        }
        // A color nearest to a blinking light must not make ordinary terrain
        // blink. Conversely, remastered water/fire must remain in the original
        // cycling group. Single-index glow/flash masks keep their exact label.
        let range = match original {
            240..=244 => 240..245,
            245..=249 => 245..250,
            250..=255 => return original,
            _ => 0..240,
        };
        if weight == LEVELS - 1 && range.contains(&(hd as usize)) {
            return hd;
        }
        let key = (original as usize * 256 + hd as usize) * LEVELS + weight;
        if self.transitions[key] != UNSET {
            return self.transitions[key];
        }
        let color: [i32; 3] = std::array::from_fn(|channel| {
            (palette[original as usize][channel] as usize * (LEVELS - 1 - weight)
                + palette[hd as usize][channel] as usize * weight
                + (LEVELS - 1) / 2) as i32
                / (LEVELS - 1) as i32
        });
        let result = range
            .min_by_key(|index| {
                (0..3)
                    .map(|channel| (color[channel] - palette[*index][channel] as i32).pow(2))
                    .sum::<i32>()
            })
            .unwrap() as u16;
        self.transitions[key] = result;
        result
    }
}

struct EdgeTargets {
    band: usize,
    adjacent: [bool; 4],
    sides: [Vec<Option<(u16, u16)>>; 4],
    corners: [CornerTarget; 4],
}
impl EdgeTargets {
    fn color(
        &self,
        side: usize,
        offset: usize,
        distance: usize,
        original: u16,
        raw: u16,
        palette: &[[u8; 3]; 256],
    ) -> u16 {
        if !self.adjacent[side] {
            return original;
        }
        self.sides[side][offset * self.band + distance]
            .filter(|(_, source)| same_material(original, *source, palette))
            .map_or(raw, |(target, _)| target)
    }
}
struct CornerTarget {
    complete: bool,
    targets: Vec<Option<(u16, u16)>>,
}
impl CornerTarget {
    fn color(
        &self,
        horizontal_distance: usize,
        vertical_distance: usize,
        band: usize,
        original: u16,
        raw: u16,
        palette: &[[u8; 3]; 256],
    ) -> u16 {
        if !self.complete {
            return original;
        }
        self.targets[vertical_distance * band + horizontal_distance]
            .filter(|(_, source)| same_material(original, *source, palette))
            .map_or(raw, |(target, _)| target)
    }
}
#[inline]
fn same_material(first: u16, second: u16, palette: &[[u8; 3]; 256]) -> bool {
    first == second
        || (group(first) == group(second)
            && (0..3).all(|channel| {
                palette[first as usize][channel].abs_diff(palette[second as usize][channel]) <= 24
            }))
}

fn validate(
    layer: &Sprite,
    context: &Sprite,
    replacement: &Sprite,
    logical_size: [usize; 2],
    scale: usize,
) -> OverlayResult {
    let [width, height] = logical_size;
    if !matches!(scale, 1 | 2 | 3 | 4)
        || width == 0
        || height == 0
        || replacement.width != width.saturating_mul(scale)
        || replacement.height != height.saturating_mul(scale)
        || replacement.pixels.len() != replacement.width.saturating_mul(replacement.height)
        || context.width != layer.width
        || context.height != layer.height
        || layer.pixels.len() != layer.width.saturating_mul(layer.height)
        || context.pixels.len() != layer.pixels.len()
    {
        return OverlayResult::InvalidCanvas;
    }
    if replacement.pixels.iter().any(|pixel| *pixel >= TRANSPARENT) {
        return OverlayResult::NonOpaque;
    }
    OverlayResult::Applied
}

fn group(original: u16) -> std::ops::Range<usize> {
    match original {
        240..=244 => 240..245,
        245..=249 => 245..250,
        250..=255 => original as usize..original as usize + 1,
        _ => 0..240,
    }
}
fn edge_weight(distance: usize, band: usize) -> usize {
    if distance >= band {
        return LEVELS - 1;
    }
    // Integer smoothstep t²(3-2t), rounded to sixteen indexed weights.
    let denominator = band * band * band;
    (distance * distance * (3 * band - 2 * distance) * (LEVELS - 1) + denominator / 2) / denominator
}

#[cfg(test)]
mod retained_original_join_tests {
    use super::*;
    fn detail(index:usize,cells:Vec<[u32;2]>) -> RetainedOriginalPlacement {
        RetainedOriginalPlacement {replacement_index:index,
            details:crate::hd::OriginalDetailCells::for_test(cells,[32,32])}
    }
    fn palette()->[[u8;3];256] {std::array::from_fn(|i|[i as u8;3])}
    #[test]
    fn edge_protection_is_after_all_joins_no_neighbor_leak_at_any_scale() {
        for scale in 1..=4 {
            let context=Sprite {width:64*scale,height:32*scale,pixels:vec![17;64*32*scale*scale]};
            let tiles=vec![Replacement{image:Sprite{width:32*scale,height:32*scale,pixels:vec![60;32*32*scale*scale]},position:[0,0],logical_size:[32,32]},
                Replacement{image:Sprite{width:32*scale,height:32*scale,pixels:vec![80;32*32*scale*scale]},position:[32,0],logical_size:[32,32]}];
            let mut t=TerrainHd::default();let base=t.compose(&context,&tiles,scale,&palette()).image;
            let result=t.compose_retaining_original(&context,&tiles,&[detail(0,vec![[31,16]])],scale,&palette());
            assert!(result.results.iter().all(|r|*r==OverlayResult::Applied));
            for y in 0..context.height {for x in 0..context.width {
                let i=y*context.width+x;let protected=x/scale==31&&y/scale==16;
                assert_eq!(result.image.pixels[i],if protected{context.pixels[i]}else{base.pixels[i]});
            }}
            let empty=t.compose_retaining_original(&context,&tiles,&[],scale,&palette()).image;
            assert_eq!(base,empty);
        }
    }
    #[test]
    fn duplicate_protected_owners_fail_to_original_not_last_write() {
        let context=Sprite{width:64,height:32,pixels:vec![17;64*32]};
        let tiles=vec![Replacement{image:Sprite{width:32,height:32,pixels:vec![60;1024]},position:[0,0],logical_size:[32,32]},
            Replacement{image:Sprite{width:32,height:32,pixels:vec![80;1024]},position:[1,0],logical_size:[32,32]}];
        let result=TerrainHd::default().compose_retaining_original(&context,&tiles,
            &[detail(0,vec![[1,0]]),detail(1,vec![[0,0]])],1,&palette());
        assert_eq!(result.image,context);assert!(result.results.iter().all(|r|*r==OverlayResult::InvalidOriginalDetails));
    }

    #[test]
    fn reserved_detail_after_joins_preserves_functional_labels_and_never_leaks_to_neighbors() {
        let mut logical=Sprite{width:64,height:32,pixels:vec![17;64*32]};
        logical.pixels[15*64+31]=252;logical.pixels[16*64+31]=253;
        logical.pixels[15*64+32]=243;logical.pixels[16*64+32]=240;
        for scale in 1..=4 {
            let context=crate::render::upscale(&logical,scale).unwrap();
            let hd=vec![Replacement{image:Sprite{width:32*scale,height:32*scale,pixels:vec![60;32*32*scale*scale]},position:[0,0],logical_size:[32,32]},Replacement{image:Sprite{width:32*scale,height:32*scale,pixels:vec![80;32*32*scale*scale]},position:[32,0],logical_size:[32,32]}];
            let mut compositor=TerrainHd::default();
            let baseline=compositor.compose(&context,&hd,scale,&palette()).image;
            let hybrid=compositor.compose_retaining_original(&context,&hd,&[detail(0,vec![[31,15],[31,16]])],scale,&palette()).image;
            let mut phase=palette();phase[252]=[255,0,0];phase[253]=[0,255,0];
            let mut phase2=phase;phase2[252]=[0,0,0];phase2[253]=[255,255,255];
            let rgba1=crate::render::Canvas{image:hybrid.clone(),scale}.rgba(&phase,false);
            let rgba2=crate::render::Canvas{image:hybrid.clone(),scale}.rgba(&phase2,false);
            for y in 0..context.height {for x in 0..context.width {
                let i=y*context.width+x;let protected=x/scale==31&&(y/scale==15||y/scale==16);
                assert_eq!(hybrid.pixels[i],if protected{context.pixels[i]}else{baseline.pixels[i]});
                if protected&&(hybrid.pixels[i]==252||hybrid.pixels[i]==253){assert_ne!(&rgba1[i*4..i*4+3],&rgba2[i*4..i*4+3]);}
            }}
            let mixed=&hd[..1];let base_mixed=compositor.compose(&context,mixed,scale,&palette()).image;
            let retained_mixed=compositor.compose_retaining_original(&context,mixed,&[detail(0,vec![[31,15],[31,16]])],scale,&palette()).image;
            for y in 0..context.height {for x in 32*scale..context.width {
                let i=y*context.width+x;assert_eq!(retained_mixed.pixels[i],base_mixed.pixels[i],"foreign Original fallback unchanged");
            }}
        }
    }
}
