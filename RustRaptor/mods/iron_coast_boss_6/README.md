# Iron Crown boss

A standalone API 1 mod for the Iron Coast finale. It adds a new command
Dreadnought with broad armored wings and three forward cannon pods, matching
the industrial overhead style of the original game. The package has no mod
dependencies and does not replace any original or Iron Coast enemy definition.

- Enemy: `iron_coast_boss_6:unit`; health 160, reward 1800, air boss, logical 96×64.
- Weapon: `iron_coast_boss_6:projectile`; damage 3, speed 4, logical 8×8.
- Objective: every actual boss death increments `iron_coast_boss_6:defeated`.
- Entry: fly downward to y 24, then patrol between x 80 and x 144.
- Attack: every 54 simulation ticks, alternate a three-shell fan with two
  straight cannon lanes. A rising charging sound begins nine ticks before
  each volley. At 70/3 Hz this gives 0.386 seconds warning before a 2.314-second
  volley cycle. Charging creates no explosion effects.
- State: per-entity patrol direction, age and volley cursor; removed on death.
  Supports the finale's two staged bosses and simultaneous spawns. It never
  completes a mission directly or fires from retired entities.

Difficulty uses the engine's original boss health rule: definitions retain 160
health, and the two lower difficulty levels spawn bosses with 80 health.

`art/unit-sd.png` and `art/unit-hd.png` share one centered 96×64 logical canvas.
The HD texture is 768×512 (8×) and the SD version is derived from the same
transparent generated master. The cannon shell likewise has matching 8×8 and
64×64 versions. `art-qa.json` records bounds and source hashes. The supplied
alpha is preserved; runtime colors with alpha below 128 remain transparent.

The built-in imagegen tool generated both masters. Exact prompts live in
`prompts/`; `provenance.json` records their outputs. All authored images and
sounds belong in Git. Original sprite references remain outside this package.

Reproduce the deterministic sounds and SD/HD reductions with:

```sh
python3 RustRaptor/mods/iron_coast_boss_6/build_assets.py
```

`--audio-only` needs only Python's standard library. `audio-recipe.json`
records seeds, PCM properties and hashes. The sounds are non-silent PCM16
mono 22050 Hz charging, firing and destruction cues; no recordings are used.

Validate activation and lifecycle behavior using the production simulation:

```sh
CARGO_TARGET_DIR=RustRaptor/target cargo run --offline \
  --manifest-path RustRaptor/mods/iron_coast_boss_6/validation/Cargo.toml
```

The validation checks alternating patterns, warning timing, independent
entity state, serialized state restoration, death counter/reward behavior,
dead-enemy firing guards and two staged encounters on all four difficulties.
`validation-results.json` records the controlled outcomes. The complete
mission 6 mod runs separate campaign and balance checks with its other enemies.
