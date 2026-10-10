# Optional HD artwork

The Rust Options screen includes **HD art**. It starts disabled. Enable it to use reviewed artwork from `data/hd/hd.json`; each missing or rejected frame keeps the selected original / 2x / 3x / 4x crisp treatment. The scale setting still determines the indexed rendering resolution, and the HD toggle can be changed while paused. HD art is presentation only: simulation, collision sizes, banking positions and save content IDs stay unchanged.

The current local proof covers **the light player ship's straight banking frame only** (`0x1011d`, frame 3 of 7). The other six frames, the dark-sector ship, enemies, projectiles and terrain retain original art. Switching into a bank therefore changes visual style. This proof is suitable for evaluating the look; it is not a finished remaster. Original and generated game pixels are excluded from Git.

The source was decoded with `tools/hd_art_source.py`, inspected, and passed to the **built-in image_gen tool** using the imagegen skill. The optional proof and its exact generation prompt are saved locally at:

- `data/hd/light-player-straight-hd-v1.png`
- `data/hd/prompts/light-player-straight-v1.txt`
- `data/hd/provenance.json`
- `data/hd/source/light-player-straight.png`

The PNG has real alpha transparency, is 1254x1254, and was copied unchanged from the tool's output. At the original 32x32 logical resolution, its visible alpha footprint overlaps the source by 92.1% intersection-over-union; its bounds are `(3,0)..(29,31)` against `(2,0)..(29,31)` for the original. The nose, wing layout, silver/gunmetal body and dark red accents remain recognizable, but panel detail and some contours differ. Further artistic review and a complete, consistent banking sequence are required before enabling HD art by default. An additional extreme-bank attempt is saved as `data/hd/light-player-bank-0-hd-v1.png` with `prompts/light-player-bank-0-v1.txt`, but is excluded from the active pack because its footprint overlap is only 62.2% and its engine ends are shortened. The original extreme-bank sprite continues to render.

## Pack format

The following is metadata only; artwork belongs in a separately distributed local pack. Decimal IDs are shown alongside their hexadecimal meaning.

```json
{
  "format_version": 1,
  "name": "Source-aligned HD artwork",
  "description": "Optional artwork; original fallback for uncovered frames",
  "sequences": [
    {
      "name": "Light player banking",
      "base_asset": 65818,
      "frame_count": 7,
      "frames": [
        {
          "frame": 3,
          "file": "light-player-straight-hd-v1.png",
          "logical_width": 32,
          "logical_height": 32,
          "origin": [0, 0],
          "source_sha256": "SHA-256 of the exact original 0x1011d catalog payload"
        }
      ]
    }
  ]
}
```

`base_asset` is `0x1011a`; the supplied frame targets `base_asset + frame`, so frames never depend on filenames or glob ordering. `frame_count` declares the whole original animation sequence and `frames` explicitly declares replacement coverage. An optional `crop: [x,y,width,height]` selects a rectangle from a PNG atlas.

Version 1 requires exact original logical canvas dimensions and the original top-left anchor `[0,0]`. Canvas alignment is retained even when transparent margins surround the visible image. The PNG or crop must have the same aspect ratio as the original canvas and at least twice its logical resolution. The source hash prevents artwork silently matching a changed original asset. Duplicate IDs, invalid sequence metadata, bad paths, crop bounds, missing transparency and unreasonable image allocations are rejected. Paths must remain inside the pack directory, including after symlink resolution. Open **D: details** from the main menu to inspect rejected frames and coverage.

HD frames are resampled directly to the selected presentation canvas and quantized to the game palette. They bypass ScaleNx filtering, preserve transparent pixels and use the normal layer order. Indexed output allows palette effects to apply consistently; subtle RGB shades and alpha edges are reduced by the original palette and binary sprite transparency. Terrain is currently composed at original resolution before its joined ScaleNx pass; use crisp terrain until a dedicated HD terrain composition path is validated.

## Source and sequence review

Use the existing catalog decoder to prepare a transparent reference without redrawing it:

```sh
python3 tools/hd_art_source.py --asset 1011d \
  --output data/hd/source/light-player-straight.png --preview-scale 16
```

Inspect every source frame before generating its replacement. Request the same orthographic camera, silhouette, canvas placement, orientation, material colors and lighting for every frame. Preserve the generated alpha. Do not substitute rotations of one frame for the original bank poses: compare the complete sequence at its logical size and at the intended display resolution. Verify that the nose, engine exits, wing extremes and animation pivots remain aligned and that no clipping or background halos appear.

Keep image-generation prompts and provenance alongside the artwork. Never overwrite original catalog assets. The loader deliberately accepts partial coverage so a reviewed sprite can be previewed before the complete pack is ready, while preserving per-frame fallback.
