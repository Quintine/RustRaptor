//! Full-color menu illustration; indexed gameplay and movie palettes stay separate.
use crate::{assets::TRANSPARENT, render::Canvas};
use image::{DynamicImage, RgbaImage, imageops::FilterType};
use std::collections::BTreeMap;

pub const MENU_PANEL: u16 = 257;
pub const MENU_CARD: u16 = 258;
pub const MENU_FOCUS: u16 = 259;
pub const MENU_TEXT: u16 = 260;
pub const MENU_MUTED: u16 = 261;
pub const MENU_ACCENT: u16 = 262;
pub const MENU_RULE: u16 = 263;
/// A menu-only full-color briefing viewport; never a gameplay palette entry.
pub const MENU_BRIEFING: u16 = 264;
pub const BRIEFING_WIDTH: u32 = 132;
pub const BRIEFING_HEIGHT: u32 = 70;

pub struct MenuArt {
    original: RgbaImage,
    briefing: Option<(String, RgbaImage)>,
    resized: BTreeMap<(usize, usize, usize), RgbaImage>,
}
impl MenuArt {
    pub fn bundled() -> Self {
        let original = image::load_from_memory(include_bytes!("../art/menu-background-v1.png"))
            .expect("bundled menu artwork is a checked PNG")
            .into_rgba8();
        Self {
            original,
            briefing: None,
            resized: BTreeMap::new(),
        }
    }
    pub fn clear_briefing(&mut self) {
        self.briefing = None;
    }
    pub fn has_briefing(&self, key: &str) -> bool {
        self.briefing
            .as_ref()
            .is_some_and(|(cached, _)| cached == key)
    }
    /// Cache only the current thumbnail. A huge mod list must not retain every
    /// decoded full-size source; checked PNG decoding happens before this call.
    pub fn set_briefing(
        &mut self,
        key: String,
        image: RgbaImage,
        frames: u32,
        scale: usize,
    ) -> anyhow::Result<()> {
        anyhow::ensure!(
            frames > 0 && image.width() % frames == 0,
            "invalid briefing strip"
        );
        anyhow::ensure!(scale > 0 && scale <= 8, "invalid briefing display scale");
        let frame_width = image.width() / frames;
        anyhow::ensure!(
            frame_width > 0 && image.height() > 0,
            "empty briefing image"
        );
        let first = image::imageops::crop_imm(&image, 0, 0, frame_width, image.height()).to_image();
        // This matches the cinematic Stormwall briefing: a landscape image
        // fills one shared viewport without stretching its aircraft or terrain.
        let image = DynamicImage::ImageRgba8(first)
            .resize_to_fill(
                BRIEFING_WIDTH * scale as u32,
                BRIEFING_HEIGHT * scale as u32,
                FilterType::Lanczos3,
            )
            .into_rgba8();
        self.briefing = Some((key, image));
        Ok(())
    }
    pub fn compose(
        &mut self,
        canvas: &Canvas,
        palette: &[[u8; 3]; 256],
        scanlines: bool,
    ) -> Vec<u8> {
        let background = self
            .resized
            .entry((canvas.scale, canvas.image.width, canvas.image.height))
            .or_insert_with(|| {
                DynamicImage::ImageRgba8(self.original.clone())
                    .resize_to_fill(
                        canvas.image.width as u32,
                        canvas.image.height as u32,
                        FilterType::Lanczos3,
                    )
                    .into_rgba8()
            });
        let mut rgba = background.as_raw().clone();
        // Locate the marker on the final menu canvas. This follows the host's
        // centered 16:9 menu offset and also works for direct menu captures.
        let briefing_origin = canvas
            .image
            .pixels
            .iter()
            .enumerate()
            .filter(|(_, index)| **index == MENU_BRIEFING)
            .fold(None, |origin: Option<(usize, usize)>, (index, _)| {
                let point = (index % canvas.image.width, index / canvas.image.width);
                Some(origin.map_or(point, |(x, y)| (x.min(point.0), y.min(point.1))))
            });
        for (i, index) in canvas.image.pixels.iter().enumerate() {
            let color = if *index == MENU_BRIEFING {
                let pixel = self
                    .briefing
                    .as_ref()
                    .and_then(|(_, image)| {
                        let (left, top) = briefing_origin?;
                        let x = i % canvas.image.width - left;
                        let y = i / canvas.image.width - top;
                        (x < image.width() as usize && y < image.height() as usize)
                            .then(|| image.get_pixel(x as u32, y as u32).0)
                    })
                    .unwrap_or([0, 0, 0, 255]);
                [0, 1, 2].map(|channel| {
                    ((pixel[channel] as u16 * pixel[3] as u16
                        + rgba[i * 4 + channel] as u16 * (255 - pixel[3] as u16))
                        / 255) as u8
                })
            } else if matches!(*index, MENU_PANEL | MENU_CARD | MENU_FOCUS) {
                let (tint, opacity) = match *index {
                    MENU_CARD => ([10u16, 17, 23], 72),
                    MENU_FOCUS => ([49u16, 38, 27], 82),
                    _ => ([12u16, 18, 29], 85),
                };
                [0, 1, 2].map(|channel| {
                    ((tint[channel] * opacity + rgba[i * 4 + channel] as u16 * (100 - opacity))
                        / 100) as u8
                })
            } else if *index == MENU_TEXT {
                [221, 225, 224]
            } else if *index == MENU_MUTED {
                [147, 163, 171]
            } else if *index == MENU_ACCENT {
                [237, 180, 105]
            } else if *index == MENU_RULE {
                [65, 79, 85]
            } else if *index == TRANSPARENT {
                [rgba[i * 4], rgba[i * 4 + 1], rgba[i * 4 + 2]]
            } else {
                palette[(*index).min(255) as usize]
            };
            let dark =
                scanlines && (i / canvas.image.width) % (canvas.scale * 3) == canvas.scale * 2;
            for j in 0..3 {
                rgba[i * 4 + j] = if dark { color[j] / 2 } else { color[j] };
            }
            rgba[i * 4 + 3] = 255;
        }
        rgba
    }
    pub fn sidebars(&self) -> RgbaImage {
        let mut image = DynamicImage::ImageRgba8(self.original.clone())
            .resize_to_fill(800, 450, FilterType::Lanczos3)
            .into_rgba8();
        for pixel in image.pixels_mut() {
            for channel in &mut pixel.0[..3] {
                *channel = (*channel as u16 * 23 / 100) as u8;
            }
            pixel[3] = 255;
        }
        image
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn menu_overlay_preserves_full_color_background_and_opaque_zero() {
        let mut art = MenuArt::bundled();
        let mut canvas = Canvas::new(2);
        canvas.clear(TRANSPARENT);
        let mut palette = [[0; 3]; 256];
        palette[7] = [240, 210, 160];
        let background = art.compose(&canvas, &palette, false);
        assert!(background.chunks_exact(4).any(|pixel| pixel[0] != pixel[1]));
        canvas.rect(10, 10, 3, 3, 7);
        canvas.rect(20, 20, 3, 3, 0);
        let overlay = art.compose(&canvas, &palette, false);
        let amber = (20 * canvas.image.width + 20) * 4;
        assert_eq!(&overlay[amber..amber + 4], &[240, 210, 160, 255]);
        let black = (40 * canvas.image.width + 40) * 4;
        assert_eq!(&overlay[black..black + 4], &[0, 0, 0, 255]);
        assert_eq!(&background[..4], &overlay[..4]);
        assert_eq!(art.resized.len(), 1);
    }
    #[test]
    fn briefing_crop_preserves_square_geometry_and_uses_frame_zero() {
        let mut art = MenuArt::bundled();
        let source = RgbaImage::from_fn(320, 80, |x, y| {
            image::Rgba(if x >= 160 {
                [255, 0, 0, 255]
            } else if (60..100).contains(&x) && (20..60).contains(&y) {
                [0, 255, 0, 255]
            } else {
                [0, 0, 0, 255]
            })
        });
        art.set_briefing("strip".into(), source, 2, 1).unwrap();
        let image = &art.briefing.as_ref().unwrap().1;
        assert_eq!(image.dimensions(), (BRIEFING_WIDTH, BRIEFING_HEIGHT));
        let points: Vec<_> = image
            .enumerate_pixels()
            .filter(|(_, _, p)| p[1] > 200)
            .map(|(x, y, _)| (x, y))
            .collect();
        let width = points.iter().map(|p| p.0).max().unwrap()
            - points.iter().map(|p| p.0).min().unwrap()
            + 1;
        let height = points.iter().map(|p| p.1).max().unwrap()
            - points.iter().map(|p| p.1).min().unwrap()
            + 1;
        assert!(
            width.abs_diff(height) <= 1,
            "aircraft geometry must not be stretched: {width}x{height}"
        );
        assert!(
            !image.pixels().any(|p| p[0] > 0),
            "later animation frames must not leak into frame zero"
        );
    }
    #[test]
    fn briefing_marker_follows_menu_offset_and_does_not_change_palette_pixels() {
        let mut art = MenuArt::bundled();
        art.set_briefing(
            "full-color".into(),
            RgbaImage::from_pixel(320, 200, image::Rgba([17, 123, 231, 255])),
            1,
            2,
        )
        .unwrap();
        let mut canvas = Canvas::new(2);
        canvas.clear(TRANSPARENT);
        canvas.rect(
            70,
            60,
            BRIEFING_WIDTH as i32,
            BRIEFING_HEIGHT as i32,
            MENU_BRIEFING,
        );
        canvas.rect(10, 10, 2, 2, 7);
        let mut palette = [[0; 3]; 256];
        palette[7] = [101, 102, 103];
        let rgba = art.compose(&canvas, &palette, false);
        for (x, y) in [(140, 120), (403, 259)] {
            let index = (y * canvas.image.width + x) * 4;
            assert_eq!(&rgba[index..index + 4], &[17, 123, 231, 255]);
        }
        let index = (20 * canvas.image.width + 20) * 4;
        assert_eq!(&rgba[index..index + 4], &[101, 102, 103, 255]);
    }
    #[test]
    fn briefing_alpha_and_scanlines_apply_inside_the_same_viewport() {
        let mut art = MenuArt::bundled();
        let mut canvas = Canvas::new(1);
        canvas.clear(TRANSPARENT);
        let palette = [[0; 3]; 256];
        let background = art.compose(&canvas, &palette, false);
        art.set_briefing(
            "alpha".into(),
            RgbaImage::from_pixel(132, 70, image::Rgba([20, 80, 150, 128])),
            1,
            1,
        )
        .unwrap();
        canvas.rect(40, 30, 132, 70, MENU_BRIEFING);
        let plain = art.compose(&canvas, &palette, false);
        let scan = art.compose(&canvas, &palette, true);
        for (x, y) in [(40, 30), (41, 32)] {
            let i = (y * canvas.image.width + x) * 4;
            for c in 0..3 {
                let expected = ([20u16, 80, 150][c] * 128 + background[i + c] as u16 * 127) / 255;
                assert_eq!(plain[i + c], expected as u8);
                assert_eq!(
                    scan[i + c],
                    if y % 3 == 2 {
                        expected as u8 / 2
                    } else {
                        expected as u8
                    }
                );
            }
        }
        assert_eq!(&plain[..4], &background[..4]);
    }
    #[test]
    fn briefing_cache_is_one_thumbnail_and_invalid_strips_are_rejected() {
        let mut art = MenuArt::bundled();
        art.set_briefing("sd".into(), RgbaImage::new(320, 200), 1, 1)
            .unwrap();
        assert!(art.has_briefing("sd"));
        art.set_briefing("hd".into(), RgbaImage::new(1280, 800), 1, 4)
            .unwrap();
        assert!(!art.has_briefing("sd"));
        assert!(art.has_briefing("hd"));
        assert_eq!(art.briefing.as_ref().unwrap().1.dimensions(), (528, 280));
        assert!(
            art.set_briefing("bad".into(), RgbaImage::new(7, 4), 2, 1)
                .is_err()
        );
        assert!(
            art.set_briefing("bad".into(), RgbaImage::new(8, 4), 0, 1)
                .is_err()
        );
        assert!(art.has_briefing("hd"));
        art.clear_briefing();
        assert!(!art.has_briefing("hd"));
    }
}
