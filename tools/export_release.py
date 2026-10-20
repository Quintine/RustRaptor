#!/usr/bin/env python3
"""Export a frozen, unchanged playable package as independently extractable ZIPs.

No builds, data staging, runtime-manifest rewriting, Git changes or uploads.
Each platform core plus ALL shared data ZIPs extracts into one RustRaptor folder.
"""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import time
import zipfile

from assemble_runtime import checked_file, digest

MAX_ASSET_BYTES = 2 * 1024**3  # GitHub requires each release asset UNDER 2 GiB.
DEFAULT_VOLUME_BYTES = 1_500_000_000
ROOT_DISK_FLOOR = 1_800_000_000
SKIPPED = {"target", "dist", ".reference", ".local", "derived", "__pycache__", ".git"}


def read_json(path):
    return json.loads(Path(path).read_bytes())


def write_new_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def git_commit(package):
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=package, text=True).strip()


def require_clean_workspace(package):
    if subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=all"], cwd=package):
        raise ValueError("release exports require a clean, fully committed workspace")


def snapshot_identity(package):
    return {"commit": git_commit(package),
            "runtime_manifest_sha256": digest(package / "runtime-manifest.json"),
            "windows_manifest_sha256": digest(package / "runtime-windows-manifest.json")}


def check_snapshot(package, plan):
    require_clean_workspace(package)
    if snapshot_identity(package) != plan["snapshot"]:
        raise ValueError("source commit or runtime manifests changed after release planning")


def entry(package, name, expected=None):
    path = checked_file(package, name)
    safe_member("RustRaptor/" + name)
    return {"name": name, "bytes": path.stat().st_size,
            "sha256": expected if expected is not None else digest(path)}


def safe_member(name):
    """All exports are portable ordinary files below the one installation root."""
    if not isinstance(name, str) or not name.startswith("RustRaptor/") or "\\" in name:
        raise ValueError("unsafe release member path")
    parts = name.split("/")
    reserved = {"CON", "PRN", "AUX", "NUL"} | {f"{prefix}{i}" for prefix in ("COM", "LPT") for i in range(1, 10)}
    if any(not part or part in (".", "..") or part.endswith((".", " "))
           or any(ord(c) < 32 or c in '<>:"|?*' for c in part)
           or part.split(".")[0].upper() in reserved for part in parts):
        raise ValueError("unsafe or nonportable release member path")
    return name


def selected_runtime_files(package):
    """Explicit finite no-follow inventory; skipped private namespaces stay private."""
    files = []
    visited = 0

    def excluded(relative):
        if relative.parts[0] == "data":
            return False  # The complete physical runtime tree is mandatory.
        return (bool(SKIPPED.intersection(relative.parts))
                or any(part.startswith(".runtime-data-") for part in relative.parts)
                or (len(relative.parts) >= 4 and relative.parts[0] == "mods"
                    and relative.parts[2:4] == ("art", "source")))

    def walk(directory, depth):
        nonlocal visited
        if depth > 128:
            raise ValueError("release source tree exceeds the 128-level inventory bound")
        with os.scandir(directory) as stream:
            children = sorted(stream, key=lambda child: child.name)
        for child in children:
            path = Path(child.path)
            relative = path.relative_to(package)
            if excluded(relative):
                continue
            visited += 1
            if visited > 1_000_000:
                raise ValueError("release source tree exceeds the one-million-entry inventory bound")
            metadata = child.stat(follow_symlinks=False)
            if stat.S_ISLNK(metadata.st_mode):
                raise ValueError(f"symlink in selected release tree: {relative}")
            if stat.S_ISDIR(metadata.st_mode):
                walk(path, depth + 1)
            elif stat.S_ISREG(metadata.st_mode):
                files.append(path)
            else:
                raise ValueError(f"non-regular member in selected release tree: {relative}")
    walk(package, 0)
    return sorted(files)


def partition(rows, budget):
    if type(budget) is not int or not 0 < budget <= DEFAULT_VOLUME_BYTES:
        raise ValueError("ZIP volume budget must be positive and at most 1,500,000,000 bytes")
    groups, current, size = [], [], 0
    for row in rows:
        if row["bytes"] > budget:
            raise ValueError(f"one runtime file exceeds ZIP volume budget: {row['name']}")
        if current and size + row["bytes"] > budget:
            groups.append(current)
            current, size = [], 0
        current.append(row)
        size += row["bytes"]
    if current:
        groups.append(current)
    return groups


def build_plan(package, expected_commit, budget=DEFAULT_VOLUME_BYTES):
    package = Path(package).resolve(strict=True)
    if not re.fullmatch(r"[0-9a-f]{40}", expected_commit):
        raise ValueError("an exact final tested Git commit is required")
    require_clean_workspace(package)
    snapshot = snapshot_identity(package)
    if snapshot["commit"] != expected_commit:
        raise ValueError("package HEAD is not the requested tested checkpoint")
    selected = selected_runtime_files(package)
    manifest = read_json(package / "runtime-manifest.json")
    windows = read_json(package / "runtime-windows-manifest.json")
    hd = read_json(package / "data/hd/hd.json")
    hd_count = sum(len(sequence["frames"]) for sequence in hd["sequences"])
    if hd_count != manifest["approved_hd_frames"] or windows["approved_hd_frames"] != hd_count:
        raise ValueError("shared data and platform HD counts differ")
    if digest(package / "bin/raptor-rust") != manifest["binary_sha256"]:
        raise ValueError("included Linux executable differs from its runtime manifest")
    for name, expected in windows["files"].items():
        if digest(checked_file(package, name)) != expected:
            raise ValueError(f"included Windows payload differs: {name}")
    rows = [entry(package, name, expected) for name, expected in sorted(manifest["files"].items())]
    if any(not row["name"].startswith("data/") for row in rows):
        raise ValueError("shared runtime manifest must contain data/ paths only")
    if len(rows) != manifest["data_files"] or sum(row["bytes"] for row in rows) != manifest["data_bytes"]:
        raise ValueError("shared runtime file count/bytes differ from its manifest")
    for sequence in hd["sequences"]:
        for frame in sequence["frames"]:
            checked_file(package / "data/hd", frame["file"])
            if "data/hd/" + frame["file"] not in manifest["files"]:
                raise ValueError("active HD artwork is absent from the shared runtime manifest")
    physical_data = {path.relative_to(package).as_posix() for path in selected
                     if path.relative_to(package).parts[0] == "data"}
    if physical_data != set(manifest["files"]):
        raise ValueError("runtime manifest does not cover the complete physical data tree")
    groups = partition(rows, budget)
    assets = [{"name": f"RustRaptor-data-{index:02d}-of-{len(groups):02d}.zip",
               "kind": "shared-data", "files": group,
               "uncompressed_bytes": sum(row["bytes"] for row in group)}
              for index, group in enumerate(groups, 1)]
    core = [entry(package, path.relative_to(package).as_posix()) for path in selected
            if path.relative_to(package).parts[0] != "data"]
    for platform in ("linux", "windows"):
        if platform == "linux":
            excluded = {"bin/raptor-rust.exe", "bin/SDL2.dll", "bin/SDL2-WINDOWS-LICENSE.txt",
                        "run.cmd", "runtime-windows-manifest.json"}
            files = [row for row in core if row["name"] not in excluded]
        else:
            files = [row for row in core if row["name"] not in {"bin/raptor-rust", "run.sh"}
                     and not row["name"].startswith("lib/")]
        if sum(row["bytes"] for row in files) > DEFAULT_VOLUME_BYTES:
            raise ValueError("platform core exceeds the safe single-asset budget")
        assets.append({"name": f"RustRaptor-{platform}-x86_64.zip", "kind": platform,
                       "files": files, "uncompressed_bytes": sum(row["bytes"] for row in files)})
    plan = {"format_version": 1, "package": str(package), "snapshot": snapshot,
            "catalog_entries": manifest["catalog_entries"], "approved_hd_frames": hd_count,
            "bundled_mods": len(list((package / "mods").glob("*/mod.toml"))),
            "data_files": len(rows), "data_bytes": manifest["data_bytes"],
            "volume_uncompressed_budget": budget, "assets": assets,
            "install": "Extract your platform ZIP and every shared-data ZIP into the same directory; run RustRaptor/run.sh or RustRaptor/run.cmd.",
            "payload_scope": "Complete unchanged runtime-manifest data plus explicitly inventoried mods, source, docs and platform libraries. No proof/lineage files from the manifest are silently removed."}
    for platform in ("linux", "windows"):
        installation = [row["name"].casefold() for asset in assets
                        if asset["kind"] in ("shared-data", platform) for row in asset["files"]]
        if len(installation) != len(set(installation)):
            raise ValueError("case-insensitive duplicate installation path across assets")
    for asset in assets:
        seen = set()
        for row in asset["files"]:
            key = row["name"].casefold()
            if key in seen:
                raise ValueError("case-insensitive duplicate release path")
            seen.add(key)
    check_snapshot(package, plan)
    return plan


def source_identity(metadata):
    return metadata.st_dev, metadata.st_ino, metadata.st_size, metadata.st_mtime_ns


@contextmanager
def opened_source(package, name, expected_size):
    relative = Path(name)
    if relative.is_absolute() or not relative.parts or any(part in (".", "..") for part in relative.parts):
        raise ValueError("unsafe release member path")
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK
    directory = os.open("/", flags | os.O_DIRECTORY)
    source = None
    try:
        for part in package.parts[1:] + relative.parts[:-1]:
            following = os.open(part, flags | os.O_DIRECTORY, dir_fd=directory)
            os.close(directory)
            directory = following
        source = os.open(relative.name, flags, dir_fd=directory)
        before = os.fstat(source)
        if not stat.S_ISREG(before.st_mode) or before.st_size != expected_size:
            raise ValueError("release source is not the planned regular file")
        with os.fdopen(source, "rb", closefd=False) as stream:
            yield stream, before
        if source_identity(before) != source_identity(os.fstat(source)):
            raise ValueError("release source changed while being read")
    finally:
        if source is not None:
            os.close(source)
        os.close(directory)


def write_asset(plan_path, asset_name, output):
    plan_path, output = Path(plan_path), Path(output)
    plan = read_json(plan_path)
    package = Path(plan["package"]).resolve(strict=True)
    check_snapshot(package, plan)
    matches = [asset for asset in plan["assets"] if asset["name"] == asset_name]
    if len(matches) != 1 or Path(asset_name).name != asset_name:
        raise ValueError("choose one exact planned release asset")
    asset = matches[0]
    if output.name != asset_name:
        raise ValueError("output filename must equal the planned asset name")
    if output.exists():
        raise ValueError("archive output already exists; never overwrite exports")
    output.parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(package).free < ROOT_DISK_FLOOR:
        raise ValueError("workspace free space is below the 1.8GB floor")
    # Deflate worst-case and ZIP overhead fit this generous reserve. /tmp may
    # be tmpfs: only one volume is held and no complete runtime tree is copied.
    if shutil.disk_usage(output.parent).free < asset["uncompressed_bytes"] + 128 * 1024**2:
        raise ValueError("insufficient output space for one archive and reserve")
    if (output.parent.stat().st_dev == package.stat().st_dev
            and shutil.disk_usage(package).free < ROOT_DISK_FLOOR + asset["uncompressed_bytes"] + 128 * 1024**2):
        raise ValueError("same-filesystem output would cross the workspace 1.8GB floor")
    measured = {}
    with zipfile.ZipFile(output, "x", zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
        for row in asset["files"]:
            h = hashlib.sha256()
            with opened_source(package, row["name"], row["bytes"]) as (original, before):
                info = zipfile.ZipInfo("RustRaptor/" + row["name"], time.localtime(before.st_mtime)[:6])
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 3
                info.external_attr = (before.st_mode & 0xFFFF) << 16
                with archive.open(info, "w", force_zip64=True) as member:
                    remaining = row["bytes"]
                    while remaining:
                        block = original.read(min(128 * 1024, remaining))
                        if not block:
                            raise ValueError("release source ended before its planned size")
                        remaining -= len(block)
                        h.update(block)
                        member.write(block)
                    if original.read(1):
                        raise ValueError("release source grew beyond its planned size")
            if h.hexdigest() != row["sha256"]:
                raise ValueError(f"release source changed or differs from plan: {row['name']}")
            measured[row["name"]] = h.hexdigest()
    if output.stat().st_size >= MAX_ASSET_BYTES:
        raise ValueError("release asset reaches GitHub's 2GiB limit")
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise ValueError("release ZIP failed CRC validation")
        if archive.namelist() != ["RustRaptor/" + row["name"] for row in asset["files"]]:
            raise ValueError("release ZIP membership differs from plan")
    check_snapshot(package, plan)
    return {"status": "ZIP_CRC_AND_COMPLETE_PAYLOAD_SHA256_PASS", "asset": asset_name,
            "kind": asset["kind"], "bytes": output.stat().st_size, "sha256": digest(output),
            "plan_sha256": digest(plan_path), "checkpoint": plan["snapshot"],
            "payload_files": len(measured), "payload_sha256": measured,
            "root_disk_floor_after_bytes": shutil.disk_usage(package).free,
            "builds_or_source_manifest_mutations": 0}


def checksums(plan_path, receipts, output, manifest_output=None, tag=None):
    plan_path, receipts, output = Path(plan_path), Path(receipts), Path(output)
    plan = read_json(plan_path)
    if manifest_output is not None and (not isinstance(tag, str) or not re.fullmatch(r"v[0-9A-Za-z._-]+", tag)):
        raise ValueError("a safe exact release tag is required")
    lines, published = [], []
    for asset in plan["assets"]:
        receipt = read_json(receipts / (asset["name"] + ".json"))
        if (receipt.get("status") != "ZIP_CRC_AND_COMPLETE_PAYLOAD_SHA256_PASS"
                or receipt.get("asset") != asset["name"]
                or receipt.get("kind") != asset["kind"]
                or receipt.get("checkpoint") != plan["snapshot"]
                or receipt.get("payload_files") != len(asset["files"])
                or receipt.get("plan_sha256") != digest(plan_path)
                or receipt.get("payload_sha256") != {row["name"]: row["sha256"] for row in asset["files"]}
                or not re.fullmatch(r"[0-9a-f]{64}", receipt.get("sha256", ""))
                or not 0 < receipt.get("bytes", 0) < MAX_ASSET_BYTES):
            raise ValueError("incomplete or mismatched release asset receipt")
        lines.append(f"{receipt['sha256']}  {asset['name']}\n")
        published.append({"name": asset["name"], "kind": asset["kind"], "bytes": receipt["bytes"],
                          "sha256": receipt["sha256"], "files": asset["files"]})
    with output.open("x", encoding="ascii") as stream:
        stream.writelines(lines)
    if manifest_output is not None:
        write_new_json(manifest_output, {"format_version": 1, "tag": tag, "checkpoint": plan["snapshot"],
            "approved_hd_frames": plan["approved_hd_frames"], "data_files": plan["data_files"],
            "data_bytes": plan["data_bytes"], "bundled_mods": plan["bundled_mods"], "assets": published})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    planning = commands.add_parser("plan")
    planning.add_argument("--package", type=Path, required=True)
    planning.add_argument("--expected-commit", required=True)
    planning.add_argument("--output", type=Path, required=True)
    exporting = commands.add_parser("archive")
    exporting.add_argument("--plan", type=Path, required=True)
    exporting.add_argument("--asset", required=True)
    exporting.add_argument("--output", type=Path, required=True)
    exporting.add_argument("--receipt", type=Path, required=True)
    summing = commands.add_parser("checksums")
    summing.add_argument("--plan", type=Path, required=True)
    summing.add_argument("--receipts", type=Path, required=True)
    summing.add_argument("--output", type=Path, required=True)
    summing.add_argument("--manifest-output", type=Path, required=True)
    summing.add_argument("--tag", required=True)
    args = parser.parse_args()
    if args.command == "plan":
        value = build_plan(args.package, args.expected_commit)
        write_new_json(args.output, value)
        print(json.dumps({key: value[key] for key in ("snapshot", "approved_hd_frames", "bundled_mods", "data_files", "data_bytes")}))
    elif args.command == "archive":
        value = write_asset(args.plan, args.asset, args.output)
        write_new_json(args.receipt, value)
        print(json.dumps({key: value[key] for key in ("status", "asset", "bytes", "sha256", "payload_files")}))
    else:
        checksums(args.plan, args.receipts, args.output, args.manifest_output, args.tag)


if __name__ == "__main__":
    main()
