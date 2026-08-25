# Raptor: Call of the Shadows — Replica Plan

## 0. Goal

Faithful playable replica of *Raptor: Call of the Shadows* (Cybernetics Corporation / Apogee, 1994; MS-DOS, VGA 320×200×256, AdLib/Sound Blaster).

Parity bar: a player moving between our binary and the original under DOSBox cannot tell the difference without looking at the window title.

- Identical mission structure: vertical-scrolling phases (mountain terrain → valley → sky → aerial boss) per level.
- Identical wave layouts, enemy types, fire patterns, scoring values, credit bounties.
- Identical shop economy: prices, upgrade effects, loadout slots.
- Visual parity via original assets (sprites, palettes, tilemaps), integer-scaled from 320×200.
- Audio parity: OPL2/3 music and digitized SFX.
- Input feel: same responsiveness bounds (see M3 acceptance).

## 1. Ground truth and references

- Original shareware build running in DOSBox-staging = behavioral oracle for every question (tick rate, spawn timing, scores, shop stock).
- Frame captures + input-scripted sessions for asset extraction and diffing.
- Community prior art: OpenRaptor reimplementation — study for reverse-engineered format knowledge; license review before reading any code (clean-room rule below).
- Open research tasks (each blocks its milestone):
  - exact logic tick rate of the original (timer hook frequency),
  - RNG usage and seeding (affects spawn/replay determinism),
  - full data-file formats: sprite/tile/palette packing, wave tables, music files,
  - complete weapon/missile/bomb stat tables, shop inventory and prices,
  - original save/high-score file layout (compatibility target).

## 2. Legal / asset policy

- Game data is copyrighted. Two supported modes:
  1. **BYO-data**: engine loads original game files the user supplies (like ScummVM).
  2. **Standalone**: shipped with recreated CC0 stand-in assets, clearly labeled non-original.
- Clean-room code: implement from observation and documentation only; no decompilation into the tree.

## 3. Tech stack (boring choices)

| Concern   | Choice                                   | Why |
|-----------|------------------------------------------|-----|
| Language  | C++20                                     | team-maintainable, SDL-native, no runtime |
| Graphics  | SDL2, `SDL_Renderer` sprite batching      | ubiquitous, 2D is all we need |
| Audio     | Nuked-OPL3 (cycle-exact OPL) + PCM mixer  | accurate AdLib reproduction |
| Build     | CMake + system deps                       | Linux/macOS/Windows from one file |
| Tests     | plain assert-style unit tests for pure logic | scoring, shop math, parsers |

Rendering: logical 320×200, integer scaling, letterbox; vsync off, fixed-timestep sim (target rate = measured original tick rate, hypothesis ~70 Hz VGA — verify per §1). Interpolation optional, off by default to match original feel.

## 4. Systems breakdown

1. **Core loop** — fixed-step sim, frame limiter, deterministic when seeded.
2. **Input** — arrows/fire/missile/bomb mapping mirroring original defaults, remappable via config.
3. **Asset pipeline** — loaders for original pack formats (sprites, tiles, palettes, wave tables, OPL music); hot-reload during development.
4. **World** — vertical tile-map scroller, camera, phase-transition triggers within a level.
5. **Entities** — player ship, ground units (turrets, tanks, radar), air units (waves, gunships), projectiles (player/enemy), pickups/credit pods, explosions.
6. **Combat** — data-driven weapon definitions (cannons/lasers/plasma, missile rack, bombs), damage, shield/hull model, i-frames.
7. **Economy** — kill bounties, end-of-level tally screen, shop UI (buy/sell/equip), persistence in an original-compatible save/high-score format.
8. **Audio** — OPL music sequencer, SFX trigger table, volume controls.
9. **HUD/UI** — score, credits, shield, weapon indicators, menus, shop screens at 320×200.
10. **Platform** — config file (keybinds, scaling, fullscreen/window).

## 5. Milestones

Each milestone ends with its acceptance criterion demonstrated on real hardware, not assumed.

- **M0 Scaffold** — repo, CMake build, window opens at 320×200 integer-scaled. AC: binary launches on this machine.
- **M1 Asset spike** — load one sprite sheet + palette from original data files. AC: player ship renders with correct colors/pixels vs DOSBox screenshot.
- **M2 Playfield** — scrolling terrain, camera, static HUD frame. AC: 60 s scroll, zero drift or tearing artifacts.
- **M3 Player** — movement clamped to playfield, cannon fire, projectile pool. AC: input-to-shot latency ≤ 1 sim tick; movement speed matches measured original px/s.
- **M4 Enemies & waves** — table-driven spawner; Level 1 mountain-phase ground turrets + first air waves. AC: side-by-side capture matches spawn positions/timing within tolerance.
- **M5 Combat depth** — enemy fire patterns, collisions, explosion sequence, credit drops. AC: scripted run yields identical credits/score to reference capture.
- **M6 Boss & level flow** — Level 1 boss, phase transitions (mountain→valley→sky). AC: Level 1 completable start-to-boss-kill.
- **M7 Shop & economy** — post-mission tally, full buy/sell/equip flow, persistence. AC: purchase changes next-run loadout; all prices match reference table.
- **M8 Audio** — OPL music playback, SFX triggers. AC: title theme recognizable note-for-note; SFX sync within 1 tick of events.
- **M9 Content** — remaining missions authored as wave tables (needs a small DSL/tooling first). AC: full campaign finishable.
- **M10 Parity & polish** — capture-diff harness across all levels, timing tuning, difficulty curve spot checks. AC: blind pacing test indistinguishable from original.

## 6. Verification method

- **Oracle harness**: same recorded input script fed to our binary and to DOSBox; compare screenshots at fixed ticks and state dumps (score, credits, hull).
- **Determinism check**: seeded runs produce byte-identical state dumps.
- **Unit tests** for pure logic: scoring math, shop transactions, save-format round-trip, wave-table parsing.
- Visual claims always verified against actual captured frames, never from memory.

## 7. Risks

- Unknown internal constants (tick rate, spawn tables) → measure from captures; document every deliberate deviation in `docs/deviations.md`.
- Asset format RE time blowout → time-boxed spikes; fallback to stand-in art keeps engine work unblocked.
- OPL accuracy → solved by Nuked-OPL3; residual risk only in sequencer timing.
- Scope: 9 missions × 3 phases is large → content tooling (M9 DSL) precedes bulk content entry.

## 8. Working agreements

- One milestone ≈ one review-sized changeset; PLAN.md updated as milestones land.
- Every PR states which AC it satisfies and how it was verified.
