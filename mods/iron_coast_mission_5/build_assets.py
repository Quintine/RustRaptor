#!/usr/bin/env python3
"""Package generated masters at logical/HD footprints and synthesize local cues.

Only deterministic resampling, palette conversion and whole-map tile slicing
are performed here; the source illustrations are built-in imagegen outputs.
"""
import argparse
import hashlib
import json
import math
import random
import struct
import wave
from pathlib import Path
import runpy
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def palette(path):
    data = path.read_bytes()
    if len(data) != 768:
        raise ValueError("Expected the original 768-byte VGA palette")
    colors = [(min(v, 63) << 2) | (min(v, 63) >> 4) for v in data]
    image = Image.new("P", (1, 1))
    image.putpalette(colors)
    return image, colors


def sd(image, size, colors):
    rgba = image.convert("RGBA").resize(size, Image.Resampling.LANCZOS)
    alpha = rgba.getchannel("A").point(lambda a: 255 if a >= 128 else 0)
    result = rgba.convert("RGB").quantize(palette=colors, dither=Image.Dither.NONE).convert("RGBA")
    result.putalpha(alpha)
    return result


def wav(name, duration, frequencies, mode="tone"):
    rate = 22050
    count = int(rate * duration)
    rng = random.Random(7053 + sum(ord(c) for c in name))
    pcm = bytearray()
    for i in range(count):
        t = i / rate
        note = min(len(frequencies)-1, int(t / duration * len(frequencies)))
        f = frequencies[note]
        phase = (t / duration * len(frequencies)) % 1
        envelope = min(1, phase * 24) * (1-phase)**1.2
        sample = math.sin(2*math.pi*f*t) + 0.2*math.sin(2*math.pi*f*2*t)
        if mode == "metal":
            sample += 0.8*rng.uniform(-1,1)*math.exp(-t*7)
            sample += 0.3*math.sin(2*math.pi*713*t)*math.exp(-t*10)
        elif mode == "steam":
            sample = rng.uniform(-1,1)*0.85 + 0.35*math.sin(2*math.pi*f*t)
        elif mode == "alarm":
            sample += 0.3*math.sin(2*math.pi*f*0.5*t)
        value = max(-32767,min(32767,int(sample*envelope*6700)))
        pcm += struct.pack("<h",value)
    path = ROOT / "audio" / f"{name}.wav"
    with wave.open(str(path),"wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes(pcm)
    values = struct.unpack(f"<{count}h",pcm)
    assert any(values) and max(map(abs,values)) < 32767
    return {"file":str(path.relative_to(ROOT)),"rate":rate,"channels":1,
            "seconds":duration,"frames":count,"peak":max(map(abs,values)),
            "sha256":digest(path)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--palette",type=Path,default=ROOT.parents[2]/"data/misc/PALETTE_DAT")
    args = parser.parse_args()
    art = ROOT / "art"
    (ROOT/"audio").mkdir(exist_ok=True)
    colors, rgb = palette(args.palette)
    source = Image.open(art/"terrain-source-hd.png")
    terrain_hd = source.convert("RGBA").resize((1152,1536),Image.Resampling.LANCZOS)
    terrain_sd = sd(source,(288,384),colors)
    number = 0
    # Quantize the entire terrain before slicing, preserving shared seams.
    # Reflect the second half: both wrap boundaries match pixel-for-pixel.
    for reverse in (False,True):
        h = ImageOps.flip(terrain_hd) if reverse else terrain_hd
        s = ImageOps.flip(terrain_sd) if reverse else terrain_sd
        for row in range(12):
            for col in range(9):
                h.crop((col*128,row*128,(col+1)*128,(row+1)*128)).save(art/f"tile_{number:03}_hd.png")
                s.crop((col*32,row*32,(col+1)*32,(row+1)*32)).save(art/f"tile_{number:03}_sd.png")
                number += 1
    for terrain in (terrain_sd,terrain_hd):
        width,height = terrain.size
        flipped = ImageOps.flip(terrain)
        assert terrain.crop((0,height-1,width,height)).tobytes() == flipped.crop((0,0,width,1)).tobytes()
        assert flipped.crop((0,height-1,width,height)).tobytes() == terrain.crop((0,0,width,1)).tobytes()
    terrain_sd.save(art/"terrain-preview-sd.png")
    terrain_hd.save(art/"terrain-preview-hd.png")
    for name,size in [("foundry",(48,48))]:
        image = Image.open(art/f"{name}-source-hd.png")
        sd(image,size,colors).save(art/f"{name}_sd.png")
        image.convert("RGBA").resize((size[0]*4,size[1]*4),Image.Resampling.LANCZOS).save(art/f"{name}_hd.png")
    # Rebuild the cinematic briefing without changing the other artwork.
    runpy.run_path(str(art / "build_cinematic_briefing.py"), run_name="__main__")
    audio = {
        "approach":wav("approach",1.1,[110,147,196],"metal"),
        "foundry_alarm":wav("foundry_alarm",0.9,[220,330,220,330],"alarm"),
        "heat_warning":wav("heat_warning",0.65,[554,554,740],"alarm"),
        "slag_release":wav("slag_release",0.4,[100],"steam"),
        "foundry_shot":wav("foundry_shot",0.18,[130],"metal"),
        "foundry_shutdown":wav("foundry_shutdown",0.9,[120,85,55],"metal"),
        "launch_alarm":wav("launch_alarm",1.2,[196,147,110],"alarm"),
        "coolant_use":wav("coolant_use",0.55,[440,554,660],"steam"),
        "victory":wav("victory",1.2,[262,330,392,524])
    }
    allowed = {tuple(rgb[i:i+3]) for i in range(0,768,3)}
    raw_rgb = terrain_sd.convert("RGB").tobytes()
    pixels = {tuple(raw_rgb[i:i+3]) for i in range(0,len(raw_rgb),3)}
    assert set(pixels) <= allowed
    alpha = Image.open(art/"foundry_sd.png").getchannel("A")
    alpha_pixels = alpha.tobytes()
    assert sum(a==0 for a in alpha_pixels) > 0, "foundry sprite requires transparency"
    report = {"tile_count":number,"tile_logical_size":[32,32],"hd_tile_size":[128,128],
              "vertical_repeat":"12 forward + 12 reflected rows; identical wrap-boundary pixels",
              "seam_checks_passed":True,"sd_pixels_match_original_palette":True,
              "palette_sha256":digest(args.palette),"audio":audio,
              "sources":{p.name:{"size":list(Image.open(p).size),"sha256":digest(p)} for p in art.glob("*-source-hd.png")},
              "foundry_transparent_pixels":sum(a==0 for a in alpha_pixels)}
    (ROOT/"asset-report.json").write_text(json.dumps(report,indent=2)+"\n")
    print(f"Packaged {number} SD/HD tiles, briefing/foundry sprite and {len(audio)} WAV cues")


if __name__ == "__main__":
    main()
