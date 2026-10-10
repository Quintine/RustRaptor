#!/usr/bin/env python3
"""Package imagegen sources into palette SD/HD game footprints and synthesize WAVs.

This performs deterministic cropping/resampling/palette conversion, not image
generation. The three imagegen originals remain beside the packaged local files.
"""
import argparse
import hashlib
import json
import math
import random
import struct
import wave
from pathlib import Path
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent


def palette_image(path):
    raw = path.read_bytes()
    if len(raw) != 768:
        raise ValueError("expected the original 768-byte VGA palette")
    colors = [(min(value, 63) << 2) | (min(value, 63) >> 4) for value in raw]
    palette = Image.new("P", (1, 1))
    palette.putpalette(colors)
    return palette, colors


def sd(image, size, palette):
    image = image.convert("RGBA").resize(size, Image.Resampling.LANCZOS)
    alpha = image.getchannel("A").point(lambda a: 255 if a >= 128 else 0)
    # Use one full-canvas palette pass before splitting terrain, so tile borders
    # receive identical context and no independent quantizer creates seams.
    rgb = image.convert("RGB").quantize(palette=palette, dither=Image.Dither.NONE).convert("RGBA")
    rgb.putalpha(alpha)
    return rgb


def wav(name, duration, notes, mode="tone"):
    sample_rate = 22050
    rng = random.Random(7053 + sum(map(ord, name)))
    values = bytearray()
    count = int(duration * sample_rate)
    for frame in range(count):
        t = frame / sample_rate
        section = min(len(notes) - 1, int(t / duration * len(notes)))
        frequency = notes[section]
        local = (t / duration * len(notes)) % 1
        envelope = min(1, local * 18) * (1 - local) ** 0.8
        signal = math.sin(2 * math.pi * frequency * t)
        signal += 0.24 * math.sin(2 * math.pi * frequency * 2 * t)
        if mode == "metal":
            signal += 0.45 * rng.uniform(-1, 1) * math.exp(-t * 15)
            signal += 0.3 * math.sin(2 * math.pi * 817 * t) * math.exp(-t * 10)
        if mode == "alarm":
            signal += 0.25 * math.sin(2 * math.pi * frequency * 0.5 * t)
        value = max(-32767, min(32767, int(signal * envelope * 7200)))
        values += struct.pack("<h", value)
    path = ROOT / "audio" / (name + ".wav")
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(values)
    return {"file": str(path.relative_to(ROOT)), "samples": count, "seconds": duration,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--palette", type=Path, default=ROOT.parents[2] / "data/misc/PALETTE_DAT")
    args = parser.parse_args()
    art = ROOT / "art"
    (ROOT / "audio").mkdir(exist_ok=True)
    palette, colors = palette_image(args.palette)
    terrain = Image.open(art / "terrain-source-hd.png").convert("RGBA")
    terrain_hd = terrain.resize((1152, 1536), Image.Resampling.LANCZOS)
    terrain_sd = sd(terrain, (288, 384), palette)
    tile_count = 0
    for reverse in (False, True):
        hd_map = ImageOps.flip(terrain_hd) if reverse else terrain_hd
        sd_map = ImageOps.flip(terrain_sd) if reverse else terrain_sd
        for row in range(12):
            for col in range(9):
                number = tile_count
                hd_tile = hd_map.crop((col * 128, row * 128, (col + 1) * 128, (row + 1) * 128))
                sd_tile = sd_map.crop((col * 32, row * 32, (col + 1) * 32, (row + 1) * 32))
                hd_tile.save(art / f"tile_{number:03}_hd.png")
                sd_tile.save(art / f"tile_{number:03}_sd.png")
                tile_count += 1
    # Ping-pong ordering makes both repetition boundaries identical without
    # painting over generated artwork. Validate every seam across the period.
    assert terrain_sd.crop((0, 383, 288, 384)).tobytes() == ImageOps.flip(terrain_sd).crop((0, 0, 288, 1)).tobytes()
    assert ImageOps.flip(terrain_sd).crop((0, 383, 288, 384)).tobytes() == terrain_sd.crop((0, 0, 288, 1)).tobytes()
    assert terrain_hd.crop((0, 1535, 1152, 1536)).tobytes() == ImageOps.flip(terrain_hd).crop((0, 0, 1152, 1)).tobytes()
    terrain_sd.save(art / "terrain-preview-sd.png")
    terrain_hd.save(art / "terrain-preview-hd.png")
    briefing = Image.open(art / "briefing-source-hd.png").convert("RGBA")
    sd(briefing, (320, 200), palette).save(art / "briefing_sd.png")
    briefing.resize((1280, 800), Image.Resampling.LANCZOS).save(art / "briefing_hd.png")
    convoy = Image.open(art / "convoy-source-hd.png").convert("RGBA")
    # Use the generated alpha bounds, then preserve its complete silhouette in
    # the logical canvas with a small transparent border. This is packaging.
    bounds = convoy.getchannel("A").getbbox()
    if bounds is None:
        raise ValueError("generated convoy has no opaque pixels")
    convoy = convoy.crop(bounds)
    hd_canvas = Image.new("RGBA", (96, 160))
    fitted = ImageOps.contain(convoy, (88, 152), Image.Resampling.LANCZOS)
    hd_canvas.alpha_composite(fitted, ((96-fitted.width)//2, (160-fitted.height)//2))
    hd_canvas.save(art / "convoy_hd.png")
    sd(hd_canvas, (24, 40), palette).save(art / "convoy_sd.png")
    audio = {
        "approach": wav("approach", 0.85, [146, 220, 293]),
        "convoy_alarm": wav("convoy_alarm", 0.75, [392, 294, 392], "alarm"),
        "boss_alarm": wav("boss_alarm", 1.1, [220, 165, 110], "alarm"),
        "cargo_salvage": wav("cargo_salvage", 0.5, [440, 587, 740], "metal"),
        "victory": wav("victory", 1.2, [294, 370, 440, 588]),
    }
    report = {"tile_count": tile_count, "tile_logical_size": [32, 32],
              "hd_tile_size": [128, 128], "sd_palette_colors": 256,
              "palette_sha256": hashlib.sha256(args.palette.read_bytes()).hexdigest(),
              "vertical_repeat": "12 rows forward + 12 rows reflected; matching boundary pixels",
              "seam_checks_passed": True,
              "convoy_transparent_pixels": sum(1 for a in Image.open(art / "convoy_sd.png").getchannel("A").tobytes() if a == 0),
              "audio": audio}
    palette_colors = set(tuple(colors[i:i+3]) for i in range(0, 768, 3))
    actual_colors = set(tuple(terrain_sd.convert("RGB").tobytes()[i:i+3]) for i in range(0, 288*384*3, 3))
    assert actual_colors <= palette_colors
    report["actual_sd_unique_colors"] = len(actual_colors)
    report["sd_pixels_match_original_palette"] = True
    report["sources"] = {path.name: {"size": Image.open(path).size,
                          "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                          for path in art.glob("*-source-hd.png")}
    (ROOT / "asset-report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"Packaged {tile_count} SD/HD tiles, briefing/convoy art and {len(audio)} WAVs")


if __name__ == "__main__":
    main()
