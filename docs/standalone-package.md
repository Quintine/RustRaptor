# Standalone Linux package

`RustRaptor/` contains the Rust executable, its original data catalog, approved
HD replacements, authored mods, SD/HD mod artwork, sound effects and music.
Normal play needs no C++ engine, Cargo, Python or source checkout. Run
`./run.sh`; installed pilots and configuration remain in the user's separate
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
the exact currently approved HD manifest and referenced PNGs, installs the
binary and SDL2 shared library if linked, and checks the packaged catalog.
`runtime-manifest.json` records file hashes, catalog/HD counts and platform
dependencies. Unapproved HD drafts, reference screenshots and the Cargo build
cache are excluded from the zip. The exported `RustRaptor` folder can be moved
or unpacked anywhere, including paths containing spaces.

The binary targets Linux x86_64. It still uses the operating system's C runtime
and desktop/audio drivers; this package is not a Windows or macOS executable.
Source, Cargo.lock, code licenses and mod API documentation are included.
The packaged executable, runtime libraries, original catalog and approved HD
artwork are tracked in Git, along with the assembler and authored mod images
and sounds. Build caches, working art drafts, review evidence and duplicate zip
exports are excluded. See [repository layout](repository.md).

Re-run the assembler after engine changes, new approved HD registrations or
mod edits to refresh the package. The runtime snapshot contains approved art
only; it does not claim the full original HD catalog is complete.

The current package was unpacked into a folder containing spaces and launched
from `/tmp` with only its bundled SDL2 library on the library search path.
Catalog validation checked 6,449 assets, 27 missions, 528 enemies, 16 weapons
and 24 items. All 22 bundled mods and all 221 approved HD frames validated.
Menu and gameplay screenshots at 1280×800 and 1920×1080, plus stereo audio
captures, completed successfully. Native `unzip` preserves the executable
permissions stored in the archive.
An original-intro capture at 1080p also confirms a 1440×1080 video area and
black 240-pixel side borders when gameplay stretching is enabled. Removing
the copied catalog produces an error at the copied data path, with no fallback
to the development checkout.
