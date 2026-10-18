"""Derived family cleanup preserving continuous generated RGB, not Source cells.

Source controls canvas/alpha, material-region statistics and the moving envelope.
Generated RGB supplies all body form and shading. Only explicit functional blue
cue cells are copied from Source RGB. Inputs and prior outputs are never changed.
"""
from __future__ import annotations

import argparse
from collections import deque
from fractions import Fraction
import hashlib
import io
import json
from pathlib import Path
import platform

import numpy as np
from PIL import Image, ImageFilter, __version__ as PILLOW_VERSION

import hd_frame_policy

METHOD = "derived-generated-worm-rgb-broad-material-source-alpha-shared-backing-v1"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def checked(binding, base):
    if type(binding) is not dict or set(binding) != {"path", "sha256"}:
        raise ValueError("input needs exactly path/sha256")
    path = Path(binding["path"])
    if not path.is_absolute():
        path = base / path
    data = path.read_bytes()
    if sha(data) != binding["sha256"]:
        raise ValueError(f"input hash mismatch: {path}")
    return path.resolve(), data


def up(mask, scale):
    return np.repeat(np.repeat(mask, scale, axis=0), scale, axis=1)


def nearest_generated_fill(rgb, trusted, occupied):
    """Deterministic nearest Manhattan donor, with raster/N,W,E,S tie order."""
    if not trusted.any():
        raise ValueError("no visible generated RGB donors")
    owner_y, owner_x = np.indices(trusted.shape)
    known = trusted.copy()
    queue = deque((int(y), int(x)) for y, x in np.argwhere(trusted))
    height, width = trusted.shape
    while queue:
        y, x = queue.popleft()
        for ny, nx in ((y-1, x), (y, x-1), (y, x+1), (y+1, x)):
            if 0 <= ny < height and 0 <= nx < width and not known[ny, nx]:
                known[ny, nx] = True
                owner_y[ny, nx], owner_x[ny, nx] = owner_y[y, x], owner_x[y, x]
                queue.append((ny, nx))
    missing = occupied & ~trusted
    filled = rgb.copy()
    filled[missing] = rgb[owner_y[missing], owner_x[missing]]
    return filled, int(missing.sum())


def inner_weight(mask, feather):
    """Blend inside a genuine moving envelope; outside is exactly stationary."""
    current = Image.fromarray((mask * 255).astype(np.uint8))
    weight = np.zeros(mask.shape, dtype=np.float64)
    for _ in range(feather):
        weight += np.asarray(current) > 0
        current = current.filter(ImageFilter.MinFilter(3))
    return weight / feather


def region_gain(target, generated, label):
    if len(target) == 0 or len(generated) == 0:
        raise ValueError(f"empty {label} material sample")
    target_mean, raw_mean = target.mean(axis=0), generated.mean(axis=0)
    gain = np.clip(target_mean / np.maximum(raw_mean, 1), 0.25, 2.0)
    return gain, target_mean, raw_mean


def render_family(recipe, base):
    if (type(recipe) is not dict or set(recipe) !=
            {"format_version", "label", "palette", "output_scale", "feather_logical_pixels", "frames"}
            or type(recipe["format_version"]) is not int or recipe["format_version"] != 1):
        raise ValueError("unknown recipe fields/version")
    scale = recipe["output_scale"]
    feather = recipe["feather_logical_pixels"]
    if type(scale) is not int or not 4 <= scale <= 16:
        raise ValueError("output_scale needs integer4..16")
    if type(feather) is not int or not 1 <= feather <= 2:
        raise ValueError("feather needs integer1..2 logical pixels")
    frames = recipe["frames"]
    if type(frames) is not list or not 2 <= len(frames) <= 64:
        raise ValueError("needs complete family2..64")
    palette_path, palette_data = checked(recipe["palette"], base)
    if len(palette_data) != 768:
        raise ValueError("Original palette needs768 bytes")
    palette = np.minimum(np.frombuffer(palette_data, dtype=np.uint8), 63)
    palette = ((palette << 2) | (palette >> 4)).reshape(256, 3)
    loaded, ids, shape = [], set(), None
    inputs = {str(palette_path): sha(palette_data)}
    for frame in frames:
        if type(frame) is not dict or set(frame) != {"asset", "source", "parent_raw", "logical_canvas", "origin", "atlas_grid", "raw_painted_bounds"}:
            raise ValueError("unknown frame fields")
        asset = frame["asset"]
        if type(asset) is not str or not asset or asset in ids or any(c not in "0123456789abcdef" for c in asset):
            raise ValueError("unique lowercase hexadecimal IDs required")
        ids.add(asset)
        source_path, source_data = checked(frame["source"], base)
        width, height, cells = hd_frame_policy._indices(source_data)
        if shape is not None and shape != (height, width):
            raise ValueError("family logical canvas differs")
        shape = (height, width)
        if (type(frame["logical_canvas"]) is not list or type(frame["origin"]) is not list
                or any(type(v) is not int for v in frame["logical_canvas"]+frame["origin"])
                or frame["logical_canvas"] != [width, height] or frame["origin"] != [0, 0]):
            raise ValueError("Source canvas/origin must remain exact")
        if width * height * scale * scale > 4_194_304:
            raise ValueError("output exceeds runtime pixel ceiling")
        source = np.asarray(cells, dtype=np.uint16).reshape(height, width)
        if not (source < 256).any():
            raise ValueError("empty Source")
        raw_path, raw_data = checked(frame["parent_raw"], base)
        if len(raw_data) > 32 * 1024 * 1024:
            raise ValueError("raw exceeds32MiB")
        with Image.open(io.BytesIO(raw_data)) as opened:
            if opened.format != "PNG" or opened.width * opened.height > 4_194_304:
                raise ValueError("parent needs bounded PNG")
            raw = opened.convert("RGBA")
        if raw.getchannel("A").getextrema()[0] != 0:
            raise ValueError("parent must have actual transparent alpha")
        grid = frame["atlas_grid"]
        if (type(grid) is not dict or set(grid) != {"columns", "rows", "column", "row"}
                or any(type(v) is not int for v in grid.values())):
            raise ValueError("exact integer atlas_grid required")
        cols, rows, col, row = (grid[k] for k in ("columns", "rows", "column", "row"))
        if not (1 <= cols <= 64 and 1 <= rows <= 64 and 0 <= col < cols and 0 <= row < rows):
            raise ValueError("invalid atlas grid")
        if Fraction(raw.width, cols * width) != Fraction(raw.height, rows * height):
            raise ValueError("grid aspect differs from logical canvas")
        bounds = frame["raw_painted_bounds"]
        if type(bounds) is not list or len(bounds) != 4 or any(type(v) is not int for v in bounds):
            raise ValueError("raw painted bounds need integer4")
        l, t, r, b = bounds
        if not (Fraction(col*raw.width, cols) <= l < r <= Fraction((col+1)*raw.width, cols)
                and Fraction(row*raw.height, rows) <= t < b <= Fraction((row+1)*raw.height, rows)):
            raise ValueError("painted bounds exceed predeclared cell")
        # Alignment is the actual whole body's threshold bounds within the
        # predeclared atlas cell, never a caller-chosen crop that hides artwork.
        cell_l, cell_t = col*raw.width//cols, row*raw.height//rows
        cell_r = ((col+1)*raw.width+cols-1)//cols
        cell_b = ((row+1)*raw.height+rows-1)//rows
        cell_alpha = np.asarray(raw.getchannel("A"))[cell_t:cell_b, cell_l:cell_r]
        raw_y, raw_x = np.nonzero(cell_alpha >= 128)
        actual_bounds = ([int(raw_x.min())+cell_l, int(raw_y.min())+cell_t,
                          int(raw_x.max()+1)+cell_l, int(raw_y.max()+1)+cell_t] if len(raw_x) else [])
        if bounds != actual_bounds:
            raise ValueError("declared painted bounds differ from actual whole-cell alpha>=128")
        ys, xs = np.nonzero(source < 256)
        sl, st, sr, sb = int(xs.min()), int(ys.min()), int(xs.max()+1), int(ys.max()+1)
        ax, ay = (r-l)/((sr-sl)*scale), (b-t)/((sb-st)*scale)
        affine = [ax, 0, l-ax*sl*scale, 0, ay, t-ay*st*scale]
        registered = np.array(raw.transform((width*scale, height*scale), Image.Transform.AFFINE,
                                           affine, Image.Resampling.BICUBIC))
        occupied = up(source < 256, scale)
        trusted = (registered[:, :, 3] >= 128) & occupied
        if trusted.sum() / occupied.sum() < 0.7:
            raise ValueError("most Source support lacks generated RGB; refusing relabel")
        if not np.any(registered[trusted, :3] != registered[trusted, :3][0]):
            raise ValueError("parent contains no generated spatial RGB variation")
        rgb, gaps = nearest_generated_fill(registered[:, :, :3], trusted, occupied)
        loaded.append(dict(frame=frame, source=source, rgb=rgb.astype(np.float64), affine=affine,
                           gaps=gaps, trusted=int(trusted.sum()), source_bounds=[sl, st, sr, sb]))
        inputs[str(source_path)] = sha(source_data)
        inputs[str(raw_path)] = sha(raw_data)
    sources = np.stack([item["source"] for item in loaded])
    common = np.all(sources == sources[0], axis=0) & (sources[0] < 256)
    changing = np.any(sources != sources[0], axis=0)
    common_pixels = up(common, scale)
    moving_weight = inner_weight(up(changing, scale), feather*scale)[:, :, None]
    if not common.any() or not changing.any():
        raise ValueError("family needs both stationary and genuinely changing Source regions")
    shared = np.median(np.stack([item["rgb"] for item in loaded]), axis=0)
    source0_rgb = palette[np.minimum(sources[0], 255)]
    blue0 = (source0_rgb[:, :, 2].astype(int) > source0_rgb[:, :, 0].astype(int)+4) & (source0_rgb[:, :, 2].astype(int) > source0_rgb[:, :, 1].astype(int)+4)
    backing_sample = common & ~blue0
    backing_gain, backing_target, backing_raw = region_gain(source0_rgb[backing_sample], shared[up(backing_sample, scale)], "backing")
    shared = np.clip(shared * backing_gain, 0, 255)
    outputs, reports = [], []
    for item in loaded:
        source, rgb = item["source"], item["rgb"]
        source_rgb = palette[np.minimum(source, 255)]
        values = source_rgb.astype(int)
        warm = (source < 256) & changing & (values[:, :, 0] >= 32) & (values[:, :, 0] > values[:, :, 1]*1.15) & (values[:, :, 0] > values[:, :, 2]*1.15)
        gain, target_mean, raw_mean = region_gain(source_rgb[warm], rgb[up(warm, scale)], "moving warm")
        moving = np.clip(rgb * gain, 0, 255)
        result = np.rint(shared*(1-moving_weight) + moving*moving_weight).astype(np.uint8)
        blue = (source < 256) & (values[:, :, 2] > values[:, :, 0]+4) & (values[:, :, 2] > values[:, :, 1]+4)
        cue_pixels = up(blue, scale)
        exact_cues = up(source_rgb, scale)
        result[cue_pixels] = exact_cues[cue_pixels]
        occupied = up(source < 256, scale)
        rgba = np.zeros((*occupied.shape, 4), dtype=np.uint8)
        rgba[:, :, :3][occupied] = result[occupied]
        rgba[:, :, 3][occupied] = 255
        internal = 0
        for y, x in np.argwhere(source < 256):
            cell = result[y*scale:(y+1)*scale, x*scale:(x+1)*scale]
            internal += int(np.any(cell != cell[0, 0], axis=2).sum())
        if internal == 0:
            raise ValueError("no generated spatial detail remains")
        outputs.append(rgba)
        reports.append(dict(asset=item["frame"]["asset"], logical_canvas=[shape[1], shape[0]], origin=[0, 0],
                            Source_painted_cells=int((source < 256).sum()), registered_generated_pixels=item["trusted"],
                            nearest_generated_donor_gap_pixels=item["gaps"], fullcanvas_output_to_raw_affine=item["affine"],
                            Source_painted_bounds=item["source_bounds"], warm_Source_sample_cells=int(warm.sum()),
                            warm_material_RGB_gain=gain.tolist(), warm_Source_sample_mean=target_mean.tolist(),
                            warm_generated_sample_mean_before_gain=raw_mean.tolist(), functional_blue_Source_RGB_cells=int(blue.sum()),
                            internally_nonconstant_generated_RGB_pixels=internal))
    for rgba in outputs[1:]:
        if not np.array_equal(rgba[common_pixels], outputs[0][common_pixels]):
            raise AssertionError("stationary Source backing differs between frames")
    report = dict(method=METHOD, output_class="DERIVED_GENERATED_RGB_GEOMETRY_AND_BROAD_MATERIAL_CLEANUP",
                  input_hashes=inputs, output_scale=scale, Source_stationary_cells=int(common.sum()),
                  Source_changing_union_cells=int(changing.sum()), shared_backing_RGB_gain=backing_gain.tolist(),
                  backing_Source_sample_mean=backing_target.tolist(), backing_generated_sample_mean=backing_raw.tolist(),
                  per_Source_cell_RGB_reconstruction=False, generated_RGB_controls_continuous_form=True,
                  frames=reports, decoder_module=dict(path=str(Path(hd_frame_policy.__file__).resolve()), sha256=sha(Path(hd_frame_policy.__file__).read_bytes())),
                  python_version=platform.python_version(), python_implementation=platform.python_implementation(),
                  numpy_version=np.__version__, pillow_version=PILLOW_VERSION)
    return outputs, report


def run_recipe(recipe_path, output):
    recipe_path, output = Path(recipe_path), Path(output)
    if output.exists():
        raise ValueError("output exists; never overwrite prior artwork")
    data = recipe_path.read_bytes()
    recipe = json.loads(data)
    arrays, report = render_family(recipe, recipe_path.resolve().parent)
    payloads = []
    for pixels, frame in zip(arrays, report["frames"]):
        buffer = io.BytesIO()
        Image.fromarray(pixels).save(buffer, format="PNG", compress_level=9)
        png = buffer.getvalue()
        name = frame["asset"]+"-derived.png"
        frame["output"] = dict(file=name, sha256=sha(png), bytes=len(png), RGBA_sha256=sha(pixels.tobytes()))
        payloads.append((name, png))
    report["execution"] = dict(status="success", method=METHOD, recipe_sha256=sha(data), tool_sha256=sha(Path(__file__).read_bytes()),
                               source_sha256={f["asset"]: f["source"]["sha256"] for f in recipe["frames"]},
                               parent_raw_sha256=sorted({f["parent_raw"]["sha256"] for f in recipe["frames"]}),
                               output_sha256={f["asset"]: f["output"]["sha256"] for f in report["frames"]})
    output.mkdir(parents=True)
    for name, png in payloads:
        (output/name).write_bytes(png)
    (output/"derived-provenance.json").write_text(json.dumps(report, indent=2, sort_keys=True)+"\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    parser.add_argument("output_new_directory", type=Path)
    args = parser.parse_args()
    report = run_recipe(args.recipe, args.output_new_directory)
    print(json.dumps(dict(execution=report["execution"], method=METHOD)))


if __name__ == "__main__":
    main()
