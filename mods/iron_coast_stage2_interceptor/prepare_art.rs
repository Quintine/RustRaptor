//! Derive aligned SD/HD canvases from unchanged built-in generated PNG masters.
//! The PNG master is never modified. Only wholly transparent margins are trimmed;
//! every occupied input alpha pixel remains inside the recorded source crop.
use image::{
    imageops::{self, FilterType},
    Rgba, RgbaImage,
};
use serde_json::json;
use sha2::{Digest, Sha256};
use std::{fs, path::Path};
fn sha(p: &Path) -> String {
    format!("{:x}", Sha256::digest(fs::read(p).unwrap()))
}
fn bounds(im: &RgbaImage, threshold: u8) -> (u32, u32, u32, u32) {
    let (mut x0, mut y0, mut x1, mut y1) = (im.width(), im.height(), 0, 0);
    for (x, y, p) in im.enumerate_pixels() {
        if p[3] >= threshold {
            x0 = x0.min(x);
            y0 = y0.min(y);
            x1 = x1.max(x + 1);
            y1 = y1.max(y + 1);
        }
    }
    assert!(x1 > x0 && y1 > y0, "empty sprite");
    (x0, y0, x1, y1)
}
fn filtered(im: &RgbaImage, w: u32, h: u32, filter: FilterType) -> RgbaImage {
    // Resample premultiplied alpha to keep opaque dark interior recesses while
    // preventing invisible RGB from becoming a dark fringe at the sprite edge.
    let mut premul = im.clone();
    for p in premul.pixels_mut() {
        for c in 0..3 {
            p[c] = ((p[c] as u32 * p[3] as u32 + 127) / 255) as u8;
        }
    }
    let mut out = imageops::resize(&premul, w, h, filter);
    for p in out.pixels_mut() {
        if p[3] == 0 {
            *p = Rgba([0, 0, 0, 0]);
        } else {
            for c in 0..3 {
                p[c] = ((p[c] as u32 * 255 + p[3] as u32 / 2) / p[3] as u32).min(255) as u8;
            }
        }
    }
    out
}
fn main() {
    let arg = std::env::args().nth(1).expect("pass the mod directory");
    let root = Path::new(&arg);
    let contract: serde_json::Value =
        serde_json::from_slice(&fs::read(root.join("contract.json")).unwrap()).unwrap();
    let mut reports = Vec::new();
    for kind in ["unit", "projectile"] {
        let (lw, lh) = if kind == "unit" {
            (
                contract["logical_size"][0].as_u64().unwrap() as u32,
                contract["logical_size"][1].as_u64().unwrap() as u32,
            )
        } else {
            (8, 8)
        };
        let source_path = root.join(format!("art/{kind}-generated-v1.png"));
        let original_sha = sha(&source_path);
        let raw = image::open(&source_path).unwrap().into_rgba8();
        assert!(
            raw.pixels().any(|p| p[3] == 0),
            "generated source needs genuine transparent background"
        );
        assert!(
            raw.pixels().any(|p| p[3] == 255),
            "generated source needs occupied opaque artwork"
        );
        let (x0, y0, x1, y1) = bounds(&raw, 1);
        let occupied = imageops::crop_imm(&raw, x0, y0, x1 - x0, y1 - y0).to_image();
        let scale = 8;
        let pad = if kind == "unit" { 2 } else { 1 };
        let (limit_w, limit_h) = ((lw - pad * 2) * scale, (lh - pad * 2) * scale);
        let (ow, oh) = occupied.dimensions();
        let (w, h) = if limit_w as u64 * oh as u64 <= limit_h as u64 * ow as u64 {
            (
                limit_w,
                ((oh as u64 * limit_w as u64 + ow as u64 / 2) / ow as u64) as u32,
            )
        } else {
            (
                ((ow as u64 * limit_h as u64 + oh as u64 / 2) / oh as u64) as u32,
                limit_h,
            )
        };
        let fitted = filtered(&occupied, w, h, FilterType::Lanczos3);
        let mut hd = RgbaImage::new(lw * scale, lh * scale);
        let offset = ((hd.width() - w) / 2, (hd.height() - h) / 2);
        imageops::overlay(&mut hd, &fitted, offset.0 as i64, offset.1 as i64);
        // Match the renderer's indexed HD-to-logical sample positions exactly.
        // This retains the bright projectile core and aligns both modes at 1x.
        let mut sd = RgbaImage::new(lw, lh);
        for y in 0..lh {
            for x in 0..lw {
                sd.put_pixel(x, y, *hd.get_pixel(x * scale, y * scale));
            }
        }
        let sdb = bounds(&sd, 128);
        let hdb = bounds(&hd, 128);
        assert!(
            sdb.0 >= 1 && sdb.1 >= 1 && sdb.2 < lw && sdb.3 < lh,
            "SD clipped {kind}"
        );
        assert!(
            hdb.0 >= 1 && hdb.1 >= 1 && hdb.2 < hd.width() && hdb.3 < hd.height(),
            "HD clipped {kind}"
        );
        let sdpath = root.join(format!("art/{kind}-sd.png"));
        let hdpath = root.join(format!("art/{kind}-hd.png"));
        sd.save(&sdpath).unwrap();
        hd.save(&hdpath).unwrap();
        assert_eq!(sha(&source_path), original_sha);
        reports.push(json!({"kind":kind,"raw_sha256":original_sha,"raw_dimensions":[raw.width(),raw.height()],"crop_all_alpha_ge_1":[x0,y0,x1,y1],"logical_canvas":[lw,lh],"hd_canvas":[hd.width(),hd.height()],"occupied_fit":[w,h],"offset_hd":[offset.0,offset.1],"sd_alpha128_bounds":[sdb.0,sdb.1,sdb.2,sdb.3],"hd_alpha128_bounds":[hdb.0,hdb.1,hdb.2,hdb.3],"logical_origin":[0,0],"frames":1,"sd_sha256":sha(&sdpath),"hd_sha256":sha(&hdpath)}));
    }
    let report = json!({"method":"prepare_art.rs: unchanged genuine alpha master, crop only transparent margin, aspect-preserving centered fit, premultiplied-alpha Lanczos3 HD8x and renderer-aligned floor-nearest SD; original images are style references only","source_unchanged":true,"all_occupied_input_alpha_retained_in_crop":true,"frames":reports});
    fs::write(
        root.join("art-qa.json"),
        serde_json::to_vec_pretty(&report).unwrap(),
    )
    .unwrap();
    println!("Prepared aligned SD/HD art: {}", root.display());
}
