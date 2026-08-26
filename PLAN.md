# RaptorReplica — Raptor: Call of the Shadows

**Status: PLAYABLE** — original engine, original data, extracted into a
modern asset tree. Full documentation lives in [`docs/`](docs/README.md):

- [docs/README.md](docs/README.md) — overview, layout, quick start
- [docs/architecture.md](docs/architecture.md) — startup flow, asset handles, subsystems
- [docs/glb-format.md](docs/glb-format.md) — reverse-engineered GLB archive format + cipher
- [docs/asset-pipeline.md](docs/asset-pipeline.md) — data/ tree, INDEX catalog, editing content
- [docs/building.md](docs/building.md) — dependencies, build, config/save paths
- [docs/upstream-patches.md](docs/upstream-patches.md) — every diff against the vendored engine

Run with `./play.sh`.

## The 5 mission packs

The registered data ships 5 campaign packs (each mission: mountain → valley
→ sky phases + boss). Pack presence is detected from catalog slots at boot;
slot 2 or 3 present flips the engine to registered mode.

## Roadmap (on top of the source)

1. Extra mission packs authored as new cataloged assets in the original
   formats.
2. QoL patches kept as documented diffs against upstream (see
   [docs/upstream-patches.md](docs/upstream-patches.md)): resolution options,
   audio device selection, keybind config surface. Landed so far: decoupled
   interpolated rendering (presentation at display rate, simulation at the
   original 70/3 Hz), borderless window mode (`Video/borderless`), removal
   of menu cursor snapping.
3. Track upstream (skynettx/raptor) and rebase the documented diffs.

## Legal

- `raptor/` is GPLv2+; this project inherits GPL for anything built on it.
- `data/` is derived from the user's own purchased copy (copyrighted);
  it is gitignored and never committed.
