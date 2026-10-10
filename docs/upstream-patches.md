# Patches against upstream

Base: nukeykt's reconstructed Raptor source (skynettx/raptor mirror),
vendored in `raptor/` (GPLv2+, see `raptor/LICENSE` and `raptor/VENDOR.txt`).
Everything below diverges from upstream on purpose. Keep this list current
when touching engine code.

## Asset system: catalog of loose files (largest change)

Upstream reads seven encrypted `FILE000N.GLB` archives via
`src/glbapi.cpp`. This fork replaces the archive reader with a catalog of
loose files:

- `GLB_LoadCatalog()` parses `data/INDEX` (`<hex handle> <size> <path>`,
  sorted); `GLB_CatFind()` binary-searches it; `GLB_Load()` reads the file.
- `GLB_SlotItems(slot)` (new public API, `src/glbapi.h`) counts a slot's
  assets; `src/rap.cpp` uses it for mission-pack and registered-version
  detection instead of probing for `.GLB` filenames.
- `GLB_InitSystem` keeps its signature but ignores the archive-name prefix
  parameter.
- Payloads are pre-decrypted at extraction time; the runtime never runs the
  GLB cipher. `GLB_EnCrypt/GLB_DeCrypt` remain for reference/tooling.
- `FILEDESC` shrank to `{item, items}`; the archive file-handle cache
  (`GLB_FindFile/GLB_OpenFile/GLB_CloseFiles`) was removed.

Rationale and format docs: [glb-format.md](glb-format.md),
[asset-pipeline.md](asset-pipeline.md).

## Exit: no ENDOOM screen

Upstream's `ShutDown()` (`src/rap.cpp`) loaded `LASTSCR*_TXT` and opened a
second, text-mode "farewell" window (`I_LASTSCR`, `src/i_lastscr.cpp`)
that blocked until a keypress. Removed: `ShutDown` now closes the game
window and exits directly; `src/i_lastscr.cpp/.h` deleted.

## Diagnostics: EXIT_Error prints

Upstream's `EXIT_Error` (`src/common.h`) was a stub that called `exit(0)`
without printing — every engine error died silently. It now prints its
formatted message to stderr before exiting (still `exit(0)`, matching the
original exit code behavior).

## Platform: Linux-only

- `CMakeLists.txt` reduced to the Linux/SDL2/ALSA build; the Android
  (FetchContent SDL), Windows (MSVC/MinGW + `rsrc/` resources) and macOS
  branches are gone.
- Deleted upstream trees: `raptor/android/`, `msvc/`, `gcc/`, `pkg/`,
  `rsrc/`, `win32build.bat`, `osxbuild.sh`, the bundled Windows SDL2 SDKs
  under `include/`, and the `SETUP(*).INI` distribution templates.
- `src/loadsave.cpp`: removed the `__ANDROID__` block that copied `.GLB`
  files to external storage (obsolete concept in this fork).

## Data detection

`src/rap.cpp`: mission-pack presence is derived from catalog slot counts
(`GLB_SlotItems`) rather than `access("FILE000N.GLB")` probes; the fatal
"data files NOT FOUND" check now keys off slot 0 / no packs.

## Rendering: decoupled presentation loop

The original game advanced simulation and presentation in lockstep at
70/3 Hz (~23 fps): `Do_Game()` ran one think+draw pass, then waited three
timer ticks. This fork keeps the **simulation** at exactly that rate but
presents interpolated frames at display rate:

- Simulation is paced by a wall-clock accumulator (`RAP_SIM_STEP` in
  `src/rap.cpp`, units of 1/70000 s = 3 ticks). Input handling, all
  `*_Think()`, `DEMO_Think()` (one attract-mode record per step), palette
  fades and the stats state machine run once per step, preserving game
  speed, demo playback timing and RNG consumption order.
- After each step the scene is redrawn and presented with an interpolation
  fraction until the next step is due (`GFX_SetInterp` /
  `GFX_InterpCoord`, `src/gfxapi.cpp`). When behind schedule (blocking
  menus ate wall time) renders are skipped so the simulation catches up,
  matching the old tick-wait behavior.
- Draw positions are lerped between the previous and current simulation
  states for player ship, tile map scroll, enemies, enemy/player shots,
  bonuses, anims and shadows. The map scroll interpolates an unwrapped
  counter (`vscroll` in `TILE_Scroll`) because raw `tileyoff` wraps by
  32 px while the on-screen tile grid stays positionally continuous;
  `TILE_Scroll` runs before `TILE_Think` so wrap intervals render
  seamlessly.
- State changes that used to ride inside draw calls were moved to
  simulation or gated per step: enemy engine-flame toggle (`eframe`,
  `ENEMY_Think`), beam-shot animation counter (`SHOTS_Think`),
  ion-scanner sweep (`OBJS_DisplayStats`, gated by `gl_cnt`), S_LINE
  tracers are purged by `SHOTS_Think` instead of being removed mid-draw.
  The S_LINE purge keys off a per-shot `age` counter (one simulation step
  of life, matching upstream's draw-then-remove); the turret's retire
  path never frees its shot, so the purge must not reuse `doneflag`,
  which is hit/retire game state — reusing it leaked one `SHOTS` pool
  slot per turret fire until `SHOTS_Get()` could service no weapon, and
  hid the beam on hitting ticks.
- `RAP_DisplayStats` was split into `RAP_ThinkStats` (state: death
  sequence, wave-exit control, low-shield warnings) and the drawing half.
  The shield bars are redrawn unconditionally each rendered frame: the
  old `g_oldsuper`/`g_oldshield` dirty check can never fire when the
  latch runs in `RAP_ThinkStats` before the draw, which froze the bars.
  `g_oldsuper` is gone; `g_oldshield` survives as the sim-side
  previous-step shield used for damage detection. The muzzle-flash ship
  pic (`g_flash`) is likewise cleared once per simulation step, not per
  rendered frame, or it would be invisible at display refresh rates.
- The above-player anim layer (`ANIMS_DisplayHigh`) is drawn between the
  player and enemy shots as upstream does; most air-death explosions
  register `HIGH_AIR`, so dropping that call made dying ships vanish
  without exploding.
- Vsync is enabled when the display reports a refresh rate;
  `I_VsyncActive()` lets the game loop fall back to a delay guard when
  the renderer ignores the flag.
- Menus keep their 70 Hz `GFX_DisplayUpdate` pacing; intro/story screens
  still pace at 4 ticks (~17.5 fps).

## Video: borderless window mode

New `Video/borderless` SETUP.INI option (`VIDEO_LoadPrefs`). When set,
`SetVideoMode` creates a decoration-free window at the desktop resolution
anchored at (0,0) (`SDL_WINDOW_BORDERLESS`). Alt+Enter cycles between the
borderless desktop window and a normal decorated window while the mode is
active. Exclusive `fullscreen_width/height` modes ignore it; if both
`fullscreen=1` and `borderless=1` are set, `fullscreen` wins. The stale
commented-out `-borderless` command-line snippet was removed.

## Video: HD presentation filter (scale2x/scale3x)

New `[Video]` SETUP.INI keys, read once at boot in `VIDEO_LoadPrefs`
(`src/i_video.cpp`): `upscaler` (0 = off, 2/3/4 = scale2x/scale3x/
2x scale2x, default 3) and `scanlines` (0/1, default 0). The filter is a
presentation-level CPU pass over the final RGBA frame before it enters the
streaming texture — no engine logic or asset changes; the 4:3 playfield is
kept. Kernels are the AdvMAME scale2x/scale3x rules by Andrea Mazzoleni,
reimplemented in-repo (`src/i_upscale.cpp`, GPLv2+-compatible; nothing
vendored). Filtered frames render directly from the factor-sized streaming
texture and bypass the nearest-integer intermediate (`texture_upscaled`),
which only sharpens sub-integer fits of a 1x source. With `upscaler=0` the
original four-stage pixel-perfect path is byte-for-byte unchanged. The
scanline overlay darkens every third logical row (320x240 space) after the
final copy, so it stays geometry-safe under every window mode. Like
`Video/borderless`, these are hand-edited INI settings; `raptorsetup` is
not extended.


## Effects: machine-gun casings eject into world space

Upstream's forward-gun muzzle effect (`A_PLAYER_SHOOT`, the GUNSTR
diagonal streak art) is a player-relative anim: the streak is glued to
the wingtip and flickers in place for its 4-step life, which at the
decoupled presentation rate reads as shells vibrating at the gun rather
than being ejected. This fork registers the same art once more as
`A_PLAYER_EJECTA` (GROUND layer, `src/anims.cpp`) and spawns that at each
wingtip's world position (`SHOTS_PlayerShoot` case `S_FORWARD_GUNS`) via
`ANIMS_StartGAnim`. The casings therefore stay behind as the plane moves
on and drift down with the map scroll (1 px per simulation step, ~23 px/s)
for their 172 ms life. Sim-side timing is untouched: spawn cadence
(shoot_rate 2), anim rate, RNG consumption and demo playback are
identical to upstream; only the anim's reference frame changes.

## Input: no cursor snapping

Dialog/menu code no longer warps the mouse cursor onto the default
button: `SWD_SetWindowPtr`/`SWD_SetFieldPtr` were deleted along with all
callers (`store.cpp`, `windows.cpp`), as were the direct
`PTR_SetPos(field-center)` calls when opening ask dialogs, the difficulty
select, the hangar keyboard navigation and the ship computer. Keyboard
selection still highlights fields without moving the pointer. The
mission-start `PTR_SetPos(playerx, playery)` in `Do_Game` is kept — it
seeds mouse ship control, not menu focus.

## UI: in-game options menu with runtime video settings

The Options dialog now carries the HD-remaster video settings that were
previously boot-only INI keys. `ui/OPTS_SWD` was re-authored (same catalog
handle `0x1003f`; built by `tools/swdbuild.py` from
`tools/opts_swd_spec.py`) from 13 to 23 fields, adding FILTER, SCANLINES,
RESOLUTION, FULLSCREEN and ASPECT rows with selection icons beside the
existing Music/FX/Detail rows, and new `OPTS_*` ids in `src/winids.h`.
`src/i_video.cpp` gained runtime setters (`I_SetVideoFilter/Scanlines/
VideoResolution/Fullscreen/AspectCorrect`) that only touch presentation
resources — the factor-sized surface/texture pair was extracted from
`SetVideoMode` into `RebuildStreamTextures` so the filter can change
without re-creating the 8-bit screenbuffer. Changes live-apply from the
dialog and persist to `[Video]` SETUP.INI keys (`upscaler`, `scanlines`,
`fullscreen`, `aspect_ratio_correct`) on EXIT, and the dialog is also
reachable in-mission via the O key (`Do_Game`, bracketed like F1 help).

## Deliberately unchanged

- Game logic, mission data formats, audio synthesis — untouched.
- `GLB_*` API names and handle layout (`slot << 16 | item`) — kept so
  `src/fileids.h` and all call sites stay identical to upstream.
