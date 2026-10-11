#!/usr/bin/env python3
"""Reproduce deterministic PCM16 mono electrical discharge sounds."""
import math
import struct
import wave
from pathlib import Path

PACKAGE = "lightning_shield"
RATE = 22050

def render(kind):
    heavy = PACKAGE == "lightning_cannon"
    duration = (0.24 if heavy else 0.09) if kind == "fire" else (0.11 if heavy else 0.06)
    count = int(RATE * duration)
    seed = 0x5A17C0DE
    phase = 0.0
    samples = []
    for n in range(count):
        t = n / count
        seed ^= (seed << 13) & 0xffffffff
        seed ^= seed >> 17
        seed ^= (seed << 5) & 0xffffffff
        seed &= 0xffffffff
        noise = seed / 2147483648.0 - 1.0
        frequency = (2100 - 1450 * t) if heavy else (3100 - 1650 * t)
        phase += 2 * math.pi * frequency / RATE
        crackle = noise * (0.45 + 0.25 * math.sin(2 * math.pi * 61 * n / RATE) ** 8)
        tone = math.sin(phase) * 0.24 + math.sin(phase * 1.503) * 0.15
        if kind == "impact":
            tone = math.sin(phase * 0.18) * 0.25
        attack = min(1.0, n / (RATE * 0.002))
        envelope = attack * (1 - t) ** (2.2 if kind == "fire" else 3)
        samples.append(round(max(-1, min(1, (crackle + tone) * envelope)) * 21000))
    return struct.pack("<" + "h" * len(samples), *samples)

if __name__ == "__main__":
    output = Path(__file__).resolve().parent / "audio"
    output.mkdir(exist_ok=True)
    for kind in ["fire", "impact"]:
        with wave.open(str(output / (kind + ".wav")), "wb") as wav:
            wav.setparams((1, 2, RATE, 0, "NONE", "not compressed"))
            wav.writeframes(render(kind))
        print(output / (kind + ".wav"))
