# Iron Coast Command Cruiser

Independent version 1.0.0 enemy package for mod API 1. Enable/disable it from the in-game Mods screen and use it in any mission through `iron_coast_boss:unit`. Iron Coast mission 1 supplies placements and completion objectives; this package does not add a mission or override base content.

Airborne command cruiser enters at 2 pixels/tick, settles at y24 and patrols x80..144 indefinitely. It fires a fan of three 3 damage shells every 54 ticks. A standard pilot can destroy it with starter guns; it stays in their firing corridor.

Logical collision canvas `96×64`, top-left anchor `(0,0)`, health `160`, reward `1800` credits, firing interval `54` simulation ticks. The engine halves boss health on difficulties 0/1; difficulty 2/3 uses the declared health. SD mode uses `art/unit-sd.png`; enable HD art in Settings for `art/unit-hd.png`. The HD canvas is 8× logical resolution and bypasses automatic ScaleNx. Projectile artwork has an 8×8 logical canvas and an independent 64×64 HD version.

The boss uses two registered frames (idle/amber charged); the scout and turret use stable single frames. All supplied variants stay on the same canvas and anchor. `art-qa.json` records transparency bounds and, for the boss, animation silhouette overlap.

Enemy deaths increment the current mission objective `iron_coast_boss:defeated`. Persistent script `destroyed`, `hits` and `shots` counters are statistics; current-mission objectives reset when the mission restarts. Callbacks guard retired entities and use deterministic simulation data. No wall clock or unseeded random input enters the scripts.

Generated PNG masters, SD/HD strips, previews and WAV sounds are included in Git. Original reference images under `art/source/` are excluded. Exact built-in imagegen prompts are in `prompts/`, with source IDs and generated-image provenance in `provenance.json`.

To rebuild derived artwork from supplied generated masters and regenerate audio, install Pillow and run `python3 build_assets.py`. To regenerate only audio with the Python standard library, run `python3 build_assets.py --audio-only`. WAVs are original procedural mono 16-bit PCM at 22050 Hz; `audio-recipe.json` records deterministic seeds, sizes and hashes. The art pipeline resizes and assembles supplied images; it does not redraw them.

Validate from the repository root: `cargo run -- --mods examples/mods --validate-mods iron_coast_boss`. Synthetic behavior and save/replay tests: `cargo test --test enemies_mods`. Verify shipped artwork locally: `cargo test --test enemies_mods shipped_enemy_assets_are_valid_and_aligned`.
