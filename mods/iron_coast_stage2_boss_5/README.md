# Skybreaker — Black Tide boss 5

Independent local enemy mod `iron_coast_stage2_boss_5:unit`; no dependencies, no item
or mission overrides. Enable it alone in **Mods** for other content to spawn it.
It has no standalone mission; `iron_coast_stage2_mission_5` supplies its encounter.

300 health at difficulties 2/3, 150 at 0/1; 6,000-credit actual-death reward.
Its logical canvas is 112×56, with a stable padded transparent
SD PNG and a 4× HD PNG. It is airborne.
Both artwork modes use the same collision dimensions. It enters the y 24 band
and patrols horizontally at 1px/tick over x 80..136.
It remains until killed rather than scrolling or timing out.

Each instance has its own serializable attack clock and actual starting-health
snapshot. The 84-tick cycle warns at age 36,
fires staggered outward left/right damage 3 shells at ages
50/58, then below half starting health adds
an aimed damage 4 center shot at age 66. Speeds are 4/3 respectively;
the center aim is bounded to ±2 horizontal velocity. One artwork frame is used;
the attack pattern and warning identify the phase. There is no native default
projectile or legacy movement. Projectiles reference original enemy-shell art.

Only actual death increments `iron_coast_stage2_boss_5:defeated`, clears instance state
and plays the destruction cue. The boss never completes a mission, changes
inventory or awards a separate scripted credit bonus. Removed/dead units emit
no ghost shots. Simultaneous instances keep independent clocks; new spawns
remove stale clocks from a previous mission and reset reused IDs safely.

[`provenance.json`](provenance.json) binds the genuine built-in image generation
request and untouched `sources/raw-v1.png`. Whole-canvas proportional fitting,
resampling and ordinary-palette SD conversion are the only sprite derivatives.
Original reference sheets remain external, recorded by path and hash.
[`tools/build_assets.py`](tools/build_assets.py) reproduces SD/HD art and the
original 22050Hz PCM16 warning, cannon and death cues. It reads only bundled
RustRaptor `data/misc/PALETTE_DAT`. No third-party recording was used.

Validation from RustRaptor:

```sh
cargo run --release --locked --no-default-features -- --data data --mods mods --validate-mods iron_coast_stage2_boss_5
CARGO_TARGET_DIR=target cargo test --locked --manifest-path mods/iron_coast_stage2_boss_5/validation/Cargo.toml --lib
```

Four portable tests cover warning/attack order and command bounds,
serialized continuation and independent clocks, dead-unit guards, restart
flags and one-time mission bonuses, plus actual World boss persistence through
600 ticks, relative phase transitions at all four difficulties, genuine lethal
damage, one death reward/objective and 120 ticks without ghost fire. The local
real-catalog acceptance runner checks the complete associated mission, full
inventories and replays. Actual indexed SD/HD artwork and all three cues were
checked via Rust decoding/mixing; live aggregate-scene captures are separate.
