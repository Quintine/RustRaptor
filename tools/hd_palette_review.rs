//! Diagnostic gallery linked against the already-built game library.
//! The Python wrapper prepares an isolated pack; global hd.json is never edited.
use raptor_replica::{assets::{Catalog, Sprite, TRANSPARENT}, hd::{HdAssets, Manifest}};
use serde_json::{json, Value};
use std::{env, fs, path::Path};

fn ppm(path: &Path, sprite: &Sprite, palette: &[[u8; 3]; 256]) {
    let mut bytes = format!("P6\n{} {}\n255\n", sprite.width, sprite.height).into_bytes();
    for index in &sprite.pixels {
        bytes.extend_from_slice(if *index == TRANSPARENT { &[20, 28, 38] } else { &palette[*index as usize] });
    }
    fs::write(path, bytes).unwrap();
}

fn mask(sprite: &Sprite) -> Value {
    let points: Vec<_> = sprite.pixels.iter().enumerate()
        .filter(|(_, pixel)| **pixel != TRANSPARENT)
        .map(|(index, _)| (index % sprite.width, index / sprite.width)).collect();
    if points.is_empty() { return json!({"visible_pixels": 0}); }
    let bounds = [points.iter().map(|p| p.0).min().unwrap(), points.iter().map(|p| p.1).min().unwrap(),
        points.iter().map(|p| p.0).max().unwrap() + 1, points.iter().map(|p| p.1).max().unwrap() + 1];
    let centroid = [points.iter().map(|p| p.0 as f64).sum::<f64>() / points.len() as f64,
        points.iter().map(|p| p.1 as f64).sum::<f64>() / points.len() as f64];
    let animated_palette_counts: Vec<_> = (240..=255).map(|index| sprite.pixels.iter().filter(|pixel| **pixel == index).count()).collect();
    json!({"visible_pixels": points.len(), "bounds": bounds, "centroid": centroid,
        "palette_indices_240_to_255_counts": animated_palette_counts})
}

fn main() {
    let args: Vec<_> = env::args().collect();
    assert_eq!(args.len(), 4, "expected DATA PACK OUTPUT");
    let output = Path::new(&args[3]); fs::create_dir_all(output).unwrap();
    let catalog = Catalog::open(&args[1]).unwrap(); let base_palette = catalog.palette().unwrap();
    let manifest: Manifest = serde_json::from_slice(&fs::read(Path::new(&args[2]).join("hd.json")).unwrap()).unwrap();
    let mut hd = HdAssets::load(Path::new(&args[2]), &catalog);
    assert!(hd.diagnostics.is_empty(), "{:?}", hd.diagnostics);
    let mut frames = Vec::new(); let mut indexed = Vec::new();
    for sequence in manifest.sequences { for frame in sequence.frames {
        let id = sequence.base_asset + frame.frame;
        let palette_name = match id { 0x1002b => "POGPAL_DAT", 0x1002d => "CYGPAL_DAT", 0x1002f => "TAIPAL_DAT", _ => "PALETTE_DAT" };
        let palette = if palette_name == "PALETTE_DAT" { base_palette } else {
            raptor_replica::assets::decode_palette(&catalog.named(palette_name).unwrap()).unwrap()
        };
        let original = catalog.sprite(id).unwrap();
        ppm(&output.join(format!("{id:05x}-original.ppm")), &original, &palette);
        let source_indices: Vec<u16> = original.pixels.iter().copied().filter(|&p|p<TRANSPARENT)
            .collect::<std::collections::BTreeSet<_>>().into_iter().collect();
        let mut constraint_scales = Vec::new();
        let mut masks = Vec::new(); let mut logical = None; let mut indexed_scales = Vec::new();
        for scale in 1..=4 {
            let sprite = if palette_name == "PALETTE_DAT" {
                hd.sprite(id, scale, &palette)
            } else {
                #[cfg(static_card_api)]
                { hd.sprite_static_palette(id, scale, &palette) }
                #[cfg(not(static_card_api))]
                { panic!("Static-card review requires the source-specific palette API in the selected library") }
            }.unwrap().expect("candidate rejected");
            assert_eq!((sprite.width, sprite.height), (frame.logical_width as usize * scale, frame.logical_height as usize * scale));
            assert!(sprite.pixels.iter().any(|p| *p != TRANSPARENT));
            ppm(&output.join(format!("{id:05x}-hd-{scale}.ppm")), &sprite, &palette);
            if frame.palette_constraint.is_some() {
                constraint_scales.push(json!({"scale":scale,
                    "visible_pixels":sprite.pixels.iter().filter(|&&p|p<TRANSPARENT).count(),
                    "outside_original_palette":sprite.pixels.iter().filter(|&&p|p<TRANSPARENT && source_indices.binary_search(&p).is_err()).count()}));
            }
            indexed_scales.push(json!({"scale":scale,"width":sprite.width,"height":sprite.height,"indices":sprite.pixels})); masks.push(json!({"scale": scale, "mask": mask(&sprite)}));
            if scale == 1 { logical = Some(sprite); }
        }
        indexed.push(json!({"asset":format!("{id:05x}"),"source":{"width":original.width,"height":original.height,"indices":original.pixels},"scales":indexed_scales})); let logical = logical.unwrap();
        let intersection = original.pixels.iter().zip(&logical.pixels).filter(|(a,b)| **a != TRANSPARENT && **b != TRANSPARENT).count();
        let union = original.pixels.iter().zip(&logical.pixels).filter(|(a,b)| **a != TRANSPARENT || **b != TRANSPARENT).count();
        let mut report = json!({"asset": format!("{id:05x}"), "source_sha256": frame.source_sha256, "source_palette": palette_name,
            "logical_canvas": [frame.logical_width, frame.logical_height], "source_mask": mask(&original),
            "logical_alpha_mask_iou": intersection as f64 / union.max(1) as f64, "hd_masks": masks});
        if let Some(mode) = frame.palette_constraint {
            report["palette_constraint"] = json!({"policy":mode,"applied":palette_name=="PALETTE_DAT",
                "source_indices":source_indices,
                "source_colors":source_indices.iter().map(|&i|json!({"index":i,"RGB":palette[i as usize]})).collect::<Vec<_>>(),
                "scales":constraint_scales});
        }
        frames.push(report);
    }}
    let report = json!({"method": "actual Rust HdAssets::load and sprite at scales 1..4; Catalog palette; no artwork edits",
        "validated_frames": hd.coverage(), "diagnostics": hd.diagnostics, "frames": frames,
        "limitation": "Gallery validation does not prove live scene reachability, terrain seam correctness or artistic fidelity. Opaque sprites have trivial alpha-mask overlap; compare visible source geometry manually."});
    fs::write(output.join("runtime-qa.json"), serde_json::to_vec_pretty(&report).unwrap()).unwrap();
    fs::write(output.join("actual-indexed-source-and-scales.json"),serde_json::to_vec_pretty(&indexed).unwrap()).unwrap(); println!("validated {} candidate frames at all four scales", frames.len());
}
