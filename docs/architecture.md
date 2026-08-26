# Engine architecture

The engine is the reconstructed original Raptor source (nukeykt's port,
vendored under `raptor/`), patched for loose-file assets and Linux. All game
code is C++11, built with CMake + SDL2 + ALSA.

## Startup flow

`main()` in `raptor/src/rap.cpp`:

1. `RAP_InitLoadSave()` — resolves the user data dir via
   `SDL_GetPrefPath("", "Raptor")` (`~/.local/share/Raptor/`). Saves,
   `SETUP.INI` and high scores live there; the repo stays read-only.
2. **Data detection** — `GLB_SlotItems(n)` (from `src/glbapi.cpp`) parses
   `data/INDEX` and counts assets per archive slot:
   - slot 1 present -> `gameflag[0]` (mission pack 1)
   - slot 2 present -> `gameflag[1]` (mission pack 2)
   - slots 3 and 4 present -> `gameflag[2]`, `gameflag[3]`
   - slot 2 or 3 present -> `reg_flag = 1` (registered version)
   - slot 0 missing or no packs -> fatal "data files NOT FOUND"
3. `GLB_InitSystem(RAP_GetPath(), 6, 0)` — loads the catalog, builds one
   item-descriptor array per non-empty slot (name + size per item).
4. Sound, input, graphics init; palettes/fonts/UI load from the catalog.
5. Main loop dispatches between intro, menu, hangar, store, ship computer
   and mission gameplay.

## Asset system

Assets are addressed by **handles**: `(archive slot << 16) | item index`.
The constants live in `src/fileids.h` (e.g. `FILE100_PALETTE_DAT = 0x10000`
= slot 1, item 0). At runtime:

- `data/INDEX` maps each handle to a file: `<hex id> <size> <path>`, sorted
  by id. `GLB_LoadCatalog()` parses it once; `GLB_CatFind()` binary-searches
  it.
- `GLB_GetItem / GLB_LockItem / GLB_CacheItem` allocate and read the file
  through a VM/cache layer (`src/vmemapi.cpp`) — locked items stay resident,
  others are discarded under memory pressure.
- `GLB_GetItemID(name)` resolves a NUL-terminated item name to a handle by
  scanning the per-slot descriptor arrays.

The "GLB" API names are historical — no `.GLB` archive is read at runtime.

## Archive slots

| Slot | Items  | Content |
|------|--------|---------|
| 0    | 230    | Text files, help, credits, music (`*_MUS`), SFX (`*_FX`), `GENMIDI_OP2`, `DMXGUS_INI` |
| 1    | 1538   | Fonts, palettes, UI pictures, SWD window layouts, animations |
| 2    | 1708   | Mission pack 2 assets (tiles, maps, sprites, demos) |
| 3    | 1321   | Mission pack 3 assets |
| 4    | 1559   | Mission pack 4 assets |
| 5    | 92     | Extra data (not referenced by `fileids.h`) |
| 6    | 1      | Uninstaller leftover |

## Subsystems

- **Graphics** (`gfxapi.cpp`, `i_video.cpp`): original 320x200 VGA-mode
  renderer, palette-faded, scaled to the desktop by SDL. SWD (`swdapi.cpp`)
  is the window/widget system driving every menu.
- **Music** (`i_oplmusic.cpp`, `opl3.cpp`): the original OPL2 FM soundtrack,
  emulated sample-accurately; `*_MUS` items are OPL register captures.
- **SFX** (`fx.cpp`, `dspapi.cpp`): Sound Blaster digital effects, mixed
  through ALSA/PipeWire.
- **MIDI** (`mpualsa.cpp` etc.): optional external MIDI path using
  `GENMIDI_OP2`/`DMXGUS_INI`.
- **Movies** (`movie.cpp`): intro cinematics described by `*_MDS` scripts.
- **Demos** (`demo.cpp`): attract-mode gameplay recordings (`*_REC`).

## Exit path

`ShutDown()` (`rap.cpp`) closes the window, frees the asset cache and quits.
The upstream DOS-style ENDOOM farewell screen was removed — quitting exits
immediately. See [upstream-patches.md](upstream-patches.md).
