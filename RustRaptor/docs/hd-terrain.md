# Original terrain remaster pipeline

HD terrain uses the original catalog ID of each currently displayed tile. Intact and destroyed pictures have separate IDs and source hashes; an intact replacement is never reused for a destroyed tile. Native maps keep intact art until their original destruction animation settles. JSON missions retain their existing immediate destroyed-state selection. Rendering does not change terrain health, rewards, collision dimensions, scrolling, update order or RNG.

The renderer first joins the original tiles at their logical dimensions on a row-aligned 320×268 indexed strip. The additional rows and two-pixel filtering gutter supply neighboring context for the selected Scale2x, Scale3x or Scale4x filter throughout all 32 native scroll phases. This original layer is assembled without consulting HD art, even when HD mode is enabled. Missing or rejected replacements therefore retain the complete original terrain treatment.

Reviewed native HD tiles are fetched lazily from `HdAssets` only for visible placements. Mod terrain can supply `hd_png`; a source PNG already at least twice its logical dimensions can also keep its supplied detail. Replacements are drawn directly at the selected presentation scale. Every placement uses its original logical anchor and the gutter offset. The completed layer is translated once for fractional scrolling before shadows, enemies, projectiles, effects and the ship are drawn. Individual tiles do not round their scroll offsets independently.

## Canonical tile and edge contract

Each original terrain ID needs one canonical full opaque 32×32 logical image, including IDs stored outside the named sprite folders. A generation job should include the exact original source, all cardinal neighbors encountered in mission layouts, actual 3×3 context samples and any intact/destroyed partner. Preserve coast crossings, road widths, building footprints, color families and edge geometry. Fine texture may improve; a displaced coastline or invented solid structure needs correction before acceptance.

A canonical tile may occur beside several different neighbors. The renderer prepares one pristine joined HD layer for all accepted visible tiles before resolving their edges. Where original material classes and source tones agree, adjacent HD tiles share corresponding pristine detail at each mirrored distance from the join. Four-tile corners apply this rule in both axes. This preserves fine grain rather than stretching a single outer-edge sample into repeated ridges. Distinct original coastline, road or material boundaries remain sharp. Each tile reaches its own full detail two logical pixels inward using integer smoothstep weights.

At an HD/original join, the replacement transitions to the unchanged joined original context instead. This preserves mixed coverage and source fallback. Full HD neighborhoods retain detailed colors across their internal edges, avoiding the grid produced by forcing every tile back to low-resolution source colors. Source geometry remains a generation and review requirement; edge blending does not repair a shifted coastline.

Opaque replacements must match `logical_width × scale` and `logical_height × scale` exactly. An unexpected transparent pixel or invalid canvas rejects the whole terrain overlay and adds a diagnostic. Fully opaque source pictures are accepted by the source-aware HD loader; artificial transparent holes are unnecessary.

The previous generated 3×3 shoreline prototype remains unregistered. It contains nine placements but only six unique original IDs, and its fine detail varies between repeated placements. Splitting it into global ID replacements would select arbitrary placement-specific art. Canonical jobs and source-bound review are required before those IDs count as remastered.

## Palette and memory behavior

The final terrain canvas remains indexed. Original water labels stay within the 240–244 cycling group; fire stays within 245–249. Original glow, flash and blink masks at 250–255 retain their exact labels. Ordinary terrain stays within 0–239, so quantizing an HD highlight cannot accidentally turn it into a blinking light. Palette cycling, blue flashes, fades, scanlines and subsequent indexed shadow shading therefore continue to apply to the complete scene.

The compositor retains a lazy 2 MiB palette transition table, invalidated when the base palette changes, and one prepared row-aligned viewport strip. At 4× its indexed image uses at most 2,744,320 bytes, plus a cache key capped at 64 KiB. It retains no individual HD tiles, atlases or mission map images. HD PNG, RGBA and indexed caches use the bounded lazy `HdAssets` provider. Working layers are temporary viewport images, so registering the complete terrain catalog does not require keeping every generated PNG in memory.

The prepared strip key includes the mission, row origin, selected intact/destroyed art at every visible placement, active mod hashes in priority order, base palette, presentation scale and HD setting. Terrain destruction invalidates it when the selected artwork changes; mod edits or load-order changes cannot reuse a previous content strip. Between those changes, integer scroll phases and interpolation translate the completed indexed strip without reconstructing or re-quantizing tiles. Palette cycling and fades continue at presentation time. Oversized keys or strips are discarded instead of retained.

## Verification and acceptance

Run the portable checks with:

```sh
LD_LIBRARY_PATH=/home/quintine/.local/lib cargo test --locked --manifest-path RustRaptor/Cargo.toml --test hd_terrain
```

The thirteen portable tests cover shared edges and four-tile corners at all four scales, fully remastered neighborhoods without a source-pixel grid, fine-grain preservation across join bands, hard material boundaries, mixed HD/original joins, overlay order independence, negative gutters, fractional scroll offsets, whole-tile rejection, palette masks, bounded cache memory, logical dimensions, native destruction settling and source-bound lazy loading of distinct intact/destroyed images. The row-aligned strip matches the previous joined SD viewport pixel-for-pixel at all 32 scroll phases, four scales, five interpolation values and negative row origins. Presentation work between simulation steps is compared against an untouched control for world state, RNG, damage and rewards.

Two additional original-data checks verified all 27 original missions and 4,217 distinct declared intact/destroyed terrain IDs are opaque 32×32 canvases, and produced a compositor comparison from the unregistered shoreline draft. The comparison is under ignored `.reference/terrain-hd/shoreline-draft-context-proof.png`: joined original Scale4x, the raw placement-specific HD draft, and the actual indexed HD composition. This corrected the visible grid found in an earlier source-color edge transition. A separate ignored release timing test exercises 72 visible HD placements with the 1280×816 gutter canvas. With the distance-aware grain correction, its 50 warm compositions measured 8.97 ms median and 10.46 ms p95; cold composition took 10.79 ms. The earlier edge-sample version measured 5.0/6.6 ms but stretched grain into ridges. These timings cover strip rebuilding only, excluding asset loading, SDL and the rest of the scene; normal cached scrolling reuses the prepared strip.

Independent review inspected all 66 pages of 1,706 actual neighbor, context and destruction-partner cases, plus seven focused original/pristine/previous/fixed panels. The fix removes repeated industrial and surface-grain ridges without new material, corner or pipe drift. The corpus checked 14,928 overlay applications and 175,134,720 palette-class pixels; a cached native scene averaged 1.63 ms per draw. Evidence is in `.reference/terrain-hd/join-ridge/` and `.reference/hd-full-review/terrain-ridge-final-independent.json`. Artwork acceptance and original-only destroyed-state fallback remain separate from this compositor review.

The completed strip cache was also measured in the real OpenGL SDL game with HD Stormwall terrain, enemies, projectiles, ship, shadows and HUD. Across 114 measured frames, 1280×800 presentation took 4.08 ms median and 9.86 ms p95 of game work, compared with 15.55/18.64 ms before strip reuse. Fullscreen 1920×1080 with aspect correction took 4.27/9.10 ms; total frame times were 5.86/9.28 ms. A separate cached original-mission `Host` scene averaged 2.97 ms across 60 draws. These local timings use a dummy audio output and describe this scene and machine, not every mission. Both SDL screenshots were inspected for clipping, coastline joins, low-resolution tile grids, foreground order and aspect presentation. Evidence is under `.reference/terrain-hd/stormwall-hd-prepared*.png` and the adjacent timing files.

Passing renderer tests makes the full catalog renderable; it does not count outstanding generation jobs as accepted artwork. Each supplied tile still needs source/HD review, every encountered neighboring edge and destroyed-state transition checked in real mission layouts, and live captures at the intended display size. Registration, decoded validity, visual acceptance and complete catalog coverage are separate statuses.

Canonical candidate review tooling uses an isolated manifest and the exact checked `HdAssets` loader, leaving the global manifest and coverage ledger untouched. The first 16-ID group, `terrain-10360-1036f`, produced all 48 source-layout contexts and 755 declared directional neighbor pairs: 170 HD/HD and 585 HD/original. The candidate has no declared destroyed partners. Its actual `Host` scene proof separately tests native destruction settling on a destructible placement, cached-versus-fresh equality at all 32 scroll phases and invalidation on changed mod order or content hash. Captures and JSON records are in `.reference/terrain-hd/terrain-10360-1036f/`. An independent reviewer inspected all context and pair sheets before artistic approval.

Use these ignored original-data checks for subsequent candidate groups:

```sh
RAPTOR_HD_TERRAIN_JOB=terrain-10360-1036f LD_LIBRARY_PATH=/home/quintine/.local/lib cargo test --locked --release --manifest-path RustRaptor/Cargo.toml --test hd_terrain canonical_terrain_candidate -- --ignored --nocapture
RAPTOR_HD_TERRAIN_JOB=terrain-10360-1036f LD_LIBRARY_PATH=/home/quintine/.local/lib cargo test --locked --release --manifest-path RustRaptor/Cargo.toml --lib canonical_terrain_live_scene -- --ignored --nocapture
```

The context/pair check is reusable for any complete canonical terrain candidate. The live scene check selects its first supplied source context and requires that original mission to contain destructible terrain. Successful execution verifies render reachability and consistency; it does not automatically approve generated artwork.
