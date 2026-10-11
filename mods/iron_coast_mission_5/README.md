# Iron Coast 5 — Cinder Docks

Enable this individual mission package in the Mods screen. Dependency selection
adds `iron_coast_scout`, `iron_coast_turret`, `iron_coast_boss_5`, `pulse_cannon`,
`seeker_swarm`, `ion_lance` and `iron_coast_music`, each compatible with version
1.x. Choose **Iron Coast 5 — Cinder Docks** in the mission menu. This mission has
no `next` reference; the optional Iron Coast campaign package supplies six-level
progression while the level stays independently playable.

Destroy both armored furnace stations, then defeat **Cinder Hammer** to shut down
the shipbuilding yard. The stations arrive at ticks 240 and 920 and stay at y=24
until destroyed. The boss arrives at tick 1660 and remains in the firing area.
Killing the boss first still requires the stations. Victory awards 15,000 credits
once, plus ordinary destruction rewards, including 1,200 per station and 1,800
for Cinder Hammer. The 2,600-tick duration is a catalog hint; waiting cannot win.

Original enemies join the custom scouts: two opposing diagonal sweep libraries
(`base:enemy_0_21`, `base:enemy_0_22`), two curved-entry libraries
(`base:enemy_1_25`, `base:enemy_1_26`), a straight light fighter
(`base:enemy_0_13`) and a dock boat (`base:enemy_0_8`). Their original assets,
banking, movement paths, projectiles, collision and rewards remain in the base
registry, with no clones or overrides. These escorts and the ordinary turrets
are optional targets. All native spawns are enabled on every difficulty.

Slag warnings alternate between the outer left and right lanes, followed 35
simulation ticks later by three falling shells. The central corridor stays clear.
Three coolant injectors are supplied if inventory room permits, including the
physical slot cost of reserve super-shields. A full 20-slot inventory can enter
without losing equipment. No premium weapon is borrowed or required.

Hold Fire (default Ctrl), line up with each station and keep the ship near y=160.
Alt or Shift changes selected equipment. Select **Foundry Coolant Injector** and
press Special (default Z) when energy drops to 65 or below; each use restores 30
and consumes one injector. The item costs 15,000 credits per injector and has a
five-unit capacity, matching the Iron Coast repair rate of 500 credits per shield
unit. Ordinary forward guns keep firing while a coolant injector is selected.
The shared **Coastal Steel** music loops through the mission; nine local cues
cover approach, furnace warnings, slag, cannon fire, shutdown, boss arrival,
coolant use and victory.

New generated terrain, briefing and transparent furnace-station masters are
packaged as SD and HD PNGs. SD uses the original game palette; HD uses separate
physical dimensions while preserving logical collision footprints. A reflected
terrain period makes the repetition edges match exactly. The exact imagegen
prompts, asset source hashes, procedural audio generator and generated outputs
are tracked with the mod. See `prompts.md`, `prompts.json`, `provenance.json`
and `asset-report.json`.

Regenerate the outputs with:

```sh
python3 RustRaptor/mods/iron_coast_mission_5/build_content.py
python3 RustRaptor/mods/iron_coast_mission_5/build_assets.py
```

Run `RustRaptor/mods/iron_coast_mission_5/validate.sh` for local original-data
acceptance. Its control fixture uses only starter guns, bounded horizontal
movement toward a station's x+8 coordinate (otherwise x=144), and selectable
coolant when shield is at most 65. It tests normal registration resources
(75 shield, 10,000 credits), the 100-shield fixture, identical repeated outcomes,
all six native enemies appearing and moving, full-slot entry, one-time rewards
and mission-state reset on re-entry. It does not directly damage enemies or refill
shield during the controlled flight. Results are in `validation-report.json`.
The original asset catalog is required locally and remains outside Git.

The final local run finishes at tick **1,818** (about 78 seconds) from normal
registration resources with **71 shield**, **31,950 credits** and two coolant
uses. Repeating the same controls produces an identical world digest. The
100-shield/zero-credit fixture finishes at the same tick with 66 shield and
21,950 credits using one coolant. All six native libraries were seen moving in
every run; full 20-slot inventories with zero or four reserve super-shields
preserved their equipment. Required objectives, one-time rewards and restarting
with retained script state passed. Human difficulty and presentation remain
subject to ordinary play testing.
