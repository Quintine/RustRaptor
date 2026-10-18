# Iron Coast pacing and presentation update

The 14 Iron Coast missions now use difficulty-scaled attack groups, clearer
weapon feedback and distinct enemy/boss patterns. Original campaigns and their
content definitions are unchanged.

Mission II 2, Undertow Run, version 1.0.3 moves one existing armed classic
curved pass from tick 1,650 to 1,530. The unarmed aircraft stays at 1,650, and
all other spawns and their fields remain unchanged. This count-neutral timing
correction leaves objectives, enemy statistics, equipment, prices, rewards and
the boss warning/arrival unchanged.

## Mission II 2: focused version 1.0.3 checks

On 18 October 2026, the frozen SourceE library (`3b04e473`) ran the unchanged
recorded paid-route controller. Four authentic post-Mission-1 states fed paired
version 1.0.2 and 1.0.3 continuations through Missions 2–8 and the finale replay:
68 ordinary mission executions in total. All completed with full pilot,
script-state and RNG save/load roundtrips. The changed Mission 2 version/hash
was reported and accepted through normal save compatibility; inventory and
other gameplay state were not silently rewritten.

Mission 2 completion times, shields and paid refill counts were unchanged at
all four difficulties. Ending shields were 79 / 52 / 44 / 12, preserving the
Elite route's narrow 12-shield margin. Veteran defeated one fewer optional
interceptor (two → one); Elite earned 100 more credits through the changed
encounter timing. Required skimmer and boss objectives were unchanged. These
are actual outcomes for the recorded controller and carried supplies, not a
guarantee for every loadout or play style.

Separate shield-replenished observations recorded the earlier Training/Rookie
quiet interval at ticks 1,448–1,650: 8.70 seconds with no visible enemies or
hostile shots. The retimed armed pass split it into a longest piece of 3.73
seconds and produced four observed hostile projectile births. The later quiet
intervals at 1,664–1,762 and 1,804–1,948 were unchanged, so the correction did
not merely move that lull later. Quiet time remains elsewhere, including the
deliberate boss recovery window.

Veteran/Elite arsenal observations absorbed six more replenished-shield points
each; their ordinary paid routes kept the same shields and purchases. No-fire
observers already had surviving required targets and do not establish ordinary
survival. These focused SourceE results are separate from the earlier
full-cohort measurements and do not claim a new SourceF playthrough or renderer
check.

The same seven maintained campaign, enemy and weapon suites were rerun against
the installed SourceF source epoch and version 1.0.3 definitions: **65 passed,
zero failed, four existing integration tests ignored**. The installed Linux
validator also accepts all 45 packages with one explicit override.

A separate SourceF presentation check rendered the same paid Veteran mission
state at tick 1,540 in SD and HD4 at 1920×1080. The retimed classic aircraft was
alive and entering from above the screen; partial top clipping and HUD overlap
are part of that entry pose. Both views and the actual Mods diagnostics were
reviewed at full size, with version 1.0.3 visible. This verifies that scene,
not every encounter or a complete SourceF mission playthrough.

## Wave schedules

Enabled scheduled enemies, including required targets and bosses:

| Mission | Training | Rookie | Veteran | Elite |
| --- | ---: | ---: | ---: | ---: |
| I 1 — Breakwater | 25 | 34 | 43 | 52 |
| I 2 — Tidal Relay | 29 | 40 | 51 | 62 |
| I 3 — Saltworks Convoy | 32 | 45 | 58 | 71 |
| I 4 — Stormwall | 35 | 50 | 65 | 84 |
| I 5 — Cinder Docks | 45 | 64 | 83 | 107 |
| I 6 — Iron Crown | 64 | 92 | 120 | 145 |
| II 1 — Nightbreak Inlet | 30 | 43 | 55 | 67 |
| II 2 — Undertow Run | 32 | 46 | 62 | 79 |
| II 3 — Stormglass Refinery | 42 | 50 | 62 | 78 |
| II 4 — Floodgate Zero | 42 | 50 | 62 | 78 |
| II 5 — Skybreaker Arsenal | 45 | 53 | 65 | 81 |
| II 6 — Emberwake Shipyards | 46 | 54 | 66 | 82 |
| II 7 — Siege of the Iron Fleet | 57 | 65 | 77 | 93 |
| II 8 — Black Tide | 61 | 69 | 81 | 97 |

### Earlier version 1.0.2: a different middle window

Mission II 2 version 1.0.2 adds a small number of classic aircraft in its observed middle lull. Paired current-C paid continuations from authentic post-Mission-1 saves complete Missions 2–8 and the finale replay at all four difficulties, with unchanged ending shields, completion timings and refill counts. The added kills and pickups earn normal credits. In the separate shield-replenished arsenal fixture, the longest threat-free stretch within that middle window decreases from 8.91 to 5.87 seconds; the lull is shortened rather than eliminated. The full-cohort pressure tables below remain the recorded version 1.0.1 measurements. These focused checks were recorded on 17 October 2026 and are separate from the shield-replenished observations.

Counts are not simultaneous enemies or difficulty quotas. The 27 original
missions have median scheduled totals of 139 / 139 / 228 / 313, but their
lengths, target durability and attacks differ. Iron Coast now introduces flank
groups and classic aircraft between objectives, with recovery space before
bosses. Required targets remain reachable; aircraft leaving the playfield do
not grant kills or complete objectives.

## Comparison method

The baseline covers all 27 original missions and all 14 Iron Coast missions at
all four difficulties. Controlled pressure observations use the same firing and
movement policy, with replenished shields to observe the complete schedule.
Those measurements describe activity, not ordinary-player survival. Separate
paid routes use actual inventory, shop transactions and carried shield charge.

Median mean-visible enemies during the controlled observations:

| Difficulty | Original missions | Stage I before → after | Stage II before → after |
| --- | ---: | ---: | ---: |
| Training | 0.65 | 0.28 → 0.52 | 0.22 → 0.42 |
| Rookie | 0.67 | 0.29 → 0.86 | 0.22 → 0.50 |
| Veteran | 1.30 | 0.31 → 1.26 | 0.25 → 0.59 |
| Elite | 1.98 | 0.31 → 1.52 | 0.25 → 0.68 |

The final Elite Iron Crown schedule removes ten extra reinforcements to leave
recovery space before the Fleet. Its 145 scheduled enemies remain above
Veteran’s 120. All lower-difficulty schedules are unchanged by that correction.

The final paired Stage I routes complete all six missions at all four settings,
with 96 full pilot/script-state/RNG save/load checks across baseline and revised
routes. The Elite finale completes at tick 2,649 with 47 shield using the actual
loaned Ion Lance and three purchased Field Repairs costing 37,500 credits.
The same controller’s earlier runs without those purchases died before the
Fleet; those failures remain recorded. This is one demonstrated paid strategy,
not a promise that every loadout or movement policy survives.

Stage II completes all eight missions and a finale replay at all four settings
using carried inventory, paid supplies and normal damage. The lowest observed
shield is 12 on Elite. Late-miss checks separately verify all mandatory targets
remain reachable and objectives can finish; those observer checks replenish
shields and are not survival results.

The final package metadata passes actual 45-mod resource validation and exact
save-pin roundtrips at every difficulty. Gameplay measurements use the frozen
runtime definitions/scripts; the final version-number, README and blank-line
whitespace corrections do not change gameplay tokens.

Seven maintained campaign, enemy and weapon test suites passed against the
frozen final-B runtime on 17 October 2026: 65 tests passed, none failed and four
existing integration tests remained ignored. This is the recorded result, not
a new SourceF test run. Updated fixtures check the revised attack clocks, offscreen firing
suppression, reward-free aircraft exits and short contact effects. Synthetic
native-enemy placeholders in portable mission tests are explicitly labelled;
the original-catalog playthrough checks above cover actual native enemies.

## Enemy silhouettes and attacks

Scouts and interceptors retain 24×24 logical bodies; turrets and siege units
remain 32×32, and skimmers remain 32×24. Those footprints fit their original
game roles; the update changes movement and firing rather than enlarging every
enemy. Scouts now enter, attack and break away. Interceptors make a faster
lateral pass and reversing exit. Ground units retain reachable firing lanes.

Aim locks at the start of each short salvo. Difficulty adjusts warning time,
shot speed, salvo length and recovery. Ordinary muzzle feedback uses compact
cues instead of explosion blooms. Enemy projectile artwork is 6–7 logical
pixels wide. Its visible size does not change the engine’s existing hostile
projectile collision threshold.

The first six bosses now have different patrols, dives, health phases and
warning/recovery sequences. Definition health is 240 / 280 / 320 / 360 / 400 / 420,
within the range of comparable original bosses; normal difficulty scaling applies.
The first three use 84×56
bodies, the next two 96×64 and Iron Crown 108×72. Stage II bosses retain their
existing distinct bodies, health, damage and rewards, with revised attack timing.

## Weapons and feedback

Pulse Cannon, Seeker Swarm, Ion Lance, Railburst Cannon and Depth Charge retain
their damage, targeting, cooldowns, effective ranges and prices. Pulse, rail and
depth-charge shots use more compact artwork; brief hit arcs replace oversized
explosions. Seeker artwork stays larger because the smaller trial lost readability.
Audio is gated to actual attacks and hits, reducing sustained overlapping noise.

| Weapon | Price | Role |
| --- | ---: | --- |
| Pulse Cannon | 185,000 | Primary weapon augmentation |
| Seeker Swarm | 285,000 | Selectable homing missiles |
| Ion Lance | 425,000 | Selectable penetrating beam |
| Railburst Cannon | 685,000 | Selectable piercing rail shot |
| Depth Charge | 525,000 | Selectable ground attack |

Controlled damage comparisons cover 125 cases; 30 complete gameplay-state
comparisons preserve damage, trajectories, RNG, collision, cooldowns and health
while allowing cosmetic effects/audio to differ. SD/HD enemy and boss captures
also check silhouettes, warning periods and firing feedback. Those bounded
checks do not establish every loadout’s balance or hardware audio quality.

## Using the update

Enable **Iron Coast S1: Complete Campaign** or **Iron Coast S2: Black Tide** in
Mods and apply at the main menu. Dependencies select automatically. Existing
pilots may receive the normal changed-mod warning; accepting it preserves saved
equipment and progression. Use Ctrl to fire, Alt/Shift to cycle equipment, Z for
Special and Space for owned bombs. Select mission-provided repairs before
using Special; they consume actual items. Mission 6 lends an Ion Lance when
inventory space permits—select it and hold Fire.

Package-local acceptance files describe their recorded versions. Retained
pre-retune 1.0 results are historical; they are not new-version playthrough claims.
