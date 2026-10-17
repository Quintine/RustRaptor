"""Source-registered geometry cleanup preserving generated boss RGB relief.

This produces explicitly DERIVED artwork, never alters a Source or parent PNG,
and does not approve the result. Source controls alpha, gap-fill material and
explicit support-patch tone; existing generated body colors/detail are retained.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter, __version__ as PILLOW_VERSION

import hd_frame_policy

METHOD = "derived-generated-boss-source-geometry-rgb-preserved-v1"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def checked_input(binding, base):
    if type(binding) is not dict or set(binding) != {"path", "sha256"}:
        raise ValueError("input needs exactly path/sha256")
    path = Path(binding["path"])
    if not path.is_absolute():
        path = base / path
    data = path.read_bytes()
    if sha(data) != binding["sha256"]:
        raise ValueError(f"input hash mismatch: {path}")
    return path.resolve(), data


def bounds(value, width, height, label):
    if (type(value) is not list or len(value) != 4
            or any(type(n) is not int for n in value)):
        raise ValueError(f"{label} needs four integer bounds")
    l, t, r, b = value
    if not (0 <= l < r <= width and 0 <= t < b <= height):
        raise ValueError(f"{label} exceeds its canvas")
    return l, t, r, b


def signed_generated_detail(image, rectangle, size):
    crop = image.crop(tuple(rectangle)).resize(size, Image.Resampling.LANCZOS)
    rgb = np.asarray(crop)[:, :, :3].astype(np.float64)
    blur = np.asarray(crop.convert("RGB").filter(ImageFilter.GaussianBlur(1.2)))
    detail = (rgb - blur).mean(axis=2)
    return detail - detail.mean()


def render(recipe, base):
    allowed = {"format_version", "label", "asset", "source", "palette", "parent_raw",
               "logical_canvas", "origin", "output_scale", "alignment", "patches", "gap_fill"}
    if (type(recipe) is not dict or set(recipe) - allowed
            or type(recipe.get("format_version")) is not int or recipe["format_version"] != 1):
        raise ValueError("unknown recipe fields/version")
    asset = recipe["asset"]
    if (type(asset) is not str or not asset or len(asset) > 8
            or any(c not in "0123456789abcdef" for c in asset)):
        raise ValueError("asset needs lowercase hexadecimal identity")
    source_path, source_data = checked_input(recipe["source"], base)
    raw_path, raw_data = checked_input(recipe["parent_raw"], base)
    palette_path, palette_data = checked_input(recipe["palette"], base)
    width, height, indices = hd_frame_policy._indices(source_data)
    if (type(recipe["logical_canvas"]) is not list or type(recipe["origin"]) is not list
            or any(type(n) is not int for n in recipe["logical_canvas"] + recipe["origin"])
            or recipe["logical_canvas"] != [width, height] or recipe["origin"] != [0, 0]):
        raise ValueError("Source canvas and top-left origin must remain exact")
    scale = recipe["output_scale"]
    if type(scale) is not int or not 4 <= scale <= 16:
        raise ValueError("output_scale needs integer4..16")
    if width * height * scale * scale > 4_194_304:
        raise ValueError("derived image exceeds runtime pixel ceiling")
    if len(palette_data) != 768 or len(raw_data) > 32 * 1024 * 1024:
        raise ValueError("invalid palette/raw byte limit")
    palette = np.minimum(np.frombuffer(palette_data, dtype=np.uint8), 63)
    palette = ((palette << 2) | (palette >> 4)).reshape(256, 3)
    source = np.asarray(indices, dtype=np.uint16).reshape(height, width)
    source_alpha = np.repeat(np.repeat(source < 256, scale, axis=0), scale, axis=1)
    with Image.open(io.BytesIO(raw_data)) as opened:
        if opened.format != "PNG" or opened.width * opened.height > 4_194_304:
            raise ValueError("parent must be bounded PNG")
        raw = opened.convert("RGBA")
    alignment = recipe["alignment"]
    if type(alignment) is not dict or set(alignment) != {"raw_painted_bounds", "source_painted_bounds"}:
        raise ValueError("alignment needs exactly raw/source painted bounds")
    rl, rt, rr, rb = bounds(alignment["raw_painted_bounds"], *raw.size, "raw bounds")
    sl, st, sr, sb = bounds(alignment["source_painted_bounds"], width, height, "Source bounds")
    ys, xs = np.nonzero(source < 256)
    actual_source_bounds = [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]
    if actual_source_bounds != [sl, st, sr, sb]:
        raise ValueError("declared Source bounds differ from decoded Source")
    ax, ay = (rr - rl) / ((sr - sl) * scale), (rb - rt) / ((sb - st) * scale)
    affine = [ax, 0, rl - ax * sl * scale, 0, ay, rt - ay * st * scale]
    registered = np.array(raw.transform((width * scale, height * scale), Image.Transform.AFFINE,
                                      affine, Image.Resampling.BICUBIC))
    rgba = registered.copy()
    trusted = registered[:, :, 3] >= 128
    fill = recipe["gap_fill"]
    if type(fill) is not dict or set(fill) != {"generated_donor", "detail_gain"}:
        raise ValueError("gap_fill needs generated donor and detail gain")
    donor = bounds(fill["generated_donor"], *raw.size, "gap donor")
    gain = fill["detail_gain"]
    if type(gain) not in (int, float) or not 0 <= gain <= 1:
        raise ValueError("gap detail_gain needs0..1")
    gap_detail = signed_generated_detail(raw, donor, (scale, scale))
    gap_cells = []
    gap_pixel_count = 0
    for y, x in np.argwhere(source < 256):
        y, x = int(y), int(x)
        ys, xs = slice(y * scale, (y + 1) * scale), slice(x * scale, (x + 1) * scale)
        missing = ~trusted[ys, xs]
        if not missing.any():
            continue
        target = palette[source[y, x]].astype(np.float64)
        limit = min(16.0, max(1.0, float(target.mean()) * 0.25))
        texture = np.clip(gap_detail * gain, -limit, limit)
        pixels = np.clip(np.rint(target + texture[:, :, None]), 0, 255).astype(np.uint8)
        rgba[ys, xs, :3][missing] = pixels[missing]
        gap_cells.append([x, y])
        gap_pixel_count += int(missing.sum())
    patched = np.zeros_like(source_alpha)
    patch_records = []
    patches = recipe.get("patches", [])
    if type(patches) is not list or len(patches) > 32:
        raise ValueError("too many support patches")
    for patch in patches:
        if type(patch) is not dict or set(patch) != {"name", "target", "generated_donor", "detail_gain"}:
            raise ValueError("support patch needs name/target/generated_donor/detail_gain")
        l, t, r, b = bounds(patch["target"], width, height, "patch target")
        donor = bounds(patch["generated_donor"], *raw.size, "patch donor")
        gain = patch["detail_gain"]
        if type(gain) not in (int, float) or not 0 <= gain <= 1:
            raise ValueError("patch detail_gain needs0..1")
        detail = signed_generated_detail(raw, donor, ((r - l) * scale, (b - t) * scale))
        cells = []
        for y in range(t, b):
            for x in range(l, r):
                index = int(source[y, x])
                if not 0 <= index <= 31:
                    continue  # This option repairs Source steel/backing, never arbitrary recoloring.
                ys, xs = slice(y * scale, (y + 1) * scale), slice(x * scale, (x + 1) * scale)
                if patched[ys, xs].any():
                    raise ValueError("overlapping support patches")
                texture = detail[(y - t) * scale:(y - t + 1) * scale,
                                 (x - l) * scale:(x - l + 1) * scale]
                texture = (texture - texture.mean()) * gain
                target = palette[index].astype(np.float64)
                limit = min(24.0, max(1.0, float(target.mean()) * 0.35))
                pixels = np.clip(np.rint(target + np.clip(texture, -limit, limit)[:, :, None]), 0, 255)
                rgba[ys, xs, :3] = pixels.astype(np.uint8)
                patched[ys, xs] = True
                cells.append([x, y])
        patch_records.append(dict(name=patch["name"], target=patch["target"], cells=cells,
                                  generated_donor=patch["generated_donor"], detail_gain=gain))
    # Logical occupancy is explicit Source geometry, independent of generated material.
    rgba[:, :, 3] = np.where(source_alpha, 255, 0)
    rgba[~source_alpha, :3] = 0
    direct = source_alpha & trusted & ~patched
    if not direct.any() or not np.array_equal(rgba[direct, :3], registered[direct, :3]):
        raise AssertionError("generated body RGB was not preserved")
    direct_fraction = float(direct.sum() / source_alpha.sum())
    if direct_fraction < 0.5:
        raise ValueError("most generated body is missing; refusing Source-fill relabel")
    cell_detail = 0
    direct_detail = 0
    for y, x in np.argwhere(source < 256):
        pixels = rgba[y*scale:(y+1)*scale, x*scale:(x+1)*scale, :3]
        cell_detail += int(np.any(pixels != pixels[0, 0], axis=2).sum())
        selected = pixels[direct[y*scale:(y+1)*scale, x*scale:(x+1)*scale]]
        if len(selected):
            direct_detail += int(np.any(selected != selected[0], axis=1).sum())
    if direct_detail == 0:
        raise ValueError("no internal detail remains; refusing an Original NN relabel")
    report = dict(method=METHOD, output_class="DERIVED_SCRIPTED_GEOMETRY_CLEANUP_NOT_UNTOUCHED_GENERATION",
                  source=source_path.as_posix(), parent_raw=raw_path.as_posix(), palette=palette_path.as_posix(),
                  logical_canvas=[width, height], origin=[0, 0], output_scale=scale,
                  full_canvas_affine_output_to_raw=affine, Source_painted_bounds=actual_source_bounds,
                  Source_painted_cells=int((source < 256).sum()), output_painted_pixels=int(source_alpha.sum()),
                  direct_generated_RGB_pixels=int(direct.sum()),
                  direct_generated_fraction_of_painted=direct_fraction,
                  gap_filled_pixels=gap_pixel_count, gap_filled_cells=gap_cells,
                  patches=patch_records, internally_nonconstant_pixels=cell_detail,
                  direct_generated_internally_nonconstant_pixels=direct_detail,
                  Source_decoder_sha256=sha(Path(hd_frame_policy.__file__).read_bytes()),
                  numpy_version=np.__version__, pillow_version=PILLOW_VERSION)
    return rgba, report


def run_recipe(recipe_path, output):
    recipe_path, output = Path(recipe_path), Path(output)
    if output.exists():
        raise ValueError("output exists; do not overwrite old outputs")
    recipe_bytes = recipe_path.read_bytes()
    recipe = json.loads(recipe_bytes)
    rgba, report = render(recipe, recipe_path.resolve().parent)
    buffer = io.BytesIO()
    Image.fromarray(rgba).save(buffer, format="PNG", compress_level=9)
    png = buffer.getvalue()
    name = f"{recipe['asset']}-derived.png"
    report["execution"] = dict(status="success", method=METHOD,
                               recipe_sha256=sha(recipe_bytes), tool_sha256=sha(Path(__file__).read_bytes()),
                               source_sha256={recipe["asset"]: recipe["source"]["sha256"]},
                               parent_raw_sha256=[recipe["parent_raw"]["sha256"]],
                               output_sha256={recipe["asset"]: sha(png)})
    report["output"] = dict(file=name, bytes=len(png), RGBA_sha256=sha(rgba.tobytes()))
    output.mkdir(parents=True)
    (output / name).write_bytes(png)
    (output / "derived-provenance.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    parser.add_argument("output_new_directory", type=Path)
    args = parser.parse_args()
    report = run_recipe(args.recipe, args.output_new_directory)
    print(json.dumps(dict(execution=report["execution"], direct_generated_fraction=report["direct_generated_fraction_of_painted"])))


if __name__ == "__main__":
    main()
