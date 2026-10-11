# Iron Coast II: Undertow

A standalone boss content package for Black Tide. Enable this package directly
in **Mods**, or enable its mission to select it as a dependency. It adds
`iron_coast_stage2_boss_2:unit` and no campaign, overrides or equipment.

The surfaced/ground target has 400 health, awards 16,000 credits and retains
a 48×80 logical collision canvas in SD and HD. It remains reachable until killed.
Its two phases change at half of that life’s actual spawn health on every
difficulty, with a new attack timer and twelve ticks of audible warning before
every volley. Difficulty 0/1 uses the engine’s half-health boss rule; 2/3 uses
the nominal health above. Cadence is 76 / 62 simulation ticks
(first/second phase), at the original 70/3 Hz. Every projectile is hostile and
leaves deliberate escape lanes; no phase is invulnerable.

Actual death increments `iron_coast_stage2_boss_2:defeated` once. It does not finish a mission.
Per-life cursors are removed on death and pruned on spawn/replay; early kills
before the queued spawn callback still register the real death.

Artwork is a genuine new builtin imagegen master, with full alpha and identical
SD/HD canvas alignment. `build_assets.py` reproduces palette-aware SD art, 4× HD
and deterministic PCM WAV effects from the tracked raw masters. Projectile art
is the same newly authored micro-missile independently included with each boss.
See [generation provenance](generation-provenance.json) and
[asset recipe/report](asset-report.json). Original Raptor style references and
local review captures are external.

From `RustRaptor/`:

```sh
cargo run --locked --no-default-features -- --mods mods --validate-mods iron_coast_stage2_boss_2
CARGO_TARGET_DIR="$PWD/target" cargo run --locked --release --manifest-path mods/iron_coast_stage2_boss_1/validation/Cargo.toml -- --boss-only
python3 mods/iron_coast_stage2_boss_2/build_assets.py
```

The real-catalog standalone kill, every-difficulty phase boundaries, early and
duplicate hook checks and native Mixer/mute observations passed. Exact results
and scopes are recorded in `acceptance-report.json`.

Asset recipes use Python 3 with Pillow. The game uses the shipped PNG and WAV files.
