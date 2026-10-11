#!/usr/bin/env python3
"""Export the preserved imagegen briefing master to the shared SD/HD canvas."""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--palette", type=Path, default=ROOT.parents[1] / "data/misc/PALETTE_DAT")
    args = parser.parse_args()
    raw = args.palette.read_bytes()
    if len(raw) != 768:
        raise ValueError("Expected original VGA palette")
    colors = [(min(v, 63) << 2) | (min(v, 63) >> 4) for v in raw]
    # Ordinary PNG artwork excludes the engine's cycling and effect indices.
    palette = Image.new("P", (1, 1))
    palette.putpalette(colors[:720] + colors[:3] * 16)
    art = ROOT / "art"
    master = Image.open(art / "briefing-master.png").convert("RGBA")
    if master.getchannel("A").getextrema() != (255, 255):
        raise ValueError("Briefing must be opaque")
    hd = ImageOps.fit(master, (1280, 800), method=Image.Resampling.LANCZOS)
    sd = hd.resize((320, 200), Image.Resampling.LANCZOS).convert("RGB").quantize(
        palette=palette, dither=Image.Dither.NONE).convert("RGBA")
    hd.save(art / "briefing_hd.png")
    sd.save(art / "briefing_sd.png")
    files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in
             [art / "prompt.txt", art / "briefing-master.png", art / "briefing_hd.png", art / "briefing_sd.png"]}
    provenance = {
        "generator": "built-in imagegen", "generated_date": "2026-10-11",
        "reference": "Iron Coast Stage 1 briefing used as style reference only",
        "original_artwork": True, "logical_canvas": [320, 200], "hd_canvas": [1280, 800],
        "processing": "Preserved opaque master; centered aspect fit and Lanczos export; SD noncycling VGA palette without dithering",
        "sha256": files
    }
    (art / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")

if __name__ == "__main__":
    main()
