# Iron Coast II — Mission 2: Undertow Run

An independently playable Black Tide sortie with native Raptor aircraft paths,
new patrols and its own boss. Enable **Undertow Run** in **Mods**; installed compatible
required enemy/boss/music dependencies are selected automatically. Select
`iron_coast_stage2_mission_2:mission_02` in the hangar. Installing the optional full Black Tide
campaign places this sortie in its eight-mission progression.

Destroy 4 actual `skimmer` units and then the `iron_coast_stage2_boss_2:unit` boss. Required
convoys are held inside the reachable playfield after entry; leaving or despawning
never counts as destruction. The boss arrives at tick 2280. A duration
timeout cannot grant victory. Completion awards 32,000 credits once, in addition
to actual enemy rewards. Replaying resets this sortie's kill counters and phases.

Hold **Ctrl/Fire** to use owned weapons; **Alt/Shift** cycles selected weapons;
**Space** retains bombs. Starter forward guns can target all mandatory enemies;
optional purchased gear improves firepower. The mission grants no equipment or
shield/credit cheats, and works with a full 20-slot inventory.

New terrain is generated from original Raptor material/palette references, with a
320×512 logical map and a reflected scroll cycle repeated through 4,096 rows.
This preserves terrain beneath delayed boss fights. All mandatory targets appear
on every difficulty; higher difficulties add patrol reinforcements. The briefing crops the same
master. Both SD and 4× HD terrain and generated WAV mission cues are tracked.
`build_assets.py` reproduces all derived art/audio from the untouched raw master.
See [generation provenance](generation-provenance.json) and
[asset recipe/report](asset-report.json). Original reference images and working
review captures stay outside the package.

```sh
python3 mods/iron_coast_stage2_mission_2/build_assets.py
CARGO_TARGET_DIR="$PWD/target" cargo run --locked --release --manifest-path mods/iron_coast_stage2_boss_1/validation/Cargo.toml
```

The CLI requires all dependency IDs explicitly; the in-game manager resolves them.
Final real-catalog gameplay, audio, native path and save/RNG observations are
recorded in `acceptance-report.json`. Local single-sortie campaign definition
uses no overrides, so the optional aggregate campaign controls progression.

Author acceptance passed seven complete cases: difficulties 0–3 with starter
guns, default 100-shield, a full 20-slot inventory, and owned optional new gear.
The registered 75-shield pilot completes at tick 2681 with 61 shield and
a 52,260-credit gain using ordinary Fire and a mouse movement cap of
four logical pixels per tick. Serialized script state/RNG continuation, replay
reset, reward-once and actual native path motion checks passed. A separate
health-buffer fixture verifies reachable targets and terrain after 5,000 ticks;
it is not a balance result. The purchased-gear fixture funds shop purchases
before gameplay, rather than claiming a new pilot can afford both weapons.

Asset recipes use Python 3 with Pillow. The game uses the shipped PNG and WAV files.
