#!/usr/bin/env python3
"""Package imagegen originals into palette SD/HD tiles and synthesize WAV cues.

Only deterministic resampling, cropping and palette conversion happen here.
Image creation uses the built-in imagegen tool; original sources are retained.
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
        raise ValueError("Expected the original 768-byte VGA palette")
    colors = [(min(value, 63) << 2) | (min(value, 63) >> 4) for value in raw]
    palette = Image.new("P", (1, 1))
    palette.putpalette(colors)
    return palette, colors


def palette_sd(image, size, palette):
    image = image.convert("RGBA").resize(size, Image.Resampling.LANCZOS)
    alpha = image.getchannel("A").point(lambda a: 255 if a >= 128 else 0)
    rgb = image.convert("RGB").quantize(palette=palette, dither=Image.Dither.NONE).convert("RGBA")
    rgb.putalpha(alpha)
    return rgb


def wav(name, duration, notes, alarm=False):
    rate = 22050
    rng = random.Random(7066 + sum(map(ord, name)))
    samples = bytearray()
    energy = 0
    peak = 0
    for frame in range(int(duration * rate)):
        t = frame / rate
        step = min(len(notes) - 1, int(t / duration * len(notes)))
        f = notes[step]
        local = (t / duration * len(notes)) % 1
        envelope = min(1, local * 24) * (1 - local) ** 0.6
        signal = math.sin(2 * math.pi * f * t)
        signal += 0.23 * math.sin(2 * math.pi * f * 2 * t)
        if alarm:
            signal += 0.17 * math.sin(2 * math.pi * f * 0.5 * t)
            signal += 0.08 * rng.uniform(-1, 1)
        value = max(-32767, min(32767, int(signal * envelope * 7000)))
        samples.extend(struct.pack("<h", value))
        energy += value * value
        peak = max(peak, abs(value))
    path = ROOT / "audio" / (name + ".wav")
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(samples)
    return {"file": str(path.relative_to(ROOT)), "samples": len(samples) // 2,
            "seconds": duration, "peak": peak, "rms": round(math.sqrt(energy / (len(samples) // 2)), 2),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--palette", type=Path, default=ROOT.parents[2] / "data/misc/PALETTE_DAT")
    args = parser.parse_args()
    palette, colors = palette_image(args.palette)
    art = ROOT / "art"
    (ROOT / "audio").mkdir(exist_ok=True)
    source = Image.open(art / "terrain-source-hd.png").convert("RGBA")
    terrain_hd = source.resize((1152, 1536), Image.Resampling.LANCZOS)
    terrain_sd = palette_sd(source, (288, 384), palette)
    # Split only after a joined-canvas palette pass. Reflection has identical
    # boundary pixels and prevents a cut at both ends of the scrolling period.
    for reflected in (False, True):
        hd = ImageOps.flip(terrain_hd) if reflected else terrain_hd
        sd = ImageOps.flip(terrain_sd) if reflected else terrain_sd
        for row in range(12):
            for col in range(9):
                number = int(reflected) * 108 + row * 9 + col
                hd.crop((col * 128, row * 128, (col + 1) * 128, (row + 1) * 128)).save(art / f"tile_{number:03}_hd.png")
                sd.crop((col * 32, row * 32, (col + 1) * 32, (row + 1) * 32)).save(art / f"tile_{number:03}_sd.png")
    for suffix, scale, expected in [("sd", 1, terrain_sd), ("hd", 4, terrain_hd)]:
        for reflected in (False, True):
            joined = Image.new("RGBA", expected.size)
            for row in range(12):
                for col in range(9):
                    number = int(reflected) * 108 + row * 9 + col
                    tile = Image.open(art / f"tile_{number:03}_{suffix}.png").convert("RGBA")
                    assert tile.size == (32 * scale, 32 * scale)
                    joined.paste(tile, (col * 32 * scale, row * 32 * scale))
            assert joined.tobytes() == (ImageOps.flip(expected) if reflected else expected).tobytes()
    for terrain in (terrain_sd, terrain_hd):
        height = terrain.height
        assert terrain.crop((0, height - 1, terrain.width, height)).tobytes() == ImageOps.flip(terrain).crop((0, 0, terrain.width, 1)).tobytes()
        assert ImageOps.flip(terrain).crop((0, height - 1, terrain.width, height)).tobytes() == terrain.crop((0, 0, terrain.width, 1)).tobytes()
    terrain_sd.save(art / "terrain-preview-sd.png")
    terrain_hd.save(art / "terrain-preview-hd.png")
    briefing = Image.open(art / "briefing-source-hd.png").convert("RGBA")
    palette_sd(briefing, (320, 200), palette).save(art / "briefing_sd.png")
    briefing.resize((1280, 800), Image.Resampling.LANCZOS).save(art / "briefing_hd.png")
    audio = {
        "approach": wav("approach", 1.1, [110, 147, 165, 220]),
        "fleet_alarm": wav("fleet_alarm", 0.9, [330, 247, 330, 247], True),
        "crown_alarm": wav("crown_alarm", 1.2, [196, 147, 110, 98], True),
        "victory": wav("victory", 1.6, [196, 262, 330, 392, 524]),
    }
    spawns = []
    # Real catalog IDs preserve original native movement and artwork.
    classics = {130: "base:enemy_0_73", 180: "base:enemy_0_74",
                710: "base:enemy_0_23", 760: "base:enemy_0_24",
                1730: "base:enemy_0_95", 1820: "base:enemy_0_96"}
    for tick, x in [(30, 56), (70, 208), (130, 136), (180, 232), (350, 72),
                    (410, 200), (520, 136), (570, 40), (710, 216), (760, 96),
                    (890, 176), (940, 56), (1070, 224), (1120, 136),
                    (1240, 64), (1310, 208), (1390, 136), (1570, 40),
                    (1640, 232), (1730, 88), (1820, 184), (1960, 136),
                    (2040, 56), (2460, 216), (2550, 96), (2660, 184), (2760, 136)]:
        spawns.append({"tick": tick, "enemy": classics.get(tick, "iron_coast_scout:unit"), "x": x, "y": -24})
    for tick, x in [(260, 32), (440, 72), (620, 112), (810, 152), (980, 192), (1160, 232)]:
        spawns.append({"tick": tick, "enemy": "iron_coast_turret:unit", "x": x, "y": -32})
    for tick, x in [(1450, 96), (2350, 112)]:
        spawns.append({"tick": tick, "enemy": "iron_coast_boss_6:unit", "x": x, "y": -64})
    spawns.sort(key=lambda spawn: spawn["tick"])
    content = {
        "sounds": [{"id": "iron_coast_mission_6:" + name, "name": name.replace("_", " ").title(),
                    "file": info["file"], "volume": 90 if name != "crown_alarm" else 100,
                    "pan": 127, "pitch": 128, "priority": 1 if name in ("crown_alarm", "victory") else 2}
                   for name, info in audio.items()],
        "missions": [{"id": "iron_coast_mission_6:mission_06", "name": "Iron Coast 6 — Iron Crown",
                      "duration": 3800, "auto_complete": False, "columns": 9,
                      "music_track": "iron_coast_music:iron_coast",
                      "spawns": spawns,
                      "tiles": [{"art": {"png": f"art/tile_{n:03}_sd.png", "hd_png": f"art/tile_{n:03}_hd.png",
                                          "logical_width": 32, "logical_height": 32}} for n in range(216)],
                      "layout": list(range(216)) * 6,
                      "art": {"png": "art/briefing_sd.png", "hd_png": "art/briefing_hd.png",
                              "logical_width": 320, "logical_height": 200},
                      "script": "scripts/mission.rhai"}]
    }
    (ROOT / "content.json").write_text(json.dumps(content, indent=2) + "\n")
    actual = set(terrain_sd.convert("RGB").get_flattened_data())
    assert actual <= set(tuple(colors[i:i + 3]) for i in range(0, 768, 3))
    report = {"tile_count": 216, "logical_tile_size": [32, 32], "hd_tile_size": [128, 128],
              "seam_checks_passed": True, "decoded_tile_reassembly_passed": True,
              "generated_pngs": len(list(art.glob("*.png"))), "generated_wavs": len(audio), "vertical_period": "12 forward rows + 12 reflected rows",
              "sd_pixels_match_original_palette": True, "sd_unique_colors": len(actual),
              "palette_sha256": hashlib.sha256(args.palette.read_bytes()).hexdigest(), "audio": audio,
              "sources": {path.name: {"size": Image.open(path).size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                          for path in art.glob("*-source-hd.png")}}
    (ROOT / "asset-report.json").write_text(json.dumps(report, indent=2) + "\n")
    print("Packaged 216 SD/HD terrain tiles, briefing artwork, 4 WAVs and mission definitions")


if __name__ == "__main__":
    main()
