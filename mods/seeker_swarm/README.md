# Seeker Swarm

API 1 package, version 1.1.0. Enable it in Mods at the main menu and apply the selection. This package has no mod dependencies.

Selectable reusable special. Fires three homing missiles at air or ground enemies. Hits scatter fragments into up to two nearby enemies. Select it in Inventory or cycle specials, then use Fire or Special.

Buy **Seeker Swarm** for **285,000 credits**; carry at most 1. Select it through Inventory or the Cycle control when it is a special weapon.

`seeker_swarm:projectile`: 6 damage, speed 6, 18-tick cooldown, `homing` behavior.

## Feedback

The **8×16 logical projectile canvas is retained**. Its visible SD silhouette is only 3×14; proportional downsampling can skip the thin centerline, so reducing it would harm readability. The original SD/HD PNG bytes remain unchanged. Three 6-damage missiles, 6px/tick speed, 18-tick cadence, homing and two-neighbor fragmentation are unchanged. Contact feedback uses a compact 4px arc for 2 ticks rather than a continuing explosion; coincident missile hits share the 3-tick flash and 6-tick audio gates. Fire/impact volume is 76/58. Price stays 285,000.

Only declared display sizing, cosmetic hit commands and playback levels/priorities change. No PNG/WAV pixels or samples, equipment icon dimensions, projectile collision rules, damage, cooldown, offsets, targeting, ammunition, capacity, controls or prices are changed. No new muzzle explosion or persistent trail is emitted. Normal original enemy deaths and terrain-destruction effects remain engine-controlled.

The three rapid weapons retain their prior burst/hit counters and reset only their cosmetic tick/projectile gates when mission ticks restart, accepting older saved script state without new fields. This version changes the package save pin; existing pilot compatibility confirmation remains the normal mod mechanism.

## Validation and history

See the [current Iron Coast retune results and limits](../../docs/iron-coast-retune.md). Package-local acceptance reports, validation results and retained test sources describe pre-retune 1.0 behavior unless a result explicitly identifies the newer package and runner. They remain historical material, not current playthrough guarantees.
