# Rust rewrite milestones

The C++ engine remains playable and retained as a reference. The Rust engine runs independently alongside it on branch `codex/rust-rewrite`. Both are selectable through `play.sh`. Original catalog/reference assets remain ignored; authored mod images and sounds are tracked in Git.

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

## Acceptance gates

1. **Foundation and complete playable first mission:** verify the entire mission through its boss, damage, rewards, collision/order and RNG against the rebuilt reference. Short replay equality is evidence, not completion of this gate.
2. **Complete game:** verify all 27 waves and four difficulties, equipment, training/campaign progression, cinematics, demos, menus and legacy imports.
3. **Modding release:** finish lifecycle/error/save acceptance and stabilize API version 1.
4. **Visual completion and cutover:** approve complete sprite sequences, check palette/layer/clipping/seam fidelity at 1080p and measure display performance. Make Rust the default only after preceding gates pass.

Not all gates have passed. See [validation instructions](docs/rust-rewrite.md) and [HD coverage](docs/hd-art.md). Online mod distribution, an editor, total conversions, external MIDI/SoundFonts and additional desktop targets remain outside scope.

## New content

Separate agents are building Iron Coast mission 1, three individual weapon mods and three individual enemy mods using the public API. Each package will ship local SD/HD artwork and procedurally generated sound effects, with definitions, scripts, images and sounds tracked together in Git. These packages remain in development until validation and play tests pass.
