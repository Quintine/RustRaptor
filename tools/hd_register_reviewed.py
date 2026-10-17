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
from hd_frame_policy import validate_frame_policy, retained_review_version_ok


CARRIED_TERRAIN_V2 = "standalone-terrain-carried-identity-v2"


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
        if candidate.get("carried_registered_assets") or candidate.get("carried_registered_identity"):
            raise ValueError("carried artwork requires an explicit standalone Terrain selection")
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
    carried = asset_list(candidate.get("carried_registered_assets", []), "carried_registered_assets")
    if (full != inventory or selected != set(rows) or not selected or
            selected & fallback or selected & carried or fallback & carried or
            selected | fallback | carried != full):
        raise ValueError("standalone selected/fallback partition differs from complete job inventory")
    if carried:
        # The unversioned route remains the exact legacy Master74 contract.
        # Other shards must opt into the separately checked v2 identity.
        identity = candidate.get("carried_registered_identity")
        if isinstance(identity, dict) and "contract_version" in identity:
            if identity["contract_version"] != CARRIED_TERRAIN_V2:
                raise ValueError("unknown carried Terrain identity contract")
        elif (job.get("job_id") != "terrain-2059d-205ac" or
                selected != {"205a3", "205a4"} or len(full) != 16 or
                len(carried) != 14 or fallback or
                not isinstance(identity, dict)):
            raise ValueError("carried selection differs from the reviewed master74 two-new/fourteen-carried scope")
    elif candidate.get("carried_registered_identity"):
        raise ValueError("carried identity has no registered siblings")
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
    selection = {key: sorted(value) for key, value in [
        ("full_inventory", full), ("selected_assets", selected), ("original_fallback_assets", fallback)]}
    if carried:
        selection["carried_registered_assets"] = sorted(carried)
    return selection


def same_json(left, right):
    """Identity includes JSON types: False is not the integer frame zero."""
    return json.dumps(left, sort_keys=True, separators=(",", ":")) == json.dumps(right, sort_keys=True, separators=(",", ":"))


def require_standalone_membership(proposal, assets):
    """A retained frame zero cannot be hidden inside a partial animation."""
    for sequence in proposal["sequences"]:
        base = sequence["base_asset"]
        base = int(base, 16) if isinstance(base, str) else base
        if type(sequence["frame_count"]) is not int:
            raise ValueError("carried context sequence count must be an integer")
        members = {f"{base + offset:05x}" for offset in range(sequence["frame_count"])}
        if (assets is None or members & assets) and (
                type(sequence["frame_count"]) is not int or sequence["frame_count"] != 1 or
                len(sequence["frames"]) != 1 or type(sequence["frames"][0]["frame"]) is not int or
                sequence["frames"][0]["frame"] != 0):
            raise ValueError("carried/new Terrain identity contains an animation or partial sequence")


def validate_carried_registered_identity(root, candidate, job, rows, review):
    """Authenticate already accepted siblings; never approve or insert them again."""
    carried = set(candidate.get("carried_registered_assets", []))
    if not carried:
        return
    identity = candidate["carried_registered_identity"]
    if isinstance(identity, dict) and identity.get("contract_version") == CARRIED_TERRAIN_V2:
        return validate_carried_registered_identity_v2(root, candidate, job, rows, review)
    evidence = review.get("standalone_selection", {})
    if not same_json(identity, evidence.get("carried_registered_identity")):
        raise ValueError("review carried identity differs from candidate")
    baseline = identity.get("baseline", {})
    if baseline.get("path") != "hd.json":
        raise ValueError("carried baseline must identify the current HD manifest")
    manifest = receipt_json(root, baseline)
    active = proposal_frames(manifest)
    require_standalone_membership(manifest, carried)
    if set(rows) & set(active) or not carried <= set(active):
        raise ValueError("carried baseline omits siblings or already includes new selected IDs")
    records = identity.get("frames", {})
    if not isinstance(records, dict) or set(records) != carried:
        raise ValueError("carried identity omits or adds registered IDs")
    targets = {target["asset"]: target for target in job["targets"]}
    provenance = identity.get("provenance", {})
    if provenance.get("path") != "provenance.json":
        raise ValueError("carried provenance must identify the current registration evidence")
    additions = receipt_json(root, provenance).get("reviewed_sequence_additions", [])
    index = identity.get("registration_record_index")
    if type(index) is not int or not 0 <= index < len(additions):
        raise ValueError("unsafe carried registration record index")
    registered = additions[index]
    if (registered.get("job_id") != job["job_id"] or
            asset_list(registered.get("assets"), "registered carried assets") != carried or
            type(registered.get("frames")) is not int or registered["frames"] != 14 or
            registered.get("frame_bindings_sha256") != identity.get("frame_bindings_sha256")):
        raise ValueError("carried registration belongs to another job or frame map")
    accepted_receipt = identity.get("accepted_runtime_qa", {})
    if accepted_receipt.get("path") != registered.get("runtime_qa"):
        raise ValueError("carried evidence is not the previously registered runtime receipt")
    accepted = receipt_json(root, accepted_receipt)
    accepted_frames = {frame["asset"]: frame for frame in accepted.get("frames", [])}
    if (accepted.get("diagnostics") or accepted.get("frame_bindings_sha256") != identity.get("frame_bindings_sha256") or
            len(accepted_frames) != len(accepted.get("frames", [])) or set(accepted_frames) != carried):
        raise ValueError("previously registered carried runtime evidence differs")
    bindings = {}
    for asset in sorted(carried):
        record = records[asset]
        frame = active[asset]
        if not isinstance(record, dict) or not same_json(record.get("frame_binding"), frame):
            raise ValueError(f"carried complete registered frame changed: {asset}")
        target = targets[asset]
        if (type(frame.get("frame")) is not int or frame["frame"] != 0 or
                type(frame.get("logical_width")) is not int or type(frame.get("logical_height")) is not int or
                [frame["logical_width"], frame["logical_height"]] != target["logical_canvas"] or
                frame.get("origin") != target["origin"] or
                frame.get("source_sha256") != target["source_sha256"] or
                record.get("source_sha256") != target["source_sha256"]):
            raise ValueError(f"carried native source/canvas/origin differs: {asset}")
        if set(frame) - {"frame", "file", "crop", "logical_width", "logical_height", "origin", "source_sha256"}:
            raise ValueError(f"carried master74 frame has an unreviewed optional policy: {asset}")
        raw = contained(root, frame["file"])
        measurement = accepted_frames[asset]
        masks = measurement.get("hd_masks", [])
        if (measurement.get("source_sha256") != frame["source_sha256"] or
                measurement.get("logical_canvas") != target["logical_canvas"] or len(masks) != 4 or
                any(type(mask["scale"]) is not int for mask in masks) or
                {mask["scale"] for mask in masks} != {1, 2, 3, 4}):
            raise ValueError(f"previously registered carried source/scales differ: {asset}")
        accepted_raw = accepted.get("artwork_sha256", {}).get(frame["file"])
        if (record.get("raw_sha256") != accepted_raw or
                hashlib.sha256(raw.read_bytes()).hexdigest() != accepted_raw):
            raise ValueError(f"carried raw artwork changed: {asset}")
        bindings[asset] = frame
    if identity.get("frame_bindings_sha256") != binding_digest(bindings):
        raise ValueError("carried complete frame digest differs")


def validate_carried_registered_identity_v2(root, candidate, job, rows, review):
    """Opt-in multi-record identity, not a new approval of registered artwork.

    Record hashes use canonical JSON (sorted keys, compact separators), as does
    binding_digest. Each descriptor names a WHOLE prior registration, even when
    only some of its assets are carried by this shard. Optional-field presence,
    raw routes and policies are part of each exact current frame binding.
    """
    selection = standalone_selection(candidate, job, rows)
    identity = candidate["carried_registered_identity"]
    if (selection is None or identity.get("contract_version") != CARRIED_TERRAIN_V2 or
            set(identity) != {"contract_version", "baseline", "provenance", "frames",
                              "frame_bindings_sha256", "registration_records"} or
            not same_json(identity, review.get("standalone_selection", {}).get("carried_registered_identity"))):
        raise ValueError("versioned carried identity or independent review differs")
    carried = set(selection["carried_registered_assets"])
    if identity.get("baseline", {}).get("path") != "hd.json" or identity.get("provenance", {}).get("path") != "provenance.json":
        raise ValueError("carried v2 requires the exact current canonical pair")
    manifest = receipt_json(root, identity["baseline"])
    active = proposal_frames(manifest)
    require_standalone_membership(manifest, carried)
    if (set(rows) & set(active) or set(selection["original_fallback_assets"]) & set(active)
            or not carried <= set(active)):
        raise ValueError("carried v2 selected/fallback/current registration partition differs")
    records = identity["frames"]
    if not isinstance(records, dict) or set(records) != carried:
        raise ValueError("carried v2 frame membership differs")
    # Authenticate the full original shard, including fallback. A current HD
    # sequence declaration alone cannot turn a non-Terrain animation into one.
    pictures, payloads = authentic_terrain_inventory(root, job)
    targets = {target["asset"]: target for target in job["targets"]}
    additions = receipt_json(root, identity["provenance"]).get("reviewed_sequence_additions", [])
    descriptors = identity["registration_records"]
    if not isinstance(additions, list) or not isinstance(descriptors, list) or not descriptors:
        raise ValueError("carried v2 needs actual prior registration records")
    accepted_by_index = {}
    for descriptor in descriptors:
        if (not isinstance(descriptor, dict) or set(descriptor) != {
                "registration_record_index", "registration_record_sha256", "assets",
                "frame_bindings_sha256", "accepted_runtime_qa"}):
            raise ValueError("invalid carried v2 registration descriptor")
        index = descriptor["registration_record_index"]
        if type(index) is not int or not 0 <= index < len(additions) or index in accepted_by_index:
            raise ValueError("unsafe or duplicate carried v2 registration index")
        registered = additions[index]
        if not isinstance(registered, dict) or descriptor["registration_record_sha256"] != binding_digest(registered):
            raise ValueError("carried v2 prior registration record changed")
        assets = asset_list(registered.get("assets"), "prior registered assets")
        if (not assets or asset_list(descriptor["assets"], "carried v2 record assets") != assets or
                type(registered.get("frames")) is not int or registered["frames"] != len(assets) or
                not assets <= set(active) or not assets & carried):
            raise ValueError("carried v2 prior registration asset set differs")
        receipt = descriptor["accepted_runtime_qa"]
        if not isinstance(receipt, dict) or receipt.get("path") != registered.get("runtime_qa"):
            raise ValueError("carried v2 receipt is not the actual registered runtime QA")
        accepted = receipt_json(root, receipt)
        measurements = accepted.get("frames", [])
        if not isinstance(measurements, list) or any(not isinstance(m, dict) for m in measurements):
            raise ValueError("invalid prior carried v2 runtime frames")
        measured = {m.get("asset"): m for m in measurements}
        digest = binding_digest({asset: active[asset] for asset in assets})
        if (accepted.get("diagnostics") != [] or len(measured) != len(measurements) or set(measured) != assets or
                any(value != digest for value in [registered.get("frame_bindings_sha256"),
                    descriptor["frame_bindings_sha256"], accepted.get("frame_bindings_sha256")])):
            raise ValueError("carried v2 full registered frame map/runtime QA differs")
        accepted_by_index[index] = (assets, accepted, measured)
    used, bindings = set(), {}
    for asset in sorted(carried):
        record, frame, target = records[asset], active[asset], targets[asset]
        if (not isinstance(record, dict) or set(record) != {"frame_binding", "source_sha256", "raw_sha256", "registration_record_index"}
                or not same_json(record["frame_binding"], frame)):
            raise ValueError(f"carried v2 exact native binding/policy differs: {asset}")
        index = record["registration_record_index"]
        if type(index) is not int or index not in accepted_by_index or asset not in accepted_by_index[index][0]:
            raise ValueError(f"carried v2 frame names a foreign registration: {asset}")
        used.add(index)
        if (type(frame.get("frame")) is not int or frame["frame"] != 0 or
                type(frame.get("logical_width")) is not int or type(frame.get("logical_height")) is not int or
                not same_json([frame["logical_width"], frame["logical_height"]], target["logical_canvas"]) or
                not same_json(list(pictures[asset].size), target["logical_canvas"]) or
                not same_json(frame.get("origin"), [0, 0]) or not same_json(target.get("origin"), [0, 0]) or
                frame.get("source_sha256") != target["source_sha256"] or record["source_sha256"] != target["source_sha256"]):
            raise ValueError(f"carried v2 authentic native Source differs: {asset}")
        validate_frame_policy(frame, payloads[asset])
        accepted, measurement = accepted_by_index[index][1], accepted_by_index[index][2][asset]
        masks = measurement.get("hd_masks", [])
        if (measurement.get("source_sha256") != frame["source_sha256"] or
                not same_json(measurement.get("logical_canvas"), target["logical_canvas"]) or
                not isinstance(masks, list) or len(masks) != 4 or
                any(not isinstance(m, dict) or type(m.get("scale")) is not int for m in masks) or
                {m["scale"] for m in masks} != {1, 2, 3, 4}):
            raise ValueError(f"carried v2 accepted Source/scales differ: {asset}")
        accepted_raw = accepted.get("artwork_sha256", {}).get(frame["file"])
        if (re.fullmatch(r"[0-9a-f]{64}", str(accepted_raw)) is None or record["raw_sha256"] != accepted_raw or
                hashlib.sha256(contained(root, frame["file"]).read_bytes()).hexdigest() != accepted_raw):
            raise ValueError(f"carried v2 raw artwork changed: {asset}")
        bindings[asset] = frame
    if used != set(accepted_by_index) or identity["frame_bindings_sha256"] != binding_digest(bindings):
        raise ValueError("carried v2 unused record or complete carried digest differs")


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
    baseline = receipt_json(root, authority.get("baseline"))
    future = receipt_json(root, authority.get("future_projection"))
    if selection.get("carried_registered_assets"):
        identity = evidence["carried_registered_identity"]
        active = proposal_frames(baseline)
        projected = proposal_frames(future)
        if (authority["baseline"]["sha256"] != identity["baseline"]["sha256"] or
                set(active) & set(bindings) or not same_json(projected, {**active, **bindings})):
            raise ValueError("carried context is not the exact current baseline plus new definitions")
        require_standalone_membership(proposal, None)
        require_standalone_membership(future, set(rows) | set(selection["carried_registered_assets"]))
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


def approved_catalog_only_retained_evidence(root, project, declaration, rows, qa):
    """Unused catalog pictures need real intrinsic review, without an invented scene."""
    if len(rows) != 1:
        raise ValueError("catalog-only retained review needs one complete picture")
    asset, frame = next(iter(rows.items()))
    trace = receipt_json(root, declaration.get("catalog_only_source_trace"))
    counts = trace.get("base_enemy_source_counts", {})
    if (trace.get("status") != "CLOSED_BOUNDED_SOURCE_TRACE_NO_KNOWN_ORIGINAL_RUNTIME_CALLER_INTRINSIC_ONLY"
            or trace.get("asset") != asset or type(counts.get("matching_names_or_art_frame_intervals")) is not int
            or counts["matching_names_or_art_frame_intervals"] != 0):
        raise ValueError("catalog-only review lacks the exact no-caller Source trace")
    libraries = trace.get("original_library_scan", [])
    if not isinstance(libraries, list) or len(libraries) != 4:
        raise ValueError("catalog-only trace needs all four original sprite libraries")
    source = trace.get("Source", {})
    source_path = Path(source.get("path", ""))
    data_roots = [data for data in [project / "data", project.parent / "data"]
                  if source_path.is_absolute() and source_path.is_relative_to(data)
                  and all(row.get("original_library", {}).get("path") == str(data / "misc" / f"SPRITE{game}_ITM")
                          for game, row in enumerate(libraries, 1))]
    if len(data_roots) != 1:
        raise ValueError("catalog-only Source and four sprite libraries must bind one approved data root")
    data = data_roots[0]
    entries = [line.split() for line in (data / "INDEX").read_text().splitlines()]
    names = {Path(parts[2]).name: int(parts[0], 16) for parts in entries if len(parts) == 3}
    if any(f"{edge}G{game}TILES" not in names for edge in ["START", "END"] for game in range(1, 5)):
        raise ValueError("catalog-only trace lacks original Terrain category boundaries")
    if any(names[f"STARTG{game}TILES"] < int(asset, 16) < names[f"ENDG{game}TILES"] for game in range(1, 5)):
        raise ValueError("catalog-only non-Terrain scope cannot approve original Terrain")
    category_job = receipt_json(root, trace.get("category_authority"))
    if (not isinstance(trace.get("category"), str) or trace["category"] == "Terrain"
            or category_job.get("category") != trace["category"]
            or declaration.get("catalog_only_source_category") != trace["category"]
            or asset not in {target.get("asset") for target in category_job.get("targets", [])}):
        raise ValueError("catalog-only original non-Terrain category proof differs")
    source_path = next((data / parts[2] for parts in entries
                        if len(parts) == 3 and int(parts[0], 16) == int(asset, 16)), None)
    if (source_path is None or source.get("path") != str(source_path)
            or hashlib.sha256(source_path.read_bytes()).hexdigest() != frame["source_sha256"]
            or source.get("sha256") != frame["source_sha256"]
            or names.get(trace.get("name")) != int(asset, 16)):
        raise ValueError("catalog-only trace differs from the authentic Source picture")
    traced = proposal_frames({"sequences": [trace["full_candidate_native_sequence"]]})
    if set(traced) != {asset} or not same_json(dict(traced[asset], file=frame["file"]), frame):
        raise ValueError("catalog-only Source trace belongs to another complete native frame")
    total = 0
    for game, row in enumerate(libraries, 1):
        path = data / "misc" / f"SPRITE{game}_ITM"
        payload = path.read_bytes()
        recorded = row.get("original_library", {})
        if (len(payload) % 528 or recorded.get("path") != str(path)
                or hashlib.sha256(payload).hexdigest() != recorded.get("sha256")
                or type(row.get("records")) is not int or row["records"] != len(payload) // 528
                or row.get("target_intersections") != []):
            raise ValueError("catalog-only original sprite Source trace changed")
        total += len(payload) // 528
        for offset in range(0, len(payload), 528):
            record = payload[offset:offset + 528]
            name = record[:16].split(b"\0", 1)[0].decode()
            base = names.get(name)
            frames = max(1, int.from_bytes(record[44:48], "little", signed=True))
            if base is not None and base <= int(asset, 16) < base + frames:
                raise ValueError("catalog-only picture has an original sprite caller")
    if (type(counts.get("libraries")) is not int or counts["libraries"] != 4
            or type(counts.get("records")) is not int or counts["records"] != total):
        raise ValueError("catalog-only original Source counts differ")
    named = trace.get("direct_named_native_Rust_search", {})
    sources = named.get("source_files", [])
    if (named.get("matches") != [] or {q.get("path") for q in sources}
            != {str(p) for p in (project / "src").rglob("*.rs")}):
        raise ValueError("catalog-only named native caller trace is incomplete")
    pattern = re.compile(rf"{re.escape(trace['name'])}|\b(?:0x)?{asset}\b|\b{int(asset, 16)}\b", re.I)
    for source in sources:
        payload = Path(source["path"]).read_bytes()
        if hashlib.sha256(payload).hexdigest() != source.get("sha256") or pattern.search(payload.decode()):
            raise ValueError("catalog-only native caller Source changed")
    peer = receipt_json(root, declaration.get("catalog_only_independent_material"))
    contract = declaration.get("catalog_only_material_contract", {})
    artist = peer.get("actual_artist", peer.get("original_generated_artist"))
    preparer = peer.get("hybrid_trial_preparer", peer.get("hybrid_preparer"))
    independent = peer.get("different_from_artist_and_preparer",
                           peer.get("independent_from_original_generated_artist_and_hybrid_preparer"))
    scale_records = peer.get("scales", [])
    qualified = (peer.get("qualified_complete1") is True and peer.get("all4_scales_qualified") is True
                 and type(peer.get("complete_native_frames")) is int and peer["complete_native_frames"] == 1
                 and same_json(peer.get("native_scales"), [1, 2, 3, 4]))
    # Older complete-picture peers state their whole-material verdict explicitly,
    # followed by four independently authenticated native-scale decisions.
    if isinstance(peer.get("whole_disposition"), str) and peer["whole_disposition"].partition(":")[0] == "QUALIFIED":
        qualified = (len(scale_records) == 4 and [s.get("scale") for s in scale_records] == [1, 2, 3, 4]
                     and all(type(s.get("scale")) is int and s.get("all_selected_exact_independent_SourceNx") is True
                             and s.get("all_outside_index_RGB_exact_plain") is True
                             and type(s.get("selected_samples")) is int
                             and s["selected_samples"] == len(frame["original_detail_cells"]) * s["scale"] ** 2
                             for s in scale_records))
    status_words = set(re.split(r"[^A-Z0-9]+", str(peer.get("status", "")).upper()))
    if (not status_words.intersection({"QUALIFIED", "PASS"})
            or status_words.intersection({"NOT", "UNQUALIFIED", "HOLD", "PENDING", "FAIL", "FAILED"})
            or any(re.fullmatch(r"HOLD[1-9][0-9]*", word) for word in status_words)
            or type(peer.get("held_frames", 0)) is not int or peer.get("held_frames", 0) != 0):
        qualified = False
    if (not qualified or peer.get("asset") != asset or independent is not True
            or not all(isinstance(value, str) and value for value in [peer.get("reviewer"), artist, preparer])
            or peer["reviewer"] in [artist, preparer]
            or contract.get("status") != "qualified"
            or contract.get("scope") != "complete_native_picture_intrinsic_all_scales"
            or contract.get("asset") != asset or contract.get("reviewer") != peer["reviewer"]
            or contract.get("artist") != artist or contract.get("preparer") != preparer
            or type(contract.get("qualified_frames")) is not int or contract["qualified_frames"] != 1
            or type(contract.get("held_frames")) is not int or contract["held_frames"] != 0
            or type(contract.get("retained_cell_count")) is not int
            or contract["retained_cell_count"] != len(frame["original_detail_cells"])
            or not same_json(contract.get("native_frame"), frame)
            or not same_json(contract.get("retained_cells"), frame["original_detail_cells"])
            or not same_json(contract.get("native_scales"), [1, 2, 3, 4])):
        raise ValueError("catalog-only review lacks independent qualified whole material evidence")
    reviewed = proposal_frames(receipt_json(root, peer.get("candidate")))
    if set(reviewed) != {asset}:
        raise ValueError("catalog-only material frame membership differs")
    alias = dict(reviewed[asset], file=frame["file"])
    raw = peer.get("raw", peer.get("untouched_v3_raw", {}))
    cells = peer.get("exact_original_detail_cells", peer.get("exact_retained_Original_cells"))
    if (not same_json(alias, frame) or raw.get("sha256") != qa["artwork_sha256"][frame["file"]]
            or not same_json(cells, frame["original_detail_cells"])):
        raise ValueError("catalog-only material source, raw or full native frame differs")
    measured = receipt_json(root, declaration.get("catalog_only_actual_allscale_QA"))
    frames = measured.get("frames", [])
    if (measured.get("diagnostics") != [] or type(measured.get("validated_frames")) is not int
            or measured["validated_frames"] != 1 or len(frames) != 1 or not same_json(frames, qa["frames"])
            or [mask["scale"] for mask in frames[0]["hd_masks"]] != [1, 2, 3, 4]
            or any(type(mask["scale"]) is not int for mask in frames[0]["hd_masks"])):
        raise ValueError("catalog-only actual all-scale evidence differs")


def validate_extended_retained_sources(project, rows):
    """Longer lists require authentic catalog bytes, not claimed QA pixel counts.

    Only the two product data layouts are eligible. ID+SHA select the authentic
    payload; a catalog-only trace is still separately bound to its exact root.
    No generated PNG or recorded density can supply the denominator.
    """
    for asset, frame in rows.items():
        if len(frame.get("original_detail_cells", [])) <= 64:
            continue
        authenticated = False
        for data in (project / "data", project.parent / "data"):
            index = data / "INDEX"
            if not index.is_file():
                continue
            matches = [parts for line in index.read_text().splitlines()
                       if len(parts := line.split()) == 3 and int(parts[0], 16) == int(asset, 16)]
            if len(matches) != 1:
                continue
            relative = Path(matches[0][2])
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("extended Original Source path escapes catalog")
            path = (data / relative).resolve()
            if not path.is_relative_to(data.resolve()):
                raise ValueError("extended Original Source path escapes catalog")
            payload = path.read_bytes()
            if hashlib.sha256(payload).hexdigest() != frame["source_sha256"]:
                continue
            validate_frame_policy(frame, payload)
            authenticated = True
            break
        if not authenticated:
            raise ValueError("extended Original details lack authentic catalog Source bytes")


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
    retained_details = {asset: frame["original_detail_cells"] for asset, frame in rows.items()
                        if frame.get("original_detail_cells")}
    if retained_details:
        declaration = review.get("retained_original_detail_review", {})
        catalog_only = declaration.get("hybrid_review_scope") == "catalog_only_no_known_original_runtime_caller"
        if catalog_only and selection is not None:
            raise ValueError("catalog-only scope cannot replace contextual Terrain approval")
        qualified_scope = declaration.get("hybrid_allscale_and_genuine_context_independent_review") is True
        if catalog_only:
            qualified_scope = (declaration.get("hybrid_allscale_and_genuine_context_independent_review") is False
                               and declaration.get("catalog_only_no_original_runtime_caller") is True
                               and declaration.get("catalog_only_independent_whole_material_and_allscale_review") is True)
        if (not same_json(declaration.get("cells_by_asset"), retained_details)
                or declaration.get("retained_original_not_generated_HD") is not True
                or not retained_review_version_ok(declaration.get("policy_version"), retained_details)
                or not same_json(declaration.get("painted_Source_palette_domain"), [0, 255])
                or declaration.get("functional_palette_effects_are_retained_Original") is not True
                or not qualified_scope
                or declaration.get("frame_bindings_sha256") != digest):
            raise ValueError("retained Original detail provenance and exact hybrid review are required")
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
        validate_carried_registered_identity(root, candidate, job, rows, review)
        for asset, frame in rows.items():
            validate_hd_frame(root, frame, payloads[asset], pictures[asset])
        approved_standalone_evidence(root, selection, review, rows, qa)
    elif retained_details and catalog_only:
        approved_catalog_only_retained_evidence(root, project, declaration, rows, qa)
    validate_extended_retained_sources(project, rows)
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
            if (not candidate.get("carried_registered_assets") and overlaps == set(rows) and
                    all(rows[asset] == active[asset] for asset in rows)):
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
            if candidate.get("carried_registered_assets"):
                additions[-1]["approval_scope"] = "complete_standalone_terrain_selection_with_unchanged_registered_siblings"
                additions[-1]["carried_registered_assets"] = candidate["carried_registered_assets"]
                additions[-1]["carried_registered_identity"] = candidate["carried_registered_identity"]
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
