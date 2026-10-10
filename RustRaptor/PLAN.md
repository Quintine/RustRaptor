# Rust rewrite milestones

The independent Rust engine is the default launcher on branch `codex/rust-rewrite`. Its source, mods, schemas, tests and documentation live in `RustRaptor/`. The retained C++ checkout is optional reference material. Original catalog/reference assets remain ignored; authored mod images and sounds are tracked in Git.

The registered game has three sectors with nine waves each. Archive slots are asset containers, not five independent campaigns.

## Implemented

- Checked asset decoders, typed namespaced registries and original content registration.
- Independent integer simulation at 70/3 Hz; deterministic RNG and SDL2 input/interpolated indexed rendering.
- Original / Scale2x / Scale3x / Scale4x modes, joined terrain filtering, sharp bitmap text and separate derived cache.
- Rust MUS, GENMIDI FM synthesis and digital DSP mixing, with native PCM comparisons.
- Menus, shop, equipment, mission selection, pilot slots, atomic saves, read-only legacy import and original AGX cinematics.
- Local mods, dependencies/conflicts, explicit overrides/priority/hashes, bounded deterministic Rhai hooks and transactional commands.
- In-game enable/disable and pending changes, save diagnostics, schemas, validation CLI and scripted Aurora example.
- Optional source-hashed HD loader/setting; one accepted player-frame proof with original fallback.
- C++/Rust replay recording and comparison tools, synthetic tests and local-original-data checks.

## Validation and remaining work

1. **Playable first mission:** fresh pilots win through the boss at difficulties 1 and 2 using deterministic input and predictive steering. The complete 1,889-step original demo matches all captured native gameplay fields. Wider ordinary playtesting remains useful.
2. **Complete game coverage:** all 27 waves complete at each of four difficulties under an assisted fixture; all original weapons, training/campaign progression, legacy import and cinematics have checks. These fixtures do not establish exhaustive native parity or every menu/save route.
3. **Mod API version 1:** dependencies, overrides, script limits/errors, atomic enable/disable and incompatible saves have regressions. The bundled mission, weapons and enemies validate and have controlled playthroughs.
4. **Visual treatment:** complete sampled sprite sequences, palette shadows and joined terrain pass local checks; the desktop renderer has SD/HD 1080p measurements. The base-game HD remaster is partial. Rust is the default at the user's request; finishing every reference comparison is not a prerequisite to playing it.

See [validation instructions](docs/rust-rewrite.md) and [HD coverage](docs/hd-art.md) for the evidence and its limits. Online mod distribution, an editor, total conversions, external MIDI/SoundFonts and additional desktop targets remain outside scope.

## New content

Separate agents built Iron Coast mission 1, three individual weapon mods and three individual enemy mods using the public API. Each package ships local SD/HD artwork and procedurally generated sound effects, with definitions, scripts, images and sounds tracked together in Git. The mission dependencies and two controlled victories are documented in [Iron Coast](docs/iron-coast.md).
