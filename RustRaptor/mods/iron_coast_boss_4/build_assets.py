#!/usr/bin/env python3
"""Preserve generated RGBA masters, derive SD/HD sprites and synthesize local WAVs.

This is an asset packaging pipeline, not an image redraw. Inputs are the saved
built-in imagegen results documented in prompts/ and provenance.json.
"""
import hashlib
import json
import math
from pathlib import Path
import random
import struct
import wave
from PIL import Image, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parent


def artwork():
    report = {}
    for kind, logical, scale in [("unit", (96, 64), 4), ("projectile", (8, 8), 8)]:
        source_file = f"{kind}-generated-v{2 if kind == 'projectile' else 1}.png"
        source = Image.open(ROOT / "art" / source_file).convert("RGBA")
        size = tuple(v * scale for v in logical)
        # Unit master already has matching 3:2 framing. The shell uses contain
        # with one logical pixel of padding, retaining its portrait aspect.
        if kind == "unit":
            hd = source.resize(size, Image.Resampling.LANCZOS)
        else:
            inset = ImageOps.contain(source, (size[0] - 2 * scale, size[1] - 2 * scale), Image.Resampling.LANCZOS)
            hd = Image.new("RGBA", size)
            hd.alpha_composite(inset, ((size[0] - inset.width) // 2, (size[1] - inset.height) // 2))
        sd = hd.resize(logical, Image.Resampling.BOX)
        entries = {}
        for mode, image in [("sd", sd), ("hd", hd)]:
            mask = image.getchannel("A").point(lambda value: 255 if value >= 128 else 0)
            bounds = mask.getbbox()
            assert bounds is not None, f"{kind}/{mode} is invisible"
            assert all([bounds[0] > 0, bounds[1] > 0, bounds[2] < image.width, bounds[3] < image.height]), f"{kind}/{mode} clips"
            path = ROOT / "art" / f"{kind}-{mode}.png"
            image.save(path)
            entries[mode] = {"dimensions": list(image.size), "opaque_bounds": list(bounds), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        entries["source_sha256"] = hashlib.sha256((ROOT / "art" / source_file).read_bytes()).hexdigest()
        entries["logical_dimensions"] = list(logical)
        entries["frames"] = 1
        report[kind] = entries
    preview = Image.new("RGB", (768, 560), (30, 44, 53))
    draw = ImageDraw.Draw(preview)
    draw.text((16, 12), "Stormwall Arsenal / SD nearest scale (top), HD (bottom)", fill="white")
    for kind, sd_box, hd_box in [("unit", (16, 50), (16, 238)), ("projectile", (640, 70), (640, 320))]:
        sd = Image.open(ROOT / "art" / f"{kind}-sd.png").convert("RGBA")
        hd = Image.open(ROOT / "art" / f"{kind}-hd.png").convert("RGBA")
        sd = sd.resize(tuple(v * (2 if kind == "unit" else 8) for v in sd.size), Image.Resampling.NEAREST)
        preview.paste(sd, sd_box, sd)
        preview.paste(hd, hd_box, hd)
    preview.save(ROOT / "art/preview.png")
    (ROOT / "art-qa.json").write_text(json.dumps(report, indent=2) + "\n")


def sounds():
    rate = 22050
    report = {}
    for name, seconds, seed in [("warning", 0.38, 404), ("shot", 0.23, 405), ("death", 1.08, 406)]:
        rng = random.Random(seed)
        count = round(seconds * rate)
        phase = low_noise = 0.0
        pcm = []
        for index in range(count):
            t = index / rate
            p = index / max(1, count - 1)
            noise = rng.uniform(-1, 1)
            low_noise = 0.85 * low_noise + 0.15 * noise
            if name == "warning":
                # Two distinct short rising notes; finishes before the salvo.
                note_t = t % 0.19
                phase += 2 * math.pi * (640 if t < 0.19 else 900) / rate
                value = math.sin(phase) * 0.66 + math.sin(2 * phase) * 0.12
                envelope = min(1.0, note_t / 0.006) * max(0.0, 1.0 - note_t / 0.15)
            elif name == "shot":
                phase += 2 * math.pi * (70 + 480 * (1 - p) ** 3) / rate
                value = 0.62 * math.sin(phase) + 0.22 * noise + 0.12 * math.sin(2.2 * phase)
                envelope = min(1, t / 0.002) * math.exp(-6 * p)
            else:
                phase += 2 * math.pi * (56 - 30 * p) / rate
                value = 0.62 * low_noise + 0.24 * noise + 0.35 * math.sin(phase)
                envelope = min(1, t / 0.003) * math.exp(-4 * p)
            envelope *= min(1, (count - 1 - index) / (rate * 0.005))
            pcm.append(value * max(0, envelope))
        peak = max(map(abs, pcm))
        pcm = [round(value / peak * 0.78 * 32767) for value in pcm]
        path = ROOT / "audio" / f"{name}.wav"
        with wave.open(str(path), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(rate)
            output.writeframes(struct.pack("<" + "h" * len(pcm), *pcm))
        report[name] = {"seed": seed, "duration": seconds, "sample_rate": rate, "channels": 1, "bits": 16,
                        "samples": count, "peak": max(map(abs, pcm)), "rms": math.sqrt(sum(v*v for v in pcm) / count),
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    (ROOT / "audio-recipe.json").write_text(json.dumps({"generator": "build_assets.py deterministic PCM synthesis; no recordings", "files": report}, indent=2) + "\n")


if __name__ == "__main__":
    artwork()
    sounds()
    print("Packaged Stormwall Arsenal SD/HD sprites and three non-silent WAVs")
