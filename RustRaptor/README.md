# RustRaptor

The independent Linux Rust game and its complete local mod packages live here.
SDL2 handles platform services; gameplay, asset decoding, rendering, audio,
saving and mod scripting run in Rust.

From the repository root:

```sh
./play.sh
```

Or from this folder:

```sh
./run.sh
cargo test --locked
```

Supply the original game catalog in `../data/` or `RustRaptor/data/`. You can
select another catalog with `--data DIR`. No C++ checkout or build is needed to
build or play the Rust game. Some optional comparison tests use retained source.

The **Mods** screen discovers the bundled `mods/` packages when no user mods
folder exists. Enable the Iron Coast mission package to select its six
dependencies automatically, then apply at the main menu. The three weapons can also be enabled individually.
For a user mods folder, pass `--mods DIR` or create
`$XDG_DATA_HOME/RaptorReplica/mods/`. Saves and configuration use separate XDG
`RaptorReplica` directories, with read-only legacy import.

Enter the **Hangar** to fly, choose missions, visit the supply room, manage
equipment or **Save pilot**. New pilots have editable names, callsigns and ID
pictures and difficulty; existing pilots can edit their ID from the hangar.
Registration starts with 10,000 credits and 75 energy, as in the original.
The supply room
shows an equipment image, description, price, resale value, quantity and
whether it fires automatically, is selectable, is consumed or works passively.

Default keyboard controls are arrow keys to move, **Ctrl** to fire,
**Space** to drop a bomb, **Alt or Shift** to cycle equipment, and **Z** to
use a selected consumable. Custom bindings remain configurable in Options.
Existing untouched Rust default bindings migrate to these controls.

| Folder | Contents |
| --- | --- |
| `src/` | Engine, SDL host and validation CLI |
| `mods/` | Aurora example, Iron Coast mission, three weapons and three enemies |
| `schemas/` | Version 1 mod API schemas |
| `tests/` | Portable fixtures and opt-in original-data checks |
| `tools/` | Replay comparator, content-table generator and asset reference tools |
| `docs/` | API, artwork, build and validation documentation |
| `target/` | Local Cargo builds, excluded from Git |

All bundled mod definitions, scripts, SD/HD PNGs, WAVs, generation prompts and
recipes are tracked in Git. Original data and local reference pixels are excluded.
The engine supports original and 2×/3×/4× crisp scaling, plus an optional HD
artwork setting. Bundled mods have SD/HD artwork; the base-game HD proof covers
one player frame, with crisp originals supplying the other frames.

First-mission wins at difficulties 1 and 2, a complete 1,889-step native demo
comparison, assisted coverage of all 27 missions at four difficulties, and
sample-exact audio comparisons have passed. These checks cover their documented
cases; wider playtesting and complete base-game HD coverage remain work in progress.

- [Build and validation](docs/rust-rewrite.md)
- [Mod API](docs/modding-api.md)
- [Iron Coast packages](docs/iron-coast.md)
- [Weapon prices and balance](docs/weapon-balance.md)
- [Sprite and shadow validation](docs/visual-validation.md)
- [Sound playback validation](docs/sound-validation.md)
- [Display measurements](docs/performance.md)
- [First mission](docs/first-mission-validation.md)
- [Campaign coverage](docs/campaign-validation.md)
- [Optional HD artwork](docs/hd-art.md)
- [Milestones](PLAN.md)

Code is GPL-2.0-or-later; the vendored Rust FM emulator is LGPL-2.1-or-later.
