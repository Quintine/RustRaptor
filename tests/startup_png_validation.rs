//! Rejection and renderer output contract for validation's shared PNG decoder.
use raptor_replica::{
    assets::{Catalog, Sprite, TRANSPARENT},
    content::Registry,
    modding::{self, ActiveMods},
};
use serde_json::json;
use std::{fs, path::Path};
fn bytes(w: u32, h: u32) -> Vec<u8> {
    let image = image::RgbaImage::from_pixel(w, h, image::Rgba([45, 71, 93, 255]));
    let mut output = std::io::Cursor::new(vec![]);
    image
        .write_to(&mut output, image::ImageFormat::Png)
        .unwrap();
    output.into_inner()
}
fn validate(
    sd: &[u8],
    hd: Option<&[u8]>,
    lw: u32,
    lh: u32,
    frames: u32,
) -> anyhow::Result<ActiveMods> {
    validate_with_catalog(sd, hd, lw, lh, frames, None)
}
fn validate_with_catalog(
    sd: &[u8],
    hd: Option<&[u8]>,
    lw: u32,
    lh: u32,
    frames: u32,
    catalog: Option<&Catalog>,
) -> anyhow::Result<ActiveMods> {
    let tmp = tempfile::tempdir()?;
    let m = tmp.path().join("pngprobe");
    fs::create_dir(&m)?;
    fs::write(
        m.join("mod.toml"),
        "id='pngprobe'\nname='PNG validation fixture'\nversion='1.0.0'\napi_version=1\ncontent='content.json'\n",
    )?;
    fs::write(m.join("sd.png"), sd)?;
    let mut art = json!({"png":"sd.png","logical_width":lw,"logical_height":lh,"frames":frames});
    if let Some(hd) = hd {
        fs::write(m.join("hd.png"), hd)?;
        art["hd_png"] = "hd.png".into();
    }
    fs::write(
        m.join("content.json"),
        serde_json::to_vec(
            &json!({"items":[{"id":"pngprobe:item","name":"PNG fixture","price":0,"art":art}]}),
        )?,
    )?;
    let d = modding::discover(tmp.path());
    assert!(d.errors.is_empty(), "{:?}", d.errors);
    ActiveMods::build(&Registry::default(), &d, &["pngprobe".into()], catalog)
}
fn sprite_reject(path: &Path, data: &[u8]) {
    fs::write(path, data).unwrap();
    assert!(Sprite::png(path, &[[0; 3]; 256]).is_err());
    assert!(validate(data, None, 1, 1, 1).is_err());
}
#[test]
fn alpha_threshold_ties_opaque_black_and_reserved_palette_remain_exact() {
    let d = tempfile::tempdir().unwrap();
    let p = d.path().join("pixels.png");
    let mut im = image::RgbaImage::new(5, 1);
    for (x, c) in [
        [255, 0, 0, 0],
        [0, 0, 0, 128],
        [120, 10, 20, 255],
        [120, 10, 20, 127],
        [0, 0, 255, 255],
    ]
    .into_iter()
    .enumerate()
    {
        im.put_pixel(x as u32, 0, image::Rgba(c));
    }
    im.save(&p).unwrap();
    let mut palette = [[255; 3]; 256];
    palette[0] = [0, 0, 0];
    palette[1] = [120, 10, 20];
    palette[2] = palette[1];
    palette[239] = [0, 0, 254];
    palette[240] = [0, 0, 255];
    let s = Sprite::png(&p, &palette).unwrap();
    assert_eq!(s.pixels, vec![TRANSPARENT, 0, 1, TRANSPARENT, 239]);
}
#[test]
fn corrupt_truncated_and_non_png_are_rejected_by_rendering_and_activation() {
    let d = tempfile::tempdir().unwrap();
    let p = d.path().join("invalid.png");
    let valid = bytes(8, 8);
    sprite_reject(&p, &valid[..valid.len() / 2]);
    let mut corrupt = valid.clone();
    corrupt[40] ^= 0xff;
    sprite_reject(&p, &corrupt);
    sprite_reject(&p, b"GIF89a\x01\x00\x01\x00\x00\x00\x00");
}
#[test]
fn oversized_dimensions_and_pixel_count_stay_rejected() {
    let d = tempfile::tempdir().unwrap();
    let p = d.path().join("large.png");
    sprite_reject(&p, &bytes(4097, 1));
    sprite_reject(&p, &bytes(4096, 1025));
    assert!(validate(&bytes(4096, 1), None, 4096, 1, 1).is_ok());
}
#[test]
fn strip_canvas_and_hd_resolution_checks_stay_identical() {
    let sd = bytes(6, 2);
    let hd = bytes(12, 4);
    assert!(validate(&sd, Some(&hd), 3, 2, 2).is_ok());
    let err = validate(&bytes(7, 2), None, 3, 2, 2)
        .err()
        .unwrap()
        .to_string();
    assert!(err.contains("divide evenly"), "{err}");
    let err = validate(&bytes(6, 3), None, 3, 2, 2)
        .err()
        .unwrap()
        .to_string();
    assert!(err.contains("aspect differs"), "{err}");
    let err = validate(&sd, Some(&sd), 3, 2, 2).err().unwrap().to_string();
    assert!(err.contains("twice the logical"), "{err}");
    let err = validate(&sd, Some(&bytes(12, 5)), 3, 2, 2)
        .err()
        .unwrap()
        .to_string();
    assert!(err.contains("aspect differs"), "{err}");
}

#[test]
fn activation_still_rejects_an_invalid_catalog_palette() {
    let tmp = tempfile::tempdir().unwrap();
    fs::write(tmp.path().join("INDEX"), "1 3 PALETTE_DAT\n").unwrap();
    fs::write(tmp.path().join("PALETTE_DAT"), [0, 0, 0]).unwrap();
    let c = Catalog::open(tmp.path()).unwrap();
    assert!(validate_with_catalog(&bytes(2, 2), None, 2, 2, 1, Some(&c)).is_err());
}
