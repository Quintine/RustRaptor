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

## Current runtime and validation

The included GNU executable uses the reviewed **1,148-frame HD snapshot**;
the shared manifest binds **6,848 data files** and the package contains
**45 installed mods**. Its SHA-256 is
`a74cc4ea20ddc17a39fe4cbf2da2e7391a561d1975b114ec56dd35fb5ff38f2d`.
The [1,148-frame native Windows run](https://github.com/Quintine/RustRaptor/actions/runs/38126069413)
passed portable tests, exact committed GNU runtime checks, the MSVC desktop
build and exported-folder catalog, HD, mod and SDL gameplay validation. That
run preceded the Stage 2 content commit; it verifies the engine and the
previous 22 mod packages.

The expanded workflow additionally completes all eight Black Tide missions
and a saved finale replay with normal firing/input and paid repairs. It then
checks all 45 mods and captures Stage 2 gameplay, FM music and music-muted
sound effects from the MSVC package. Final archive relocation evidence is
recorded after export and identifies the exact ZIP tested.

Earlier Windows checkpoints passed 279 portable tests under Wine 11.19,
including save replacement and preservation of a locked existing save.
The 800-frame/22-mod archive passed CRC, manifest and relocated Unicode/space
folder checks through `run.cmd`, 1920×1080 HD rendering, exact 4:3 intro
borders, stereo music and isolated original effects. Native Windows runs
[38119440288](https://github.com/Quintine/RustRaptor/actions/runs/38119440288),
[38119943948](https://github.com/Quintine/RustRaptor/actions/runs/38119943948)
and [38121272504](https://github.com/Quintine/RustRaptor/actions/runs/38121272504)
record those earlier snapshots. Automated SDL checks use dummy drivers;
physical Windows display, audio and controller hardware remain untested.
