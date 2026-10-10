#!/usr/bin/env python3
"""Derive matching SD/HD canvases from imagegen masters and synthesize local PCM.

No artwork is painted or replaced: resizing preserves source RGBA. The supplied
projectile's transparent margins are cropped before proportional fitting.
Use --audio-only to reproduce just the deterministic sounds without Pillow.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import struct
import wave

ROOT = Path(__file__).resolve().parent
RATE = 22050


def hash_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sounds():
    files = {}
    for name, duration, seed in [('warning', .22, 6609), ('shot', .27, 6654), ('death', 1.05, 6616)]:
        count = round(duration * RATE)
        rng = random.Random(seed)
        phase = low_noise = 0.0
        samples = []
        for i in range(count):
            t, p = i / RATE, i / (count - 1)
            noise = rng.uniform(-1, 1)
            low_noise = .89 * low_noise + .11 * noise
            if name == 'warning':
                frequency = [760, 1020, 1340][min(2, int(p * 3))]
                phase += 2 * math.pi * frequency / RATE
                value = .72 * math.sin(phase) + .16 * math.sin(phase * 2)
                segment = (p * 3) % 1
                envelope = math.sin(math.pi * segment) ** .55
            elif name == 'shot':
                frequency = 65 + 385 * (1 - p) ** 2
                phase += 2 * math.pi * frequency / RATE
                value = .52 * math.sin(phase) + .22 * noise + .26 * math.sin(2 * math.pi * 68 * t)
                envelope = min(1, t / .002) * math.exp(-p * 5.7)
            else:
                phase += 2 * math.pi * (62 - 35 * p) / RATE
                value = .58 * low_noise + .21 * noise + .26 * math.sin(phase)
                envelope = min(1, t / .003) * math.exp(-p * 4.3)
            envelope *= min(1, (count - 1 - i) / (RATE * .005))
            samples.append(value * max(0, envelope))
        peak = max(abs(v) for v in samples)
        pcm = [round(v / peak * .78 * 32767) for v in samples]
        path = ROOT / 'audio' / f'{name}.wav'
        with wave.open(str(path), 'wb') as out:
            out.setnchannels(1)
            out.setsampwidth(2)
            out.setframerate(RATE)
            out.writeframes(struct.pack('<' + 'h' * len(pcm), *pcm))
        files[str(path.relative_to(ROOT))] = {
            'duration': count / RATE, 'seed': seed, 'sample_rate': RATE,
            'channels': 1, 'bits': 16, 'samples': count,
            'peak': max(abs(v) for v in pcm),
            'rms': math.sqrt(sum(v * v for v in pcm) / count),
            'sha256': hash_file(path),
        }
    (ROOT / 'audio-recipe.json').write_text(json.dumps({
        'generator': 'build_assets.py deterministic standard-library chirp/noise synthesis',
        'recordings': False, 'files': files,
    }, indent=2) + '\n')


def artwork():
    from PIL import Image
    sources, files = {}, {}
    for name, logical in [('unit', (96, 64)), ('projectile', (8, 8))]:
        path = ROOT / 'art' / f'{name}-generated-v1.png'
        source = Image.open(path).convert('RGBA')
        original_size = source.size
        source_box = None
        if name == 'projectile':
            # Only transparent margin is discarded; the complete indexed-visible
            # shell remains present, with its antialiased fringe preserved.
            bbox = source.getchannel('A').point(lambda a: 255 if a >= 128 else 0).getbbox()
            source_box = (max(0, bbox[0] - 8), max(0, bbox[1] - 8),
                          min(source.width, bbox[2] + 8), min(source.height, bbox[3] + 8))
            source = source.crop(source_box)
        elif source.width * logical[1] != source.height * logical[0]:
            raise ValueError('Unit source does not have the 3:2 logical canvas aspect')
        hd_size = (logical[0] * 8, logical[1] * 8)
        padding = (32, 24) if name == 'unit' else (12, 8)
        maximum = (hd_size[0] - padding[0] * 2, hd_size[1] - padding[1] * 2)
        ratio = min(maximum[0] / source.width, maximum[1] / source.height)
        fitted = source.resize((round(source.width * ratio), round(source.height * ratio)), Image.Resampling.LANCZOS)
        hd = Image.new('RGBA', hd_size, (0, 0, 0, 0))
        hd.alpha_composite(fitted, ((hd.width - fitted.width) // 2, (hd.height - fitted.height) // 2))
        sd = hd.resize(logical, Image.Resampling.BOX)
        for mode, im in [('hd', hd), ('sd', sd)]:
            target = ROOT / 'art' / f'{name}-{mode}.png'
            bounds = im.getchannel('A').point(lambda a: 255 if a >= 128 else 0).getbbox()
            if bounds is None or bounds[0] == 0 or bounds[1] == 0 or bounds[2] == im.width or bounds[3] == im.height:
                raise ValueError(f'{name}-{mode} silhouette touches canvas edge')
            im.save(target)
            files[str(target.relative_to(ROOT))] = {'size': list(im.size), 'opaque_bounds': list(bounds), 'sha256': hash_file(target)}
        sources[str(path.relative_to(ROOT))] = {'size': list(original_size), 'visible_margin_crop': source_box, 'sha256': hash_file(path)}
    (ROOT / 'art-qa.json').write_text(json.dumps({
        'pipeline': 'Full-canvas proportional RGBA resize, centered clear padding, BOX reduction to SD; no bitmap redraw',
        'logical_boss': [96, 64], 'logical_projectile': [8, 8], 'hd_scale': 8,
        'frames': 1, 'origin': [0, 0], 'alpha': 'Preserved RGBA; runtime alpha below128 is transparent',
        'sources': sources, 'files': files,
    }, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audio-only', action='store_true')
    args = parser.parse_args()
    sounds()
    if not args.audio_only:
        artwork()
    print('Iron Crown SD/HD artwork and deterministic PCM assets ready')


if __name__ == '__main__':
    main()
