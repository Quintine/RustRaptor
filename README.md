# RaptorReplica

A Linux replica of Raptor: Call of the Shadows, with the retained C++ engine and an independent Rust engine under development.

```sh
./play.sh --engine rust
./play.sh --engine legacy
```

The C++ engine remains the launcher default while Rust gameplay parity and full-game acceptance are verified. Rust includes SDL2 input, interpolated indexed rendering, audio, all 27 original mission definitions, deterministic simulation, pilot slots, separate saves, cinematics, an in-game mod manager, bounded Rhai scripting, crisp sprite filters and an optional HD artwork setting.

The local HD proof replaces one player frame; other frames use original artwork. It is not a complete remaster. Longer reference replays, full campaign playthroughs and presentation fidelity remain in validation.

- [Building and running](docs/building.md)
- [Rust implementation and validation](docs/rust-rewrite.md)
- [Mod API and schemas](docs/modding-api.md)
- [Optional HD artwork](docs/hd-art.md)
- [Asset extraction](docs/asset-pipeline.md)
- [Milestones](PLAN.md)

Code is GPL-2.0-or-later; the vendored Rust FM emulator is LGPL-2.1-or-later. Original game catalog assets, local HD remaster proofs, builds, caches and recordings stay outside Git. Authored mod SD/HD images and sounds are included in Git. Supply your own licensed data in `data/`.
