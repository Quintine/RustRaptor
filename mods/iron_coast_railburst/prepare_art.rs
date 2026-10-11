const SHOT_W: u32 = 4;
const SHOT_H: u32 = 20;
// Fit untouched generated masters to shared logical canvases and four-times HD.
// Compile with this project's pinned image crate; see README for reproduction.
use image::{Rgba, RgbaImage, imageops};
use std::{env, fs, path::Path};
fn fit(source: &RgbaImage, w: u32, h: u32, scale: u32) -> RgbaImage {
    let mut bounds = (source.width(), source.height(), 0, 0);
    for (x, y, p) in source.enumerate_pixels() {
        if p[3] >= 128 {
            bounds.0 = bounds.0.min(x);
            bounds.1 = bounds.1.min(y);
            bounds.2 = bounds.2.max(x + 1);
            bounds.3 = bounds.3.max(y + 1);
        }
    }
    assert!(
        bounds.2 > bounds.0 && bounds.3 > bounds.1,
        "no meaningful source alpha"
    );
    let crop = imageops::crop_imm(
        source,
        bounds.0,
        bounds.1,
        bounds.2 - bounds.0,
        bounds.3 - bounds.1,
    )
    .to_image();
    // Exactly one logical pixel of clear margin, shared across SD and HD.
    let factor = ((w - 2) as f64 / crop.width() as f64).min((h - 2) as f64 / crop.height() as f64);
    let nw = (crop.width() as f64 * factor).round().max(1.) as u32;
    let nh = (crop.height() as f64 * factor).round().max(1.) as u32;
    let filter = if scale == 1 {
        imageops::FilterType::Triangle
    } else {
        imageops::FilterType::Lanczos3
    };
    let mut scaled = imageops::resize(&crop, nw * scale, nh * scale, filter);
    for p in scaled.pixels_mut() {
        if p[3] < 128 {
            *p = Rgba([0, 0, 0, 0]);
        } else {
            p[3] = 255;
        }
    }
    let mut out = RgbaImage::new(w * scale, h * scale);
    imageops::overlay(
        &mut out,
        &scaled,
        ((w * scale - nw * scale) / 2) as i64,
        ((h * scale - nh * scale) / 2) as i64,
    );
    out
}
fn main() {
    let args: Vec<_> = env::args().collect();
    assert_eq!(args.len(), 2, "usage: prepare_art PACKAGE_DIRECTORY");
    let root = Path::new(&args[1]);
    for (kind, w, h) in [("equipment", 16, 16), ("projectile", SHOT_W, SHOT_H)] {
        let source = image::open(root.join(format!("art/{kind}-generated-source-v1.png")))
            .unwrap()
            .into_rgba8();
        for (mode, scale) in [("sd", 1), ("hd", 4)] {
            let image = fit(&source, w, h, scale);
            let path = root.join(format!("art/{kind}-{mode}.png"));
            image.save(&path).unwrap();
            println!("{} {}x{}", path.display(), image.width(), image.height());
        }
    }
    assert!(
        fs::metadata(root.join("art/equipment-hd.png"))
            .unwrap()
            .len()
            > 0
    );
}
