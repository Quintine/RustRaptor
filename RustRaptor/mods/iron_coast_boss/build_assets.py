#!/usr/bin/env python3
"""Convert saved imagegen artwork and synthesize reproducible package-local WAVs.

This script resizes/atlases supplied art; it never redraws source or generated art.
Generated masters, SD/HD artwork and WAVs are tracked in Git. See prompts/ and provenance.json.
Use --audio-only to regenerate sound without Pillow or processing artwork.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import struct
import wave


def sounds(root, kind):
    rate = 22050
    values = {
        "scout": (0.11, 1400, 380, 0.34, 230, 19),
        "turret": (0.18, 900, 160, 0.52, 150, 37),
        "boss": (0.24, 500, 80, 0.90, 75, 83),
    }
    shot_length, start, end, death_length, bass, seed = values[kind]
    (root / "audio").mkdir(exist_ok=True)
    stats = {}
    for name, duration in [("shot", shot_length), ("death", death_length)]:
        rng = random.Random(seed + (100 if name == "death" else 0))
        count = int(duration * rate)
        phase = low_noise = 0.0
        samples = []
        for index in range(count):
            t = index / rate
            position = index / max(1, count - 1)
            noise = rng.uniform(-1, 1)
            low_noise = low_noise * 0.86 + noise * 0.14
            if name == "shot":
                frequency = end + (start - end) * (1 - position) ** 2
                phase += 2 * math.pi * frequency / rate
                value = (0.60 * math.sin(phase) + 0.15 * math.sin(2.31 * phase)
                         + 0.16 * noise + 0.16 * math.sin(2 * math.pi * bass * t))
                envelope = min(1, t / 0.002) * math.exp(-position * 6.0)
            else:
                frequency = bass * (1.0 - position * 0.65)
                phase += 2 * math.pi * frequency / rate
                value = 0.62 * low_noise + 0.19 * noise + 0.28 * math.sin(phase)
                envelope = min(1, t / 0.003) * math.exp(-position * 4.7)
            # Five milliseconds at the tail avoid discontinuities at mixer retirement.
            envelope *= min(1, (count - 1 - index) / (rate * 0.005))
            samples.append(value * max(0, envelope))
        peak = max(abs(value) for value in samples)
        pcm = [round(value / peak * 0.78 * 32767) for value in samples]
        path = root / "audio" / (name + ".wav")
        with wave.open(str(path), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(rate)
            output.writeframes(struct.pack("<" + "h" * len(pcm), *pcm))
        stats[str(path.relative_to(root))] = {
            "sample_rate": rate, "channels": 1, "bits": 16,
            "samples": count, "peak": max(abs(value) for value in pcm),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    (root / "audio-recipe.json").write_text(json.dumps({
        "generator": "build_assets.py deterministic chirp/noise synthesis; no recordings",
        "kind": kind, "seed": seed, "files": stats,
    }, indent=2) + "\n")


def artwork(root, kind):
    from PIL import Image
    dimensions = {"scout": (24, 24), "turret": (32, 32), "boss": (96, 64)}
    width, height = dimensions[kind]
    paths = [root / "art/unit-generated-v1.png"]
    if kind == "boss":
        paths.append(root / "art/unit-charge-generated-v1.png")
    hd_frames, sd_frames = [], []
    stats = []
    for path in paths:
        source = Image.open(path).convert("RGBA")
        if source.width * height != source.height * width:
            raise ValueError(f"{path}: source canvas aspect differs from logical canvas")
        # Identical canvas resize and padding for all frames retain their registration.
        hd = Image.new("RGBA", (width * 8, height * 8), (0, 0, 0, 0))
        pad_x, pad_y = width // 3, height // 3
        resized = source.resize((hd.width - 2 * pad_x, hd.height - 2 * pad_y), Image.Resampling.LANCZOS)
        hd.alpha_composite(resized, (pad_x, pad_y))
        sd = hd.resize((width, height), Image.Resampling.BOX)
        for image in [hd, sd]:
            bbox = image.getchannel("A").point(lambda value: 255 if value >= 128 else 0).getbbox()
            if bbox is None or bbox[0] == 0 or bbox[1] == 0 or bbox[2] == image.width or bbox[3] == image.height:
                raise ValueError(f"{path}: opaque silhouette touches logical canvas edge")
        hd_frames.append(hd)
        sd_frames.append(sd)
        stats.append({"source": str(path.relative_to(root)),
                      "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                      "sd_opaque_bounds": list(sd.getchannel("A").point(lambda value: 255 if value >= 128 else 0).getbbox())})
    for name, frames in [("unit-hd.png", hd_frames), ("unit-sd.png", sd_frames)]:
        atlas = Image.new("RGBA", (frames[0].width * len(frames), frames[0].height), (0, 0, 0, 0))
        for index, frame in enumerate(frames):
            atlas.alpha_composite(frame, (index * frame.width, 0))
        atlas.save(root / "art" / name)
    # Shared visual ammunition language; each package includes its own local copy.
    source = Image.open(root / "art/projectile-generated-v1.png").convert("RGBA")
    hd = source.resize((64, 64), Image.Resampling.LANCZOS)
    hd.save(root / "art/projectile-hd.png")
    hd.resize((8, 8), Image.Resampling.BOX).save(root / "art/projectile-sd.png")
    metadata = {"logical_size": [width, height], "hd_scale": 8, "origin": [0, 0],
                "frames": len(paths), "frame_order": ["idle", "charged"][:len(paths)],
                "alpha": "Preserved RGBA; runtime uses alpha>=128 indexed transparency",
                "registration": "Common full-canvas resize and equal padding for every frame",
                "sources": stats}
    if len(hd_frames) == 2:
        masks = [f.getchannel("A").point(lambda value: 255 if value >= 128 else 0) for f in hd_frames]
        pairs = list(zip(masks[0].get_flattened_data(), masks[1].get_flattened_data()))
        metadata["animation_silhouette_overlap"] = sum(bool(a and b) for a, b in pairs) / sum(bool(a or b) for a, b in pairs)
        if metadata["animation_silhouette_overlap"] < 0.99:
            raise ValueError("generated animation changes the silhouette beyond accepted registration tolerance")
    (root / "art-qa.json").write_text(json.dumps(metadata, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio-only", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    kind = root.name.removeprefix("iron_coast_")
    sounds(root, kind)
    if not args.audio_only:
        artwork(root, kind)
    print(f"Generated {root.name} package assets")


if __name__ == "__main__":
    main()
