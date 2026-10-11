# Optional HD artwork

The Rust Options screen includes **HD art**. It starts disabled. Enable it to use reviewed artwork from the selected data directory's `hd/hd.json`; each missing or rejected frame keeps the selected original / 2x / 3x / 4x crisp treatment. The bundled runtime uses `data/`, while development artwork and review jobs live under `../data/`. The scale setting still determines the indexed rendering resolution, and the HD toggle can be changed while paused. HD art is presentation only: simulation, collision sizes, banking positions and save content IDs stay unchanged.

The development base-game pack currently supplies **800 reviewed replacement frames in 340 complete sequences**. These include all twenty-one light, dark and firing-flash player poses, 223 boss frames, complete vehicle families, ground defenses and opening bunkers, all forty-seven equipment and pickup pictures, projectile and effect animations, eleven HUD picture glyphs, nine pilot portraits, both title logos, three standalone opening cards and 208 canonical terrain tiles. The tracked Linux/Windows playable snapshots now contain these800 reviewed frames, copied by the root assembler from the frozen handoff. Later development approvals remain separate from this runtime checkpoint. The complete catalog backlog and generation status are listed in [hd-backlog.md](hd-backlog.md).

| Reviewed artwork | Original asset IDs | Supplied / complete frames |
| --- | --- | ---: |
| Light player banking | `0x1011a`–`0x10120` | 7 / 7 |
| Dark player banking | `0x20045`–`0x2004b` | 7 / 7 |
| Firing-flash player banking | `0x2004c`–`0x20052` | 7 / 7 |
| First-mission fighter `SHIP01G1_PIC` | `0x102f8` | 1 / 1 |
| First-mission fighter `SHIP27G1_PIC` | `0x10330` | 1 / 1 |
| Fighters `SHIP02G1_PIC`, `SHIP14G1_PIC` | `0x102f9`, `0x1030a` | 2 / 2 |
| `SHIP03`, `SHIP06`, `SHIP13`, `SHIP24`, `SHIP26`, `SHIP28` craft | `0x102fa`, `0x102fd`, `0x10309`, `0x10327`, `0x1032f`, `0x10331` | 6 / 6 |
| `SHIP07` two-state craft | `0x102fe`–`0x102ff` | 2 / 2 |
| `SHIP08` moving tread phases | `0x10300`–`0x10303` | 4 / 4 |
| `SHIP09` hovercraft wake phases | `0x10304`–`0x10305` | 2 / 2 |
| `SHIP21` industrial platform wakes | `0x10317`–`0x10318` | 2 / 2 |
| `SHIP23` complete rotating craft | `0x1031f`–`0x10326` | 8 / 8 |
| `SHIP29`, `SHIP30`, `SHIP32`, `SHIP39` craft | `0x10332`, `0x10333`, `0x10335`, `0x10344` | 4 / 4 |
| `SHIP33` pod deployment | `0x10336`–`0x10339` | 4 / 4 |
| `SHIP34` orb light states | `0x1033a`–`0x1033b` | 2 / 2 |
| Orange rotor aircraft phases | `0x10311`–`0x10314` | 4 / 4 |
| Triple-cylinder and winged craft | `0x10334`, `0x1033d` | 2 / 2 |
| Yellow rotor aircraft phases | `0x10340`–`0x10343` | 4 / 4 |
| Dinosaur flight poses | `0x10328`–`0x1032d` | 6 / 6 |
| Restored fork-and-rail fighter | `0x10345` | 1 / 1 |
| TANK01 tread phases | `0x200c8`–`0x200cb` | 4 / 4 |
| TANK02 tread phases | `0x200cc`–`0x200cd` | 2 / 2 |
| Additional source-bound craft | `0x2009e`, `0x30049` | 2 / 2 |
| Corrected third-campaign boss | `0x30044` | 1 / 1 |
| First-mission industrial boss `SHIP10G1_PIC` | `0x10306` | 1 / 1 |
| Industrial bosses `SHIP12G1_PIC`, `SHIP17G1_PIC` | `0x10308`, `0x1030f` | 2 / 2 |
| Industrial boss `SHIP11G1_PIC` | `0x10307` | 1 / 1 |
| Industrial boss `SHIP16G1_PIC` | `0x1030e` | 1 / 1 |
| `SHIP22` complete hatch phases | `0x10319`–`0x1031e` | 6 / 6 |
| Second-campaign static bosses | `0x200a1`, `0x200ac`, `0x200ad`, `0x200eb` | 4 / 4 |
| Second-campaign four-phase boss | `0x200a8`–`0x200ab` | 4 / 4 |
| Second-campaign six-phase boss | `0x200ce`–`0x200d3` | 6 / 6 |
| Duo emergence phases | `0x20104`–`0x2010b` | 8 / 8 |
| Additional independently reviewed boss cohorts | Exact 56 complete families in the completion ledger | 189 / 189 accepted cohort frames |
| Ground-defense target `TARGT1G1_PIC` | `0x10138` | 1 / 1 |
| Ground-defense targets `TARGT2G1_PIC`, `TARGT3G1_PIC` | `0x10139`, `0x1013a` | 2 / 2 |
| Ground-defense target `TARGT5G1_PIC` | `0x1013c` | 1 / 1 |
| Opening ground-defense bunker `TARGT6G1_PIC` | `0x1013d`–`0x10141` | 5 / 5 |
| Opening ground-defense bunker `TARGT7G1_PIC` | `0x10142`–`0x10150` | 15 / 15 |
| Ground targets `TARGT4G1_PIC`, `TARGT9G1_PIC` | `0x1013b`, `0x10160` | 2 / 2 |
| Ground target `TARG10G1_PIC` | `0x10161` | 1 / 1 |
| Bonus crate `BONUS1G1_PIC` | `0x10151` | 1 / 1 |
| Second-campaign ground defenses | `0x20053`, `0x20054`, `0x20056`, `0x20057` | 4 / 4 |
| Second-campaign hatch-to-turret sequence | `0x2006f`–`0x2007b` | 13 / 13 |
| Jungle hatch-to-turret sequence | `0x20080`–`0x20087` | 8 / 8 |
| Intact and damaged ground turret variants | `0x2008d`, `0x20090`, `0x20093`, `0x20096` | 4 / 4 |
| Forward Guns equipment | `0x102b0` | 1 / 1 |
| Plasma Guns equipment | `0x102b1`–`0x102b2` | 2 / 2 |
| Dumb Missile equipment | `0x102b5` | 1 / 1 |
| Air Missile equipment | `0x102bf` | 1 / 1 |
| Micro Missile equipment | `0x102b3`–`0x102b4` | 2 / 2 |
| MiniGun equipment rotation | `0x102b6`–`0x102b9` | 4 / 4 |
| Turret equipment rotation | `0x102ba`–`0x102bd` | 4 / 4 |
| Ground Missile equipment | `0x102c0` | 1 / 1 |
| Energy Grab equipment phases | `0x102c1`–`0x102c4` | 4 / 4 |
| Pulse Cannon equipment phases | `0x102c6`–`0x102c7` | 2 / 2 |
| Forward Laser equipment phases | `0x102c8`–`0x102cb` | 4 / 4 |
| Missile Pods equipment | `0x102be` | 1 / 1 |
| Mega Bomb equipment | `0x102c5` | 1 / 1 |
| Super Shield pickup | `0x102d0` | 1 / 1 |
| Death Ray equipment phases | `0x102cc`–`0x102cf` | 4 / 4 |
| Energy pickup phases | `0x102d1`–`0x102d4` | 4 / 4 |
| Gold pickup flash phases | `0x102db`–`0x102de` | 4 / 4 |
| Detector and additional shop/pickup images | `0x102d5`–`0x102da` | 6 / 6 |
| Plasma projectile | `0x101cf`–`0x101d0` | 2 / 2 |
| Enemy cannon pulse | `0x101d6`–`0x101d7` | 2 / 2 |
| Dumb Missile projectile | `0x101ba`–`0x101bc` | 3 / 3 |
| Missile Pods / Air Missile 2 projectile | `0x101bd`–`0x101be` | 2 / 2 |
| Ground Missile 2 projectile | `0x101bf`–`0x101c0` | 2 / 2 |
| Forward Guns / MiniGun firing patterns | `0x101c3`–`0x101c6` | 4 / 4 |
| Mine pulse | `0x101d1`–`0x101d2` | 2 / 2 |
| Bomb and enemy missile projectiles | `0x101d3`–`0x101d5` | 3 / 3 |
| Pulse Cannon projectile phases | `0x10223`–`0x10224` | 2 / 2 |
| Death Ray projectile phases | `0x10231`–`0x10234` | 4 / 4 |
| Forward Laser projectile phases | `0x10235`–`0x10238` | 4 / 4 |
| Enemy coconut phases | `0x1024d`–`0x10250` | 4 / 4 |
| Energy Grab projectile phases | `0x1021d`–`0x10222` | 6 / 6 |
| Enemy laser projectile phases | `0x10241`–`0x10244` | 4 / 4 |
| Plasma projectile picture | `0x10251` | 1 / 1 |
| Energy ring | `0x101ae`–`0x101b9` | 12 / 12 |
| Blue sparks | `0x1019c`–`0x101a4` | 9 / 9 |
| Death-ray hits | `0x101f1`–`0x101f4` | 4 / 4 |
| Lightning growth/retraction | `0x1018e`–`0x1019b` | 14 / 14 |
| Platoon fragments | `0x10213`–`0x1021c` | 10 / 10 |
| Air blast | `0x102a0`–`0x102af` | 16 / 16 |
| Pickup glow light masks | `0x10225`–`0x10228` | 4 / 4 |
| Muzzle flash and casing phases | `0x101c7`–`0x101ca` | 4 / 4 |
| Small air explosion | `0x101fc`–`0x10209` | 14 / 14 |
| Enemy laser power phases | `0x10245`–`0x10248` | 4 / 4 |
| Pilot portraits, small and retained large variants | `0x10111`–`0x10119` | 9 / 9 |
| Original English and Chinese title logos | `0x10013`, `0x10014` | 2 / 2 |
| Apogee, Cygnus and Taiwan standalone cards | `0x1002b`, `0x1002d`, `0x1002f` | 3 / 3 |
| HUD number and symbol pictures | `0x10005`–`0x1000f` | 11 / 11 |
| SHIELDS LOW warning and classic opaque cursor | `0x10010`, `0x10012` | 2 / 2 |
| SYSTEM DAMAGED warning | `0x10011` | 1 / 1 |
| Bomb/shield counter pictures | `0x102df`–`0x102e0` | 2 / 2 |
| Slider and pointer pictures | `0x10127`–`0x10128` | 2 / 2 |
| Indicator, question and checkbox pictures | `0x1012a`–`0x1012e` | 5 / 5 |
| BUY/SELL and item buttons | `0x10130`–`0x10135` | 6 / 6 |
| Left/right double-chevron buttons | `0x10136`–`0x10137` | 2 / 2 |
| Canonical terrain set 1, first shard | `0x10360`–`0x1036f` | 16 / 16 |
| Canonical terrain set 2, corrected first shard | `0x2010d`–`0x2011c` | 16 / 16 |
| Canonical industrial terrain, first two shards | `0x300ed`–`0x3010c` | 32 / 32 |
| Soil, foliage, shadow and rubble terrain | `0x10390`–`0x103af` | 32 / 32 |
| Industrial, soil and canal terrain | `0x103b0`–`0x103cf` | 32 / 32 |
| Source coast, bridge and water terrain | `0x103e0`–`0x103ef` | 16 / 16 |
| Agricultural ground and vegetation | `0x2011d`–`0x2013c` | 32 / 32 |
| Fourth-campaign machinery and soil | `0x400d5`–`0x400f4` | 32 / 32 |

Every registered frame passed the exact original source hash, logical canvas, aspect, visible alpha and path checks. Complete contact sheets were inspected at source size and the 4× presentation size; per-frame geometry metrics and review evidence remain with each family. Their logical collision sizes are unchanged. Small contours and interpreted metal detail differ. Missing artwork keeps the crisp original fallback. HD remains an opt-in preview while the remaining catalog and game screenshots are reviewed.

An actual Rust `HdAssets::sprite` pass also checked all registered frames at scales 1–4 with the game palette: every output has the expected dimensions and visible pixels, and the pack reports no diagnostics. Complete 4× source/HD sheets from that runtime path were reviewed for readable projectiles, equipment alignment, banking progression and energy-ring timing stages. These sprite checks complement live gameplay captures and do not establish full-game visual completion.

The current 800-frame snapshot passed 3,200 actual scale checks. All 4,000 original and rendered PPMs are byte-identical to independently accepted references, with both source-age guards clear and the tested immutable library pinned by SHA and original build time. All 730 ordinary sources introduce no reserved palette labels; 67 sources retain legitimate gameplay classes, and the three opening cards use their authentic static palettes. Historical smaller-pack proofs remain separate.

The 189 additional boss frames passed complete source/1×/4× and native 2×/3× review across 56 full families. Opaque component panels, weapon apertures and source phases remain recognizable; fine material detail and minor contour interpretations are disclosed per family. These gallery decisions do not certify complete assembled-boss joins or native encounter placement. The shortened paired bottom feet in `0x200a2`, lost painted wing/strut cells in `0x30045`, Mole's missing initial blink, selected contracted hulls and the final EBOSS6 white-plate substitution remain held and are excluded.

The six corrected dinosaur poses preserve every native source occupied cell, bound and centroid, including the formerly lost dorsal, belly and tail points. They contain new painted detail at higher scales. The restored `0x10345` fighter retains its fork teeth and lower rails; ten very dark outer corner/foot cells remain an accepted contour interpretation. TANK01 has stable hull landmarks and distinct tread phases; three or four external corner cells per pose round inward at 1× while every source cell retains occupancy at 2×–4×. Minor stationary surface shading variance is disclosed.

All eleven HUD pictures retain their complete stroke layout and holes. Corrected N7's lower gold source cell becomes copper shading, with adjacent gold and the complete lower step still readable. The warning and cursor have source-bound gallery approval; the cursor retains opaque backing, all seventeen lit positions and the original index255 center. Corrected SYSTEM DAMAGED retains exact native stroke positions, holes and spacing. Counters, red indicator states, question and checkbox pictures, classic sliders/pointers, shop buttons and opposite double chevrons also have complete source/all-scale artwork approval. Their retained classic call sites do not establish reachability through the custom Rust menus. Native bitmap fonts keep their classic artwork.

The complete light banking sequence uses matching silver/gunmetal materials, dark red accents and the seven distinct original roll poses. Its safe square crop rectangles remove transparent canvas margin without excluding any pixel with alpha at least 32. Independent Rust `image::Lanczos3` checks use the runtime's two resampling stages, first to the resident 128×128 canvas and then to the original 32×32 logical size. All seven frames have source silhouette overlap of 87.7–92.3%, bounds within one logical pixel and centroid displacement below 0.74 logical pixels. Full-sequence visual review also checked the nose, canopies, wing ends and engine exits; numeric overlap alone does not approve a frame.

The first four equipment families' visible material masks overlap their originals by approximately 93–100%, and both Plasma icon frames share the same aligned alpha footprint. Their full alpha-mask overlap is lower, approximately 54–78%, because nearly black original opaque outlines become transparent around the detailed replacement. This difference is recorded separately from the visible metal silhouette. The ten newly added equipment/pickup frames have full logical-mask overlap of approximately 87.5–99.3%. Ground-defense originals and their replacements are fully opaque, which the source-aware loader accepts.

Small-scale differences remain visible. At 1×, each Plasma projectile loses one tail row: the original 8/6-pixel heights become 7/5 pixels, while 4× retains the original logical extents. The first energy effect's fine cardinal rays also contract under binary alpha at small scales; its 1× bounds become `(7,5)..(34,34)` against original `(3,2)..(38,37)`. At 4× the rays remain visible but end approximately 1–2 logical pixels inside the source extremes. Later rings use smoother, thinner contours. These differences affect presentation and are follow-up candidates for per-asset fallback; source collision dimensions remain unchanged.

Generated drafts are not active coverage. Earlier player atlas attempts and shortened extreme-bank variants were rejected. The complete light family replaces the initial straight-frame proof; the dark family uses coherent lighting edits of those reviewed poses and the original dark palette. Its exact runtime logical-mask overlap is 87.3–91.4%, with centroid displacement below 0.68 pixels, bounds within one pixel and no clipped meaningful alpha. The newly added Ground Missile, Turret, Pulse Cannon and Energy Grab families preserve their source phase differences. Late Energy Grab interprets two single-pixel peripheral ring holes as filled detail; the main transparent loop remains open. The full forty-seven-frame equipment/pickup category is now registered; the eleven HUD picture glyphs are also registered separately from the preserved fonts. A 3×3 shoreline prototype preserves the broad coastline and demonstrates the terrain renderer, but remains unregistered: repeated canonical tiles, neighbors and destroyed states need individual artwork and seam review. Original AGX cinematics retain their original artwork.

The firing family preserves all seven original poses and their localized amber reflections. Its distinct straight-frame contour points were checked explicitly: `(19,8)` remains opaque, `(11,12)` and `(11,13)` remain transparent, and `(11,14)` stays opaque. The MiniGun's four rotation phases and the seven newly registered missile phases passed complete sequence inspection; each missile retains its original exhaust length and fin layout. Native scene captures remain a separate reachability check. The additional `SHIP11G1_PIC` boss interprets its dark perimeter: logical alpha overlap is 82.9%, with 373 removed original occupied pixels (252 very dark) and 23 added pixels. Its towers, side machinery, center weapon and lower pods remain readable at every scale, but its alpha contour is not identical to the source.

The additional fifteen-frame bunker preserves its door apertures, gun and blink phases. Craft tread and hover-wake animations keep their distinct source poses and negative spaces. `SHIP13G1_PIC` has brighter detailed copper panels (mean occupied RGB about `64/47/42` becomes `82/58/52`); its original copper identity and asymmetric silhouette remain readable. `TARG10G1_PIC` uses a reviewed subdued soil correction; the superseded orange-speckled variants remain held.

The two additional ground targets use subdued brown soil corrections; their machinery and original directions remain intact. The tiny gun sprites keep all four original gray/white patterns, and the mine keeps its pink then dark burgundy center with gold corners. These families have complete gallery review; it does not establish a placed gun or mine scene occurrence. The short Death Ray and Forward Laser beams retain exact native top anchoring, three-row heights and phase widths. Forward Laser’s high-scale bottom antialias edge can end one presentation pixel inward (4× height eleven instead of twelve), while every logical footprint remains exact. The late Death Ray crops trim only weak alpha16–27 fringe and retain all alpha≥32 pixels.

The first sixteen canonical terrain replacements passed independent review of every source/logical/4× frame, all 48 supplied mission contexts and all 755 declared cardinal neighbor pairs: 170 HD/HD and 585 HD/original. Actual native scene checks exercised all 32 cached scroll phases and content-hash/load-order invalidation. None of these sixteen IDs has a declared destroyed partner; the separate native destruction-cache proof therefore adds no HD debris coverage. The additional corrected terrain family preserves the treeless `0x20111`, and the thirty-two industrial tiles preserve source roof, wall and pipe geometry. Their final compositor review covers all 66 full pages and 1,706 cases: 1,379 neighbor pairs, 234 contexts and 93 state swaps. A texture-preserving edge/corner correction removes the earlier repeating grain ridges without moving source material boundaries. These forty-eight frames are now registered. Mixed HD/original detail contrast remains visible, and foreign destroyed partners still use original fallback; their appearances in state tests do not add HD debris coverage.

The additional thirty-two terrain frames (`0x10390`–`0x103af`) preserve original grass/tree placement, cast-shadow polygons, pipe routes, rubble strips and destroyed structures. Complete independent review inspected all 61 context pages and 1,426 declared cases at scales 1–4, including the original `0x10395`/`0x10436` and `0x103ae`/`0x1045a`/`0x1045b` state relationships. The finer soil, leaves, rubble and metal texture is visibly denser than original fallback neighbors; no shifted pipe/coast, restored wreck, hole or new edge ridge was observed. Foreign partner artwork still uses original fallback.

The next thirty-two terrain frames (`0x103b0`–`0x103cf`) passed every source/native scale and all 39 current grain-fixed context boards. Their 120 cardinal pairs and 33 full 3×3 contexts produce 612 scale cases with no palette-class drift or overlay-order difference. Source pipe, roof, soil and canal joins remain aligned without recurring grain ribs. These IDs declare no state partners, so the review adds no destroyed-partner or new Host-scroll coverage. Unremastered neighbors keep original fallback.

The agricultural thirty-two tiles retain original field topology, planting directions/counts, canopy contours and shadow boundaries. All 469 cardinal joins and 91 native samples were independently viewed with 651 current composition cases. Fine grass rectangles against original fallback are accepted and disclosed; the historical Host invocation executable was not pinned, so it is not a new current Host claim. The first thirty-two fourth-campaign tiles passed 4,644 actual composition cases with all 86 native contexts, 31 declared states and 1,012 directed joins inspected. Five unique damage pairs have both HD partners; 21 directed state relationships retain original fallback. The sixteen `0x103e0`–`0x103ef` tiles passed every 64 current context board and 1,416 cases, including 27 original-partner center swaps. Nine destroyed partners remain original fallback.

Fifteen historical generation-provenance booleans across six opaque UI families were corrected from true to false using unchanged actual attempt records and saved request JSONs. Before/after byte streams and a coordinator verification journal are retained; candidate/source/raw/render bindings are unchanged. The cursor request was historically saved only as prompt text plus its same-execution attempt, and its missing request JSON is disclosed. No retrospective request history or new artwork was created.

The new rotor and hatch-to-turret families retain every original phase; the jungle leaves stay inside the source material region. Energy pickup trajectories retain all original opaque dark backing. Death Ray equipment keeps identical housing across its four light states, with four shared peripheral alpha additions disclosed. Its duplicate pale-gold phases and the gold flash duplicate medium phases use byte-identical source/raw/runtime aliases.

Four small pilot portraits (`0x10116`–`0x10119`) passed actual SDL main-menu SD/HD captures in the new 400×225 layout at logical position `(30,45)`. All eight captures and the comparison board were reviewed; their faces, equipment and slanted ID-card backgrounds stay recognizable, and every surrounding UI pixel was identical. The five large portraits and both title logos have complete gallery review but no verified active UI route. The Chinese logo legitimately uses 478 original fire-class pixels; its HD output preserves that class and adds no water or blink labels.

The newly reviewed effect families retain their complete phase ordering. Lightning branches are thinner and slightly cooler blue; the late AirBlast rim is thinner; PickupGlow uses a rounded interpreted contour rather than identical alpha. Actual `Canvas::shade` checks over original terrain confirm that pickup-mask holes preserve the background and mask RGB never paints foreground pixels. Other effects remain held where generation filled transparent holes, removed final fragments or made subdued smoke/embers too bright. A successfully decoded draft does not establish artistic approval.

Working originals, source references and generation/review drafts under `../data/` remain outside the repository. The bundled original catalog and approved HD runtime snapshot under this repository's `data/` are tracked in Git, as are the bundled game, libraries and runtime manifest. Authored mod packages include their generated SD/HD PNGs, sounds and provenance in Git. The new authored menu backdrop has its own packaged rendering path and is not counted as an original catalog sprite replacement.

The sources were decoded with `tools/hd_art_source.py`, inspected, and passed to the **built-in image_gen tool** using the imagegen skill. Sources, raw generations, prompts, contact sheets, frame metadata and review notes remain in local family folders (`enemies/`, `bosses/`, `effects/`, `equipment/`, `player-light/`, `player-dark/`, and `terrain/`). The superseded initial straight-player proof and its exact generation prompt remain saved locally at:

- `../data/hd/light-player-straight-hd-v1.png`
- `../data/hd/prompts/light-player-straight-v1.txt`
- `../data/hd/provenance.json`
- `../data/hd/source/light-player-straight.png`

That proof PNG has real alpha transparency, is 1254×1254, and was copied unchanged from the tool's output. Its logical silhouette overlap was 92.1%, but it is no longer mapped into the active pack because the complete family now has consistent materials across all seven poses. An earlier extreme-bank attempt remains at `../data/hd/light-player-bank-0-hd-v1.png` with `prompts/light-player-bank-0-v1.txt`; it is rejected because its footprint overlap is only 62.2% and its engine ends are shortened. Reviewed production frames and their crop metadata are in `../data/hd/player-light/`. The generated PNG bytes remain unchanged.

## Pack format

The following shows pack metadata; artwork paths resolve within the selected pack. The bundled approved pack and its artwork are tracked in `data/hd/`. This example shows one entry from the complete seven-frame light family. Decimal IDs are shown alongside their hexadecimal meaning.

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
          "frame": 0,
          "file": "player-light/frame-0-hd-v1.png",
          "logical_width": 32,
          "logical_height": 32,
          "origin": [0, 0],
          "crop": [30, 10, 1220, 1220],
          "source_sha256": "SHA-256 of the exact original 0x1011a catalog payload"
        }
      ]
    }
  ]
}
```

`base_asset` is `0x1011a`; the supplied frame targets `base_asset + frame`, so frames never depend on filenames or glob ordering. `frame_count` declares the whole original animation sequence and `frames` explicitly declares replacement coverage. An optional `crop: [x,y,width,height]` selects a rectangle from a PNG atlas or aligns a generated canvas by removing only transparent margin. The current pack supplies all seven light-player entries.

Version 1 requires exact original logical canvas dimensions and the original top-left anchor `[0,0]`. Canvas alignment is retained even when transparent margins surround the visible image. The PNG or crop must have the same aspect ratio as the original canvas and at least twice its logical resolution. The source hash prevents artwork silently matching a changed original asset. Original sprites with transparent negative space require transparent HD artwork; fully opaque originals may retain fully opaque replacements. Duplicate IDs, invalid sequence metadata, bad paths, crop bounds and unreasonable image allocations are rejected. Paths must remain inside the pack directory, including after symlink resolution. Open **D: details** from the main menu to inspect rejected frames and coverage.

The original picture header's two fields before width/height are `opt1` and `opt2`; they are not drawing origins. The audit records these as `header_options`. Replacement `origin: [0,0]` refers to the original canvas anchor and does not reinterpret those header options as sprite offsets.

The streaming runtime source-checks the complete manifest and validates each original generator-sized PNG/crop when used. It stores no more than the original logical canvas at 4× resolution, the highest supported presentation scale. Raw generated PNGs and provenance remain intact on disk. Three 32 MiB LRU caches hold decoded atlases, derived RGBA frames and palette-bound indexed sprites; eviction never removes a registered frame. A separate derived disk cache is capped at 512 MiB. The full catalog is no longer subject to a 128 MiB artwork admission limit. See [hd-streaming.md](hd-streaming.md) for validation ceilings, cache identities and corruption handling.

Original source locations also constrain palette classes: ordinary art uses indices 0–239, water stays in 240–244, fire in 245–249, and original blink/flash labels 250–255 remain exact. New HD coverage over an originally transparent location stays ordinary. Compact source-label metadata has a separate 32 MiB ceiling and is omitted for wholly ordinary sources. This prevents static metal or equipment highlights from acquiring fire cycles or blinking merely because a generated RGB value matches an animated palette entry. The accepted frames passed all-scale checks of these reserved-index counts. Static cinematic cards use a separate palette mode with all 256 colors; source references bind Apogee, Cygnus and Taiwan cards to their authentic palettes. The three complete source-bound HD still cards are now registered. Their original titles, tagline, Traditional Chinese glyphs and line breaks were compared at all four scales; stronger nebula, star and metal highlights are disclosed. The Taiwan card has no active opening cue, so its coverage is gallery-only. These standalone pictures are distinct from preserved AGX playback.

HD frames are resampled directly to the selected presentation canvas and quantized to the game palette. They bypass ScaleNx filtering, preserve transparent pixels and use the normal layer order. Indexed output allows palette effects to apply consistently; subtle RGB shades and alpha edges are reduced by the original palette and binary sprite transparency. The validated [terrain renderer](hd-terrain.md) overlays canonical, full-opaque HD tiles on the joined original layer. It shares HD edges and corners where source material classes agree, transitions HD/original boundaries over two logical pixels, and preserves water/fire/flash palette classes. Intact and destroyed IDs are independent targets. The renderer adds no remaster coverage by itself; each terrain family needs the same contextual review before registration.

The metadata-only [completion ledger](hd-completion.json) tracks every one of the 5,753 original picture IDs, including unused enemies, damaged variants, HUD graphics and unnamed terrain. It separates missing, in-progress, candidate, reviewed, registered and render-reachable stages. `tools/hd_job_queue.py` creates 674 disjoint picture jobs, plus 13 classic cinematic and four bitmap-font verification jobs. Original AGX artwork and sharp native glyphs have explicit preservation policies; they are never reported as AI remasters. The external `../data/hd/jobs/queues/` files assign continuous enemy, boss, equipment/UI, effect/projectile and terrain work with exact source hashes, complete animation families and neighbor/state references. Exact-payload aliases may share reviewed artwork while retaining each ID's source binding.

Workers can validate an isolated proposal with `python3 tools/hd_candidate_review.py --candidate ../data/hd/jobs/JOB_ID/candidate.json`. The helper hard-links raw artwork into a temporary pack, captures an immutable copy of the newest built Rust game library, and exports all scales 1–4 plus source/logical/4× contact sheets. The copy retains the exact original build timestamp and SHA-256; a concurrent Cargo rebuild cannot replace the tested artifact or make old code appear fresh. It records raw artwork hashes, library identity and build origin, rejects a changed snapshot, warns when asset-loader source is newer than the build, and pages large reviews in groups of sixteen frames to avoid an unbounded giant image. Admission rechecks the snapshot hash and source age. Every page listed in `runtime-contact-sheets.json` requires inspection. It never edits the active pack or generated pixels. A successful gallery still needs coordinator visual approval and separate scene/context evidence.

After explicit artistic and independent approval, the coordinator can run `python3 tools/hd_register_reviewed.py --job JOB_ID --dry-run`, then omit `--dry-run` to register the reviewed family. The command checks every original target, complete sequences, the exact approved frame bindings, all four runtime scales, the reviewed library and unchanged PNG hashes. Held artwork, stale evidence and duplicate registered IDs are rejected. It writes the complete manifest atomically and preserves provenance; registration does not claim a native scene occurrence or finish the catalog backlog.

Generation workers share a four-submission gate through `tools/hd_generation_gate.py`. They prepare references and save prompts before acquiring. One orchestration acquires, marks the request started, awaits built-in imagegen and reports its actual outcome immediately before returning to the model or doing local review. Started and legacy-unknown requests require explicit completion; only unstarted reservations expire. Status shows phases, ages and admissions, and supports owner recovery without cancelling tools. Connection failures retain exact sanitized text and UTC timestamps, impose a 60–600-second cooldown, and permit at most three connection failures per job in a thirty-minute retry batch. See the [mandatory workflow and wrapper](hd-generation-workflow.md). Logs and gate state remain ignored.

## Source and sequence review

Use the existing catalog decoder to prepare a transparent reference without redrawing it:

```sh
python3 tools/hd_art_source.py --asset 1011d \
  --output ../data/hd/source/light-player-straight.png --preview-scale 16
```

Inspect every source frame before generating its replacement. Request the same orthographic camera, silhouette, canvas placement, orientation, material colors and lighting for every frame. Preserve the generated alpha. Do not substitute rotations of one frame for the original bank poses: compare the complete sequence at its logical size and at the intended display resolution. Verify that the nose, engine exits, wing extremes and animation pivots remain aligned and that no clipping or background halos appear.

Keep image-generation prompts and provenance alongside the artwork. Never overwrite original catalog assets. The loader deliberately accepts partial coverage so a reviewed sprite can be previewed before the complete pack is ready, while preserving per-frame fallback.
