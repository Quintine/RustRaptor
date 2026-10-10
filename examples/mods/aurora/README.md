# Aurora Field Trials

This API v1 example adds a scripted pulse cannon, a repair pickup, weaving drones, a guardian, a mission and a campaign. It references the player's installed original sprite catalog; no game artwork is included.

From the repository root:

```sh
cargo run --no-default-features -- --mods examples/mods --validate-mods aurora
cargo run --no-default-features -- --mods examples/mods --enabled aurora \
  --headless aurora:field_trials --ticks 700
```

To play, start the Rust engine with `--mods examples/mods`, enable Aurora in **Mods**, apply the selection at the main menu, create a separate pilot and choose **Aurora Field Trials**. The mission equips its cannon on the first simulation step. Keep existing pilots' required mod sets available.

Content IDs intentionally separate the inventory item `aurora:pulse_cannon` from its projectile `aurora:pulse_projectile`. The scripts demonstrate `on_fire`, `on_hit`, `on_spawn`, `on_tick`, `on_death`, `on_pickup`, `on_use`, `on_mission_start` and `on_mission_end`. See `docs/modding-api.md` for the complete API and compatibility rules.
