# Image provenance

Generated with the built-in `image_gen.imagegen` tool on 2026-10-10. Original
local catalog assets `0x10360` (terrain, 32×32) and `0x102f6` (military sprite,
24×24) were decoded and visually inspected before generation. Reference PNGs
remain outside Git under `.reference/`; original assets remain in `data/`.

## Terrain source

Use case: stylized-concept. Actual scrolling terrain texture for a top-down
2D arcade shoot-em-up, Iron Coast Mission 1. Original Raptor terrain and
military sprite are style/scale references. Flat orthographic overhead view:
dark slate blue seawater on the left third, worn gray concrete seawall and
paved industrial port on the right. Rust-red loading pads, restrained yellow
safety lines, pipes and compact machinery. Readable 1990s military
science-fiction sprite aesthetics with HD material details. Opaque tall
composition, requested 1152×1536, split into nine columns and twelve rows of
128-pixel tiles. Uniform upper-left lighting. Quiet matching vertical edge
strips, no tile grid, text, aircraft, enemies, UI, perspective or watermark.

Source: `art/terrain-source-hd.png`; built-in output
`exec-24f2ac88-7f7c-4a13-8d7f-9e6a04dc209f.png`.

## Briefing/menu source

Use case: stylized-concept. Actual game briefing and mission-menu background,
referencing the generated shoreline terrain. Detailed overhead military
science-fiction harbor, wide composition for a 320×200 logical screen: dark
sea, fortified industrial docks, coastal road and armored docking platforms.
Uniform upper-left lighting, restrained sprite palette, clear dark upper area
for separately rendered bitmap text. No aircraft, enemies, text, labels,
grid, border, UI, perspective, horizon or watermark.

Source: `art/briefing-source-hd.png`; built-in output
`exec-4eb2c607-7c0b-4b9e-b646-ffbd16665672.png`.

## Destructible depot source

Use case: stylized-concept. Actual transparent overhead game sprite, using
original terrain and new shoreline as style references: compact square
rust-red supply crates and dark olive fuel tank, yellow hazard corners,
repair cross and steel tie-downs. Complete silhouette on a 32×32 logical
canvas with transparent margin, requested 256×256 HD output. Uniform
upper-left lighting, crisp military science-fiction shading. No floor,
background, terrain, external shadow, words, border, logo or watermark.
Genuinely transparent background.

Source: `art/depot-source-hd.png`; built-in output
`exec-65871adc-7bcd-40bd-bbf8-01230bb02b31.png`.

## Packaging and audio

Sources are retained without repainting. `build_assets.py` performs whole-map
resampling, palette conversion, cropping and reflection. Terrain is repeated
as twelve forward rows plus twelve reflected rows so repeat boundary pixels
match exactly; structures therefore recur in reflected blocks. Individual
tiles are cropped after the global SD pass to retain neighboring context.

Audio is original procedural synthesis from deterministic sine/harmonic
oscillators and seeded noise. Approach, dock warning, boss warning, victory,
depot impact and repair cues are mono PCM16 at 22,050 Hz, 0.35–1.2 seconds.
No original sound recording or external SoundFont was used. Generator seeds,
sample counts and SHA-256 output hashes are recorded in `asset-report.json`.
