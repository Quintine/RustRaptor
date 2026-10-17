# Depth Charge

API 1 package, version 1.1.0. Enable it in Mods at the main menu and apply the selection. This package has no mod dependencies.

Ground/naval blast, 36px radius. Selectable reusable ground/naval special. Ctrl launches a slow charge; a real ground hit deals 72 damage and splashes at most three other ground enemies within 36 pixels (36 inner / 20 outer). Deliberate 2.06-second cadence; no air damage or ammunition consumed. Alt/Shift selects weapons; Space drops mega bombs.

Buy **Depth Charge** for **525,000 credits**; carry at most 1. Select it through Inventory or the Cycle control when it is a special weapon.

`iron_coast_depth_charge:projectile`: 72 damage, speed 6, 48-tick cooldown, `straight` behavior.

## Feedback

The unchanged 8×12 SD / 32×48 HD projectile files now display on a proportional **6×9 logical canvas**. Point collision, 6px/tick speed, 48-tick cadence, 72 damage, ground-only targeting, three-neighbor limit and 16/36px falloff remain unchanged. A real enemy hit shows one compact **16px / 15-tick** impact (0.64s) instead of the former 40px / 43-tick ground blast (1.84s); the visual is a contact marker, not a drawn damage-radius boundary. Fire/impact volume is 80/72. Price stays 525,000.

Only declared display sizing, cosmetic hit commands and playback levels/priorities change. No PNG/WAV pixels or samples, equipment icon dimensions, projectile collision rules, damage, cooldown, offsets, targeting, ammunition, capacity, controls or prices are changed. No new muzzle explosion or persistent trail is emitted. Normal original enemy deaths and terrain-destruction effects remain engine-controlled.

The three rapid weapons retain their prior burst/hit counters and reset only their cosmetic tick/projectile gates when mission ticks restart, accepting older saved script state without new fields. This version changes the package save pin; existing pilot compatibility confirmation remains the normal mod mechanism.

## Validation and history

See the [current Iron Coast retune results and limits](../../docs/iron-coast-retune.md). Package-local acceptance reports, validation results and retained test sources describe pre-retune 1.0 behavior unless a result explicitly identifies the newer package and runner. They remain historical material, not current playthrough guarantees.
