#!/usr/bin/env python3
"""Refresh only this menu briefing SD image; gameplay artwork is untouched."""
from pathlib import Path
import hashlib
from PIL import Image
root = Path(__file__).resolve().parent
source = root / "briefing_hd.png"
assert hashlib.sha256(source.read_bytes()).hexdigest() == "cb87cd81b6d8e87c0ceb5469d1832879906c9cee48728e2c56459b51d8a07b2a", "Unexpected HD briefing"
with Image.open(source) as image:
    image.convert("RGB").resize((320,200), Image.Resampling.LANCZOS).save(root / "briefing_sd.png")
