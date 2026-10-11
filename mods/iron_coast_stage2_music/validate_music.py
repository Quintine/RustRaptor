#!/usr/bin/env python3
"""Reproduce native FM QA/previews outside this mod without changing selected mods.

Run `python3 mods/iron_coast_stage2_music/validate_music.py` from RustRaptor or
any directory. Requires the local Rust compiler and original GENMIDI catalog.
Only generated QA/binaries go to the chosen output directory (ignored default).
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


PACKAGE = Path(__file__).resolve().parent
REPO = PACKAGE.parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=REPO / "data")
    parser.add_argument("--output", type=Path, default=REPO.parent / ".reference/iron-coast-stage2-music")
    parser.add_argument("--skip-build", action="store_true",
                        help="Reuse a previously recorded Cargo artifact pair in --output; require unchanged bytes")
    args = parser.parse_args()
    data, output = args.data.resolve(), args.output.resolve()
    if output == PACKAGE or PACKAGE in output.parents:
        parser.error("WAV previews/QA must remain outside the hashed mod package")
    output.mkdir(parents=True, exist_ok=True)
    pair_file = output / "cargo-artifact-library-pair.json"
    if not args.skip_build:
        build = subprocess.run(["cargo", "build", "--locked", "--release", "--no-default-features", "--lib",
                                "--message-format=json", "--manifest-path", str(REPO / "Cargo.toml")],
                               check=True, text=True, stdout=subprocess.PIPE)
        records = [json.loads(line) for line in build.stdout.splitlines() if line.strip()]
        artifacts = {}
        for name in ["raptor_replica", "serde_json"]:
            matches = {Path(filename).resolve()
                       for record in records if record.get("reason") == "compiler-artifact"
                       and record.get("target", {}).get("name") == name
                       and "lib" in record.get("target", {}).get("kind", [])
                       for filename in record.get("filenames", []) if filename.endswith(".rlib")}
            if len(matches) != 1:
                parser.error(f"Cargo must report exactly one active {name} library; found {sorted(matches)}")
            artifact = matches.pop()
            artifacts[name] = {"path": str(artifact), "sha256": digest(artifact)}
        pair = {"selection": "Exact active compiler-artifact filenames from Cargo JSON; no mtime inference",
                "profile": "release", "features": "no-default-features", "artifacts": artifacts}
        pair_file.write_text(json.dumps(pair, indent=2) + "\n")
    else:
        if not pair_file.is_file():
            parser.error("--skip-build requires a prior successful Cargo artifact pair in --output")
        pair = json.loads(pair_file.read_text())
    for name, artifact in pair["artifacts"].items():
        if not Path(artifact["path"]).is_file() or digest(Path(artifact["path"])) != artifact["sha256"]:
            parser.error(f"Recorded {name} artifact changed; rerun without --skip-build")
    library = Path(pair["artifacts"]["raptor_replica"]["path"])
    dependencies = REPO / "target/release/deps"
    serde = Path(pair["artifacts"]["serde_json"]["path"])
    # Copy exact library snapshots to the ignored QA folder before rustc so
    # simultaneous engine builds cannot replace the direct --extern files.
    stable_library, stable_serde = output / "libraptor_replica.rlib", output / "libserde_json.rlib"
    stable_library.write_bytes(library.read_bytes()); stable_serde.write_bytes(serde.read_bytes())
    assert digest(stable_library) == pair["artifacts"]["raptor_replica"]["sha256"]
    assert digest(stable_serde) == pair["artifacts"]["serde_json"]["sha256"]
    binary = output / "validate-music"
    subprocess.run(["rustc", "--edition=2024", "-O", str(PACKAGE / "validate_music.rs"),
                    "--extern", f"raptor_replica={stable_library}", "--extern", f"serde_json={stable_serde}",
                    "-L", f"dependency={dependencies}", "-o", str(binary)], check=True)
    subprocess.run([str(binary), str(data), str(REPO / "mods"), str(output)], check=True)
    provenance = json.loads((PACKAGE / "provenance.json").read_text())
    report = json.loads((output / "native-validation.json").read_text())
    for native, authored in zip(report["tracks"], provenance["tracks"]):
        for name in ["duration_ticks", "notes", "events"]:
            assert native[name] == authored[name], (native["track"], name)
        native["score_sha256"] = digest(PACKAGE / authored["file"])
        assert native["score_sha256"] == authored["sha256"]
        native["preview_sha256"] = digest(Path(native["preview"]))
        native["loop_boundary_sha256"] = digest(Path(native["loop_boundary_preview"]))
        native["sections"] = [{**section,
            "start_seconds": section["first_bar"] * 240 / authored["tempo_bpm"],
            "duration_seconds": section["bars"] * 240 / authored["tempo_bpm"]}
            for section in authored["sections"]]
    report["native_library_sha256"] = digest(stable_library)
    report["cargo_artifact_library_pair"] = pair
    report["native_sources"] = {str(path.relative_to(REPO)): digest(path)
        for path in [REPO / "src/audio.rs", REPO / "src/audio/opl3.rs", REPO / "src/sound.rs"]}
    report["validator_recipe_sha256"] = digest(PACKAGE / "validate_music.py")
    report["validator_rust_sha256"] = digest(PACKAGE / "validate_music.rs")
    report["genmidi_sha256"] = digest(data / "misc/GENMIDI_OP2")
    (output / "native-validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"Native QA and all six WAV previews: {output}")


if __name__ == "__main__":
    main()
