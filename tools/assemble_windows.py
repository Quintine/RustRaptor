#!/usr/bin/env python3
"""Build and include a Windows x86_64 runtime using the shared packaged catalog."""
import argparse
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import zipfile

from assemble_runtime import checked_file, digest, iter_archive_files


SYSTEM_DLLS = {
    "advapi32.dll", "bcrypt.dll", "bcryptprimitives.dll", "comdlg32.dll", "crypt32.dll", "dinput8.dll",
    "gdi32.dll", "hid.dll", "imm32.dll", "iphlpapi.dll", "kernel32.dll",
    "msvcrt.dll", "ntdll.dll", "ole32.dll", "oleaut32.dll", "powrprof.dll",
    "psapi.dll", "rpcrt4.dll", "secur32.dll", "setupapi.dll", "shell32.dll",
    "shlwapi.dll", "ucrtbase.dll", "user32.dll", "userenv.dll", "version.dll",
    "winmm.dll", "winspool.drv", "ws2_32.dll",
}


def pe_imports(path):
    """Read checked PE32+ headers and DLL imports without host-specific tools."""
    payload = path.read_bytes()
    def u32(offset):
        return struct.unpack_from("<I", payload, offset)[0]
    if len(payload) < 64 or payload[:2] != b"MZ":
        raise ValueError(f"not a Windows executable: {path}")
    header = u32(60)
    if payload[header:header+4] != b"PE\0\0":
        raise ValueError(f"invalid PE signature: {path}")
    machine, sections = struct.unpack_from("<HH", payload, header+4)
    optional_size = struct.unpack_from("<H", payload, header+20)[0]
    optional = header+24
    if machine != 0x8664 or struct.unpack_from("<H", payload, optional)[0] != 0x20B or optional_size < 128:
        raise ValueError(f"expected a Windows x86_64 PE32+ image: {path}")
    headers_size = u32(optional+60)
    # Dependency closure must include every runtime-loaded import. Delay
    # imports are not used by our builds; reject them rather than overlooking
    # a DLL needed only after the game has started.
    if u32(optional+108) > 13:
        if optional_size < 224 or any(struct.unpack_from("<II", payload, optional+216)):
            raise ValueError(f"unsupported PE delay imports: {path}")
    table = optional+optional_size
    def offset(rva):
        if rva < headers_size and rva < len(payload):
            return rva
        for index in range(sections):
            start = table+index*40
            virtual_size, address, raw_size, raw_offset = struct.unpack_from("<IIII", payload, start+8)
            if address <= rva < address+max(virtual_size, raw_size):
                delta = rva-address
                if delta < raw_size and raw_offset+delta < len(payload):
                    return raw_offset+delta
        raise ValueError(f"unmapped PE address in {path}")
    imports, size = struct.unpack_from("<II", payload, optional+120)
    if not imports:
        return []
    result = []
    for index in range(min(size//20, 4096)):
        descriptor = struct.unpack_from("<IIIII", payload, offset(imports+index*20))
        if not any(descriptor):
            return sorted(set(result))
        start = offset(descriptor[3])
        end = payload.find(b"\0", start, min(start+256, len(payload)))
        if end < 0:
            raise ValueError(f"unterminated PE import name: {path}")
        result.append(payload[start:end].decode("ascii").lower())
    raise ValueError(f"unterminated PE import table: {path}")


def sdk_files(root, target):
    if target.endswith("-msvc"):
        library = root / "lib/x64/SDL2.lib"
        dll = root / "lib/x64/SDL2.dll"
    else:
        if (root / "x86_64-w64-mingw32").is_dir():
            root = root / "x86_64-w64-mingw32"
        library = root / "lib/libSDL2.dll.a"
        dll = root / "bin/SDL2.dll"
    for path in (library, dll):
        if not path.is_file():
            raise ValueError(f"missing SDL2 Windows SDK file: {path}")
    return library, dll


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdl2-dir", type=Path, required=True, help="extracted SDL2 MinGW or Visual C SDK")
    parser.add_argument("--target", default="x86_64-pc-windows-msvc" if os.name == "nt" else "x86_64-pc-windows-gnu",
                        choices=["x86_64-pc-windows-gnu", "x86_64-pc-windows-msvc"])
    parser.add_argument("--cargo", default="cargo")
    parser.add_argument("--rustc", type=Path, help="optional matching compiler from an isolated toolchain")
    parser.add_argument("--linker", help="cross-linker command or full path")
    parser.add_argument("--sysroot", type=Path, help="optional isolated matching Rust target standard library")
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--extra-dll", type=Path, action="append", default=[])
    parser.add_argument("--zip", type=Path, help="export a Windows-only playable folder with source, docs and mods")
    args = parser.parse_args()
    package = Path(__file__).resolve().parents[1]
    library, sdl_dll = sdk_files(args.sdl2_dir.resolve(), args.target)
    license = args.sdl2_dir.resolve() / "COPYING.txt"
    if not license.is_file():
        license = args.sdl2_dir.resolve() / "LICENSE.txt"
    if not license.is_file():
        raise ValueError("SDL2 SDK license is missing")
    environment = os.environ.copy()
    if args.rustc:
        environment["RUSTC"] = str(args.rustc.resolve())
    key = args.target.upper().replace("-", "_")
    flags = ["-L", "native="+str(library.parent)]
    if args.sysroot:
        flags += ["--sysroot", str(args.sysroot.resolve())]
    if args.target.endswith("-msvc"):
        flags += ["-C", "target-feature=+crt-static"]
    # Encoded flags preserve SDK/sysroot paths containing spaces. Cargo's
    # explicit --target keeps these flags away from host build scripts.
    environment["CARGO_ENCODED_RUSTFLAGS"] = "\x1f".join(flags)
    if args.linker:
        environment["CARGO_TARGET_"+key+"_LINKER"] = args.linker
        linker = Path(args.linker)
        if linker.is_file():
            # Rust also invokes the cross toolchain's dlltool for raw Windows
            # imports; an isolated linker needs its sibling tools on PATH.
            environment["PATH"] = str(linker.resolve().parent)+os.pathsep+environment.get("PATH", "")
    build = package / "target/windows-runtime"
    if not args.skip_build:
        subprocess.run([args.cargo, "build", "--locked", "--release", "--target", args.target,
                        "--target-dir", str(build), "--bin", "raptor-rust", "--features", "desktop"],
                       cwd=package, env=environment, check=True)
    executable = build / args.target / "release/raptor-rust.exe"
    dependencies = pe_imports(executable)
    if "sdl2.dll" not in dependencies:
        raise ValueError("Windows binary has no SDL2 import; rebuild the desktop feature")
    bundle = {"raptor-rust.exe": executable, "SDL2.dll": sdl_dll}
    for extra in args.extra_dll:
        if extra.name.lower() in {name.lower() for name in bundle}:
            raise ValueError(f"duplicate bundled DLL: {extra.name}")
        bundle[extra.name] = extra.resolve()
    bundled_names = {name.lower() for name in bundle}
    dependency_report = {}
    for name, path in bundle.items():
        imports = pe_imports(path)
        unresolved = [dll for dll in imports if dll not in SYSTEM_DLLS and dll not in bundled_names
                      and not dll.startswith(("api-ms-win-", "ext-ms-win-"))]
        if unresolved:
            raise ValueError(f"unbundled Windows dependency for {name}: {unresolved}; supply --extra-dll")
        dependency_report[name] = imports
    data_manifest = json.loads((package / "runtime-manifest.json").read_text())
    for name, expected in data_manifest["files"].items():
        if digest(checked_file(package, name)) != expected:
            raise ValueError(f"packaged data differs from runtime manifest: {name}; refresh the shared bundle first")
    (package / "bin").mkdir(exist_ok=True)
    for name, path in bundle.items():
        shutil.copy2(path, package / "bin" / name)
    shutil.copy2(license, package / "bin/SDL2-WINDOWS-LICENSE.txt")
    report = {"format_version": 1, "platform": "Windows x86_64", "target": args.target,
              "catalog_entries": data_manifest["catalog_entries"],
              "approved_hd_frames": data_manifest["approved_hd_frames"],
              "shared_data_manifest": "runtime-manifest.json", "dependencies": dependency_report,
              "files": {"bin/"+name: digest(package / "bin" / name) for name in bundle},
              "launcher": "run.cmd", "validation": "PE imports and complete shared data hashes; see docs/windows-build.md"}
    report["files"]["bin/SDL2-WINDOWS-LICENSE.txt"] = digest(package / "bin/SDL2-WINDOWS-LICENSE.txt")
    report["files"]["run.cmd"] = digest(package / "run.cmd")
    (package / "runtime-windows-manifest.json").write_text(json.dumps(report, indent=2)+"\n")
    if os.name == "nt":
        subprocess.run([str(package / "bin/raptor-rust.exe"), "--verify-assets"], cwd=package.parent, check=True)
    if args.zip:
        archive = args.zip.resolve()
        archive.parent.mkdir(parents=True, exist_ok=True)
        skipped = {"target", "dist", ".reference", ".local", "derived", "__pycache__", ".git", "lib"}
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as output:
            for path in iter_archive_files(package, archive, skipped,
                                           excluded_files=(Path("bin/raptor-rust"),),
                                           required_files=data_manifest["files"]):
                relative = path.relative_to(package)
                output.write(path, str(Path("RustRaptor") / relative))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
