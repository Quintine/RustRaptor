# pulse_cannon artwork provenance

Generated locally with the built-in image generation tool and the imagegen skill. Original catalog IDs `0x102b1` (gray gun inventory icon) and `0x101cf` (8×8 projectile) were decoded and inspected as style/scale references. Original pixels are not included in the mod or Git. The prompt uses these references to create a distinct naval industrial weapon rather than copy the original.

Generated master images, SD/HD sprites and sound WAVs are tracked with the package, as requested. Original game pixels and decoded reference images remain outside Git. The generated source is converted into 16×16/64×64 equipment canvases and a 8×12 logical projectile canvas plus its 4× HD counterpart. Transparent margins remain inside the logical canvas. Sound synthesis is deterministic, PCM16 mono 22,050 Hz; `generate_audio.py` is the complete reproduction source.

Prompts and generated-source SHA256 hashes are recorded in `art-provenance.json` after output verification. Palette conversion occurs in the runtime loader; gameplay dimensions do not depend on HD artwork.
