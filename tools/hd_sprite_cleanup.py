"""Deterministic, explicitly DERIVED sprite cleanup; never modifies input artwork.

Recipe v1: palette {path,sha256}, output_scale (4..16), and frames containing
asset, source {path,sha256}, raw_png {path,sha256}, viewport [l,t,r,b], origin.
Viewport values may be exact rational strings. Source alpha/material values
define geometry; bounded high-frequency generated detail supplies the texture.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from fractions import Fraction
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter, __version__ as PILLOW_VERSION

import hd_frame_policy
from hd_frame_policy import _indices

METHOD = "derived-source-alpha-material-shared-generated-detail-v1"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def checked_input(binding, base):
    if not isinstance(binding, dict) or set(binding) != {"path", "sha256"}:
        raise ValueError("input needs exactly path/sha256")
    path = Path(binding["path"])
    if not path.is_absolute():
        path = base / path
    data = path.read_bytes()
    if digest(data) != binding["sha256"]:
        raise ValueError(f"input hash mismatch: {path}")
    return path.resolve(), data


def palette_rgb(data):
    if len(data) < 768:
        raise ValueError("truncated Original palette")
    values = np.minimum(np.frombuffer(data[:768], dtype=np.uint8), 63)
    return ((values << 2) | (values >> 4)).reshape(256, 3)


def viewport_numbers(value, image_size):
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError("viewport needs four exact bounds")
    values = [Fraction(v) for v in value]
    left, top, right, bottom = values
    if not (0 <= left < right <= image_size[0]
            and 0 <= top < bottom <= image_size[1]):
        raise ValueError("viewport exceeds raw canvas")
    return values


def _texture(high, target, strength):
    """Remove generated broad lighting/bevels, retain bounded fine variation."""
    if not np.any(target):
        return np.zeros_like(high)
    limit = min(8.0, max(1.0, float(target.mean()) * 0.20))
    # A zero/full Source channel cannot carry symmetric detail. Keeping it exact
    # avoids adding a colored tint when clipping the signed texture residual.
    limits = np.minimum(limit, np.minimum(target, 255 - target))
    detail = high.astype(np.float64) * strength
    detail -= detail.mean(axis=(0, 1), keepdims=True)
    detail = np.clip(detail, -limits, limits)
    detail -= detail.mean(axis=(0, 1), keepdims=True)
    return np.clip(detail, -limits, limits)


def render_family(recipe, base):
    """Return separate RGBA arrays and measurements; performs no writes."""
    if recipe.get("format_version") != 1:
        raise ValueError("unsupported cleanup recipe version")
    if set(recipe) - {"format_version", "palette", "output_scale", "detail_strength",
                      "highpass_radius_pixels", "require_generated_detail", "frames", "label"}:
        raise ValueError("unknown cleanup recipe fields")
    scale = recipe.get("output_scale", 8)
    if type(scale) is not int or not 4 <= scale <= 16:
        raise ValueError("output_scale must be integer4..16")
    strength = recipe.get("detail_strength", 1.0)
    if type(strength) not in (int, float) or not 0 <= strength <= 2:
        raise ValueError("detail_strength must be0..2")
    radius = recipe.get("highpass_radius_pixels", 1.2)
    if type(radius) not in (int, float) or not 0 < radius <= 4:
        raise ValueError("highpass radius must be positive and<=4")
    frames = recipe.get("frames")
    if not isinstance(frames, list) or not 1 <= len(frames) <= 64:
        raise ValueError("cleanup needs1..64 complete family frames")
    palette_path, palette_data = checked_input(recipe["palette"], base)
    palette = palette_rgb(palette_data)
    ids = set()
    loaded = []
    shape = None
    inputs = {str(palette_path): digest(palette_data)}
    for frame in frames:
        if set(frame) - {"asset", "source", "raw_png", "viewport", "origin", "detail_donors"}:
            raise ValueError("unknown cleanup frame fields")
        asset = frame["asset"]
        if not isinstance(asset, str) or not asset or any(c not in "0123456789abcdef" for c in asset) or asset in ids:
            raise ValueError("asset IDs must be unique lowercase hexadecimal")
        ids.add(asset)
        source_path, source_data = checked_input(frame["source"], base)
        width, height, cells = _indices(source_data)
        if shape is not None and shape != (height, width):
            raise ValueError("complete family must have consistent logical canvas")
        shape = (height, width)
        if width * height * scale * scale > 4_194_304:
            raise ValueError("derived frame exceeds runtime PNG pixel ceiling")
        origin = frame.get("origin", [0, 0])
        if not isinstance(origin, list) or len(origin) != 2 or any(type(v) is not int for v in origin):
            raise ValueError("origin needs two integer coordinates")
        source = np.asarray(cells, dtype=np.uint16).reshape(height, width)
        raw_path, raw_data = checked_input(frame["raw_png"], base)
        if len(raw_data) > 32 * 1024 * 1024:
            raise ValueError("raw PNG exceeds32MiB")
        with Image.open(io.BytesIO(raw_data)) as image:
            if image.format != "PNG" or image.width * image.height > 4_194_304:
                raise ValueError("raw must be a bounded PNG")
            viewport = viewport_numbers(frame["viewport"], image.size)
            sampled = np.asarray(image.convert("RGBA").transform(
                (width * scale, height * scale), Image.Transform.EXTENT,
                tuple(float(v) for v in viewport), Image.Resampling.BICUBIC)).copy()
        rgb = sampled[:, :, :3]
        blurred = np.asarray(Image.fromarray(rgb).filter(ImageFilter.GaussianBlur(radius)))
        high = rgb.astype(np.float64) - blurred.astype(np.float64)
        trusted = sampled[:, :, 3] >= 128
        high[~trusted] = 0
        donors = frame.get("detail_donors", [])
        donor_targets = set()
        original_high = high.copy()
        for donor in donors:
            if not isinstance(donor, dict) or set(donor) != {"target", "source"}:
                raise ValueError("detail donor needs exactly target/source cells")
            positions = []
            for key in ["target", "source"]:
                cell = donor[key]
                if not isinstance(cell, list) or len(cell) != 2 or any(type(v) is not int for v in cell):
                    raise ValueError("detail donor cell needs two integers")
                x, y = cell
                if not (0 <= x < width and 0 <= y < height) or source[y, x] == 256:
                    raise ValueError("detail donor must use painted Original cells")
                positions.append((x, y))
            (tx, ty), (sx, sy) = positions
            if (tx, ty) in donor_targets:
                raise ValueError("duplicate detail donor target")
            donor_targets.add((tx, ty))
            high[ty*scale:(ty+1)*scale, tx*scale:(tx+1)*scale] = original_high[sy*scale:(sy+1)*scale, sx*scale:(sx+1)*scale]
        loaded.append(dict(frame=frame, source=source, high=high, trusted=trusted,
                           viewport=[str(v) for v in viewport], donor_count=len(donors)))
        inputs[str(source_path)] = digest(source_data)
        inputs[str(raw_path)] = digest(raw_data)
    sources = np.stack([item["source"] for item in loaded])
    common = np.all(sources == sources[0], axis=0) & (sources[0] < 256)
    shared = np.median(np.stack([item["high"] for item in loaded]), axis=0)
    outputs = []
    reports = []
    for item in loaded:
        source = item["source"]
        height, width = source.shape
        rgba = np.zeros((height * scale, width * scale, 4), dtype=np.uint8)
        fallback_cells = []
        detail_pixels = 0
        max_mean_error = 0.0
        for y, x in np.argwhere(source < 256):
            ys = slice(y * scale, (y + 1) * scale)
            xs = slice(x * scale, (x + 1) * scale)
            target = palette[source[y, x]].astype(np.float64)
            texture = shared[ys, xs] if common[y, x] else item["high"][ys, xs]
            detail = _texture(texture, target, strength)
            pixels = np.clip(np.rint(target + detail), 0, 255).astype(np.uint8)
            rgba[ys, xs, :3] = pixels
            rgba[ys, xs, 3] = 255
            detail_pixels += int(np.any(pixels != target, axis=2).sum())
            max_mean_error = max(max_mean_error, float(np.max(np.abs(pixels.mean(axis=(0, 1)) - target))))
            if not np.any(item["trusted"][ys, xs]):
                fallback_cells.append([int(x), int(y)])
        if recipe.get("require_generated_detail", True) and detail_pixels == 0:
            raise ValueError("no generated interior detail survived; refusing HD relabel")
        outputs.append(rgba)
        reports.append(dict(asset=item["frame"]["asset"], logical_width=width,
                            logical_height=height, origin=item["frame"].get("origin", [0, 0]),
                            source_sha256=item["frame"]["source"]["sha256"],
                            sampled_raw_viewport=item["viewport"], detail_donor_cells=item["donor_count"],
                            Source_painted_cells=int((source < 256).sum()),
                            Source_supported_alpha_pixels=int((rgba[:, :, 3] == 255).sum()),
                            nonzero_generated_detail_pixels=detail_pixels,
                            maximum_cell_channel_mean_error=max_mean_error,
                            Source_fill_cells_without_visible_raw=fallback_cells))
    for output in outputs[1:]:
        for y, x in np.argwhere(common):
            if not np.array_equal(output[y*scale:(y+1)*scale, x*scale:(x+1)*scale], outputs[0][y*scale:(y+1)*scale, x*scale:(x+1)*scale]):
                raise AssertionError("shared Source backing is not identical")
    return outputs, dict(method=METHOD, output_class="DERIVED_SCRIPTED_CLEANUP_NOT_UNTOUCHED_GENERATION",
                         input_hashes=inputs, output_scale=scale, Source_identical_shared_cells=int(common.sum()),
                         detail_strength=strength, highpass_radius_pixels=radius, frames=reports,
                         numpy_version=np.__version__, pillow_version=PILLOW_VERSION)


def run_recipe(recipe_path, output):
    recipe_path, output = Path(recipe_path), Path(output)
    if output.exists():
        raise ValueError("output directory already exists; inputs and old outputs are never overwritten")
    recipe_bytes = recipe_path.read_bytes()
    recipe = json.loads(recipe_bytes)
    arrays, report = render_family(recipe, recipe_path.resolve().parent)
    payloads = []
    for pixels, frame in zip(arrays, recipe["frames"]):
        buffer = io.BytesIO()
        Image.fromarray(pixels).save(buffer, format="PNG", compress_level=9)
        payloads.append((f"{frame['asset']}-derived.png", buffer.getvalue()))
    output.mkdir(parents=True)
    for index, ((name, data), frame) in enumerate(zip(payloads, report["frames"])):
        (output / name).write_bytes(data)
        frame["output"] = dict(file=name, sha256=digest(data), bytes=len(data),
                               RGBA_sha256=digest(arrays[index].tobytes()))
    report["recipe_sha256"] = digest(recipe_bytes)
    report["tool_sha256"] = digest(Path(__file__).read_bytes())
    report["decoder_module"] = dict(path=str(Path(hd_frame_policy.__file__).resolve()),
                                    sha256=digest(Path(hd_frame_policy.__file__).read_bytes()))
    report["execution"] = dict(
        status="success", method=METHOD, recipe_sha256=report["recipe_sha256"],
        tool_sha256=report["tool_sha256"],
        source_sha256={frame["asset"]: frame["source"]["sha256"] for frame in recipe["frames"]},
        parent_raw_sha256=sorted({frame["raw_png"]["sha256"] for frame in recipe["frames"]}),
        output_sha256={frame["asset"]: frame["output"]["sha256"] for frame in report["frames"]})
    (output / "derived-provenance.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    parser.add_argument("output_new_directory", type=Path)
    args = parser.parse_args()
    report = run_recipe(args.recipe, args.output_new_directory)
    print(json.dumps(dict(method=report["method"], derived_frames=len(report["frames"]),
                          shared_Source_cells=report["Source_identical_shared_cells"])))


if __name__ == "__main__":
    main()
