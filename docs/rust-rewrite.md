# Rust engine and validation

## 17 October 2026: live mod snapshots and dense-event queries

World callbacks now receive `difficulty` and the addressed enemy's current `actor`
snapshot, including damage, movement and removal committed by earlier callbacks.
Dense enemy snapshots exposed Rhai's recursive map limit: even an ordinary query
could reject a 24-enemy event. The bounded limit is now 16,384 properties; existing
operation, command and serialized-state limits remain unchanged.

All 45 modding tests pass, including all four difficulties, save/RNG continuation,
stale callbacks, 64-enemy queries and oversized intermediate/output rejection.
Linux and Windows executables are rebuilt. Menu and two original-mission 1080p
SDL captures are byte-identical across the change (6,220,800 pixels compared).
Windows execution is verified separately by the post-push native workflow.

Rust is the default engine. The Rust binary never calls or embeds the C++ engine. SDL2 provides window/input/controller/audio services. Simulation and the validation CLI build without SDL2. The retained C++ checkout is optional reference material.

| Module | Responsibility |
| --- | --- |
| assets | Checked catalog, palettes, raw/span pictures, libraries, maps and demo records. |
| content, legacy_tables | Typed registries and generated original numeric mappings. |
| simulation | Rational clock, integer motion, shared RNG, collision/weapon/enemy/terrain rules, script transactions. |
| render, hd | Indexed canvas, ScaleNx, caches, PNG/palette conversion and optional source-hashed HD art. |
| audio, sound | Original MUS/GENMIDI FM and digital DSP behavior; package-local PCM WAV decoding. |
| cinematics | Checked AGX delta frames and movie timing. |
| persistence | TOML settings, versioned JSON pilots, atomic writes and read-only legacy import. |
| modding | Packages, dependency ordering, overrides, bounded Rhai callbacks/state and save pins. |
| desktop | SDL2 services, UI, shop/equipment, mod manager, settings and interpolation. |

## Build and run

Rust 1.88+, Cargo and SDL2 development libraries are required. A local SDL2 installation in `~/.local/lib` is supported. Commands below run from `RustRaptor/`. The launcher sets the library path and uses a release build:

```sh
./run.sh
./run.sh --mods mods
```

For development and tests:

```sh
export LD_LIBRARY_PATH="$HOME/.local/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
cargo test --locked
cargo test --locked --no-default-features
RAPTOR_TEST_DATA="$PWD/data" cargo test --locked
RAPTOR_TEST_DATA="$PWD/data" cargo test --locked -- --ignored
```

Portable fixtures use synthetic assets and the bundled authored mod art/audio. Original integration checks are opt-in and local. Native audio comparisons compile a small retained-source harness with g++ and SDL2 headers; pure Rust playback itself uses no C++ runtime.

## Profiles and settings

Rust uses `$XDG_DATA_HOME/RaptorReplica/pilot-NNNN.json` and `mods/`, `$XDG_CONFIG_HOME/RaptorReplica/config.toml`, and `$XDG_CACHE_HOME/RaptorReplica/` for derived assets. Normal XDG defaults apply. Pilots record active package versions/hashes and script state/RNG. Missing, changed or reordered requirements show a compatibility prompt with Cancel selected and **Load anyway** available. Confirming keeps unavailable equipment, quantities, progression and inactive script state. The first subsequent write preserves the previous save in a hash-named `before-mod-change` backup. Corrupt files and unsafe structural values remain errors; inspecting or cancelling never modifies the file.

Legacy `~/.local/share/Raptor/SETUP.INI` and pilot files are imported read-only. All difficulties, waves, portrait and training metadata are retained. Rust writes only its separate versioned files. Explicit CLI import output cannot be the original file.

Options include scaling, scanlines, aspect correction, fullscreen/borderless, input bindings/controller, volumes and optional HD art. New/load pilot controls show compatibility details for affected save slots. The Mods screen applies validated selections at the main menu; selections made during flight remain pending until returning there.

The main menu leads to the Hangar, new/load/import pilots, options, mods and
extras. The Hangar keeps flying, mission selection, the supply room, inventory,
**Save pilot**, pilot ID editing and exit visible together. Saving writes the
pilot atomically and shows the callsign and slot. Completed missions and
equipment purchases also save automatically. Saves contain hangar/progression
state; an in-flight save does not create a mid-mission checkpoint.
New pilot registration selects a name, callsign, ID picture and difficulty,
and starts with the original 10,000 credits and 75 energy. Imported ID pictures
retain their native catalog identity.

Keyboard defaults are arrows for movement, Ctrl for firing, Space for bombs,
Alt or Shift for cycling equipment, and Z for selected consumables. Selecting
a weapon makes the fire control fire it alongside the forward guns. Settings
that retain the old complete default cycle/bomb/special binding combination
migrate on load; custom combinations are preserved.

## Local asset and platform checks

```sh
cargo run --locked --no-default-features -- --data data --verify-assets
cargo run --locked --no-default-features -- --data data --mods mods --validate-mods aurora
cargo run --locked --no-default-features -- --data data --mods mods \
  --enabled aurora --headless aurora:field_trials --ticks 700
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy cargo run --locked -- \
  --data data --profile-root ../.reference/smoke --smoke-frames 5 \
  --screenshot ../.reference/menu.png
```

Use real SDL video for interactive/display-performance checks. Dummy screenshots verify raster placement, not GPU/vsync performance. `--preview-mission ID` starts a mission; `--preview-cinematic credits|intro|landing|death|end1|end2|end3` previews movies. Frame-limited runs do not save pilots/settings; cache stays within the selected profile.

## Controlled reference replays

This optional comparison workflow uses the retained C++ source. Rebuild it before recording. Trace output is opt-in during legacy demo playback and records complete updates after palette/stat processing, which also consumes the shared RNG.

```sh
mkdir -p ../.reference
cmake --build ../raptor/build --target raptor --parallel 8
(cd ../data && env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  XDG_DATA_HOME="$PWD/../.reference/legacy-profile" \
  RAPTOR_REFERENCE_TRACE="$PWD/../.reference/cpp-demo.jsonl" \
  RAPTOR_REFERENCE_TICKS=1889 \
  ../raptor/build/bin/raptor PLAY "$PWD/demos/DEMO1G1_REC")
cargo run --locked --no-default-features -- --data data \
  --replay DEMO1G1_REC --ticks 1889 --trace ../.reference/rust-demo.jsonl
python3 tools/compare_replays.py ../.reference/cpp-demo.jsonl ../.reference/rust-demo.jsonl
```

All 1,889 available steps of DEMO1G1_REC match the captured fields: RNG, player coordinates/bank/shields/credits, ordered enemy position/health/animation/path state and ordered projectile assets/positions. The comparator fails at first divergence or unequal lengths. This is a subset of full state; inventory, effects, objectives and internal AI counters are outside this trace. That demo starts sector 1 wave 3 and ends before its boss. See the separate [first-mission wins](first-mission-validation.md), [108 campaign runs](campaign-validation.md) and [departure/death checks](transition-validation.md). Recordings stay ignored in `../.reference/`.

## Audio and remaining acceptance

The Rust FM/DSP implementation has synthetic sample-by-sample native comparisons and a four-second original intro-music comparison at 44.1kHz. The checked sound bank also dispatches original and mod cues through the SDL callback; real-device output checks are documented in [sound validation](sound-validation.md). These establish those cases, not every track/input/output rate. The Rust core retains the original envelope/noise semantics and LGPL source provenance.

The campaign checks cover all waves and difficulties with assistance, and first-mission tests win without replenishing pilot health or editing enemy state. Wider ordinary playtesting and more complete native state comparisons remain useful. Normal startup includes the original logos, fanfare and intro. Native timing, sound-marker resolution, scene stops and custom logo palettes are checked in [intro validation](intro-validation.md). The refined menu uses an authored hangar backdrop and has a [42-frame screenshot review](menu-validation.md). Base-game HD coverage is partial; bundled mods supply SD/HD art. See [display measurements](performance.md).

Scale2x/3x follows the [published algorithm](https://www.scale2x.it/algorithm); Scale4x applies Scale2x twice. WAV parsing follows the [RIFF chunk format](https://learn.microsoft.com/en-us/windows/win32/xaudio2/resource-interchange-file-format--riff-). The playable catalog, approved runtime HD assets and authored mod artwork/sounds are tracked. Working source references and review captures remain outside the repository.
