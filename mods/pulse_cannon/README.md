# Pulse Cannon

API 1 package, version 1.1.0. Enable it in Mods at the main menu and apply the selection. This package has no mod dependencies.

Always-equipped primary upgrade. Fires paired pulses at air and ground targets alongside your other primary guns. Every third burst adds two angled shots. Hold Fire; no ammunition is consumed.

Buy **Pulse Cannon** for **185,000 credits**; carry at most 1. Select it through Inventory or the Cycle control when it is a special weapon.

`pulse_cannon:projectile`: 4 damage, speed 8, 9-tick cooldown, `straight` behavior.

## Feedback

Projectile files remain 8×12 SD and 32×48 HD, displayed on a proportional **4×6 logical canvas** (previously 8×12). The point collision, 8px/tick speed, 4 damage, paired offsets, 9-tick cadence and third-volley spread are unchanged. A hit uses a compact 4px contact arc for 2 ticks (86ms), with one flash per projectile and at least 3 ticks between flashes; impact audio is limited to one event per 6 ticks. Fire/impact volume is 72/50. The price remains 185,000 because damage, range and utility are unchanged.

Only declared display sizing, cosmetic hit commands and playback levels/priorities change. No PNG/WAV pixels or samples, equipment icon dimensions, projectile collision rules, damage, cooldown, offsets, targeting, ammunition, capacity, controls or prices are changed. No new muzzle explosion or persistent trail is emitted. Normal original enemy deaths and terrain-destruction effects remain engine-controlled.

The three rapid weapons retain their prior burst/hit counters and reset only their cosmetic tick/projectile gates when mission ticks restart, accepting older saved script state without new fields. This version changes the package save pin; existing pilot compatibility confirmation remains the normal mod mechanism.

## Validation and history

See the [current Iron Coast retune results and limits](../../docs/iron-coast-retune.md). Package-local acceptance reports, validation results and retained test sources describe pre-retune 1.0 behavior unless a result explicitly identifies the newer package and runner. They remain historical material, not current playthrough guarantees.
