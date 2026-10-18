# Iron Coast S2 M06: Emberwake Shipyards

API 1 package, version 1.0.1. Enable it in Mods at the main menu and apply the selection. The normal dependency selection also enables `iron_coast_stage2_boss_6`, `iron_coast_stage2_music`, `iron_coast_stage2_siege`, `iron_coast_stage2_skimmer`.

Mission `iron_coast_stage2_mission_6:mission_06`: **Iron Coast S2 M06: Emberwake Shipyards**. Destroy all three required targets and the boss. Required ground objectives remain reachable; escaping optional aircraft never counts as a kill. Elapsed time alone does not finish the mission.

Scheduled spawn totals for Training / Rookie / Veteran / Elite are **46 / 54 / 66 / 82**. These are enabled scheduled entries, not simultaneous live-enemy counts. Groups can overlap when earlier enemies survive.

Align the forward guns with required targets while moving around incoming shots. If carried, select Field Repair or coolant with Cycle and use Special: they restore 25 or 30 energy respectively and consume a real item. Shop purchases and refills still cost credits.

## Validation and history

See the [current Iron Coast retune results and limits](../../docs/iron-coast-retune.md). Package-local acceptance reports, validation results and retained test sources describe pre-retune 1.0 behavior unless a result explicitly identifies the newer package and runner. They remain historical material, not current playthrough guarantees.

## Rebuilding the briefing

Run `python3 art/build_cinematic_briefing.py` from this package directory
(Pillow required). It verifies the unchanged cinematic master and rebuilds the
exact SD/HD filenames referenced by `content.json`; the prompt and provenance
are beside the master in `art/`. This artwork update changes package hashes;
existing pilots use the normal changed-mod confirmation, with stable IDs and
saved equipment/progression retained.

`tools/build_assets.py` also includes the cinematic briefing recipe when rebuilding
this package's assets; its tile, sprite and sound processing is unchanged.
