#!/usr/bin/env python3
"""Deterministic DERIVED terrain reconstruction, never a generator-return asset.

The authentic opaque ordinary Source controls geometry and low-frequency colour.
Only a bounded monochrome fine band from the parent image survives. Material
boundaries use the engine's ScaleNx4 shape, and interpolation never mixes material
families. This deliberately removes coarse generated stones and colour drift.
No asset registration, frame policy, game Source or parent image is modified.
Requires NumPy and Pillow; run with the bundled dependency Python.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import struct
import numpy as np
from PIL import Image

METHOD = 'source-nx4-material-normalized-lowpass-plus-bounded-parent-fine-luma-v1'
DEFAULTS = dict(output_side=512, source_sigma=1.0, residual_sigma_fine=0.65,
                residual_sigma_coarse=2.2, residual_percentile=95.0,
                residual_amplitude=dict(gray=2.0, olive=1.25, soil=2.5, rim=1.5))
FAMILY_NAMES = ('gray', 'olive', 'soil', 'rim')

def read_regular(path):
    p = Path(path).absolute()
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        a = os.fstat(fd)
        if not stat.S_ISREG(a.st_mode):
            raise ValueError('input must be a regular file')
        with os.fdopen(fd, 'rb', closefd=False) as f:
            data = f.read()
        b = os.fstat(fd)
        if (a.st_dev, a.st_ino, a.st_size, a.st_mtime_ns) != (b.st_dev, b.st_ino, b.st_size, b.st_mtime_ns):
            raise ValueError('input changed during read')
    finally:
        os.close(fd)
    return data, dict(path=str(p), sha256=hashlib.sha256(data).hexdigest(),
                      size=a.st_size, mtime_ns=a.st_mtime_ns, mode=a.st_mode)

def decode_source(data):
    if len(data) < 20:
        raise ValueError('short Source PIC')
    header = struct.unpack_from('<5i', data)
    kind, count, offset, width, height = header
    if (kind, count, offset) != (1, 1, 0) or not (1 <= width <= 128 and 1 <= height <= 128):
        raise ValueError('this tool supports a single uncompressed Source PIC only')
    if len(data) != 20 + width * height:
        raise ValueError('Source payload size mismatch')
    indices = np.frombuffer(data[20:], dtype=np.uint8).reshape(height, width).copy()
    if np.any(indices >= 240):
        raise ValueError('only fully opaque ordinary Source indices0..239 are supported')
    return indices

def palette_rgb(data):
    if len(data) != 768:
        raise ValueError('palette must contain256 three-channel6-bit entries')
    a = np.minimum(np.frombuffer(data, np.uint8).reshape(256, 3).astype(np.uint16), 63)
    return ((a << 2) | (a >> 4)).astype(np.uint8)

def material_families(indices):
    """Explicit supported Raptor palette families; no per-asset painted mask."""
    a = np.asarray(indices)
    out = np.full(a.shape, -1, dtype=np.int8)
    out[a < 32] = 0
    out[(a >= 60) & (a <= 63)] = 1
    out[((a >= 192) & (a <= 223)) | (a == 239)] = 2
    out[(a >= 224) & (a <= 238)] = 3
    if np.any(out < 0):
        raise ValueError('Source contains unsupported material family')
    return out

def scale_nx(indices, factor):
    """Exact Scale2x/3x; Scale4x is two Scale2x passes, as render::upscale."""
    a = np.asarray(indices)
    if factor == 1:
        return a.copy()
    if factor == 4:
        return scale_nx(scale_nx(a, 2), 2)
    if factor not in (2, 3) or a.ndim != 2:
        raise ValueError('ScaleNx factor must be1..4 on a plane')
    h, w = a.shape
    p = np.pad(a, 1, mode='edge')
    out = np.empty((h * factor, w * factor), dtype=a.dtype)
    for y in range(h):
        for x in range(w):
            nw, n, ne, west, c, east, sw, south, se = p[y:y+3, x:x+3].flatten().tolist()
            cells = [c] * (factor * factor)
            if n != south and west != east:
                if factor == 2:
                    cells = [west if west == n else c, east if n == east else c,
                             west if west == south else c, east if south == east else c]
                else:
                    cells = [west if west == n else c,
                             n if (west == n and c != ne) or (n == east and c != nw) else c,
                             east if n == east else c,
                             west if (west == n and c != sw) or (west == south and c != nw) else c,
                             c,
                             east if (n == east and c != se) or (south == east and c != ne) else c,
                             west if west == south else c,
                             south if (west == south and c != se) or (south == east and c != sw) else c,
                             east if south == east else c]
            out[y*factor:(y+1)*factor, x*factor:(x+1)*factor] = np.array(cells).reshape(factor, factor)
    return out

def gaussian(a, sigma):
    a = np.asarray(a, dtype=np.float64)
    if not math.isfinite(sigma) or sigma <= 0:
        raise ValueError('sigma must be finite and positive')
    radius = int(math.ceil(3 * sigma))
    q = np.arange(-radius, radius + 1, dtype=np.float64)
    k = np.exp(-0.5 * (q / sigma) ** 2)
    k /= k.sum()
    b = a
    for axis in (0, 1):
        padding = [(0, 0)] * a.ndim
        padding[axis] = (radius, radius)
        p = np.pad(b, padding, mode='edge')
        b = np.zeros_like(a)
        for i, weight in enumerate(k):
            sl = [slice(None)] * a.ndim
            sl[axis] = slice(i, i + a.shape[axis])
            b += weight * p[tuple(sl)]
    return b

def resize_float(a, size):
    a = np.asarray(a, np.float32)
    if a.ndim == 3:
        return np.stack([resize_float(a[..., i], size) for i in range(a.shape[2])], -1)
    return np.asarray(Image.fromarray(a).resize(size, Image.Resampling.BILINEAR), np.float64)

def validate_parameters(p, source_shape):
    if set(p) != set(DEFAULTS):
        raise ValueError('unknown or missing reconstruction parameter')
    side = p['output_side']
    if type(side) is not int or not 4 * max(source_shape) <= side <= 2048 or side % (4 * max(source_shape)):
        raise ValueError('output must be an integer expansion of SourceNx4, at least4x')
    for name in ('source_sigma', 'residual_sigma_fine', 'residual_sigma_coarse'):
        if type(p[name]) not in (int, float) or not math.isfinite(p[name]) or not 0 < p[name] <= 8:
            raise ValueError('invalid smoothing parameter')
    if p['residual_sigma_fine'] >= p['residual_sigma_coarse']:
        raise ValueError('fine band must be narrower than coarse band')
    q = p['residual_percentile']
    if type(q) not in (int, float) or not math.isfinite(q) or not 50 <= q <= 100:
        raise ValueError('invalid residual percentile')
    if set(p['residual_amplitude']) != set(FAMILY_NAMES):
        raise ValueError('all material residual amplitudes required')
    for v in p['residual_amplitude'].values():
        if type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 8:
            raise ValueError('invalid bounded residual amplitude')

def reconstruct(indices, palette, generated_rgb, parameters=None):
    p = json.loads(json.dumps(DEFAULTS if parameters is None else parameters))
    a = np.asarray(indices)
    if a.ndim != 2 or a.shape[0] != a.shape[1] or a.size == 0 or np.any(a >= 240) or np.any(a < 0):
        raise ValueError('square opaque ordinary Source required')
    validate_parameters(p, a.shape)
    guide_indices = scale_nx(a, 4)
    labels = material_families(guide_indices)
    guide = np.asarray(palette)[guide_indices].astype(np.float64)
    side = p['output_side']
    factor = side // labels.shape[0]
    owners = np.repeat(np.repeat(labels, factor, 0), factor, 1)
    base = np.zeros((side, side, 3), dtype=np.float64)
    # Normalized filtering and interpolation are performed separately per family.
    # Thus no olive/soil/rim/gray mixture can shift a Source material boundary.
    for family in np.unique(labels):
        mask = (labels == family).astype(np.float64)
        weights = resize_float(gaussian(mask, p['source_sigma']), (side, side))
        numerator = resize_float(gaussian(guide * mask[..., None], p['source_sigma']), (side, side))
        field = numerator / np.maximum(weights[..., None], 1e-12)
        base[owners == family] = field[owners == family]
    raw = np.asarray(generated_rgb)
    if raw.ndim != 3 or raw.shape[2] != 3 or raw.dtype != np.uint8:
        raise ValueError('generated input must be RGB uint8')
    parent = np.asarray(Image.fromarray(raw).resize((side, side), Image.Resampling.LANCZOS), np.float64)
    luma = parent @ np.array([0.2126, 0.7152, 0.0722])
    band = gaussian(luma, p['residual_sigma_fine']) - gaussian(luma, p['residual_sigma_coarse'])
    band -= band.mean()
    divisor = max(float(np.percentile(np.abs(band), p['residual_percentile'])), 1.0)
    fine = np.clip(band / divisor, -1, 1)
    amplitudes = np.array([p['residual_amplitude'][n] for n in FAMILY_NAMES])
    residual = fine * amplitudes[owners]
    output = np.clip(np.rint(base + residual[..., None]), 0, 255).astype(np.uint8)
    base8 = np.clip(np.rint(base), 0, 255).astype(np.uint8)
    metrics = dict(method=METHOD, source_shape=list(a.shape), output_shape=list(output.shape),
                   sourceNx4_indices_sha256=hashlib.sha256(guide_indices.astype('<u2').tobytes()).hexdigest(),
                   geometry_material_labels_sha256=hashlib.sha256(owners.tobytes()).hexdigest(),
                   material_output_pixels={FAMILY_NAMES[int(i)]: int((owners == i).sum()) for i in np.unique(owners)},
                   generated_fine_band_std=float(band.std()), fine_normalization=divisor,
                   maximum_retained_luma_residual=float(np.abs(residual).max()),
                   pixels_changed_from_Source_guided_base=int(np.any(output != base8, axis=2).sum()),
                   mean_absolute_generated_residual=float(np.abs(residual).mean()),
                   output_RGB_sha256=hashlib.sha256(output.tobytes()).hexdigest(),
                   output_is_derived_not_untouched=True,
                   limits='SourceNx4 family geometry, normalized Source colour, bounded generated fine luma; no generated coarse structure or hue retained. Not a material or context approval.')
    return output, base8, owners, metrics

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--recipe', required=True)
    ap.add_argument('--output', required=True)
    args = ap.parse_args(argv)
    recipe_path = Path(args.recipe).absolute()
    recipe_bytes, recipe_pin = read_regular(recipe_path)
    recipe = json.loads(recipe_bytes)
    if recipe.get('method') != METHOD or not isinstance(recipe.get('frames'), list) or not recipe['frames']:
        raise ValueError('wrong method or empty recipe')
    def recipe_input(binding):
        path = Path(binding['path'])
        if not path.is_absolute():
            path = recipe_path.parent / path
        return read_regular(path)
    palette_bytes, palette_pin = recipe_input(recipe['palette'])
    if palette_pin['sha256'] != recipe['palette']['sha256']:
        raise ValueError('palette identity mismatch')
    palette = palette_rgb(palette_bytes)
    prepared = []
    seen = set()
    for row in recipe['frames']:
        asset = row['asset']
        if not isinstance(asset, str) or len(asset) != 5 or any(c not in '0123456789abcdef' for c in asset) or asset in seen:
            raise ValueError('invalid or duplicate asset')
        seen.add(asset)
        source, source_pin = recipe_input(row['Source'])
        parent_bytes, parent_pin = recipe_input(row['parent_raw'])
        if source_pin['sha256'] != row['Source']['sha256'] or parent_pin['sha256'] != row['parent_raw']['sha256']:
            raise ValueError('source or parent identity mismatch')
        indices = decode_source(source)
        import io
        parent = Image.open(io.BytesIO(parent_bytes))
        if parent.convert('RGBA').getchannel('A').getextrema() != (255, 255):
            raise ValueError('parent must be wholly opaque; no alpha repair')
        crop = row['crop']
        if not isinstance(crop, list) or len(crop) != 4 or any(type(v) is not int for v in crop):
            raise ValueError('crop must be four exact integers')
        x, y, w, h = crop
        if min(x, y) < 0 or w <= 0 or h <= 0 or x+w > parent.width or y+h > parent.height:
            raise ValueError('crop outside untouched parent')
        raw = np.array(parent.convert('RGB').crop((x, y, x+w, y+h)))
        derived, base, labels, metrics = reconstruct(indices, palette, raw, recipe['parameters'])
        prepared.append((asset, derived, base, labels, metrics, source_pin, parent_pin, crop))
    out = Path(args.output).absolute()
    out.mkdir(exist_ok=False)
    tool_bytes, tool_pin = read_regular(__file__)
    results = []
    for asset, derived, base, labels, metrics, source_pin, parent_pin, crop in prepared:
        image_path = out / f'{asset}-DERIVED-source-guided-material-v1.png'
        Image.fromarray(derived).save(image_path)
        Image.fromarray(base).save(out / f'{asset}-SOURCE-GUIDED-BASE-diagnostic.png')
        Image.fromarray(labels.astype(np.uint8)).save(out / f'{asset}-SOURCE-NX4-FAMILY-geometry-diagnostic.png')
        _, output_pin = read_regular(image_path)
        results.append(dict(asset=asset, output=output_pin, Source=source_pin, parent_raw=parent_pin,
                            parent_crop=crop, recipe=recipe_pin, tool=tool_pin,
                            parameters=recipe['parameters'], metrics=metrics,
                            lineage='DERIVED scripted cleanup; generator-return parent remains untouched'))
    for record in [recipe_pin, palette_pin] + [p for t in prepared for p in (t[5], t[6])]:
        _, now = read_regular(record['path'])
        if now != record:
            raise ValueError('input changed across cleanup')
    execution = dict(status='success', method=METHOD,
                     recipe_sha256=recipe_pin['sha256'], tool_sha256=tool_pin['sha256'],
                     source_sha256={r['asset']: r['Source']['sha256'] for r in results},
                     parent_raw_sha256=sorted({r['parent_raw']['sha256'] for r in results}),
                     output_sha256={r['asset']: r['output']['sha256'] for r in results})
    (out / 'DERIVED-LINEAGE-AND-ACTUAL-RECONSTRUCTION-METRICS.json').write_text(
        json.dumps(dict(status='DERIVED_OUTPUTS_NOT_MATERIAL_APPROVAL', method=METHOD,
                        recipe=recipe_pin, tool=tool_pin, palette=palette_pin, frames=results,
                        execution=execution), indent=2, sort_keys=True) + '\n')
    print(json.dumps(dict(output=str(out), frames=len(results), method=METHOD), indent=2))

if __name__ == '__main__':
    main()
