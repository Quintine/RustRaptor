#!/usr/bin/env python3
"""Rebuild only this generated mission briefing's SD/HD derivatives (Pillow)."""
from pathlib import Path
import hashlib
from PIL import Image, ImageOps
root = Path(__file__).resolve().parent
master = root / 'briefing-cinematic-generated-master.png'
if hashlib.sha256(master.read_bytes()).hexdigest() != '9cb3a40a4bc07894bd01da6b4c2911ba69df1926e4e23dfcaa3ccf7eced742bc':
    raise SystemExit('Unexpected original briefing master bytes')
with Image.open(master) as image:
    hd = ImageOps.fit(image.convert('RGB'), (1280, 800), Image.Resampling.LANCZOS, centering=(0.5,0.5))
    hd.save(root / 'briefing_hd.png')
    hd.resize((320, 200), Image.Resampling.LANCZOS).save(root / 'briefing_sd.png')
