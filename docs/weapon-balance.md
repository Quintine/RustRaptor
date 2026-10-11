# Shipped weapon prices and balance

The five independent weapon mods use the original game's credit scale. The first three
initial example prices of 6,500, 14,000 and 22,000 made reusable upgrades cheaper
than much weaker original equipment. The revised prices preserve their firing,
damage, scripts, sounds and artwork.

| Mod weapon | Price | Place in the original progression |
| --- | ---: | --- |
| Pulse Cannon | 185,000 | Just above the 175,600-credit Micro Missile primary upgrade. It adds similar sustained damage and also adds a spread burst every third volley. |
| Seeker Swarm | 285,000 | Above the 250,650-credit Mini Gun. Its three missiles track air and ground enemies and hits fragment into at most two nearby enemies. It remains below the 512,850-credit instant Turret. |
| Ion Lance | 425,000 | Below the Turret and the 950,000-credit Death Ray. Its lower damage per target trades against immediate hits and the ability to pierce several enemies in one column. |
| Lightning Cannon | 825,000 | Above the original 725,000-credit Pulse Cannon and below the 950,000-credit Death Ray. Its strong immediate forward hit can chain to three nearby enemies, but it needs an initial target in its aiming lane and the chain has a strict 48-pixel reach. |
| Lightning Shield | 155,000 | A supplementary primary below the 175,600-credit Micro Missile. It adds only a little damage and reaches roughly 12 pixels beyond the pilot's hull; its value comes from covering close airborne threats in every direction while the other guns fire. |

Pulse Cannon is always equipped and fires alongside other primary guns. Seeker
Swarm, Ion Lance and Lightning Cannon occupy the selected special slot and fire with Fire or
Special while selected. Lightning Shield is always equipped and pulses only while
Fire is held; it does not occupy the selected slot. All five are reusable, consume no ammunition and have
a maximum inventory count of one. Each equipment definition includes a shop
description stating these controls and its target behavior.

## Controlled damage observations

The local benchmark loads the original asset catalog and original registered
weapons, plus eight shipped weapon/enemy packages. Every weapon runs through
the real `World::step` simulation and real scripts at difficulty 2. Each scene
holds Fire for 700 steps, exactly 30 seconds at 70/3 Hz, against 32×32 fixtures
with 1,000,000 health. The pilot remains at the initial position with no other
weapons equipped. Ground fixtures use a test-only movement callback to cancel
the normal one-pixel terrain scroll after each collision pass.

The numbers below include travel delay and misses during that 30-second window.
They measure health lost per second, rather than nominal damage divided by
cooldown.

| Weapon | Price | Aligned air damage/s | Aligned ground damage/s | Air target 76 pixels to the right damage/s |
| --- | ---: | ---: | ---: | ---: |
| Original Forward Guns | 12,000 | 23.13 | 23.13 | 0 |
| Original Plasma Guns | 78,800 | 4.67 | 0 | 0 |
| Original Micro Missile | 175,600 | 23.07 | 23.07 | 0 |
| Original Mini Gun | 250,650 | 12.57 | 12.57 | 16.27 |
| Original Turret | 512,850 | 19.50 | 0 | 19.50 |
| Original Pulse Cannon | 725,000 | 38.50 | 38.50 | 0 |
| Original Death Ray | 950,000 | 80.00 | 80.00 | 0 |
| Original Forward Laser | 1,750,000 | 266.67 | 266.67 | 0 |
| Mod Pulse Cannon | 185,000 | 24.00 | 24.00 | 0 |
| Seeker Swarm | 285,000 | 23.40 | 23.40 | 23.40 |
| Ion Lance | 425,000 | 26.67 | 26.67 | 0 |
| Lightning Cannon | 825,000 | 41.60 | 41.60 | 0 |
| Lightning Shield | 155,000 | 0 | 0 | 0 |

The original forward laser's native beam damage pass reaches ground enemies
despite its historical air target metadata; the observations use its actual
behavior. The original turret selects airborne enemies. Original weapons retain
their native update and collision paths throughout this comparison.

Equipping Pulse Cannon with the starter Forward Guns produced 46.33 damage/s
against either aligned target, compared with 46.20 for Forward Guns plus Micro
Missile. Pulse therefore belongs beside that original primary upgrade, rather
than below the 12,000-credit starter guns. Scripted angled shots also reached a
second target in the cluster scene.

Seeker Swarm delivered 23.40 damage/s to an offset airborne or ground target.
In a tight three-enemy cluster, it delivered 23.40 to the primary target plus
7.80 to each of two neighbors: 39.00 combined. Its fragmentation is bounded;
it does not damage every enemy on screen.

Ion Lance delivered 26.67 damage/s to each of two vertically separated targets
in the same column: 53.33 combined. It delivered 80.00 combined across three
overlapping column targets. It dealt zero damage to targets outside its launch
column. It is a brief aimed beam, rather than a screen-wide attack.

Lightning Cannon fires every 18 ticks and hits the first target for 32 damage.
In a chain scene with 40 pixels between target centers, it delivered 41.60,
26.00, 15.60 and 10.40 damage/s to four distinct targets, for 93.60 combined.
A fifth neighboring target took zero damage. Each hop chooses the nearest
living, previously unhit target within 48 pixels of the previous hit; it can
chain through air and ground targets and never revisits a target. It missed an
isolated target 76 pixels to the right of its narrow forward acquisition lane.
Its 825,000-credit price reflects better single-target output than the original
Pulse Cannon plus bounded cluster utility, while staying below the Death Ray's
80.00 aligned damage/s. Cluster performance alone does not guarantee campaign
performance: spaced enemies break the chain and weak targets reduce its useful
damage through overkill.

Lightning Shield cannot reach the normal distant fixtures. Against a stationary
aircraft with its hull 28 pixels from the pilot's center, it delivered **5.87
damage/s**. The equivalent ground fixture took zero damage. Against five close
aircraft it dealt 5.87 to each of the four closest targets, for 23.47 combined,
and zero to the fifth. The 28-pixel distance is measured to the nearest point on
the enemy hull, so it reaches only about 12 pixels beyond the pilot's own hull.
Its 155,000-credit price treats this as supplemental coverage near the ship,
below the Micro Missile and mod Pulse Cannon upgrades. Its short reach requires
dangerous proximity, and it provides no protection from collisions or bullets.
Firing alongside Forward Guns preserves its 5.87 close-target damage/s; selecting
another special never disables it. Its pulses consume no equipment.

## Economy and limits

Stage 2 adds two reusable selected specials, measured separately through the
same real `World::step` and script path for 700 ticks (30 seconds).
**Railburst Cannon**, priced at **685,000**, delivered 44.80 damage/s to an
aligned air or ground target and 102.40 combined across its three-target
forward column. It dealt zero damage to off-axis fixtures. Its narrow alignment
requirement and finite penetration put it below Lightning Cannon's more flexible
chain utility. **Depth Charge**, priced at **525,000**, delivered 36.00 damage/s
to an aligned ground target and 74.00 combined in its bounded ground cluster.
Air and off-axis fixtures took zero damage. With starter guns, the corresponding
single-ground results were 67.93 and 59.13 damage/s. These prices reflect their
specialist roles; campaign missions do not loan or award either item.
The complete observations and fixture constraints are in
[Railburst](../mods/iron_coast_railburst/validation/balance.json) and
[Depth Charge](../mods/iron_coast_depth_charge/validation/balance.json).

Controlled first-mission runs starting with 100 energy and zero credits earned
42,775 credits at difficulty 1 and 59,025 at difficulty 2 with starter guns.
The in-game registration flow starts with 10,000 credits and 75 energy, matching
the original hangar setup. Compared with the latter controlled gross
reward, the first three prices represent approximately 3.13, 4.83 and 7.20 such payouts.
Lightning Cannon costs about 13.98 and Lightning Shield about 2.63 such payouts.
Repairs and other purchases increase the saving time; later missions have
different rewards. This comparison sets a progression tier and does not promise
an exact purchase mission.

Stationary fixtures favor perfect alignment and long-lived targets. They do
not establish equal campaign difficulty, measure moving-target accuracy,
account for overkill against weak enemies or quantify projectile travel time
against fast enemies. The benchmark also isolates weapons; real pilots can
combine several primaries with one selected special. These prices are concrete
initial balance choices, not an assertion that every loadout is equally strong.

Iron Coast Mission 1 intentionally supplies a free Pulse Cannon loan if the
pilot does not already own one. The mission returns the loan at its end while
preserving previously owned equipment. The trial therefore helps this mission
without granting a permanent shop upgrade or a repeatable resale reward.

## Reproduce

Run the local-only test from the repository root with the original catalog:

```sh
RAPTOR_TEST_DATA="$PWD/data" RAPTOR_BALANCE_REPORT="$PWD/.reference/weapon-balance.json" \
  cargo test --release \
  --no-default-features --test weapon_balance -- --ignored --nocapture
```

`RAPTOR_TEST_DATA` can override the catalog directory. The optional JSON report
records all 120 observations: seventeen weapons in six scenes, the three original
primary upgrade comparisons with Forward Guns, four additional proximity/chain
scenes for each lightning weapon, and four lightning/Forward Guns comparisons. Assertions
check all-target homing, column piercing, off-axis beam misses, target survival
and unchanged pilot shields. The test uses the Rust engine without SDL or C++.
The bundled original data is tracked; locally written reference reports stay outside Git. The portable
weapon tests additionally check range boundaries, chain gaps, repeated-hit
exclusion, kills, cooldown, absence of input, removed equipment, combined loadouts
and deterministic continuation.

The opt-in visual proof uses the actual package icons, original palette and
public arc renderer in SD and HD. It writes local, ignored captures:

```sh
cargo test --locked --no-default-features --test weapons_mods \
  lightning_mods_render_real_icons_and_discharge_arcs_in_sd_and_hd \
  -- --ignored --nocapture
```

Both packages include a numeric `balance-report.json`; these observations do
not include original game artwork or catalog data.
