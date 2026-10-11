# Windows build

The repository includes `bin/raptor-rust.exe`, `bin/SDL2.dll` and `run.cmd`.
Double-click `run.cmd` after extracting the entire `RustRaptor` folder.
Windows and Linux share the same `data/`, `art/` and `mods/` directories;
the Windows launcher needs no Rust, Python, SDL installation or old engine.
Use a 64-bit Windows 10 or Windows 11 machine.

Windows pilots, settings and user mods live in `%APPDATA%\RaptorReplica`.
Derived artwork and audio caches use `%LOCALAPPDATA%\RaptorReplica\cache`.
Redirected folders are respected; `%USERPROFILE%\AppData` is a fallback.
Legacy import reads `%APPDATA%\Raptor`. Moving the game leaves profiles intact.

`runtime-windows-manifest.json` records executable, DLL, license and launcher
hashes and checked PE dependencies. The shared `runtime-manifest.json`
records every original/approved-HD data-file hash. The Windows exporter
excludes Linux libraries, build caches, local toolchains, review drafts and Git.

## Rebuild

The included build uses Rust 1.99.0, `x86_64-pc-windows-gnu` and the official
SDL2 2.32.10 MinGW SDK. Native Windows CI builds the same engine with MSVC and
statically links its C runtime.

On Linux with Rust's Windows target and MinGW-w64 installed:

```sh
rustup target add x86_64-pc-windows-gnu
python3 tools/assemble_windows.py \
  --sdl2-dir /path/to/SDL2-2.32.10 \
  --linker x86_64-w64-mingw32-gcc \
  --zip dist/RustRaptor-windows-x86_64.zip
```

Download the SDK from the [official SDL2 release](https://github.com/libsdl-org/SDL/releases/tag/release-2.32.10).
The MinGW tarball SHA256 is
`83a5d74012311edc3c0d40ea6faecbe57ad692aa033fa5dc273cc937e3938ff2`.
Rust's [Windows GNU target documentation](https://doc.rust-lang.org/rustc/platform-support/windows-gnu.html)
describes cross-toolchain requirements.

On Windows with Rust and Visual Studio C++ build tools:

```powershell
python tools/assemble_windows.py --target x86_64-pc-windows-msvc `
  --sdl2-dir C:\SDKs\SDL2-2.32.10 `
  --zip dist\RustRaptor-windows-x86_64.zip
```

Use the Visual C SDK for that command. Its official zip SHA256 is
`af347939395a58b365846aaea27391e69f9ec9d4dd650d6ac40802159b418a6e`.
The assembler checks architecture, SDL import, complete data hashes and DLL
dependencies. Supply `--extra-dll FILE` if another compiler introduces another
runtime dependency. Optional `--rustc` and `--sysroot` support an isolated
matching cross toolchain without changing the system Rust installation.

The [Windows workflow](../.github/workflows/windows.yml) runs simulation,
modding and save tests on Windows, validates packaged assets and all local
mods, captures SDL gameplay and publishes the zip as a workflow artifact.

## Validation checkpoint: 11 October 2026

The included GNU executable passed 279 portable tests under Wine 11.19,
including Windows save replacement and preserving a locked existing save.
All 22 installed mod hashes match their previous Linux hashes exactly.
The shared catalog validates 6,449 assets and the current packaged HD snapshot
validates all 340 supplied frames. The exporter verifies all 6,593 shared
data-file hashes and includes only checked Windows DLL dependencies.

The exported zip passed CRC and manifest checks, then launched through
`run.cmd` from another working directory after extraction into a path with
spaces and Unicode. Its HD gameplay capture renders at 1920×1080. The
original intro retains its 4:3 viewport with 240-pixel black side borders.
SDL captured three seconds of 44.1 kHz stereo audio; a separate capture with
music muted verified nonzero original sound effects (251,682 nonzero samples).

The [native Windows CI run](https://github.com/Quintine/RustRaptor/actions/runs/38119440288)
also passed all 279 portable tests, built the MSVC desktop release and
validated the exported folder's launcher, catalog, HD art, all mods and SDL
gameplay from a path with spaces and Unicode. The local GNU build additionally
ran Iron Coast mission 1 at 1080p with all 22 mods enabled and captured its
custom music. Both runs used SDL's dummy output drivers for automation;
physical Windows display, audio and controller hardware remain untested.
