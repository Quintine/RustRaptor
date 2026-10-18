#!/usr/bin/env python3
"""Rebuild only this generated mission briefing's SD/HD derivatives (Pillow)."""
from pathlib import Path
import hashlib
from PIL import Image, ImageOps
root = Path(__file__).resolve().parent
master = root / 'briefing-cinematic-generated-master.png'
if hashlib.sha256(master.read_bytes()).hexdigest() != '3a185ba599eab01222b849b226f676e5c20126f6a8b4b9ae4ca64fde3f285a88':
    raise SystemExit('Unexpected original briefing master bytes')
with Image.open(master) as image:
    hd = ImageOps.fit(image.convert('RGB'), (1280, 800), Image.Resampling.LANCZOS, centering=(0.5,0.5))
    hd.save(root / 'briefing-hd.png')
    hd.resize((320, 200), Image.Resampling.LANCZOS).save(root / 'briefing-sd.png')
