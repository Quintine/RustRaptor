# Rust engine and validation

The Rust binary never calls or embeds the C++ engine. SDL2 provides window/input/controller/audio services. Simulation and the validation CLI build without SDL2. The C++ checkout stays available for controlled reference comparisons and normal play until full acceptance passes.

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

Rust 1.88+, Cargo and SDL2 development libraries are required. A local SDL2 installation in `~/.local/lib` is supported. The launcher sets the library path and uses a release build:

```sh
./play.sh --engine rust
./play.sh --engine rust --mods examples/mods
```

For development and tests:

```sh
export LD_LIBRARY_PATH="$HOME/.local/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
cargo test --locked
cargo test --locked --no-default-features
RAPTOR_TEST_DATA="$PWD/data" cargo test --locked
RAPTOR_TEST_DATA="$PWD/data" cargo test --locked -- --ignored
```

Synthetic fixtures contain no copyrighted or generated game pixels. Original integration checks are opt-in and local. Native audio comparisons compile a small retained-source harness with g++ and SDL2 headers; pure Rust playback itself uses no C++ runtime.

## Profiles and settings

Rust uses `$XDG_DATA_HOME/RaptorReplica/pilot-NNNN.json` and `mods/`, `$XDG_CONFIG_HOME/RaptorReplica/config.toml`, and `$XDG_CACHE_HOME/RaptorReplica/` for derived assets. Normal XDG defaults apply. Pilots record active package versions/hashes and script state/RNG. Missing or changed requirements block loading, without deleting equipment or replacing the save.

Legacy `~/.local/share/Raptor/SETUP.INI` and pilot files are imported read-only. All difficulties, waves, portrait and training metadata are retained. Rust writes only its separate versioned files. Explicit CLI import output cannot be the original file.

Options include scaling, scanlines, aspect correction, fullscreen/borderless, input bindings/controller, volumes and optional HD art. New/load pilot controls keep incompatible save slots separate. The Mods screen applies validated selections at the main menu; selections made during flight remain pending until returning there.

## Local asset and platform checks

```sh
cargo run --locked --no-default-features -- --data data --verify-assets
cargo run --locked --no-default-features -- --data data --mods examples/mods --validate-mods aurora
cargo run --locked --no-default-features -- --data data --mods examples/mods \
  --enabled aurora --headless aurora:field_trials --ticks 700
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy cargo run --locked -- \
  --data data --profile-root .reference/smoke --smoke-frames 5 \
  --screenshot .reference/menu.png
```

Use real SDL video for interactive/display-performance checks. Dummy screenshots verify raster placement, not GPU/vsync performance. `--preview-mission ID` starts a mission; `--preview-cinematic intro|landing|death|end1|end2|end3` previews movies. Frame-limited runs do not save pilots/settings; cache stays within the selected profile.

## Controlled reference replays

Rebuild the current C++ source before recording. Trace output is opt-in during legacy demo playback and records complete updates after palette/stat processing, which also consumes the shared RNG.

```sh
mkdir -p .reference
cmake --build raptor/build --target raptor --parallel 8
(cd data && env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  XDG_DATA_HOME="$PWD/../.reference/legacy-profile" \
  RAPTOR_REFERENCE_TRACE="$PWD/../.reference/cpp-demo.jsonl" \
  RAPTOR_REFERENCE_TICKS=1000 \
  ../raptor/build/bin/raptor PLAY "$PWD/demos/DEMO1G1_REC")
cargo run --locked --no-default-features -- --data data \
  --replay DEMO1G1_REC --ticks 1000 --trace .reference/rust-demo.jsonl
python3 tools/compare_replays.py .reference/cpp-demo.jsonl .reference/rust-demo.jsonl
```

The first 1,000 steps of DEMO1G1_REC have matched all captured fields: RNG, player coordinates/bank/shields/credits, ordered enemy position/health/animation/path state and ordered projectile assets/positions. The comparator fails at first divergence or unequal lengths. This is a subset of full state: add inventory, effects, objectives and all internal AI state before declaring complete parity. That demo starts sector 1 wave 3, so it does not validate the first mission or every campaign. Recordings stay ignored in `.reference/`.

## Audio and remaining acceptance

The Rust FM/DSP implementation has synthetic sample-by-sample native comparisons and a four-second original intro-music comparison at 44.1kHz. These establish those cases, not every track/input/output rate. The Rust core retains the original envelope/noise semantics and LGPL source provenance.

Longer replays, all campaign/difficulty paths and end-to-end boss playthroughs still require verification. Original cinematics decode/play locally but exact fade/transition/custom-palette fidelity needs comparison. Some menu layouts differ. HD coverage is partial and display performance must be measured before cutover.

Scale2x/3x follows the [published algorithm](https://www.scale2x.it/algorithm); Scale4x applies Scale2x twice. WAV parsing follows the [RIFF chunk format](https://learn.microsoft.com/en-us/windows/win32/xaudio2/resource-interchange-file-format--riff-). Original catalog/reference assets remain outside version control. Authored mod artwork and sounds are tracked.
