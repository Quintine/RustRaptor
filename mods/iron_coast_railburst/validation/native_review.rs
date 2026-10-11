//! Read-only public engine asset/audio review for both independent Stage 2 mods.
//! Writes captures only to the caller's evidence directory, never to game data.
use image::{RgbaImage, imageops};
use raptor_replica::{
    assets::{Catalog, Sprite, TRANSPARENT},
    audio::Mixer,
    content::{ContentId, Registry, art_sprite_variant},
    modding::{self, ActiveMods},
    render::{Canvas, nearest},
    sound::{SoundBank, encode_capture},
};
use serde_json::json;
use std::{env, fs, path::Path};
fn normalized(sprite: &Sprite, w: usize, h: usize) -> Sprite {
    let mut out = Sprite::blank(w, h);
    for y in 0..h {
        for x in 0..w {
            out.pixels[y * w + x] =
                sprite.pixels[(y * sprite.height / h) * sprite.width + x * sprite.width / w];
        }
    }
    out
}
fn main() {
    let args: Vec<_> = env::args().collect();
    assert_eq!(args.len(), 4, "usage: native_review DATA MODS EVIDENCE");
    let catalog = Catalog::open(&args[1]).unwrap();
    let base = Registry::base(&catalog).unwrap();
    let ids = ["iron_coast_railburst", "iron_coast_depth_charge"].map(String::from);
    let discovery = modding::discover(Path::new(&args[2]));
    let active = ActiveMods::build(&base, &discovery, &ids, Some(&catalog)).unwrap();
    let out = Path::new(&args[3]);
    fs::create_dir_all(out).unwrap();
    let palette = catalog.palette().unwrap();
    let mut rows = Vec::new();
    let mut gallery = RgbaImage::new(1024, 1024);
    let mut row = 0;
    for owner in &ids {
        for kind in ["equipment", "projectile"] {
            let id: ContentId = format!(
                "{owner}:{}",
                if kind == "equipment" {
                    "equipment"
                } else {
                    "projectile"
                }
            )
            .as_str()
            .into();
            let art = active.registry.art(&id).unwrap();
            for hd in [false, true] {
                let source =
                    art_sprite_variant(&catalog, &active.registry, owner, art, 0, hd).unwrap();
                assert!(
                    source
                        .pixels
                        .iter()
                        .filter(|c| **c != TRANSPARENT)
                        .all(|c| *c < 240)
                );
                assert!(
                    source.pixels[0] == TRANSPARENT
                        && source.pixels[source.width - 1] == TRANSPARENT
                );
                let mut counts = Vec::new();
                for scale in 1..=4 {
                    // The same canvas sizing and nearest resampling used by Host::art.
                    let display = if source.width == art.logical_width as usize
                        && source.height == art.logical_height as usize
                    {
                        nearest(&source, scale)
                    } else {
                        normalized(
                            &source,
                            art.logical_width as usize * scale,
                            art.logical_height as usize * scale,
                        )
                    };
                    counts.push(json!({"scale":scale,"width":display.width,"height":display.height,"painted":display.pixels.iter().filter(|c|**c!=TRANSPARENT).count()}));
                    let mut canvas = Canvas::new(scale);
                    canvas.clear(12);
                    canvas.rect(160, 0, 160, 200, 93);
                    for (x, y) in [(70, 90), (230, 90)] {
                        canvas.blit(&display, x * scale as i32, y * scale as i32);
                    }
                    let rgba = RgbaImage::from_raw(
                        canvas.image.width as u32,
                        canvas.image.height as u32,
                        canvas.rgba(&palette, false),
                    )
                    .unwrap();
                    rgba.save(out.join(format!(
                        "{owner}-{kind}-{}-{scale}x.png",
                        if hd { "hd" } else { "sd" }
                    )))
                    .unwrap();
                }
                let display = normalized(
                    &source,
                    art.logical_width as usize * 8,
                    art.logical_height as usize * 8,
                );
                let mut cell = Canvas::new(1);
                cell.clear(12);
                cell.rect(160, 0, 160, 200, 93);
                cell.blit(&display, 20, 20);
                cell.blit(&display, 180, 20);
                let rgba = RgbaImage::from_raw(320, 200, cell.rgba(&palette, false)).unwrap();
                imageops::overlay(
                    &mut gallery,
                    &rgba,
                    if hd { 512 } else { 0 },
                    (row * 256) as i64,
                );
                rows.push(json!({"owner":owner,"kind":kind,"hd":hd,"physical_canvas":[source.width,source.height],"logical_canvas":[art.logical_width,art.logical_height],"frame":0,"frames":art.frames,"ordinary_palette_only":true,"clear_corner_alpha":true,"all_scales":counts}));
            }
            row += 1;
        }
    }
    gallery.save(out.join("indexed-sd-hd-gallery.png")).unwrap();
    let instruments = catalog.named("GENMIDI_OP2").unwrap();
    let mut audio = Vec::new();
    for owner in &ids {
        for kind in ["fire", "impact"] {
            let id: ContentId = format!("{owner}:{kind}").as_str().into();
            let mut bank = SoundBank::default();
            let sample = bank.mod_sample(&active.registry, &id).unwrap();
            assert!(!sample.data.is_empty());
            let mut mixer = Mixer::new(44100, &instruments).unwrap();
            mixer.start_capture(1).unwrap();
            bank.queue_mod(&active.registry, &mut mixer, &id).unwrap();
            let mut samples = vec![0; 44100 * 2];
            mixer.mix(&mut samples);
            assert!(samples.iter().any(|x| *x != 0));
            let file = format!("{owner}-{kind}-mixed.wav");
            fs::write(
                out.join(&file),
                encode_capture(&mixer.take_capture().unwrap()).unwrap(),
            )
            .unwrap();
            audio.push(json!({"id":id,"decoder":"SoundBank::mod_sample","mixer":"Mixer::sample through SoundBank::queue_mod","source_rate":sample.rate,"decoded_samples":sample.data.len(),"mixed_rate":44100,"mixed_channels":2,"nonzero_output_samples":samples.iter().filter(|x|**x!=0).count(),"peak":samples.iter().map(|x|(*x as i32).abs()).max().unwrap(),"capture":file}));
        }
    }
    fs::write(out.join("native-review.json"),serde_json::to_vec_pretty(&json!({"scope":"Public PNG decoder, same Host art normalization, indexed Canvas blitter and actual SoundBank/Mixer. Synthetic backgrounds; no live desktop/gameplay claim.","assets":rows,"audio":audio})).unwrap()).unwrap();
}
