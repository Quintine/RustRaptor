# Iron Coast S1 M05: Cinder Docks

API 1 package, version 1.0.1. Enable it in Mods at the main menu and apply the selection. The normal dependency selection also enables `iron_coast_scout`, `iron_coast_turret`, `iron_coast_boss_5`, `pulse_cannon`, `seeker_swarm`, `ion_lance`, `iron_coast_music`.

Mission `iron_coast_mission_5:mission_05`: **Iron Coast S1 M05: Cinder Docks**. Destroy both foundries and Cinder Hammer. Required ground objectives remain reachable; escaping optional aircraft never counts as a kill. Elapsed time alone does not finish the mission.

Scheduled spawn totals for Training / Rookie / Veteran / Elite are **45 / 64 / 83 / 107**. These are enabled scheduled entries, not simultaneous live-enemy counts. Groups can overlap when earlier enemies survive.

Align the forward guns with required targets while moving around incoming shots. If carried, select Field Repair or coolant with Cycle and use Special: they restore 25 or 30 energy respectively and consume a real item. Shop purchases and refills still cost credits.

## Equipment supplied by the mission

The mission supplies three coolant cells when inventory capacity allows. Select coolant with Cycle, then press Special to restore 30 energy per consumed cell. Healing is not automatic.

## Validation and history

See the [current Iron Coast retune results and limits](../../docs/iron-coast-retune.md). Package-local acceptance reports, validation results and retained test sources describe pre-retune 1.0 behavior unless a result explicitly identifies the newer package and runner. They remain historical material, not current playthrough guarantees.

## Rebuilding the briefing

Run `python3 art/build_cinematic_briefing.py` from this package directory
(Pillow required). It verifies the unchanged cinematic master and rebuilds the
exact SD/HD filenames referenced by `content.json`; the prompt and provenance
are beside the master in `art/`. This artwork update changes package hashes;
existing pilots use the normal changed-mod confirmation, with stable IDs and
saved equipment/progression retained.

`build_assets.py` also includes the cinematic briefing recipe when rebuilding
this package's assets; its tile, sprite and sound processing is unchanged.
