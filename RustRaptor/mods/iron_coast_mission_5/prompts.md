# Cinder Docks artwork and audio provenance

The three `art/*-source-hd.png` masters are authored for this mission using the
built-in imagegen tool. Exact prompts are in `prompts.json`; no API key or CLI
image generation was used. Terrain uses the existing Mission 1 generated terrain
as its material reference and a locally decoded original Raptor terrain tile as
its palette reference. The original tile remains outside Git. The briefing and
furnace station use the new Cinder Docks terrain as a style reference.

`build_assets.py` performs deterministic full-canvas palette conversion,
resampling and tile slicing. SD terrain is quantized before slicing so neighboring
tiles share one palette pass. A reflected second half makes both vertical repeat
boundaries match exactly. Logical dimensions stay separate from HD dimensions;
the station has a transparent 48×48 logical canvas and 192×192 HD canvas.

The slag projectile reuses copies of the authored `iron_coast_boss` projectile
SD/HD artwork. The coolant icon reuses copies of the authored Mission 1 repair
SD/HD artwork. These copies are distributed locally with this mission so no
cross-package filesystem paths are needed. They are generated mod artwork,
not original game assets. Their hashes are recorded in `provenance.json`.

All nine WAV cues are synthesized locally with the deterministic oscillator,
seeded noise, envelopes and PCM encoder in `build_assets.py`. They are mono
22,050 Hz signed PCM16, contain nonzero samples and do not clip. The procedural
source, generated PNG/WAV outputs, exact prompts and reports are included in Git.
No external audio samples are used.
