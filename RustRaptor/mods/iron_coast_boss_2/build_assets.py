#!/usr/bin/env python3
"""Resize saved generated masters and synthesize reproducible package WAVs.

No original assets are copied. Canvas resampling retains the master's true alpha;
art is never redrawn. Run from any directory with Python 3 and Pillow installed.
"""
from pathlib import Path
from PIL import Image
import hashlib
import json
import math
import random
import struct
import wave

ROOT = Path(__file__).resolve().parent
RATE = 22050


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def artwork():
    stats = []
    for name, size, scale in [('unit', (96, 64), 8), ('projectile', (8, 8), 8)]:
        path = ROOT / 'art' / (name + '-generated-v1.png')
        original = Image.open(path).convert('RGBA')
        assert original.getchannel('A').getextrema()[0] == 0
        if name == 'unit':
            assert original.width * size[1] == original.height * size[0]
            hd = original.resize((size[0] * scale, size[1] * scale), Image.Resampling.LANCZOS)
        else:
            # Keep the complete square alpha canvas; this preserves every source pixel.
            side = max(original.size)
            canvas = Image.new('RGBA', (side, side), (0, 0, 0, 0))
            canvas.alpha_composite(original, ((side-original.width)//2, (side-original.height)//2))
            hd = canvas.resize((size[0] * scale, size[1] * scale), Image.Resampling.LANCZOS)
        sd = hd.resize(size, Image.Resampling.BOX)
        for mode, sprite in [('sd', sd), ('hd', hd)]:
            alpha = sprite.getchannel('A')
            mask = alpha.point(lambda a: 255 if a >= 128 else 0)
            bounds = mask.getbbox()
            assert bounds and bounds[0] > 0 and bounds[1] > 0
            assert bounds[2] < sprite.width and bounds[3] < sprite.height
            out = ROOT / 'art' / (name + '-' + mode + '.png')
            sprite.save(out)
            stats.append({'file': str(out.relative_to(ROOT)), 'size': list(sprite.size),
                          'opaque_bounds': list(bounds), 'source': str(path.relative_to(ROOT)),
                          'alpha_min_max': list(alpha.getextrema()), 'sha256': sha(out)})
    (ROOT / 'art-qa.json').write_text(json.dumps({
        'logical_unit': [96, 64], 'logical_projectile': [8, 8], 'hd_scale': 8,
        'frames': 1, 'alpha': 'True RGBA; runtime palette mapping uses alpha >= 128',
        'conversion': 'Full source canvas Lanczos HD, BOX SD; no sprite redraw or catalog copies',
        'files': stats}, indent=2) + '\n')


def audio():
    stats = []
    for name, duration, seed in [('shot', 0.21, 212), ('warning', 0.36, 222), ('death', 0.95, 232)]:
        rng = random.Random(seed)
        count = int(duration * RATE)
        phase = 0.0
        low_noise = 0.0
        signal = []
        for n in range(count):
            t = n / RATE
            p = n / max(1, count-1)
            noise = rng.uniform(-1, 1)
            low_noise = low_noise * .86 + noise * .14
            if name == 'warning':
                # Two brief rising radar pips separated by a clear gap.
                local = t % .18
                frequency = 1450 + 900 * min(1, local / .11)
                phase += 2 * math.pi * frequency / RATE
                envelope = (math.sin(math.pi * min(1, local / .12)) ** 2 if local < .12 else 0)
                value = .68 * math.sin(phase) + .15 * math.sin(phase * 2)
            elif name == 'shot':
                phase += 2 * math.pi * (170 + 710 * (1-p)**2) / RATE
                value = .60*math.sin(phase) + .22*math.sin(phase*1.52) + .12*noise
                envelope = min(1, t / .003) * math.exp(-p*6.0)
            else:
                phase += 2 * math.pi * (80 - 55*p) / RATE
                value = .65*low_noise + .20*noise + .26*math.sin(phase)
                envelope = min(1, t / .004) * math.exp(-p*4.5)
            envelope *= min(1, (count-1-n) / (RATE*.005))
            signal.append(value * max(0, envelope))
        maximum = max(abs(x) for x in signal)
        pcm = [round(v / maximum * 0.78 * 32767) for v in signal]
        path = ROOT / 'audio' / (name + '.wav')
        with wave.open(str(path), 'wb') as wav:
            wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(RATE)
            wav.writeframes(struct.pack('<' + 'h'*len(pcm), *pcm))
        stats.append({'file': str(path.relative_to(ROOT)), 'sample_rate': RATE,
                      'channels': 1, 'bits': 16, 'samples': count, 'duration': duration,
                      'peak': max(abs(x) for x in pcm),
                      'rms': round(math.sqrt(sum(x*x for x in pcm)/len(pcm)),2),
                      'seed': seed, 'sha256': sha(path)})
    (ROOT / 'audio-recipe.json').write_text(json.dumps({
        'generator': 'build_assets.py deterministic chirp/noise synthesis; no recordings',
        'files': stats}, indent=2) + '\n')


if __name__ == '__main__':
    artwork()
    audio()
    print('Generated Relay Warden SD/HD art and three non-silent WAVs')
