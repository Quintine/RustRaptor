//! Indexed visual contracts and independent ScaleNx specification oracle.
//! Original-data contact sheets are opt-in and remain under ignored .reference/.
use raptor_replica::{
    assets::{Catalog, Sprite, TRANSPARENT},
    content::Registry,
    render::{
        BitmapFont, Canvas, SpriteCache, legacy_light_table, nearest, prefers_nearest,
        shade_air_shadow, shade_ground_shadow, upscale,
    },
};
use std::{collections::BTreeSet, fs, path::Path};

// Uses independent per-corner consensus rules rather than the renderer's shared
// optimized guard. Source specification: https://www.scale2x.it/algorithm
fn oracle(source: &Sprite, factor: usize) -> Sprite {
    if factor == 1 {
        return source.clone();
    }
    if factor == 4 {
        return oracle(&oracle(source, 2), 2);
    }
    let mut result = Sprite::blank(source.width * factor, source.height * factor);
    for y in 0..source.height {
        for x in 0..source.width {
            let read = |dx: i32, dy: i32| {
                let column = (x as i32 + dx).max(0).min(source.width as i32 - 1) as usize;
                let row = (y as i32 + dy).max(0).min(source.height as i32 - 1) as usize;
                source.pixels[row * source.width + column]
            };
            let [a, b, c, d, e, f, g, h, i] = [
                read(-1, -1),
                read(0, -1),
                read(1, -1),
                read(-1, 0),
                read(0, 0),
                read(1, 0),
                read(-1, 1),
                read(0, 1),
                read(1, 1),
            ];
            let northwest = d == b && b != f && d != h;
            let northeast = b == f && b != d && f != h;
            let southwest = d == h && d != b && h != f;
            let southeast = h == f && d != h && b != f;
            let select = |condition, replacement| if condition { replacement } else { e };
            let values = if factor == 2 {
                vec![
                    select(northwest, d),
                    select(northeast, f),
                    select(southwest, d),
                    select(southeast, f),
                ]
            } else {
                vec![
                    select(northwest, d),
                    select((northwest && e != c) || (northeast && e != a), b),
                    select(northeast, f),
                    select((northwest && e != g) || (southwest && e != a), d),
                    e,
                    select((northeast && e != i) || (southeast && e != c), f),
                    select(southwest, d),
                    select((southwest && e != i) || (southeast && e != g), h),
                    select(southeast, f),
                ]
            };
            for yy in 0..factor {
                for xx in 0..factor {
                    result.pixels[(y * factor + yy) * result.width + x * factor + xx] =
                        values[yy * factor + xx];
                }
            }
        }
    }
    result
}

fn crop(source: &Sprite, x: usize, y: usize, width: usize, height: usize) -> Sprite {
    let mut out = Sprite::blank(width, height);
    for row in 0..height {
        out.pixels[row * width..(row + 1) * width].copy_from_slice(
            &source.pixels[(y + row) * source.width + x..(y + row) * source.width + x + width],
        );
    }
    out
}

fn pattern(width: usize, height: usize, mut seed: u32) -> Sprite {
    let pixels = (0..width * height)
        .map(|_| {
            seed = seed.wrapping_mul(1664525).wrapping_add(1013904223);
            [0, 1, 245, 255, TRANSPARENT][(seed >> 16) as usize % 5]
        })
        .collect();
    Sprite {
        width,
        height,
        pixels,
    }
}

#[test]
fn all_three_symbol_neighborhoods_match_unoptimized_published_oracle() {
    // 3^9 arrangements cover every local equality class for two colors plus
    // transparency; additional multi-color/border patterns are tested below.
    for mut code in 0..3_usize.pow(9) {
        let pixels = (0..9)
            .map(|_| {
                let value = [0, 245, TRANSPARENT][code % 3];
                code /= 3;
                value
            })
            .collect();
        let source = Sprite {
            width: 3,
            height: 3,
            pixels,
        };
        for factor in [2, 3, 4] {
            assert_eq!(upscale(&source, factor).unwrap(), oracle(&source, factor));
        }
    }
}

#[test]
fn clamped_borders_and_single_pixel_dimensions_match_oracle() {
    for (width, height) in [(1, 1), (1, 9), (9, 1), (2, 2), (7, 11)] {
        for seed in 0..20 {
            let source = pattern(width, height, seed);
            for factor in [1, 2, 3, 4] {
                assert_eq!(upscale(&source, factor).unwrap(), oracle(&source, factor));
            }
        }
    }
}

#[test]
fn scale_copies_palette_labels_and_keeps_opaque_black_and_white() {
    let source = Sprite {
        width: 3,
        height: 2,
        pixels: vec![0, 255, TRANSPARENT, 245, 0, 255],
    };
    let colors: BTreeSet<_> = source.pixels.iter().copied().collect();
    for factor in [1, 2, 3, 4] {
        let scaled = upscale(&source, factor).unwrap();
        assert!(scaled.pixels.iter().all(|value| colors.contains(value)));
        assert!(scaled.pixels.contains(&0));
        assert!(scaled.pixels.contains(&255));
        assert!(scaled.pixels.contains(&TRANSPARENT));
        assert_eq!(source.width, 3);
        assert_eq!(source.height, 2);
    }
    let mut canvas = Canvas::new(1);
    canvas.clear(37);
    canvas.blit(&source, 4, 5);
    let mut first = [[0; 3]; 256];
    first[0] = [1, 2, 3];
    first[255] = [250, 251, 252];
    first[245] = [200, 90, 10];
    first[37] = [8, 9, 10];
    let pixels_before = canvas.image.pixels.clone();
    let rgba_first = canvas.rgba(&first, false);
    first[245] = [10, 90, 200];
    let rgba_second = canvas.rgba(&first, false);
    assert_eq!(canvas.image.pixels, pixels_before);
    assert_ne!(rgba_first, rgba_second);
    assert_eq!(
        &rgba_second[((5 * 320 + 4) * 4)..((5 * 320 + 4) * 4 + 3)],
        &[1, 2, 3]
    );
    assert_eq!(canvas.image.pixels[5 * 320 + 6], 37);
}

#[test]
fn scaled_transparent_sprites_clip_cleanly_at_every_viewport_edge() {
    let source = pattern(7, 9, 19);
    for factor in [1, 2, 3, 4] {
        let sprite = upscale(&source, factor).unwrap();
        let width = 320 * factor;
        let height = 200 * factor;
        for (x, y) in [
            (-(sprite.width as i32) + 1, -(sprite.height as i32) + 1),
            (-3, 20),
            (30, -4),
            (width as i32 - 1, height as i32 - 1),
            (width as i32 - 4, 30),
            (40, height as i32 - 4),
            (-100, -100),
        ] {
            let mut canvas = Canvas::new(factor);
            canvas.clear(37);
            canvas.blit(&sprite, x, y);
            for yy in 0..height {
                for xx in 0..width {
                    let sx = xx as i32 - x;
                    let sy = yy as i32 - y;
                    let expected = if sx >= 0
                        && sy >= 0
                        && sx < sprite.width as i32
                        && sy < sprite.height as i32
                    {
                        let pixel = sprite.pixels[sy as usize * sprite.width + sx as usize];
                        if pixel == TRANSPARENT { 37 } else { pixel }
                    } else {
                        37
                    };
                    assert_eq!(canvas.image.pixels[yy * width + xx], expected);
                }
            }
        }
    }
}

#[test]
fn two_pixel_terrain_context_matches_full_joined_filter_at_all_scales() {
    let source = pattern(18, 18, 28);
    let with_gutter = crop(&source, 4, 4, 10, 10);
    for factor in [2, 3, 4] {
        let full = upscale(&source, factor).unwrap();
        let gutter = upscale(&with_gutter, factor).unwrap();
        assert_eq!(
            crop(&full, 6 * factor, 6 * factor, 6 * factor, 6 * factor),
            crop(&gutter, 2 * factor, 2 * factor, 6 * factor, 6 * factor)
        );
        assert_eq!(gutter, oracle(&with_gutter, factor));
    }
}

#[test]
fn independent_tile_filtering_is_detected_by_joined_seam_regression() {
    let source = pattern(8, 6, 1);
    let left = crop(&source, 0, 0, 4, 6);
    let right = crop(&source, 4, 0, 4, 6);
    for factor in [2, 3, 4] {
        let joined = upscale(&source, factor).unwrap();
        let a = upscale(&left, factor).unwrap();
        let b = upscale(&right, factor).unwrap();
        let mut tiled = Sprite::blank(8 * factor, 6 * factor);
        for row in 0..tiled.height {
            tiled.pixels[row * tiled.width..row * tiled.width + a.width]
                .copy_from_slice(&a.pixels[row * a.width..(row + 1) * a.width]);
            tiled.pixels[row * tiled.width + a.width..(row + 1) * tiled.width]
                .copy_from_slice(&b.pixels[row * b.width..(row + 1) * b.width]);
        }
        assert_ne!(joined, tiled, "fixture must expose a seam at scale{factor}");
    }
}

#[test]
fn bitmap_text_keeps_exact_square_pixel_blocks_at_every_scale() {
    let mut bytes = vec![0; 772];
    bytes[..4].copy_from_slice(&2_i32.to_le_bytes());
    bytes[516 + b'A' as usize] = 3;
    bytes.extend([1, 0, 1, 0, 1, 0]);
    let font = BitmapFont::decode(&bytes).unwrap();
    assert_eq!(font.height(), 2);
    for scale in [1, 2, 3, 4] {
        let mut canvas = Canvas::new(scale);
        canvas.clear(37);
        font.text(&mut canvas, 10, 20, "A", 100);
        for y in 0..2 * scale {
            for x in 0..3 * scale {
                let expected = if [1, 0, 1, 0, 1, 0][y / scale * 3 + x / scale] == 0 {
                    37
                } else {
                    100
                };
                assert_eq!(
                    canvas.image.pixels[(20 * scale + y) * canvas.image.width + 10 * scale + x],
                    expected
                );
            }
        }
        assert_eq!(
            canvas
                .image
                .pixels
                .iter()
                .filter(|pixel| **pixel == 100)
                .count(),
            3 * scale * scale
        );
    }
}

#[test]
fn indexed_shadow_masks_clip_without_shading_transparent_pixels() {
    let mask = Sprite {
        width: 3,
        height: 3,
        pixels: vec![
            TRANSPARENT,
            1,
            TRANSPARENT,
            1,
            1,
            1,
            TRANSPARENT,
            1,
            TRANSPARENT,
        ],
    };
    let mut canvas = Canvas::new(2);
    canvas.clear(10);
    let mut lookup = std::array::from_fn(|index| index as u8);
    lookup[10] = 11;
    let y = canvas.image.height as i32 - 2;
    canvas.shade(&mask, -1, y, &lookup);
    for yy in 0..canvas.image.height {
        for x in 0..canvas.image.width {
            let source_x = x + 1;
            let source_y = yy as i32 - y;
            let affected = source_x < 3
                && (0..3).contains(&source_y)
                && mask.pixels[source_y as usize * 3 + source_x] != TRANSPARENT;
            assert_eq!(
                canvas.image.pixels[yy * canvas.image.width + x],
                if affected { 11 } else { 10 }
            );
        }
    }
}

#[test]
fn vga_light_tables_clamp_six_bit_channels_and_choose_last_equal_match() {
    let palette = std::array::from_fn(|index| [(index % 64) as u8; 3]);
    let identity = legacy_light_table(&palette, 0);
    let dark = legacy_light_table(&palette, -9);
    let light = legacy_light_table(&palette, 9);
    for index in 0..256 {
        assert_eq!(identity[index], 192 + (index % 64) as u8);
        assert_eq!(dark[index], 192 + (index % 64).saturating_sub(9) as u8);
        assert_eq!(light[index], 192 + ((index % 64) + 9).min(63) as u8);
    }
}

#[test]
fn vga_remap_uses_manhattan_rgb_distance_instead_of_squared_distance() {
    let mut palette = [[63; 3]; 256];
    palette[0] = [20; 3];
    palette[1] = [14, 10, 10]; // Manhattan 4, squared distance 16.
    palette[2] = [12, 12, 11]; // Manhattan 5, squared distance 9.
    assert_eq!(legacy_light_table(&palette, -10)[0], 1);
}

#[test]
fn ground_shadows_keep_native_mask_offsets_and_clip_at_every_scale() {
    let mask = pattern(7, 9, 31);
    let lookup = std::array::from_fn(|index| index.saturating_add(1).min(255) as u8);
    for (x, y) in [(3, -4), (-2, 40), (320, 190), (100, 197), (-20, -30)] {
        let mut native = Canvas::new(1);
        native.clear(10);
        // Reference inverse mask coordinates include SHADOW_GAdd's (-3,+4).
        for yy in 0..200 {
            for xx in 0..320 {
                let sx = xx as i32 - x + 3;
                let sy = yy as i32 - y - 4;
                if (0..mask.width as i32).contains(&sx)
                    && (0..mask.height as i32).contains(&sy)
                    && mask.pixels[sy as usize * mask.width + sx as usize] != TRANSPARENT
                {
                    native.image.pixels[yy * 320 + xx] = 11;
                }
            }
        }
        for scale in [1, 2, 3, 4] {
            let mut actual = Canvas::new(scale);
            actual.clear(10);
            shade_ground_shadow(&mut actual, &mask, x as f32, y as f32, &lookup);
            assert_eq!(actual.image, nearest(&native.image, scale));
        }
    }
}

// Reference SHADOW_Draw at native integer coordinates. Find mask runs from
// occupied coordinates, project their endpoints, then expand the final native
// raster. This keeps the oracle independent of high-resolution span drawing.
fn native_air_shadow(mask: &Sprite, x: i32, y: i32, lookup: &[u8; 256]) -> Sprite {
    let project = |value: i32, center: i32| {
        let fixed = ((value - center) as i64 * 409_600) / 280;
        (fixed >> 11) as i32 + center
    };
    let mut result = Sprite {
        width: 320,
        height: 200,
        pixels: vec![10; 320 * 200],
    };
    let mut seen_rows = BTreeSet::new();
    for row in 0..mask.height {
        let occupied: Vec<_> = (0..mask.width)
            .filter(|&column| mask.pixels[row * mask.width + column] != TRANSPARENT)
            .collect();
        if occupied.is_empty() {
            continue;
        }
        let yy = project(y + 20 + row as i32, 100);
        if !seen_rows.insert(yy) || !(0..200).contains(&yy) {
            continue;
        }
        let mut starts = vec![0];
        for index in 1..occupied.len() {
            if occupied[index] != occupied[index - 1] + 1 {
                starts.push(index);
            }
        }
        starts.push(occupied.len());
        for endpoints in starts.windows(2) {
            let start = project(x - 10 + occupied[endpoints[0]] as i32, 160);
            let end = project(x - 10 + occupied[endpoints[1] - 1] as i32, 160);
            for xx in start.max(0)..=end.min(319) {
                let pixel = &mut result.pixels[yy as usize * 320 + xx as usize];
                *pixel = lookup[*pixel as usize] as u16;
            }
        }
    }
    result
}

#[test]
fn air_shadows_project_signed_spans_and_suppress_collapsed_rows() {
    let mask = Sprite {
        width: 7,
        height: 7,
        pixels: vec![1; 49],
    };
    let lookup = std::array::from_fn(|index| index.saturating_add(1).min(255) as u8);
    for scale in [1, 2, 3, 4] {
        let mut actual = Canvas::new(scale);
        actual.clear(10);
        shade_air_shadow(&mut actual, &mask, 170.0, 80.0, &lookup);
        assert_eq!(
            actual.image,
            nearest(&native_air_shadow(&mask, 170, 80, &lookup), scale)
        );
        assert_eq!(
            actual.image.pixels.iter().filter(|&&p| p == 11).count(),
            25 * scale * scale
        );
        assert!(
            !actual.image.pixels.contains(&12),
            "collapsed rows must not shade twice"
        );
        assert_eq!(
            actual.image.pixels[100 * scale * actual.image.width + 160 * scale],
            11
        );
        assert_eq!(
            actual.image.pixels[105 * scale * actual.image.width + 160 * scale],
            10
        );
    }
}

#[test]
fn air_shadows_preserve_sparse_mask_spans_and_clip_projected_edges() {
    let mask = pattern(21, 17, 76);
    let lookup = std::array::from_fn(|index| index.saturating_add(1).min(255) as u8);
    for (x, y) in [
        (12, -48),
        (-55, 30),
        (389, 198),
        (165, 64),
        (303, 223),
        (-80, -70),
    ] {
        let expected = native_air_shadow(&mask, x, y, &lookup);
        for scale in [1, 2, 3, 4] {
            let mut actual = Canvas::new(scale);
            actual.clear(10);
            shade_air_shadow(&mut actual, &mask, x as f32, y as f32, &lookup);
            assert_eq!(
                actual.image,
                nearest(&expected, scale),
                "air position ({x},{y}) at{scale}x"
            );
        }
    }
}

#[test]
fn interpolated_shadows_translate_masks_without_changing_coverage_or_transparency() {
    let mask = Sprite {
        width: 7,
        height: 7,
        pixels: vec![1; 49],
    };
    let lookup = std::array::from_fn(|index| index.saturating_add(1).min(255) as u8);
    let mut integer = Canvas::new(4);
    integer.clear(10);
    shade_air_shadow(&mut integer, &mask, 170.0, 80.0, &lookup);
    let mut half = Canvas::new(4);
    half.clear(10);
    shade_air_shadow(&mut half, &mask, 170.5, 80.5, &lookup);
    assert_eq!(half.image.pixels.iter().filter(|&&p| p == 11).count(), 400);
    for y in 100 * 4..105 * 4 {
        for x in 160 * 4..165 * 4 {
            assert_eq!(
                integer.image.pixels[y * integer.image.width + x],
                half.image.pixels[(y + 1) * half.image.width + x + 1]
            );
        }
    }
    let mut empty = Canvas::new(4);
    empty.clear(TRANSPARENT);
    shade_air_shadow(&mut empty, &mask, 170.0, 80.0, &lookup);
    assert!(empty.image.pixels.iter().all(|&p| p == TRANSPARENT));
    shade_ground_shadow(&mut empty, &mask, 10.0, 10.0, &lookup);
    assert!(empty.image.pixels.iter().all(|&p| p == TRANSPARENT));
}

fn png(sprite: &Sprite, palette: &[[u8; 3]; 256], path: &Path) {
    let mut image = image::RgbaImage::new(sprite.width as u32, sprite.height as u32);
    for (index, &value) in sprite.pixels.iter().enumerate() {
        let color = if value == TRANSPARENT {
            [0, 0, 0, 0]
        } else {
            let [r, g, b] = palette[value as usize];
            [r, g, b, 255]
        };
        image.put_pixel(
            (index % sprite.width) as u32,
            (index / sprite.width) as u32,
            image::Rgba(color),
        );
    }
    image.save(path).unwrap();
}

fn sheet(sprites: &[Sprite], columns: usize, palette: &[[u8; 3]; 256], path: &Path) {
    let width = sprites.iter().map(|s| s.width).max().unwrap() + 12;
    let height = sprites.iter().map(|s| s.height).max().unwrap() + 12;
    let rows = sprites.len().div_ceil(columns);
    let mut canvas = Canvas::new(1);
    canvas.image = Sprite {
        width: columns * width,
        height: rows * height,
        pixels: vec![0; columns * width * rows * height],
    };
    for (index, sprite) in sprites.iter().enumerate() {
        canvas.blit(
            sprite,
            ((index % columns) * width + 6) as i32,
            ((index / columns) * height + 6) as i32,
        );
    }
    png(&canvas.image, palette, path);
}

#[test]
#[ignore = "requires local original palette and sprites; emits private shadow contacts"]
fn original_shadow_tables_and_banking_masks_match_indexed_projection() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR"));
    let catalog = Catalog::open(root.join("data")).unwrap();
    let palette = catalog.palette().unwrap();
    let bytes = catalog.named("PALETTE_DAT").unwrap();
    let vga: [[u8; 3]; 256] = std::array::from_fn(|i| bytes[i * 3..i * 3 + 3].try_into().unwrap());
    assert_eq!(palette.map(|rgb| rgb.map(|component| component >> 2)), vga);
    let output = root.join(".reference/visuals");
    fs::create_dir_all(&output).unwrap();
    // Independent argmin over (distance, reverse index) preserves GFX_Remap's
    // last-equal tie rule without the renderer's imperative running minimum.
    for level in [-9, -6, 9] {
        let expected: [u8; 256] = std::array::from_fn(|index| {
            let target = vga[index].map(|component| (component as i32 + level).clamp(0, 63));
            (0..256)
                .min_by_key(|&candidate| {
                    let distance: i32 = vga[candidate]
                        .iter()
                        .zip(target)
                        .map(|(&a, b)| (a as i32 - b).abs())
                        .sum();
                    (distance, std::cmp::Reverse(candidate))
                })
                .unwrap() as u8
        });
        assert_eq!(legacy_light_table(&vga, level), expected);
    }
    let air = legacy_light_table(&vga, -6);
    let ground = legacy_light_table(&vga, -9);
    let mut banking = vec![];
    let base = catalog.id("LPLAYER_PIC").unwrap();
    let terrain_id = Registry::base(&catalog).unwrap().missions[&"base:sector_1_wave_1".into()]
        .tiles[0]
        .art
        .asset
        .unwrap();
    let tile = catalog.sprite(terrain_id).unwrap();
    for frame in 0..7 {
        let mask = catalog.sprite(base + frame).unwrap();
        let lookup = std::array::from_fn(|index| index.saturating_add(1).min(255) as u8);
        for scale in [1, 2, 3, 4] {
            let mut actual = Canvas::new(scale);
            actual.clear(10);
            shade_air_shadow(&mut actual, &mask, 144.0, 160.0, &lookup);
            assert_eq!(
                actual.image,
                nearest(&native_air_shadow(&mask, 144, 160, &lookup), scale)
            );
        }
        let mut preview = Canvas::new(4);
        for y in (0..200).step_by(tile.height) {
            for x in (0..320).step_by(tile.width) {
                preview.blit(&upscale(&tile, 4).unwrap(), (x * 4) as i32, (y * 4) as i32);
            }
        }
        shade_air_shadow(&mut preview, &mask, 144.0, 160.0, &air);
        preview.blit(&upscale(&mask, 4).unwrap(), 144 * 4, 160 * 4);
        banking.push(crop(&preview.image, 112 * 4, 132 * 4, 80 * 4, 68 * 4));
    }
    sheet(
        &banking,
        7,
        &palette,
        &output.join("player-shadow-banking-4x.png"),
    );
    let mask = catalog.sprite(catalog.id("SHIP37G1_PIC").unwrap()).unwrap();
    let mut preview = Canvas::new(4);
    for y in (0..200).step_by(tile.height) {
        for x in (0..320).step_by(tile.width) {
            preview.blit(&upscale(&tile, 4).unwrap(), (x * 4) as i32, (y * 4) as i32);
        }
    }
    shade_ground_shadow(&mut preview, &mask, 144.0, 80.0, &ground);
    preview.blit(&upscale(&mask, 4).unwrap(), 144 * 4, 80 * 4);
    png(
        &crop(&preview.image, 128 * 4, 64 * 4, 64 * 4, 64 * 4),
        &palette,
        &output.join("ground-shadow-4x.png"),
    );
    fs::write(
        output.join("shadow-tables.json"),
        serde_json::to_vec_pretty(&serde_json::json!({
            "ground_offset":[-3,4],"ground_level":-9,"air_offset":[-10,20],"air_level":-6,
            "air_view":[160,100,1000],"air_depth":1280,"distance":200,
            "ground_table":ground.to_vec(),"air_table":air.to_vec()
        }))
        .unwrap(),
    )
    .unwrap();
}

#[test]
#[ignore = "requires local original catalog; emits private .reference/visuals contact sheets"]
fn original_sequences_preserve_canvases_palette_origins_and_terrain_context() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR"));
    let catalog = Catalog::open(root.join("data")).unwrap();
    let palette = catalog.palette().unwrap();
    let output = root.join(".reference/visuals");
    fs::create_dir_all(&output).unwrap();
    let sequences = [
        ("LPLAYER_PIC", 7),
        ("DPLAYER_PIC", 7),
        ("FPLAYER_PIC", 7),
        ("GEXPLO_BLK", 42),
        ("AIRBOOM_PIC", 16),
        ("EXPLO2_BLK", 13),
        ("NMSHOT_BLK", 4),
        ("GUNSTR_BLK", 4),
        ("SHIP22G1_PIC", 6),
        ("SHIP08G1_PIC", 4),
    ];
    let mut report = vec![];
    let mut runtime_cache = SpriteCache::new(None);
    for (name, count) in sequences {
        let base = catalog.id(name).unwrap();
        let first = catalog.sprite(base).unwrap();
        let mut original = vec![];
        let mut filtered = vec![];
        let mut runtime = vec![];
        let mut metadata = vec![];
        for frame in 0..count {
            let sprite = catalog.sprite(base + frame).unwrap();
            assert_eq!(
                (sprite.width, sprite.height),
                (first.width, first.height),
                "{name} frame{frame} shifts animation canvas"
            );
            let labels: BTreeSet<_> = sprite.pixels.iter().copied().collect();
            let mut bounds = vec![];
            for factor in [1, 2, 3, 4] {
                let scaled = upscale(&sprite, factor).unwrap();
                assert_eq!(
                    scaled,
                    oracle(&sprite, factor),
                    "{name} frame{frame} scale{factor}"
                );
                assert!(scaled.pixels.iter().all(|value| labels.contains(value)));
                assert_eq!(
                    (scaled.width, scaled.height),
                    (sprite.width * factor, sprite.height * factor)
                );
                let use_nearest = prefers_nearest(base + frame);
                let presented = runtime_cache.get(&sprite, factor, use_nearest).unwrap();
                if use_nearest {
                    assert_eq!(*presented, nearest(&sprite, factor));
                    assert_eq!(
                        presented
                            .pixels
                            .iter()
                            .filter(|pixel| **pixel != TRANSPARENT)
                            .count(),
                        sprite
                            .pixels
                            .iter()
                            .filter(|pixel| **pixel != TRANSPARENT)
                            .count()
                            * factor
                            * factor,
                        "{name} frame{frame} loses opacity under nearest fallback"
                    );
                } else {
                    assert_eq!(*presented, scaled);
                }
                if factor == 4 {
                    runtime.push(presented.clone());
                }
                // C++ centers registered animations using the full frame canvas,
                // never its changing opaque bounds. Keep that anchor at every scale.
                let anchor = (sprite.width as i32 / 2, sprite.height as i32 / 2);
                let mut canvas = Canvas::new(factor);
                canvas.clear(37);
                canvas.blit(
                    &scaled,
                    (160 - anchor.0) * factor as i32,
                    (100 - anchor.1) * factor as i32,
                );
                assert_eq!(
                    (160 - anchor.0) * factor as i32 + anchor.0 * factor as i32,
                    160 * factor as i32
                );
                let mut minx = scaled.width;
                let mut miny = scaled.height;
                let mut maxx = 0;
                let mut maxy = 0;
                for (index, &pixel) in scaled.pixels.iter().enumerate() {
                    if pixel != TRANSPARENT {
                        minx = minx.min(index % scaled.width);
                        miny = miny.min(index / scaled.width);
                        maxx = maxx.max(index % scaled.width + 1);
                        maxy = maxy.max(index / scaled.width + 1);
                    }
                }
                bounds.push(serde_json::json!({"factor":factor,"bounds":[minx,miny,maxx,maxy],
                    "opaque_pixels":scaled.pixels.iter().filter(|pixel|**pixel!=TRANSPARENT).count()}));
                if factor == 4 {
                    filtered.push(scaled);
                }
            }
            original.push(nearest(&sprite, 4));
            metadata.push(serde_json::json!({"frame":frame,"asset":format!("{:05x}",base+frame),"logical_canvas":[sprite.width,sprite.height],"center_anchor":[sprite.width/2,sprite.height/2],"nearest_fallback":prefers_nearest(base+frame),"bounds":bounds}));
        }
        sheet(
            &original,
            7.min(count as usize),
            &palette,
            &output.join(format!("{name}-nearest4.png")),
        );
        sheet(
            &filtered,
            7.min(count as usize),
            &palette,
            &output.join(format!("{name}-scale4.png")),
        );
        sheet(
            &runtime,
            7.min(count as usize),
            &palette,
            &output.join(format!("{name}-runtime4.png")),
        );
        report.push(serde_json::json!({"name":name,"frames":metadata}));
    }
    let registry = Registry::base(&catalog).unwrap();
    let mission = &registry.missions[&"base:sector_1_wave_1".into()];
    let columns = mission.columns as usize;
    let rows = mission.layout.len() / columns;
    let selected = (0..rows - 2)
        .find(|row| {
            let labels: BTreeSet<_> = (0..3)
                .flat_map(|y| (0..3).map(move |x| mission.layout[(row + y) * columns + x + 3]))
                .collect();
            labels.len() > 2
        })
        .unwrap();
    let mut joined = Canvas::new(1);
    joined.image = Sprite {
        width: 96,
        height: 96,
        pixels: vec![0; 96 * 96],
    };
    let mut tiles = vec![];
    for row in 0..3 {
        for column in 0..3 {
            let index = mission.layout[(selected + row) * columns + column + 3];
            let sprite = catalog
                .sprite(mission.tiles[index].art.asset.unwrap())
                .unwrap();
            assert_eq!((sprite.width, sprite.height), (32, 32));
            joined.blit(&sprite, (column * 32) as i32, (row * 32) as i32);
            tiles.push(sprite);
        }
    }
    let mut seam_counts = vec![];
    for factor in [2, 3, 4] {
        let filtered = upscale(&joined.image, factor).unwrap();
        assert_eq!(filtered, oracle(&joined.image, factor));
        let gutter = crop(&joined.image, 30, 30, 36, 36);
        assert_eq!(
            crop(
                &filtered,
                32 * factor,
                32 * factor,
                32 * factor,
                32 * factor
            ),
            crop(
                &upscale(&gutter, factor).unwrap(),
                2 * factor,
                2 * factor,
                32 * factor,
                32 * factor
            )
        );
        let mut tiled = Canvas::new(1);
        tiled.image = Sprite::blank(96 * factor, 96 * factor);
        for (index, tile) in tiles.iter().enumerate() {
            tiled.blit(
                &upscale(tile, factor).unwrap(),
                ((index % 3) * 32 * factor) as i32,
                ((index / 3) * 32 * factor) as i32,
            );
        }
        let differences = filtered
            .pixels
            .iter()
            .zip(&tiled.image.pixels)
            .filter(|(a, b)| a != b)
            .count();
        seam_counts
            .push(serde_json::json!({"factor":factor,"independent_tile_differences":differences}));
        png(
            &filtered,
            &palette,
            &output.join(format!("terrain-joined-{factor}x.png")),
        );
        png(
            &tiled.image,
            &palette,
            &output.join(format!("terrain-independent-{factor}x.png")),
        );
    }
    fs::write(output.join("report.json"),serde_json::to_vec_pretty(&serde_json::json!({"sequences":report,"terrain_source_row":selected,"terrain_differences":seam_counts})).unwrap()).unwrap();
}
