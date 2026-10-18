# Current standalone packaging checkpoint — 19 October 2026

The runtime includes SD/HD mission briefings for all 42 missions: 27 Original, 14 Iron Coast and Aurora. Menu previews use a shared 132×70 logical-pixel full-RGB viewport with aspect-preserving centered cropping; original intro and gameplay retain 4:3 presentation within the 16:9 display. Iron Coast display names include stage/mission numbers; stable IDs and saved equipment/progression references remain unchanged. Cosmetic mod updates can trigger the usual changed-package save confirmation.

The current checked snapshot contains **6,449 catalog entries, 5,596 approved Original HD pictures and 10,689 data files / 8,691,739,470 bytes**, plus the 45 bundled mod packages. The briefing pass adds 240 data files; mod SD refreshes do not change that data count. The 157 remaining Original sprite/terrain remasters are unchanged. Linux and Windows SourceG2 executables were rebuilt; new native Windows CI evidence remains pending.

The assembler prefers `RustRaptor/data` when its `INDEX` is present and selects the complete contained data tree, including `data/briefings/` and its provenance. An explicit `--hd-source PATH` replaces the selected `hd/` subtree with that complete checked pack. With an external catalog, missing required Original briefing pairs are supplied from the bundled briefing tree while existing external files keep priority. Selection checks preserve package containment and required briefing files. This checkpoint records the refreshed runtime and selector checks; earlier full archive/export and relocation receipts below retain their dated scope.

# Earlier standalone package notes — retained historical snapshot

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

The corrected Stage 2 Linux and Windows archives pass CRC, complete data and
mod hashes, and relocated launch from `/tmp` in folders containing spaces and
Unicode. Both launchers capture the first mission and finale at 1920×1080 in
HD, with separate three-second music-only and effects-only stereo recordings.
Every recording contains audio without clipping. The original intro occupies
1440×1080 with black 240-pixel side borders even when gameplay aspect correction
is disabled. The pictures have been visually inspected. These entry captures
complement the full simulation campaign/save checks; they do not claim a full
interactive playthrough. Native `unzip` preserves Linux executable permissions.

The full runtime proofs bind Linux ZIP SHA-256
`07c81928ccfdd25bf05316cce74e17d42a0c4f00dfa6e67da48b6e97192fe861`
and Windows ZIP SHA-256
`4c48ca7f6fd532db5247820182c1fb00fcf94def605f69b727f10ed3fcd3b008`.
Final exports refresh documentation and packaging metadata. A strict successor
check compares complete archive membership and payloads and requires identical
game executables, platform libraries, launchers, data, all mod packages and
content hashes. It separately identifies permitted documentation/manifest and
exporter-tool changes; the runtime proof is retained rather than relabeled as
a fresh SDL run on different ZIP bytes. Local receipts are stored under
`.reference/iron-coast-stage2/` and the Linux review directory in the parent
workspace.

Linux all-mod startup measured 7.3–13.5 seconds in the relocation checks.
Windows/Wine timings were measured under shared compilation load and are not
directly comparable. Automated captures use SDL dummy drivers and the software
renderer; physical display/audio/controller and hardware frame rates remain
manual checks. Removing the copied catalog reports its own missing path rather
than using a development checkout. Earlier 800-frame/22-mod receipts remain
historical and are not used to approve the corrected runtime.
