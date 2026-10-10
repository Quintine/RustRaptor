#!/usr/bin/env python3
"""Resize saved imagegen masters and reproduce seeded PCM effects.

Generated alpha is preserved. No image is painted or reconstructed here.
Run with --audio-only to regenerate WAVs without Pillow.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import struct
import wave


def synthesize(root):
    rate = 22050
    reports = {}
    for name, duration, seed in [("shot", 0.22, 303), ("warning", 0.17, 304), ("death", 0.95, 305)]:
        rng = random.Random(seed)
        count = round(duration * rate)
        phase = smooth_noise = 0.0
        samples = []
        for index in range(count):
            t = index / rate
            u = index / max(1, count - 1)
            noise = rng.uniform(-1, 1)
            smooth_noise = smooth_noise * 0.88 + noise * 0.12
            if name == "shot":
                phase += 2 * math.pi * (95 + 520 * (1-u)**2) / rate
                value = 0.6 * math.sin(phase) + 0.24 * noise + 0.14 * math.sin(2.21 * phase)
                envelope = math.exp(-6*u)
            elif name == "warning":
                phase += 2 * math.pi * (640 + 740*u) / rate
                value = 0.6 * math.sin(phase) + 0.12 * math.sin(2*phase)
                envelope = math.sin(math.pi*u)**1.5 * (0.3 + 0.7 * (0.5 + 0.5*math.sin(2*math.pi*18*t)))
            else:
                phase += 2 * math.pi * (90 - 65*u) / rate
                value = 0.65 * smooth_noise + 0.17 * noise + 0.31 * math.sin(phase)
                envelope = math.exp(-4.9*u)
            envelope *= min(1, t/0.003) * min(1, (count-1-index)/(rate*0.005))
            samples.append(value * max(0, envelope))
        peak = max(abs(v) for v in samples)
        pcm = [round(v / peak * (0.54 if name == "warning" else 0.78) * 32767) for v in samples]
        path = root / "audio" / f"{name}.wav"
        with wave.open(str(path), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(rate)
            output.writeframes(struct.pack("<" + "h" * count, *pcm))
        reports[str(path.relative_to(root))] = {
            "sample_rate": rate, "channels": 1, "bits": 16, "samples": count,
            "seed": seed, "duration_seconds": count/rate,
            "peak": max(abs(v) for v in pcm),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()
        }
    (root / "audio-recipe.json").write_text(json.dumps({"generator": "build_assets.py seeded chirp/noise synthesis; no recordings", "files": reports}, indent=2) + "\n")


def artwork(root):
    from PIL import Image, ImageOps
    reports = {}
    for name, logical, scale in [("unit", (96,64), 8), ("projectile", (8,8), 8)]:
        path = root / "art" / f"{name}-generated-v1.png"
        source = Image.open(path).convert("RGBA")
        if source.getchannel("A").getextrema()[0] != 0:
            raise ValueError(f"{path}: missing true transparent pixels")
        size = tuple(v*scale for v in logical)
        if name == "unit":
            hd = Image.new("RGBA", size, (0,0,0,0))
            fitted = ImageOps.contain(source, (size[0]-64, size[1]-42), Image.Resampling.LANCZOS)
            hd.alpha_composite(fitted, ((size[0]-fitted.width)//2, (size[1]-fitted.height)//2))
        else:
            hd = source.resize(size, Image.Resampling.LANCZOS)
        sd = hd.resize(logical, Image.Resampling.BOX)
        bounds = []
        for image in (sd,hd):
            bbox = image.getchannel("A").point(lambda v:255 if v>=128 else 0).getbbox()
            if bbox is None or bbox[0] <= 0 or bbox[1] <= 0 or bbox[2] >= image.width or bbox[3] >= image.height:
                raise ValueError(f"{name}: silhouette clips or is missing: {bbox}")
            bounds.append(list(bbox))
        sd.save(root / "art" / f"{name}-sd.png")
        hd.save(root / "art" / f"{name}-hd.png")
        reports[name] = {"logical_size": list(logical), "hd_size": list(size), "hd_scale": scale,
            "sd_opaque_bounds": bounds[0], "hd_opaque_bounds": bounds[1],
            "source": str(path.relative_to(root)), "source_size": list(source.size),
            "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "frames": 1, "origin": [0,0], "alpha": "Generated RGBA preserved; indexed threshold alpha>=128"}
    (root / "art-qa.json").write_text(json.dumps(reports, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio-only", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    synthesize(root)
    if not args.audio_only:
        artwork(root)
    print("Saltbreaker assets validated and generated")


if __name__ == "__main__":
    main()
