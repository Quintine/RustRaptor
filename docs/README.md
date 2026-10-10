# RaptorReplica

The retained C++ engine described below is the playable reference. An independent
Rust rewrite is now selectable with `./play.sh --engine rust`; see
[Rust implementation and validation](rust-rewrite.md), [modding API](modding-api.md)
and [optional HD art](hd-art.md). Full Rust cutover acceptance remains in progress.

A faithful, playable replica of **Raptor: Call of the Shadows** (Cygnus
Studios, 1994) running the reconstructed original engine on Linux, with the
original game data extracted into a modern, editable asset tree.

## Quick start

```sh
./play.sh
```

Builds the engine on first run, then launches fullscreen. Saves and
`SETUP.INI` live in `~/.local/share/Raptor/` — nothing in the repo is
written to.

## Repository layout

| Path        | What it is |
|-------------|------------|
| `raptor/`   | Vendored engine source (GPLv2+), trimmed to a Linux-only build. Patches against upstream are listed in [upstream-patches.md](upstream-patches.md). |
| `data/`     | The asset tree the engine loads: one `INDEX` catalog plus category directories (`music/`, `sprites/`, ...). Derived from the copyrighted originals — **gitignored, never commit**. See [asset-pipeline.md](asset-pipeline.md). |
| `tools/glbextract.py` | Cracks the original `.GLB` archives into `data/`. See [glb-format.md](glb-format.md). |
| `docs/`     | This documentation. |
| `play.sh`   | One-command launcher (build if needed, run from `data/`). |
| `PLAN.md`   | Project status and roadmap. |

## Documentation index

- [architecture.md](architecture.md) — how the engine starts up and loads assets
- [glb-format.md](glb-format.md) — the original archive format and its cipher
- [asset-pipeline.md](asset-pipeline.md) — extraction, categories, the INDEX catalog
- [building.md](building.md) — dependencies, building, config and save paths
- [upstream-patches.md](upstream-patches.md) — every local diff against the vendored engine

## Status

Playable end to end: title/menu, hangar, store, ship computer, all mission
phases, original OPL2 soundtrack and Sound Blaster SFX through PipeWire/ALSA.
Verified on this machine at 1920x1080.

## Legal

- `raptor/` is GPLv2+; this project inherits GPL for everything built on it.
- Game data is copyrighted. `data/` is derived from the user's own purchased
  copy and is never committed.
