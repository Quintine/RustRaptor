"""Strict optional HD presentation metadata; source fidelity requires peer review."""
import struct
from fractions import Fraction

FRAME_KEYS = {"frame", "file", "logical_width", "logical_height", "origin",
              "source_sha256", "crop", "atlas_grid", "preserve_reserved_coverage", "native_nearest_cues", "original_detail_cells", "palette_constraint"}

def validate_atlas_grid(frame):
    grid = frame.get("atlas_grid")
    if grid is None:
        return None
    if type(grid) is not dict or set(grid) != {"columns", "rows", "column", "row"}:
        raise ValueError("atlas_grid needs exactly columns/rows/column/row")
    if any(type(value) is not int or not 0 <= value < 2**32 for value in grid.values()):
        raise ValueError("atlas_grid fields must be u32 integers")
    if frame.get("crop") is not None:
        raise ValueError("atlas_grid and crop are mutually exclusive")
    if grid["columns"] == 0 or grid["rows"] == 0 or grid["columns"] * grid["rows"] > 16384:
        raise ValueError("atlas_grid axes or cell count invalid")
    if grid["column"] >= grid["columns"] or grid["row"] >= grid["rows"]:
        raise ValueError("atlas_grid cell is outside its declared axes")
    return grid

def atlas_grid_geometry(frame, width, height):
    """Exact equal bounds and a bounded, uniform resident2x–4x canvas."""
    grid = validate_atlas_grid(frame)
    if grid is None:
        return None
    if any(type(value) is not int or value <= 0 for value in [width, height]):
        raise ValueError("invalid atlas dimensions")
    lw, lh = frame["logical_width"], frame["logical_height"]
    if any(type(value) is not int or not 0 < value < 2**32 for value in [lw, lh]):
        raise ValueError("invalid logical dimensions")
    cols, rows = grid["columns"], grid["rows"]
    if width * lh * rows != height * lw * cols:
        raise ValueError("rational atlas cell aspect differs from original canvas")
    if width < 2 * cols * lw or height < 2 * rows * lh:
        raise ValueError("rational atlas cell needs at least twice the logical resolution")
    factor = min(width // (cols * lw), height // (rows * lh), 4)
    left, right = Fraction(width * grid["column"], cols), Fraction(width * (grid["column"] + 1), cols)
    top, bottom = Fraction(height * grid["row"], rows), Fraction(height * (grid["row"] + 1), rows)
    floor = lambda value: value.numerator // value.denominator
    ceil = lambda value: -(-value.numerator // value.denominator)
    return dict(bounds=(left, top, right, bottom),
                pixels=(floor(left), floor(top), ceil(right), ceil(bottom)),
                resident=(lw * factor, lh * factor))

LEGACY_RETAINED_POLICY = "retained-original-details-v2-painted0255"
EXTENDED_RETAINED_POLICY = "retained-original-details-v3-max128-quarter-painted0255"
MAX256_RETAINED_POLICY = "retained-original-details-v4-max256-quarter-painted0255"

def retained_review_version_ok(version, retained_details):
    """Each old declaration keeps its ceiling, independent of map insertion order."""
    if type(version) is not str:
        return False
    ceilings = {LEGACY_RETAINED_POLICY: 64, EXTENDED_RETAINED_POLICY: 128,
                MAX256_RETAINED_POLICY: 256}
    return version in ceilings and all(len(cells) <= ceilings[version]
                                      for cells in retained_details.values())

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
    validate_atlas_grid(frame)
    constraint = frame.get("palette_constraint")
    if constraint is not None and (type(constraint) is not str or constraint != "original-painted-ordinary-v1"):
        raise ValueError("unknown palette constraint")
    if constraint is not None and source_payload is not None:
        original_palette_indices(frame, source_payload)
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
    if type(details) is not list or len(details) > 256:
        raise ValueError("original_detail_cells must contain at most256 Source cells")
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

        # Metadata-only preparation can check structure, not claim Source density.
        # Runtime, audit and extended registrar approval supply actual payloads.
        if len(details) > 64 and len(details) * 4 > sum(0 <= p <= 255 for p in indices):
            raise ValueError("65..256 Original details may retain at most one quarter of painted Source")


def original_palette_indices(frame, source_payload):
    """Derive the exact allowed set from authentic Source, never a supplied list.

    Metadata-only preparation cannot claim this validation. Rust and actual
    audit/registration provide the checked payload and keep PNG alpha separate.
    """
    constraint = frame.get("palette_constraint")
    if constraint is None:
        return None
    if type(constraint) is not str or constraint != "original-painted-ordinary-v1":
        raise ValueError("unknown palette constraint")
    sw, sh, indices = _indices(source_payload)
    if (type(frame.get("logical_width")) is not int or type(frame.get("logical_height")) is not int
            or (sw, sh) != (frame["logical_width"], frame["logical_height"])
            or not indices or any(not 0 <= i < 240 for i in indices)):
        raise ValueError("Original palette constraint requires opaque ordinary Source")
    return sorted(set(indices))
