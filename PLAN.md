# RaptorReplica — Raptor: Call of the Shadows

## Status: PLAYABLE — original engine, original data, original soundtrack

A faithful replica built **on the actual Raptor source code** (pivot from a
from-scratch engine, approved by project owner).

## Architecture (post-pivot)

| Path        | What it is |
|-------------|------------|
| `raptor/`   | Vendored upstream: nukeykt's reconstructed Raptor source (skynettx/raptor), GPLv2+. Original game logic, GLB asset loading, OPL2 music emulation (`i_oplmusic.cpp`), AdLib SFX. |
| `original/` | User-supplied original game data (GLB v1.2+ registered, 5 mission packs). **Gitignored — copyrighted.** |
| `game/`     | Runtime dir: GLB symlinks + built binary. **Gitignored.** |
| `src/`, `tests/`, `Makefile`, `ui_render.inc` | Legacy from-scratch prototype (X11+ALSA engine). Superseded by the pivot; preserved on branch `prototype-engine`. Scheduled for removal from main. |
| `play.sh`   | One-command launcher: links assets, builds if needed, runs. |

## Running

```sh
./play.sh          # builds on first run, then launches fullscreen 1080p
```

Requirements: SDL2 (installed user-local at `~/.local` if not in distro),
ALSA/PipeWire for sound. Config: `~/.local/share/Raptor/SETUP.INI`
(`fullscreen=1` set for 1920×1080 desktop resolution).

## Verified working (this machine, 2026-08-25)

- Builds clean with gcc + CMake (user-local CMake 3.30.3, SDL2 2.28.2).
- Registered v1.2 detected; original title screen, menus, intro cinematics.
- **Original OPL2 soundtrack + Sound Blaster SFX audible** (PulseAudio/PipeWire
  sink connected; required one-time `pactl set-card-profile` cycle to restore
  the real audio sink after a session-manager glitch).
- **In-mission gameplay verified by screenshot**: player fire, enemy fighters,
  credit pickups, scrolling terrain, score counter — at 1920×1080.

## The 5 mission packs

The registered v1.2 GLB data contains the original 5 campaign mission packs
(each mission: mountain → valley → sky phases + boss). These are the packs the
replica ships with — loaded from `original/` at runtime.

## Expansion roadmap (on top of the source)

1. Extra mission packs authored as new wave-table data in the original formats.
2. QoL patches kept as minimal diffs against upstream: resolution options,
   audio device selection, keybind config surface.
3. Track upstream (skynettx/raptor) and rebase the diff regularly.

## Legal

- `raptor/` is GPLv2+; this project inherits GPL for anything built on it.
- `original/` game data is never committed; users must supply their own copy.
