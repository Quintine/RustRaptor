//! Full-color menu illustration; indexed gameplay and movie palettes stay separate.
use crate::{assets::TRANSPARENT, render::Canvas};
use image::{
    RgbaImage,
    imageops::{FilterType, resize},
};
use std::collections::BTreeMap;

pub const MENU_PANEL: u16 = 257;

pub struct MenuArt {
    original: RgbaImage,
    resized: BTreeMap<usize, RgbaImage>,
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
        let background = self.resized.entry(canvas.scale).or_insert_with(|| {
            resize(
                &self.original,
                canvas.image.width as u32,
                canvas.image.height as u32,
                FilterType::Lanczos3,
            )
        });
        let mut rgba = background.as_raw().clone();
        for (i, index) in canvas.image.pixels.iter().enumerate() {
            let color = if *index == MENU_PANEL {
                [0, 1, 2].map(|channel| {
                    (([12u16, 18, 29][channel] * 85 + rgba[i * 4 + channel] as u16 * 15) / 100)
                        as u8
                })
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
