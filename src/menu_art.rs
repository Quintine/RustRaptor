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

pub struct MenuArt {
    original: RgbaImage,
    resized: BTreeMap<(usize, usize, usize), RgbaImage>,
}
impl MenuArt {
    pub fn bundled() -> Self {
        let original = image::load_from_memory(include_bytes!("../art/menu-background-v1.png"))
            .expect("bundled menu artwork is a checked PNG")
            .into_rgba8();
        Self {
            original,
            resized: BTreeMap::new(),
        }
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
        for (i, index) in canvas.image.pixels.iter().enumerate() {
            let color = if matches!(*index, MENU_PANEL | MENU_CARD | MENU_FOCUS) {
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
}
