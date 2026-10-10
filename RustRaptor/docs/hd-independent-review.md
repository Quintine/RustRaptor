# Independent review of original HD artwork

Reviewed on 2026-10-10 against the original loose catalog, native artwork references, a fresh Rust decoder/HD-loader probe, and the registered pack. This review was performed separately from the artwork generation and registration jobs.

The original catalog inventory is complete. **The remaster is still partial:** the reviewed snapshot has 32 registered replacements out of 5,753 standalone pictures. All 32 load successfully and produce visible, correctly sized indexed sprites at presentation scales 1–4. No blocking clipping, background, source-hash or banking-order defect was found in those registered frames. This does not establish full-game visual parity or approve the unregistered drafts.

## Independent evidence

Every one of the 6,449 catalog entries passed its recorded byte-size check. A separate strict Python decoder, which does not import the existing artwork audit or source decoder, produced exactly the same picture IDs, dimensions and indexed pixels as a fresh Rust `Sprite::decode` pass. This verified all 5,753 standalone pictures, including **4,768 outside `sprites/`**: 232 in `tiles/` and 4,536 in `misc/`.

The fresh Rust probe also decoded and applied all **303 AGX delta frames across 13 streams**, checked the active HD pack with no diagnostics, and requested each registered frame at all four scales. Four bitmap fonts were inventoried separately. Their glyphs should retain sharp indexed scaling; cinematic delta streams require a dedicated treatment rather than ordinary sprite registration.

Original source SHA-256 hashes, logical dimensions and replacement anchors match every registered frame. All active player crop rectangles exclude **zero pixels with alpha at least 32**. The complete runtime sheets were inspected for light-player banking, the boss, two fighters and ground target, equipment, projectiles, and every energy-ring frame.

Local evidence is saved under `.reference/hd-independent-review/`: `runtime_probe.rs`, `runtime.json`, `audit.py` and `report.json`. The report records per-frame hashes, silhouettes, visible bounds and scale-specific results. It is ignored alongside the original assets. The reviewed manifest SHA-256 is `b75330698a7baac975988cc206f040e1addbe1bb873a210e032a343c78a9e582`; later registered families require another review.

## Coverage and omissions

The category correction below includes gameplay artwork that the earlier generation backlog had incorrectly grouped under UI/misc. The overall picture inventory was already complete; these were omissions from the dedicated animation job list.

| Original category | Picture frames | Registered HD in this snapshot | Remaining |
| --- | ---: | ---: | ---: |
| Player banking and firing flash | 21 | 7 | 14 |
| Bosses | 249 | 1 | 248 |
| Enemies and ground objects referenced by sprite libraries | 419 | 3 | 416 |
| Main player/enemy projectile sprites | 51 | 4 | 47 |
| Explosions, smoke, sparks, glows and beam companions | 281 | 12 | 269 |
| Equipment and pickups | 47 | 5 | 42 |
| Terrain | 4,535 | 0 | 4,535 |
| Menus, portraits, HUD and other retained pictures | 150 | 0 | 150 |
| **Total standalone pictures** | **5,753** | **32** | **5,721** |

Native animation registration and direct rendering references revealed **77 gameplay effect frames** missing from the explicit effect sequence backlog:

| Family | Original asset range / count | Original reference |
| --- | --- | --- |
| Laser impact | `0x10229`, 4 | `anims.cpp` |
| Small smoke | `0x1020a`, 9 | `anims.cpp`; descending smoke reuses the last 5 |
| Smoke trail | `0x1022d`, 4 | `anims.cpp` |
| Lightning / energy grab | `0x1018e`, 14 | `anims.cpp`; two animation handles share these frames |
| Blue sparks | `0x1019c`, 9 | `anims.cpp` |
| Orange sparks | `0x101a5`, 9 | `anims.cpp` |
| Gun/casing streaks | `0x101c7`, 4 | `anims.cpp`; muzzle and ejected-casing handles share them |
| Super-shield glow | `0x10249`, 4 | `anims.cpp` |
| Death Ray power | `0x10239`, 4 | `shots.cpp` |
| Laser power | `0x1023d`, 4 | `shots.cpp` |
| Beam impact | `0x101f1`, 4 | `shots.cpp` / `eshot.cpp` |
| Enemy laser power | `0x10245`, 4 | `eshot.cpp` |
| Pickup light mask | `0x10225`, 4 | `bonus.cpp` |

These ranges are counted once despite shared handles and overlapping smoke subsets. The coordinator has incorporated them into the maintained backlog. Pickup glow, descending smoke and super-shield masks use palette-table shading in the original renderer; a colored RGBA replacement alone does not reproduce their operation. The lightning family uses ordinary indexed sprite drawing.

The four native sprite libraries contain 528 enemy records sharing 262 art sequences and 668 picture frames. The 27 original mission layouts reference 512 records and 260 sequences. Static fighters do not represent the remaining animated bosses, ground targets or directional variants. An additional 33 enemy-shaped pictures remain in the retained miscellaneous inventory: the three unused eight-frame `WORMDN`, `WORMRITE` and `WORMLEFT` families, and nine `DSHP` pictures. No references to those pictures were found in the native sprite libraries or rendering code; retain their catalog entries and identify them explicitly before any cleanup.

The original `SPACE_AGX` stream contains 22 of the 303 cinematic frames and has no playback reference in the current native source. It remains cataloged and decodable. The classic intro, landing, death and campaign-ending streams remain original artwork; the new authored menu background is a separate packaged asset, not HD coverage for the original logo/menu/portrait pictures.

## Registered artwork quality

All seven light-player bank poses remain distinct, progress in the original order and keep coherent silver/gunmetal materials and red markings. The independent logical masks match the recorded 87.7–92.3% silhouette overlap. The nose, canopy, wing ends and engine exits remain visible; maximum logical bound difference is one pixel. The original mask still determines collision dimensions and shadow geometry. The dark-sector `DPLAYER` and firing-flash `FPLAYER` seven-frame families are not registered in this snapshot. The straight firing-flash frame has a different source mask and must receive separate review, even when other poses can reuse lighting edits.

The first industrial boss, two fighters and opaque ground target preserve their source orientation and canvas. The boss's interpreted metal machinery and both fighters' finer contours differ from the source. Neither their static-frame approval nor their shared palette establishes completion of other enemy/boss families.

Equipment retains readable visible metal geometry and the two Plasma icon frames remain aligned. The remaster removes nearly black opaque source outlines around the equipment. Consequently full alpha-mask overlap is only about 54–78%, while the separately measured visible-material masks have approximately 93–100% overlap. Both measurements should remain visible in provenance; the material result must not be reported as identical source transparency.

Small-scale resampling has two documented differences. At 1×, the Plasma projectile loses one tail row (original heights 8/6 visible pixels become 7/5); 4× retains its original logical extent. The first energy flash becomes narrower at 1×, with source bounds `[3,2,38,37]` becoming `[7,5,34,34]`; at 4× its bounds are approximately `[4.75,3.25,36.5,35.75]` in logical units. The later energy rings are smoother and thinner, so silhouette overlap alone is not a useful acceptance gate. These are presentation differences rather than discarded PNG crop pixels. Check the 1× option in motion and retain a crisp fallback if the shorter flash or projectile reduces readability.

## Remaining rendering and integration checks

The review found routing gaps that are independent of generation quality. The original equipped-weapon HUD path uses the raw catalog sprite, so registered base equipment HD is bypassed there even though the shop and pickups can use it. Native HUD digits, bomb/shield icons and warning labels also use an intentionally crisp path. New HD portraits already have an appropriate optional route, but no portrait replacements are registered.

The native beam renderer repeats the main laser sprite along its full line and draws power/impact companion frames. The reviewed Rust projectile path draws the main original projectile sprite without that native composite. Similarly, the current `EffectKind` models the eleven explosion/effect families, but the additional smoke, sparks, muzzle/casing, lightning and glow events found above have no corresponding original-art effect path in that snapshot. Registering their HD PNGs would not by itself make those native visual events appear. Restore and screenshot the original composition/event paths before claiming complete visual fidelity, then review their HD replacements against that output.

Terrain has four sets of 672, 1,437, 1,082 and 1,344 pictures. They contain 4,524 unique original payloads and decoded indexed images. The original missions require **3,483 intact frame IDs and 736 destroyed frame IDs**, a union of 4,217; **734 are destroyed-only** and therefore absent from an intact-map screenshot. There are 889 destructible intact frames. Those destruction states belong in the remaster jobs and seam tests.

The reviewed 3×3 shoreline draft is continuous internally and preserves the broad coast, but nine placements contain only six distinct original tile IDs. The generated copies of a repeated tile are not guaranteed identical. It cannot safely be split into global per-ID replacements without a reusable edge contract or context-aware terrain chunks. External neighbors, alternate placements, destroyed states, scrolling offsets and palette cycling remain unverified, and native terrain currently lacks a catalog-HD composition route. The terrain draft remains correctly unregistered.

Before wider opt-in release, prioritize complete dark/firing player families, the original effect/beam routing gaps, representative remaining animated enemy and boss sequences, and context-aware terrain including destroyed variants. Follow that with remaining equipment/projectiles, original portraits/HUD/logo assets where retained, and a separately approved cinematic treatment. Keep the complete ID inventory as the completion checklist; filenames, a single mission screenshot and the number of generated PNGs are insufficient coverage measures.

## Follow-up after this snapshot

The engine now restores native beam composition and secondary visual events, routes optional HD artwork through HUD pictures and indexed light masks, and composes canonical source-bound HD terrain with neighboring context and a bounded scrolling strip. The complete dark-player family has also passed review. These corrections do not complete the remaster: all 5,753 picture IDs remain required, including unused original pictures and destroyed terrain. The ongoing [complete-original review](hd-full-review.md) records subsequent exact manifest hashes, complete-family approvals and held corrections; the [completion ledger](hd-completion.json) is the current per-ID checklist. Classic original cinematics and sharp bitmap fonts keep their explicit preservation policies.
