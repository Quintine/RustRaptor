# Iron Coast — Mission 1: Breakwater

Enable this package in the in-game Mods screen to select its seven installed dependencies automatically:
`iron_coast_scout`, `iron_coast_turret`, `iron_coast_boss`, `pulse_cannon`,
`seeker_swarm`, `ion_lance`, and `iron_coast_music`. Each package is independent and version 1.0.0.
Choose **Iron Coast 1 — Breakwater** in the mission list. The original
Coastal Steel FM soundtrack loops during flight.

Disable at least two harbor turrets and destroy the command ship to complete
the raid. Scout waves arrive during the approach; two supply depots release
repair kits. When inventory space allows, the mission grants a trial Pulse
Cannon loan and three field repairs. The loan is returned before the completed
flight is saved; a cannon you already own is preserved. Field repairs cost
12,500 credits each in the shop, a premium over the original 10,000-credit
hangar energy refill for use during combat.
Repairs restore 25 shield when selected and used with the special button.
Victory awards 5,000 credits in addition to ordinary destruction rewards.
A full inventory can still start the mission; existing equipment is preserved
and new grants are skipped when there is no free slot.

This mission uses explicit script completion. Its duration is a catalog hint;
waiting out the timer cannot win. The boss stays in the firing corridor, and
surviving objective turrets stay on screen and can be hit with starter forward guns. Equipment and
mission progress remain subject to the normal mod-save compatibility checks.

The generated masters, packaged SD/HD PNGs and synthesized WAVs are included
in Git with their definitions, scripts, generator, prompts and validation
report. Original game data and the original style-reference PNGs remain
outside Git. The three
`art/*-source-hd.png` inputs were generated with the built-in imagegen tool
using the original terrain and military sprite as style/scale references.
Run `python3 mods/iron_coast_mission_1/build_assets.py --palette
../data/misc/PALETTE_DAT` to regenerate the exact
packaged crops, SD palette conversion, HD footprints and synthesized WAVs.
See `prompts.md`, `asset-report.json`, and [Iron Coast documentation](../../docs/iron-coast.md) for provenance
and validation limits.

The release acceptance run completes with starter guns at step **882**
(shield 94) and the trial Pulse Cannon at step **786** (shield 92), both with
7,715 credits. These are deterministic headless runs on difficulty 2: initial
shield 100, held fire, position fixed at (144,160), repairs selected on step 2
and the special button pressed every 90 steps starting at step 61. They use
the mission's granted/dropped repairs; they apply no direct shield refills or
enemy damage commands. Human-play difficulty and audiovisual approval remain
subject to normal play testing.
