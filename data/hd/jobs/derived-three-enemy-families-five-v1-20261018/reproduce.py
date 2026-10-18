"""Replay a checked batch of existing boss cleanup recipes without new pixel math.

Each frame is passed to the hash-bound hd_boss_cleanup.run_recipe unchanged.
This dispatcher records actual subruns and binds one outer portable recipe.
It does not approve artwork or register assets.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
from pathlib import Path
import sys

METHOD = "derived-generated-boss-source-geometry-batch-v1"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return (type(value) is str and len(value) == 64
            and all(c in "0123456789abcdef" for c in value))


def contained(base, value):
    if type(value) is not str or not value or "\\" in value:
        raise ValueError("expected portable relative path")
    path = Path(value)
    if path.is_absolute() or any(part in (".", "..") for part in path.parts):
        raise ValueError("expected contained relative path")
    result = (base / path).resolve()
    if not result.is_relative_to(base.resolve()) or not result.is_file():
        raise ValueError("missing or escaped input")
    return result


def checked_ref(base, value):
    if type(value) is not dict or set(value) != {"path", "sha256"} or not digest(value["sha256"]):
        raise ValueError("expected path/sha256 binding")
    path = contained(base, value["path"])
    if sha(path) != value["sha256"]:
        raise ValueError("input hash mismatch")
    return path


def plan(recipe_path, project):
    recipe_path = Path(recipe_path).resolve()
    recipe = json.loads(recipe_path.read_bytes())
    if (type(recipe) is not dict or set(recipe) != {
            "format_version", "kind", "method", "cleanup_tool", "decoder", "frames"}
            or type(recipe["format_version"]) is not int or recipe["format_version"] != 1
            or recipe["kind"] != "boss_cleanup_reproduce_batch" or recipe["method"] != METHOD):
        raise ValueError("unsupported batch recipe")
    project = Path(project).resolve()
    for field, expected in [("cleanup_tool", "tools/hd_boss_cleanup.py"),
                            ("decoder", "tools/hd_frame_policy.py")]:
        if type(recipe[field]) is not dict or recipe[field].get("path") != expected:
            raise ValueError("unsupported cleanup implementation")
        checked_ref(project, recipe[field])
    frames = recipe["frames"]
    if type(frames) is not list or not 1 <= len(frames) <= 32:
        raise ValueError("expected bounded nonempty frame list")
    planned, seen = [], set()
    for frame in frames:
        if type(frame) is not dict or set(frame) != {"asset", "recipe", "expected_output_sha256"}:
            raise ValueError("invalid batch frame")
        asset = frame["asset"]
        if (type(asset) is not str or not 1 <= len(asset) <= 8
                or any(c not in "0123456789abcdef" for c in asset) or asset in seen
                or not digest(frame["expected_output_sha256"])):
            raise ValueError("invalid or duplicate asset/output binding")
        seen.add(asset)
        subpath = checked_ref(recipe_path.parent, frame["recipe"])
        sub = json.loads(subpath.read_bytes())
        if type(sub) is not dict or sub.get("asset") != asset:
            raise ValueError("subrecipe asset mismatch")
        # Validate all declared input bodies before creating any output directory.
        for key in ("source", "palette", "parent_raw"):
            value = sub.get(key)
            if type(value) is not dict or set(value) != {"path", "sha256"} or not digest(value["sha256"]):
                raise ValueError("invalid subrecipe input binding")
            p = Path(value["path"])
            if not p.is_absolute():
                p = subpath.parent / p
            if not p.is_file() or sha(p) != value["sha256"]:
                raise ValueError("subrecipe input hash mismatch")
        planned.append((frame, subpath, sub))
    return recipe, planned


def run_batch(recipe_path, output, project):
    recipe_path, output, project = Path(recipe_path).resolve(), Path(output), Path(project).resolve()
    if output.exists():
        raise ValueError("output exists; do not overwrite old outputs")
    recipe, planned = plan(recipe_path, project)
    sys.path.insert(0, str(project / "tools"))
    cleanup = importlib.import_module("hd_boss_cleanup")
    decoder = importlib.import_module("hd_frame_policy")
    if (Path(cleanup.__file__).resolve() != project / "tools/hd_boss_cleanup.py"
            or Path(decoder.__file__).resolve() != project / "tools/hd_frame_policy.py"
            or sha(cleanup.__file__) != recipe["cleanup_tool"]["sha256"]
            or sha(decoder.__file__) != recipe["decoder"]["sha256"]):
        raise ValueError("loaded implementation differs from bound tools")
    output.mkdir(parents=True)
    subruns, sources, parents, outputs = [], {}, set(), {}
    for frame, subpath, sub in planned:
        asset = frame["asset"]
        destination = output / asset
        report = cleanup.run_recipe(subpath, destination)
        png = destination / f"{asset}-derived.png"
        actual = sha(png)
        if actual != frame["expected_output_sha256"]:
            raise ValueError(f"accepted PNG not reproduced: {asset}")
        if report["execution"]["output_sha256"] != {asset: actual}:
            raise ValueError("subrun output receipt mismatch")
        sources[asset] = sub["source"]["sha256"]
        parents.add(sub["parent_raw"]["sha256"])
        outputs[asset] = actual
        provenance = destination / "derived-provenance.json"
        subruns.append({"asset": asset, "recipe": frame["recipe"],
                        "execution": report["execution"],
                        "provenance": {"path": f"{asset}/derived-provenance.json", "sha256": sha(provenance)}})
    result = {"format_version": 1, "kind": "boss_cleanup_actual_batch_execution",
              "execution": {"status": "success", "method": METHOD,
                  "recipe_sha256": sha(recipe_path), "tool_sha256": sha(__file__),
                  "source_sha256": sources, "parent_raw_sha256": sorted(parents),
                  "output_sha256": outputs},
              "actual_dispatcher_calls": 1, "actual_cleanup_subruns": len(subruns),
              "subruns": subruns, "cleanup_tool": recipe["cleanup_tool"], "decoder": recipe["decoder"],
              "scope": "Bookkeeping replay only; existing cleanup pixel algorithm unchanged; no approval/registration."}
    (output / "batch-execution.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    parser.add_argument("output_new_directory", type=Path)
    parser.add_argument("project", type=Path)
    args = parser.parse_args()
    report = run_batch(args.recipe, args.output_new_directory, args.project)
    print(json.dumps(report["execution"], sort_keys=True))


if __name__ == "__main__":
    main()
