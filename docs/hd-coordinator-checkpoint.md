# HD coordinator checkpoint — 11 October 2026

The reviewed development pack is **441 original picture frames in 179 complete sequences**. The tracked playable snapshot at commit `26ed9cc` contains **340**; only the root assembler refreshes `data/`, `bin/`, `lib/` and `runtime-manifest.json`. Working artwork, prompts and review jobs remain in external `../data/hd/`. These two snapshots are intentional and must not be confused.

## Verified development coverage

| Category | Registered / original pictures |
| --- | ---: |
| Player banking and firing | 21 / 21 |
| Bosses | 33 / 249 |
| Enemies and ground objects | 105 / 419 |
| Projectiles | 34 / 51 |
| Effects | 91 / 281 |
| Equipment and pickups | 47 / 47 |
| Terrain | 96 / 4,535 |
| Menus, portraits, HUD and other pictures | 14 / 150 |
| Total | 441 / 5,753 |

The complete ledger includes all unused and damaged picture IDs. No picture is excluded because it lacks a current runtime occurrence. The 303 AGX delta frames and four bitmap fonts have explicit classic-art preservation policies; they are not counted as generated HD replacements.

The current audit has no source/hash/canvas/ID errors. The ledger records 421 registered, 20 render-reachable, 1,266 candidate, 1,213 in-progress and 2,833 missing pictures. Candidate status establishes neither artistic acceptance nor native scene coverage. The resulting 5,312-picture HD backlog remains active.

## Exact runtime evidence

`../data/hd/registered-class-review/runtime-441-current/combined-review.json` verifies all **1,764 actual scale outputs** and **2,205 original/scaled PPMs** against independently accepted images byte for byte. All complete new families had separate coordinator original/1×/4× inspection and independent native 2×/3× review before admission. Loader diagnostics are empty, and both source-age guards passed.

The tested immutable library is `target/hd-review-libraries/bc54cb791cb6c17ae65e651491af51831ee9fef33d78000df9904a98c8279876/libraptor_replica-79676ac8bb9ed60d.rlib`, original build timestamp `1791697513165136322`. Its filename, bytes, SHA and original build age are preserved across concurrent Cargo rebuilds. Registration rechecks the exact snapshot and asset/HD source age.

There are 420 ordinary sources with zero newly introduced palette indices 240–255, 18 sources with legitimate gameplay cycling/flash labels, and three standalone cinematic cards using their authentic static 256-color palettes. Static card indices are not gameplay animation classes. Apogee/Cygnus/Taiwan titles, text and line breaks passed source review; Taiwan remains retained gallery-only art with no active opening cue. Four small pilot portraits have current 400×225 SDL menu proof; surrounding UI pixels are identical.

The previous 340-frame full-pack proof remains historical. Admission cohorts are journaled in `../data/hd/registered-class-review/batch-{390,397,429,433,441}-*.json`, with per-job `coordinator-review.json` bound to exact frame maps, raw hashes, independent evidence and current runtime output. Generated pixels were not edited.

The 32 additional set-1 terrain frames passed all 61 independent context pages and 1,426 declared cases at scales 1–4, including original intact/destroyed partners. The other 48 admitted terrain frames retain their earlier 1,706-case grain-fix proof. Foreign state-partner artwork stays original fallback and adds no HD debris coverage. Fine texture contrast against original neighbors is disclosed.

## Resume ownership and pending acceptance

The coordinator alone edits development `../data/hd/hd.json`, provenance, the audit and ledger. Artists own their original disjoint job IDs. Queue refreshes omit registered jobs and can shift numeric positions; continue from durable job IDs rather than reassigning shifted indices. Job bookkeeping can change status metadata while exact candidate/raw/source/render bindings remain frozen; record both metadata hashes honestly.

- `iron_coast_3` independently approved 74 boss03 frames in 22 complete families; `200a2` remains held for a two-logical-pixel shortened nozzle. Exact decisions are in external `.reference/iron-coast-3-hd/boss03-cross-review/`. These approvals still need coordinator primary/current admission.
- `iron_coast_5` independently approved 50 boss02 frames in 17 complete families. `30045` remains held for occupied wing/backing/strut losses. Full evidence is `.reference/hd-boss2-independent-review/independent-bosses02-review.json`. Component galleries do not prove complete assembled boss seams.
- `iron_coast_4` independently reviews the other artist's remaining boss01 queue (24 families/81 IDs). Its own Mole and `30045` artwork remain frozen; it never approves its own art.
- `hd_terrain_render` approved short beam eight, now registered. Separate Mole v4 review accepts repaired later eight phases but keeps the family held: original `10352` index253 indicator disappears at native 1×. Preserve the held main candidate and separate v4. Await root's alpha-edge policy decision before duplicating generation.
- `hd_full_review` retains terrain `103b0–103bf` / `103c0–103cf` (32) current source/context/material review. HUD eleven is held for `1000c` N7's missing original bright stroke at `(3,6)`; ten other bindings stay unchanged during author correction.
- `iron_coast_2` authors separate DINO/SHIP35/SHIP40 corrections from source loss maps. Frozen original candidates/queues remain untouched. SHIP40 v3 has independent acceptance with ten small near-black contour losses disclosed; this separate proposal still needs controlled coordinator promotion and admission. SHIP35 v3 and DINO single-source family remain pending/held.
- `campaign_integration` continues effect/projectile corrections. EnergyGrab6 v3, Plasma1 v2 and EnemyLaser4 v4 are pending independent review. Flare, person fragments and other known source-color/contour holds remain isolated.
- `hd_dark_player` completed the registered equipment category and prepares only the held N7 correction. `hd_enemies_01` continues its original ungenerated queue; later flying families, damaged variants and tank phases need independent acceptance. APE output-stage refusal is recorded separately from transient connection failures and is not automatically retried.
- Terrain artists retain source/state/material holds: set1 bridge rows `103d5/6`; set2 fine-grain islands and selected pipe/support geometry; set3 subdued gray remnants/overemphasized debris/foreign beams; set4 source-only crack corrections and mixed original/HD soil density. Successful decode or opacity overlap never resolves these artistic holds.

All generation uses the shared four-slot gate: prepare/view/save prompt before acquire, then acquire → successful start → built-in imagegen → classify and report/release in one execution before returning. Started/unknown calls are recovered rather than silently expired or regenerated. No coordinator generation request is in flight.

Continue acceptance from exact independent records, run current immutable loader proofs, inspect every family row, compare source/scaled output hashes, dry-run complete-family registration, then admit only unchanged approved bindings. Refresh audit and ledger sequentially after admission. Keep tracked runtime untouched until the root assembler explicitly refreshes it. Source/menu/engine changes remain root-owned; Git commands run from this `RustRaptor` repository and checkpoints stage only owned metadata/tools.
