//! Terrain remasters preserve native geometry, scrolling and palette semantics.
use raptor_replica::{
    assets::{Catalog, Sprite, TRANSPARENT},
    content::{ContentPack, Registry, TileDef},
    hd::HdAssets,
    modding::ScriptRuntime,
    persistence::Pilot,
    render::{Canvas, upscale},
    simulation::{Input, World},
    terrain_hd::{OverlayResult, Replacement, TerrainHd, logical_sprite, selected_art},
};
use serde_json::json;

fn solid(width: usize, height: usize, color: u16) -> Sprite {
    Sprite {
        width,
        height,
        pixels: vec![color; width * height],
    }
}
fn palette() -> [[u8; 3]; 256] {
    std::array::from_fn(|index| [index as u8; 3])
}
fn at(sprite: &Sprite, x: usize, y: usize) -> u16 {
    sprite.pixels[y * sprite.width + x]
}

#[test]
fn neighboring_hd_tiles_share_the_original_context_at_every_edge_and_keep_interior_detail() {
    let mut source = solid(64, 32, 40);
    // A diagonal coastline passes through the shared boundary, exercising joined
    // ScaleNx rather than separately filtering either tile with clamped edges.
    for y in 0..32 {
        for x in 0..64 {
            if x >= 25 + y / 2 {
                source.pixels[y * 64 + x] = 80;
            }
        }
    }
    for scale in [1, 2, 3, 4] {
        let context = upscale(&source, scale).unwrap();
        let mut layer = context.clone();
        let mut compositor = TerrainHd::default();
        assert_eq!(
            compositor.overlay(
                &mut layer,
                &context,
                &solid(32 * scale, 32 * scale, 180),
                [0, 0],
                [32, 32],
                scale,
                &palette()
            ),
            OverlayResult::Applied
        );
        assert_eq!(
            compositor.overlay(
                &mut layer,
                &context,
                &solid(32 * scale, 32 * scale, 210),
                [32, 0],
                [32, 32],
                scale,
                &palette()
            ),
            OverlayResult::Applied
        );
        for y in 0..32 * scale {
            for x in [0, 32 * scale - 1, 32 * scale, 64 * scale - 1] {
                assert_eq!(at(&layer, x, y), at(&context, x, y));
            }
        }
        assert_eq!(at(&layer, 16 * scale, 16 * scale), 180);
        assert_eq!(at(&layer, 48 * scale, 16 * scale), 210);
        let band: Vec<_> = (0..=2 * scale).map(|x| at(&layer, x, 16 * scale)).collect();
        assert!(band.windows(2).all(|pair| pair[0] <= pair[1]));
        assert!(
            band.iter().any(|color| *color > 40 && *color < 180),
            "edge must transition rather than a hard raw-pixel strip"
        );
        assert_eq!(compositor.cache_bytes(), 2 * 1024 * 1024);
    }
}

#[test]
fn missing_hd_tiles_keep_neighbor_context_and_overlays_are_order_independent() {
    let source = Sprite {
        width: 64,
        height: 32,
        pixels: (0..64 * 32)
            .map(|index| if index % 64 < index / 64 + 20 { 40 } else { 90 })
            .collect(),
    };
    let context = upscale(&source, 4).unwrap();
    let replacement = solid(128, 128, 180);
    let mut mixed = context.clone();
    let mut compositor = TerrainHd::default();
    compositor.overlay(
        &mut mixed,
        &context,
        &replacement,
        [0, 0],
        [32, 32],
        4,
        &palette(),
    );
    for y in 0..128 {
        assert_eq!(
            &mixed.pixels[y * 256 + 128..(y + 1) * 256],
            &context.pixels[y * 256 + 128..(y + 1) * 256]
        );
    }
    let mut forward = context.clone();
    let mut reverse = context.clone();
    for x in [0, 32] {
        compositor.overlay(
            &mut forward,
            &context,
            &replacement,
            [x, 0],
            [32, 32],
            4,
            &palette(),
        );
    }
    for x in [32, 0] {
        compositor.overlay(
            &mut reverse,
            &context,
            &replacement,
            [x, 0],
            [32, 32],
            4,
            &palette(),
        );
    }
    assert_eq!(forward, reverse);
}

#[test]
fn complete_hd_neighborhood_has_shared_detailed_edges_and_corners_without_an_original_pixel_grid() {
    for scale in [1, 2, 3, 4] {
        let context = solid(64 * scale, 64 * scale, 40);
        let replacements: Vec<_> = [
            ([0, 0], 180),
            ([32, 0], 190),
            ([0, 32], 200),
            ([32, 32], 210),
        ]
        .into_iter()
        .map(|(position, color)| Replacement {
            image: solid(32 * scale, 32 * scale, color),
            position,
            logical_size: [32, 32],
        })
        .collect();
        let mut compositor = TerrainHd::default();
        let forward = compositor.compose(&context, &replacements, scale, &palette());
        assert!(
            forward
                .results
                .iter()
                .all(|result| *result == OverlayResult::Applied)
        );
        let mut reversed = replacements;
        reversed.reverse();
        let reverse = compositor.compose(&context, &reversed, scale, &palette());
        assert_eq!(forward.image, reverse.image);
        for y in 4 * scale..60 * scale {
            for x in [32 * scale - 1, 32 * scale] {
                assert!(
                    at(&forward.image, x, y) >= 180,
                    "full HD edge must not revert to source color 40"
                );
            }
        }
        for x in 4 * scale..60 * scale {
            for y in [32 * scale - 1, 32 * scale] {
                assert!(at(&forward.image, x, y) >= 180);
            }
        }
        assert_eq!(
            at(&forward.image, 32 * scale - 1, 16 * scale),
            at(&forward.image, 32 * scale, 16 * scale)
        );
        let corner = at(&forward.image, 32 * scale - 1, 32 * scale - 1);
        for (x, y) in [
            (32 * scale, 32 * scale - 1),
            (32 * scale - 1, 32 * scale),
            (32 * scale, 32 * scale),
        ] {
            assert_eq!(at(&forward.image, x, y), corner);
        }
    }
}

#[test]
fn shared_hd_edges_preserve_original_hard_material_boundaries_and_mixed_fallback() {
    let mut context = solid(256, 128, 40);
    for y in 0..128 {
        context.pixels[y * 256 + 128..(y + 1) * 256].fill(80);
    }
    let mut compositor = TerrainHd::default();
    let replacements = [
        Replacement {
            image: solid(128, 128, 180),
            position: [0, 0],
            logical_size: [32, 32],
        },
        Replacement {
            image: solid(128, 128, 210),
            position: [32, 0],
            logical_size: [32, 32],
        },
    ];
    let complete = compositor.compose(&context, &replacements, 4, &palette());
    assert_eq!(at(&complete.image, 127, 64), 180);
    assert_eq!(at(&complete.image, 128, 64), 210);
    let mixed = compositor.compose(&context, &replacements[..1], 4, &palette());
    assert_eq!(at(&mixed.image, 127, 64), 40);
    assert_eq!(at(&mixed.image, 128, 64), 80);
    assert_eq!(at(&mixed.image, 100, 64), 180);
}

#[test]
fn negative_gutters_and_fractional_scroll_move_the_completed_layer_together() {
    for scale in [1, 2, 3, 4] {
        let context = solid(320 * scale, 204 * scale, 30);
        let mut compositor = TerrainHd::default();
        let layer = compositor
            .compose(
                &context,
                &[Replacement {
                    image: solid(32 * scale, 32 * scale, 180),
                    position: [16, -10],
                    logical_size: [32, 32],
                }],
                scale,
                &palette(),
            )
            .image;
        // The replacement extends above the gutter, and is cropped without
        // wrapping into another row. Its lower interior remains full detail.
        assert_eq!(at(&layer, 32 * scale, 0), 180);
        assert_eq!(at(&layer, 15 * scale, 0), 30);
        for alpha in [0.0_f32, 0.25, 0.5, 0.75, 1.0] {
            let shift = (-2.0 * scale as f32 + (alpha - 1.0) * scale as f32).round() as i32;
            let mut canvas = Canvas::new(scale);
            canvas.blit(&layer, 0, shift);
            for y in 0..canvas.image.height {
                let source_y = (y as i32 - shift) as usize;
                assert_eq!(
                    &canvas.image.pixels[y * canvas.image.width..(y + 1) * canvas.image.width],
                    &layer.pixels[source_y * layer.width..(source_y + 1) * layer.width]
                );
            }
        }
    }
}

#[test]
fn row_aligned_strip_matches_uncached_joined_terrain_at_every_scroll_phase() {
    let tiles: Vec<_> = (0..16)
        .map(|row| Sprite {
            width: 64,
            height: 32,
            pixels: (0..64 * 32)
                .map(|index| {
                    let (x, y) = (index % 64, index / 64);
                    if (x + y + row * 7) % 23 < 11 {
                        40 + row as u16
                    } else {
                        240 + (row % 5) as u16
                    }
                })
                .collect(),
        })
        .collect();
    for scale in [1, 2, 3, 4] {
        for origin in [-192, -224] {
            let mut prepared = Canvas {
                scale: 1,
                image: solid(64, 268, 0),
            };
            for (row, tile) in tiles.iter().enumerate() {
                prepared.blit(tile, 0, origin + row as i32 * 32 + 34);
            }
            let prepared = upscale(&prepared.image, scale).unwrap();
            for phase in 0..32 {
                let mut original = Canvas {
                    scale: 1,
                    image: solid(64, 204, 0),
                };
                for (row, tile) in tiles.iter().enumerate() {
                    original.blit(tile, 0, origin + row as i32 * 32 + phase + 2);
                }
                let original = upscale(&original.image, scale).unwrap();
                for alpha in [0.0_f32, 0.25, 0.5, 0.75, 1.0] {
                    let mut actual = Canvas {
                        scale,
                        image: solid(64 * scale, 200 * scale, 0),
                    };
                    let mut expected = Canvas {
                        scale,
                        image: solid(64 * scale, 200 * scale, 0),
                    };
                    actual.blit(
                        &prepared,
                        0,
                        ((-34.0 + phase as f32 + alpha - 1.0) * scale as f32).round() as i32,
                    );
                    expected.blit(
                        &original,
                        0,
                        ((-2.0 + alpha - 1.0) * scale as f32).round() as i32,
                    );
                    assert_eq!(
                        actual.image, expected.image,
                        "scale {scale}, phase {phase}, origin {origin}, alpha {alpha}"
                    );
                }
            }
        }
    }
}

#[test]
fn prepared_viewport_cache_is_bounded_and_never_returns_a_different_content_key() {
    let mut compositor = TerrainHd::default();
    let first = b"mission:a/native:100/mod-order:a,b/hash:1/scale:4/hd:true".to_vec();
    compositor.retain_layer(first.clone(), solid(1280, 1072, 40));
    assert_eq!(at(compositor.cached_layer(&first).unwrap(), 0, 0), 40);
    assert!(compositor.prepared_bytes() <= 320 * 268 * 16 * 2 + 65536);
    for changed in [
        b"mission:a/native:101/mod-order:a,b/hash:1/scale:4/hd:true".as_slice(),
        b"mission:a/native:100/mod-order:b,a/hash:1/scale:4/hd:true".as_slice(),
        b"mission:a/native:100/mod-order:a,b/hash:2/scale:4/hd:true".as_slice(),
        b"mission:a/native:100/mod-order:a,b/hash:1/scale:3/hd:true".as_slice(),
        b"mission:a/native:100/mod-order:a,b/hash:1/scale:4/hd:false".as_slice(),
    ] {
        assert!(compositor.cached_layer(changed).is_none());
    }
    compositor.retain_layer(vec![0; 65537], solid(1, 1, 40));
    assert_eq!(compositor.prepared_bytes(), 0);
    compositor.retain_layer(first, solid(1280, 1073, 40));
    assert_eq!(compositor.prepared_bytes(), 0);
}

#[test]
fn wrong_canvas_and_transparent_hd_fall_back_without_partial_replacement() {
    let context = solid(64, 64, 30);
    let mut layer = context.clone();
    let mut compositor = TerrainHd::default();
    assert_eq!(
        compositor.overlay(
            &mut layer,
            &context,
            &solid(63, 64, 180),
            [0, 0],
            [32, 32],
            2,
            &palette()
        ),
        OverlayResult::InvalidCanvas
    );
    let mut hd = solid(64, 64, 180);
    hd.pixels[400] = TRANSPARENT;
    assert_eq!(
        compositor.overlay(&mut layer, &context, &hd, [0, 0], [32, 32], 2, &palette()),
        OverlayResult::NonOpaque
    );
    assert_eq!(layer, context);
    assert_eq!(compositor.cache_bytes(), 0);
}

#[test]
fn water_fire_and_flashing_masks_remain_indexed_and_static_terrain_does_not_blink() {
    let mut compositor = TerrainHd::default();
    for original in [40_u16, 242, 247, 250, 251, 252, 253, 254, 255] {
        let context = solid(128, 128, original);
        let layer = compositor
            .compose(
                &context,
                &[Replacement {
                    image: solid(128, 128, 243),
                    position: [0, 0],
                    logical_size: [32, 32],
                }],
                4,
                &palette(),
            )
            .image;
        let expected = match original {
            242 => 240..245,
            247 => 245..250,
            250..=255 => original..original + 1,
            _ => 0..240,
        };
        assert!(layer.pixels.iter().all(|color| expected.contains(color)));
        let mut canvas = Canvas::new(4);
        canvas.blit(&layer, 0, 0);
        let first = canvas.rgba(&palette(), false);
        let mut cycled = palette();
        cycled[original as usize] = [200, 0, 100];
        assert_ne!(first, canvas.rgba(&cycled, false));
        assert_eq!(at(&layer, 0, 0), original);
    }
    // A palette change invalidates the lazy transition lookup.
    let context = solid(128, 128, 40);
    let mut before = context.clone();
    compositor.overlay(
        &mut before,
        &context,
        &solid(128, 128, 180),
        [0, 0],
        [32, 32],
        4,
        &palette(),
    );
    let mut changed = palette();
    changed[40] = [10; 3];
    changed[180] = [220; 3];
    let mut after = context.clone();
    compositor.overlay(
        &mut after,
        &context,
        &solid(128, 128, 180),
        [0, 0],
        [32, 32],
        4,
        &changed,
    );
    assert_ne!(at(&before, 4, 64), at(&after, 4, 64));
    assert_eq!(compositor.cache_bytes(), 2 * 1024 * 1024);
}

#[test]
fn native_destroyed_tiles_wait_for_settling_and_keep_independent_art_ids() {
    let tile: TileDef = serde_json::from_value(json!({
        "art":{"asset":100,"logical_width":32,"logical_height":32},
        "health":10,"reward":700,
        "destroyed":{"asset":101,"logical_width":32,"logical_height":32}
    }))
    .unwrap();
    assert_eq!(selected_art(&tile, true, true, false).asset, Some(100));
    assert_eq!(selected_art(&tile, true, true, true).asset, Some(101));
    assert_eq!(selected_art(&tile, false, true, false).asset, Some(101));
    assert_eq!(selected_art(&tile, false, false, true).asset, Some(100));
    let source = Sprite {
        width: 64,
        height: 64,
        pixels: (0..64 * 64).map(|i| (i % 239) as u16).collect(),
    };
    let logical = logical_sprite(&source, 32, 32).unwrap();
    assert_eq!((logical.width, logical.height), (32, 32));
    assert_eq!(at(&logical, 15, 12), at(&source, 30, 24));
    let mut no_destroyed = tile.clone();
    no_destroyed.destroyed = None;
    assert_eq!(
        selected_art(&no_destroyed, true, true, true).asset,
        Some(100)
    );
}

#[test]
fn catalog_terrain_is_loaded_lazily_and_destroyed_art_never_reuses_the_intact_replacement() {
    use sha2::{Digest, Sha256};
    let directory = tempfile::tempdir().unwrap();
    let root = directory.path();
    let hd_root = root.join("hd");
    std::fs::create_dir(&hd_root).unwrap();
    let mut frames = Vec::new();
    let mut index = String::new();
    for (id, original, remastered) in [(100_u32, 40_u8, 180_u8), (101, 80, 210)] {
        let source: Vec<_> = [1_i32, 0, 0, 32, 32]
            .into_iter()
            .flat_map(i32::to_le_bytes)
            .chain([original; 32 * 32])
            .collect();
        let file = format!("tile-{id}.bin");
        std::fs::write(root.join(&file), &source).unwrap();
        index.push_str(&format!("{id:x} {} {file}\n", source.len()));
        let image_file = format!("tile-{id}.png");
        image::RgbaImage::from_pixel(
            128,
            128,
            image::Rgba([remastered, remastered, remastered, 255]),
        )
        .save(hd_root.join(&image_file))
        .unwrap();
        frames.push(
            json!({"frame":id-100,"file":image_file,"logical_width":32,"logical_height":32,
            "origin":[0,0],"source_sha256":format!("{:x}",Sha256::digest(&source))}),
        );
    }
    std::fs::write(root.join("INDEX"), index).unwrap();
    let manifest = json!({"format_version":1,"name":"Terrain fixture","sequences":[{
        "name":"Intact and destroyed","base_asset":100,"frame_count":2,"frames":frames}]});
    std::fs::write(
        hd_root.join("hd.json"),
        serde_json::to_vec(&manifest).unwrap(),
    )
    .unwrap();
    let catalog = Catalog::open(root).unwrap();
    let mut hd = HdAssets::load_lazy(&hd_root, &catalog, None);
    assert_eq!(hd.registered_count(), 2);
    assert_eq!(hd.validated_count(), 0);
    let tile: TileDef = serde_json::from_value(json!({
        "art":{"asset":100,"logical_width":32,"logical_height":32},
        "destroyed":{"asset":101,"logical_width":32,"logical_height":32}
    }))
    .unwrap();
    let mut compositor = TerrainHd::default();
    for (dead, settled, expected_original, expected_hd) in [
        (false, false, 40, 180),
        (true, false, 40, 180),
        (true, true, 80, 210),
    ] {
        let id = selected_art(&tile, true, dead, settled).asset.unwrap();
        let context = upscale(&catalog.sprite(id).unwrap(), 4).unwrap();
        let mut layer = context.clone();
        let replacement = hd.sprite(id, 4, &palette()).unwrap().unwrap();
        assert_eq!(
            compositor.overlay(
                &mut layer,
                &context,
                &replacement,
                [0, 0],
                [32, 32],
                4,
                &palette()
            ),
            OverlayResult::Applied
        );
        assert_eq!(at(&layer, 0, 64), expected_original);
        assert_eq!(at(&layer, 64, 64), expected_hd);
    }
    assert_eq!(hd.validated_count(), 2);
    assert!(hd.diagnostics.is_empty());
    // A partial pack supplying only intact art cannot paint intact HD over
    // destroyed terrain. The destroyed catalog sprite is the whole fallback.
    let mut partial = manifest;
    partial["sequences"][0]["frames"]
        .as_array_mut()
        .unwrap()
        .pop();
    std::fs::write(
        hd_root.join("hd.json"),
        serde_json::to_vec(&partial).unwrap(),
    )
    .unwrap();
    let mut hd = HdAssets::load_lazy(&hd_root, &catalog, None);
    let destroyed_id = selected_art(&tile, true, true, true).asset.unwrap();
    assert!(hd.sprite(destroyed_id, 4, &palette()).unwrap().is_none());
    assert!(
        upscale(&catalog.sprite(destroyed_id).unwrap(), 4)
            .unwrap()
            .pixels
            .iter()
            .all(|color| *color == 80)
    );
}

#[test]
fn rendering_between_steps_does_not_change_world_rng_damage_or_rewards() {
    let pack: ContentPack = serde_json::from_value(json!({
        "weapons":[{"id":"base:gun","name":"Gun","damage":1,"speed":8,"cooldown":2,"behavior":"straight","target":"all","legacy":0}],
        "items":[{"id":"base:forward_guns","name":"Guns","price":0,"legacy":0,"weapon":"base:gun"},
            {"id":"base:energy","name":"Energy","price":0,"legacy":16,"max_count":100}],
        "missions":[{"id":"base:sector_1_wave_1","name":"Terrain","duration":1000,"columns":1,"layout":[0],
            "tiles":[{"art":{"asset":100,"logical_width":32,"logical_height":32},"health":2,"reward":700,
                "destroyed":{"asset":101,"logical_width":32,"logical_height":32}}]}]
    })).unwrap();
    let mut registry = Registry::default();
    registry.apply(pack, "base").unwrap();
    registry.validate().unwrap();
    let mut pilot = Pilot::default();
    pilot.inventory.insert("base:energy".into(), 75);
    let mut world = World::new(&pilot.mission, &pilot, &registry).unwrap();
    let mut control = world.clone();
    let mut scripts = ScriptRuntime::new();
    let mut control_scripts = ScriptRuntime::new();
    let context = upscale(&solid(64, 32, 40), 4).unwrap();
    let mut compositor = TerrainHd::default();
    for tick in 0..30 {
        let input = Input {
            fire: true,
            ..Input::default()
        };
        world.step(input.clone(), &registry, &mut scripts).unwrap();
        control
            .step(input, &registry, &mut control_scripts)
            .unwrap();
        let before = serde_json::to_vec(&world).unwrap();
        for _ in 0..if tick % 2 == 0 { 1 } else { 4 } {
            let mut layer = context.clone();
            compositor.overlay(
                &mut layer,
                &context,
                &solid(128, 128, 180),
                [0, 0],
                [32, 32],
                4,
                &palette(),
            );
            let tile = &registry.missions[&pilot.mission].tiles[0];
            selected_art(tile, false, world.terrain_dead[0], world.terrain_settled[0]);
        }
        assert_eq!(serde_json::to_vec(&world).unwrap(), before);
        assert_eq!(
            serde_json::to_vec(&world).unwrap(),
            serde_json::to_vec(&control).unwrap()
        );
        assert_eq!(scripts.rng, control_scripts.rng);
    }
}

#[test]
#[ignore = "requires original local catalog; verifies every mission terrain source"]
fn original_all_missions_keep_opaque_32_pixel_terrain_and_destroyed_canvases() {
    use std::collections::BTreeSet;
    let project = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap();
    let catalog = Catalog::open(project.join("data")).unwrap();
    let registry = Registry::base(&catalog).unwrap();
    let mut ids = BTreeSet::new();
    let mut missions = 0;
    for mission in registry
        .missions
        .values()
        .filter(|mission| mission.legacy_map.is_some())
    {
        missions += 1;
        for tile in &mission.tiles {
            for art in std::iter::once(&tile.art).chain(tile.destroyed.as_ref()) {
                let id = art.asset.unwrap();
                assert_eq!(
                    (art.logical_width, art.logical_height),
                    (32, 32),
                    "{id:05x}"
                );
                ids.insert(id);
            }
        }
    }
    for id in &ids {
        let source = catalog.sprite(*id).unwrap();
        assert_eq!((source.width, source.height), (32, 32), "{id:05x}");
        assert!(
            source.pixels.iter().all(|pixel| *pixel < TRANSPARENT),
            "opaque source {id:05x}"
        );
    }
    assert_eq!(missions, 27);
    let output = project.join(".reference/terrain-hd");
    std::fs::create_dir_all(&output).unwrap();
    std::fs::write(output.join("original-contract.json"), serde_json::to_vec_pretty(&json!({
        "native_missions":missions,"unique_referenced_tile_definitions":ids.len(),
        "all_opaque":true,"logical_canvas":[32,32],
        "note":"Includes all referenced intact artwork and declared destroyed partners in original mission definitions."
    })).unwrap()).unwrap();
    println!(
        "{missions} native missions; {} distinct declared intact/destroyed terrain IDs checked",
        ids.len()
    );
}

#[test]
#[ignore = "requires original catalog and local shoreline draft; writes unregistered compositor proof"]
fn original_shoreline_draft_previews_context_edges_without_registering_canonical_coverage() {
    let project = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap();
    let catalog = Catalog::open(project.join("data")).unwrap();
    let colors = catalog.palette().unwrap();
    let draft_root = project.join("data/hd/terrain");
    let metadata: serde_json::Value = serde_json::from_slice(
        &std::fs::read(draft_root.join("source/map1g1-start-shore-3x3-source.json")).unwrap(),
    )
    .unwrap();
    let atlas = image::open(draft_root.join("generated/map1g1-start-shore-3x3-hd-v1.png"))
        .unwrap()
        .into_rgba8();
    let mut source = Canvas {
        scale: 1,
        image: solid(96, 96, 0),
    };
    for tile in metadata["tiles"].as_array().unwrap() {
        let id = u32::from_str_radix(tile["asset"].as_str().unwrap(), 16).unwrap();
        let x = tile["context_column"].as_i64().unwrap() as i32 * 32;
        let y = tile["context_row"].as_i64().unwrap() as i32 * 32;
        source.blit(&catalog.sprite(id).unwrap(), x, y);
    }
    let context = upscale(&source.image, 4).unwrap();
    let mut raw = context.clone();
    let mut compositor = TerrainHd::default();
    let mut replacements = Vec::new();
    let output = project.join(".reference/terrain-hd");
    std::fs::create_dir_all(&output).unwrap();
    let temporary = tempfile::tempdir().unwrap();
    for row in 0..3_u32 {
        for col in 0..3_u32 {
            let left = col * atlas.width() / 3;
            let top = row * atlas.height() / 3;
            let right = (col + 1) * atlas.width() / 3;
            let bottom = (row + 1) * atlas.height() / 3;
            let crop =
                image::imageops::crop_imm(&atlas, left, top, right - left, bottom - top).to_image();
            let resized =
                image::imageops::resize(&crop, 128, 128, image::imageops::FilterType::Lanczos3);
            let file = temporary.path().join("crop.png");
            resized.save(&file).unwrap();
            let replacement = Sprite::png(&file, &colors).unwrap();
            for y in 0..128 {
                let destination = (row as usize * 128 + y) * raw.width + col as usize * 128;
                raw.pixels[destination..destination + 128]
                    .copy_from_slice(&replacement.pixels[y * 128..(y + 1) * 128]);
            }
            replacements.push(Replacement {
                image: replacement,
                position: [col as i32 * 32, row as i32 * 32],
                logical_size: [32, 32],
            });
        }
    }
    let composed = compositor.compose(&context, &replacements, 4, &colors);
    assert!(
        composed
            .results
            .iter()
            .all(|result| *result == OverlayResult::Applied)
    );
    let mut proof = Canvas {
        scale: 1,
        image: solid(3 * 384, 384, 0),
    };
    proof.blit(&context, 0, 0);
    proof.blit(&raw, 384, 0);
    proof.blit(&composed.image, 768, 0);
    image::save_buffer(
        output.join("shoreline-draft-context-proof.png"),
        &proof.rgba(&colors, false),
        proof.image.width as u32,
        proof.image.height as u32,
        image::ColorType::Rgba8,
    )
    .unwrap();
    std::fs::write(output.join("shoreline-draft-context-proof.json"), serde_json::to_vec_pretty(&json!({
        "panels":["Joined original Scale4x","Placement-specific generated draft","Indexed contextual HD transition"],
        "registration":"None; repeated IDs in this placement-specific atlas are not canonical replacements.",
        "edge_contract":"HD/HD shared detail where source geometry agrees; original context at HD/original edges",
        "cache_bytes":compositor.cache_bytes()
    })).unwrap()).unwrap();
}

#[test]
#[ignore = "writes local terrain compositor timing; run with --release"]
fn visible_full_hd_terrain_compositor_timing() {
    let context = solid(320 * 4, 204 * 4, 40);
    let replacements: Vec<_> = (0..8)
        .flat_map(|row| {
            (0..9).map(move |column| {
                let mut image = solid(128, 128, 180);
                for (index, pixel) in image.pixels.iter_mut().enumerate() {
                    *pixel = 170 + ((index * 17 + row * 7 + column * 11) % 40) as u16;
                }
                Replacement {
                    image,
                    position: [16 + column as i32 * 32, row as i32 * 32 - 30],
                    logical_size: [32, 32],
                }
            })
        })
        .collect();
    let mut compositor = TerrainHd::default();
    let started = std::time::Instant::now();
    let first = compositor.compose(&context, &replacements, 4, &palette());
    let cold_ms = started.elapsed().as_secs_f64() * 1000.0;
    assert!(
        first
            .results
            .iter()
            .all(|result| *result == OverlayResult::Applied)
    );
    let mut times = Vec::new();
    for _ in 0..50 {
        let started = std::time::Instant::now();
        let frame = compositor.compose(&context, &replacements, 4, &palette());
        std::hint::black_box(&frame.image);
        times.push(started.elapsed().as_secs_f64() * 1000.0);
    }
    times.sort_by(f64::total_cmp);
    let report = json!({"presentation_scale":4,"indexed_canvas":[1280,816],
        "visible_hd_tiles":replacements.len(),"frames":times.len(),"cold_ms":cold_ms,
        "p50_ms":times[25],"p95_ms":times[47],"max_ms":times[49],
        "retained_compositor_cache_bytes":compositor.cache_bytes(),
        "note":"Composer only; excludes source asset loading, SDL and the rest of the game scene."});
    println!("{}", serde_json::to_string_pretty(&report).unwrap());
    let project = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap();
    let output = project.join(".reference/terrain-hd");
    std::fs::create_dir_all(&output).unwrap();
    std::fs::write(
        output.join("compositor-timing.json"),
        serde_json::to_vec_pretty(&report).unwrap(),
    )
    .unwrap();
    assert_eq!(compositor.cache_bytes(), 2 * 1024 * 1024);
}

#[test]
#[ignore = "requires original catalog and a canonical terrain candidate; writes actual runtime context/pair proofs"]
fn canonical_terrain_candidate_preserves_all_declared_contexts_and_neighbor_pairs() {
    use std::{collections::BTreeMap, path::Path};
    let project = Path::new(env!("CARGO_MANIFEST_DIR")).parent().unwrap();
    let catalog = Catalog::open(project.join("data")).unwrap();
    let colors = catalog.palette().unwrap();
    let job_id =
        std::env::var("RAPTOR_HD_TERRAIN_JOB").unwrap_or_else(|_| "terrain-10360-1036f".into());
    assert!(
        job_id
            .chars()
            .all(|c| c.is_ascii_alphanumeric() || c == '-')
    );
    let hd_root = project.join("data/hd");
    let job_root = hd_root.join("jobs").join(&job_id);
    let job: serde_json::Value =
        serde_json::from_slice(&std::fs::read(job_root.join("job.json")).unwrap()).unwrap();
    let candidate: serde_json::Value =
        serde_json::from_slice(&std::fs::read(job_root.join("candidate.json")).unwrap()).unwrap();
    let temporary = tempfile::tempdir().unwrap();
    // Keep the coordinator-owned global manifest untouched. This isolated pack
    // uses exactly the candidate files and source metadata through HdAssets.
    for target in candidate["targets"].as_array().unwrap() {
        let file = Path::new(target["file"].as_str().unwrap());
        let destination = temporary.path().join(file);
        std::fs::create_dir_all(destination.parent().unwrap()).unwrap();
        if !destination.exists() {
            std::fs::copy(hd_root.join(file), destination).unwrap();
        }
    }
    std::fs::write(
        temporary.path().join("hd.json"),
        serde_json::to_vec(&json!({
            "format_version":1,"name":job_id,"sequences":candidate["sequences"]
        }))
        .unwrap(),
    )
    .unwrap();
    let mut hd = HdAssets::load_lazy(temporary.path(), &catalog, None);
    assert_eq!(
        hd.registered_count(),
        candidate["targets"].as_array().unwrap().len()
    );
    let mut compositor = TerrainHd::default();
    let output = project.join(".reference/terrain-hd").join(&job_id);
    std::fs::create_dir_all(&output).unwrap();
    let ids = |values: &serde_json::Value| -> Vec<u32> {
        values
            .as_array()
            .unwrap()
            .iter()
            .map(|id| {
                id.as_str()
                    .map_or(0, |id| u32::from_str_radix(id, 16).unwrap())
            })
            .collect()
    };
    let compose = |ids: &[u32],
                   columns: usize,
                   scale: usize,
                   hd: &mut HdAssets,
                   compositor: &mut TerrainHd| {
        let mut original = Canvas {
            scale: 1,
            image: solid(columns * 32, ids.len().div_ceil(columns) * 32, 0),
        };
        let mut replacements = Vec::new();
        for (index, id) in ids.iter().enumerate() {
            if *id == 0 {
                continue;
            } // Outside the native map's playable columns.
            let position = [(index % columns * 32) as i32, (index / columns * 32) as i32];
            original.blit(&catalog.sprite(*id).unwrap(), position[0], position[1]);
            if let Some(image) = hd.sprite(*id, scale, &colors).unwrap() {
                replacements.push(Replacement {
                    image,
                    position,
                    logical_size: [32, 32],
                });
            }
        }
        let original = upscale(&original.image, scale).unwrap();
        let result = compositor.compose(&original, &replacements, scale, &colors);
        assert!(
            result
                .results
                .iter()
                .all(|result| *result == OverlayResult::Applied)
        );
        (original, result.image, replacements.len())
    };
    let save = |image: &Sprite, path: &Path| {
        let canvas = Canvas {
            scale: 1,
            image: image.clone(),
        };
        image::save_buffer(
            path,
            &canvas.rgba(&colors, false),
            image.width as u32,
            image.height as u32,
            image::ColorType::Rgba8,
        )
        .unwrap();
    };
    let mut contexts = Vec::new();
    let mut pairs = Vec::new();
    let mut pair_classes = BTreeMap::<&str, usize>::new();
    let mut native_context_targets = Vec::new();
    let mut gallery_only_unused_targets = Vec::new();
    for target in job["targets"].as_array().unwrap() {
        let target_name = target["asset"].as_str().unwrap();
        let id = u32::from_str_radix(target_name, 16).unwrap();
        // Complete catalog coverage also includes unused pictures with no
        // native placement. Validate their genuine source-bound art without
        // inventing neighbors or presenting a gallery as a mission context.
        let mut detailed = None;
        for scale in 1..=4 {
            let image = hd
                .sprite(id, scale, &colors)
                .unwrap()
                .expect("candidate artwork rejected");
            assert_eq!((image.width, image.height), (32 * scale, 32 * scale));
            assert!(image.pixels.iter().all(|pixel| *pixel < TRANSPARENT));
            if scale == 4 {
                detailed = Some(image);
            }
        }
        let unused = target["terrain_context"]["roles"]
            .as_array()
            .unwrap()
            .is_empty();
        if unused {
            assert!(
                target["terrain_context"]["samples"]
                    .as_array()
                    .unwrap()
                    .is_empty()
            );
            assert!(
                target["terrain_context"]["neighbors"]
                    .as_object()
                    .unwrap()
                    .values()
                    .all(|neighbors| neighbors.as_array().unwrap().is_empty())
            );
            let mut gallery = Canvas {
                scale: 1,
                image: solid(256, 128, 0),
            };
            gallery.blit(&upscale(&catalog.sprite(id).unwrap(), 4).unwrap(), 0, 0);
            gallery.blit(&detailed.unwrap(), 128, 0);
            let file = format!("{target_name}-runtime-unused-gallery.png");
            save(&gallery.image, &output.join(&file));
            gallery_only_unused_targets
                .push(json!({"asset":target_name,"file":file,"native_occurrence":false}));
        } else {
            native_context_targets.push(target_name.to_owned());
        }
        for (sample_index, sample) in target["terrain_context"]["samples"]
            .as_array()
            .unwrap()
            .iter()
            .enumerate()
        {
            let source_ids = ids(&sample["target_3x3"]);
            assert_eq!(source_ids.len(), 9);
            let (original, composed, placements) =
                compose(&source_ids, 3, 4, &mut hd, &mut compositor);
            let mut proof = Canvas {
                scale: 1,
                image: solid(768, 384, 0),
            };
            proof.blit(&original, 0, 0);
            proof.blit(&composed, 384, 0);
            let file = format!("{target_name}-{sample_index}-runtime-context.png");
            save(&proof.image, &output.join(&file));
            contexts.push(
                json!({"asset":target_name,"sample":sample,"file":file,"hd_placements":placements}),
            );
        }
        // Every declared neighbor is exercised, including neighbors absent from
        // the three representative context samples. The per-ID sheet displays
        // original/composed pairs in the JSON order at presentation scale 2.
        let mut proofs = Vec::new();
        let mut local_pairs = Vec::new();
        for side in ["north", "south", "west", "east"] {
            for neighbor in target["terrain_context"]["neighbors"][side]
                .as_array()
                .unwrap()
            {
                let neighbor_name = neighbor.as_str().unwrap();
                let neighbor_id = u32::from_str_radix(neighbor_name, 16).unwrap();
                let ordered = if side == "north" || side == "west" {
                    [neighbor_id, id]
                } else {
                    [id, neighbor_id]
                };
                let columns = if side == "north" || side == "south" {
                    1
                } else {
                    2
                };
                let (original, composed, placements) =
                    compose(&ordered, columns, 2, &mut hd, &mut compositor);
                let class = if placements == 2 {
                    "HD/HD"
                } else {
                    "HD/original"
                };
                *pair_classes.entry(class).or_default() += 1;
                let mut proof = Canvas {
                    scale: 1,
                    image: solid(256, 128, 0),
                };
                proof.blit(&original, 0, 0);
                proof.blit(&composed, 128, 0);
                proofs.push(proof.image);
                local_pairs.push(json!({"target":target_name,"side":side,"neighbor":neighbor_name,"class":class}));
            }
        }
        if !proofs.is_empty() {
            let mut sheet = Canvas {
                scale: 1,
                image: solid(1024, proofs.len().div_ceil(4) * 128, 0),
            };
            for (index, proof) in proofs.iter().enumerate() {
                sheet.blit(proof, (index % 4 * 256) as i32, (index / 4 * 128) as i32);
            }
            let file = format!("{target_name}-runtime-cardinal-pairs.png");
            save(&sheet.image, &output.join(&file));
            for (index, mut pair) in local_pairs.into_iter().enumerate() {
                pair["file"] = json!(file);
                pair["sheet_cell"] = json!([index % 4, index / 4]);
                pairs.push(pair);
            }
        }
    }
    assert!(hd.diagnostics.is_empty(), "{:?}", hd.diagnostics);
    assert_eq!(hd.validated_count(), hd.registered_count());
    let partners: Vec<_> = job["targets"]
        .as_array()
        .unwrap()
        .iter()
        .filter(|target| {
            !target["terrain_context"]["state_partners"]
                .as_array()
                .unwrap()
                .is_empty()
        })
        .map(|target| target["asset"].clone())
        .collect();
    let report = json!({"job_id":job_id,"contexts":contexts,"cardinal_pairs":pairs,"pair_classes":pair_classes,
        "registered":hd.registered_count(),"decoded":hd.validated_count(),"diagnostics":hd.diagnostics,
        "native_context_targets":native_context_targets,"gallery_only_unused_targets":gallery_only_unused_targets,
        "targets_with_state_partners":partners,"state_partner_note":"Empty means this candidate has no declared damaged/destroyed partner; separate synthetic/source-bound tests verify state selection.",
        "panels":["Joined original ScaleNx","Exact HdAssets + TerrainHd composition"],
        "registration":"Isolated test pack only; global manifest and coverage untouched.","review":"Files require visual inspection; test success verifies reachability/canvas/indexing, not artistic acceptance."});
    std::fs::write(
        output.join("runtime-proof.json"),
        serde_json::to_vec_pretty(&report).unwrap(),
    )
    .unwrap();
    println!(
        "{} contexts, {} directional neighbor pairs, {} exact source-bound tiles; {}",
        report["contexts"].as_array().unwrap().len(),
        report["cardinal_pairs"].as_array().unwrap().len(),
        hd.validated_count(),
        output.display()
    );
}
