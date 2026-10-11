#!/usr/bin/env python3
"""Reproduce isolated Stage 2 package validation and public indexed/audio review."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    data = (args.data or root / "data").resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    packages = ["iron_coast_railburst", "iron_coast_depth_charge"]
    subprocess.run(["cargo", "build", "--locked", "--no-default-features", "--lib", "--bin", "raptor-rust"], cwd=root, check=True)
    deps = root / "target/debug/deps"
    suffix = ".exe" if os.name == "nt" else ""
    executable = output / ("native_review" + suffix)
    command = ["rustc", "--edition=2024", str(Path(__file__).with_name("native_review.rs")), "-L", f"dependency={deps}", "-o", str(executable)]
    libraries = {}
    for name in ["raptor_replica", "image", "serde_json"]:
        library = root / "target/debug/libraptor_replica.rlib" if name == "raptor_replica" else max(deps.glob(f"lib{name}-*.rlib"), key=lambda path: path.stat().st_mtime_ns)
        command += ["--extern", f"{name}={library}"]
        libraries[name] = {"path": str(library), "sha256": hashlib.sha256(library.read_bytes()).hexdigest()}
    subprocess.run(command, cwd=root, check=True)
    cases = []
    with tempfile.TemporaryDirectory(prefix="iron-coast-stage2-review-") as folder:
        frozen = Path(folder)
        for package in packages:
            shutil.copytree(root / "mods" / package, frozen / package)
        for selected in [[packages[0]], [packages[1]], packages]:
            result = subprocess.run([str(root / ("target/debug/raptor-rust" + suffix)), "--data", str(data), "--mods", str(frozen), "--validate-mods", ",".join(selected)], cwd=root, check=True, capture_output=True, text=True)
            print(result.stdout, end="")
            cases.append({"enabled": selected, "stdout": result.stdout.strip(), "stderr": result.stderr.strip(), "exit_code": result.returncode})
        subprocess.run([str(executable), str(data), str(frozen), str(output)], cwd=root, check=True)
    (output / "build-bindings.json").write_text(json.dumps({"libraries": libraries, "review_source_sha256": hashlib.sha256(Path(__file__).with_name("native_review.rs").read_bytes()).hexdigest(), "validation_cases": cases, "scope": "Frozen package copies; public asset, indexed Canvas and audio APIs; no live desktop or pilot mutations."}, indent=2) + "\n")


if __name__ == "__main__":
    main()
