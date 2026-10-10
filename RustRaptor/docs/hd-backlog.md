# Original artwork HD backlog

The checked catalog contains **5,753 standalone picture frames**. The active local HD pack supplies **63**; **5,690** have no registered HD replacement. These counts include unnamed graphics outside `sprites/`. Scale2x/3x/4x filtering is crisp scaling, not a newly authored HD replacement. Authored mod SD/HD art is separate from this original-catalog audit.

| Category | Picture frames | Registered HD | Missing HD | Declared sequences / terrain sets |
| --- | ---: | ---: | ---: | ---: |
| Player banking | 21 | 14 | 7 | 3 |
| Bosses | 249 | 1 | 248 | 79 |
| Enemies and ground objects | 419 | 10 | 409 | 183 |
| Player and enemy projectiles | 51 | 4 | 47 | 18 |
| Explosions and effects | 281 | 12 | 269 | 25 |
| Equipment and pickups | 47 | 6 | 41 | 23 |
| Terrain | 4,535 | 16 | 4,519 | 4 |
| Menus, portraits, HUD and other pictures | 150 | 0 | 150 | mixed static / animated |

## Registered pack and generation jobs

Only registered frames passing canvas, source-hash, PNG and alpha checks count as registered HD. This is loader coverage, not proof that every original animation event is reachable in the current renderer. A generated image or successful still-image review does not complete an animated family. The optional pack remains disabled by default.

| Registered sequence | Asset base | Valid / complete frames |
| --- | --- | ---: |
| Light player banking | `0x1011a` | 7 / 7 |
| First mission industrial boss | `0x10306` | 1 / 1 |
| Plasma Guns projectile HD | `0x101cf` | 2 / 2 |
| Enemy cannon projectile HD | `0x101d6` | 2 / 2 |
| SHIP01G1 faithful HD remaster | `0x102f8` | 1 / 1 |
| Energy effect HD | `0x101ae` | 12 / 12 |
| SHIP27G1 faithful HD remaster | `0x10330` | 1 / 1 |
| Forward Guns equipment | `0x102b0` | 1 / 1 |
| Plasma Guns equipment | `0x102b1` | 2 / 2 |
| Dumb Missile equipment | `0x102b5` | 1 / 1 |
| Air Missile equipment | `0x102bf` | 1 / 1 |
| TARGT1G1 faithful HD remaster | `0x10138` | 1 / 1 |
| TARGT6G1_PIC | `0x1013d` | 5 / 5 |
| Dark player banking | `0x20045` | 7 / 7 |
| TARGT2G1_PIC | `0x10139` | 1 / 1 |
| TARGT3G1_PIC | `0x1013a` | 1 / 1 |
| Terrain 10360 | `0x10360` | 1 / 1 |
| Terrain 10361 | `0x10361` | 1 / 1 |
| Terrain 10362 | `0x10362` | 1 / 1 |
| Terrain 10363 | `0x10363` | 1 / 1 |
| Terrain 10364 | `0x10364` | 1 / 1 |
| Terrain 10365 | `0x10365` | 1 / 1 |
| Terrain 10366 | `0x10366` | 1 / 1 |
| Terrain 10367 | `0x10367` | 1 / 1 |
| Terrain 10368 | `0x10368` | 1 / 1 |
| Terrain 10369 | `0x10369` | 1 / 1 |
| Terrain 1036a | `0x1036a` | 1 / 1 |
| Terrain 1036b | `0x1036b` | 1 / 1 |
| Terrain 1036c | `0x1036c` | 1 / 1 |
| Terrain 1036d | `0x1036d` | 1 / 1 |
| Terrain 1036e | `0x1036e` | 1 / 1 |
| Terrain 1036f | `0x1036f` | 1 / 1 |
| Super Shield pickup | `0x102d0` | 1 / 1 |

| Generation job | Status |
| --- | --- |
| Light player banking, 7 poses | Complete 7-pose family registered after source and full-sequence review and exact Rust resident 4× → logical QA; earlier failed drafts stay unregistered. |
| Dark player banking, 7 poses | Complete coherent seven-frame family registered after actual Rust source/logical/indexed4× review. Earlier independent drafts remain rejected. |
| Firing-flash player, 7 poses | Awaiting a complete coherent family; the straight firing-flash pose has a distinct source alpha mask and needs separate review. |
| First mission enemies and boss | Boss, two common fighters and opaque ground-defense target complete and registered. |
| Projectiles and effects | Plasma 2, enemy cannon 2 and energy ring 12 frames complete and registered; other originals retain crisp fallback. |
| Equipment and pickups | Forward Guns 1, Plasma 2, Dumb Missile 1 and Air Missile 1 frames complete and registered; other originals retain crisp fallback. |
| Terrain shoreline | Contextual 3×3 prototype remains unregistered. Canonical terrain renderer and ten portable checks pass; all reusable tile IDs, neighbors and intact/destroyed states still require generated artwork review. |
| Menu background | Separate authored background job and menu renderer integration; not part of original sprite HD manifest. |
| Original cinematic artwork | Original AGX sequences retained; no HD cinematic replacement registered. |
| First canonical terrain shard,16 IDs | Registered after all48 actualcontexts,755cardinalpairs and32native scrollphases; independent review passes. No IDhas a destroyedpartner; this adds no HD debris coverage. |

The catalog also contains **303 AGX cinematic delta frames in 13 sequences** and **4 bitmap fonts**. These have explicit native-art preservation policies: keep the classic cinematics and sharp original glyphs, validate complete playback/alignment, and never count them as generated HD replacements. The AGX frames are separate from standalone pictures.

## Sequence priorities

1. Keep all light/dark-player banking poses and firing-flash poses coherent as complete families. Preserve the exact firing-flash source mask, which differs from the light/dark mask for the straight pose.
2. Ground defenses, airborne enemies and complete boss animation sequences; share palettes and the original logical canvases, rather than treating each enemy frame as an unrelated illustration.
3. Original projectiles and pickup/equipment animations. Tiny projectiles need careful readability checks; per-asset nearest fallback remains temporary until a clean remaster passes review.
4. Explosions, flame/spark sequences and other effects. Check full animation timing, transparency and palette cycling, not only a still image.
5. All four terrain sets, including unnamed catalog tiles. Generate with neighboring context and verify joined seams before changing runtime coverage.
6. Every original menu background, portrait, HUD and retained unused picture. Gameplay UI text and button labels must remain readable and match their actions. Verify the preserved native cinematic/font paths separately.

## Reproduce the audit

```sh
python3 tools/hd_art_audit.py --data ../data \
  --json ../data/hd/coverage-audit.json --markdown docs/hd-backlog.md
python3 tools/hd_job_queue.py --data ../data
```

The JSON gives every picture's asset ID, path, logical dimensions, original header options, source hash and HD status, plus each declared animation/set. The [completion ledger](hd-completion.json) records every required picture and native-art verification target, including complete families, ownership and candidate/review/registration stages. Both contain metadata only. Original and original-derived artwork remains outside Git.

Folder totals: `sprites/`: 985, `tiles/`: 232, `misc/`: 4,536. These folders are not semantic categories; terrain and other pictures also live in `misc/`.

## Secondary effect coverage

Native animation registrations, pickup masks and beam impact/power companion arrays contribute 281 distinct effect frames. The 25 declared ranges include one five-frame descending-smoke subset of the nine-frame smoke family, leaving 24 complete families. This includes muzzle flashes/casings, laser impacts, smoke trails, lightning, sparks and the super-shield glow as well as explosions. Pickup glow uses indexed light-table mask semantics and needs a different HD treatment from an ordinary color sprite. These assets are not UI artwork merely because they are absent from the content registries. Renderer event reachability needs its own check before claiming complete gameplay effect coverage.

## Runtime reachability and duplicate artwork

The terrain backlog contains **4,524 distinct payload hashes** and **4,524 distinct decoded images** across 4,535 catalog IDs. Duplicate IDs can share the same reviewed treatment; they still require explicit source-bound metadata. The canonical HD terrain renderer is validated: intact/destroyed source-bound tiles, shared HD edge/corner treatment and palette-class preservation are implemented. This adds no artwork coverage; each generated tile still requires its own contextual seam review.

The Python inventory matches the Rust decoder's complete picture ID and logical-dimension inventory. The shipped **27 missions** reference **512 of 528 enemy definitions**, which reduce to **260 of 262 distinct art sequences**, and **4,217 terrain frames**, including destroyed variants. Enemy names may alias the same artwork; the category table counts each asset ID once and the sequence count deduplicates identical base/frame ranges.
