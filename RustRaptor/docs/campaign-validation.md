# Original campaign validation

Local checks on 2026-10-10 reached mission completion for all 27 original waves
at each of the four difficulties. These 108 runs are assisted inspection fixtures,
not ordinary player victories and not per-wave C++ parity proofs. Original game
data, reference recordings, profiles and CSV reports remain under ignored local
directories.

The separate, complete `DEMO1G1_REC` comparison matches the rebuilt C++ engine
across all 1,889 available simulation steps. Captured fields are the RNG seed,
player coordinates/banking/shields/credits, ordered enemy asset/position/health/
animation/movement coordinates, and ordered projectile asset/position/hostility.
The recording starts in sector 1 wave 3 and ends before the boss. Inventory,
internal AI counters, terrain damage, effects, audio samples and presentation are
outside this gameplay trace; this does not establish full-game parity.

## Assisted campaign fixture

`tools/campaign_check.rs` gives the pilot the original arsenal and five mega
bombs, fires continuously, aims horizontally at visible enemies while preferring
bosses, cycles specials every 180 simulation steps and presses the bomb control
every 480 steps. Before each step it replenishes energy and super-shield values
to 100 each. Inputs still use the game input path. Enemy definitions, damage,
spawn timing, RNG and mission outcomes are not replaced. A run stops at the
reported outcome or its 12,000-step inspection limit.

The final run visited every spawn record, observed every expected boss instance
and finished with no remaining enemies. Its local CSV is
`../.reference/campaign-validation-final.csv` (SHA-256
`c4e1fc0ca1199efd2a9e72ceb7ebbe3d71325b517cb9829995138ead99486901`).

| Difficulty | Completed waves | Steps per wave | Enabled spawns | Boss instances seen | Nonpositive last health | Positive last health |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| 0 | 27 | 4,601–4,873 | 3,751 | 88 | 53 | 35 |
| 1 | 27 | 4,607–4,873 | 3,751 | 88 | 53 | 35 |
| 2 | 27 | 4,651–5,079 | 6,259 | 88 | 37 | 51 |
| 3 | 27 | 4,650–5,082 | 8,668 | 88 | 36 | 52 |

The 108 runs cover 513,003 simulation steps, 22,429 enabled spawns and 352 boss
appearances. Boss retirement counts classify the health observed immediately
before removal: 179 nonpositive and 173 positive. Positive health commonly
indicates a boss leaving the screen; damage and removal within the same step
can also affect this classification. These counts are not an exact death-event
audit. The harness deliberately allows the original wave completion condition
after all spawned ships have died or left, rather than requiring every boss to
be killed.

Additional opt-in tests exercised all 15 original player weapon definitions with
live mission targets and observed emitted projectiles. This verifies availability
and basic firing paths, not exact weapon effects. Progression checks exercise
training's four-wave route, each normal 27-wave route, difficulty promotion,
campaign resets and the training reward. They call the progression API directly
and bypass combat; end cinematics and menu transitions need separate checks.

Run the four original-data integration tests from the `RustRaptor/` directory:

```sh
RAPTOR_CAMPAIGN_REPORT=../.reference/campaign-validation-final.csv \
  cargo test --release --no-default-features --test campaigns -- --ignored --nocapture
```

Set `RAPTOR_TEST_DATA` if the original catalog is elsewhere. Set
`RAPTOR_REFERENCE_DEMO1` to use a different full C++ reference trace. Without
`--ignored`, these tests do not require or distribute original assets.

The reporting helper is also a standalone Rust CLI. Build the library, supply
its resulting `libraptor_replica-*.rlib` path to `rustc --extern`, and retain the
dependency directory:

```sh
cargo build --release --no-default-features --lib
rustc --edition=2024 tools/campaign_check.rs \
  --extern raptor_replica=target/release/deps/libraptor_replica-HASH.rlib \
  --extern anyhow=target/release/deps/libanyhow-HASH.rlib \
  -L dependency=target/release/deps -o ../.reference/campaign-check
../.reference/campaign-check ../data
```

Its optional second argument selects one difficulty, for example
`../.reference/campaign-check ../data 3`.

## Reproduce the complete demo comparison

Rebuild the retained C++ source before capturing a reference. The local debug
build used `../.reference/cpp-rng-build`; use the available CMake executable if it
is outside `PATH`. Prepare an isolated legacy profile with `raptorsetup`, or
copy an existing `SETUP.INI` into `../.reference/full-demo-profile/Raptor/` before
running the following commands. The original executable requires `data/` as its
working directory. A complete reference takes about 81 seconds at 70/3 Hz.

```sh
cmake --build ../.reference/cpp-rng-build --parallel 4
(
  cd ../data
  XDG_DATA_HOME="$PWD/../.reference/full-demo-profile" \
  SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  RAPTOR_REFERENCE_TRACE="$PWD/../.reference/cpp-demo1-full.jsonl" \
  RAPTOR_REFERENCE_TICKS=1889 \
  ../.reference/cpp-rng-build/bin/raptor PLAY demos/DEMO1G1_REC
)
cargo run --no-default-features -- \
  --replay DEMO1G1_REC --ticks 1889 --trace ../.reference/rust-demo1-full.jsonl
python3 tools/compare_replays.py \
  ../.reference/cpp-demo1-full.jsonl ../.reference/rust-demo1-full.jsonl
```

The comparator reports `Identical gameplay snapshots across 1889 simulation
steps.` and rejects unequal lengths, repeated tick numbers or the first differing
field. The local C++ trace SHA-256 is
`6f0378dbe4d819b44de86dc22822d2e70cb65546e6aed89dd45a44a8eb3d02fe`.

This comparison found and repaired beam damage before player-follow artwork,
raw recorded positions beyond ordinary input bounds, low-shield equipment loss
and automatic selection cycling, and the last authored kamikaze leg's transition
into the player chase. Portable synthetic regressions in `tests/gameplay.rs`
cover those rules without original pixels or recordings.

## Remaining gameplay validation

The catalog inspection found no wave completion blocker under the assisted
fixture. Source inspection also found and repaired three original weapon rules,
with four additional portable regressions:

- Energy Grab damages only airborne ships by one point, drains the original
  resistance counter and disables susceptible enemies' firing. Immunity and
  continued suppression after animation updates have separate coverage.
- Ground Bomb damages terrain before checking a ground enemy and applies the
  original left/up/right neighbor effects, including the preceding-row pass.
  One test verifies simultaneous terrain and ground-enemy damage.
- Mega Bomb applies its original 50 enemy damage, clears hostile shots and
  subtracts 20 health only from visible destructible terrain. A test covers
  distant tiles, inert terrain, destroyed tiles and the final visible tile.

A longer record set, C++ traces through bosses and departure/death sequences,
ordinary pilot playthroughs, all weapon effects, shield recharging and complete
save/menu/cinematic routes are still needed for full acceptance. The complete
demo match and assisted campaign coverage should be retained as regression
evidence while those gaps are resolved.
