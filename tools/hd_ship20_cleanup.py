"""Reproduce a complete SHIP20 family using reviewed RGB and Original-tip steps.

This is a portable dispatcher, not a new pixel algorithm. It calls the unchanged
DSHP complete-family renderer and functional Original retention helper in memory.
All paths in the geometry recipe resolve against the outer recipe's directory.
No artwork approval, engine operation or registration is performed.
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
import hd_other_functional_cleanup as functional

METHOD = "derived-SHIP20-complete4-reviewed-generated-RGB-and-Original-tips-v1"
FUNCTIONAL_SHA = "f8078284e300947aec4d2c9e70cbc7198fa3cb5d34de6b36c07cacc5f3820a84"
ASSETS = ["200c4", "200c5", "200c6", "200c7"]


def digest(payload):
    return hashlib.sha256(payload).hexdigest()


def dependency_pins():
    path = Path(functional.__file__).resolve()
    if digest(path.read_bytes()) != FUNCTIONAL_SHA:
        raise ValueError("functional Original implementation changed")
    return {"functional_Original_tool": {"path": "tools/hd_other_functional_cleanup.py",
                                        "sha256": FUNCTIONAL_SHA},
            **functional.dependency_pins()}


def run_recipe(recipe_path, output):
    recipe_path, output = Path(recipe_path).resolve(), Path(output)
    if output.exists():
        raise ValueError("fresh absent output directory required")
    dependencies = dependency_pins()
    rb = recipe_path.read_bytes()
    recipe = json.loads(rb)
    if (type(recipe) is not dict or set(recipe) != {
            "format_version", "method", "geometry_recipe", "functional_original_cells",
            "expected_output_sha256"}
            or type(recipe["format_version"]) is not int or recipe["format_version"] != 1
            or recipe["method"] != METHOD):
        raise ValueError("exact SHIP20 dispatcher recipe fields/version required")
    geometry = recipe["geometry_recipe"]
    frames = geometry.get("frames") if type(geometry) is dict else None
    if (type(frames) is not list or len(frames) != 4
            or any(type(f) is not dict for f in frames)
            or [f.get("asset") for f in frames] != ASSETS):
        raise ValueError("complete4 exact SHIP20 frame order required")
    selected = recipe["functional_original_cells"]
    expected = recipe["expected_output_sha256"]
    if (type(selected) is not dict or set(selected) != set(ASSETS)
            or type(expected) is not dict or set(expected) != set(ASSETS)
            or any(type(v) is not str or len(v) != 64
                   or any(c not in "0123456789abcdef" for c in v)
                   for v in expected.values())):
        raise ValueError("complete4 functional cells and expected PNG hashes required")

    # Validate the complete selection before invoking the existing renderer.
    sources = []
    for frame in frames:
        _, sb = functional.base.checked(frame["source"], recipe_path.parent)
        w, h, cells = functional.base._indices(sb)
        if (w, h) != (48, 56) or frame.get("origin") != [0, 0]:
            raise ValueError("exact native48x56/origin0 SHIP20 canvas required")
        source = np.asarray(cells, np.uint16).reshape(h, w)
        points = selected[frame["asset"]]
        if (type(points) is not list or len(points) > 64
                or any(type(xy) is not list or len(xy) != 2
                       or any(type(v) is not int for v in xy)
                       or not 0 <= xy[0] < w or not 0 <= xy[1] < h
                       or int(source[xy[1], xy[0]]) not in (82, 83, 84)
                       for xy in points)
                or points != sorted(points)
                or len({tuple(xy) for xy in points}) != len(points)):
            raise ValueError("sorted unique painted Source yellow82..84 cells required")
        sources.append(source)

    arrays, geometry_report = functional.base.render_family(geometry, recipe_path.parent)
    _, pb = functional.base.checked(geometry["palette"], recipe_path.parent)
    p6 = np.frombuffer(pb, np.uint8).reshape(256, 3).astype(np.uint16)
    palette = ((p6 << 2) | (p6 >> 4)).astype(np.uint8)
    payloads, reports = [], []
    for frame, source, rgba in zip(frames, sources, arrays):
        asset = frame["asset"]
        points = selected[asset]
        if points:
            out, retention = functional.retain_functional_original(rgba, source, palette, points)
            if not np.array_equal(out[:, :, 3], rgba[:, :, 3]):
                raise ValueError("functional selection changed SourceScale4 alpha")
        else:
            out = rgba
            retention = {"cells": [], "actual_Original_Scale4_RGBA_samples": 0,
                         "outside_explicit_footprints_RGBA_exact": True}
        encoded = io.BytesIO()
        Image.fromarray(out).save(encoded, format="PNG", compress_level=9)
        png = encoded.getvalue()
        if digest(png) != expected[asset]:
            raise ValueError(f"reviewed PNG not reproduced: {asset}")
        payloads.append((asset, png))
        reports.append({"asset": asset, "functional_Original": retention,
                        "sha256": digest(png), "RGBA_sha256": digest(out.tobytes())})

    # Reject changed input/implementation bytes before the first output write.
    if recipe_path.read_bytes() != rb or dependency_pins() != dependencies:
        raise ValueError("recipe or implementation changed during reconstruction")
    for frame in frames:
        functional.base.checked(frame["source"], recipe_path.parent)
        functional.base.checked(frame["raw_png"], recipe_path.parent)
    functional.base.checked(geometry["palette"], recipe_path.parent)
    execution = {"status": "success", "method": METHOD,
                 "recipe_sha256": digest(rb), "tool_sha256": digest(Path(__file__).read_bytes()),
                 "source_sha256": {f["asset"]: f["source"]["sha256"] for f in frames},
                 "parent_raw_sha256": sorted({f["raw_png"]["sha256"] for f in frames}),
                 "output_sha256": {a: digest(b) for a, b in payloads}}
    report = {"execution": execution, "dependencies": dependencies,
              "geometry": geometry_report, "frames": reports,
              "Original_tip_cells_are_not_generated_HD": True,
              "actual_dispatcher_calls": 1, "actual_geometry_renderer_calls": 1,
              "actual_pure_retention_calls": sum(bool(selected[a]) for a in ASSETS),
              "python_version": sys.version, "numpy_version": np.__version__,
              "pillow_version": PILLOW_VERSION,
              "scope": "Portable byte-exact replay only; no new art/engine/QA/context approval."}
    output.mkdir(parents=True)
    for asset, png in payloads:
        with (output / f"{asset}-derived.png").open("xb") as stream:
            stream.write(png)
    with (output / "derived-provenance.json").open("x") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    parser.add_argument("fresh_output", type=Path)
    args = parser.parse_args()
    print(json.dumps(run_recipe(args.recipe, args.fresh_output)["execution"], sort_keys=True))


if __name__ == "__main__":
    main()
