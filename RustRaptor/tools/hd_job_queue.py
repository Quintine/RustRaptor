#!/usr/bin/env python3
"""Create exhaustive, source-bound HD jobs and a metadata-only completion ledger.

Original/reference PNGs and AI artwork stay in ignored data/hd. Jobs own disjoint
catalog IDs; exact payload aliases may reuse reviewed art with separate hashes.
"""
import argparse
import collections
import fcntl
import hashlib
import json
import math
import os
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from hd_art_source import decode
from hd_candidate_review import proposal_frames, binding_digest
from hd_art_audit import source_palette_name, checked_palette

CATEGORY_SLUGS = {
    "Player banking": "players",
    "Bosses": "bosses",
    "Enemies and ground objects": "enemies",
    "Player and enemy projectiles": "projectiles",
    "Explosions and effects": "effects",
    "Equipment and pickups": "equipment",
    "Terrain": "terrain",
    "Menus, portraits, HUD and other pictures": "interface-other",
}
STAGES = ["missing", "inprogress", "candidate", "reviewed", "registered", "renderreachable"]


def read_json(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    temporary.replace(path)


def index_entries(data):
    result = {}
    for line in (data / "INDEX").read_text().splitlines():
        if line.strip():
            asset, size, source = line.split()
            result[int(asset, 16)] = {"path": source, "bytes": int(size)}
    return result


def families(report):
    pictures = {int(row["asset"], 16): row for row in report["assets"]}
    parent = {asset: asset for asset in pictures}

    def find(asset):
        while parent[asset] != asset:
            parent[asset] = parent[parent[asset]]
            asset = parent[asset]
        return asset

    def join(ids):
        ids = [asset for asset in ids if asset in pictures]
        if ids:
            first = find(ids[0])
            for asset in ids[1:]:
                parent[find(asset)] = first

    declared = []
    for category, groups in report["sequences"].items():
        if category == "Terrain":
            continue
        for group in groups:
            ids = [asset for asset in group["frames"] if asset in pictures]
            join(ids)
            declared.append((category, group, ids))
    # Unreferenced named picture suffixes still form complete animation families.
    stems = collections.defaultdict(list)
    for asset, row in pictures.items():
        if row["category"] != "Terrain":
            stem = re.sub(r"\.\d+$", "", Path(row["path"]).name)
            stems[stem].append(asset)
    for ids in stems.values():
        ids = sorted(ids)
        if len(ids) > 1 and ids == list(range(ids[0], ids[-1] + 1)):
            join(ids)
    # Related static variants are kept together for material/readability QA.
    for start, count in [(0x10005, 11), (0x1001a, 4), (0x1001e, 4),
                         (0x10023, 8), (0x10111, 9), (0x10121, 4),
                         (0x1012a, 2), (0x1012d, 2), (0x10130, 4),
                         (0x10134, 2), (0x10136, 2), (0x10162, 2),
                         (0x102df, 2), (0x102e1, 23), (0x50005, 2)]:
        join(range(start, start + count))
    components = collections.defaultdict(list)
    for asset, row in pictures.items():
        if row["category"] != "Terrain":
            components[find(asset)].append(asset)
    result = []
    for ids in components.values():
        ids.sort()
        categories = {pictures[asset]["category"] for asset in ids}
        category = min(categories, key=lambda name: list(CATEGORY_SLUGS).index(name))
        ranges = []
        for declared_category, group, members in declared:
            if members and members[0] in ids:
                item = {"name": group["name"], "base_asset": group["base_asset"],
                        "frames": len(group["frames"])}
                if "render_semantics" in group:
                    item["render_semantics"] = group["render_semantics"]
                if item not in ranges:
                    ranges.append(item)
        names = list(dict.fromkeys(item["name"] for item in ranges))
        if not names:
            names = list(dict.fromkeys(re.sub(r"\.\d+$", "", Path(pictures[asset]["path"]).name) for asset in ids))
        result.append({"id": f"{CATEGORY_SLUGS[category]}-{ids[0]:05x}-{ids[-1]:05x}",
                       "category": category, "name": " / ".join(names),
                       "assets": ids, "declared_ranges": ranges,
                       "kind": "complete_family"})
    return sorted(result, key=lambda family: family["assets"][0])


def terrain_context(runtime):
    neighbors = collections.defaultdict(lambda: collections.defaultdict(set))
    samples = collections.defaultdict(list)
    partners = collections.defaultdict(set)
    roles = collections.defaultdict(set)

    def ids(art):
        return list(range(art["asset"], art["asset"] + art["frames"])) if art and art.get("asset") is not None else []

    for mission_id, mission in runtime.get("missions", {}).items():
        columns = mission["columns"]
        layout = mission["layout"]
        cells = []
        for tile_index in layout:
            tile = mission["tiles"][tile_index]
            normal, destroyed = ids(tile["art"]), ids(tile["destroyed"])
            for asset in normal:
                roles[asset].add("intact")
                partners[asset].update(destroyed)
            for asset in destroyed:
                roles[asset].add("destroyed")
                partners[asset].update(normal)
            cells.append((normal, destroyed))
        for position, (normal, destroyed) in enumerate(cells):
            row, column = divmod(position, columns)
            adjacent = {"north": position - columns if row else None,
                        "south": position + columns if position + columns < len(cells) else None,
                        "west": position - 1 if column else None,
                        "east": position + 1 if column + 1 < columns else None}
            for asset in normal + destroyed:
                for direction, neighbor in adjacent.items():
                    if neighbor is not None:
                        neighbors[asset][direction].update(cells[neighbor][0] + cells[neighbor][1])
                if len(samples[asset]) < 3:
                    patch = []
                    for dy in [-1, 0, 1]:
                        for dx in [-1, 0, 1]:
                            rr, cc = row + dy, column + dx
                            at = rr * columns + cc
                            patch.append(cells[at][0][0] if 0 <= rr and 0 <= cc < columns and at < len(cells) and cells[at][0] else None)
                    sample = {"mission": mission_id, "row": row, "column": column,
                              "intact_3x3": [f"{item:05x}" if item is not None else None for item in patch]}
                    target_patch = sample["intact_3x3"].copy()
                    target_patch[4] = f"{asset:05x}"
                    sample["target_3x3"] = target_patch
                    if sample not in samples[asset]:
                        samples[asset].append(sample)
    return {asset: {"roles": sorted(roles[asset]),
                    "state_partners": [f"{item:05x}" for item in sorted(partners[asset])],
                    "neighbors": {direction: [f"{item:05x}" for item in sorted(neighbors[asset].get(direction, []))]
                                  for direction in ["north", "south", "west", "east"]},
                    "samples": samples[asset]}
            for asset in set(roles) | set(neighbors)}


def contract(family):
    terrain = family["kind"] == "contextual_terrain_shard"
    return {
        "generation": "Use built-in imagegen with inspected original source sheets. Produce newly authored detail, materials and lighting; nearest/ScaleNx enlargement alone is not HD completion.",
        "submission_gate": "Prepare and inspect sources and save the prompt before acquiring. In one functions.exec orchestration, acquire one of four slots, start the reservation, submit built-in imagegen only when start.changed is true, then classify and report the actual result immediately after await before returning to the model or doing QA. See RustRaptor/docs/hd-generation-workflow.md. Started and legacy-unknown requests require explicit finish; only unstarted reservations expire. If denied or cooling down, prepare/review other jobs. Do not substitute scaling for a failed remaster.",
        "source_truth": "Keep every source orientation, silhouette, color identity, logical canvas, anchor and explicit source hash. Use each target's source_palette and source_palette_sha256; Apogee/Cygnus/Taiwan cards use their own palettes, not the gameplay palette. Inspect every frame before generating. Never invent poses or drop damaged/destroyed variants.",
        "ownership": "Only this job's target IDs may be proposed. Neighbor/context references and exact-source aliases are reference-only; never claim or overwrite another job's IDs.",
        "raw_output": "Keep raw generated PNG bytes, prompts, source references and provenance. Do not retouch generated RGB/alpha. Atlas/square margin crops are allowed only if they preserve all meaningful visible pixels and original aspect.",
        "full_family": "Review all frames together at logical resolution and indexed 4× with exact Rust Lanczos3 resident→presentation resampling. A good still does not complete an animation family. Record partial candidates and rejections truthfully.",
        "quality": "Check clipping, alpha halos, banking/animation centers, source bounds, pivots, tiny-projectile readability, palette fades/cycling, material continuity and intended timing. Original ordinary pixels must not gain indices240..255; water/fire/individualblink source classes retain their semantics. Compare original and allscale dynamic-palette counts in runtime-qa.json. Numeric mask metrics support visual review, never replace it.",
        "terrain": "Use supplied 3×3 neighboring context, all cardinal adjacency sets, repeated tile aliases and intact/destroyed state partners. Preserve coastline/topography crossings, native edge colors and exact reusable tile identity. Review every required adjacent pair, including state changes; full opaque 32×32 terrain canvases are valid. Do not publish context-specific alternate art for one repeated ID. The validated renderer shares adjoining HD edge/corner colors only where original surface class/geometry agrees, and transitions HD/original boundaries towards the joined original layer over two logical pixels; see RustRaptor/docs/hd-terrain.md. Feathering cannot repair shifted coastlines or make a low-resolution grid acceptable; detailed interiors must remain newly authored HD art. Preserve source water indices 240..244, fire 245..249 and single-index glow/flash 250..255; ordinary terrain maps to 0..239." if terrain else None,
        "renderer": "Registration is separate from render reachability. Require a verified Rust rendering path and record scene/gallery evidence; unsupported terrain/mask/shader semantics remain explicitly pending.",
        "result": "Write candidate.json with job_id, source_sha256 and every proposed target's file/logical dimensions/origin/crop, plus complete sequence metadata and review evidence. Only the coordinator edits global hd.json, completion ledger or provenance.",
    }


def build(args):
    report = read_json(args.audit)
    if report is None:
        raise ValueError("run hd_art_audit.py first")
    pictures = {int(row["asset"], 16): row for row in report["assets"]}
    entries = index_entries(args.data)
    runtime = read_json(args.runtime, {})
    context = terrain_context(runtime)
    family_list = families(report)
    for terrain_set in report["sequences"]["Terrain"]:
        ids = terrain_set["frames"]
        for start in range(0, len(ids), args.terrain_batch):
            subset = ids[start:start + args.terrain_batch]
            family_list.append({"id": f"terrain-{subset[0]:05x}-{subset[-1]:05x}",
                                "name": terrain_set["name"] + f" shard {start // args.terrain_batch + 1}",
                                "category": "Terrain", "assets": subset,
                                "kind": "contextual_terrain_shard", "declared_ranges": [],
                                "terrain_set": terrain_set["name"]})
    hashes = collections.defaultdict(list)
    for asset, row in pictures.items():
        hashes[row["source_sha256"]].append(asset)
    canonical = {asset: min(ids) for ids in hashes.values() for asset in ids}
    asset_jobs = {}
    for family in family_list:
        for asset in family["assets"]:
            if asset in asset_jobs:
                raise ValueError(f"duplicate job owner for {asset:05x}")
            asset_jobs[asset] = family["id"]
    if set(asset_jobs) != set(pictures):
        raise ValueError("job partition does not cover the complete picture inventory")
    previous = read_json(args.ledger, {})
    previous_assets = previous.get("assets", {})
    jobs = []
    ledger_assets = {}
    for family in family_list:
        directory = args.jobs / family["id"]
        directory.mkdir(parents=True, exist_ok=True)
        job_lock = (directory / ".claim.lock").open("a")
        fcntl.flock(job_lock, fcntl.LOCK_EX)
        existing = read_json(directory / "job.json", {})
        owner = existing.get("owner")
        if family["assets"][0] == 0x20045:
            owner = owner or "/root/hd_dark_player"
        if family["assets"][0] == 0x2004c:
            owner = owner or "/root/hd_light_player"
        expected = {f"{asset:05x}": pictures[asset] for asset in family["assets"]}
        candidate_path = directory / "candidate.json"
        candidates = {}
        candidate_error = None
        candidate_digest = None
        if candidate_path.is_file():
            try:
                proposal = read_json(candidate_path)
                if proposal.get("job_id") != family["id"]:
                    raise ValueError("candidate job identity differs")
                candidates = proposal_frames(proposal, expected)
                for frame in candidates.values():
                    root = (args.data / "hd").resolve()
                    art = (root / frame["file"]).resolve()
                    if not art.is_relative_to(root) or not art.is_file():
                        raise ValueError("candidate artwork missing or escapes pack")
                candidate_digest = hashlib.sha256(candidate_path.read_bytes()).hexdigest()
            except (ValueError, KeyError, TypeError, OSError) as error:
                candidates = {}
                candidate_error = str(error)
        coordinator_review = read_json(directory / "coordinator-review.json")
        review_changed = coordinator_review and (
            coordinator_review.get("frame_bindings_sha256") != binding_digest(candidates)
            if coordinator_review.get("frame_bindings_sha256") else
            coordinator_review.get("candidate_sha256") != candidate_digest)
        if review_changed:
            # A corrected proposal needs fresh review; an old approval or hold must
            # never silently apply to newly submitted artwork.
            coordinator_review = None
        target_rows = []
        for asset in family["assets"]:
            source = pictures[asset]
            identity = f"{asset:05x}"
            prior = previous_assets.get(identity, {})
            if prior.get("source_sha256") not in [None, source["source_sha256"]]:
                raise ValueError(f"ledger source changed at {identity}")
            status = "registered" if source["hd"] else "inprogress" if owner else "missing"
            if not source["hd"] and identity in candidates:
                status = "candidate"
                if coordinator_review and coordinator_review.get("status") == "approved":
                    status = "reviewed"
                if prior.get("status") == "reviewed" and prior.get("candidate", {}).get("sha256") == candidate_digest:
                    status = "reviewed"
            renderer = prior.get("renderer", {"availability": "unverified", "evidence": []})
            if source["category"] == "Terrain" and renderer["availability"] in ["unverified", "pipeline_pending"]:
                if report["terrain"]["runtime_hd_composition_supported"]:
                    renderer = {"availability": "canonical_terrain_path_available", "evidence": report["terrain"].get("renderer_evidence", [])}
                else:
                    renderer["availability"] = "pipeline_pending"
            if 0x10225 <= asset <= 0x10228 and renderer["availability"] in ["unverified", "pipeline_pending"]:
                renderer = {"availability": "alpha_shade_mask_path_available", "evidence": ["RustRaptor/src/desktop.rs:pickup glow mask path", "RustRaptor/src/render.rs:Canvas::shade"], "limits": "Shape-alpha and native light table semantics are supported; this adds no remastered mask artwork."}
            if source["source_palette"] != "PALETTE_DAT" and renderer["availability"] in ["unverified", "pipeline_pending", "hd_card_playback_pending"]:
                opening_card = asset in [0x1002b, 0x1002d]
                renderer = {"availability": "static_palette_opening_card_path_available" if opening_card else "static_palette_api_available_scene_pending",
                            "evidence": ["RustRaptor/docs/hd-opening-cards.md", "RustRaptor/src/hd.rs:HdAssets::sprite_static_palette"],
                            "limits": "The source-specific palette API supports all256 static colors. Optional Apogee/Cygnus still-card routing is implemented; Taiwan artwork has no verified native optional-HD scene. These code paths add no remastered artwork or actual-art scene coverage."}
            if prior.get("status") == "renderreachable" and source["hd"]:
                status = "renderreachable"
            row = {"kind": "picture", "category": source["category"],
                   "source_path": source["path"], "source_sha256": source["source_sha256"],
                   "logical_canvas": source["logical_canvas"], "header_options": source["header_options"],
                   "source_palette": source["source_palette"], "source_palette_sha256": source["source_palette_sha256"],
                   "decoded_rgba_sha256": source["decoded_rgba_sha256"],
                   "canonical_source_asset": f"{canonical[asset]:05x}",
                   "family_id": family["id"], "job_id": family["id"],
                   "status": status, "owner": owner, "remaster_required": True,
                   "registry_or_layout_referenced": source["registry_or_layout_referenced"],
                   "renderer": renderer}
            if identity in candidates:
                row["candidate"] = {"manifest": f"jobs/{family['id']}/candidate.json", "sha256": candidate_digest,
                                    "validation_scope": "source-bound metadata, target ownership and artwork file presence; artistic/PNG/runtime review is separate"}
                if coordinator_review:
                    row["coordinator_review"] = coordinator_review
            ledger_assets[identity] = row
            target = {"asset": identity, "source_path": source["path"],
                      "source_sha256": source["source_sha256"], "logical_canvas": source["logical_canvas"],
                      "source_palette": source["source_palette"], "source_palette_sha256": source["source_palette_sha256"],
                      "origin": [0, 0], "canonical_source_asset": f"{canonical[asset]:05x}",
                      "status": status}
            if canonical[asset] != asset:
                target["reuse_dependency_job"] = asset_jobs[canonical[asset]]
            if source["category"] == "Terrain":
                target["terrain_context"] = context.get(asset, {
                    "roles": [], "state_partners": [],
                    "neighbors": {direction: [] for direction in ["north", "south", "west", "east"]},
                    "samples": [], "registry_or_layout_referenced": False,
                    "limits": "Unused catalog tile: no native mission neighbors or state partners were found. Source/runtime gallery review does not establish a native scene occurrence."
                })
            target_rows.append(target)
        statuses = collections.Counter(row["status"] for row in target_rows)
        job = {"format_version": 1, "job_id": family["id"], "name": family["name"],
               "category": family["category"], "kind": family["kind"], "owner": owner,
               "targets": target_rows, "declared_ranges": family["declared_ranges"],
               "status_counts": dict(statuses), "contract": contract(family),
               "source_sheet": "source-sheet.png", "source_directory": "sources/",
               "output_directory": "generated/", "candidate_manifest": "candidate.json"}
        if family.get("terrain_set"):
            job["terrain_set"] = family["terrain_set"]
        if candidate_error:
            job["candidate_error"] = candidate_error
        if coordinator_review:
            job["coordinator_review"] = coordinator_review
        write_json(directory / "job.json", job)
        fcntl.flock(job_lock, fcntl.LOCK_UN)
        job_lock.close()
        jobs.append({"job_id": family["id"], "name": family["name"],
                     "category": family["category"], "kind": family["kind"], "owner": owner,
                     "target_count": len(target_rows), "status_counts": dict(statuses),
                     "job_file": family["id"] + "/job.json"})
    native_groups = collections.defaultdict(list)
    for asset, entry in entries.items():
        stem = re.sub(r"\.\d+$", "", Path(entry["path"]).name)
        if stem.endswith("_AGX") or stem.endswith("_FNT"):
            native_groups[stem].append(asset)
    for name, ids in sorted(native_groups.items()):
        kind = "cinematic_delta" if name.endswith("_AGX") else "bitmap_font"
        job_id = f"preserve-{name.lower()}"
        directory = args.jobs / job_id
        directory.mkdir(parents=True, exist_ok=True)
        job_lock = (directory / ".claim.lock").open("a")
        fcntl.flock(job_lock, fcntl.LOCK_EX)
        local = read_json(directory / "job.json", {})
        local_targets = {row["asset"]: row for row in local.get("targets", [])}
        targets = []
        for asset in sorted(ids):
            entry = entries[asset]
            payload = (args.data / entry["path"]).read_bytes()
            identity = f"{asset:05x}"
            old = previous_assets.get(identity, local_targets.get(identity, {}))
            owner = local.get("owner") or old.get("owner")
            status = old.get("status", "missing")
            if owner and status == "missing":
                status = "inprogress"
            row = {"kind": kind, "source_path": entry["path"],
                   "source_sha256": hashlib.sha256(payload).hexdigest(),
                   "job_id": job_id, "family_id": job_id, "owner": owner,
                   "status": status, "remaster_required": False,
                   "preservation_policy": "classic native AGX playback" if kind == "cinematic_delta" else "sharp native bitmap glyphs; no AI replacement typography",
                   "renderer": old.get("renderer", {"availability": "native_path_pending_review", "evidence": []})}
            if kind == "cinematic_delta":
                row["logical_canvas"] = [320, 200]
            ledger_assets[identity] = row
            targets.append({"asset": identity, **row})
        job = {"format_version": 1, "job_id": job_id, "name": name, "kind": kind,
               "category": "Preserved classic cinematics" if kind == "cinematic_delta" else "Sharp native fonts",
               "owner": local.get("owner"), "targets": targets,
               "contract": {"method": "Preserve every original source payload. Validate checked decoder and complete sequence/glyph playback, palette, timing, transparency and alignment; do not relabel scaling as remastering."}}
        write_json(args.jobs / job_id / "job.json", job)
        fcntl.flock(job_lock, fcntl.LOCK_UN)
        job_lock.close()
        jobs.append({"job_id": job_id, "name": name, "kind": kind,
                     "category": job["category"], "owner": job["owner"], "target_count": len(targets),
                     "job_file": job_id + "/job.json"})
    counts = collections.Counter(row["status"] for row in ledger_assets.values() if row["remaster_required"])
    ledger = {"format_version": 1, "scope": {"picture_targets": len(pictures),
              "distinct_picture_payloads": len(hashes), "exact_payload_alias_targets": len(pictures) - len(hashes),
              "classic_cinematic_delta_targets": sum(row["kind"] == "cinematic_delta" for row in ledger_assets.values()),
              "sharp_bitmap_font_targets": sum(row["kind"] == "bitmap_font" for row in ledger_assets.values()),
              "all_art_targets": len(ledger_assets), "no_unreferenced_picture_exclusions": True},
              "stages": STAGES, "stage_contract": "Every generated candidate stays distinct from review, registration and render reachability. Original-only fallback is temporary for every required picture. Native cinematics/fonts have explicit preservation exceptions, not HD claims.",
              "picture_status_counts": dict(counts), "assets": dict(sorted(ledger_assets.items())), "jobs": jobs}
    write_json(args.ledger, ledger)
    write_json(args.jobs / "index.json", {"format_version": 1, "scope": ledger["scope"], "jobs": jobs})
    queues(args.jobs, jobs, ledger_assets)
    print(json.dumps({"scope": ledger["scope"], "picture_status_counts": dict(counts),
                      "job_counts": dict(collections.Counter(job["category"] for job in jobs))}, indent=2))


def queues(root, jobs, ledger_assets):
    """Disjoint complete-family worker queues; exact source aliases stay together."""
    picture_jobs = [job for job in jobs if job["kind"] not in ["cinematic_delta", "bitmap_font"]
                    and sum(job["status_counts"].get(stage, 0) for stage in ["registered", "renderreachable"]) < job["target_count"]]
    result = []
    assigned = set()
    previous_assignment = {}
    previous_index = read_json(root / "queues/index.json", {})
    for summary in previous_index.get("queues", []):
        previous_queue = read_json(root / summary["file"], {})
        for identity in previous_queue.get("job_ids", []):
            previous_assignment[identity] = summary["queue_id"]

    def emit(name, members, category):
        members.sort(key=lambda job: job["job_id"])
        ids = [job["job_id"] for job in members]
        if any(identity in assigned for identity in ids):
            raise ValueError("worker queues overlap")
        assigned.update(ids)
        queue = {"format_version": 1, "queue_id": name, "category": category,
                 "job_ids": ids, "target_count": sum(job["target_count"] for job in members),
                 "instructions": "Work through this entire queue until every assigned complete family has reviewed candidate artwork. Read each job.json, claim only unowned or your-owned jobs, generate checked source sheets, inspect every original, use built-in imagegen, keep raw outputs/provenance and submit full candidate.json. Do not stop after one image. Never edit global manifest/ledger or another job's art. Record failures and continue independent jobs; registered art and existing foreign owners are not yours to regenerate. Only coordinator-reviewed complete families are registered. Terrain edges/state pairs require contextual QA.",
                 "source_sheet_command": "python3 RustRaptor/tools/hd_job_queue.py --data data --sheet-job JOB_ID",
                 "claim_command": "python3 RustRaptor/tools/hd_job_queue.py --data data --claim-job JOB_ID --owner /root/YOUR_AGENT",
                 "job_directory": "data/hd/jobs/JOB_ID", "candidate_path": "data/hd/jobs/JOB_ID/candidate.json"}
        write_json(root / "queues" / (name + ".json"), queue)
        result.append({"queue_id": name, "file": "queues/" + name + ".json",
                       "jobs": len(ids), "targets": queue["target_count"]})

    def balanced(category, prefix, count):
        selected = [job for job in picture_jobs if job["category"] == category]
        parents = {job["job_id"]: job["job_id"] for job in selected}
        def find(identity):
            while parents[identity] != identity:
                parents[identity] = parents[parents[identity]]
                identity = parents[identity]
            return identity
        source_owners = collections.defaultdict(set)
        for row in ledger_assets.values():
            if row.get("job_id") in parents:
                source_owners[row["source_sha256"]].add(row["job_id"])
        for owners in source_owners.values():
            owners = sorted(owners)
            for identity in owners[1:]:
                parents[find(identity)] = find(owners[0])
        bundles = collections.defaultdict(list)
        for job in selected:
            bundles[find(job["job_id"])].append(job)
        bins = [[] for _ in range(count)]
        for bundle in sorted(bundles.values(), key=lambda members: -sum(job["target_count"] for job in members)):
            previous_bins = {previous_assignment[job["job_id"]] for job in bundle if job["job_id"] in previous_assignment}
            if len(previous_bins) > 1:
                raise ValueError("source-alias bundle has conflicting frozen queue owners")
            if previous_bins:
                previous_bin = next(iter(previous_bins))
                expected = [f"{prefix}-{index+1:02d}" for index in range(count)]
                if previous_bin not in expected:
                    raise ValueError("frozen queue category changed")
                at = expected.index(previous_bin)
            else:
                at = min(range(count), key=lambda index: sum(job["target_count"] for job in bins[index]))
            bins[at].extend(bundle)
        for index, members in enumerate(bins):
            emit(f"{prefix}-{index+1:02d}", members, category)

    balanced("Enemies and ground objects", "enemies", 3)
    balanced("Bosses", "bosses", 3)
    emit("equipment-interface", [job for job in picture_jobs if job["category"] in ["Equipment and pickups", "Menus, portraits, HUD and other pictures"]], "Equipment, HUD, portraits and retained other artwork")
    emit("effects-projectiles", [job for job in picture_jobs if job["category"] in ["Explosions and effects", "Player and enemy projectiles"]], "Effects and projectiles")
    for index in range(1, 5):
        selected = []
        for job in picture_jobs:
            if job["category"] == "Terrain":
                full = read_json(root / job["job_file"])
                if full.get("terrain_set") == f"Terrain set {index}":
                    selected.append(job)
        emit(f"terrain-set-{index}", selected, f"Terrain set {index}")
    for job in picture_jobs:
        if job["category"] == "Player banking":
            emit(job["job_id"], [job], "Player banking")
    if assigned != {job["job_id"] for job in picture_jobs}:
        raise ValueError("worker queues omit required picture jobs")
    write_json(root / "queues/index.json", {"format_version": 1, "queues": result,
               "disjoint_job_ownership": True, "all_missing_picture_jobs_queued": True,
               "partition_frozen_across_registration_updates": True})


def source_sheet(args):
    directory = args.jobs / args.sheet_job
    job = read_json(directory / "job.json")
    if job is None or job["kind"] in ["bitmap_font", "cinematic_delta"]:
        raise ValueError("source sheets require an existing picture job")
    entries = index_entries(args.data)
    palettes = {}
    for entry in entries.values():
        name = Path(entry["path"]).name
        if name in ["PALETTE_DAT", "POGPAL_DAT", "CYGPAL_DAT", "TAIPAL_DAT"]:
            palettes[name] = checked_palette((args.data / entry["path"]).read_bytes())
    sources = directory / "sources"
    sources.mkdir(parents=True, exist_ok=True)
    prepared = []
    decoded = {}

    def load_source(asset):
        if asset not in decoded:
            path = entries[int(asset, 16)]["path"]
            decoded[asset] = decode(args.data / path, palettes[source_palette_name(path)])
        return decoded[asset]
    for target in job["targets"]:
        path = args.data / target["source_path"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != target["source_sha256"]:
            raise ValueError(f"source changed at {target['asset']}")
        image = load_source(target["asset"])
        if list(image.size) != target["logical_canvas"]:
            raise ValueError(f"canvas changed at {target['asset']}")
        image.save(sources / (target["asset"] + ".png"))
        scale = max(1, min(8, 224 // max(image.size)))
        prepared.append((target, image.resize((image.width * scale, image.height * scale), Image.Resampling.NEAREST)))
    columns = min(4, len(prepared))
    cell_width = max(image.width for _, image in prepared) + 24
    cell_height = max(image.height for _, image in prepared) + 48
    sheet = Image.new("RGB", (columns * cell_width, math.ceil(len(prepared) / columns) * cell_height), (20, 28, 38))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=12)
    for index, (target, image) in enumerate(prepared):
        x, y = index % columns * cell_width, index // columns * cell_height
        draw.text((x + 8, y + 6), target["asset"] + " " + Path(target["source_path"]).name, font=font, fill="white")
        draw.text((x + 8, y + 23), f"{target['logical_canvas'][0]}x{target['logical_canvas'][1]} original source", font=font, fill=(170, 185, 205))
        sheet.paste(image, (x + 8, y + 42), image.getchannel("A"))
    sheet.save(directory / "source-sheet.png")
    if job["kind"] == "contextual_terrain_shard":
        contexts = directory / "contexts"
        contexts.mkdir(exist_ok=True)
        context_images = []
        gray_palette = [(index, index, index) for index in range(256)]
        edge_profiles = {}
        for target in job["targets"]:
            encoded = decode(args.data / target["source_path"], gray_palette)
            width, height = encoded.size
            value = lambda x, y: encoded.getpixel((x, y))[0]
            edge_profiles[target["asset"]] = {
                "north": [value(x, 0) for x in range(width)],
                "south": [value(x, height - 1) for x in range(width)],
                "west": [value(0, y) for y in range(height)],
                "east": [value(width - 1, y) for y in range(height)]}
            for number, sample in enumerate(target.get("terrain_context", {}).get("samples", [])):
                patch = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
                for at, identity in enumerate(sample["target_3x3"]):
                    if identity:
                        tile = load_source(identity)
                        if tile.size != (32, 32):
                            raise ValueError("terrain context requires canonical 32×32 tiles")
                        patch.paste(tile, (at % 3 * 32, at // 3 * 32))
                patch.save(contexts / f"{target['asset']}-{number}.png")
                if number == 0:
                    context_images.append((target["asset"], patch.resize((192, 192), Image.Resampling.NEAREST)))
        write_json(contexts / "native-edge-palette-indices.json", edge_profiles)
        if context_images:
            context_sheet = Image.new("RGB", (4 * 208, math.ceil(len(context_images) / 4) * 224), (20, 28, 38))
            context_draw = ImageDraw.Draw(context_sheet)
            for at, (identity, patch) in enumerate(context_images):
                x, y = at % 4 * 208, at // 4 * 224
                context_draw.text((x + 8, y + 4), identity + " target at center", fill="white", font=font)
                context_sheet.paste(patch, (x + 8, y + 24), patch.getchannel("A"))
            context_sheet.save(contexts / "neighbor-context-sheet.png")
    print(directory / "source-sheet.png")


def claim(args):
    if not args.owner:
        raise ValueError("claim-job requires --owner")
    if Path(args.claim_job).name != args.claim_job:
        raise ValueError("job ID must be a direct directory name")
    directory = args.jobs / args.claim_job
    path = directory / "job.json"
    if not path.is_file():
        raise ValueError("unknown job ID")
    with (directory / ".claim.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        job = read_json(path)
        if job.get("owner") not in [None, args.owner]:
            raise ValueError(f"job already belongs to {job['owner']}")
        job["owner"] = args.owner
        for target in job["targets"]:
            if target.get("status") == "missing":
                target["status"] = "inprogress"
        job["status_counts"] = dict(collections.Counter(target.get("status", "missing") for target in job["targets"]))
        write_json(path, job)
    # Workers claim only their local job. The coordinator rebuilds global
    # metadata serially so independent worker claims cannot race the ledger.
    print(json.dumps({"job_id": args.claim_job, "owner": args.owner,
                      "status_counts": job["status_counts"]}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    project = Path(__file__).resolve().parents[1]
    parser.add_argument("--data", type=Path, default=project.parent / "data")
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--runtime", type=Path)
    parser.add_argument("--jobs", type=Path)
    parser.add_argument("--ledger", type=Path, default=project / "docs/hd-completion.json")
    parser.add_argument("--terrain-batch", type=int, default=16)
    parser.add_argument("--sheet-job", help="Prepare checked original reference PNGs and a contact sheet for one job")
    parser.add_argument("--claim-job", help="Atomically claim one local job; does not rewrite the global ledger")
    parser.add_argument("--owner", help="Stable agent/task name for claim-job")
    args = parser.parse_args()
    args.audit = args.audit or args.data / "hd/coverage-audit.json"
    args.runtime = args.runtime or args.data / "hd/runtime-content-audit.json"
    args.jobs = args.jobs or args.data / "hd/jobs"
    if not 1 <= args.terrain_batch <= 64:
        parser.error("terrain-batch must be 1..64")
    if args.claim_job:
        claim(args)
    elif args.sheet_job:
        source_sheet(args)
    else:
        build(args)


if __name__ == "__main__":
    main()
