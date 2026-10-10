# Iron Coast 6 — Iron Crown

The finale raids the offshore command citadel. Destroy all six fixed batteries
and both command cruisers to end the Iron Coast operation. The second cruiser
arrives at tick 2,350, about 101 seconds into the mission; there is no survival
timeout that bypasses the objectives. Surviving batteries remain anchored at
y48 or y80 and cruisers patrol at y24, so required targets cannot escape.

This is an independent local mod with mission ID
`iron_coast_mission_6:mission_06`. Enable it in **Mods**; the game automatically
selects its seven installed dependencies: `iron_coast_scout`,
`iron_coast_turret`, `iron_coast_boss_6`, `pulse_cannon`, `seeker_swarm`,
`ion_lance` and `iron_coast_music`, all compatible with `^1.0`. It has no
mission-to-mission dependency
and no definition overrides. The optional `iron_coast_campaign` assembly adds
the full six-level progression.

Select **Ion Lance** with Alt or Shift and hold Ctrl to fire. Aim the narrow
column at ground batteries, then track the broad command cruiser. Space drops
bombs if the pilot owns them. The sortie lends an Ion Lance only when a free
inventory slot exists, returns that loan on success or failure, and preserves
an already owned copy. A full 20-slot inventory, including physical reserve
super-shield modules, can still start without equipment loss. Pilots receive
25 shield on arrival and 20 shield at each cruiser phase, clamped to 100.

The finale awards a 30,000-credit completion bonus once, in addition to normal
enemy rewards. There are 21 custom scout sorties, six classic aircraft, six
batteries and two
Iron Crown bosses. The classic aircraft directly reference `base:enemy_0_73`,
`base:enemy_0_74`, `base:enemy_0_23`, `base:enemy_0_24`, `base:enemy_0_95` and
`base:enemy_0_96`, retaining their original loop, sweeping and banking flight
paths without cloning or overriding definitions. Original pixels stay outside
this package. The campaign music is `iron_coast_music:iron_coast`.
The terrain definition spans 3,800 ticks, about 163 seconds, and completion
remains objective-driven if a pilot needs longer to finish surviving targets.

`art/terrain-source-hd.png` and `art/briefing-source-hd.png` are new artwork
generated using the built-in imagegen skill. `prompts.json` records both exact
prompts, reference role and provenance. The source terrain is packaged into
216 paired 32px SD/128px HD tiles, plus a 320×200 SD/1280×800 HD briefing card.
SD art uses the original game's palette. A single joined-canvas conversion
preserves horizontal tile seams; reflected vertical repetition has identical
boundary pixels. Four original PCM16 mono WAV cues provide approach, fleet
alarm, final command alarm and victory audio. Generated art and audio belong
in Git; no original catalog image is copied into this package.

Repackage derived files with:

```sh
python RustRaptor/mods/iron_coast_mission_6/build_assets.py
```

The local palette source is required only for repackaging. Validate actual
shipped mod files and production deterministic simulation with:

```sh
CARGO_TARGET_DIR=RustRaptor/target cargo run --offline --manifest-path \
  RustRaptor/mods/iron_coast_mission_6/validation/Cargo.toml
```

The runner checks all four difficulties with the registered pilot's 75 shield
and 10,000 credits and the deterministic fixture's 100 shield and zero credits.
It uses the loan without buying a premium weapon, bounds lateral movement to
4 pixels per tick, tests six reachable batteries, full inventories, reserve
modules, restart reset, owned-weapon retention on success/failure and one-time
reward payment. The eight loan runs finish at ticks 2,385–2,426 with 100 shield.
A registered pilot with 20 neutral inventory slots and only the starter guns
finishes at tick 2,512 with 95 shield, without receiving a loan.
It records outcomes in `validation-results.json`. The actual original asset
catalog and native enemy definitions are used locally. Additional neutral
fixture items only fill inventory slots for the no-loan safety check. Set
`RAPTOR_TEST_DATA` if the original catalog lives elsewhere.
