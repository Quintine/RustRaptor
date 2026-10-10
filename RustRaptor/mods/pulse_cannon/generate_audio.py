#!/usr/bin/env python3
"""Reproduce local procedural weapon audio; WAV outputs are tracked with the package."""
import math
import struct
import wave
from pathlib import Path

PACKAGE = "pulse_cannon"
RATE = 22050

def render(kind):
    duration = 0.13 if kind == "fire" else 0.17
    count = int(RATE * duration)
    phase = 0.0
    seed = 0xA7C51D3
    samples = []
    for n in range(count):
        t = n / count
        seed ^= (seed << 13) & 0xffffffff
        seed ^= seed >> 17
        seed ^= (seed << 5) & 0xffffffff
        seed &= 0xffffffff
        noise = (seed / 2147483648.0) - 1.0
        if PACKAGE == "pulse_cannon":
            frequency = (1350 * (1 - t) + 190) if kind == "fire" else 130
            tone = math.sin(phase) * 0.64 + noise * 0.22
        elif PACKAGE == "seeker_swarm":
            frequency = 330 + 850 * t if kind == "fire" else 95
            tone = noise * 0.48 + math.sin(phase) * 0.35
        else:
            frequency = 1850 + 680 * t if kind == "fire" else 680 * (1 - t) + 110
            tone = math.sin(phase) * 0.52 + math.sin(phase * 1.997) * 0.2 + noise * 0.06
        phase += 2 * math.pi * frequency / RATE
        attack = min(1.0, n / (RATE * 0.003))
        envelope = attack * (1 - t) ** (3 if kind == "impact" else 2)
        samples.append(round(max(-1, min(1, tone * envelope)) * 21000))
    return struct.pack("<" + "h" * len(samples), *samples)

if __name__ == "__main__":
    output = Path(__file__).resolve().parent / "audio"
    output.mkdir(exist_ok=True)
    for kind in ["fire", "impact"]:
        with wave.open(str(output / (kind + ".wav")), "wb") as wav:
            wav.setparams((1, 2, RATE, 0, "NONE", "not compressed"))
            wav.writeframes(render(kind))
        print(output / (kind + ".wav"))
