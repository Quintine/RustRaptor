# Restart checkpoint — 13 October 2026

The latest power outage interrupted the HD review workers, but their completed
outputs and the next playable asset bundle survived. The Git root is this
`RustRaptor` folder on branch `codex/rust-rewrite`, with public remote
[Quintine/RustRaptor](https://github.com/Quintine/RustRaptor). The last confirmed
publication is `5224219771538ef420fefdcb4ac5e671ff76a06a`, containing 5,069
reviewed original pictures. Its native Windows workflow
[38279526351](https://github.com/Quintine/RustRaptor/actions/runs/38279526351)
passed 341 tests, loaded all 5,069 HD frames with zero rejects, validated all
45 mods, and passed Unicode relocation, SDL gameplay and mixed/SFX-only PCM
checks. These automated results do not establish hardware or listening quality.

The recovered next bundle contains **5,131 reviewed pictures / 3,310 complete
sequences**, including **4,045 terrain pictures**. It adds 62 source-native
terrain singletons. Both bundled executables and the Rust source remain
unchanged. Actual packaged CLI validation passed all 5,131 frames with zero
rejects and 45 mods / one override. Root reviewed five full 1080p screenshots
before the outage and two additional original Sector 3 Wave 2/7 screenshots
after recovery. Visible texture differences where HD meets original terrain
remain documented; complete visual coverage is still in progress. At this
checkpoint the 5,131 publication and its native Windows workflow are pending.
Later publication receipts take precedence over this recorded observation.

**622 original pictures remain:** 490 terrain, 89 enemies/ground objects,
36 UI/other and seven boss pictures. Of the remaining terrain, 168 have
qualified material candidates awaiting context, metadata or admission work;
322 retain concrete art holds, prior selection exclusions or actual tool
refusals. A generated draft is not counted as an approved remaster. Permanent
refusals and failed repair methods must remain visible, without automatic retry.

Recovered work is divided as follows:

| Work | Recovery owner / saved evidence |
| --- | --- |
| 62-frame bundle, runtime validation and Git publication | Root; `.reference/hd-root-next-publication-after5069/` |
| External registration and four HD coverage documents | HD coordinator; `.reference/hd-coordinator-compact62-canonical-registration-5131-20261013/` |
| Six qualified terrain candidates | Iron Coast 2 private metadata writer; Iron Coast 3 independent metadata audit; current 5,131 baseline |
| 29 qualified terrain candidates | Middle independent physical review of 63 changed compositions; Full's technical outputs are frozen |
| 59 qualified terrain candidates | Iron Coast 5 independent physical review of 313 compositions, followed by current-baseline source comparison |
| 73 qualified terrain candidates | Campaign release reviewer combines five source plans; Dark player closes six current intrinsic-QA gaps |
| Held terrain repairs | Terrain sets 1/2 inspect histories and perform distinct local edits; Iron Coast 6 investigates existing sampling behavior |
| Native Windows | Windows persistence observes the exact published commit; no duplicate large artifact download |

Read the current [HD coordinator checkpoint](hd-coordinator-checkpoint.md) and
[coverage backlog](hd-backlog.md) for accepted counts and qualifications. Private
review evidence lives in `.reference/` and the external `../data/hd/` workspace;
approved artwork, original game data, Linux/Windows executables and all authored
mod media remain tracked inside this self-contained folder. Recover an existing
terminal receipt before running a writer or image request again, and retain
literal previous review roles and output hashes. Root owns Git and runtime
packaging; the coordinator owns external canonical metadata and coverage docs.

The following 11 October checkpoint is preserved as historical evidence.

# Earlier restart checkpoint — 11 October 2026

The shutdown interrupted the final coordinated stop before the unified note
was written. Work is preserved on `codex/rust-rewrite`; no game, Cargo, review
helper or packaging shell process remained at recovery. The image-generation
gate was paused with zero active leases, and has now been resumed. Recover each
worker from its existing outputs before submitting another generation request.

## Repository relocation and GitHub

`RustRaptor/` is now the Git root, including its `.git/` metadata. Migration
commit `8f45979` preserves history and is pushed to the public
[Quintine/RustRaptor](https://github.com/Quintine/RustRaptor) repository on
`codex/rust-rewrite`. Run all Git commands from `RustRaptor/`, with paths such
as `src/desktop.rs` and `docs/hd-backlog.md`.

The user explicitly requested that the bundled game and data be included in
Git. `bin/`, `lib/`, `data/` and `runtime-manifest.json` are tracked; caches,
review files and duplicate zip exports are ignored. All 6,566 runtime data
hashes match in a fresh public GitHub checkout, which validates all 6,449
original catalog entries. Its SDL game also launched from `/tmp` using only
the bundled library and an isolated profile. Pending source, mod and artwork-review work survived
the relocation. See [repository layout](repository.md).

## Engine and package

### Current runtime and Stage 2 work

The current Linux and Windows runtimes include the reviewed **1,148-frame /
421-sequence** HD snapshot and **6,848 data files**, with unchanged original
`INDEX`. Linux binary SHA-256 is
`7e62ae1b0e8d18670a7c6c3d4f6419878f696f62ba4c7dd2ee9ebf7545f648de`;
Windows is `63d040f5d5c76bad15a74ab1ef54ca992a0fd9cd8b7a46f8506d8cce4fbec275`.
Checked script commands control nonlegacy boss animation frames and native
impact-effect kinds. The renderer applies phase pins to sprites and both
shadow layers; clearing a pin restores ordinary animation. Original effect
serialization remains compatible. PNG activation fully decodes with the same
limits while avoiding discarded palette conversion; all 6,682 referenced PNG
outputs compare byte-identically and five rejection/output regressions pass.

**Iron Coast II: Black Tide** adds eight missions, eight bosses, three shared
enemies, three original FM scores and two optional purchased weapons through
23 individual packages. Independent review completes the eight missions plus
saved finale replay at difficulties 0–3 from registered-pilot starting gear,
with paid repairs. The final root Veteran route saves/loads between nine wins
and binds the documentation-only aggregate successor hash. All 34 Host
artwork/shop/menu pictures are reviewed; the six changed phase pictures were
inspected again and the other 28 remain byte-identical. Ordinary release suites
pass **315 headless / 380 desktop** tests, with 26/36 deliberate original-data
and capture tests ignored. Corrected Linux/Windows archives pass full integrity,
Unicode/space relocation, first/final mission 1080p rendering, separate music
and effects recordings and the original intro's forced 4:3 framing. All 45 mod
hashes match and combined catalog validation passes; the Windows CLI review's
CSV-quoting correction is retained as a separate addendum. The
[corrected native Windows run](https://github.com/Quintine/RustRaptor/actions/runs/38129755440)
also checks the eight-sortie saved route, displayed phases and both shadow
layers, SD/HD shop captures and packaged MSVC audio/gameplay. Final documentation
exports receive strict whole-archive successor checks requiring identical
runtime, libraries, launchers, data and mods. Previous runtime receipts remain
historical. [Stage 2 design and validation](iron-coast-stage2-design.md) and
[standalone packages](standalone-package.md) record content, controls, prices
and acceptance scope.

Original HD work continues under `hd_coordinator`; later approved candidates
remain separate from the immutable packaged 1,148-frame snapshot. The paragraphs
below preserve the earlier recovery and 800-frame package evidence.

### Earlier package checkpoints

- Windows support is now included: `bin/raptor-rust.exe`, adjacent `SDL2.dll`,
  `run.cmd`, `runtime-windows-manifest.json` and the Windows export tool/CI.
  The GNU executable SHA-256 is
  `e414d2df745369115082439414099f528aca8457f9c58d1c1745eb1b511fc484`.
  All 279 portable tests pass under Wine, including Windows save replacement;
  all 22 mod hashes match existing Linux save pins. Windows paths respect
  APPDATA/LOCALAPPDATA and mods preserve exact bytes through Git checkouts.
  The exported folder launches via `run.cmd` from `/tmp` after relocation to
  a path with spaces and Unicode; all hashes/mods validate. HD gameplay at 1080p,
  the original 4:3 intro and music-muted SDL sound-effect capture pass. Local
  evidence is in `.reference/windows/`. Native Windows CI also passes all 279
  portable tests plus MSVC desktop/exported-folder checks at
  [the build run](https://github.com/Quintine/RustRaptor/actions/runs/38119440288).
  A [second native run](https://github.com/Quintine/RustRaptor/actions/runs/38119943948)
  also verifies the exact committed GNU runtime and launcher before its MSVC build.
  The [800-frame native run](https://github.com/Quintine/RustRaptor/actions/runs/38121272504)
  passes all 279 tests and both runtime checks with the refreshed art and all mods.
  The Windows executable additionally runs Iron Coast mission 1 with all 22 mods enabled
  and captures its custom music. Hardware display/audio/controller checks
  remain manual; automated runs use SDL dummy drivers.
  See [Windows build and validation](windows-build.md). The tracked catalog
  now contains the immutable 800-frame reviewed snapshot while broader HD review continues.
- Packaged executable now includes the `c0a6fd3` reviewed source checkpoint,
  including diagnostics navigation and interpolated Lightning effects. Its
  SHA-256 is `4b4304f625381cbbf1331e126c62ca0913d49a52e7a35191f12e734067660e66`.
  The original `fdf2ff0` checkpoint supplied standalone RustRaptor, widescreen
  menus and always-4:3 original cinematics, including when gameplay stretching
  is selected. Fresh 1080p intro capture confirms black 240-pixel side borders.
- `RustRaptor/bin/raptor-rust`, `lib/`, `data/` and
  `dist/RustRaptor-linux-x86_64.zip` exist. The latest snapshot includes all
  6,449 original assets, 800 approved HD frames and 22 local mods. It was
  launched from a copied folder containing spaces, from `/tmp`, without Cargo.
- Before shutdown, 320 default tests, the complete 42-image menu/intro audit,
  separate cinematic aspect regression, mod/catalog/HD validation and copied
  1280×800/1080p SDL/audio smoke checks passed. Later fixes require fresh checks.
- Source navigation fixes are committed in `4b1edef`; the terrain compositor
  fix is committed in `ab23255`; Lightning weapon/API packages and authored
  art/audio are committed in `c0a6fd3`. The refreshed package validates all
  22 mods and 800 supplied HD frames. Desktop builds use the isolated
  `target/desktop-runtime` directory to avoid competing headless artifacts.

## Next user fixes

1. Mod/save diagnostics: parent and selection are now preserved when details
   are reopened. The Escape regression and fresh 42-capture screenshot audit
   pass, including repeated details, confirmation and back navigation.
2. Installed mod rows now stay in ID order through toggles and priority changes,
   with dependency and confirmation behavior preserved. Navigation tests pass.
3. Default Forward Guns still appear to miss miscellaneous buildings/cars.
   Actual original-data checks now cover all 889 destructible terrain
   definitions, 17 early wave 6/7 occurrences, all 110 classic ground units
   and four early native spawn paths. These pass. Some industrial pieces are
   deliberately indestructible in the original tables; the exact reported
   object remains unidentified, so no speculative native collision change was made.

The resumed source suite passes 333 tests with 31 optional checks ignored.
The original menu/intro audit passes and completes at 1,891 service ticks.
The subsequent independent Lightning review found and fixed attached-effect
interpolation and missing mod/script/hook command-error context. All 72 focused
API, modding and weapon checks pass after those fixes. The reviewed packages
are committed, and the executable and zip have been refreshed and launched.

Root owns menu fixes. `iron_coast_5` temporarily owns the ground-target diagnosis;
its completed boss candidates and pending equipment review remain preserved.

## Earlier HD state and recovery owners

The original picture inventory is 5,753 IDs. The approved handoff has 800
registered frames across 340 complete sequences; 4,953 IDs remain unregistered.
Both packaged runtimes have the same immutable 800-frame approved snapshot,
with 6,742 original/HD data files and unchanged executable hashes. The assembler's
`--hd-source` selects the private approved input rather than mutable working art.
See [the current coordinator checkpoint](hd-coordinator-checkpoint.md) for
active worker ownership and later admissions. The table below retains the
earlier recovery assignments as historical context. Existing raw
candidates are not counted as accepted remasters. Working originals, generated
drafts and proof captures remain outside the Git root; the approved runtime
snapshot and all authored mod artwork and sound are tracked in Git.

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
