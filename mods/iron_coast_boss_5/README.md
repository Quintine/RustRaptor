# Iron Coast Cinder Hammer

API 1 package, version 1.0.1. Enable it in Mods at the main menu and apply the selection. This package has no mod dependencies.

Enemy `iron_coast_boss_5:unit` is an airborne boss with **400** nominal health and a **96×64** logical canvas. Actual destruction awards 1,800 credits. The existing World rule halves boss health, rounded up, on Training and Rookie. SD and HD use the same logical body.

Three staggered furnaces / converging outer pair / locked mortar. Each life has three health phases (above two-thirds, at/below two-thirds, at/below one-third of its actual spawn health). Every phase change restarts a full warning. Brief 8-pixel, 8-tick anchored charge arcs and existing quiet audio precede the salvo; the warning and short burst hold position, then the boss recovers into a bounded lateral patrol. Gun positions follow the existing artwork. No homing retarget occurs after aim is locked.

Warning leads are 18 / 16 / 14 / 12 ticks for Training / Rookie / Veteran / Elite. Recovery leaves a new approach opportunity; watch the charge cue and move into the opening before the volley.

Only actual death increments `iron_coast_boss_5:defeated`; escape or time passing grants no objective credit. This enemy package does not decide mission completion. Its existing art, audio, generation provenance and asset recipes are retained.

## Validation and history

See the [current Iron Coast retune results and limits](../../docs/iron-coast-retune.md). Package-local acceptance reports, validation results and retained test sources describe pre-retune 1.0 behavior unless a result explicitly identifies the newer package and runner. They remain historical material, not current playthrough guarantees.
