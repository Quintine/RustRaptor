# Stormwall artwork provenance

Both source masters were generated with the built-in image generation tool on 2026-10-10. Exact prompts and input roles are recorded in `prompts.json`; neither call supplied an existing image. Terrain and briefing use the Iron Coast naval/industrial palette and Raptor-inspired visual language. The generated fighter is briefing artwork, not a replacement for the original player sprite.

The source files remain alongside the packaged variants. `build_assets.py` resizes, palette-quantizes and slices these images deterministically; it does not paint replacement art. SD conversion uses the original VGA palette from the local catalog. The 216 terrain pairs share a full-map resampling pass and a 24-row forward/reflected period to avoid independently filtered tile edges. Source dimensions and SHA-256 hashes, SD palette checks, seam checks and audio hashes are in `asset-report.json`.

The four WAV cues are new deterministic procedural synthesis, mono PCM16 at 22,050 Hz, with seeded noise for the warning tones. They contain no sampled original recordings. Their notes, envelopes and seeds are defined in `build_assets.py`.

The distinct Stormwall Arsenal sprite, shell and boss warning sounds belong
to the independent `iron_coast_boss_4` package and have their own provenance.
The mission also references six original aircraft definitions directly; their
original sprites and path data remain in the external catalog. No image
generation replaces those classic enemy definitions here. The original
Coastal Steel MUS composition belongs to `iron_coast_music` and plays through
the Rust synthesizer.
