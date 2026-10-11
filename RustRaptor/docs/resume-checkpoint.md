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

1. Mod/save diagnostics: Escape can get trapped after details are reopened from
   diagnostics, replacing its parent with itself. Preserve parent and selection.
2. Keep installed mod rows stable when enabled/disabled. Load priority must be
   separate from the displayed order; dependencies and confirmation stay intact.
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
| hd_coordinator | Sole global manifest/ledger owner; register fresh approved29boss frames, keepMole9hold; audit all recoveredrequests before resuming |
| hd_full_review | Terrain corpus49/66pagesreviewed; pages50–66remain;48terrainframeholdstaysuntilfullreview |
| hd_terrain_render | Frozen compositor SHA b30b4a65…;29bossframesapproved,Mole9held;8newportraitscreenssaved,7/fullboardinspectionremain |
| campaign_integration | 34effect/projectilefamilies303IDsraw; detailed RESTART.md preserved; severalgeometry/brightness/layout corrections and independentreviewsremain |
| campaign_release_review | Terrain4queue84jobs1344IDs; recover currentraw/contextcandidates andholds |
| hd_dark_player | Equipment/HUDdigits, acceptedandheldfamilies; reconcilecurrentmanifest before newgeneration |
| hd_enemies_01 | Enemy01queue139IDs; sourcegeometryholds,SHIP25connectionfailure,APE4service-refusalpending |
| hd_terrain_set_1 | Terrain1queue42jobs672IDs; first16registered; recover alreadycompleted103e0output andsubsequentcandidateholds |
| hd_terrain_set_2 | Terrain2queue90jobs1437IDs; continue savedcanonicalchunks andall-contextreview |
| iron_coast_2 | Frozenenemy03firstdrafts59families138IDs; recovered45familyenemy02queuecontinues, old11familiesfrozen |
| iron_coast_3 | Boss01queue26families83IDs; recovered11completedatlasfamiliesneedbindings/QA; previous15candidatespreserved |
| iron_coast_4 | Boss02queue27families83IDs; approvedsubset/corrections,connectionfailurecooldowns |
| iron_coast_5 | Boss03complete25families82IDs/328scalechecks; equipment8reviewpending; temporarygroundgunbugassignment |
| iron_coast_6 | Terrain3queue68jobs1082IDs, withmiddleandlateshards; preserve strictdestroyedgeometryholds |

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
