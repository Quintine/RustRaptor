#!/usr/bin/env python3
"""Rebuild Aurora's SD/HD briefing from its unchanged generated master."""
from pathlib import Path
import hashlib
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent
source = ROOT / 'art/briefing-generated-master.png'
expected = 'ddb0b50b344611d49038ac2d5b8e4f609b66daa8c7e3799d4530804780cb1a3f'
if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
    raise SystemExit('Unexpected briefing master; preserve the recorded original bytes.')
with Image.open(source) as image:
    image.load()
    hd = ImageOps.fit(image.convert('RGB'), (1280, 800), Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    hd.save(ROOT / 'art/briefing_hd.png')
    hd.resize((320, 200), Image.Resampling.LANCZOS).save(ROOT / 'art/briefing_sd.png')
