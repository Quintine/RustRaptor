# Sprite and terrain validation

`tests/visuals.rs` separates portable synthetic checks from local checks of the original catalog. Generated contact sheets and original pixels stay under ignored `../.reference/visuals/`; they are not shipped with the engine or committed.

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

The original 20-byte GFX header contains type, two option fields, width and height; its option fields are not replacement x/y origins. Span x/y coordinates locate pixels within the unchanged canvas. Player rendering uses that top-left canvas origin. Original centered effects use half the full canvas width/height, as recorded by `ANIMS_Register` in `../raptor/src/anims.cpp`; visible explosion bounds must not become animation anchors. Missing transparent margins or auto-cropping frames would move those anchors.

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

Optional HD replacements receive a separate source, canvas and silhouette review, recorded in `hd-art.md` and `hd-backlog.md`. The runtime selects accepted frames from the HD manifest and retains the original crisp fallback for unregistered or rejected frames. Original ScaleNx checks above do not certify generated HD artwork.

The frontend previously requested `AIRMED_BLK`, which does not exist in the original catalog. Effects now carry typed identities for the original air/ground explosions, flak, energy, people, flares and sparkles. The renderer selects each sequence's asset, duration, centered canvas origin and ground/air layer. Enemy deaths retain their original multiple bursts and RNG consumption; ground effects follow terrain scroll. This source-based port repairs the missing sequence and generic fallback. Exhaustive visual comparison of every effect remains outside the sampled checks above.

The new enemy packages include their generated SD/HD artwork and audio in Git. Their original style-reference pixels under `art/source/` remain excluded. Their per-package `art-qa.json` and `provenance.json` provide a separate record of supplied-art canvas alignment and generation prompts.

## Native effects and player presentation

The 2026-10-10 source review also compared `ANIMS_Register`, `SHOTS_Display`, `ESHOT_Display`, `BONUS_Display`, `RAP_GetShipPic` and `FLAME_Down` against their Rust render paths. It restored player and enemy laser shafts tiled every three logical pixels, their distinct power animations, native impact caps and three indexed turret-tracer lines. Emissions now include missile smoke, blue/orange hit sparks, energy-grab animations attached to enemies, world-space gun casings, missile-pod muzzle animations, shield lighting and delayed terrain flare/sparkle overlays. Gun casings use the original four-frame streak rather than an explosion at the muzzle. Native explosions and secondary animations jointly obey the original 100-animation allocation limit; visual allocation failure leaves weapon firing and RNG consumption intact.

Pickup halos, smoke masks and shield glow use the original +9 VGA light lookup to transform the existing background indices. Mask colors are not painted as foreground sprites. Colored companions use the normal optional HD selection and original fallback. The secondary queue and pickup presentation latches are excluded from saved gameplay serialization, advance on simulation steps and never consume the simulation RNG. Eight focused portable tests cover beam direction, cap offsets, tracer colors, lighting-mask holes, casing placement, smoke drift/lifetime, unchanged gameplay state and pool saturation. The complete retained native demo still matches all 1,889 gameplay snapshots, finishing with shield 3 and 60,825 credits.

Player presentation selects all seven `LPLAYER` poses normally. The two native dark missions, sector 2 wave 8 and sector 3 wave 3, select `DPLAYER` between shots and `FPLAYER` when the existing simulation firing-flash latch is set. Light missions retain `LPLAYER` during the flash. The player and its original shadow mask use the same selected canvas. Accepted HD frames are read by that asset ID, with original fallback for an unregistered dark or flash frame.

Engine flames are native procedural shading, not missing sprite files. Each simulation tick selects an eight-row or twelve-row phase; the two four-pixel-wide bands follow the original seven bank offsets and draw immediately before the ship. Eight original VGA remap tables add 16, 14, 12, 10, 8, 6, 4 and 2 to six-bit palette components. The ramp preserves the native 16.16 accumulator and recomputes its height after viewport clipping. The ship covers the bands at its rear edge, and both flame passes disappear when the player is hidden. Four portable tests cover all campaign/frame mappings, bank offsets, interpolated placement, exact ramp phases, clipping, overlapping shade passes, composition order and render-only behavior at 1× and 4×.

Local render captures are under ignored `../.reference/secondary-effects/`. `native-effects-{sd,hd}-{1,2,3}.png` show controlled beam and secondary-animation frames. `native-player-family-{0,1,2}-{sd,hd}.png` show the light, dark and flash families in their original mission scenes. `native-player-banking-flames-{sd,hd}.png` contain all seven banking poses, with rows ordered light/eight-row phase, light/twelve-row phase, dark/eight-row phase, dark/twelve-row phase, flash/eight-row phase and flash/twelve-row phase. Their fixtures assert that drawing does not mutate the world. These controlled captures assess placement and composition; they are not an exhaustive pixel comparison of every effect against C++.

Both player contact sheets and the light HD and dark firing-flash mission scenes were inspected after capture. Engines remain registered across the seven banks, both phases retain their indexed terrain colors and the ship covers the upper flame row. At capture time, the light family selected its supplied HD artwork; the dark and firing-flash frames retained the original crisp fallback. The earlier secondary-effect captures were also inspected for beam caps, pickup halos and shield composition. Subsequent complete-family approvals are recorded in the maintained HD ledger and independent full review.

```sh
cargo test --lib original_
cargo test --test secondary_effects --test transitions
cargo test --lib original_secondary_effects_capture_sd_and_hd_without_gameplay_mutation -- --ignored
cargo test --lib original_player_flames_and_flash_capture_complete_banking_families_in_sd_and_hd -- --ignored
cargo test --test campaigns complete_demo_1_matches_every_reference_gameplay_snapshot -- --ignored
```

The generic `A_SMALL_SMOKE` and `A_ENERGY_GRAB_HIT` handles have no C++ call sites, so no invented emitters were added. The restored render paths do not imply that every original effect has an HD remaster; remaining artwork is tracked in the HD backlog.

Generic HUD pictures, timed currency pickups and native light masks now consult the same source-bound optional HD pack. HUD and pickup artwork retains its original logical anchor and canvas. Smoke, shield and pickup glow use replacement alpha only to shade existing palette indices through the native light table. They do not paint the replacement's RGB colors onto the scene. Synthetic HUD and sparse HD-mask regressions at 1× and 4× verify the supplied artwork reaches these paths, indexed shading retains holes and centers, and drawing does not change world state. Original collision and projected shadow masks continue to use native geometry.
