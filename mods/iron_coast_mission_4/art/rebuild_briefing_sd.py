#!/usr/bin/env python3
"""Refresh only this menu briefing SD image; gameplay artwork is untouched."""
from pathlib import Path
import hashlib
from PIL import Image
root = Path(__file__).resolve().parent
source = root / "briefing_hd.png"
assert hashlib.sha256(source.read_bytes()).hexdigest() == "cd987c13bc55bba2620379ca435c0cccf08d7564364d730c65d0be285bb82221", "Unexpected HD briefing"
with Image.open(source) as image:
    image.convert("RGB").resize((320,200), Image.Resampling.LANCZOS).save(root / "briefing_sd.png")
