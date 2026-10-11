# Standalone game packages

`RustRaptor/` contains the Rust executable, its original data catalog, approved
HD replacements, authored mods, SD/HD mod artwork, sound effects and music.
Normal play needs no C++ engine, Cargo, Python or source checkout. Run
`./run.sh` on Linux or `run.cmd` on Windows; installed pilots and configuration remain in the user's separate
`RaptorReplica` profile directories.

The executable finds its package from `bin/raptor-rust`, including when launched
from another working directory. A missing packaged catalog reports an error
instead of selecting another checkout's data. `--data` and `--mods` remain
available for deliberate overrides.

From this folder, run:

```sh
python3 tools/assemble_runtime.py --zip dist/RustRaptor-linux-x86_64.zip
```

The assembler builds the desktop release, copies all catalog-listed files and
the exact currently approved HD manifest, provenance and referenced PNGs, installs the
binary and SDL2 shared library if linked, and checks the packaged catalog.
Desktop packaging uses its own `target/desktop-runtime` build directory so
concurrent headless asset reviews cannot replace the packaged executable.
`runtime-manifest.json` records file hashes, catalog/HD counts and platform
dependencies. Unapproved HD drafts, reference screenshots and the Cargo build
cache are excluded from the zip. The exported `RustRaptor` folder can be moved
or unpacked anywhere, including paths containing spaces.

Use `--source-data PATH` for an original catalog and `--hd-source PATH` for
a separately frozen, reviewed HD pack containing `hd.json`. This keeps
the packaged artwork stable while artists continue working on later batches.

The Linux binary targets Linux x86_64 and uses the operating system's C runtime
and desktop/audio drivers. The included Windows x86_64 executable and SDL2 DLL
use the same data and mods. See [Windows packaging](windows-build.md)
for its separate launcher, build tool, manifest, zip and validation.
Source, Cargo.lock, code licenses and mod API documentation are included.
The packaged executable, runtime libraries, original catalog and approved HD
artwork are tracked in Git, along with the assembler and authored mod images
and sounds. Build caches, working art drafts, review evidence and duplicate zip
exports are excluded. See [repository layout](repository.md).

Re-run the assembler after engine changes, new approved HD registrations or
mod edits to refresh the package. The runtime snapshot contains approved art
only; it does not claim the full original HD catalog is complete.

The current runtime contains **6,449 catalog entries, 1,148 approved HD frames
and 6,848 data files**. There are **45 bundled mod packages**, including the
23 packages for [Iron Coast II: Black Tide](iron-coast-stage2-design.md).
All installed mods pass catalog validation; Stage 2 adds no overrides. The
one existing override belongs to the Stage 1 campaign progression package.

The earlier 800-frame/22-mod archives passed relocated-folder launch, 1080p
SDL rendering, music and isolated sound-effect captures. Their original-intro
capture confirms a 1440×1080 video area with black 240-pixel side borders.
Removing the copied catalog reports its own missing path rather than using a
development checkout. The final Stage 2 archive checks are recorded after
export so their evidence refers to the exact distributed bytes. Native
`unzip` preserves the executable permissions stored in the Linux archive.
