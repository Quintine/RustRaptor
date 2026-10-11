#!/usr/bin/env python3
"""Refresh the self-contained Linux runtime and optionally export a clean zip."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import zipfile


def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def checked_file(root, relative):
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe runtime path: {relative}")
    resolved = (root / path).resolve(strict=True)
    resolved.relative_to(root.resolve())
    if not resolved.is_file():
        raise ValueError(f"not a runtime file: {relative}")
    return resolved


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-data", type=Path)
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--zip", type=Path, help="export runtime, source, docs and mods; exclude build caches")
    args = parser.parse_args()
    package = Path(__file__).resolve().parents[1]
    working_data = package.parent / "data"
    default_data = working_data if (working_data / "INDEX").is_file() else package / "data"
    source = (args.source_data or default_data).resolve()
    environment = os.environ.copy()
    local_lib = Path.home() / ".local/lib"
    environment["LD_LIBRARY_PATH"] = str(local_lib) + ":" + environment.get("LD_LIBRARY_PATH", "")
    if not args.skip_build:
        subprocess.run(["cargo", "build", "--locked", "--release", "--bin", "raptor-rust", "--features", "desktop"],
                       cwd=package, env=environment, check=True)
    executable = package / "target/release/raptor-rust"
    if not executable.is_file():
        raise ValueError("release executable is missing; run without --skip-build")

    files = {"INDEX"}
    entries = (source / "INDEX").read_text().splitlines()
    for row in entries:
        if not row.strip():
            continue
        _, length, name = row.split()
        original = checked_file(source, name)
        if original.stat().st_size != int(length):
            raise ValueError(f"catalog size mismatch: {name}")
        files.add(name)
    hd_path = source / "hd/hd.json"
    hd_bytes = hd_path.read_bytes() if hd_path.is_file() else None
    hd_frames = 0
    if hd_bytes:
        hd = json.loads(hd_bytes)
        files.add("hd/hd.json")
        for sequence in hd["sequences"]:
            for frame in sequence["frames"]:
                checked_file(source / "hd", frame["file"])
                files.add("hd/" + frame["file"])
                hd_frames += 1

    staging = Path(tempfile.mkdtemp(prefix=".runtime-data-", dir=package))
    try:
        for name in sorted(files):
            destination = staging / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            if name == "hd/hd.json":
                destination.write_bytes(hd_bytes)
            else:
                shutil.copy2(checked_file(source, name), destination)
        previous = package / ".runtime-data-previous"
        if previous.exists():
            raise ValueError("previous interrupted package exists; preserve/recover .runtime-data-previous before retrying")
        data = package / "data"
        if data.exists():
            data.rename(previous)
        try:
            staging.rename(data)
        except BaseException:
            if previous.exists():
                previous.rename(data)
            raise
        if previous.exists():
            shutil.rmtree(previous)
    finally:
        if staging.exists():
            shutil.rmtree(staging)

    (package / "bin").mkdir(exist_ok=True)
    shutil.copy2(executable, package / "bin/raptor-rust")
    dependencies = subprocess.run(["ldd", str(executable)], env=environment,
                                  capture_output=True, text=True, check=False).stdout
    if "not found" in dependencies:
        raise ValueError("unresolved release dependency:\n" + dependencies)
    sdl_libraries = re.findall(r"libSDL2[^ ]* => ([^ ]+)", dependencies)
    if not sdl_libraries:
        raise ValueError("release binary has no SDL2 dependency; rebuild with the desktop feature")
    for library in sdl_libraries:
        destination = package / "lib"
        destination.mkdir(exist_ok=True)
        shutil.copy2(Path(library).resolve(), destination / "libSDL2-2.0.so.0")
        copyright_file = Path("/usr/share/doc/libsdl2-2.0-0/copyright")
        if copyright_file.is_file():
            shutil.copy2(copyright_file, destination / "SDL2-COPYRIGHT.txt")
    report = {"format_version": 1, "platform": "Linux x86_64", "catalog_entries": len([row for row in entries if row.strip()]),
              "approved_hd_frames": hd_frames, "binary_sha256": digest(package / "bin/raptor-rust"),
              "data_files": len(files), "data_bytes": sum((package / "data" / name).stat().st_size for name in files),
              "files": {"data/" + name: digest(package / "data" / name) for name in sorted(files)},
              "system_dependencies": dependencies.splitlines()}
    (package / "runtime-manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    subprocess.run([str(package / "run.sh"), "--verify-assets"], cwd="/", check=True)
    if args.zip:
        archive = args.zip.resolve()
        archive.parent.mkdir(parents=True, exist_ok=True)
        skipped = {"target", "dist", ".reference", "__pycache__", ".git"}
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as output:
            for path in sorted(package.rglob("*")):
                relative = path.relative_to(package)
                if path.is_file() and not skipped.intersection(relative.parts) and path.resolve() != archive:
                    if any(part.startswith(".runtime-data-") for part in relative.parts):
                        continue
                    output.write(path, str(Path("RustRaptor") / relative))
    print(json.dumps({key: value for key, value in report.items() if key not in {"files", "system_dependencies"}}, indent=2))


if __name__ == "__main__":
    main()
