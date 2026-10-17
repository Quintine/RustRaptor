# Iron Coast II — Mission 2: Undertow Run

API 1 package, version 1.0.3. Enable it in Mods at the main menu and apply the selection. The normal dependency selection also enables `iron_coast_stage2_boss_2`, `iron_coast_stage2_music`, `iron_coast_stage2_interceptor`, `iron_coast_stage2_skimmer`.

Mission `iron_coast_stage2_mission_2:mission_02`: **Undertow Run**. Destroy four required skimmers and the boss. Required ground objectives remain reachable; escaping optional aircraft never counts as a kill. Elapsed time alone does not finish the mission.

Scheduled spawn totals for Training / Rookie / Veteran / Elite are **32 / 46 / 62 / 79**. These are enabled scheduled entries, not simultaneous live-enemy counts. Groups can overlap when earlier enemies survive.

The middle convoy interval now includes one light curved pass on Training, a mirrored second pass on Rookie and above, and one unarmed straight dash on Elite. These use unchanged classic aircraft definitions; their ordinary kill rewards still apply. The boss warning at tick 2,100 and boss arrival at 2,280 are unchanged.

The earlier armed curved pass now arrives at tick 1,530 instead of 1,650. The unarmed straight dash stays at 1,650; the Veteran/Elite entries at 1,580 and 1,590 and all later passes stay unchanged. This is a count-neutral timing change, with the same aircraft definitions, health, damage and rewards.

Align the forward guns with required targets while moving around incoming shots. If carried, select Field Repair or coolant with Cycle and use Special: they restore 25 or 30 energy respectively and consume a real item. Shop purchases and refills still cost credits.

## Validation and history

See the [current Iron Coast retune results and limits](../../docs/iron-coast-retune.md). Package-local acceptance reports, validation results and retained test sources describe pre-retune 1.0 behavior unless a result explicitly identifies the newer package and runner. They remain historical material, not current playthrough guarantees.

The full-cohort retune measurements describe version 1.0.1. Focused version 1.0.2 checks on 17 October 2026 used authentic post-Mission-1 saves under current C, then paired baseline and revised paid continuations through Missions 2–8 and the finale replay at all four difficulties. All completed with exact save/load roundtrips. Mission 2 ended with the same 79 / 52 / 44 / 12 shield and the same paid refill counts in each pair. Normal kills and pickups yielded slightly more credits; no shield or equipment grants were added.

In the separate shield-replenished arsenal fixture, the longest threat-free stretch inside the targeted middle window fell from 8.91 to 5.87 seconds. Some later aircraft can be shot down before becoming visible to that overpowered fixture, so the change shortens the lull without eliminating it. No-fire observers already had surviving required targets in that interval; those observations are not ordinary survival. The unchanged boss lead-in remains deliberate recovery space. These bounded results do not guarantee every loadout or movement strategy.

Focused version 1.0.3 checks on 18 October 2026 used the frozen SourceE library and the same recorded legal controller. Four authentic post-Mission-1 saves fed paired version 1.0.2 and 1.0.3 paid continuations through Missions 2–8 and the finale replay. Every route completed with exact save/load, script-state and RNG roundtrips. Mission 2 again ended at 79 / 52 / 44 / 12 shield, with unchanged completion times and refill counts. Veteran defeated one fewer optional interceptor; Elite earned 100 more credits through the altered encounter. Required skimmer and boss objectives were unchanged.

The separate shield-replenished arsenal observations recorded the earlier Training/Rookie quiet interval from ticks 1,448–1,650 (8.70 seconds). Moving the armed pass split it into a longest piece of 3.73 seconds and produced four observed hostile shots. The later quiet intervals at 1,664–1,762 and 1,804–1,948 were unchanged. Some quiet time remains elsewhere: this is a local pacing correction, not a claim of continuous combat. Veteran/Elite replenished-fixture shield loss rose by six points each, while their ordinary paid routes retained the same shields and purchases. Replenished observations do not establish survival for other controllers or loadouts.
