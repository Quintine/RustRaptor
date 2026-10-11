# Stormwall Arsenal

An independent Iron Coast boss mod for mission 4. The wide aerial arsenal carries two massive downward-facing batteries, red storm-warning stripes and four rear engines. It has its own true transparent SD/HD boss and shell artwork, alarm, cannon and destruction sounds.

Enable `iron_coast_boss_4` to register the boss; the Stormwall mission selects it as a dependency. This package has no dependencies, overrides or mission definitions.

| Definition | ID |
| --- | --- |
| Enemy | `iron_coast_boss_4:unit` |
| Projectile | `iron_coast_boss_4:projectile` |
| Death objective | `iron_coast_boss_4:defeated` |
| Sounds | `iron_coast_boss_4:warning`, `iron_coast_boss_4:shot`, `iron_coast_boss_4:death` |

The 96×64 boss enters at two logical pixels per simulation tick, holds y=24 and patrols x=80–144. Every 54 ticks it pauses for 12 ticks with a two-note arming alarm, then fires three 3-damage shells at speed 4. The third shell alternates between batteries. Each boss stores its own direction and attack age, so concurrent bosses remain independent. Ordinary difficulty scaling applies to its 160 health; destruction awards 1,800 credits.

Actual death increments `iron_coast_boss_4:defeated` once and retires that entity's live state. A dead boss never keeps firing, and a fresh sortie safely resets reused entity IDs even when a lethal projectile hits before its queued spawn callback runs. The script does not declare mission success: the mission combines the death objective with its other targets.

`art/unit-sd.png` and `art/unit-hd.png` share a 96×64 logical canvas (HD is 384×256). `art/projectile-sd.png` and `art/projectile-hd.png` share an 8×8 logical canvas (HD is 64×64). Both use one static frame, consistent registration and preserved alpha. `art/preview.png` shows both modes. The first shell master is retained for provenance but is not loaded; v2 gives a readable SD core.

The built-in image generation tool supplied the artwork. Exact prompts are in `prompts/`, tool results and processing details in `provenance.json`, and image dimensions, bounds and hashes in `art-qa.json`. The package includes generated masters, runtime art and WAVs for Git tracking. Original catalog reference pixels are excluded.

`python3 build_assets.py` reproduces the SD/HD packaging and deterministic 22,050 Hz mono PCM16 sounds from saved masters. `audio-recipe.json` records seeds, nonzero peaks/RMS and hashes; no recordings or external sound downloads are used.

After building RustRaptor in release mode, run `python3 validate.py` for six tests through the real simulation and Rhai callbacks: warning timing and alternate batteries, independent multi-boss state, once-only destruction, saved state/RNG determinism, fresh sorties, lethal spawn-step hits with restored death state, duplicate death callbacks and persistent patrol bounds. Results are recorded in `acceptance-report.json`. The normal Rust mod validation CLI also validates this package independently.
