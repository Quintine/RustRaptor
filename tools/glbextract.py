#!/usr/bin/env python3
"""Extract Raptor: Call of the Shadows .GLB archives into a modern asset tree.

Source format (reverse-engineered from the GLib library shipped with the
game, see raptor/src/glbapi.cpp):

  - A GLB file is a sequence of 28-byte records:
        uint32 opt       0 = plain, 1 = encrypted
        uint32 offset    payload offset (header record: item count)
        uint32 filesize  payload size   (header record: unused)
        char   name[16]  NUL-padded item name
  - Record 0 is the header; its `offset` field holds the item count.
  - Records 1..count are the item descriptor table, starting at byte 28.
  - Every record and every encrypted payload is scrambled with the same
    rolling cipher keyed on "32768GLB", seeded at 25 (SEED in glbapi.h).

Output layout (OUTDIR, default ./data):

    INDEX              catalog: "<hex asset id> <size> <relative path>"
    music/             *_MUS
    sound/             *_FX, *_SFX
    sprites/           *_PIC, *_AGX
    tiles/             *_BLK, *TILES
    maps/              *_MAP
    fonts/             *_FNT
    text/              *_TXT, *_DIZ, *_DIX, *_ERR, *_HELP
    ui/                *_SWD (window layouts)
    movies/            *_MDS
    demos/             *_REC
    misc/              everything else

Asset ids are the engine handles: (archive slot << 16) | item index, so
FILE0001 item 5 is 0x10005. The INDEX file is sorted by id and is what the
engine loads at startup (GLB_LoadCatalog in glbapi.cpp).

Usage:
    glbextract.py list   FILE0000.GLB [...]
    glbextract.py extract -o OUTDIR FILE0000.GLB [...]
"""

import argparse
import re
import struct
import sys
from pathlib import Path

KEY = b"32768GLB"
SEED = 25  # SEED in glbapi.h
RECORD = struct.Struct("<III16s")  # opt, offset, filesize, name[16]
NORMAL, ENCODED = 0, 1

# name suffix -> category directory
CATEGORIES = [
    ("MUS", "music"),
    ("SFX", "sound"), ("FX", "sound"),
    ("PIC", "sprites"), ("AGX", "sprites"),
    ("BLK", "tiles"), ("TILES", "tiles"),
    ("MAP", "maps"),
    ("FNT", "fonts"),
    ("TXT", "text"), ("DIZ", "text"), ("DIX", "text"),
    ("ERR", "text"), ("HELP", "text"),
    ("SWD", "ui"),
    ("MDS", "movies"),
    ("REC", "demos"),
]


def classify(name: str) -> str:
    for suffix, cat in CATEGORIES:
        if name.endswith("_" + suffix) or name.endswith(suffix):
            return cat
    return "misc"


def crypt(data: bytes, key: bytes = KEY) -> bytes:
    """GLB_DeCrypt (its inverse, GLB_EnCrypt, differs only by +/- sign).

    Byte-exact despite the original's signed-char arithmetic: the stored
    byte is the mathematical result mod 256 either way. The chain state is
    the previous *ciphertext* byte, as in GLB_DeCrypt.
    """
    out = bytearray(len(data))
    kidx = SEED % len(key)
    prev = key[kidx]
    for i, b in enumerate(data):
        out[i] = (b - key[kidx] - prev) % 256
        prev = b
        kidx = (kidx + 1) % len(key)
    return bytes(out)


def read_entries(buf: bytes, source: str):
    if len(buf) < RECORD.size:
        sys.exit(f"{source}: too small to hold a GLB header")

    _opt, count, _size, _name = RECORD.unpack(crypt(buf[: RECORD.size]))
    entries = []
    pos = RECORD.size
    for _ in range(count):
        if pos + RECORD.size > len(buf):
            sys.exit(f"{source}: descriptor table truncated")
        opt, off, size, name = RECORD.unpack(crypt(buf[pos : pos + RECORD.size]))
        entries.append((opt, off, size, name.split(b"\0", 1)[0].decode("ascii", "replace")))
        pos += RECORD.size
    return entries


def sanitize(name: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9._$-]", "_", name)
    return clean or "unnamed"


def extract(glb: Path, outdir: Path, seen: dict):
    """Write one archive's items into category dirs.

    `seen` is shared across archives so identical names landing in the
    same category get distinct suffixes (last-writer-wins would corrupt
    the catalog sizes otherwise).

    Returns catalog rows: (asset_id, size, relative path).
    """
    slot = int(glb.stem[4:])  # FILE000N -> N
    buf = glb.read_bytes()
    entries = read_entries(buf, str(glb))

    rows = []
    for idx, (opt, off, size, name) in enumerate(entries):
        data = buf[off : off + size]
        if len(data) != size:
            print(f"  warning: {glb.name}[{idx}] {name}: "
                  f"payload {off}+{size} exceeds file size {len(buf)}", file=sys.stderr)
        if opt == ENCODED:
            data = crypt(data)
        elif opt != NORMAL:
            print(f"  warning: {glb.name}[{idx}] {name}: unknown opt={opt}", file=sys.stderr)

        cat = classify(name)
        fname = sanitize(name)
        key = f"{cat}/{fname}"
        if key in seen:
            seen[key] += 1
            fname = f"{fname}.{seen[key]}"
        else:
            seen[key] = 0
        (outdir / cat).mkdir(parents=True, exist_ok=True)
        (outdir / cat / fname).write_bytes(data)
        rows.append(((slot << 16) | idx, len(data), f"{cat}/{fname}"))

    return rows

def listing(glb: Path) -> None:
    entries = read_entries(glb.read_bytes(), str(glb))
    print(f"{glb.name}: {len(entries)} items")
    for idx, (opt, off, size, name) in enumerate(entries):
        enc = " enc" if opt == ENCODED else ""
        print(f"  [{idx:4d}] {name:<16} {size:>10} bytes @ {off:#08x}{enc}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["list", "extract"])
    ap.add_argument("-o", "--out", default="data", help="asset root (default: ./data)")
    ap.add_argument("files", nargs="+", type=Path, help=".GLB archives")
    args = ap.parse_args()

    outdir = None
    if args.command == "extract":
        outdir = Path(args.out)
        outdir.mkdir(parents=True, exist_ok=True)

    total = 0
    rows = []
    seen = {}
    for glb in args.files:
        if not glb.is_file():
            sys.exit(f"{glb}: not found")
        if args.command == "list":
            listing(glb)
        else:
            r = extract(glb, outdir, seen)
            rows.extend(r)
            total += len(r)
            print(f"{glb.name}: wrote {len(r)} items")

    if rows:
        rows.sort()
        (outdir / "INDEX").write_text(
            "".join(f"{uid:x} {size} {path}\n" for uid, size, path in rows),
            encoding="ascii")
        print(f"total: {total} items -> {outdir}/INDEX")


if __name__ == "__main__":
    main()
