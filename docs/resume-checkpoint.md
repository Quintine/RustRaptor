# Restart checkpoint — 11 October 2026

The shutdown interrupted the final coordinated stop before the unified note
was written. Work is preserved on `codex/rust-rewrite`; no game, Cargo, review
helper or packaging shell process remained at recovery. The image-generation
gate was paused with zero active leases, and has now been resumed. Recover each
worker from its existing outputs before submitting another generation request.

## Engine and package

- Last committed engine checkpoint: `fdf2ff0`, standalone RustRaptor, widescreen
  menus and always-4:3 original cinematics, including when gameplay stretching
  is selected. Fresh 1080p intro capture confirms black 240-pixel side borders.
- `RustRaptor/bin/raptor-rust`, `lib/`, `data/` and
  `dist/RustRaptor-linux-x86_64.zip` exist. The latest snapshot includes all
  6,449 original assets, 221 approved HD frames and 22 local mods. It was
  launched from a copied folder containing spaces, from `/tmp`, without Cargo.
- Before shutdown, 320 default tests, the complete 42-image menu/intro audit,
  separate cinematic aspect regression, mod/catalog/HD validation and copied
  1280×800/1080p SDL/audio smoke checks passed. Later fixes require fresh checks.
- Uncommitted lightning weapon/API packages and terrain compositor improvements
  are preserved. Review and commit them separately; do not discard their work.
  The executable/package must be refreshed after source or accepted-art changes.

## Next user fixes

1. Mod/save diagnostics: parent and selection are now preserved when details
   are reopened. The Escape regression passes; full screenshot audit is running.
2. Installed mod rows now stay in ID order through toggles and priority changes,
   with dependency and confirmation behavior preserved. Navigation tests pass.
3. Default Forward Guns still appear to miss miscellaneous buildings/cars.
   Expand actual original-content coverage beyond the earlier ten-unit test.

Root owns menu fixes. `iron_coast_5` temporarily owns the ground-target diagnosis;
its completed boss candidates and pending equipment review remain preserved.

## HD state and owners

The original picture inventory is 5,753 IDs; 221 are registered and 5,532 remain
unregistered. Existing raw candidates are not counted as accepted remasters.
All original/generated base pixels and proof captures remain ignored; authored
mod artwork and sound belong in Git.

| Agent | Recover and continue |
| --- | --- |
| hd_coordinator | Sole manifest/ledger owner; 29 boss and 48 terrain frames await final registration checks; retain Mole9 hold |
| hd_full_review | All 66 terrain pages and 1,706 cases now reviewed; exact-hash terrain approval saved |
| hd_terrain_render | Frozen compositor SHA b30b4a65…; 29 boss frames approved, Mole9 held; all eight new portrait screenshots approved |
| campaign_integration | 34 effect/projectile families, 303 IDs have raw outputs; geometry, brightness and layout corrections continue |
| campaign_release_review | Terrain 4: 84 jobs, 1,344 IDs; 64 candidates saved, half await further visual/Host QA |
| hd_dark_player | Equipment and HUD digits; reconcile accepted frames, preserve pending Death Ray/Energy review |
| hd_enemies_01 | Enemy 1: 139 IDs; source geometry holds, SHIP25 connection failures and APE service refusal preserved |
| hd_terrain_set_1 | Terrain 1: 42 jobs, 672 IDs; first 16 registered; 80 other candidates and explicit rejected scenery remain |
| hd_terrain_set_2 | Terrain 2: 90 jobs, 1,437 IDs; continue canonical chunks and full neighboring-context review |
| iron_coast_2 | Enemy 3: 59 families, 138 raw IDs; recovered 45-family enemy 2 queue continues, old 11 families frozen |
| iron_coast_3 | Boss 1: 26 families, 83 IDs; 11 recovered atlas families need binding/QA; previous 15 candidates preserved |
| iron_coast_4 | Boss 2: 27 families, 83 IDs; continue corrections, complete reviews and respect service cooldowns |
| iron_coast_5 | Boss 3: 25 families, 82 candidates and 328 scale checks; temporarily auditing every destructible classic tile for ground-gun misses |
| iron_coast_6 | Terrain 3: 68 jobs, 1,082 IDs with middle/late shards; retain destroyed-state geometry holds |

## Durable worker evidence

- `data/hd/jobs/effects-10249-1024c/RESTART.md` and adjacent checkpoint JSON:
  effect/projectile raw outputs, exact hashes, request outcomes and next tasks.
- `.reference/hd-terrain-cross-review/restart-checkpoint.json`:
  frozen terrain fix, 29 boss approvals, Mole9 hold and current portrait captures.
- `.reference/hd-boss3-cross-review/shutdown-checkpoint.json`:
  completed boss shard, exact equipment8 candidate hashes and unfinished review.
- `data/hd/jobs/bosses-03-review-summary.json` and
  `bosses-03-owner-progress.json`: all boss03 candidates and known caveats.
- Current source-bound candidates/provenance under `data/hd/jobs/<job>/`;
  lease history under `data/hd/jobs/.imagegen-gate/`.

Do not regenerate already-returned raw images, infer approval from validation,
clear source-fidelity holds or reset the shared checkout. Follow the documented
single-call gate lifecycle and refresh checkpoints before the next shutdown.
