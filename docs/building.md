# Building and running

## Requirements

- Linux with X11 (developed and verified on Arch, Cinnamon)
- GCC or Clang with C++11
- CMake >= 3.10
- SDL2 development libraries (a user-local build in `~/.local` works —
  `play.sh` extends `LD_LIBRARY_PATH` accordingly)
- ALSA (PipeWire's ALSA bridge is what this machine actually uses)

## Build and run

```sh
./play.sh
```

`play.sh` checks `data/INDEX`, builds `raptor/build/bin/raptor` on first run
(`cmake -DCMAKE_BUILD_TYPE=Release`, then `make -j$(nproc)`), and executes
the engine with `data/` as the working directory — the engine resolves the
catalog and assets relative to the CWD.

Manual equivalent:

```sh
cmake -E make_directory raptor/build
cmake -S raptor -B raptor/build -DCMAKE_BUILD_TYPE=Release
cmake --build raptor/build -j$(nproc)
cd data && ../raptor/build/bin/raptor
```

Targets:

- `raptor` — the game
- `raptorsetup` — the original text-mode setup tool (audio/input settings)

## Runtime files

| File | Location |
|------|----------|
| `SETUP.INI` | `~/.local/share/Raptor/` |
| Save games | `~/.local/share/Raptor/` |
| High scores | `~/.local/share/Raptor/` |

Useful `SETUP.INI` settings (created on first exit): `fullscreen=1` for
borderless 1080p, `aspect_ratio_correct`, `txt_fullscreen` (obsolete here —
the text-mode exit screen was removed).

## Command-line options

The engine accepts the original demo flags:

```sh
raptor REC demo.dmo   # record a demo
raptor PLAY demo.dmo  # play one back
```

## Troubleshooting

- **"All game data files NOT FOUND"** — `data/INDEX` missing or empty;
  restore the asset tree (see [asset-pipeline.md](asset-pipeline.md)).
- **No audio** — check the ALSA/PipeWire sink; the original mixer expects a
  working default ALSA device. If a session-manager glitch leaves the wrong
  card profile active, `pactl set-card-profile` back to the real one.
- **Silent early exit** — since the local patch, engine errors print to
  stderr before exiting; run from a terminal and read the message.

## Build layout

- `raptor/CMakeLists.txt` — Linux-only (Windows/Android/OSX support was
  stripped; see [upstream-patches.md](upstream-patches.md))
- `raptor/build/` — gitignored build tree
- `raptor/include/textscreen/` — text UI library (used by `raptorsetup`)
- `raptor/include/TinySoundFont/` — SF2 MIDI fallback synth
