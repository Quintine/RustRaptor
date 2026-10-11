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


def binding_digest(rows):
    """Hash only renderer-bound fields, separately from artist review notes."""
    return hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def freeze_library(project, library):
    """Keep exact tested bytes and the original build time across Cargo rebuilds."""
    before = library.stat()
    payload = library.read_bytes()
    after = library.stat()
    identity = lambda value: (value.st_ino, value.st_size, value.st_mtime_ns)
    if identity(before) != identity(after):
        raise ValueError("Rust library changed while taking review snapshot; retry")
    digest = hashlib.sha256(payload).hexdigest()
    directory = project / "target/hd-review-libraries" / digest
    directory.mkdir(parents=True, exist_ok=True)
    frozen = directory / library.name
    if frozen.exists():
        if hashlib.sha256(frozen.read_bytes()).hexdigest() != digest:
            raise ValueError("review library snapshot is corrupt")
        if frozen.stat().st_mtime_ns != before.st_mtime_ns:
            # Identical bytes rebuilt later must not make an old snapshot look
            # fresh. Separate build times retain an honest source-age check.
            frozen = directory / (library.stem + "-build-" + str(before.st_mtime_ns) + library.suffix)
    if not frozen.exists():
        descriptor, temporary = tempfile.mkstemp(prefix="library-", dir=directory)
        try:
            with os.fdopen(descriptor, "wb") as output:
                output.write(payload)
                output.flush()
                os.fsync(output.fileno())
            os.utime(temporary, ns=(before.st_atime_ns, before.st_mtime_ns))
            os.chmod(temporary, 0o444)
            try:
                # Publish without replacing an identical snapshot another
                # reviewer may already be using. Concurrent first readers
                # must retain one stable inode as well as identical bytes.
                os.link(temporary, frozen)
            except FileExistsError:
                pass
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    if hashlib.sha256(frozen.read_bytes()).hexdigest() != digest or frozen.stat().st_mtime_ns != before.st_mtime_ns:
        raise ValueError("review library snapshot identity differs")
    return frozen, digest, before


def select_compatible_serde_json(project, library, dependency_directory, output, candidates=None):
    """Compile-check serde's trait identity against the exact frozen game library.

    Cargo can leave several feature graphs in one deps directory. A newer
    serde_json may use a different serde_core instance from Manifest, so its
    build time cannot establish compatibility.
    """
    candidates = sorted(candidates if candidates is not None else
                        dependency_directory.glob("libserde_json-*.rlib"))
    if not candidates:
        raise ValueError("build serde_json before candidate review")
    output.mkdir(parents=True, exist_ok=True)
    report = {
        "method": "rustc metadata compile of Manifest Deserialize and Serialize against exact frozen libraries",
        "raptor_library_sha256": hashlib.sha256(library.read_bytes()).hexdigest(),
        "attempts": [],
    }
    evidence = output / "dependency-selection.json"
    with tempfile.TemporaryDirectory(prefix="serde-compatibility-", dir=output) as temporary:
        directory = Path(temporary)
        source = directory / "probe.rs"
        source.write_text("""fn main() {
    let manifest: raptor_replica::hd::Manifest = serde_json::from_slice(b"{}").unwrap();
    let _ = serde_json::to_vec(&manifest).unwrap();
}
""")
        for candidate in candidates:
            frozen, digest, original = freeze_library(project, candidate)
            result = subprocess.run([
                "rustc", "--edition=2021", "--emit=metadata", str(source),
                "--extern", f"raptor_replica={library}",
                "--extern", f"serde_json={frozen}",
                "-L", f"dependency={dependency_directory}",
                "-o", str(directory / "probe.rmeta"),
            ], capture_output=True, text=True)
            report["attempts"].append({
                "build_origin": str(candidate.relative_to(project)),
                "library": str(frozen.relative_to(project)),
                "sha256": digest,
                "build_origin_modified_ns": original.st_mtime_ns,
                "compatible": result.returncode == 0,
                "compiler_stderr": result.stderr,
            })
            if result.returncode == 0:
                report["selected"] = report["attempts"][-1]
                evidence.write_text(json.dumps(report, indent=2) + "\n")
                return frozen, report
    evidence.write_text(json.dumps(report, indent=2) + "\n")
    raise ValueError(f"no compiler-compatible serde_json for the selected Rust library; see {evidence}")


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
    candidate_at_start = args.candidate.read_bytes()
    proposal = json.loads(candidate_at_start)
    job_path = args.candidate.parent / "job.json"
    expected = None
    if job_path.is_file():
        job = json.loads(job_path.read_text())
        if proposal.get("job_id") != job["job_id"]:
            raise ValueError("candidate job identity differs")
        expected = {target["asset"]: target for target in job["targets"]}
    rows = proposal_frames(proposal, expected)
    bindings_at_start = binding_digest(rows)
    static_cards = any(int(identity, 16) in [0x1002b, 0x1002d, 0x1002f] for identity in rows)
    manifest = {"format_version": 1, "name": "Isolated candidate review", "description": "Unregistered diagnostic pack", "sequences": proposal["sequences"]}
    profiles = ["debug", "release"] if args.profile == "auto" else [args.profile]
    libraries = [library for profile in profiles for library in (project / "target" / profile / "deps").glob("libraptor_replica-*.rlib")]
    if not libraries:
        raise ValueError("build the Rust game library before candidate review")
    built_library = max(libraries, key=lambda path: path.stat().st_mtime_ns)
    dependency_directory = built_library.parent
    library, library_sha256, built_library_at_start = freeze_library(project, built_library)
    library_at_start = library.stat()
    output = (args.output or args.candidate.parent / "runtime-review").resolve()
    output.mkdir(parents=True, exist_ok=True)
    serde, serde_selection = select_compatible_serde_json(project, library, dependency_directory, output)
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
        compiler_args = ["rustc", "--edition=2021", str(project / "tools/hd_candidate_review.rs"), "--extern", f"raptor_replica={library}", "--extern", f"serde_json={serde}", "-L", f"dependency={dependency_directory}", "-L", "native=" + str(Path.home() / ".local/lib"), "-o", str(binary)]
        if static_cards:
            compiler_args.extend(["--cfg", "static_card_api"])
        subprocess.run(compiler_args, check=True)
        environment = os.environ.copy()
        environment["LD_LIBRARY_PATH"] = str(Path.home() / ".local/lib") + os.pathsep + environment.get("LD_LIBRARY_PATH", "")
        subprocess.run([str(binary), str(args.data.resolve()), str(isolated), str(output)], check=True, env=environment)
        for relative, digest in artwork_hashes.items():
            if hashlib.sha256((pack_root / relative).read_bytes()).hexdigest() != digest:
                raise ValueError("artwork changed during runtime review")
    library_at_finish = library.stat()
    if (library_at_start.st_ino, library_at_start.st_size, library_at_start.st_mtime_ns) != (library_at_finish.st_ino, library_at_finish.st_size, library_at_finish.st_mtime_ns):
        raise ValueError("Rust library changed during runtime review; rebuild and rerun")
    qa_path = output / "runtime-qa.json"
    qa = json.loads(qa_path.read_text())
    candidate_at_finish = args.candidate.read_bytes()
    if binding_digest(proposal_frames(json.loads(candidate_at_finish), expected)) != bindings_at_start:
        raise ValueError("candidate renderer bindings changed during runtime review")
    qa["library"] = str(library.relative_to(project))
    qa["library_modified_ns"] = library_at_start.st_mtime_ns
    qa["library_sha256"] = library_sha256
    qa["library_build_origin"] = str(built_library.relative_to(project))
    qa["library_build_origin_modified_ns"] = built_library_at_start.st_mtime_ns
    qa["serde_json_dependency"] = serde_selection
    qa["candidate_sha256"] = hashlib.sha256(candidate_at_finish).hexdigest()
    qa["candidate_sha256_at_start"] = hashlib.sha256(candidate_at_start).hexdigest()
    qa["candidate_notes_changed_during_review"] = candidate_at_start != candidate_at_finish
    qa["frame_bindings_sha256"] = bindings_at_start
    qa["artwork_sha256"] = artwork_hashes
    qa["static_card_palette_mode"] = static_cards
    qa["source_newer_than_library"] = any((project / "src" / name).stat().st_mtime_ns > library_at_start.st_mtime_ns for name in ["assets.rs", "hd.rs"])
    qa["any_game_source_newer_than_library"] = any(path.stat().st_mtime_ns > library_at_start.st_mtime_ns for path in (project / "src").glob("*.rs"))
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
