//! Fit the transparent equipment master to the 16px SD and 64px HD canvases.
use image::{Rgba, RgbaImage, imageops};
use std::{env, fs, path::Path};
fn canvas(source: &RgbaImage, width: u32, height: u32, hd: bool) -> RgbaImage {
    // Only the solid silhouette defines its fitting box; faint outer glows stay bounded.
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
        "source has no opaque silhouette"
    );
    let cropped = imageops::crop_imm(
        source,
        bounds.0,
        bounds.1,
        bounds.2 - bounds.0,
        bounds.3 - bounds.1,
    )
    .to_image();
    let margin = if hd { 4 } else { 1 };
    let available = (
        width.saturating_sub(margin * 2).max(1),
        height.saturating_sub(margin * 2).max(1),
    );
    let factor = (available.0 as f64 / cropped.width() as f64)
        .min(available.1 as f64 / cropped.height() as f64);
    let size = (
        (cropped.width() as f64 * factor).round().max(1.) as u32,
        (cropped.height() as f64 * factor).round().max(1.) as u32,
    );
    let filter = if hd {
        imageops::FilterType::Lanczos3
    } else {
        imageops::FilterType::Nearest
    };
    let mut scaled = imageops::resize(&cropped, size.0, size.1, filter);
    for p in scaled.pixels_mut() {
        if p[3] < (if hd { 64 } else { 128 }) {
            *p = Rgba([0, 0, 0, 0]);
        } else {
            p[3] = 255;
        }
    }
    let mut out = RgbaImage::new(width, height);
    imageops::overlay(
        &mut out,
        &scaled,
        ((width - size.0) / 2) as i64,
        ((height - size.1) / 2) as i64,
    );
    out
}
fn main() {
    let args: Vec<_> = env::args_os().collect();
    assert_eq!(
        args.len(),
        3,
        "usage: prepare_art EQUIPMENT_SOURCE PACKAGE_DIRECTORY"
    );
    let output = Path::new(&args[2]).join("art");
    fs::create_dir_all(&output).unwrap();
    let source = image::open(&args[1]).unwrap().into_rgba8();
    fs::copy(&args[1], output.join("equipment-generated-source.png")).unwrap();
    for (mode, scale) in [("sd", 1), ("hd", 4)] {
        let sprite = canvas(&source, 16 * scale, 16 * scale, scale == 4);
        let path = output.join(format!("equipment-{mode}.png"));
        sprite.save(&path).unwrap();
        println!("{}x{} {}", sprite.width(), sprite.height(), path.display());
    }
}
