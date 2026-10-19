"""Intrinsic admission for complete, currently dormant Original enemy animations.

This is a Source/receipt validator, not a renderer or a secret-mode implementation.
Ordinary retained-art and contextual Terrain approval paths do not use it.
"""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import struct
from types import SimpleNamespace

from hd_art_audit import checked_palette, validate_hd_frame
from hd_art_source import decode
from hd_frame_policy import _indices
from hd_candidate_review import binding_digest, proposal_frames

DORMANT_ENEMY_SCOPE = "catalog_dormant_original_enemy_animation"
DORMANT_ENEMY_TRACE = "original-dormant-enemy-animation-source-v1"
DORMANT_ENEMY_MATERIAL = "original-dormant-enemy-animation-material-v1"
MAX_PHASES = 96
_MAX_FILE_BYTES = 64 * 1024 * 1024
# These exact current Source implementations preserve raw MAP difficulty and
# enable only normal codes3/4/5. A gameplay change requires a new reviewed gate.
SUPPORTED_GATE_SOURCES = {
    "src/assets.rs": "44515745330b47a6a99761c449225c67cbee95c7b1f9d653d919ed09032b1beb",
    "src/content.rs": "80021611102f22b3152164e88a3ee7ecc8c16e9b3a4563551a047c089f2ba7d2",
    "src/simulation.rs": "2537120f280a1cfcfcc73a42a4103a4435ba8aeb98e69c87fde3b885b97a9925",
}


def _fail(message):
    raise ValueError("dormant enemy animation: " + message)


def _read(root, record, route=None, source=False):
    if not isinstance(record, dict) or not isinstance(record.get("path"), str):
        _fail("missing portable hash-bound file")
    text = record["path"]
    relative = PurePosixPath(text)
    if (relative.is_absolute() or not relative.parts or
            any(p in {".", ".."} for p in relative.parts) or
            relative.as_posix() != text or "\\" in text or ":" in text or
            route is not None and text != route or
            re.fullmatch("[0-9a-f]{64}", str(record.get("sha256", ""))) is None):
        _fail("unsafe or mismatched portable file pin")
    path = root.resolve()
    for part in relative.parts:
        path = path / part
        if path.is_symlink():
            _fail("symlink in proof or Source route")
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_size > _MAX_FILE_BYTES:
        _fail("file must be bounded and regular")
    flags = (os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0) |
             getattr(os, "O_NONBLOCK", 0))
    identity = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_size, s.st_mtime_ns)
    with os.fdopen(os.open(path, flags), "rb") as stream:
        opened = os.fstat(stream.fileno())
        if (not stat.S_ISREG(opened.st_mode) or opened.st_size > _MAX_FILE_BYTES or
                identity(before) != identity(opened)):
            _fail("opened file must remain bounded, regular and unchanged")
        payload = stream.read(_MAX_FILE_BYTES + 1)
        if len(payload) > _MAX_FILE_BYTES or stream.read(1):
            _fail("file exceeds bounded read or did not reach EOF")
        finished = os.fstat(stream.fileno())
    if (identity(before) != identity(opened) or identity(before) != identity(finished)
            or identity(before) != identity(path.lstat())
            or hashlib.sha256(payload).hexdigest() != record["sha256"]):
        _fail("file changed or hash differs")
    if source and (type(record.get("bytes")) is not int or record["bytes"] != len(payload)):
        _fail("Source byte count differs")
    return payload


def _proof(root, record):
    payload = _read(root, record)
    if len(payload) > 8 * 1024 * 1024:
        _fail("proof JSON exceeds8MiB")
    value = json.loads(payload)
    if not isinstance(value, dict):
        _fail("proof must contain an object")
    return value


def approved_dormant_enemy_animation(root, project, candidate, job, review, rows, qa):
    """Recompute Original family/caller facts, then require explicit intrinsic authority."""
    declaration = review.get("retained_original_detail_review", {})
    sequences = candidate.get("sequences", [])
    if (candidate.get("approval_scope") != DORMANT_ENEMY_SCOPE or
            declaration.get("hybrid_review_scope") != DORMANT_ENEMY_SCOPE or
            job.get("category") != "Enemies and ground objects" or
            candidate.get("category") != job.get("category") or candidate.get("kind") != "complete_family" or
            job.get("kind") != "complete_family" or candidate.get("complete_family") is not True or
            candidate.get("complete_standalone_selection") or len(sequences) != 1):
        _fail("requires one complete Original enemy animation, never singleton slices")
    sequence = sequences[0]
    base, count = sequence.get("base_asset"), sequence.get("frame_count")
    if (type(base) is not int or type(count) is not int or not 2 <= count <= MAX_PHASES or not 0 <= base <= 0xfffff-count+1 or
            set(rows) != {f"{base+i:05x}" for i in range(count)} or
            len(sequence.get("frames", [])) != count or
            any(type(f.get("frame")) is not int for f in sequence["frames"]) or
            [f.get("frame") for f in sequence["frames"]] != list(range(count))):
        _fail("phase inventory must be complete, contiguous and ordered")
    if (declaration.get("hybrid_allscale_and_genuine_context_independent_review") is not False or
            declaration.get("catalog_dormant_no_genuine_runtime_context_claimed") is not True or
            declaration.get("catalog_only_independent_whole_material_and_allscale_review") is not True):
        _fail("intrinsic-only declaration cannot claim genuine gameplay context")
    assets = sorted(rows)
    if any(frame.get("palette_constraint") is not None for frame in rows.values()):
        _fail("palette constraints retain their ordinary genuine-context approval requirement")
    targets = {t["asset"]: t for t in job.get("targets", [])}
    if len(targets) != len(job.get("targets", [])) or set(targets) != set(rows):
        _fail("Original job inventory differs")
    trace_ref = declaration.get("dormant_source_trace")
    trace = _proof(root, trace_ref)
    if (trace.get("contract_version") != DORMANT_ENEMY_TRACE or
            trace.get("no_genuine_original_runtime_context_claimed") is not True):
        _fail("explicit dormant Source trace required; no fabricated context")
    index = _read(project, trace.get("catalogue"), "data/INDEX", True)
    entries, names = {}, {}
    for line in index.decode().splitlines():
        if not line.strip():
            continue
        parts = line.split()
        if (len(parts) != 3 or re.fullmatch("[0-9a-fA-F]{1,8}", parts[0]) is None or
                not parts[1].isdigit() or int(parts[0], 16) in entries):
            _fail("invalid or duplicate INDEX record")
        identity = int(parts[0], 16)
        relative = PurePosixPath(parts[2])
        if relative.is_absolute() or ".." in relative.parts or relative.as_posix() != parts[2] or "\\" in parts[2]:
            _fail("unsafe INDEX route")
        entries[identity] = (int(parts[1]), "data/" + parts[2])
        names.setdefault(relative.name, []).append(identity)

    def named(name):
        ids = names.get(name, [])
        if len(ids) != 1:
            _fail("missing or ambiguous named Original Source")
        return ids[0], entries[ids[0]]

    family = trace.get("family", {})
    name = family.get("name")
    if (not isinstance(name, str) or re.fullmatch("[A-Za-z0-9_]{1,15}", name) is None or
            named(name)[0] != base or family.get("assets") != assets or
            type(family.get("frame_count")) is not int or family["frame_count"] != count):
        _fail("named Original family differs")
    named_family = {identity for stem, ids in names.items()
                    if re.fullmatch(re.escape(name) + r"(?:\.[0-9]+)?", stem)
                    for identity in ids}
    if named_family != {base+i for i in range(count)}:
        _fail("Original named family has omitted or additional phases")
    phases = trace.get("phases", [])
    if not isinstance(phases, list) or [p.get("asset") for p in phases] != assets:
        _fail("complete phase Source records required")
    palette_id, (palette_size, palette_route) = named("PALETTE_DAT")
    palette = _read(project, trace.get("palette"), palette_route, True)
    if len(palette) != palette_size:
        _fail("catalogue palette size differs")
    colors = checked_palette(palette)
    source_reserved, source_visible = {}, {}
    for i, record in enumerate(phases):
        asset = assets[i]
        identity, (size, route) = named(name if i == 0 else f"{name}.{i}")
        target, frame = targets[asset], rows[asset]
        payload = _read(project, record.get("Source"), route, True)
        if len(payload) < 20 or len(payload) != size or identity != base+i:
            _fail("phase Source size or ID differs")
        header = list(struct.unpack_from("<5i", payload))
        claimed = record.get("header_le_i32")
        if (not isinstance(claimed, list) or any(type(v) is not int for v in claimed) or
                claimed != header or header[0] not in (0, 1) or
                target.get("source_path") != route.removeprefix("data/") or
                target.get("source_sha256") != record["Source"]["sha256"] or
                json.dumps(target.get("logical_canvas")) != json.dumps(header[3:]) or
                json.dumps(target.get("origin")) != "[0, 0]" or json.dumps(frame.get("origin")) != "[0, 0]" or
                target.get("source_palette") != "PALETTE_DAT" or
                target.get("source_palette_sha256") != trace["palette"]["sha256"]):
            _fail("complete phase header, canvas, palette or Source binding differs")
        validate_hd_frame(root, frame, payload, decode(SimpleNamespace(read_bytes=lambda: payload), colors))
        _, _, indices = _indices(payload)
        source_reserved[asset] = [indices.count(i) for i in range(240, 256)]
        source_visible[asset] = sum(i < 256 for i in indices)

    libraries = trace.get("sprite_libraries", [])
    if not isinstance(libraries, list) or len(libraries) != 4:
        _fail("all four Original SPRITE libraries required")
    callers, record_total = [], 0
    for game, record in enumerate(libraries):
        _, (size, route) = named(f"SPRITE{game+1}_ITM")
        payload = _read(project, record, route, True)
        if not payload or len(payload) != size or len(payload) % 528:
            _fail("truncated Original SPRITE library")
        record_total += len(payload) // 528
        for ordinal in range(len(payload) // 528):
            raw = payload[ordinal*528:(ordinal+1)*528]
            stem = raw[:16].split(b"\0", 1)[0].decode()
            if stem not in names:
                continue
            start, _ = named(stem)
            frames = max(1, struct.unpack_from("<i", raw, 44)[0])
            if start < base+count and base < start+frames:
                if start != base or frames != count or stem != name or struct.unpack_from("<i", raw, 64)[0] != 0:
                    _fail("SPRITE library contains a partial, aliased or boss family")
                callers.append(dict(game=game, ordinal=ordinal, name=stem, base_asset=f"{base:05x}",
                                    frame_count=frames, enemy_id=f"base:enemy_{game}_{ordinal}",
                                    record_sha256=hashlib.sha256(raw).hexdigest()))
    if not callers or trace.get("sprite_callers") != callers:
        _fail("exact complete-family SPRITE callers differ")

    source_records = trace.get("current_rust_sources", [])
    current_paths = {p.relative_to(project).as_posix() for p in (project / "src").rglob("*.rs")}
    if (not isinstance(source_records, list) or len(source_records) != len(current_paths) or
            {r.get("path") for r in source_records} != current_paths or len(current_paths) > 256):
        _fail("complete current Rust Source inventory required")
    current_sources = {}
    direct = re.compile("|".join([re.escape(name)] + [re.escape(c["enemy_id"]) for c in callers] +
                        [rf"\b(?:0x)?{asset}\b|\b{int(asset,16)}\b" for asset in assets]), re.I)
    for record in source_records:
        payload = _read(project, record, record["path"], True)
        text = payload.decode()
        if re.search(r"\b(?:secret|bday)\w*\b", text, re.I) or direct.search(text):
            _fail("current Rust has a secret activation or direct family caller requiring review")
        current_sources[record["path"]] = record["sha256"]
    if any(current_sources.get(path) != sha for path, sha in SUPPORTED_GATE_SOURCES.items()):
        _fail("current raw-decode, registry or normal-difficulty gate Source changed")
    measured_sources = qa.get("current_game_source_sha256", qa.get("actual_sourceG2_source18_sha256"))
    if (measured_sources != current_sources or qa.get("source_newer_than_library") is not False or
            qa.get("any_game_source_newer_than_library") is not False):
        _fail("actual current QA does not bind all current Rust Source bytes")
    library = trace.get("current_library", {})
    route = qa.get("library", "")
    if (not route.startswith("target/") or library.get("path") != route or
            library.get("sha256") != qa.get("library_sha256")):
        _fail("current compiled library differs")
    _read(project, library, route, True)
    modified = (project / route).stat().st_mtime_ns
    if (type(qa.get("library_modified_ns")) is not int or modified != qa["library_modified_ns"] or
            any((project / path).stat().st_mtime_ns > modified for path in current_paths)):
        _fail("current compiled library is older than a game Source")

    expected_maps = [named(f"MAP{wave}G{sector}_MAP")[1][1]
                     for sector in range(1, 4) for wave in range(1, 10)]
    maps = trace.get("maps", [])
    if not isinstance(maps, list) or len(maps) != 27 or [r.get("path") for r in maps] != expected_maps:
        _fail("all27 distinct ordered Original MAP records required")
    declarations, spawn_total = [], 0
    target_callers = {(c["game"], c["ordinal"]) for c in callers}
    for record in maps:
        route = record["path"]
        _, (size, _) = named(PurePosixPath(route).name)
        payload = _read(project, record, route, True)
        if len(payload) < 5412:
            _fail("truncated Original MAP")
        length, offset, number = struct.unpack_from("<3i", payload)
        if length != size or length != len(payload) or offset != 5412 or not 0 <= number < 65536 or 5412+24*number > length:
            _fail("invalid Original MAP header")
        for tile in range(1350):
            flat, game = struct.unpack_from("<hh", payload, 12+4*tile)
            if flat < 0 or not 0 <= game < 4:
                _fail("invalid Original MAP layout")
        spawn_total += number
        for ordinal in range(number):
            location = 5412+24*ordinal
            fields = list(struct.unpack_from("<6i", payload, location))
            link, lib, x, row, game, difficulty = fields
            if lib < 0 or not 0 <= game < 4:
                _fail("invalid Original MAP spawn reference")
            if (game, lib) not in target_callers:
                continue
            enabled = [difficulty == 3 or difficulty == 4 and pilot >= 2 or difficulty == 5 and pilot >= 3
                       for pilot in range(4)]
            if any(enabled) or difficulty not in (0, 1, 2):
                _fail("family has an ordinary or unsupported Original MAP caller")
            declarations.append(dict(map=route, ordinal=ordinal, byte_offset=location, fields=fields,
                                     raw_bytes_hex=payload[location:location+24].hex(), enabled_by_pilot_difficulty=enabled))
    counts = dict(maps=27, sprite_libraries=4, sprite_records=record_total,
                  family_library_callers=len(callers), spawn_records=spawn_total,
                  family_map_declarations=len(declarations), ordinary_difficulty_callers=0)
    if (trace.get("map_declarations") != declarations or trace.get("counts") != counts or
            any(type(trace.get("counts", {}).get(k)) is not int for k in counts)):
        _fail("false or incomplete recomputed Original caller census")

    digest = binding_digest(rows)
    cells = {a: f.get("original_detail_cells", []) for a, f in rows.items()}
    sources = {a: f["source_sha256"] for a, f in rows.items()}
    artwork = {f["file"]: qa["artwork_sha256"][f["file"]] for f in rows.values()}
    if candidate.get("artwork_derivation"):
        lineage = _proof(root, candidate["artwork_derivation"])
        raw_records = [p["raw_png"] for p in lineage["parents"]]
    else:
        raw_records = [dict(path=p, sha256=sha) for p, sha in artwork.items()]
    raw_hashes = sorted({record["sha256"] for record in raw_records})
    for record in raw_records:
        if not _read(root, record).startswith(b"\x89PNG\r\n\x1a\n"):
            _fail("genuine parent binding is not a PNG")
    qa_path = review.get("runtime_qa", "")
    qa_record = declaration.get("dormant_actual_allscale_QA", {})
    if qa_record.get("path") != qa_path:
        _fail("actual allscale QA reference differs")
    qa_bytes = _read(root, qa_record)
    qa_sha = hashlib.sha256(qa_bytes).hexdigest()
    if (json.loads(qa_bytes) != qa or type(qa.get("validated_frames")) is not int or
            qa["validated_frames"] != count or qa.get("diagnostics") != [] or
            qa.get("static_card_palette_mode") is not False):
        _fail("current complete-family runtime QA differs")
    for asset in assets:
        reports = [r for r in qa["frames"] if r["asset"] == asset]
        if len(reports) != 1 or [s.get("scale") for s in reports[0]["hd_masks"]] != [1, 2, 3, 4]:
            _fail("current QA omits or duplicates a frame/native scale")
        report = reports[0]
        if (report.get("source_palette") != "PALETTE_DAT" or
                type(report.get("source_mask", {}).get("visible_pixels")) is not int or
                report["source_mask"]["visible_pixels"] != source_visible[asset] or
                json.dumps(report.get("source_mask", {}).get("palette_indices_240_to_255_counts")) !=
                json.dumps(source_reserved[asset])):
            _fail("runtime Source palette/mask differs from actual Original bytes")
        for scale in report["hd_masks"]:
            k = scale.get("scale")
            mask = scale.get("mask", {})
            palette_counts = mask.get("palette_indices_240_to_255_counts")
            visible = mask.get("visible_pixels")
            if (type(k) is not int or type(visible) is not int or not 0 < visible <=
                    rows[asset]["logical_width"] * rows[asset]["logical_height"] * k * k or
                    not isinstance(palette_counts, list) or len(palette_counts) != 16 or
                    any(type(n) is not int or n < 0 for n in palette_counts) or sum(palette_counts) > visible or
                    any(n and not original for n, original in zip(palette_counts, source_reserved[asset]))):
                _fail("native masks or functional palette labels differ")
    peer_ref = declaration.get("dormant_independent_material")
    peer = _proof(root, peer_ref)
    artist, preparer, reviewer = peer.get("artist"), peer.get("preparer"), peer.get("reviewer")
    common = dict(scope=DORMANT_ENEMY_SCOPE, assets=assets, frame_bindings_sha256=digest,
                  source_sha256_by_asset=sources, artwork_sha256=artwork, original_generated_raw_sha256=raw_hashes,
                  retained_cells_by_asset=cells, native_scales=[1, 2, 3, 4],
                  all_frames_whole_viewed=True, no_genuine_original_runtime_context_claimed=True,
                  runtime_qa_sha256=qa_sha)
    if (peer.get("contract_version") != DORMANT_ENEMY_MATERIAL or peer.get("status") != "qualified" or
            any(json.dumps(peer.get(k), sort_keys=True) != json.dumps(v, sort_keys=True) for k, v in common.items()) or
            not all(isinstance(v, str) and v for v in (artist, preparer, reviewer)) or
            reviewer in (artist, preparer) or peer.get("different_from_artist_and_preparer") is not True or
            type(peer.get("qualified_frames")) is not int or peer["qualified_frames"] != count or
            type(peer.get("held_frames")) is not int or peer["held_frames"] != 0 or
            proposal_frames(_proof(root, peer.get("candidate"))) != rows):
        _fail("exact different whole-family intrinsic approval required")
    expected = [dict(asset=a, scale=k, status="qualified", retained_SourceNx_exact=True,
                     retained_samples=len(cells[a])*k*k) for a in assets for k in range(1, 5)]
    if json.dumps(peer.get("native_decisions"), sort_keys=True) != json.dumps(expected, sort_keys=True):
        _fail("independent all-frame/native-scale/Original-retention decisions differ")
    if review.get("independent_review") not in (peer_ref, peer.get("actual_whole_material_review")):
        _fail("coordinator independent citation differs from whole-family authority")
    actual = _proof(root, peer.get("actual_whole_material_review"))
    actual_decisions = actual.get("decisions", [])
    actual_views = [r for r in actual.get("physical_views", []) if r.get("kind") == "native1to4"]
    if (not isinstance(actual_decisions, list) or len(actual_decisions) != count or
            len(actual_views) != count or actual.get("reviewer") != reviewer or
            not str(actual.get("status", "")).startswith("QUALIFIED_") or
            any(re.fullmatch(r"NOT|UNQUALIFIED|HOLD[0-9]*|FAIL(?:ED)?|PENDING", word)
                for word in re.split(r"[^A-Z0-9]+", str(actual.get("status", "")).upper())) or
            {r.get("asset") for r in actual.get("decisions", [])
             if r.get("intrinsic") in ("QUALIFIED", "QUALIFIED_WITH_LIMITS")} != set(assets) or
            {r.get("asset") for r in actual.get("physical_views", [])
             if r.get("kind") == "native1to4" and r.get("whole_frame_personally_viewed") is True} != set(assets)):
        _fail("independent actual whole-native material review differs")
    approval = _proof(root, declaration.get("dormant_root_approval"))
    if (approval.get("status") != "approved" or approval.get("authority_role") != "project_root" or
            not isinstance(approval.get("reviewer"), str) or not approval["reviewer"] or
            approval["reviewer"] in (artist, preparer, reviewer) or
            any(json.dumps(approval.get(k), sort_keys=True) != json.dumps(v, sort_keys=True) for k, v in common.items()) or
            approval.get("source_trace_sha256") != trace_ref["sha256"] or
            approval.get("independent_material_sha256") != peer_ref["sha256"]):
        _fail("explicit Root whole-family intrinsic/no-context approval required")
    return counts
