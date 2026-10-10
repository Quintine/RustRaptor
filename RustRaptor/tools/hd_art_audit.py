#!/usr/bin/env python3
"""Inventory original HD coverage by checked catalog ID, including unnamed pictures.

Writes metadata only. Original pixels are never copied into version control.
"""
import argparse
import collections
import hashlib
import json
import re
import struct
from pathlib import Path
from PIL import Image
from hd_art_source import decode

CATEGORIES = ["Player banking", "Bosses", "Enemies and ground objects", "Player and enemy projectiles", "Explosions and effects", "Equipment and pickups", "Terrain", "Menus, portraits, HUD and other pictures"]

def source_palette_name(path):
    return {"APOGEE_PIC": "POGPAL_DAT", "CYGNUS_PIC": "CYGPAL_DAT", "TAIWARN_PIC": "TAIPAL_DAT"}.get(Path(path).name, "PALETTE_DAT")

def checked_palette(payload):
    if len(payload) != 768:
        raise ValueError("invalid VGA palette")
    return [tuple((min(v, 63) << 2) | (min(v, 63) >> 4) for v in payload[n:n + 3]) for n in range(0, 768, 3)]

def validate_hd_frame(root, frame, payload, picture):
    """Mirror loader checks; artistic approval is deliberately a separate step."""
    if frame["source_sha256"] != hashlib.sha256(payload).hexdigest():
        raise ValueError("original source hash changed")
    if [frame["logical_width"], frame["logical_height"]] != list(picture.size):
        raise ValueError("logical canvas differs from original")
    if frame["origin"] != [0, 0]:
        raise ValueError("original top-left anchor must be [0, 0]")
    relative=Path(frame["file"])
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("artwork path must stay relative to pack directory")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("artwork escapes pack directory")
    if path.stat().st_size > 32 * 1024 * 1024:
        raise ValueError("PNG exceeds 32 MiB")
    with Image.open(path) as source:
        if source.format != "PNG":
            raise ValueError("artwork must be PNG")
        if max(source.size) > 4096 or source.width * source.height > 4_194_304:
            raise ValueError("PNG dimensions exceed runtime limit")
        image = source.convert("RGBA")
    if frame.get("crop") is not None:
        x, y, width, height = frame["crop"]
        if min(x, y) < 0 or min(width, height) <= 0 or x + width > image.width or y + height > image.height:
            raise ValueError("atlas crop exceeds PNG")
        image = image.crop((x, y, x + width, y + height))
    if image.width * picture.height != image.height * picture.width:
        raise ValueError("PNG aspect differs from original canvas")
    if image.width < picture.width * 2 or image.height < picture.height * 2:
        raise ValueError("artwork needs at least twice the logical resolution")
    alpha_min, alpha_max = image.getchannel("A").getextrema()
    if picture.getchannel("A").getextrema()[0] == 0 and alpha_min != 0:
        raise ValueError("transparent original needs a transparent HD background")
    if alpha_max < 128:
        raise ValueError("artwork has no visible pixels")
    # Rust validates the generator-sized PNG/crop, then stores only the largest
    # usable 4x presentation canvas. Keep raw generated pixels on disk.
    return min(image.width, picture.width * 4) * min(image.height, picture.height * 4) * 4


def runtime_references(runtime):
    """Record actual registry aliases and mission-layout references by asset ID."""
    aliases = collections.defaultdict(set)
    reachable = collections.defaultdict(set)
    enemy_ids = {spawn["enemy"] for mission in runtime["missions"].values() for spawn in mission["spawns"]}

    def art_ids(art):
        if not art or art.get("asset") is None:
            return []
        return list(range(art["asset"], art["asset"] + art["frames"]))

    for kind in ["enemies", "weapons", "items"]:
        for identity, definition in runtime[kind].items():
            for asset in art_ids(definition.get("art")):
                aliases[asset].add(identity)
                if kind != "enemies" or identity in enemy_ids:
                    reachable[kind].add(asset)
    for identity, mission in runtime["missions"].items():
        for index, tile in enumerate(mission["tiles"]):
            for kind in ["art", "destroyed"]:
                for asset in art_ids(tile.get(kind)):
                    aliases[asset].add(f"{identity}:tile_{index}:{kind}")
                    if index in mission["layout"]:
                        reachable["terrain"].add(asset)
    return aliases, reachable, enemy_ids


def audit(data, project, runtime_path=None):
    entries = {int(i, 16): (int(n), name) for i, n, name in (line.split() for line in (data / "INDEX").read_text().splitlines() if line.strip())}
    names = {Path(name).name: asset for asset, (_, name) in entries.items()}
    palette_payloads = {name: (data / entries[names[name]][1]).read_bytes() for name in ["PALETTE_DAT", "POGPAL_DAT", "CYGPAL_DAT", "TAIPAL_DAT"] if name in names}
    palettes = {name: checked_palette(payload) for name, payload in palette_payloads.items()}
    groups = collections.defaultdict(list)
    assigned = {}
    def group(category, name, base, count):
        ids = list(range(base, base + max(1, count)))
        groups[category].append({"name": name, "base_asset": f"{base:05x}", "frames": ids})
        for asset in ids:
            assigned.setdefault(asset, category)
    for name in ["LPLAYER_PIC", "DPLAYER_PIC", "FPLAYER_PIC"]:
        group(CATEGORIES[0], name, names[name], 7)
    enemies = []
    for game in range(1, 5):
        payload = (data / entries[names[f"SPRITE{game}_ITM"]][1]).read_bytes()
        if len(payload) % 528:
            raise ValueError("truncated enemy library")
        for offset in range(0, len(payload), 528):
            record = payload[offset:offset + 528]
            name = record[:16].split(b"\0", 1)[0].decode("ascii")
            fields = struct.unpack_from("<26i", record, 16)
            if name in names:
                enemies.append((CATEGORIES[1] if fields[12] else CATEGORIES[2], name, names[name], fields[7]))
    for category, name, base, count in sorted(enemies):
        group(category, name, base, count)
    source = (project / "src/legacy_tables.rs").read_text()
    for category, kind in [(CATEGORIES[3], "LegacyWeapon"), (CATEGORIES[5], "LegacyObject")]:
        # Match records only; the type declaration also contains `LegacyWeapon {`.
        # An unanchored search swallowed the first equipment record as a weapon.
        for body in re.findall(rf"^        {kind} \{{(.*?)^        \}}", source, re.S | re.M):
            values = {key: int(value) for key, value in re.findall(r"(asset|frames): (\d+)", body)}
            if values.get("asset", 0):
                title = re.search(r'name: "([^"]+)"', body).group(1)
                group(category, title, values["asset"], values["frames"])
    for base, count, name in [(0x101d6, 2, "Enemy cannon"), (0x101d4, 2, "Enemy missile"), (0x10241, 4, "Enemy laser"), (0x101d1, 2, "Enemy beam"), (0x1024d, 4, "Enemy coconut"), (0x10251, 1, "Enemy plasma")]:
        group(CATEGORIES[3], name, base, count)
    # Native ANIMS_Register ranges include secondary effects absent from the
    # content registries. Keep the descending smoke subset visible as a distinct
    # animation range; category totals still count each catalog ID only once.
    # Beam impact/power companion arrays come from SHOTS/ESHOTS registration.
    for base, count, name in [
        (0x10164,42,"Ground blast"), (0x1027d,35,"Small ground blast"),
        (0x101e5,12,"Large air explosion"), (0x101d8,13,"Medium air explosion"),
        (0x101fc,14,"Small air explosion"), (0x102a0,16,"Air blast"),
        (0x101ae,12,"Energy effect"), (0x101f5,7,"Person effect"),
        (0x10213,10,"Platoon effect"), (0x10252,26,"Flare"), (0x1026c,17,"Sparkle"),
        (0x10229,4,"Laser impact"), (0x1020a,9,"Smoke"),
        (0x1020e,5,"Descending smoke subset"), (0x1022d,4,"Smoke trail"),
        (0x1018e,14,"Lightning and energy grab"), (0x1019c,9,"Blue sparks"),
        (0x101a5,9,"Orange sparks"), (0x101c7,4,"Muzzle flash and casings"),
        (0x10249,4,"Super shield glow"),
        (0x10225,4,"Pickup light-mask glow"),
        (0x10239,4,"Death ray power companion"),
        (0x1023d,4,"Laser power companion"),
        (0x101f1,4,"Death ray hit companion"),
        (0x10245,4,"Enemy laser power companion"),
    ]:
        group(CATEGORIES[4], name, base, count)
        if base == 0x10225:
            groups[CATEGORIES[4]][-1]["render_semantics"] = "Native pickup light-table alpha mask: RGB is ignored and each nontransparent pixel applies one light-table pass. Generate genuine highresolution source-faithful alpha shape/edges, not a painted colored glow. Runtime Canvas::shade supports this HD path."
    for game in range(1,5):
        start, end = names[f"STARTG{game}TILES"] + 1, names[f"ENDG{game}TILES"]
        group(CATEGORIES[6], f"Terrain set {game}", start, end - start)
    supplied = {}
    hd_errors = []
    active_sequences = []
    manifest_path = data / "hd/hd.json"
    if manifest_path.exists():
        manifest_bytes = manifest_path.read_bytes()
        if len(manifest_bytes) > 8 * 1024 * 1024:
            raise ValueError("HD metadata exceeds 8 MiB")
        manifest = json.loads(manifest_bytes)
        if set(manifest) - {"format_version","name","description","sequences"}:
            raise ValueError("unknown HD manifest fields")
        if manifest.get("format_version") != 1 or len(manifest["sequences"]) > 8192:
            raise ValueError("HD pack has invalid format or sequence limit")
        for sequence in manifest["sequences"]:
            if set(sequence) - {"name","base_asset","frame_count","frames"}:
                raise ValueError("unknown HD sequence fields")
            active_sequences.append({"name":sequence["name"],"base_asset":f"{sequence['base_asset']:05x}","frame_count":sequence["frame_count"],"supplied_frames":len(sequence["frames"]),"valid_frames":0})
            if not 1 <= sequence["frame_count"] <= 512 or len(sequence["frames"]) > sequence["frame_count"]:
                raise ValueError("HD pack has invalid frame count")
            for frame in sequence["frames"]:
                if set(frame) - {"frame","file","logical_width","logical_height","origin","source_sha256","crop"}:
                    raise ValueError("unknown HD frame fields")
                asset = sequence["base_asset"] + frame["frame"]
                if not 0 <= frame["frame"] < sequence["frame_count"] or asset in supplied:
                    raise ValueError("HD pack has duplicate ID or invalid frame index")
                supplied[asset] = frame
                if len(supplied) > 16384:
                    raise ValueError("HD pack exceeds 16,384 supplied IDs")
    runtime_path = runtime_path or data / "hd/runtime-content-audit.json"
    runtime = json.loads(runtime_path.read_text()) if runtime_path.is_file() else None
    aliases, reachable, enemy_ids = runtime_references(runtime) if runtime else ({}, {}, set())
    pictures = []
    hd_bytes = 0
    valid_frame_bytes = {}
    cinematics = collections.Counter()
    fonts = []
    for asset, (size, name) in entries.items():
        path = data / name
        if path.stat().st_size != size:
            raise ValueError(f"INDEX size mismatch {asset:05x}")
        stem = re.sub(r"\.\d+$", "", Path(name).name)
        if stem.endswith("_AGX"):
            cinematics[stem] += 1
            continue
        if stem.endswith("_FNT"):
            fonts.append({"asset": f"{asset:05x}", "name": stem})
            continue
        if size < 20:
            continue
        payload = path.read_bytes()
        if struct.unpack_from("<i", payload)[0] not in [0,1]:
            continue
        try:
            palette_name = source_palette_name(name)
            picture = decode(path, palettes[palette_name])
        except (ValueError, struct.error, IndexError):
            continue
        frame = supplied.get(asset)
        accepted = False
        if frame:
            try:
                frame_bytes = validate_hd_frame(data / "hd", frame, payload, picture)
                valid_frame_bytes[asset] = frame_bytes
                accepted = True
            except (ValueError, OSError, KeyError) as error:
                hd_errors.append({"asset": f"{asset:05x}", "error": str(error)})
        pictures.append({"asset": f"{asset:05x}", "path":name, "category":assigned.get(asset,CATEGORIES[7]), "logical_canvas":list(picture.size), "header_options":list(struct.unpack_from("<ii",payload,4)), "source_sha256":hashlib.sha256(payload).hexdigest(), "source_palette":palette_name,"source_palette_sha256":hashlib.sha256(palette_payloads[palette_name]).hexdigest(), "decoded_rgba_sha256":hashlib.sha256(picture.tobytes()).hexdigest(), "registry_aliases":sorted(aliases.get(asset, [])), "registry_or_layout_referenced":any(asset in ids for ids in reachable.values()), "hd":accepted})
    picture_rows={int(row["asset"],16):row for row in pictures}
    # Streaming caches evict resident pixels without dropping registrations.
    # Report the full 4x decoded footprint as an estimate, not an admission cap.
    for asset in supplied:
        if asset not in picture_rows:
            hd_errors.append({"asset":f"{asset:05x}","error":"HD metadata targets a missing or non-picture catalog entry"})
        elif asset in valid_frame_bytes:
            frame_bytes=valid_frame_bytes[asset]
            hd_bytes += frame_bytes
    crosscheck = {"available": runtime is not None}
    if runtime:
        local = {p["asset"]: p["logical_canvas"] for p in pictures}
        engine = {p["asset"]: p["canvas"] for p in runtime["pictures"]}
        if local != engine:
            raise ValueError("Python picture audit differs from checked Rust Sprite decoder")
        if any(assigned.get(asset) != CATEGORIES[3] for asset in reachable.get("weapons",set())):
            raise ValueError("registry weapon artwork is missing from projectile classification")
        if any(assigned.get(asset) != CATEGORIES[5] for asset in reachable.get("items",set())):
            raise ValueError("registry equipment artwork is missing from item classification")
        enemy_sequences={(enemy["art"]["asset"],enemy["art"]["frames"]) for enemy in runtime["enemies"].values()}
        used_enemy_sequences={(runtime["enemies"][identity]["art"]["asset"],runtime["enemies"][identity]["art"]["frames"]) for identity in enemy_ids}
        crosscheck.update({"picture_ids_and_dimensions_match":True,"registry_weapon_and_item_categories_match":True,"enemy_definitions":len(runtime["enemies"]),"mission_referenced_enemy_definitions":len(enemy_ids),"unique_enemy_art_sequences":len(enemy_sequences),"mission_referenced_enemy_art_sequences":len(used_enemy_sequences),"missions":len(runtime["missions"]),"reachable_asset_frames":{kind:len(ids) for kind,ids in reachable.items()}})
    terrain_rows = [p for p in pictures if p["category"] == CATEGORIES[6]]
    active_ids = {int(row["asset"],16) for row in pictures if row["hd"]}
    for sequence in active_sequences:
        sequence["valid_frames"] = sum((int(sequence["base_asset"],16)+frame) in active_ids for frame in range(sequence["frame_count"]))
    provenance_path=data / "hd/provenance.json"
    provenance=json.loads(provenance_path.read_text()) if provenance_path.exists() else {}
    jobs=provenance.get("jobs",[])
    source_duplicates = collections.defaultdict(list)
    for row in terrain_rows:
        source_duplicates[row["source_sha256"]].append(row["asset"])
    capabilities = provenance.get("renderer_capabilities", {})
    terrain_renderer = capabilities.get("terrain", {})
    terrain = {"catalog_frames":len(terrain_rows),"unique_payload_hashes":len(source_duplicates),"unique_decoded_rgba_hashes":len({p["decoded_rgba_sha256"] for p in terrain_rows}),"mission_referenced_frames":len(reachable.get("terrain",set())) if runtime else None,"duplicate_payload_groups":[ids for ids in source_duplicates.values() if len(ids)>1],"runtime_hd_composition_supported":terrain_renderer.get("validated", False),"renderer_evidence":terrain_renderer.get("evidence", [])}
    summaries=[]
    for category in CATEGORIES:
        rows=[p for p in pictures if p["category"]==category]
        unique_groups = {(g["base_asset"],len(g["frames"])) for g in groups[category]}
        summaries.append({"category":category,"pictures":len(rows),"hd":sum(p["hd"] for p in rows),"missing":sum(not p["hd"] for p in rows),"registry_or_layout_referenced_frames":sum(p["registry_or_layout_referenced"] for p in rows) if runtime else None,"declared_sequences_or_sets":len(unique_groups) if category!=CATEGORIES[7] else None})
    return {"format_version":2,"catalog_entries":len(entries),"pictures":len(pictures),"accepted_hd":sum(p["hd"] for p in pictures),"missing_hd":sum(not p["hd"] for p in pictures),"active_sequences":active_sequences,"jobs":jobs,"hd_estimated_4x_rgba_bytes":hd_bytes,"hd_runtime_cache_budgets":{"atlas_mib":32,"rgba_mib":32,"indexed_mib":32,"source_palette_labels_mib":32,"derived_disk_mib":512},"hd_frame_errors":hd_errors,"runtime_crosscheck":crosscheck,"terrain":terrain,"by_category":summaries,"by_folder":dict(collections.Counter(Path(p["path"]).parts[0] for p in pictures)),"cinematics":{"sequences":dict(cinematics),"frames":sum(cinematics.values()),"hd":0},"fonts":fonts,"sequences":dict(groups),"assets":pictures}

def markdown(report):
    lines=["# Original artwork HD backlog","",f"The checked catalog contains **{report['pictures']:,} standalone picture frames**. The active local HD pack supplies **{report['accepted_hd']:,}**; **{report['missing_hd']:,}** have no registered HD replacement. These counts include unnamed graphics outside `sprites/`. Scale2x/3x/4x filtering is crisp scaling, not a newly authored HD replacement. Authored mod SD/HD art is separate from this original-catalog audit.","","| Category | Picture frames | Registered HD | Missing HD | Declared sequences / terrain sets |","| --- | ---: | ---: | ---: | ---: |"]
    for row in report["by_category"]:
        lines.append(f"| {row['category']} | {row['pictures']:,} | {row['hd']:,} | {row['missing']:,} | {row['declared_sequences_or_sets'] if row['declared_sequences_or_sets'] is not None else 'mixed static / animated'} |")
    lines.extend(["","## Registered pack and generation jobs","","Only registered frames passing canvas, source-hash, PNG and alpha checks count as registered HD. This is loader coverage, not proof that every original animation event is reachable in the current renderer. A generated image or successful still-image review does not complete an animated family. The optional pack remains disabled by default.","","| Registered sequence | Asset base | Valid / complete frames |","| --- | --- | ---: |"])
    for sequence in report["active_sequences"]:
        lines.append(f"| {sequence['name']} | `0x{sequence['base_asset']}` | {sequence['valid_frames']} / {sequence['frame_count']} |")
    if report["jobs"]:
        lines.extend(["","| Generation job | Status |","| --- | --- |"])
        for job in report["jobs"]:
            lines.append(f"| {job['name']} | {job['status']} |")
    lines.extend(["",f"The catalog also contains **{report['cinematics']['frames']} AGX cinematic delta frames in {len(report['cinematics']['sequences'])} sequences** and **{len(report['fonts'])} bitmap fonts**. These have explicit native-art preservation policies: keep the classic cinematics and sharp original glyphs, validate complete playback/alignment, and never count them as generated HD replacements. The AGX frames are separate from standalone pictures.","","## Sequence priorities","","1. Keep all light/dark-player banking poses and firing-flash poses coherent as complete families. Preserve the exact firing-flash source mask, which differs from the light/dark mask for the straight pose.","2. Ground defenses, airborne enemies and complete boss animation sequences; share palettes and the original logical canvases, rather than treating each enemy frame as an unrelated illustration.","3. Original projectiles and pickup/equipment animations. Tiny projectiles need careful readability checks; per-asset nearest fallback remains temporary until a clean remaster passes review.","4. Explosions, flame/spark sequences and other effects. Check full animation timing, transparency and palette cycling, not only a still image.","5. All four terrain sets, including unnamed catalog tiles. Generate with neighboring context and verify joined seams before changing runtime coverage.","6. Every original menu background, portrait, HUD and retained unused picture. Gameplay UI text and button labels must remain readable and match their actions. Verify the preserved native cinematic/font paths separately.","","## Reproduce the audit","","```sh","python3 tools/hd_art_audit.py --data ../data \\","  --json ../data/hd/coverage-audit.json --markdown docs/hd-backlog.md","python3 tools/hd_job_queue.py --data ../data","```","","The JSON gives every picture's asset ID, path, logical dimensions, original header options, source hash and HD status, plus each declared animation/set. The [completion ledger](hd-completion.json) records every required picture and native-art verification target, including complete families, ownership and candidate/review/registration stages. Both contain metadata only. Original and original-derived artwork remains outside Git.","","Folder totals: " + ", ".join(f"`{name}/`: {count:,}" for name,count in report["by_folder"].items()) + ". These folders are not semantic categories; terrain and other pictures also live in `misc/`.",""])
    effects=next(row for row in report["by_category"] if row["category"]==CATEGORIES[4])
    effect_ranges=effects["declared_sequences_or_sets"]
    lines.extend(["## Secondary effect coverage", "", f"Native animation registrations, pickup masks and beam impact/power companion arrays contribute {effects['pictures']:,} distinct effect frames. The {effect_ranges} declared ranges include one five-frame descending-smoke subset of the nine-frame smoke family, leaving {effect_ranges-1} complete families. This includes muzzle flashes/casings, laser impacts, smoke trails, lightning, sparks and the super-shield glow as well as explosions. Pickup glow uses indexed light-table mask semantics and needs a different HD treatment from an ordinary color sprite. These assets are not UI artwork merely because they are absent from the content registries. Renderer event reachability needs its own check before claiming complete gameplay effect coverage.", ""])
    terrain=report["terrain"]
    crosscheck=report["runtime_crosscheck"]
    terrain_status = "The canonical HD terrain renderer is validated: intact/destroyed source-bound tiles, shared HD edge/corner treatment and palette-class preservation are implemented. This adds no artwork coverage; each generated tile still requires its own contextual seam review." if terrain["runtime_hd_composition_supported"] else "HD terrain composition remains pending, so terrain experiments remain drafts until joined-seam checks and the renderer path pass."
    lines.extend(["## Runtime reachability and duplicate artwork","",f"The terrain backlog contains **{terrain['unique_payload_hashes']:,} distinct payload hashes** and **{terrain['unique_decoded_rgba_hashes']:,} distinct decoded images** across {terrain['catalog_frames']:,} catalog IDs. Duplicate IDs can share the same reviewed treatment; they still require explicit source-bound metadata. {terrain_status}",""])
    if crosscheck["available"]:
        lines.extend([f"The Python inventory matches the Rust decoder's complete picture ID and logical-dimension inventory. The shipped **{crosscheck['missions']} missions** reference **{crosscheck['mission_referenced_enemy_definitions']} of {crosscheck['enemy_definitions']} enemy definitions**, which reduce to **{crosscheck['mission_referenced_enemy_art_sequences']} of {crosscheck['unique_enemy_art_sequences']} distinct art sequences**, and **{terrain['mission_referenced_frames']:,} terrain frames**, including destroyed variants. Enemy names may alias the same artwork; the category table counts each asset ID once and the sequence count deduplicates identical base/frame ranges.",""])
    else:
        lines.extend(["The Rust registry cross-check is unavailable. Generate `../data/hd/runtime-content-audit.json` before using reachability totals to prioritize artwork.",""])
    return "\n".join(lines)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data",type=Path,default=Path(__file__).resolve().parents[2]/"data")
    parser.add_argument("--json",type=Path,required=True)
    parser.add_argument("--markdown",type=Path)
    parser.add_argument("--runtime-json",type=Path,help="Optional checked Rust Registry/Sprite inventory; defaults to data/hd/runtime-content-audit.json")
    args=parser.parse_args();report=audit(args.data,Path(__file__).resolve().parents[1],args.runtime_json)
    args.json.parent.mkdir(parents=True,exist_ok=True);args.json.write_text(json.dumps(report,indent=2)+"\n")
    if args.markdown:args.markdown.write_text(markdown(report))
    print(json.dumps({key:report[key] for key in ["catalog_entries","pictures","accepted_hd","missing_hd","by_category","terrain","runtime_crosscheck","hd_frame_errors","cinematics"]},indent=2))
if __name__=="__main__":main()
