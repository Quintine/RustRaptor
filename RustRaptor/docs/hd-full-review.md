# Complete-original HD review

Independent review started **2026-10-10**. This is an ongoing acceptance record, separate from the generation jobs and registration coordinator. Full completion requires all **5,753 standalone source picture IDs** to have reviewed, registered remasters and their retained rendering paths to work. Candidate images, queue entries, original fallback and a successful PNG decode do not establish completion.

## Inventory checked independently

A strict picture decoder read every one of the 6,449 original catalog entries and checked the recorded byte lengths. Its 5,753 picture IDs, source SHA-256 hashes and logical canvases match the maintained completion ledger and the previous independent Rust pixel audit. **4,768 pictures are outside `sprites/`.** Every picture has `remaster_required: true`; no unused enemy, directional, terrain or miscellaneous picture has been excluded.

The disjoint queues contain 659 jobs and 5,714 source targets in this snapshot. Their union with the 46 registered pictures covers all 5,753 IDs exactly; seven registered dark-player pictures remain in their frozen queue. Every job target's source hash and canvas match the independent inventory. The original unused WORM direction and DSHP picture families remain explicitly required.

All 4,535 terrain pictures remain required, including the 734 destroyed-only IDs absent from intact-map screenshots. Original missions reference 3,483 intact and 736 destroyed IDs, a union of 4,217. The complete target inventory includes the terrain pictures not referenced by those missions.

The **303 AGX delta frames** and **four bitmap fonts** have explicit preservation policies: classic original cinematics and sharply scaled native glyphs. These exceptions are separate from picture coverage and are never counted as HD replacements.

Snapshot ledger SHA-256: `3b024a1a1dd342afabfb0f3829f1933769869f6a8798059826e796b3f7e34fb4`. The ignored evidence is `.reference/hd-full-review/inventory.json`; later ledger updates need a fresh snapshot rather than treating this dated count as current.

## Registered pack reviewed

Manifest SHA-256 `aa2b823acce157f0b49ee2f44bad133cefeca0304905038f004b59b4b6c22835` supplies **46 frames in 16 complete families**. The actual Rust loader decoded each at all four presentation scales, producing 184 correctly sized indexed sprites with no diagnostics. Every source hash, logical canvas and zero origin passed. All seven source/1×/4× contact pages and six separate native-resolution 2×/3× pages were inspected, including every bank pose and every animation frame.

| Reviewed family | Original IDs | Frames | Assessment |
| --- | --- | ---: | --- |
| Light player banking | `1011a–10120` | 7 | Bank ordering, materials, canopy, wing tips and engines remain readable. |
| Dark player banking | `20045–2004b` | 7 | Distinct dark lighting preserves the approved bank geometry and canvas. |
| Ground targets TARGT1/2/3 | `10138–1013a` | 3 | Source orientation and centered mechanism preserved; full opaque canvases intentional. |
| Ground target TARGT6 | `1013d–10141` | 5 | Complete opening/firing sequence aligned on the same square structure. |
| Fighters SHIP01G1 / SHIP27G1 | `102f8`, `10330` | 2 | Source directions, canopy and gunmetal/blue or neutral material cues retained. |
| Industrial boss | `10306` | 1 | Full source footprint and left/right machinery retained. |
| Plasma and enemy-cannon projectiles | `101cf–101d0`, `101d6–101d7` | 4 | Readable indexed projectiles; Plasma's known 1× tail shortening remains documented. |
| Energy flash/rings | `101ae–101b9` | 12 | Complete expansion sequence aligned; known narrower first flash and thin rings remain documented. |
| Forward, Plasma, Dumb Missile, Air Missile equipment | `102b0–102b2`, `102b5`, `102bf` | 5 | Logical inventory canvases retained; loss of original dark opaque outlines remains documented rather than called identical transparency. |

This pack is **partial: 5,707 required pictures still have no registered remaster in this snapshot**. Static fighter approval does not cover other old enemies, bosses, directional variants or terrain. A generated menu background does not count as remastering the original portraits, HUD and retained menu pictures.

Evidence: `.reference/hd-full-review/snapshot-aa2b823a/` contains the exact manifest snapshot, fresh actual Rust 1×–4× indexed outputs, `runtime-qa.json` and every contact-sheet page. The loader library is current for asset decoding and HD loading. Desktop rendering changed after that library was built, so this gallery does not establish those newer runtime routes.

A subsequent registered snapshot, **63 frames**, has manifest SHA-256 `33ec0a782a852ffef36880432d3e8d472f18a39e9a31d545fe47eb0256bb0dfd`. Fresh actual Rust validation passes all 252 scale outputs without diagnostics. Every prior 46 frame's indexed output is byte-identical to the previous reviewed snapshot; the 16 canonical terrain frames and Super Shield pickup match their independently reviewed isolated outputs. The newly added terrain's native 2× and 3× outputs were also inspected. The picture inventory still has **5,690 unregistered targets** at this snapshot. Evidence: `.reference/hd-full-review/snapshot-33ec0a78/review-comparison.json`.

**Palette animation defect found and corrected:** static equipment highlights can select native cycling/fire/flash indices 240–255 despite their original source having none. The PNG source and shape can be valid while the runtime asset flashes unintentionally. The coordinator reported this in Micro Missile/Missile Pods/Mega Bomb candidates and requested an engine correction. Independent pre-fix review found 24 of 63 registered pictures affected across 86 scale outputs. Source-bound palette classes now constrain ordinary art to indices 0–239, water/fire to their own cycling group, and flash masks to exact original labels. Fresh independent post-fix galleries pass **all 63 registered pictures and ten additional equipment frames at scales 1–4 (292 outputs)** with no newly introduced dynamic index. All 24 changed registered frames and all ten equipment frames were visually re-inspected without a shape or readability regression. Evidence: `.reference/hd-full-review/snapshot-63-palette-audit-fixed/` and `equipment-palette-fixed/`.

## Isolated candidate reviews

| Candidate | Candidate JSON SHA-256 | Actual Rust outputs | Status |
| --- | --- | ---: | --- |
| Terrain `10360–1036f` | `ad6062f325e730bdb71d22190ff1589f5d86f6c69c62ed94e8caacfdd9ce955c` | 16 × four scales | All source/1×/4× rows inspected; 48 contexts, 755 cardinal pairs and four native scene captures independently pass. Approved for partial-pack registration. |
| Terrain `2010d–2011c` | `74d3a5e8cc32569c849c8baeee3a47d7c265e238c5d00b5f84a98a52198e8527` | 16 × four scales | Held: `20111` invents a tree canopy absent from source. |
| TARGT5 v2 `1013c` | `e7af1db9fb30f995eaf2c2c360f86c952401bac874087b4f4c462487a9e9ca8a` | One × four scales | Structure preserved and prior orange speckles removed; darker soil needs neighbor review. |
| TARG10 v1 `10161` | `44a2720e6b6164cb96888a024b5fc068c4abe6e331cff54e3389c721890c4eb4` | One × four scales | Cannon pose preserved; orange border speckles and soil color need correction or contextual approval. |
| Super Shield pickup `102d0` | `adf4b4823aee9bade62b755b170bc0393b73d84c02653e51827109016b3d97ea` | One × four scales | Independently approved; golden S glyph, pointed silhouette, transparency and source canvas preserved. |

All five isolated packs passed source hash, canvas, origin, PNG/crop and nonempty indexed validation without diagnostics. That result does not approve their artistry. TARGT5's outer three logical pixels change from source mean RGB 124/76/63 to indexed 1× 74/32/28. TARG10 changes from 104/65/55 to 4× 92/40/30 and introduces bright orange border pixels (1.63% of that band; source zero). These measurements explain the requested ground-neighbor check; they are not universal numeric art gates.

Evidence is under `.reference/hd-full-review/terrain-10360-1036f/`, `terrain-2010d-2011c/`, `held-targt5/`, `held-targ10/` and `equipment-102d0/`. Only source inspection and preview extraction were performed; no candidate pixels or global registration were changed.

## First terrain family's contextual acceptance

Candidate `10360–1036f` passed independent inspection of all **48 actual 3×3 contexts** and all **755 cardinal pairs** across 24 review pages: 170 HD/HD joins and 585 HD/original joins. Trees, dirt/grass boundaries, adjoining native coastlines, roads, structures and existing destroyed neighbors keep their source arrangement. No tile hole, crossing-material leakage or low-resolution interior edge grid was found. Texture contrast at the temporary HD/original boundary remains visible, so this approval is for the current partial pack and does not establish finished full-map consistency.

Four actual native scene captures show phase 0, phase 31, intact terrain and settled destruction. The engineer's runtime assertions compare cached and fresh composition at every one of 32 scroll phases, preserve simulation/pilot/script/RNG state across draw calls, and invalidate the prepared layer after mod hash or load-order changes. The original debug-profile isolated warmed scene averaged 2.97 ms with a 2.76 MiB retained strip and 2 MiB transition lookup. These scene results are distinct from the PNG gallery check.

This family has **no declared destroyed-state partners**. Its destruction capture exercises another native tile's intact/settled cache transition; it does not approve generated HD debris. Those 734 destroyed-only targets remain required in their own jobs.

Runtime proof SHA-256: `c00e11d26e2a49a6b0f2e156581a7a7b1fc217f922a34e6b70ed7dbd5b95a0de`. Independent evidence is `.reference/hd-full-review/terrain-10360-1036f/context-review.json`, its 24 cardinal pages and three 48-context contact parts. Original native captures are under `.reference/terrain-hd/terrain-10360-1036f/`.

## Runtime routes and remaining gates

The former original beam/effect routing gaps have dedicated native composition paths. Beam shafts, muzzle/power/impact companions and secondary smoke/sparks/glows preserve original frame IDs and original anchors. Original shadows deliberately retain the original logical masks and collision dimensions.

Code review of the newly extended HUD, timed currency pickup and light-mask routes confirms they request HD frames at the presentation scale while retaining source logical placement. Light masks call indexed `Canvas::shade` instead of painting RGBA colors. Generic HUD assets keep nearest-neighbor source fallback; bitmap font text remains sharply scaled. Focused runtime fixtures now pass at **1× and 4×**: generic HUD and equipped-weapon icons use supplied HD pixels at the original logical anchor; a sparse red RGBA shield replacement uses its own alpha holes and transforms background index **37→44** through the light table rather than painting its red foreground. World/pilot state remains unchanged. The broader 13 original-rendering checks also pass. A dedicated full `Host::scene` currency fixture now passes at 1×/4× and interpolation α=0/0.5: synthetic native `N$_PIC` stays green in SD while supplied red/blue HD halves appear at the interpolated source anchor, with every pickup pixel and its surrounding black border checked. At 4× the half-step anchor is `(246,410)`. World digest, RNG, pickup countdown/previous-art-position/glow-frame, pilot and clock state remain unchanged; no HD diagnostic appears. This proves route behavior separately from artistic acceptance; no currency remaster is approved by that synthetic test.

Canonical terrain candidate review and actual terrain composition checks are ongoing. Fresh isolated Rust review decoded all 32 tiles in the first two groups at scales 1–4 without diagnostics; all eight paged source/1×/4× contact sheets were inspected. The first group (`10360–1036f`) keeps the broad tree/grass/dirt placements. The second group is held for the concrete source drift below. Every candidate tile requires independent source geometry review plus neighboring placements, mixed HD/original joins, destroyed states and scroll phases. Opaque alpha-mask overlap alone is trivial and is not an artistic quality gate. Rendering test success adds no artwork coverage.

## Open findings

- Full art generation and registration are unfinished; preserve the per-ID checklist through every cohort.
- Generic HD palette quantization is corrected and independently passes all current supplied frames at scales 1–4. Preserve this source-class gate for every future family.
- Firing-player frames require separate source-contour review, especially straight frame `2004f`; the dark/light banking review does not approve that sequence.
- Generic HUD, lighting-mask and timed-currency routes now pass supplied-art runtime fixtures at 1×/4×, preserving indexed shading and original/interpolated anchors. Review their actual generated artwork separately when candidates arrive.
- **Hold terrain `2010d–2011c`: picture `20111` invents a tree canopy.** Its original palette contains olive grass and brown dirt only; the remaster adds a bright green canopy at the upper-left covering about 15% of logical pixels. The source hash and opaque alpha-mask overlap pass, demonstrating why those checks do not establish source geometry. Regenerate that picture with the original grass/dirt arrangement before approving the family. Coordinator, artist and terrain engineer were notified. Proof: `.reference/hd-full-review/terrain-2010d-2011c/runtime-contact-sheet-002.png` and `20111-original-enlarged.png`.
- First canonical terrain group `10360–1036f` is independently approved; complete the corrected second group contextual review before registration.

This record will be extended as new complete families arrive. Original-derived artwork and review renders remain in ignored `data/` and `.reference/`; authored mod artwork and sounds remain Git-tracked under `RustRaptor/mods/`.
