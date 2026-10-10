# Saltbreaker

Standalone API 1 mod, version 1.0.0, with no dependencies. Saltworks Convoy requires this package and references `iron_coast_boss_3:unit` and the death objective `iron_coast_boss_3:defeated`.

The armored twin-fan escort enters vertically, then patrols between x=80 and x=144 at y=24. Its logical canvas remains 96×64 in SD and HD. It has 160 health and pays 1,800 credits when destroyed. Every 54 simulation steps after arrival, one nose cannon fires two three-damage shells. The cannons alternate and each warning sounds nine steps before firing. Shells move four pixels vertically, with a second shell angled one pixel toward the center. The boss never completes a mission or pays a separate scripted victory reward.

Every entity retains its own direction, clock and cannon side in serializable script state. Dead or absent entities cannot move or fire. A duplicate death callback cannot count twice. A new spawn resets its lifecycle even when a lethal collision precedes its queued callback, so restored state and reused entity IDs cannot suppress replay objectives. Mission-start objective reset and victory gating belong to the mission mod.

Generated master images, aligned SD/HD PNGs and synthesized mono 16-bit 22,050 Hz WAVs are included. `prompts/` contains the exact built-in image generation prompts, `provenance.json` records the sources, and `build_assets.py` reproduces derived artwork and audio. Use `--audio-only` to regenerate sounds without Pillow. `art-qa.json` records logical dimensions and clipping checks; `audio-recipe.json` records non-silent PCM peaks and hashes.

Validate content with `raptor-rust --data data --mods RustRaptor/mods --validate-mods iron_coast_boss_3` from the repository root. `validate.rs` is a package-local acceptance probe compiled against the RustRaptor library and serde_json. It checks cannon alternation, warning timing, independent entities, restoration, patrol bounds and death objectives. A real World regression kills the boss through collision before queued callbacks, restores script checkpoints and repeats three lifecycles with the same entity ID; each must count and pay exactly once without firing after death.
