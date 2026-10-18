"""Reconstruct Original UI geometry around authenticated generated material.

This creates DERIVED artwork, not untouched generation and not art approval.
Original owns all occupied/empty pixels. Generated RGB is registered in complete
declared regions, shifted once per Original palette class, and bounded around
that class. Unsupported strokes receive disclosed flat Original-color backing.
No text is inferred, no random detail is made, and no new runtime policy is used.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image, __version__ as PILLOW_VERSION

import hd_frame_policy

METHOD = "derived-generated-ui-original-stencil-class-tone-visible-parent-variance-v3"
PARENT_VISIBLE_ALPHA = 128
MAX_PIXELS = 4_194_304
MAX_INPUT_BYTES = 32 * 1024 * 1024


def sha(data):
    return hashlib.sha256(data).hexdigest()


def checked_input(binding, base, byte_limit=MAX_INPUT_BYTES):
    if type(binding) is not dict or set(binding) != {"path", "sha256"}:
        raise ValueError("input needs exactly path/sha256")
    if type(binding["path"]) is not str or not binding["path"]:
        raise ValueError("input path must be nonempty text")
    digest = binding["sha256"]
    if (type(digest) is not str or len(digest) != 64
            or any(c not in "0123456789abcdef" for c in digest)):
        raise ValueError("input SHA256 must be lowercase hexadecimal")
    path = Path(binding["path"])
    if not path.is_absolute():
        path = Path(base) / path
    if path.stat().st_size > byte_limit:
        raise ValueError("input byte limit exceeded")
    data = path.read_bytes()
    if len(data) > byte_limit or sha(data) != digest:
        raise ValueError(f"input identity mismatch: {path}")
    return path.resolve(), data


def bounds(value, width, height, label):
    if (type(value) is not list or len(value) != 4
            or any(type(n) is not int for n in value)):
        raise ValueError(f"{label} needs four integer bounds")
    l, t, r, b = value
    if not (0 <= l < r <= width and 0 <= t < b <= height):
        raise ValueError(f"{label} exceeds its canvas")
    return l, t, r, b


def parent_material_witnesses(parent, original_classes):
    """Certify local RGB variation before alpha/resampling can manufacture it.

    All nine pixels must be visible (alpha>=128) and belong to the same mapped Original
    palette class. Hidden RGB, low-alpha feather pixels, Source gaps and class boundaries
    cannot certify material. This is a conservative numeric witness, not an
    artistic verdict about whether the texture is useful.
    """
    height, width = original_classes.shape
    witnesses = np.zeros((height, width), dtype=bool)
    if height < 3 or width < 3:
        return witnesses
    center = original_classes[1:-1, 1:-1]
    eligible = (parent[1:-1, 1:-1, 3] >= PARENT_VISIBLE_ALPHA) & (center < 240)
    varying = np.zeros_like(eligible)
    center_rgb = parent[1:-1, 1:-1, :3]
    for dy, dx in [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]:
        neighbor = parent[1+dy:height-1+dy, 1+dx:width-1+dx]
        neighbor_class = original_classes[1+dy:height-1+dy, 1+dx:width-1+dx]
        eligible &= (neighbor[:, :, 3] >= PARENT_VISIBLE_ALPHA) & (neighbor_class == center)
        varying |= np.any(neighbor[:, :, :3] != center_rgb, axis=2)
    witnesses[1:-1, 1:-1] = eligible & varying
    return witnesses


def render(recipe, base):
    allowed = {"format_version", "label", "asset", "source", "palette", "parent_raw",
               "logical_canvas", "origin", "output_scale", "regions", "classes"}
    required = allowed - {"label"}
    if (type(recipe) is not dict or set(recipe) - allowed or not required <= set(recipe)
            or type(recipe["format_version"]) is not int or recipe["format_version"] != 1):
        raise ValueError("unknown/missing recipe fields or version")
    asset = recipe["asset"]
    if (type(asset) is not str or not asset or len(asset) > 8
            or any(c not in "0123456789abcdef" for c in asset)):
        raise ValueError("asset needs lowercase hexadecimal identity")
    source_path, source_bytes = checked_input(recipe["source"], base)
    raw_path, raw_bytes = checked_input(recipe["parent_raw"], base)
    palette_path, palette_bytes = checked_input(recipe["palette"], base, 768)
    if len(palette_bytes) != 768:
        raise ValueError("palette must have768 six-bit components")
    width, height, indices = hd_frame_policy._indices(source_bytes)
    if (type(recipe["logical_canvas"]) is not list or type(recipe["origin"]) is not list
            or any(type(n) is not int for n in recipe["logical_canvas"] + recipe["origin"])
            or recipe["logical_canvas"] != [width, height] or recipe["origin"] != [0, 0]):
        raise ValueError("Original canvas and top-left origin must remain exact")
    scale = recipe["output_scale"]
    if type(scale) is not int or not 4 <= scale <= 16:
        raise ValueError("output_scale needs integer4..16")
    if width * height * scale * scale > MAX_PIXELS:
        raise ValueError("derived image exceeds pixel ceiling")
    if isinstance(indices, (bytes, bytearray, memoryview)):
        decoded = np.frombuffer(indices, dtype=np.uint8).astype(np.uint16)
    else:
        decoded = np.asarray(indices, dtype=np.uint16)
    source = decoded.reshape(height, width)
    painted = source < 256
    if not painted.any():
        raise ValueError("Original has no painted UI")
    source_classes = set(int(x) for x in np.unique(source[painted]))
    if any(x >= 240 for x in source_classes):
        raise ValueError("UI cleanup supports ordinary Original palette classes only")
    classes = recipe["classes"]
    if type(classes) is not list or not 1 <= len(classes) <= 16:
        raise ValueError("classes needs one to16 explicit Original palette classes")
    limits = {}
    for cls in classes:
        if (type(cls) is not dict or set(cls) != {"index", "max_channel_delta"}
                or type(cls["index"]) is not int or type(cls["max_channel_delta"]) is not int
                or not 0 <= cls["index"] < 240 or not 0 <= cls["max_channel_delta"] <= 32
                or cls["index"] in limits):
            raise ValueError("invalid/duplicate Original material class")
        limits[cls["index"]] = cls["max_channel_delta"]
    if set(limits) != source_classes:
        raise ValueError("material classes must exactly cover painted Original indices")
    palette = np.minimum(np.frombuffer(palette_bytes, dtype=np.uint8), 63)
    palette = ((palette << 2) | (palette >> 4)).reshape(256, 3)
    with Image.open(io.BytesIO(raw_bytes)) as opened:
        if opened.format != "PNG" or opened.width * opened.height > MAX_PIXELS:
            raise ValueError("parent must be a bounded PNG")
        raw = opened.convert("RGBA")
    regions = recipe["regions"]
    if type(regions) is not list or not 1 <= len(regions) <= 16:
        raise ValueError("regions needs one to16 explicit material registrations")
    assigned = np.zeros((height, width), dtype=bool)
    plan = []
    for region in regions:
        if (type(region) is not dict or set(region) != {"name", "source_bounds", "raw_bounds"}
                or type(region["name"]) is not str or not region["name"]):
            raise ValueError("region needs name/source_bounds/raw_bounds")
        l, t, r, b = bounds(region["source_bounds"], width, height, "Original region")
        rb = bounds(region["raw_bounds"], *raw.size, "raw material region")
        if assigned[t:b, l:r].any():
            raise ValueError("material registration regions overlap")
        selected = painted[t:b, l:r]
        if not selected.any():
            raise ValueError("material region contains no painted Original cells")
        assigned[t:b, l:r] = True
        plan.append((region, (l, t, r, b), rb))
    if not np.all(assigned[painted]):
        raise ValueError("material regions do not cover every painted Original cell")
    # Inspect untouched parent pixels before performing any RGBA resize. Map the
    # logical stencil into each parent region by exact pixel-center arithmetic.
    authenticated_material = []
    parent_witness_count = 0
    for region, (l, t, r, b), rb in plan:
        parent = np.asarray(raw.crop(rb))
        ph, pw = parent.shape[:2]
        ox = ((np.arange(pw, dtype=np.int64)*2+1)*(r-l)) // (pw*2)
        oy = ((np.arange(ph, dtype=np.int64)*2+1)*(b-t)) // (ph*2)
        original_classes = source[t+oy[:,None], l+ox[None,:]]
        witnesses = parent_material_witnesses(parent, original_classes)
        parent_witness_count += int(witnesses.sum())
        authenticated_material.append((region, (l,t,r,b), rb, witnesses, original_classes))
    if parent_witness_count == 0:
        raise ValueError("no generated fine RGB: no pre-resample visible parent material variance")
    # Each registered material field remains continuous across its complete region.
    source_nx = source.repeat(scale, axis=0).repeat(scale, axis=1)
    occupied = source_nx < 256
    rgb = np.zeros((height * scale, width * scale, 3), dtype=np.uint8)
    trusted = np.zeros_like(occupied)
    certified_class = np.full(source_nx.shape, 256, dtype=np.uint16)
    region_reports = []
    for region, (l, t, r, b), rb, witnesses, original_classes in authenticated_material:
        size = ((r-l)*scale, (b-t)*scale)
        sampled = np.asarray(raw.crop(rb).resize(size, Image.Resampling.LANCZOS))
        yy, xx = slice(t*scale, b*scale), slice(l*scale, r*scale)
        rgb[yy, xx] = sampled[:, :, :3]
        trusted[yy, xx] = sampled[:, :, 3] >= 128
        # Nearest registration carries evidence only; it never paints RGB.
        witness_classes = np.where(witnesses, original_classes, 256).astype(np.uint16)
        certified_class[yy, xx] = np.asarray(Image.fromarray(witness_classes).resize(size, Image.Resampling.NEAREST))
        region_reports.append(dict(name=region["name"], source_bounds=[l,t,r,b],
                                   raw_material_sampling_bounds=list(rb), registered_canvas=list(size),
                                   registered_RGBA_sha256=sha(sampled.tobytes()),
                                   pre_resample_visible_parent_material_witnesses=int(witnesses.sum()),
                                   parent_witness_class_map_sha256=sha(witness_classes.tobytes())))
    direct = occupied & trusted
    restored = occupied & ~trusted
    certified_direct = direct & (certified_class == source_nx)
    direct_fraction = float(direct.sum() / occupied.sum())
    if direct_fraction < 0.5:
        raise ValueError("most generated UI support is absent; refusing Source-fill relabel")
    registered_rgb = rgb.copy()
    class_reports = []
    for index in sorted(source_classes):
        selected = source_nx == index
        supported = selected & direct
        missing = selected & restored
        target = palette[index].astype(np.int16)
        if supported.any():
            # A single tone anchor per entire palette class, never per source cell.
            median = np.median(registered_rgb[supported], axis=0)
            shift = target.astype(np.float64) - median
            before_limit = np.rint(registered_rgb[supported].astype(np.float64) + shift)
            delta = np.clip(before_limit-target, -limits[index], limits[index])
            rgb[supported] = np.clip(target + delta, 0, 255).astype(np.uint8)
            clipped = int(np.count_nonzero(before_limit-target != delta))
        else:
            median, shift, clipped = None, None, 0
        rgb[missing] = target.astype(np.uint8)
        class_reports.append(dict(index=index, Original_RGB=target.tolist(),
                                  max_channel_delta=limits[index],
                                  generated_supported_pixels=int(supported.sum()),
                                  restored_flat_Original_functional_pixels=int(missing.sum()),
                                  registered_RGB_median=None if median is None else median.tolist(),
                                  consistent_RGB_shift=None if shift is None else shift.tolist(),
                                  channel_samples_clipped_to_declared_tone_bound=clipped))
    detail_cells = []
    detail_pixels = 0
    for y, x in np.argwhere(painted):
        yy, xx = slice(y*scale, (y+1)*scale), slice(x*scale, (x+1)*scale)
        values = rgb[yy, xx][certified_direct[yy, xx]]
        if len(values) > 1:
            differing = int(np.any(values != values[0], axis=1).sum())
            if differing:
                detail_cells.append([int(x),int(y)])
                detail_pixels += differing
    if not detail_cells:
        raise ValueError("no generated fine RGB remains; refusing an Original NN relabel")
    rgba = np.zeros((height*scale, width*scale, 4), dtype=np.uint8)
    rgba[occupied, :3] = rgb[occupied]
    rgba[occupied, 3] = 255
    report = dict(method=METHOD,
                  output_class="DERIVED_ORIGINAL_UI_GEOMETRY_WITH_REGISTERED_GENERATED_RGB_NOT_ART_APPROVAL",
                  input_paths=dict(source=str(source_path),parent_raw=str(raw_path),palette=str(palette_path)),
                  logical_canvas=[width,height], origin=[0,0], output_scale=scale,
                  full_output_canvas=[width*scale,height*scale], runtime_crop=None,
                  Original_painted_cells=int(painted.sum()), painted_output_pixels=int(occupied.sum()),
                  exact_Original_Nx_alpha=True, direct_generated_support_pixels=int(direct.sum()),
                  direct_generated_support_fraction=direct_fraction,
                  pre_resample_visible_parent_material_witnesses=parent_witness_count,
                  registered_certified_parent_material_pixels=int(certified_direct.sum()),
                  fine_RGB_credit_requires_same_class_parent_material_witness=True,
                  parent_material_visibility=dict(alpha_min=PARENT_VISIBLE_ALPHA,neighborhood=[3,3],
                      RGB_variance_before_resampling=True,Original_class_must_match_all_neighbors=True),
                  restored_flat_Original_functional_pixels=int(restored.sum()),
                  restored_Original_cells=[[int(x),int(y)] for y,x in np.argwhere(restored.reshape(height,scale,width,scale).any(axis=(1,3)))],
                  material_regions=region_reports, class_tone_controls=class_reports,
                  generated_fine_RGB_cells=detail_cells, generated_fine_RGB_pixels=detail_pixels,
                  material_metrics_are_not_artistic_approval=True,
                  raw_RGB_is_shifted_and_bounded_not_claimed_byte_exact=True,
                  no_random_or_tiled_synthetic_detail=True,
                  Source_decoder_sha256=sha(Path(hd_frame_policy.__file__).read_bytes()),
                  reader_environment=dict(Python=sys.version,Python_executable_sha256=sha(Path(sys.executable).read_bytes()),
                                          NumPy=np.__version__,Pillow=PILLOW_VERSION))
    return rgba, report


def run_recipe(recipe_path, output):
    recipe_path, output = Path(recipe_path), Path(output)
    if output.exists():
        raise ValueError("output exists; never overwrite old artwork or evidence")
    recipe_bytes = recipe_path.read_bytes()
    recipe = json.loads(recipe_bytes)
    rgba, report = render(recipe, recipe_path.resolve().parent)
    buffer = io.BytesIO()
    Image.fromarray(rgba).save(buffer, format="PNG", compress_level=9)
    png = buffer.getvalue()
    name = f"{recipe['asset']}-derived.png"
    report["execution"] = dict(status="success",method=METHOD,
        recipe_sha256=sha(recipe_bytes),tool_sha256=sha(Path(__file__).read_bytes()),
        source_sha256={recipe["asset"]:recipe["source"]["sha256"]},
        parent_raw_sha256=[recipe["parent_raw"]["sha256"]],
        output_sha256={recipe["asset"]:sha(png)})
    report["output"] = dict(file=name,bytes=len(png),RGBA_sha256=sha(rgba.tobytes()))
    output.mkdir(parents=True,exist_ok=False)
    (output/name).write_bytes(png)
    (output/"derived-provenance.json").write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe",type=Path)
    parser.add_argument("output_new_directory",type=Path)
    args=parser.parse_args()
    report=run_recipe(args.recipe,args.output_new_directory)
    print(json.dumps(dict(execution=report["execution"],generated_support_fraction=report["direct_generated_support_fraction"],restored_Original_pixels=report["restored_flat_Original_functional_pixels"])))


if __name__ == "__main__":
    main()
