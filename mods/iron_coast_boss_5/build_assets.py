#!/usr/bin/env python3
"""Derive SD/HD PNGs from saved imagegen masters and synthesize local PCM WAVs.

Artwork is only resized and placed on padded transparent canvases. No generated
shape is painted over or replaced. Re-run with Python 3 and Pillow.
"""
from pathlib import Path
import hashlib
import json
import math
import random
import struct
import wave

ROOT = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def artwork():
    from PIL import Image
    records = []
    for name, logical, target in [
        ("unit", (96, 64), (768, 512)),
        ("projectile", (8, 8), (64, 64)),
    ]:
        source_path = ROOT / "art" / f"{name}-generated-v1.png"
        source = Image.open(source_path).convert("RGBA")
        if source.width * logical[1] != source.height * logical[0]:
            raise ValueError(f"{name}: source and logical canvas aspect differ")
        alpha = source.getchannel("A")
        if alpha.getextrema()[0] != 0 or alpha.getextrema()[1] < 128:
            raise ValueError(f"{name}: generated master lacks real transparent alpha")
        hd = Image.new("RGBA", target, (0, 0, 0, 0))
        # A common, whole-canvas resize preserves orientation and relative detail.
        # Clear padding leaves all opaque art inside its original collision box.
        fit = (672, 448) if name == "unit" else (56, 56)
        resized = source.resize(fit, Image.Resampling.LANCZOS)
        hd.alpha_composite(resized, ((target[0] - fit[0]) // 2,
                                    (target[1] - fit[1]) // 2))
        sd = hd.resize(logical, Image.Resampling.BOX)
        result = {"name": name, "logical_size": list(logical), "hd_scale": 8,
                  "origin": [0, 0], "frames": 1,
                  "master_sha256": digest(source_path),
                  "master_size": list(source.size), "files": {}}
        for mode, image in [("sd", sd), ("hd", hd)]:
            path = ROOT / "art" / f"{name}-{mode}.png"
            image.save(path)
            opaque = image.getchannel("A").point(lambda a: 255 if a >= 128 else 0)
            bounds = opaque.getbbox()
            if not bounds or bounds[0] == 0 or bounds[1] == 0 or bounds[2] == image.width or bounds[3] == image.height:
                raise ValueError(f"{name}-{mode}: opaque silhouette touches its canvas")
            result["files"][str(path.relative_to(ROOT))] = {
                "physical_size": list(image.size), "opaque_bounds": list(bounds),
                "transparent_pixels": sum(a < 128 for a in image.getchannel("A").get_flattened_data()),
                "sha256": digest(path),
            }
        records.append(result)
    # Review sheet exposes alpha edges and the exact SD silhouette at 4x.
    preview = Image.new("RGBA", (1280, 620), (24, 32, 40, 255))
    boss_hd = Image.open(ROOT / "art/unit-hd.png")
    preview.alpha_composite(boss_hd, (0, 0))
    boss_sd = Image.open(ROOT / "art/unit-sd.png").resize((384, 256), Image.Resampling.NEAREST)
    preview.alpha_composite(boss_sd, (848, 330))
    preview.alpha_composite(Image.open(ROOT / "art/projectile-hd.png"), (900, 20))
    preview.save(ROOT / "art/preview.png")
    (ROOT / "art-qa.json").write_text(json.dumps({
        "alpha": "Preserved RGBA; runtime alpha>=128 indexed transparency",
        "registration": "Whole-canvas proportional resize, fixed padding; single idle frame",
        "files": records,
    }, indent=2) + "\n")


def audio():
    rate = 22050
    files = {}
    durations = {"warning": 0.28, "shot": 0.24, "death": 0.95}
    for name, duration in durations.items():
        seed = {"warning": 5501, "shot": 5502, "death": 5503}[name]
        rng = random.Random(seed)
        count = round(duration * rate)
        phase = low_noise = 0.0
        samples = []
        for index in range(count):
            time = index / rate
            position = index / (count - 1)
            noise = rng.uniform(-1, 1)
            low_noise = low_noise * 0.88 + noise * 0.12
            if name == "warning":
                frequency = 430 + 310 * position
                phase += 2 * math.pi * frequency / rate
                # Two separated furnace-pressure tones, distinct from a weapon hit.
                pulse = 0.0
                for start, end in [(0.02, 0.105), (0.155, 0.245)]:
                    if start <= time <= end:
                        pulse = max(0.0, min(1.0, (time - start) / 0.005,
                                             (end - time) / 0.005))
                value = (0.7 * math.sin(phase) + 0.12 * math.sin(2 * phase)) * pulse
                envelope = math.sin(math.pi * position) ** 2
            elif name == "shot":
                frequency = 70 + 550 * (1 - position) ** 2
                phase += 2 * math.pi * frequency / rate
                value = 0.59 * math.sin(phase) + 0.19 * low_noise + 0.09 * noise
                envelope = math.exp(-position * 6.0)
            else:
                frequency = 34 + 75 * (1 - position) ** 2
                phase += 2 * math.pi * frequency / rate
                value = 0.65 * low_noise + 0.18 * noise + 0.25 * math.sin(phase)
                envelope = math.exp(-position * 4.4)
            envelope *= min(1.0, time / 0.003)
            envelope *= max(0.0, min(1.0, (count - 1 - index) / (rate * 0.006)))
            samples.append(value * envelope)
        peak = max(abs(v) for v in samples)
        pcm = [round(v / peak * 0.72 * 32767) for v in samples]
        path = ROOT / "audio" / f"{name}.wav"
        with wave.open(str(path), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(rate)
            output.writeframes(struct.pack("<" + "h" * len(pcm), *pcm))
        files[str(path.relative_to(ROOT))] = {
            "sample_rate": rate, "channels": 1, "bits": 16, "seed": seed,
            "duration_seconds": duration, "samples": len(pcm),
            "peak": max(abs(v) for v in pcm),
            "rms": (sum(v * v for v in pcm) / len(pcm)) ** 0.5,
            "sha256": digest(path),
        }
    (ROOT / "audio-recipe.json").write_text(json.dumps({
        "generator": "build_assets.py deterministic chirp/noise PCM synthesis; no recordings",
        "files": files,
    }, indent=2) + "\n")


if __name__ == "__main__":
    artwork()
    audio()
    print("Cinder Hammer: SD/HD artwork and three non-silent PCM sounds generated")
