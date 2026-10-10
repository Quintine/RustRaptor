# Sprite and terrain validation

`tests/visuals.rs` separates portable synthetic checks from local checks of the original catalog. Generated contact sheets and original pixels stay under ignored `.reference/visuals/`; they are not shipped with the engine or committed.

The independent test oracle follows the unoptimized corner rules in the [published Scale2x/Scale3x algorithm specification](https://www.scale2x.it/algorithm), with its clamped border sampling. Scale4x applies the independent Scale2x oracle twice. The renderer uses a shared optimized guard, so the oracle and renderer express the rules differently.

The portable suite checks all 19,683 neighborhoods over two palette colors plus transparency, additional multi-color patterns and one-pixel borders. It verifies exact output indices, opaque palette indices 0/255, transparent composition, palette changes without changing stored indices, clipping on every viewport edge, indexed shadow masks, sharply scaled bitmap text and neighbor context at terrain boundaries. Its independent-tile fixture deliberately produces different results when tiles are filtered separately, so the seam check cannot pass trivially. Shadow checks cover six-bit RGB clamping, the original Manhattan palette-distance and last-equal tie rules, native ground-mask offsets, signed air projection, collapsed-row suppression, sparse spans, clipping at 1×..4× and interpolated translation without coverage loss.

Run portable checks with:

```sh
cargo test --test visuals
```

Run the original-data checks and create private contact sheets with:

```sh
cargo test --test visuals original_sequences_preserve_canvases_palette_origins_and_terrain_context -- --ignored
cargo test --test visuals original_shadow_tables_and_banking_masks_match_indexed_projection -- --ignored
```

The local checks cover all seven light, dark and firing-flash player banking frames; all 42 `GEXPLO_BLK` ground explosion frames; all 16 `AIRBOOM_PIC` and 13 `EXPLO2_BLK` frames; four micro-missile and gun-ejecta frames; six `SHIP22G1_PIC` boss frames and four `SHIP08G1_PIC` enemy frames. Each original frame is compared against the oracle at 1×, 2×, 3× and 4×, with exact logical canvas dimensions and original palette labels retained. The report records frame IDs, logical canvases, full-canvas center anchors and visible bounds at every scale.

The original 20-byte GFX header contains type, two option fields, width and height; its option fields are not replacement x/y origins. Span x/y coordinates locate pixels within the unchanged canvas. Player rendering uses that top-left canvas origin. Original centered effects use half the full canvas width/height, as recorded by `ANIMS_Register` in `raptor/src/anims.cpp`; visible explosion bounds must not become animation anchors. Missing transparent margins or auto-cropping frames would move those anchors.

A three-by-three patch from the first original mission is composed at native resolution and filtered as one image. The center tile filtered with two original pixels of neighboring context must exactly match the center of the full joined patch at 2×, 3× and 4×. The renderer's two-pixel terrain gutter covers Scale4x's two successive passes. This establishes filter consistency across the tested boundaries; it does not assess whether different source tiles were artistically seamless.

Each sequence emits `<NAME>-nearest4.png`, `<NAME>-scale4.png` and `<NAME>-runtime4.png`. The runtime sheet applies the engine's per-asset fallback. Read left-to-right, then top-to-bottom, up to seven frames per row. Terrain comparisons are `terrain-joined-2x.png`, `terrain-joined-3x.png`, `terrain-joined-4x.png` and matching `terrain-independent-*` files. `report.json` stores frame order, bounds, opaque pixel counts, fallback flags, selected terrain row and the number of pixels changed by independent tile filtering.

## Review findings

On 2026-10-10, all fourteen portable tests and both local catalog checks passed. The sequence check covered all 110 frames at every scale plus the terrain patch. Complete nearest-neighbor and Scale4 contact sheets were inspected for banking, explosions, projectiles, the sample enemy and the opening boss animation. No canvas shift, clipped replacement canvas, lost palette identity or changed simulation dimensions was found. Banking retains the nose and engine registration across all seven poses. Large explosion lobes and expanding rings remain aligned throughout their sequences.

Two nearest-neighbor fallback groups are implemented in `render::prefers_nearest`, covering 26 original frames:

- `NMSHOT_BLK` frames 0..3, assets `0x101c3..0x101c6`: each frame has four visible source pixels. At 4×, ScaleNx keeps 44 opaque pixels against nearest-neighbor's 64, reducing visible coverage by 31.25% and changing the small square mark into a round bead. The implemented nearest-neighbor fallback preserves this tiny projectile's brightness and shape.
- Sparse late `GEXPLO_BLK` frames 20..41, assets `0x10178..0x1018d`: Scale4 reduces opaque coverage by approximately 10..25%. The implemented nearest-neighbor fallback preserves those residual embers; the large early flame frames retain the smoother filter. The initial 17-pixel flash also loses about 10.3% coverage and remains a candidate for the tiny-effect fallback after playback review.

The original-data test exercises the actual `SpriteCache` fallback route at all four factors and asserts exact nearest-neighbor pixels and full original opaque coverage for every fallback frame. Other frames must still match ScaleNx. Supplied HD PNGs bypass this original-asset filtering policy and retain their detail.

The desktop shadow pass follows `shadow.cpp` and `gfxapi.cpp`: ground masks use the -9 palette table at (-3,+4); aircraft and player masks use a separate -6 table at (-10,+20), projected through view (160,100,1000), depth 1280 and distance 200. The renderer retains signed integer division followed by arithmetic shift, inclusive horizontal span endpoints, and first-row coverage when several source rows collapse to one projected row. It shades existing palette indices rather than painting flat translucent black. Ground shadows precede ground enemies; air and player shadows follow ground enemies and precede ground effects and aircraft. Legacy enemy field 11 controls presence, with the original 25-ground/50-air limits. Mod enemies receive the corresponding ground/air shadow from their supplied SD logical canvas. Optional HD artwork retains this logical shadow mask.

The original shadow code's preliminary bounds check projects its origin twice and calculates height using the projected x coordinate. Rust clips each actual projected span instead, correcting missing valid shadows near the lower edge. This is a presentation culling repair; original span projection and palette mapping are retained. It does not alter collisions or simulation state.

The local shadow test compares all 256 entries of the original -9, -6 and +9 tables against an independent distance/tie oracle. It verifies all seven player banking masks against an independent native span raster at all four factors and emits `player-shadow-banking-4x.png`, `ground-shadow-4x.png` and `shadow-tables.json` under the private visual directory. The first contact sheet pairs each complete banking pose with its projected shadow on original terrain; the second checks native ground offset and registration.

Both shadow contacts were inspected after the tests passed. The seven banking shadows retain their changing silhouette and full-canvas registration without transparent rectangles or missing lower-screen spans. The ground defense shadow retains the native (-3,+4) offset. Shadow pixels remain terrain palette colors, so palette changes and indexed composition remain available.

The inspected light ship frames retain 97.2..98.3% of nearest-neighbor opaque coverage at 4×, dark/flash frames retain at least 97.8%, the large boss retains at least 99.6% and the sample enemy retains 99.9%. These are presentation measurements, not collision masks. Their full original logical canvases remain unchanged. No nearest-neighbor fallback is recommended for those reviewed sequences.

The original terrain patch exposed 113 differing pixels at 2×, 297 at 3× and 727 at 4× when the tiles were filtered independently. Filtering the joined patch with the tested two-pixel neighbor gutter exactly matched the full-image center at each factor. The paired contact sheets show subtle texture discontinuities along independent tile boundaries; joined filtering retains the diagonal water transition. This review covers the crisp original terrain path; supplied HD terrain needs its own artistic edge review.

The optional HD player proof remains a separate review: it replaces only straight flight, so banking still changes visual style. The generated extreme-bank attempt remains excluded because it shortened the engines and failed the footprint check; crisp original fallback is retained for that frame.

The frontend previously requested `AIRMED_BLK` for effects, but that name does not exist in the original catalog. Actual original sequences include `AIRBOOM_PIC`, `GEXPLO_BLK`, `EXPLO2_BLK`, flak and sparks. This finding was reported to the engine owner. A generic explosion sequence repairs the visible fallback, but full effect identity, duration, layer, origin and update parity require separate comparison with the C++ animation system.

The new enemy packages include their generated SD/HD artwork and audio in Git. Their original style-reference pixels under `art/source/` remain excluded. Their per-package `art-qa.json` and `provenance.json` provide a separate record of supplied-art canvas alignment and generation prompts.
