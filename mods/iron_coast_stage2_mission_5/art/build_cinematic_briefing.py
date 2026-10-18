#!/usr/bin/env python3
"""Reproduce the briefing from its bundled master; remove one baked deck glyph."""
from pathlib import Path
import hashlib
from PIL import Image, ImageOps, ImageDraw, ImageFilter
root = Path(__file__).resolve().parent
master = root / "briefing-cinematic-generated-master.png"
assert hashlib.sha256(master.read_bytes()).hexdigest() == "f800320ff740cbdfe1f16fbfd3d680f8941a6ce632364543f1f85b1827c07977", "Unexpected briefing master"
with Image.open(master) as source:
    hd = ImageOps.fit(source.convert("RGB"), (1280, 800), Image.Resampling.LANCZOS, centering=(0.5, 0.5))
# Source-only finite paint cleanup: white H/ring, never the aircraft or coastline.
# The accepted master stays untouched. Deterministic four-neighbor diffusion
# restores nearby deck colors only inside this 100x44 box and dilated paint mask.
roi = (1038, 353, 1138, 397)
crop = hd.crop(roi)
region = Image.new("L", hd.size)
ImageDraw.Draw(region).polygon([(1043,362),(1099,358),(1133,375),(1113,385),(1068,391)], fill=255)
region = region.crop(roi)
mask = Image.new("L", crop.size)
w, h = crop.size
mask.putdata([255 if region.getpixel((x,y)) and sum(crop.getpixel((x,y))) > 330 else 0 for y in range(h) for x in range(w)])
mask = mask.filter(ImageFilter.MaxFilter(3))
pixels = [list(map(float, crop.getpixel((x,y)))) for y in range(h) for x in range(w)]
indices = [y*w+x for y in range(1,h-1) for x in range(1,w-1) if mask.getpixel((x,y))]
assert len(indices) == 992
for i in indices:
    pixels[i] = [70.,75.,78.]
for _ in range(300):
    for i in indices:
        pixels[i] = [sum(pixels[j][c] for j in (i-1,i+1,i-w,i+w))/4 for c in range(3)]
clean = Image.new("RGB", crop.size)
clean.putdata([tuple(round(value) for value in pixel) for pixel in pixels])
hd.paste(clean, roi[:2])
hd.save(root / "briefing-hd.png")
hd.resize((320,200), Image.Resampling.LANCZOS).save(root / "briefing-sd.png")
