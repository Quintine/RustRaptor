# Repository and playable bundle

`RustRaptor/` is the Git repository root. Run Git commands, `./run.sh` and
Cargo commands from this folder. The public remote is
[Quintine/RustRaptor](https://github.com/Quintine/RustRaptor), on branch
`codex/rust-rewrite`.

The repository includes the Linux executable in `bin/`, its bundled libraries
in `lib/`, the complete original game catalog and approved HD snapshot in
`data/`, and `runtime-manifest.json`. All authored mod definitions, scripts,
SD/HD artwork, sounds and music are included. A fresh checkout can launch the
bundled game with `./run.sh` without compiling it.

Build output in `target/`, local review evidence in `.reference/`, generation
source references and duplicate zip exports in `dist/` are ignored. Working
HD candidates in the old parent directory remain outside this repository;
the assembler copies approved runtime artwork into tracked `data/`.

Refresh the bundle after reviewed source, mod or HD changes:

```sh
python3 tools/assemble_runtime.py --source-data ../data
git add bin lib data runtime-manifest.json
```

The 11 October 2026 repository relocation preserves previous commits and uses
a normal forward commit. Older commits use paths such as `RustRaptor/src/`;
the current tree uses `src/`. The legacy C++ checkout remains on this drive
outside the current Git root and is available in the preserved history.
