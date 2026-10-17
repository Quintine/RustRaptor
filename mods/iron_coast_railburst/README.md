# Railburst Cannon

API 1 package, version 1.1.0. Enable it in Mods at the main menu and apply the selection. This package has no mod dependencies.

Pierces up to 3 aligned targets. Selectable reusable special. Ctrl fires a fast rail slug at air or ground targets. A real hit penetrates up to two more enemies ahead within a narrow 24-pixel lane, with falling damage (42/32/22). Best against aligned armor; no ammunition consumed. Alt/Shift selects weapons; Space drops mega bombs.

Buy **Railburst Cannon** for **685,000 credits**; carry at most 1. Select it through Inventory or the Cycle control when it is a special weapon.

`iron_coast_railburst:projectile`: 42 damage, speed 16, 22-tick cooldown, `straight` behavior.

## Feedback

The unchanged 4×20 SD / 16×80 HD projectile files now display on a proportional **3×15 logical canvas**. Point collision, 16px/tick speed, 22-tick cadence, 42/32/22 damage, 24px penetration lane and 160px follow-through limit are unchanged. Each of at most three struck targets receives a short 8px, 2-tick cosmetic contact streak, instead of long air/ground explosions. Fire/impact volume is 80/66. Price stays 685,000.

Only declared display sizing, cosmetic hit commands and playback levels/priorities change. No PNG/WAV pixels or samples, equipment icon dimensions, projectile collision rules, damage, cooldown, offsets, targeting, ammunition, capacity, controls or prices are changed. No new muzzle explosion or persistent trail is emitted. Normal original enemy deaths and terrain-destruction effects remain engine-controlled.

The three rapid weapons retain their prior burst/hit counters and reset only their cosmetic tick/projectile gates when mission ticks restart, accepting older saved script state without new fields. This version changes the package save pin; existing pilot compatibility confirmation remains the normal mod mechanism.

## Validation and history

See the [current Iron Coast retune results and limits](../../docs/iron-coast-retune.md). Package-local acceptance reports, validation results and retained test sources describe pre-retune 1.0 behavior unless a result explicitly identifies the newer package and runner. They remain historical material, not current playthrough guarantees.
