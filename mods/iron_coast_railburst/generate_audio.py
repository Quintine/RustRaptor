#!/usr/bin/env python3
"""Reproduce original deterministic PCM sound effects; no external recordings."""
import math, struct, wave, json, hashlib
from pathlib import Path
PACKAGE = 'iron_coast_railburst'
RATE = 22050

def render(kind):
    rail = PACKAGE.endswith("railburst")
    duration = (0.16 if kind == "fire" else 0.23) if rail else (0.21 if kind == "fire" else 0.46)
    count = int(RATE * duration)
    seed = 0x71AC092D if rail else 0xDC042681
    phase = 0.0
    samples = []
    for n in range(count):
        t = n / RATE
        progress = n / count
        seed ^= (seed << 13) & 0xffffffff
        seed ^= seed >> 17
        seed ^= (seed << 5) & 0xffffffff
        seed &= 0xffffffff
        noise = seed / 2147483648.0 - 1.0
        if rail:
            frequency = (2100 * math.exp(-22*t) + 280) if kind == "fire" else (780 * math.exp(-14*t) + 95)
            tone = 0.30*math.sin(phase) + 0.18*math.sin(phase*1.993) + noise*(0.44 if kind=="fire" else 0.34)
            envelope = math.exp(-(32 if kind=="fire" else 19)*t)
        else:
            frequency = (175 * math.exp(-10*t) + 65) if kind=="fire" else (98*math.exp(-7*t)+42)
            tone = math.sin(phase)*0.53 + math.sin(phase*1.47)*0.10 + noise*(0.26 if kind=="fire" else 0.35)*math.exp(-6*t)
            envelope = math.exp(-(20 if kind=="fire" else 9)*t)
        phase += 2*math.pi*frequency/RATE
        attack = min(1.0, n/(RATE*0.002))
        tail = min(1.0, (count-n)/(RATE*0.015))
        samples.append(round(max(-1.0,min(1.0,tone*envelope*attack*tail))*22000))
    return samples

if __name__ == "__main__":
    root=Path(__file__).resolve().parent
    rows=[]
    for kind in ["fire","impact"]:
        samples=render(kind)
        path=root/"audio"/(kind+".wav")
        with wave.open(str(path),"wb") as output:
            output.setparams((1,2,RATE,0,"NONE","not compressed"))
            output.writeframes(struct.pack("<"+"h"*len(samples),*samples))
        rows.append({"file":str(path.relative_to(root)),"sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"rate":RATE,"channels":1,"bits":16,"frames":len(samples),"duration_seconds":len(samples)/RATE,"peak":max(abs(x) for x in samples),"rms":math.sqrt(sum(x*x for x in samples)/len(samples)),"dc_mean":sum(samples)/len(samples),"clipped_samples":sum(abs(x)>=32767 for x in samples)})
    (root/"audio"/"provenance.json").write_text(json.dumps({"tool":"original procedural Python synthesis","recipe":"generate_audio.py","source_recordings":[],"deterministic_seed":hex(0x71AC092D if PACKAGE.endswith("railburst") else 0xDC042681),"outputs":rows},indent=2)+"\n")
