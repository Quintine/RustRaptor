#!/usr/bin/env python3
"""Register explicitly approved, source-bound complete HD families.

Generation and a successful loader probe never approve artwork. Each job must
already have a coordinator-review.json approval bound to its exact frame map,
plus complete current all-scale evidence. Raw images are read, never changed.
"""
import argparse
import datetime
import hashlib
import json
import os
import tempfile
from pathlib import Path

from hd_candidate_review import binding_digest, proposal_frames


def contained(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"path escapes HD root: {relative}")
    return path


def approved_job(root, identity, project):
    directory = contained(root, Path("jobs") / identity)
    if directory.parent != (root / "jobs").resolve():
        raise ValueError("job must be one direct directory in jobs/")
    candidate_path = directory / "candidate.json"
    candidate = json.loads(candidate_path.read_text())
    job = json.loads((directory / "job.json").read_text())
    if job["job_id"] != identity or candidate.get("job_id") != identity:
        raise ValueError(f"job identity differs: {identity}")
    expected = {target["asset"]: target for target in job["targets"]}
    rows = proposal_frames(candidate, expected)
    if not candidate.get("complete_family") or set(rows) != set(expected):
        raise ValueError(f"incomplete family: {identity}")
    if any({frame["frame"] for frame in sequence["frames"]} != set(range(sequence["frame_count"])) for sequence in candidate["sequences"]):
        raise ValueError(f"complete-family claim contains a partial sequence: {identity}")
    review = json.loads((directory / "coordinator-review.json").read_text())
    if review.get("status") != "approved":
        raise ValueError(f"no artistic approval: {identity}")
    digest = binding_digest(rows)
    if review.get("frame_bindings_sha256") != digest:
        raise ValueError(f"artistic approval belongs to another frame map: {identity}")
    if not review.get("source_and_all_scale_visual_review") or not review.get("independent_review"):
        raise ValueError(f"missing complete visual/independent review: {identity}")
    qa_path = contained(root, review["runtime_qa"])
    qa = json.loads(qa_path.read_text())
    if qa.get("frame_bindings_sha256") != digest or qa.get("diagnostics"):
        raise ValueError(f"runtime evidence differs or reports errors: {identity}")
    if qa.get("source_newer_than_library"):
        raise ValueError(f"runtime evidence used stale asset/HD code: {identity}")
    library = (project / qa["library"]).resolve()
    if not library.is_relative_to(project / "target") or library.stat().st_mtime_ns != qa["library_modified_ns"]:
        raise ValueError(f"runtime library was replaced after review: {identity}")
    for name in ["assets.rs", "hd.rs"]:
        if (project / "src" / name).stat().st_mtime_ns > qa["library_modified_ns"]:
            raise ValueError(f"asset/HD code changed after review: {identity}")
    reports = {frame["asset"]: frame for frame in qa["frames"]}
    if set(reports) != set(rows):
        raise ValueError(f"runtime evidence omits family IDs: {identity}")
    for asset, frame in rows.items():
        report = reports[asset]
        if report["source_sha256"] != frame["source_sha256"] or report["logical_canvas"] != [frame["logical_width"], frame["logical_height"]]:
            raise ValueError(f"runtime source/canvas differs: {asset}")
        if {mask["scale"] for mask in report["hd_masks"]} != {1, 2, 3, 4}:
            raise ValueError(f"missing presentation scale: {asset}")
        source_reserved = report["source_mask"]["palette_indices_240_to_255_counts"]
        if not qa.get("static_card_palette_mode") and not any(source_reserved):
            if any(any(mask["mask"]["palette_indices_240_to_255_counts"]) for mask in report["hd_masks"]):
                raise ValueError(f"ordinary source gained animated palette labels: {asset}")
        artwork = contained(root, frame["file"])
        if hashlib.sha256(artwork.read_bytes()).hexdigest() != qa["artwork_sha256"][frame["file"]]:
            raise ValueError(f"raw artwork changed since review: {asset}")
    return candidate, review, rows


def atomic_json(path, value):
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as output:
            json.dump(value, output, indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    project = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hd-root", type=Path, default=project.parent / "data/hd")
    parser.add_argument("--job", action="append", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    root = args.hd_root.resolve()
    manifest_path = root / "hd.json"
    provenance_path = root / "provenance.json"
    original_manifest = manifest_path.read_bytes()
    original_provenance = provenance_path.read_bytes()
    manifest = json.loads(original_manifest)
    provenance = json.loads(original_provenance)
    active = proposal_frames(manifest)
    additions = []
    for identity in args.job:
        candidate, review, rows = approved_job(root, identity, project)
        overlaps = set(rows) & set(active)
        if overlaps:
            if overlaps == set(rows) and all(rows[asset] == active[asset] for asset in rows):
                continue
            raise ValueError(f"duplicate registered ID; review a replacement explicitly: {sorted(overlaps)}")
        manifest["sequences"].extend(candidate["sequences"])
        active.update(rows)
        detail = f"jobs/{identity}/provenance.json"
        if not contained(root, detail).is_file():
            # Some artists keep generation provenance in their review or
            # family folder. Do not invent a nonexistent evidence reference.
            detail = f"jobs/{identity}/candidate.json"
        additions.append({
            "job_id": identity,
            "assets": sorted(rows),
            "frames": len(rows),
            "metadata": "hd.json",
            "detail": detail,
            "coordinator_review": f"jobs/{identity}/coordinator-review.json",
            "runtime_qa": review["runtime_qa"],
            "review": review["source_and_all_scale_visual_review"],
            "independent_review": review["independent_review"],
            "frame_bindings_sha256": review["frame_bindings_sha256"],
        })
    if additions and not args.dry_run:
        # Do not overwrite another registration completed during validation.
        if manifest_path.read_bytes() != original_manifest or provenance_path.read_bytes() != original_provenance:
            raise ValueError("active pack changed during validation; retry from the new snapshot")
        provenance.setdefault("reviewed_sequence_additions", []).extend(additions)
        provenance["registered_frame_count"] = len(active)
        provenance["status"] = f"{len(active)} complete-family reviewed original picture frames registered. Whole-catalog queues remain active; HD stays optional. Render reachability is recorded separately."
        provenance["registration_updated_at_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        # Runtime uses hd.json alone. Write its ancillary evidence first, then
        # replace the complete manifest in one atomic rename.
        atomic_json(provenance_path, provenance)
        atomic_json(manifest_path, manifest)
    print(json.dumps({"dry_run": args.dry_run, "jobs_added": [row["job_id"] for row in additions], "frames_added": sum(row["frames"] for row in additions), "registered_frames": len(active)}))


if __name__ == "__main__":
    main()
