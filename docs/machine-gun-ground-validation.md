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

The October 11 follow-up expands that check to all 110 distinct non-boss ground
enemy definitions referenced by the 27 original maps, plus those five Iron
Coast units. All 115 can take damage from the default guns. The original ten
cases still require destruction and the exact reward. Additional cases require
damage, rather than treating disappearance as a kill: moving units can escape,
and the deliberately aggressive secret enemies can kill a starter pilot. Of
the 115 range cases, 91 were actually destroyed. Four needed a second ordinary
input strategy: a closer firing lane with movement lead. The report retains
both attempts. This proves collision eligibility, not that an unequipped pilot
can defeat every original enemy from a stationary firing lane.

Buildings, parked cars and other map props are usually terrain definitions,
rather than enemies. A separate local test covers every one of the 889 unique
destructible terrain definitions used by the original maps, with actual health,
replacement art and rewards. All explode, settle and pay once in the native
collision window. One definition starts with negative health and therefore
explodes without a hit, as it does in the classic source. Original terrain
requires health below zero, rather than exactly zero, before its deferred
explosion; the follow-up does not change that rule.

Two focused tests cover the reported Bravo Sector waves 6 and 7. They keep each
complete original layout and advance ordinary simulation steps to the actual
displayed positions. All 17 destructible occurrences in rows 130 through 149
are destroyed by default-gun input. Examples in wave 7 include building `1045a`
at row 143, column 6 (25 health, 100 credits), and small vehicle/debris tiles
`1040c`, `1040a`, `1040e` and `1040d` (3–5 health). Nearby industrial/fence tiles
`1045c` through `1045f` remain intact: their original intact and replacement IDs
are identical, and the classic `TILE_IsHit` deliberately rejects them.

The spawn-path test retains the native tick, placement, dimensions, movement
and full terrain for the four ordinary early ground emplacements. With capped
four-pixel mouse movement and the default guns, the wave 6 bonus emplacement
and turret die at ticks 565 and 648; wave 7's two turrets die at ticks 392 and
744. All runs retain 75 shield. The report records each original spawn position,
the first gun-hit coordinates, current logical bounds and prior interpolation
position. Every first hit is inside the displayed enemy's current bounds;
interpolation differs by the expected single vertical pixel.

No further native collision defect was reproduced, so this follow-up changes
tests and documentation only. The original point collision rules, update order,
terrain delay and deliberately static scenery remain intact. These simulation
checks do not independently prove every HD image's visible footprint or the
desktop presentation; the exact reported screenshot would still be useful if
the player sees a destructible object that differs from these examples.

The detailed JSON reports and original map contact images are local under
`.reference/ground-investigation/` in the parent project directory, outside the
Git root. The runtime catalog is tracked in `data/`. Their report variables are
`RAPTOR_GROUND_REPORT`, `RAPTOR_TERRAIN_REPORT`, `RAPTOR_EARLY_TERRAIN_REPORT` and
`RAPTOR_EARLY_SPAWN_REPORT`.

Run the portable checks with:

```sh
cargo test --locked --test machine_gun_ground --test gameplay
```

After campaign package files are stable, run all four local original-data checks with:

```sh
RAPTOR_TEST_DATA=../data cargo test --locked --no-default-features \
  --test machine_gun_ground -- --ignored
```

Commands above run from `RustRaptor/`. Set the usual local SDL library path
when needed. The native reference comparison is the ignored
`complete_demo_1_matches_every_reference_gameplay_snapshot` test in
`tests/campaigns.rs` and reads the untracked original catalog/reference trace.
