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


def default_data_source(package):
    """The portable package is authoritative when it has its own catalog."""
    bundled = package / "data"
    return bundled if (bundled / "INDEX").is_file() else package.parent / "data"


def checked_tree(root):
    """Select a complete contained file tree; never silently follow/skip symlink directories."""
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError(f"not a runtime data directory: {root}")
    def raise_walk_error(error):
        raise error

    files = {}
    for directory, directories, names in os.walk(root, followlinks=False, onerror=raise_walk_error):
        parent = Path(directory)
        for name in directories:
            if (parent / name).is_symlink():
                raise ValueError(f"symlink directory in runtime data: {parent / name}")
        for name in names:
            relative = (parent / name).relative_to(root).as_posix()
            files[relative] = checked_file(root, relative)
    return files


def select_data_files(package, source=None, hd_source=None):
    """Validate and select the complete runtime data without copying or mutating it."""
    source = (source or default_data_source(package)).resolve(strict=True)
    files = checked_tree(source)
    entries = checked_file(source, "INDEX").read_text().splitlines()
    catalog = {"INDEX"}
    for row in entries:
        if not row.strip():
            continue
        _, length, name = row.split()
        original = checked_file(source, name)
        if original.stat().st_size != int(length):
            raise ValueError(f"catalog size mismatch: {name}")
        catalog.add(Path(name).as_posix())

    if hd_source is not None:
        hd_source = hd_source.resolve(strict=True)
        replacement = checked_tree(hd_source)
        checked_file(hd_source, "hd.json")
        if any(Path(name).parts[0] == "hd" for name in catalog):
            raise ValueError("HD pack paths conflict with the original catalog")
        files = {name: path for name, path in files.items() if Path(name).parts[0] != "hd"}
        files.update({"hd/" + name: path for name, path in replacement.items()})

    hd_frames = 0
    if "hd/hd.json" in files:
        hd = json.loads(files["hd/hd.json"].read_bytes())
        hd_root = hd_source if hd_source is not None else source / "hd"
        for sequence in hd["sequences"]:
            for frame in sequence["frames"]:
                payload = checked_file(hd_root, frame["file"])
                name = "hd/" + Path(frame["file"]).as_posix()
                if name not in files or files[name] != payload:
                    raise ValueError(f"HD frame is missing from runtime selection: {name}")
                if name in catalog:
                    raise ValueError("HD pack paths conflict with the original catalog")
                hd_frames += 1

    # Original missions register these 27 SD/HD pairs in src/content.rs.
    # An external legacy catalog need not carry new menu art; the bundled art
    # is the only fallback, and existing external briefing files keep priority.
    bundled = (package / "data").resolve()
    required_briefings = [
        f"briefings/sector_{sector}_wave_{wave}_{mode}.png"
        for sector in range(1, 4) for wave in range(1, 10) for mode in ("sd", "hd")
    ]
    if source != bundled and any(name not in files for name in required_briefings):
        briefings = bundled / "briefings"
        if briefings.is_symlink():
            raise ValueError(f"symlink directory in bundled mission briefings: {briefings}")
        for name, path in checked_tree(briefings).items():
            files.setdefault("briefings/" + name, path)
    for name in required_briefings:
        if name not in files:
            raise ValueError(f"required mission briefing is missing: {name}")
    return files, entries, hd_frames


def iter_archive_files(package, archive, skipped, excluded_files=(), required_files=()):
    """Keep manifest payloads even when a parent has a build-cache name."""
    required = {Path(name) for name in required_files}
    required_directories = {parent for path in required for parent in path.parents}
    for relative in required:
        checked_file(package, relative)

    def excluded(relative):
        if relative in required or relative in required_directories:
            return False
        return (skipped.intersection(relative.parts)
                or any(part.startswith(".runtime-data-") for part in relative.parts)
                or (len(relative.parts) >= 4 and relative.parts[0] == "mods"
                    and relative.parts[2:4] == ("art", "source")))

    files = []
    for directory, directories, names in os.walk(package, followlinks=False):
        parent = Path(directory)
        directories[:] = [name for name in directories
                          if not excluded((parent / name).relative_to(package))]
        for name in names:
            path = parent / name
            relative = path.relative_to(package)
            if (not excluded(relative) and relative not in excluded_files and path.is_file()
                    and path.resolve() != archive):
                files.append(path)
    missing = required - {path.relative_to(package) for path in files}
    if missing:
        raise ValueError(f"runtime archive is missing required files: {sorted(map(str, missing))}")
    yield from sorted(files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-data", type=Path)
    parser.add_argument("--hd-source", type=Path,
                        help="approved HD pack containing hd.json; defaults to SOURCE_DATA/hd")
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--zip", type=Path, help="export runtime, source, docs and mods; exclude build caches")
    args = parser.parse_args()
    package = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    local_lib = Path.home() / ".local/lib"
    environment["LD_LIBRARY_PATH"] = str(local_lib) + ":" + environment.get("LD_LIBRARY_PATH", "")
    # Asset-review helpers also build a headless release. Keep the desktop
    # artifact separate so concurrent validation cannot replace this binary.
    desktop_target = package / "target/desktop-runtime"
    if not args.skip_build:
        subprocess.run(["cargo", "build", "--locked", "--release", "--target-dir", str(desktop_target),
                        "--bin", "raptor-rust", "--features", "desktop"],
                       cwd=package, env=environment, check=True)
    executable = desktop_target / "release/raptor-rust"
    if not executable.is_file():
        raise ValueError("release executable is missing; run without --skip-build")

    files, entries, hd_frames = select_data_files(package, args.source_data, args.hd_source)

    staging = Path(tempfile.mkdtemp(prefix=".runtime-data-", dir=package))
    try:
        for name in sorted(files):
            destination = staging / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(files[name], destination)
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
        skipped = {"target", "dist", ".reference", ".local", "derived", "__pycache__", ".git"}
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as output:
            for path in iter_archive_files(package, archive, skipped,
                                           required_files=report["files"]):
                relative = path.relative_to(package)
                output.write(path, str(Path("RustRaptor") / relative))
    print(json.dumps({key: value for key, value in report.items() if key not in {"files", "system_dependencies"}}, indent=2))


if __name__ == "__main__":
    main()
