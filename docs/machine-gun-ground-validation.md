# Default machine gun and ground collisions

The original Forward Guns remain an air-and-ground weapon: two banked muzzle
positions, one damage per round, a two-step firing interval and the original
8-to-16 projectile acceleration. They do not require another selected weapon.

The confirmed compatibility defect was in JSON mission terrain. Original guns
used the native eight-row collision window even when a mod map was displayed
at a different position. Their terrain damage also bypassed destruction: a
two-health test tile reached minus 52 health without exploding or paying its
reward. JSON terrain now uses its displayed row coordinates and completes
destruction immediately, just as mod projectile terrain damage does. This
includes short maps, continued scrolling and optional replacement artwork.
Destroyed tiles cannot absorb more shots or award their reward again. Their
destruction emits the original positional ground-explosion sound.

Original mission terrain keeps its delayed explosion, neighbor damage and
replacement-art timing. Seven portable regressions in
`tests/machine_gun_ground.rs` cover ground enemy damage/rewards, one-time terrain
destruction and sound, native delayed destruction, short maps, continued
scrolling, offscreen rejection and optional replacement artwork. The 15
existing gameplay checks, nine enemy package checks and nine Breakwater mission
checks also pass. After the correction, the complete 1,889-step native DEMO1
trace still matches every recorded enemy, projectile, player and RNG snapshot.

The local original-data test isolates actual enemy definitions, movement,
artwork and callbacks in a quiet test mission. It uses a fresh pilot, only the
default guns and ordinary mouse-position/fire input; it never injects
projectiles, changes health or grants equipment. It checks classic non-boss
ground units from the original first mission and the Iron Coast turret, depot,
relay, convoy and foundry, including their kill rewards.

That local combat check passed for all ten definitions (five classic and five
Iron Coast), each starting with 75 shield and 10,000 credits. The 90-health
foundry was destroyed in 99 steps with 71 shield remaining. Relay and convoy
shield recovery came from their real destruction callbacks. The optional
`RAPTOR_GROUND_REPORT` output records each unit's health, kill timing, shield and
reward; this run wrote `.reference/machine-gun-ground.json` outside Git.
Package PNG/WAV decoding remains covered by the separate mod validator; this
collision test loads the actual definitions, logical canvases and Rhai sources.

Run the portable checks with:

```sh
cargo test --locked --test machine_gun_ground --test gameplay
```

After campaign package files are stable, run the local original-data check with:

```sh
RAPTOR_TEST_DATA=../data cargo test --locked --test machine_gun_ground \
  real_forward_guns_damage_classic_and_iron_coast_ground_units -- --ignored
```

Commands above run from `RustRaptor/`. Set the usual local SDL library path
when needed. The native reference comparison is the ignored
`complete_demo_1_matches_every_reference_gameplay_snapshot` test in
`tests/campaigns.rs` and reads the untracked original catalog/reference trace.
