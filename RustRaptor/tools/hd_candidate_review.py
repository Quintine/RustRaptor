#!/usr/bin/env python3
"""Review a proposed HD family with the exact already-built Rust loader.

Creates an isolated temporary pack with hard-linked raw artwork. It never edits
the active manifest or generated pixels. Build the game library before use.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

FRAME_KEYS = {"frame", "file", "logical_width", "logical_height", "origin", "source_sha256", "crop"}


def proposal_frames(proposal, expected=None):
    """Check source-bound target membership; artistic approval remains separate."""
    rows = {}
    for sequence in proposal.get("sequences", []):
        base = sequence["base_asset"]
        if isinstance(base, str):
            base = int(base, 16)
        if not 1 <= sequence["frame_count"] <= 512:
            raise ValueError("invalid sequence frame count")
        for frame in sequence["frames"]:
            if set(frame) - FRAME_KEYS:
                raise ValueError("unknown manifest frame fields")
            if not 0 <= frame["frame"] < sequence["frame_count"]:
                raise ValueError("frame outside sequence")
            identity = f"{base + frame['frame']:05x}"
            if identity in rows:
                raise ValueError("duplicate candidate ID")
            rows[identity] = frame
    if not rows:
        raise ValueError("candidate needs manifest-compatible sequences")
    supplied = {str(row["asset"]).lower().removeprefix("0x").zfill(5): row for row in proposal.get("targets", [])}
    if supplied and set(supplied) != set(rows):
        raise ValueError("candidate targets and sequences differ")
    for identity, frame in rows.items():
        if supplied and any(supplied[identity].get(key) != value for key, value in frame.items()):
            raise ValueError(f"target and sequence metadata differ for {identity}")
        if expected is not None:
            if identity not in expected:
                raise ValueError(f"candidate claims foreign ID {identity}")
            source = expected[identity]
            if frame["source_sha256"] != source["source_sha256"]:
                raise ValueError(f"candidate source changed for {identity}")
            if [frame["logical_width"], frame["logical_height"]] != source["logical_canvas"]:
                raise ValueError(f"candidate logical canvas changed for {identity}")
        if frame["origin"] != [0, 0]:
            raise ValueError(f"candidate anchor changed for {identity}")
        relative = Path(frame["file"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("artwork must remain pack-relative")
    if expected is not None and proposal.get("complete_family") and set(rows) != set(expected):
        raise ValueError("complete-family claim omits source IDs")
    return rows


def main():
    project = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--data", type=Path, default=project.parent / "data")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--profile", choices=["auto", "debug", "release"], default="auto")
    parser.add_argument("--sheet-rows", type=int, default=16, help="Maximum frames per contact-sheet page; review every page")
    args = parser.parse_args()
    if not 1 <= args.sheet_rows <= 64:
        parser.error("sheet-rows must be 1..64")
    proposal = json.loads(args.candidate.read_text())
    job_path = args.candidate.parent / "job.json"
    expected = None
    if job_path.is_file():
        job = json.loads(job_path.read_text())
        if proposal.get("job_id") != job["job_id"]:
            raise ValueError("candidate job identity differs")
        expected = {target["asset"]: target for target in job["targets"]}
    rows = proposal_frames(proposal, expected)
    manifest = {"format_version": 1, "name": "Isolated candidate review", "description": "Unregistered diagnostic pack", "sequences": proposal["sequences"]}
    profiles = ["debug", "release"] if args.profile == "auto" else [args.profile]
    libraries = [library for profile in profiles for library in (project / "target" / profile / "deps").glob("libraptor_replica-*.rlib")]
    if not libraries:
        raise ValueError("build the Rust game library before candidate review")
    library = max(libraries, key=lambda path: path.stat().st_mtime_ns)
    dependency_directory = library.parent
    serde = max(dependency_directory.glob("libserde_json-*.rlib"), key=lambda path: path.stat().st_mtime_ns)
    output = (args.output or args.candidate.parent / "runtime-review").resolve()
    output.mkdir(parents=True, exist_ok=True)
    pack_root = (args.data / "hd").resolve()
    artwork_hashes = {}
    with tempfile.TemporaryDirectory(prefix="isolated-pack-", dir=output) as temporary:
        isolated = Path(temporary)
        for frame in rows.values():
            source = (pack_root / frame["file"]).resolve()
            if not source.is_relative_to(pack_root):
                raise ValueError("artwork escapes real pack root")
            artwork_hashes[frame["file"]] = hashlib.sha256(source.read_bytes()).hexdigest()
            destination = isolated / frame["file"]
            if destination.exists():
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.link(source, destination)
            except OSError:
                shutil.copyfile(source, destination)
        (isolated / "hd.json").write_text(json.dumps(manifest))
        binary = isolated / "review-bin"
        subprocess.run(["rustc", "--edition=2021", str(project / "tools/hd_candidate_review.rs"), "--extern", f"raptor_replica={library}", "--extern", f"serde_json={serde}", "-L", f"dependency={dependency_directory}", "-L", "native=" + str(Path.home() / ".local/lib"), "-o", str(binary)], check=True)
        environment = os.environ.copy()
        environment["LD_LIBRARY_PATH"] = str(Path.home() / ".local/lib") + os.pathsep + environment.get("LD_LIBRARY_PATH", "")
        subprocess.run([str(binary), str(args.data.resolve()), str(isolated), str(output)], check=True, env=environment)
        for relative, digest in artwork_hashes.items():
            if hashlib.sha256((pack_root / relative).read_bytes()).hexdigest() != digest:
                raise ValueError("artwork changed during runtime review")
    qa_path = output / "runtime-qa.json"
    qa = json.loads(qa_path.read_text())
    qa["library"] = str(library.relative_to(project))
    qa["library_modified_ns"] = library.stat().st_mtime_ns
    qa["candidate_sha256"] = hashlib.sha256(args.candidate.read_bytes()).hexdigest()
    qa["artwork_sha256"] = artwork_hashes
    qa["source_newer_than_library"] = any((project / "src" / name).stat().st_mtime_ns > library.stat().st_mtime_ns for name in ["assets.rs", "hd.rs"])
    qa["any_game_source_newer_than_library"] = any(path.stat().st_mtime_ns > library.stat().st_mtime_ns for path in (project / "src").glob("*.rs"))
    qa_path.write_text(json.dumps(qa, indent=2) + "\n")
    identities = sorted(rows)
    pages = []
    # These are tool-produced diagnostics, never input art. Remove stale pages
    # so a former shorter proposal cannot be mistaken for this complete review.
    for obsolete in output.glob("runtime-contact-sheet*.png"):
        obsolete.unlink()
    for start in range(0, len(identities), args.sheet_rows):
        page = identities[start:start + args.sheet_rows]
        cell_width = max(rows[identity]["logical_width"] for identity in page) * 4 + 24
        row_height = max(rows[identity]["logical_height"] for identity in page) * 4 + 42
        sheet = Image.new("RGB", (cell_width * 3, row_height * len(page)), (20, 28, 38))
        draw = ImageDraw.Draw(sheet)
        for row, identity in enumerate(page):
            for column, (suffix, label) in enumerate([("original", "Original"), ("hd-1", "Rust 1x"), ("hd-4", "Rust 4x")]):
                with Image.open(output / f"{identity}-{suffix}.ppm") as source:
                    sprite = source.convert("RGB")
                if suffix != "hd-4":
                    sprite = sprite.resize((sprite.width * 4, sprite.height * 4), Image.Resampling.NEAREST)
                x, y = column * cell_width + 12, row * row_height + 36
                draw.text((x, row * row_height + 4), identity, fill=(225, 225, 230))
                draw.text((x, row * row_height + 16), label, fill=(225, 225, 230))
                sheet.paste(sprite, (x, y))
        name = "runtime-contact-sheet.png" if len(identities) <= args.sheet_rows else f"runtime-contact-sheet-{len(pages) + 1:03}.png"
        sheet.save(output / name)
        pages.append({"file": name, "assets": page})
    (output / "runtime-contact-sheets.json").write_text(json.dumps({"review_every_page": True, "pages": pages}, indent=2) + "\n")
    print(json.dumps({"output": str(output), "frames": len(rows), "sheet_pages": len(pages), "stale_library": qa["source_newer_than_library"]}))


if __name__ == "__main__":
    main()
