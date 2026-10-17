# RustRaptor

The independent Linux and Windows Rust game and its complete local mod packages live here.
SDL2 handles platform services; gameplay, asset decoding, rendering, audio,
saving and mod scripting run in Rust.

This folder is the Git repository root. Run from here:

```sh
./run.sh
cargo test --locked
```

The self-contained runtime uses `bin/raptor-rust`, its sibling `data/` catalog
and the bundled `mods/`. `./run.sh` launches that executable without Cargo or
the old engine; paths remain valid after moving the folder. For development,
the launcher falls back to Cargo when no packaged executable is present.
`--data DIR` selects another catalog. Some optional comparison tests use retained source.
On Windows, double-click `run.cmd`; it starts the included
`bin/raptor-rust.exe` with its adjacent SDL2 DLL and the same data and mods.
See [Windows builds and packaging](docs/windows-build.md).

Refresh the executable and copied original/approved-HD data with
`python3 tools/assemble_runtime.py`. Add `--zip dist/RustRaptor-linux-x86_64.zip`
to export a distributable folder containing the runtime, mods, source and API
documentation, excluding build caches and review drafts. See
[standalone packaging](docs/standalone-package.md).

The **Mods** screen discovers the bundled `mods/` packages when no user mods
folder exists. Enable **Iron Coast Campaign** to select all six mission mods,
their enemies, distinct bosses, weapons and original soundtrack automatically,
then apply at the main menu. Missions, bosses and the three weapons can also
be enabled individually; each mission selects its own dependencies.
**Lightning Cannon** and **Lightning Shield** are two additional independent
weapon mods. Enable them in Mods and buy them in the supply room. The cannon
is a selected special that chains through nearby targets; the shield fires
with your primary guns while Fire is held. Both ship SD/HD icons and sounds.

**Iron Coast II: Black Tide** adds eight more missions, eight separate bosses,
three shared enemy types and three original FM music tracks. Enable its campaign
in **Mods**, apply at the main menu, then choose **Nightbreak Inlet** in the
Hangar's mission menu to begin the linked campaign.
The campaign selects its dependencies automatically. **Railburst Cannon**
(685,000 credits) and **Depth Charge** (525,000 credits) are optional shop
purchases; completing missions does not grant either weapon. Each mission,
boss and weapon is also an individual mod. See [Stage 2](docs/iron-coast-stage2-design.md).
For a user mods folder, pass `--mods DIR` or create
`$XDG_DATA_HOME/RaptorReplica/mods/` on Linux or
`%APPDATA%\RaptorReplica\mods\` on Windows. Saves and configuration use separate
user profile directories, with read-only legacy import.

Enter the **Hangar** to fly, choose missions, visit the supply room, manage
equipment or **Save pilot**. New pilots have editable names, callsigns and ID
pictures and difficulty; existing pilots can edit their ID from the hangar.
Registration starts with 10,000 credits and 75 energy, as in the original.
The original Apogee/Cygnus logos and intro play on normal startup and through
**Watch intro**. Saves with changed or missing mods show the differences and
offer **Load anyway**, retaining unavailable equipment and progression. The
first subsequent save keeps a backup of the previous file.
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
| `mods/` | 45 packages: Aurora example, two Iron Coast campaigns with 14 missions, seven weapons, shared enemies, bosses and original music |
| `schemas/` | Version 1 mod API schemas |
| `tests/` | Portable fixtures and opt-in original-data checks |
| `tools/` | Replay comparator, content-table generator and asset reference tools |
| `docs/` | API, artwork, build and validation documentation |
| `bin/`, `data/`, `lib/` | Included Linux/Windows executables, shared data and SDL2 runtimes |
| `target/` | Local Cargo builds, excluded from Git |

The bundled executable, libraries, original game catalog and approved HD assets
are tracked in Git, along with mod definitions, scripts, SD/HD PNGs, WAVs,
generation prompts and recipes. Build caches and local review files are excluded.
See [repository layout](docs/repository.md).
The engine supports original rendering and crisp 2×/3×/4× scaling, plus an
optional HD artwork setting. The reviewed base-game pack now covers **5,480 of
5,753 original pictures**, with **273 still awaiting approval**. All 307 native
AGX cinematic/font records remain preserved separately. Bundled mods include
SD/HD artwork. [The HD backlog](docs/hd-backlog.md) records the remaining
originals, held drafts and review limits.

First-mission wins at difficulties 1 and 2, a complete 1,889-step native demo
comparison, assisted coverage of all 27 missions at four difficulties, and
sample-exact audio comparisons have passed. These checks cover their documented
cases; wider playtesting and complete base-game HD coverage remain work in progress.

- [Build and validation](docs/rust-rewrite.md)
- [Mod API](docs/modding-api.md)
- [AI mod authoring checklist](docs/mod-authoring-checklist.md)
- [Iron Coast packages](docs/iron-coast.md)
- [Iron Coast pacing and difficulty comparisons](docs/iron-coast-retune.md)
- [Iron Coast II: Black Tide](docs/iron-coast-stage2-design.md)
- [Weapon prices and balance](docs/weapon-balance.md)
- [Sprite and shadow validation](docs/visual-validation.md)
- [Sound playback validation](docs/sound-validation.md)
- [Classic intro validation](docs/intro-validation.md)
- [Menu screenshot review](docs/menu-validation.md)
- [Campaign music](docs/music-validation.md)
- [Display measurements](docs/performance.md)
- [First mission](docs/first-mission-validation.md)
- [Campaign coverage](docs/campaign-validation.md)
- [Optional HD artwork](docs/hd-art.md)
- [Milestones](PLAN.md)

Code is GPL-2.0-or-later; the vendored Rust FM emulator is LGPL-2.1-or-later.
