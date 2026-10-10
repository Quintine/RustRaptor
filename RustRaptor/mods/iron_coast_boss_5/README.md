# Cinder Hammer

An independent boss mod for Iron Coast mission 5, **Cinder Docks**. The furnace
gunship patrols persistently at the top of the combat area. A pressure-warning
sound precedes three molten projectiles fired six simulation ticks apart. The
center mortar travels vertically; the two plasma rounds spread outward.

- Enemy: `iron_coast_boss_5:unit`; health 160, reward 1,800, logical size 96×64.
- Mortar and plasma: damage 3, speed 4; a 54-tick attack cycle.
- Death objective: `iron_coast_boss_5:defeated`, incremented only on actual death.
- Manifest API 1, package version 1.0.0, no dependencies or overrides.

The package never completes a mission itself. A mission must spawn the enemy,
declare this package as a dependency, and require its death objective. Each
enemy instance stores its own attack clock and patrol direction in serializable
Rhai state. Dead or removed enemies cannot issue attacks or movement commands.

SD PNGs are derived from the same transparent generated masters as the 8× HD
PNGs. Both modes retain the same logical canvas and collision dimensions.
`art/preview.png` shows the HD hull and exact SD silhouette enlarged for review.
The generation prompts are in `prompts/`; `provenance.json` records tool mode
and source hashes. All artwork and audio belong in Git with this mod.

Run `python3 build_assets.py` to reproduce the resized art and synthesized mono
22,050 Hz, 16-bit PCM warning, shot and destruction sounds. Python and Pillow
are required. `audio-recipe.json` and `art-qa.json` record file hashes and checks.

Run `cargo test --locked --manifest-path validation/Cargo.toml` from this folder
for five asset-independent checks of attack timing, multiple-instance state,
save serialization, dead-entity guards, patrol turns, actual simulation
persistence, rewards and the single death objective. The simulation test also
validates the real package-local PNGs and WAVs.
