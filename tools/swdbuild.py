#!/usr/bin/env python3
"""Dump and build Raptor .SWD dialog assets.

On-disk format (little-endian), mirrored from src/swdapi.h:

    SWIN header    120 bytes   <8i 16s 16s 14i>
    SFIELD32[]     148 bytes   <8i 16s 16s i 16s 15i i>  (sptr -> PlaceHolder)
    text blob      NUL-padded strings

Each TEXT/BUTTON/INPUT/DRAGBAR field stores its text at `txtoff` RELATIVE
TO ITS OWN RECORD (SWD_ReformatFieldData compensates the 64-bit struct
growth with `(numflds - i) * 4`, which only closes under that reading).
Other field types never dereference txtoff.

Modes:
  dump  <file.swd>                 pretty-print SWIN, fields, text blob
  build <spec.py> <out.swd>        assemble a .swd from a Python spec

Spec module contract (see tools/opts_swd_spec.py):
  from swdbuild import BUTTON_TEMPLATE, ...   # clone-source records
  SWIN   = {...}     # all 24 ints + name/item_name strings
  FIELDS = [ {...}, ... ]   # {**TEMPLATE, **overrides}; "text_index" links
                            # the field to TEXTS[i] and computes txtoff
  TEXTS  = ["...", ...]     # blob entries, laid out in list order
"""

import argparse
import importlib.util
import struct
import sys
from pathlib import Path

SWIN_STRUCT = struct.Struct("<8i16s16s14i")
FIELD_STRUCT = struct.Struct("<8i16s16si16s15ii")

SWIN_KEYS = [
    "version", "swdsize", "arrowflag", "display", "opt3", "opt4", "id", "type",
    "name", "item_name",
    "item", "picflag", "lock", "fldofs", "txtofs", "firstfld", "opt", "color",
    "numflds", "x", "y", "lx", "ly", "shadow",
]
FIELD_KEYS = [
    "opt", "id", "hotkey", "kbflag", "opt3", "opt4", "input_opt", "bstatus",
    "name", "item_name", "item", "font_name",
    "fontid", "fontbasecolor", "maxchars", "picflag", "color", "lite", "mark",
    "saveflag", "shadow", "selectable", "x", "y", "lx", "ly",
]

FLD_TEXT, FLD_BUTTON, FLD_INPUT, FLD_DRAGBAR = 1, 2, 5, 6  # txtoff-carrying


def _s(raw: bytes) -> str:
    return raw.split(b"\0", 1)[0].decode("ascii", "replace")


def _pack_str(text, field):
    raw = text.encode("ascii")
    if len(raw) > 16:
        raise ValueError(f"{field}: string longer than 16 chars: {text!r}")
    return raw.ljust(16, b"\0")


def _check_keys(where, given, required, optional=()):
    missing = [k for k in required if k not in given]
    extra = [k for k in given if k not in required and k not in optional]
    if missing or extra:
        raise ValueError(f"{where}: missing {missing}, unknown {extra}")

BUMPIN_TEMPLATE = {
    "opt": 7, "id": 0, "hotkey": 0, "kbflag": 10, "opt3": 0, "opt4": 0,
    "input_opt": 0, "bstatus": 0,
    "name": "", "item_name": "",
    "item": 0, "font_name": "SYSTEM_FNT", "fontid": 5, "fontbasecolor": 0,
    "maxchars": 3, "picflag": 0, "color": 1, "lite": 15, "mark": 0,
    "saveflag": 0, "shadow": 0, "selectable": 0,
    "x": 0, "y": 0, "lx": 127, "ly": 3,
}
ICON_TEMPLATE = {
    "opt": 9, "id": 0, "hotkey": 0, "kbflag": 30, "opt3": 0, "opt4": 0,
    "input_opt": 0, "bstatus": 0,
    "name": "PIC1", "item_name": "",
    "item": -1, "font_name": "SYSTEM_FNT", "fontid": 5, "fontbasecolor": 0,
    "maxchars": 1, "picflag": 2, "color": 8, "lite": 15, "mark": 0,
    "saveflag": 0, "shadow": 0, "selectable": 0,
    "x": 11, "y": 35, "lx": 16, "ly": 11,
}
BUTTON_TEMPLATE = {
    "opt": 2, "id": 1, "hotkey": 0x20, "kbflag": 80, "opt3": 0, "opt4": 0,
    "input_opt": 0, "bstatus": 0,
    "name": "DETAIL", "item_name": "STEXTURE_PIC",
    "item": 0x10024, "font_name": "FONT2_FNT", "fontid": 0x10004,
    "fontbasecolor": 82, "maxchars": 13, "picflag": 1, "color": 8, "lite": 15,
    "mark": 0, "saveflag": 0, "shadow": 1, "selectable": 0,
    "x": 35, "y": 35, "lx": 118, "ly": 12,
}
TEXT_TEMPLATE = {
    "opt": 1, "id": 150, "hotkey": 0, "kbflag": 90, "opt3": 0, "opt4": 0,
    "input_opt": 0, "bstatus": 0,
    "name": "", "item_name": "",
    "item": 0, "font_name": "FONT2_FNT", "fontid": 0x10004, "fontbasecolor": 82,
    "maxchars": 13, "picflag": 0, "color": 8, "lite": 15, "mark": 0,
    "saveflag": 0, "shadow": 0, "selectable": 0,
    "x": 35, "y": 57, "lx": 104, "ly": 8,
}
VIEWAREA_TEMPLATE = {
    "opt": 11, "id": 0, "hotkey": 0, "kbflag": 110, "opt3": 0, "opt4": 0,
    "input_opt": 0, "bstatus": 0,
    "name": "VMUSIC", "item_name": "",
    "item": 0, "font_name": "SYSTEM_FNT", "fontid": 5, "fontbasecolor": 0,
    "maxchars": 1, "picflag": 0, "color": 8, "lite": 15, "mark": 0,
    "saveflag": 0, "shadow": 0, "selectable": 0,
    "x": 35, "y": 68, "lx": 127, "ly": 13,
}
def parse(path: Path):
    """Return (swin dict, field dicts, blob bytes) for a .swd file."""
    data = path.read_bytes()
    if len(data) < SWIN_STRUCT.size:
        raise ValueError(f"{path}: {len(data)} bytes, shorter than SWIN header")

    raw = SWIN_STRUCT.unpack_from(data, 0)
    swin = dict(zip(SWIN_KEYS[:8], raw[:8]))
    swin["name"] = _s(raw[8])
    swin["item_name"] = _s(raw[9])
    swin.update(dict(zip(SWIN_KEYS[10:], raw[10:])))

    numflds = swin["numflds"]
    fields = []
    for i in range(numflds):
        off = swin["fldofs"] + i * FIELD_STRUCT.size
        if off + FIELD_STRUCT.size > len(data):
            raise ValueError(f"{path}: field {i} at {off} past EOF")
        fr = FIELD_STRUCT.unpack_from(data, off)
        fld = dict(zip(FIELD_KEYS[:8], fr[:8]))
        fld["name"] = _s(fr[8])
        fld["item_name"] = _s(fr[9])
        fld["item"] = fr[10]
        fld["font_name"] = _s(fr[11])
        fld.update(dict(zip(FIELD_KEYS[12:], fr[12:26])))
        fld["txtoff"] = fr[26]
        fld["_offset"] = off
        fields.append(fld)

    blob_start = swin["fldofs"] + numflds * FIELD_STRUCT.size
    return swin, fields, data[blob_start:]


def dump(path: Path) -> None:
    swin, fields, blob = parse(path)
    print(f"file: {path}  ({path.stat().st_size} bytes, blob at "
          f"{SWIN_STRUCT.size + len(fields) * FIELD_STRUCT.size})")
    print("SWIN:")
    for k in SWIN_KEYS:
        print(f"  {k:<12} {swin[k]!r}")
    for i, fld in enumerate(fields):
        print(f"field[{i:2d}] at +{fld['_offset']}:")
        for k in FIELD_KEYS:
            print(f"    {k:<14} {fld[k]!r}")
        if fld["opt"] in (FLD_TEXT, FLD_BUTTON, FLD_INPUT, FLD_DRAGBAR):
            blob_start = SWIN_STRUCT.size + len(fields) * FIELD_STRUCT.size
            t = blob[fld["_offset"] + fld["txtoff"] - blob_start:]
            text = t.split(b"\0", 1)[0].decode("ascii", "replace")
            print(f"    text          {text!r}")
        print()


def build(spec_path: Path, out_path: Path) -> None:
    # Import swdbuild itself under its own name so specs can pull templates.
    self_spec = importlib.util.spec_from_file_location(
        "swdbuild", Path(__file__).resolve())
    self_mod = importlib.util.module_from_spec(self_spec)
    sys.modules["swdbuild"] = self_mod
    self_spec.loader.exec_module(self_mod)
    spec = importlib.util.spec_from_file_location("swd_spec", spec_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    swin_in, fields_in, texts = mod.SWIN, mod.FIELDS, mod.TEXTS
    _check_keys("SWIN", swin_in, SWIN_KEYS)
    if len(fields_in) != swin_in["numflds"]:
        raise ValueError(f"SWIN.numflds={swin_in['numflds']} but "
                         f"len(FIELDS)={len(fields_in)}")
    if swin_in["fldofs"] != SWIN_STRUCT.size:
        raise ValueError(f"SWIN.fldofs must be {SWIN_STRUCT.size}")

    # Lay out the text blob: entry i is padded to the max slot size its
    # referencing fields need (SWD_SetFieldText writes maxchars bytes).
    slot_size = [len(t.encode("ascii")) + 1 for t in texts]
    for i, fld in enumerate(fields_in):
        _check_keys(f"FIELDS[{i}] (after template merge)", fld,
                    FIELD_KEYS, optional=("text_index",))
        ti = fld.get("text_index")
        if ti is not None:
            if not 0 <= ti < len(texts):
                raise ValueError(f"FIELDS[{i}]: text_index {ti} out of range")
            slot_size[ti] = max(slot_size[ti], fld["maxchars"])

    blob = bytearray()
    slot_off = []
    for text, size in zip(texts, slot_size):
        raw = text.encode("ascii")
        if len(raw) >= size:
            raise ValueError(f"TEXTS entry {text!r} does not fit slot {size}")
        slot_off.append(len(blob))
        blob += raw.ljust(size, b"\0")
    blob_start = SWIN_STRUCT.size + len(fields_in) * FIELD_STRUCT.size

    # Header bookkeeping: total file size and blob offset (the original
    # asset stores exactly these; specs pass 0 and get the real values).
    swin = dict(swin_in)
    swin["swdsize"] = blob_start + len(blob)
    swin["txtofs"] = blob_start

    out = bytearray()
    swin_vals = [swin[k] for k in SWIN_KEYS[:8]]
    out += SWIN_STRUCT.pack(*swin_vals,
                            _pack_str(swin["name"], "SWIN.name"),
                            _pack_str(swin["item_name"], "SWIN.item_name"),
                            *[swin[k] for k in SWIN_KEYS[10:]])

    for i, fld in enumerate(fields_in):
        rec_off = SWIN_STRUCT.size + i * FIELD_STRUCT.size
        txtoff = 0
        ti = fld.get("text_index")
        if ti is not None:
            txtoff = blob_start + slot_off[ti] - rec_off
        out += FIELD_STRUCT.pack(
            *[fld[k] for k in FIELD_KEYS[:8]],
            _pack_str(fld["name"], f"FIELDS[{i}].name"),
            _pack_str(fld["item_name"], f"FIELDS[{i}].item_name"),
            fld["item"],
            _pack_str(fld["font_name"], f"FIELDS[{i}].font_name"),
            *[fld[k] for k in FIELD_KEYS[12:]],
            txtoff, 0)

    assert len(out) == blob_start
    out += blob
    out_path.write_bytes(out)
    print(f"{out_path}: {len(out)} bytes "
          f"({len(fields_in)} fields, {len(texts)} text slots)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="mode", required=True)
    sub.add_parser("dump").add_argument("swd", type=Path)
    bp = sub.add_parser("build")
    bp.add_argument("spec", type=Path)
    bp.add_argument("out", type=Path)
    args = ap.parse_args()

    if args.mode == "dump":
        dump(args.swd)
    else:
        build(args.spec, args.out)


if __name__ == "__main__":
    main()
