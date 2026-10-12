#!/usr/bin/env python3
"""Register approved complete HD families or explicit standalone Terrain selections.

Generation and a successful loader probe never approve artwork. Each job must
already have a coordinator-review.json approval bound to its exact frame map,
plus complete current all-scale evidence. Raw images are read, never changed.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

from hd_candidate_review import binding_digest, proposal_frames
from hd_art_audit import checked_palette, validate_hd_frame
from hd_art_source import decode


def asset_list(value, label):
    if not isinstance(value, list) or any(not isinstance(asset, str) or
            re.fullmatch(r"[0-9a-f]{5}", asset) is None for asset in value):
        raise ValueError(f"{label} needs canonical catalog IDs")
    if len(value) != len(set(value)):
        raise ValueError(f"duplicate {label}")
    return set(value)


def standalone_selection(candidate, job, rows):
    """Standalone means a complete one-frame definition, never an animation slice."""
    if candidate.get("complete_standalone_selection") is not True:
        return None
    if candidate.get("complete_family") is not False:
        raise ValueError("standalone selection must not claim whole-family approval")
    for value in [candidate, job]:
        if value.get("category") != "Terrain" or value.get("kind") != "contextual_terrain_shard":
            raise ValueError("standalone selection is restricted to contextual Terrain")
    targets = [target["asset"] for target in job["targets"]]
    inventory = asset_list(targets, "job inventory")
    full = asset_list(candidate.get("full_inventory"), "full_inventory")
    selected = asset_list(candidate.get("selected_assets"), "selected_assets")
    fallback = asset_list(candidate.get("original_fallback_assets"), "original_fallback_assets")
    if full != inventory or selected != set(rows) or not selected or selected & fallback or selected | fallback != full:
        raise ValueError("standalone selected/fallback partition differs from complete job inventory")
    if candidate.get("targets"):
        asset_list([target["asset"] for target in candidate["targets"]], "candidate targets")
    inventory_job = candidate.get("inventory_job_id", job["job_id"])
    span = re.fullmatch(r"terrain-([0-9a-f]{5})-([0-9a-f]{5})", inventory_job)
    if span is None or full != {f"{asset:05x}" for asset in range(int(span[1], 16), int(span[2], 16) + 1)}:
        raise ValueError("standalone full inventory differs from original Terrain shard range")
    for sequence in candidate["sequences"]:
        if (type(sequence["frame_count"]) is not int or sequence["frame_count"] != 1 or
                len(sequence["frames"]) != 1 or type(sequence["frames"][0]["frame"]) is not int or
                sequence["frames"][0]["frame"] != 0):
            raise ValueError("standalone selection contains an animation or partial sequence")
    return {key: sorted(value) for key, value in [
        ("full_inventory", full), ("selected_assets", selected), ("original_fallback_assets", fallback)]}


def receipt_json(root, receipt):
    if (not isinstance(receipt, dict) or not isinstance(receipt.get("path"), str) or
            re.fullmatch(r"[0-9a-f]{64}", str(receipt.get("sha256", ""))) is None):
        raise ValueError("missing hash-bound independent receipt")
    relative = Path(receipt["path"])
    path = relative if relative.is_absolute() else contained(root, relative)
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != receipt["sha256"]:
        raise ValueError("independent receipt changed")
    return json.loads(payload)


def authentic_terrain_inventory(root, job):
    """Corroborate the full shard against the real catalog, including fallbacks."""
    data = root.parent.resolve()
    entries, markers = {}, {}
    for line in (data / "INDEX").read_text().splitlines():
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) != 3 or re.fullmatch(r"[0-9a-fA-F]{1,8}", parts[0]) is None:
            raise ValueError("invalid original INDEX record")
        identity = int(parts[0], 16)
        if identity in entries or not parts[1].isdigit():
            raise ValueError("duplicate or invalid original INDEX record")
        relative = Path(parts[2])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("unsafe original INDEX path")
        path = (data / relative).resolve()
        if not path.is_relative_to(data):
            raise ValueError("original INDEX path escapes data")
        entries[identity] = (int(parts[1]), parts[2], path)
        name = relative.name
        if re.fullmatch(r"(?:START|END)G[1-4]TILES", name):
            if name in markers:
                raise ValueError("ambiguous original Terrain marker")
            markers[name] = identity
    ranges = [(markers[f"STARTG{n}TILES"], markers[f"ENDG{n}TILES"])
              for n in range(1, 5) if f"STARTG{n}TILES" in markers and f"ENDG{n}TILES" in markers]
    if not ranges or any(start >= end for start, end in ranges):
        raise ValueError("missing or invalid original Terrain ranges")
    palettes, pictures, payloads = {}, {}, {}
    for target in job["targets"]:
        asset = target["asset"]
        identity = int(asset, 16)
        if not any(start < identity < end for start, end in ranges) or identity not in entries:
            raise ValueError(f"original ID is not catalog Terrain: {asset}")
        size, relative, path = entries[identity]
        payload = path.read_bytes()
        if (relative != target["source_path"] or len(payload) != size or
                hashlib.sha256(payload).hexdigest() != target["source_sha256"]):
            raise ValueError(f"original inventory source differs: {asset}")
        if target.get("origin") != [0, 0] or target.get("source_palette") != "PALETTE_DAT":
            raise ValueError(f"original Terrain anchor/palette differs: {asset}")
        palette_path = (data / "misc/PALETTE_DAT").resolve()
        if not palette_path.is_relative_to(data):
            raise ValueError("original palette escapes data")
        palette = palette_path.read_bytes()
        if hashlib.sha256(palette).hexdigest() != target["source_palette_sha256"]:
            raise ValueError(f"original Terrain palette changed: {asset}")
        if palette not in palettes:
            palettes[palette] = checked_palette(palette)
        picture = decode(path, palettes[palette])
        if list(picture.size) != target["logical_canvas"]:
            raise ValueError(f"original inventory canvas differs: {asset}")
        pictures[asset], payloads[asset] = picture, payload
    return pictures, payloads


def approved_material_evidence(root, selection, review, rows, qa):
    evidence = review.get("standalone_selection", {})
    if any(evidence.get(key) != value for key, value in selection.items()):
        raise ValueError("review selected/fallback inventory differs")
    materials = evidence.get("material_approvals", {})
    if set(materials) != set(rows):
        raise ValueError("independent material map omits or adds selected IDs")
    for asset, frame in rows.items():
        approval = materials[asset]
        raw_sha = qa["artwork_sha256"][frame["file"]]
        if (approval.get("status") != "approved" or
                approval.get("frame_bindings_sha256") != binding_digest({asset: frame}) or
                approval.get("source_sha256") != frame["source_sha256"] or approval.get("raw_sha256") != raw_sha):
            raise ValueError(f"independent material binding differs: {asset}")
        peer = receipt_json(root, approval.get("independent_review"))
        reviewer = peer.get("reviewer", peer.get("owner"))
        if not isinstance(reviewer, str) or not peer.get("author") or reviewer == peer["author"]:
            raise ValueError(f"material review is not independent: {asset}")
        records, index = peer.get("records", []), approval.get("record_index")
        if type(index) is not int or not 0 <= index < len(records):
            raise ValueError(f"unsafe independent decision index: {asset}")
        record = records[index]
        if (record.get("asset") != asset or record.get("standalone_verdict") not in ["APPROVE", "QUALIFIED_APPROVE"] or
                record.get("selected_frame_binding") != frame or
                record.get("source_payload_sha256") != frame["source_sha256"] or
                record.get("full_untouched_raw_sha256") != raw_sha or record.get("actual_scales") != [1, 2, 3, 4]):
            raise ValueError(f"independent per-ID decision does not approve exact artwork: {asset}")


def approved_standalone_evidence(root, selection, review, rows, qa):
    approved_material_evidence(root, selection, review, rows, qa)
    evidence = review["standalone_selection"]
    context = evidence.get("contextual_approval", {})
    if (asset_list(context.get("selected_assets"), "context selected_assets") != set(rows) or
            context.get("selected_frame_bindings_sha256") != binding_digest(rows)):
        raise ValueError("combined context restriction differs from selected definitions")
    peer = receipt_json(root, context.get("receipt"))
    reviewer = peer.get("reviewer", peer.get("owner"))
    if not isinstance(reviewer, str) or not peer.get("author") or reviewer == peer["author"]:
        raise ValueError("combined contextual review is not independent")
    authority = peer.get("standalone_selection_context", {})
    proposal = receipt_json(root, authority.get("candidate"))
    bindings = proposal_frames(proposal)
    if (asset_list(authority.get("selected_assets"), "context complete selected_assets") != set(bindings) or
            authority.get("frame_bindings_sha256") != binding_digest(bindings) or not set(rows) <= set(bindings) or
            any(bindings[asset] != frame for asset, frame in rows.items()) or
            authority.get("technical_verdict") != "QUALIFIED_CONTEXT_INTEGRATION"):
        raise ValueError("combined contextual authority differs or is incomplete")
    if any(sequence["frame_count"] != 1 or len(sequence["frames"]) != 1 or sequence["frames"][0]["frame"] != 0
           for sequence in proposal["sequences"]):
        raise ValueError("combined context candidate includes animation slices")
    for key in ["baseline", "future_projection"]:
        receipt_json(root, authority.get(key))
    closure = receipt_json(root, authority.get("changed_case_closure"))
    if (closure.get("status") != "CLOSED_QUALIFIED_CONTEXT" or
            closure.get("candidate_sha256") != authority["candidate"]["sha256"] or
            closure.get("frame_bindings_sha256") != binding_digest(bindings) or
            closure.get("baseline_sha256") != authority["baseline"]["sha256"] or
            closure.get("future_projection_sha256") != authority["future_projection"]["sha256"]):
        raise ValueError("changed-case closure belongs to another candidate or projection")
    receipt_json(root, closure.get("changed_case_proof"))


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
    selection = standalone_selection(candidate, job, rows)
    if selection is None and (not candidate.get("complete_family") or set(rows) != set(expected)):
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
    if selection is not None:
        candidate_sha = hashlib.sha256(candidate_path.read_bytes()).hexdigest()
        if review.get("candidate_sha256") != candidate_sha or qa.get("candidate_sha256") != candidate_sha:
            raise ValueError("standalone approval belongs to another candidate")
        if (qa.get("source_newer_than_library") is not False or qa.get("any_game_source_newer_than_library") is not False or
                not qa.get("library_sha256")):
            raise ValueError("standalone runtime freshness/library identity is incomplete")
    library = (project / qa["library"]).resolve()
    if not library.is_relative_to(project / "target") or library.stat().st_mtime_ns != qa["library_modified_ns"]:
        raise ValueError(f"runtime library was replaced after review: {identity}")
    if qa.get("library_sha256") and hashlib.sha256(library.read_bytes()).hexdigest() != qa["library_sha256"]:
        raise ValueError(f"runtime library bytes changed after review: {identity}")
    for name in ["assets.rs", "hd.rs"]:
        if (project / "src" / name).stat().st_mtime_ns > qa["library_modified_ns"]:
            raise ValueError(f"asset/HD code changed after review: {identity}")
    if selection is not None and any(path.stat().st_mtime_ns > qa["library_modified_ns"]
                                     for path in (project / "src").rglob("*.rs")):
        raise ValueError("game source changed after standalone review")
    reports = {frame["asset"]: frame for frame in qa["frames"]}
    if selection is not None and len(reports) != len(qa["frames"]):
        raise ValueError("duplicate standalone runtime ID")
    if set(reports) != set(rows):
        raise ValueError(f"runtime evidence omits family IDs: {identity}")
    for asset, frame in rows.items():
        report = reports[asset]
        if report["source_sha256"] != frame["source_sha256"] or report["logical_canvas"] != [frame["logical_width"], frame["logical_height"]]:
            raise ValueError(f"runtime source/canvas differs: {asset}")
        if {mask["scale"] for mask in report["hd_masks"]} != {1, 2, 3, 4}:
            raise ValueError(f"missing presentation scale: {asset}")
        if selection is not None and (len(report["hd_masks"]) != 4 or any(type(mask["scale"]) is not int for mask in report["hd_masks"])):
            raise ValueError(f"duplicate or invalid presentation scale: {asset}")
        source_reserved = report["source_mask"]["palette_indices_240_to_255_counts"]
        if not qa.get("static_card_palette_mode") and not any(source_reserved):
            if any(any(mask["mask"]["palette_indices_240_to_255_counts"]) for mask in report["hd_masks"]):
                raise ValueError(f"ordinary source gained animated palette labels: {asset}")
        artwork = contained(root, frame["file"])
        if hashlib.sha256(artwork.read_bytes()).hexdigest() != qa["artwork_sha256"][frame["file"]]:
            raise ValueError(f"raw artwork changed since review: {asset}")
    if selection is not None:
        pictures, payloads = authentic_terrain_inventory(root, job)
        for asset, frame in rows.items():
            validate_hd_frame(root, frame, payloads[asset], pictures[asset])
        approved_standalone_evidence(root, selection, review, rows, qa)
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
        if candidate.get("complete_standalone_selection") and set(candidate["original_fallback_assets"]) & set(active):
            raise ValueError("original fallback already has registered HD artwork")
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
        if candidate.get("complete_standalone_selection"):
            additions[-1]["approval_scope"] = "complete_standalone_terrain_selection"
            additions[-1]["original_fallback_assets"] = candidate["original_fallback_assets"]
            additions[-1]["full_inventory"] = candidate["full_inventory"]
    if additions and not args.dry_run:
        # Do not overwrite another registration completed during validation.
        if manifest_path.read_bytes() != original_manifest or provenance_path.read_bytes() != original_provenance:
            raise ValueError("active pack changed during validation; retry from the new snapshot")
        provenance.setdefault("reviewed_sequence_additions", []).extend(additions)
        provenance["registered_frame_count"] = len(active)
        provenance["status"] = f"{len(active)} reviewed original picture frames registered as complete families or explicit standalone Terrain selections. Whole-catalog queues remain active; HD stays optional. Render reachability is recorded separately."
        provenance["registration_updated_at_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        # Runtime uses hd.json alone. Write its ancillary evidence first, then
        # replace the complete manifest in one atomic rename.
        atomic_json(provenance_path, provenance)
        atomic_json(manifest_path, manifest)
    print(json.dumps({"dry_run": args.dry_run, "jobs_added": [row["job_id"] for row in additions], "frames_added": sum(row["frames"] for row in additions), "registered_frames": len(active)}))


if __name__ == "__main__":
    main()
