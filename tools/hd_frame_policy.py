"""Strict optional HD presentation metadata; source fidelity requires peer review."""
import struct

FRAME_KEYS = {"frame", "file", "logical_width", "logical_height", "origin",
              "source_sha256", "crop", "preserve_reserved_coverage", "native_nearest_cues", "original_detail_cells"}

def _indices(payload):
    if len(payload) < 20:
        raise ValueError("truncated original picture")
    kind, _, _, width, height = struct.unpack_from("<iiiii", payload)
    if not (1 <= width <= 4096 and 1 <= height <= 4096 and width * height <= 1_048_576):
        raise ValueError("invalid original canvas")
    if kind == 1:
        if len(payload) < 20 + width * height:
            raise ValueError("truncated original raw picture")
        return width, height, payload[20:20 + width * height]
    if kind != 0:
        raise ValueError("unsupported original picture type")
    out = [256] * (width * height)
    off = 20
    runs = 0
    while True:
        if off + 16 > len(payload):
            raise ValueError("truncated original picture span")
        x, y, dest, length = struct.unpack_from("<iiii", payload, off)
        off += 16
        if dest == -1:
            break
        if not (x >= 0 and 0 <= y < height and length > 0 and x + length <= width
                and off + length <= len(payload)):
            raise ValueError("invalid original picture span")
        start = y * width + x
        out[start:start + length] = payload[off:off + length]
        off += length
        runs += 1
        if runs > len(out):
            raise ValueError("too many original picture spans")
    return width, height, out

def validate_frame_policy(frame, source_payload=None):
    if set(frame) - FRAME_KEYS:
        raise ValueError("unknown HD frame fields")
    if type(frame.get("preserve_reserved_coverage", False)) is not bool:
        raise ValueError("preserve_reserved_coverage must be a boolean")
    cues = frame.get("native_nearest_cues", [])
    if not isinstance(cues, list) or len(cues) > 64:
        raise ValueError("native_nearest_cues must contain at most64 cells")
    width, height = frame["logical_width"], frame["logical_height"]
    if type(width) is not int or type(height) is not int or not (0 < width < 2**32 and 0 < height < 2**32):
        raise ValueError("logical dimensions must be nonzero u32")
    previous = None
    for cue in cues:
        if not isinstance(cue, list) or len(cue) != 2 or any(type(n) is not int or not 0 <= n < 2**32 for n in cue):
            raise ValueError("native nearest cue must be a pair of u32 coordinates")
        if cue[0] >= width or cue[1] >= height:
            raise ValueError("native nearest cue outside original logical canvas")
        key = tuple(cue)
        if previous is not None and key <= previous:
            raise ValueError("native nearest cues must be sorted and unique")
        previous = key
    if source_payload is not None and cues:
        source_width, source_height, indices = _indices(source_payload)
        if (source_width, source_height) != (width, height):
            raise ValueError("logical canvas differs from original")
        if any(index == 256 for index in indices):
            raise ValueError("native nearest cues require an opaque original canvas")
        if any(indices[y * width + x] >= 240 for x, y in cues):
            raise ValueError("native nearest cue must be an ordinary original source cell")

    details = frame.get("original_detail_cells", [])
    if type(details) is not list or len(details) > 64:
        raise ValueError("original_detail_cells must contain at most64 Source cells")
    previous = None
    for cell in details:
        if type(cell) is not list or len(cell) != 2 or any(type(n) is not int or not 0 <= n < 2**32 for n in cell):
            raise ValueError("Original detail must be a pair of u32 coordinates")
        key = tuple(cell)
        if cell[0] >= width or cell[1] >= height or (previous is not None and key <= previous):
            raise ValueError("Original details must be inbounds sorted unique cells")
        if cell in cues:
            raise ValueError("Original detail and PNG-nearest policies may not overlap")
        previous = key
    if source_payload is not None and details:
        source_width, source_height, indices = _indices(source_payload)
        if (source_width, source_height) != (width, height):
            raise ValueError("Original detail canvas differs from Source")
        if any(not 0 <= indices[y * width + x] < 256 for x, y in details):
            raise ValueError("Original details select painted Source indices0–255 only")
