# Iron Coast — Mission 1: Breakwater

Enable this package and its six dependencies in the in-game Mods screen:
`iron_coast_scout`, `iron_coast_turret`, `iron_coast_boss`, `pulse_cannon`,
`seeker_swarm`, and `ion_lance`. Each package is independent and version 1.0.0.
Choose **Iron Coast 1 — Breakwater** in the mission list.

Disable at least two harbor turrets and destroy the command ship to complete
the raid. Scout waves arrive during the approach; two supply depots release
repair kits. The mission grants a trial Pulse Cannon and three field repairs.
Repairs restore 25 shield when selected and used with the special button.
Victory awards 5,000 credits in addition to ordinary destruction rewards.

This mission uses explicit script completion. Its duration is a catalog hint;
waiting out the timer cannot win. The boss stays in the firing corridor, and
the two central turrets can be hit with starter forward guns. Equipment and
mission progress remain subject to the normal mod-save compatibility checks.

The generated masters, packaged SD/HD PNGs and synthesized WAVs are included
in Git with their definitions, scripts, generator, prompts and validation
report. Original game data and the original style-reference PNGs remain
outside Git. The three
`art/*-source-hd.png` inputs were generated with the built-in imagegen tool
using the original terrain and military sprite as style/scale references.
Run `python3 examples/mods/iron_coast_mission_1/build_assets.py --palette
data/misc/PALETTE_DAT` to regenerate the exact
packaged crops, SD palette conversion, HD footprints and synthesized WAVs.
See `prompts.md`, `asset-report.json`, and `docs/iron-coast.md` for provenance
and validation limits.
