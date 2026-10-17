# Iron Coast II — Stormglass

API 1 package, version 1.1.0. Enable it in Mods at the main menu and apply the selection. This package has no mod dependencies.

Enemy `iron_coast_stage2_boss_3:unit` is a ground boss with **240** nominal health and a **104×72** logical canvas. Actual destruction awards 2,400 credits. The existing World rule halves boss health, rounded up, on Training and Rookie. SD and HD use the same logical body.

Stormglass now uses slow rail sentry alternating one active turret. Each charge locks its aim and stops movement until its burst finishes. Difficulty changes cadence and bounded shot count; health, reward, damage and all artwork/collision canvases remain unchanged. On an API without event.difficulty the documented fallback is difficulty1.

Only actual death increments `iron_coast_stage2_boss_3:defeated`; escape or time passing grants no objective credit. This enemy package does not decide mission completion. Its existing art, audio, generation provenance and asset recipes are retained.

## Validation and history

See the [current Iron Coast retune results and limits](../../docs/iron-coast-retune.md). Package-local acceptance reports, validation results and retained test sources describe pre-retune 1.0 behavior unless a result explicitly identifies the newer package and runner. They remain historical material, not current playthrough guarantees.
