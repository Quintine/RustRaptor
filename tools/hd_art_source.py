#!/usr/bin/env python3
"""Decode a catalog picture into transparent PNG source references; never redraw art."""
import argparse
import struct
from pathlib import Path
from PIL import Image

def decode(path, palette):
    data = path.read_bytes()
    kind, _, _, width, height = struct.unpack_from('<iiiii', data)
    if not (0 < width <= 4096 and 0 < height <= 4096):
        raise ValueError('invalid picture dimensions')
    pixels = bytearray(width * height * 4)
    def put(x, y, value):
        p = (y * width + x) * 4
        pixels[p:p+4] = bytes((*palette[value], 255))
    if kind == 1:
        if len(data) < 20 + width * height:
            raise ValueError('truncated picture')
        for p, value in enumerate(data[20:20 + width * height]):
            put(p % width, p // width, value)
    elif kind == 0:
        off = 20
        while True:
            x, y, dest, length = struct.unpack_from('<iiii', data, off)
            off += 16
            if dest == -1:
                break
            if not (0 <= x < width and 0 <= y < height and 0 < length <= width - x and off + length <= len(data)):
                raise ValueError('invalid picture span')
            for i, value in enumerate(data[off:off+length]):
                put(x+i, y, value)
            off += length
    else:
        raise ValueError('unsupported picture type')
    return Image.frombytes('RGBA', (width, height), bytes(pixels))

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data', type=Path, default=Path('data'))
    p.add_argument('--asset', required=True, type=lambda s: int(s, 16))
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--preview-scale', type=int, default=1)
    args = p.parse_args()
    entries = {int(i, 16):(int(n), Path(name)) for i,n,name in (line.split() for line in (args.data/'INDEX').read_text().splitlines() if line.strip())}
    pal = (args.data/'misc/PALETTE_DAT').read_bytes()
    if len(pal) != 768:
        raise ValueError('invalid VGA palette')
    palette = [tuple((min(c,63)<<2)|(min(c,63)>>4) for c in pal[i:i+3]) for i in range(0,768,3)]
    size, relative = entries[args.asset]
    source = (args.data / relative).resolve()
    if not source.is_relative_to(args.data.resolve()) or source.stat().st_size != size:
        raise ValueError('invalid catalog entry')
    image = decode(source, palette)
    if args.preview_scale < 1 or args.preview_scale > 32:
        raise ValueError('preview scale must be 1..32')
    if args.preview_scale != 1:
        image = image.resize((image.width * args.preview_scale, image.height * args.preview_scale), Image.Resampling.NEAREST)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    image.save(args.output)
    print(f'{args.asset:05x}: {image.width}x{image.height} -> {args.output}')
if __name__ == '__main__':
    main()
