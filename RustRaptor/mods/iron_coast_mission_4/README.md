# Iron Coast — Mission 4: Stormwall

Enable this individual mission in **Mods**. Its seven installed dependencies
are selected automatically: `iron_coast_scout`, `iron_coast_turret`,
`iron_coast_boss_4`, `pulse_cannon`, `seeker_swarm`, `ion_lance`, and
`iron_coast_music`, all at
compatible 1.x versions. This mission is independently playable; the optional
Iron Coast campaign pack supplies campaign ordering.

Choose **Iron Coast 4 — Stormwall**. Scout flights screen four coastal
batteries on the right-hand cliff. Destroy all four emplacements and the
Stormwall Arsenal to finish. Turrets enter at ticks 180, 340, 620 and 820;
the Arsenal enters at 1150. Surviving batteries stop at logical y=72 and
the Arsenal patrols at the top of the battlefield until killed. Waiting out
the 3000-tick duration never completes the mission.

Six original aircraft entries mix with fourteen Iron Coast scouts. The
`base:enemy_0_73` and `base:enemy_0_74` pair follows curved nine-point
routes; `base:enemy_0_23` and `base:enemy_0_24` cross the battlefield;
`base:enemy_1_25` and `base:enemy_1_26` use a second original curved entry.
Their catalog definitions retain original flight points, speed, firing,
animation and rewards. This package references them directly and contains
no copied original sprites or definitions.

Hold Fire, move under each battery on the right, then follow the Arsenal's
horizontal patrol. Its battery alarms and visible pauses warn before each
three-shell salvo. A Pulse Cannon is loaned when absent and an inventory slot
is free. It fires alongside the primary guns without weapon selection. The
loan is returned on success or failure; owned equipment is preserved. Full
20-slot inventories skip the loan and start without deleting equipment.
Storm effects are artwork and warning sounds; there is no hidden weather
damage. The separate soundtrack mod supplies the looping **Coastal Steel**
MUS composition through Rust FM synthesis. Victory awards 12,000 credits
plus ordinary enemy destruction rewards.

The mission contains 216 SD/HD terrain pairs, matching SD/HD briefing art,
two generated source masters and four synthesized WAV cues. Artwork, sounds,
prompts and provenance are packaged here for Git. Original game data remains
external. See `prompts.json`, `prompts.md` and `asset-report.json`.

Regenerate the deterministic packaging from the project root:

```sh
python3 RustRaptor/mods/iron_coast_mission_4/build_assets.py
```

After building RustRaptor in release mode, validate the real catalog, scripts
and playthrough without changing any saves:

```sh
python3 RustRaptor/mods/iron_coast_mission_4/validate.py
```

Actual-input acceptance uses difficulty 2, held fire, y=160, and horizontal
movement limited to four logical pixels per step, aiming at a visible turret
first, then the Arsenal, then aircraft. It uses the mission loan and no
purchased equipment, direct damage commands or shield refills. Separate
tests check original enemies seen and moving, late reachable objectives,
reward gating, one-time payout, full-inventory victory, loan return on failure,
successful replay with retained script state and owned equipment.
Final revision results are recorded in `acceptance-report.json`.

The revised eight-package run passes seven focused tests. A normal
75-shield/10,000-credit pilot completes at tick **1218** with **63 shield
and 27,805 credits**; the 100-shield/zero-credit fixture ends at the same
step with **88 shield and 17,805 credits**. All six native aircraft types
are observed moving in both runs. A veteran with twenty occupied inventory
slots also completes without receiving the loan or losing equipment.
These controlled runs establish a viable path; they do not establish
balancing for every player, loadout or difficulty.
