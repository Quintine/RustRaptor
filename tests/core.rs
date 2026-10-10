use raptor_replica::{
    assets::{Catalog, Sprite, TRANSPARENT, contained, i16_at, i32_at},
    audio::{DigitalSample, Mixer, MusScore},
    content::{ContentPack, Registry},
    persistence::{Config, Pilot},
    render::upscale,
};

fn pilot_registry() -> Registry {
    let missions: Vec<_> = (1..=3).flat_map(|s| (1..=9).map(move |w| serde_json::json!({
        "id":format!("base:sector_{s}_wave_{w}"),"name":"Synthetic wave","duration":100,"legacy_map":100+s*9+w
    }))).collect();
    let pack: ContentPack = serde_json::from_value(serde_json::json!({
        "items":[
            {"id":"base:forward_guns","name":"Forward Guns","price":12000,"legacy":0},
            {"id":"base:energy","name":"Energy","price":10000,"max_count":100,"initial_count":25,"legacy":16}
        ],"missions":missions
    })).unwrap();
    let mut registry = Registry::default();
    registry.apply(pack, "base").unwrap();
    registry.validate().unwrap();
    registry
}

#[test]
fn training_graduation_and_sector_cycles_preserve_original_progression() {
    let registry = pilot_registry();
    let mut pilot = Pilot {
        difficulty: 0,
        credits: 900000,
        mission: "base:sector_2_wave_4".into(),
        ..Pilot::default()
    };
    pilot.complete_mission(&registry).unwrap();
    assert_eq!(pilot.mission.0, "base:sector_1_wave_1");
    assert_eq!(pilot.difficulty, 1);
    assert_eq!(pilot.credits, 10000);
    assert_eq!(pilot.inventory[&"base:energy".into()], 75);
    assert!(pilot.legacy_progress.as_ref().unwrap().training_completed);
    pilot.mission = "base:sector_3_wave_9".into();
    pilot.difficulty = 2;
    pilot.complete_mission(&registry).unwrap();
    assert_eq!(pilot.mission.0, "base:sector_1_wave_1");
    assert_eq!(pilot.legacy_progress.as_ref().unwrap().difficulties[2], 3);
    assert_eq!(pilot.difficulty, 1);
    pilot.mission = "base:sector_1_wave_2".into();
    pilot.complete_mission(&registry).unwrap();
    assert_eq!(pilot.mission.0, "base:sector_1_wave_3");
}

#[test]
fn legacy_save_import_retains_metadata_without_modifying_source() {
    fn encrypt(bytes: &[u8]) -> Vec<u8> {
        let key = b"CASTLE";
        let mut index = 25 % key.len();
        let mut previous = key[index];
        bytes
            .iter()
            .map(|clear| {
                let byte = clear.wrapping_add(key[index]).wrapping_add(previous);
                previous = byte;
                index = (index + 1) % key.len();
                byte
            })
            .collect()
    }
    let mut header = vec![0u8; 88];
    header[..9].copy_from_slice(b"Synthetic");
    header[20..24].copy_from_slice(b"TEST");
    for (offset, value) in [
        (32, 65814i32),
        (36, 98765),
        (40, -1),
        (44, 1),
        (48, 3),
        (52, 8),
        (56, 1),
        (60, 2),
        (64, 0),
        (68, 2),
        (72, 1),
        (76, 3),
        (80, 0),
        (84, 1),
    ] {
        header[offset..offset + 4].copy_from_slice(&value.to_le_bytes());
    }
    let mut body = vec![0u8; 48];
    for (offset, value) in [(8, 1i32), (12, 0), (32, 71), (36, 16)] {
        body[offset..offset + 4].copy_from_slice(&value.to_le_bytes());
    }
    let bytes = [encrypt(&header), encrypt(&body)].concat();
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("CHAR0000.FIL");
    std::fs::write(&path, &bytes).unwrap();
    let registry = pilot_registry();
    let pilot = Pilot::import_legacy(&path, &registry).unwrap();
    assert_eq!(pilot.callsign, "TEST");
    assert_eq!(pilot.credits, 98765);
    assert_eq!(pilot.mission.0, "base:sector_2_wave_9");
    assert_eq!(pilot.inventory[&"base:energy".into()], 71);
    assert_eq!(pilot.completed.len(), 12);
    let progress = pilot.legacy_progress.as_ref().unwrap();
    assert_eq!(progress.portrait, 65814);
    assert_eq!(progress.difficulties, [0, 2, 1, 3]);
    assert!(progress.training_completed);
    let output = dir.path().join("pilot.json");
    pilot.save(&output).unwrap();
    assert_eq!(Pilot::load(&output, &registry, &[]).unwrap().credits, 98765);
    assert_eq!(std::fs::read(path).unwrap(), bytes);
}

fn header(kind: i32, width: i32, height: i32) -> Vec<u8> {
    [kind, 0, 0, width, height]
        .into_iter()
        .flat_map(i32::to_le_bytes)
        .collect()
}

#[test]
fn raw_pictures_keep_zero_opaque_and_spans_keep_empty_pixels_transparent() {
    let mut raw = header(1, 2, 1);
    raw.extend([0, 255]);
    assert_eq!(Sprite::decode(&raw).unwrap().pixels, [0, 255]);
    let mut span = header(0, 3, 2);
    span.extend([1i32, 1, 4, 2].into_iter().flat_map(i32::to_le_bytes));
    span.extend([0, 17]);
    span.extend([0i32, 0, -1, 0].into_iter().flat_map(i32::to_le_bytes));
    assert_eq!(
        Sprite::decode(&span).unwrap().pixels,
        [TRANSPARENT, TRANSPARENT, TRANSPARENT, TRANSPARENT, 0, 17]
    );
    for n in 0..span.len() {
        assert!(Sprite::decode(&span[..n]).is_err());
    }
}

#[test]
fn malformed_fields_and_spans_fail_without_panicking() {
    assert!(i16_at(&[], usize::MAX).is_err());
    assert!(i32_at(&[], usize::MAX).is_err());
    let mut span = header(0, 2, 2);
    span.extend([i32::MAX, 0, 0, 2].into_iter().flat_map(i32::to_le_bytes));
    span.extend([1, 2]);
    assert!(Sprite::decode(&span).is_err());
    assert!(Sprite::decode(&header(1, 4096, 4096)).is_err());
}

#[test]
fn scale_kernels_have_published_corner_results() {
    let input = Sprite {
        width: 3,
        height: 3,
        pixels: vec![9, 1, 8, 1, 2, 3, 7, 4, 6],
    };
    let two = upscale(&input, 2).unwrap();
    let four = upscale(&input, 4).unwrap();
    assert_eq!(
        [
            two.pixels[2 * 6 + 2],
            two.pixels[2 * 6 + 3],
            two.pixels[3 * 6 + 2],
            two.pixels[3 * 6 + 3]
        ],
        [1, 2, 2, 2]
    );
    let three = upscale(&input, 3).unwrap();
    let center: Vec<_> = (3..6)
        .flat_map(|y| (3..6).map(move |x| y * 9 + x))
        .map(|n| three.pixels[n])
        .collect();
    assert_eq!(center, [1, 1, 2, 1, 2, 2, 2, 2, 2]);
    assert_eq!(four, upscale(&two, 2).unwrap());
    assert!(upscale(&input, 5).is_err());
}

#[test]
fn catalog_paths_cannot_escape_or_follow_an_external_symlink() {
    let root = tempfile::tempdir().unwrap();
    let other = tempfile::tempdir().unwrap();
    std::fs::write(other.path().join("outside"), b"outside").unwrap();
    assert!(contained(root.path(), std::path::Path::new("../outside")).is_err());
    #[cfg(unix)]
    {
        std::os::unix::fs::symlink(other.path().join("outside"), root.path().join("link")).unwrap();
        assert!(contained(root.path(), std::path::Path::new("link")).is_err());
    }
}

#[test]
fn importing_settings_preserves_source_and_uses_sdl_key_names() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("SETUP.INI");
    let original = b"[Keyboard]\nFire=29\nFireSp=56\nMegaFire=54\n[Video]\nupscaler=3\n";
    std::fs::write(&path, original).unwrap();
    let config = Config::import_ini(&path).unwrap();
    assert_eq!(config.scale, 3);
    assert_eq!(config.bindings["fire"], "Left Ctrl");
    assert_eq!(config.bindings["special"], "Left Alt");
    assert_eq!(std::fs::read(path).unwrap(), original);
    #[cfg(feature = "desktop")]
    for key in config.bindings.values() {
        assert!(
            sdl2::keyboard::Scancode::from_name(key).is_some(),
            "unknown SDL key {key}"
        );
    }
}

// Original pixels never enter the test fixtures or version control. Set this
// variable only on a machine with the licensed extracted asset catalog.
#[test]
fn original_data_decoders_and_all_campaigns_when_available() {
    let Some(data) = std::env::var_os("RAPTOR_TEST_DATA") else {
        return;
    };
    let catalog = Catalog::open(data).unwrap();
    let registry = Registry::base(&catalog).unwrap();
    registry.validate().unwrap();
    assert_eq!(registry.missions.len(), 27);
    assert_eq!(registry.campaigns.len(), 3);
    let mut sprites = 0;
    for entry in catalog.entries.values() {
        let bytes = catalog.read(entry.id).unwrap();
        if bytes.len() >= 20
            && (i32_at(&bytes, 0).ok() == Some(0)
                || (i32_at(&bytes, 0).ok() == Some(1)
                    && i32_at(&bytes, 4).ok() == Some(1)
                    && i32_at(&bytes, 8).ok() == Some(0)))
            && matches!(i32_at(&bytes, 12).ok(), Some(1..=4096))
            && matches!(i32_at(&bytes, 16).ok(), Some(1..=4096))
        {
            Sprite::decode(&bytes).unwrap_or_else(|e| panic!("asset {:x}: {e}", entry.id));
            sprites += 1;
        }
        if bytes.starts_with(b"MUS\x1a") {
            MusScore::decode(&bytes).unwrap();
        }
    }
    assert!(
        sprites > 1000,
        "format discovery must include unnamed graphics"
    );
    for sector in 0..3 {
        let pilot = Pilot::demo(sector, &registry).unwrap();
        pilot.validate(&registry, &[]).unwrap();
        let selected = &registry.items[pilot.selected.as_ref().unwrap()];
        assert_eq!(selected.legacy, Some([5, 8, 8][sector]));
    }
    let mut mixer = Mixer::new(44100, &catalog.named("GENMIDI_OP2").unwrap()).unwrap();
    mixer.play(
        MusScore::decode(&catalog.named("RAP1_MUS").unwrap()).unwrap(),
        false,
    );
    let mut output = vec![0i16; 44100 * 2];
    mixer.mix(&mut output);
    assert!(
        output.iter().any(|v| *v != 0),
        "FM playback must produce sound"
    );
    let sample = catalog
        .entries
        .values()
        .find_map(|e| DigitalSample::decode(&catalog.read(e.id).ok()?).ok())
        .unwrap();
    mixer.sample(sample, 128, 128, 127, 1);
    mixer.mix(&mut output);
    assert!(output.iter().any(|v| *v != 0));
}
