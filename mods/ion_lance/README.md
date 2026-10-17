# Ion Lance

API 1 package, version 1.1.0. Enable it in Mods at the main menu and apply the selection. This package has no mod dependencies.

Selectable reusable special. A brief beam hits every air or ground enemy in the column ahead of your ship. Aim the column, then use Fire or Special while selected. No ammunition is consumed.

Buy **Ion Lance** for **425,000 credits**; carry at most 1. Select it through Inventory or the Cycle control when it is a special weapon.

`ion_lance:projectile`: 8 damage, speed 12, 14-tick cooldown, `beam` behavior.

## Feedback

The actual gameplay renderer draws a **2px-wide column** from the top of the playfield to the pilot for the existing two beam ticks. It does not draw the supplied 4×32 projectile PNG in that path; that asset and its declaration are retained. Damage 8 per beam tick, 14-tick cadence, column aiming and penetration are unchanged. One compact 2-tick contact arc per projectile, 3-tick flash spacing and 6-tick impact-audio spacing replace repeated explosions/audio at every column target. Fire/impact volume is 70/46. Price stays 425,000.

Only declared display sizing, cosmetic hit commands and playback levels/priorities change. No PNG/WAV pixels or samples, equipment icon dimensions, projectile collision rules, damage, cooldown, offsets, targeting, ammunition, capacity, controls or prices are changed. No new muzzle explosion or persistent trail is emitted. Normal original enemy deaths and terrain-destruction effects remain engine-controlled.

The three rapid weapons retain their prior burst/hit counters and reset only their cosmetic tick/projectile gates when mission ticks restart, accepting older saved script state without new fields. This version changes the package save pin; existing pilot compatibility confirmation remains the normal mod mechanism.

## Validation and history

See the [current Iron Coast retune results and limits](../../docs/iron-coast-retune.md). Package-local acceptance reports, validation results and retained test sources describe pre-retune 1.0 behavior unless a result explicitly identifies the newer package and runner. They remain historical material, not current playthrough guarantees.
