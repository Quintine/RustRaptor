"""Reproduce complete PLATOON1 art from genuine per-body/material RGB and Source support.

A narrowly fixed six-frame renderer, never artistic approval. Decoder, Source,
palette and PNG bytes are verified once and consumed in memory. Source supplies
alpha and six declared face cells; other painted RGB comes unchanged from the
same generated phase/body/material. No gains, texture synthesis or cascading fills.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import stat
import sys

import numpy as np
from PIL import Image, __version__ as PILLOW_VERSION

METHOD = 'derived-PLATOON1-complete6-generated-component-material-SourceScale4-face6-v1'
DECODER_SHA = '66184a4758027dadbadb5e20fe90b2add2b9fc218b7810304b1a1ea2de74f58e'
ASSETS = [f'{0x200ec+i:05x}' for i in range(6)]
WINDOWS = [('top', [0, 0, 24, 7]), ('middle_left', [0, 7, 12, 13]),
           ('middle_right', [12, 7, 24, 13]), ('lower_middle', [6, 13, 13, 19]),
           ('lower_left', [0, 19, 12, 24]), ('lower_right', [13, 13, 24, 24])]
CAPS = {0: (.92, .70, 1.5), 1: (.36, .25, .65), 2: (.42, .30, .35)}
NAMES = {0: 'near_black', 1: 'green', 2: 'tan'}


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def keys(value, expected, label):
    if type(value) is not dict or set(value) != set(expected):
        raise ValueError(f'{label}: exact fields required')


def hash_string(value):
    return type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def regular_bytes(path):
    """Read one regular nonsymlink once; consume this buffer, never reopen it."""
    path = Path(path)
    for parent in [path, *path.parents]:
        if parent.is_symlink():
            raise ValueError('symlink input path')
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise ValueError('regular input required')
    descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(descriptor, 'rb') as stream:
        opened = os.fstat(stream.fileno())
        payload = stream.read()
        after = os.fstat(stream.fileno())
    def identity(s):
        return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_mode
    if identity(before) != identity(opened) or identity(opened) != identity(after) or identity(path.lstat()) != identity(before):
        raise ValueError('input changed during buffered read')
    return payload


def checked(binding, root):
    keys(binding, {'path', 'sha256'}, 'binding')
    name = binding['path']
    if type(name) is not str or not name or '\\' in name or ':' in name:
        raise ValueError('portable relative path required')
    relative = PurePosixPath(name)
    if relative.is_absolute() or any(part in ('', '.', '..') for part in name.split('/')):
        raise ValueError('unsafe relative path')
    if not hash_string(binding['sha256']):
        raise ValueError('sha256 required')
    root = Path(root).resolve()
    path = root.joinpath(*relative.parts)
    if not path.resolve().is_relative_to(root):
        raise ValueError('input escapes root')
    payload = regular_bytes(path)
    if sha(payload) != binding['sha256']:
        raise ValueError(f'input hash mismatch: {name}')
    return payload


def verified_decoder(project_root):
    payload = checked({'path': 'tools/hd_frame_policy.py', 'sha256': DECODER_SHA}, project_root)
    namespace = {'__name__': '_verified_hd_frame_policy', '__file__': '<verified-hd-frame-policy-buffer>'}
    exec(compile(payload, '<verified-hd-frame-policy-buffer>', 'exec'), namespace)
    return namespace['_indices']


def scale2(source):
    """Published Scale2x, identical label comparisons including transparent256."""
    h, w = source.shape
    b = np.concatenate([source[:1], source[:-1]], axis=0)
    d = np.concatenate([source[:, :1], source[:, :-1]], axis=1)
    f = np.concatenate([source[:, 1:], source[:, -1:]], axis=1)
    g = np.concatenate([source[1:], source[-1:]], axis=0)
    condition = (b != g) & (d != f)
    out = np.empty((h*2, w*2), np.uint16)
    out[0::2, 0::2] = np.where(condition & (d == b), d, source)
    out[0::2, 1::2] = np.where(condition & (b == f), f, source)
    out[1::2, 0::2] = np.where(condition & (d == g), d, source)
    out[1::2, 1::2] = np.where(condition & (g == f), f, source)
    return out


def materials(rgb):
    r, g, b = rgb.astype(np.int32).transpose(2, 0, 1)
    result = np.full(r.shape, 255, np.uint8)
    result[(np.maximum(np.maximum(r, g), b) <= 64) & (g-r < 5)] = 0
    result[(g >= r+5) & (g >= b+5) & (g >= 24)] = 1
    result[(r >= g+5) & (g >= b+5) & (r >= 64)] = 2
    return result


def box(value, maximum, label):
    if (type(value) is not list or len(value) != 4 or any(type(v) is not int for v in value)
            or not 0 <= value[0] < value[2] <= maximum or not 0 <= value[1] < value[3] <= maximum):
        raise ValueError(f'{label}: bounded integer rectangle required')
    return value


def bounds(mask):
    y, x = np.where(mask)
    if len(x) == 0:
        raise ValueError('empty anatomical body')
    return [int(x.min()), int(y.min()), int(x.max()+1), int(y.max()+1)]


def render_frame(frame, source, palette, raw_cell):
    """Pure buffered renderer. No file access and no writable input aliases."""
    source4 = scale2(scale2(source))
    source_colors = np.zeros((257, 3), np.uint8)
    source_colors[:256] = palette
    source_classes = materials(source_colors.reshape(1, 257, 3))[0]
    source_classes[256] = 255
    classes4 = source_classes[source4]
    if np.any((source4 < 256) & (classes4 == 255)):
        raise ValueError('Original contains unsupported material')
    raw_classes = materials(raw_cell[:, :, :3])
    visible = raw_cell[:, :, 3] >= 128
    rgba = np.zeros((96, 96, 4), np.uint8)
    rgba[:, :, 3] = np.where(source4 < 256, 255, 0)
    owned = np.zeros((96, 96), bool)
    raw_owned = np.zeros((512, 512), bool)
    reports = []
    expected_faces = []
    for component, (expected_name, window) in zip(frame['components'], WINDOWS):
        keys(component, {'name', 'source_bbox', 'raw_bbox'}, 'component')
        if component['name'] != expected_name:
            raise ValueError('fixed Source body order required')
        x0, y0, x1, y1 = window
        logical_ownership = np.zeros((24, 24), bool)
        logical_ownership[y0:y1, x0:x1] = True
        original_body = logical_ownership & (source < 256)
        sb = box(component['source_bbox'], 24, 'Source bbox')
        if bounds(original_body) != sb:
            raise ValueError('Source body bbox does not match authenticated Source')
        face_y = sb[1]+1
        face_x = [x for x in range(sb[0], sb[2]) if source_classes[source[face_y, x]] == 2]
        if len(face_x) != 1:
            raise ValueError('exact central Original face cell required')
        expected_faces.append([face_x[0], face_y])
        l, t, r, b = box(component['raw_bbox'], 512, 'raw bbox')
        if raw_owned[t:b, l:r].any():
            raise ValueError('raw body boxes overlap')
        raw_owned[t:b, l:r] = True
        if bounds(visible[t:b, l:r]) != [0, 0, r-l, b-t]:
            raise ValueError('raw body bbox differs from genuine alpha>=128 bounds')
        owner = np.repeat(np.repeat(logical_ownership, 4, axis=0), 4, axis=1) & (source4 < 256)
        if np.any(owned & owner):
            raise ValueError('Source ownership overlaps')
        owned |= owner
        sx = (r-l)/(sb[2]-sb[0])
        sy = (b-t)/(sb[3]-sb[1])
        for cls in (0, 1, 2):
            yy, xx = np.where(owner & (classes4 == cls))
            if len(xx) == 0:
                continue
            donor_y, donor_x = np.where(visible[t:b, l:r] & (raw_classes[t:b, l:r] == cls))
            donor_x, donor_y = donor_x+l, donor_y+t
            if not len(donor_x):
                raise ValueError('missing genuine same-body/material donors')
            u = l+((xx+.5)/4-sb[0])*sx
            v = t+((yy+.5)/4-sb[1])*sy
            px, py = np.floor(u).astype(int), np.floor(v).astype(int)
            if np.any(px < l) or np.any(px >= r) or np.any(py < t) or np.any(py >= b):
                raise ValueError('SourceScale4 sample escapes raw body')
            direct = visible[py, px] & (raw_classes[py, px] == cls)
            missing = float(np.mean(~direct))
            per_cap, _, distance_cap = CAPS[cls]
            if missing > per_cap+1e-12:
                raise ValueError(f'{expected_name}/{NAMES[cls]}: fixed missing fraction exceeded')
            maximum_distance = 0.0
            for point in np.where(~direct)[0]:
                # np.where returns donors in y/x order; argmin fixes equal-distance ties.
                distances = ((donor_x+.5-u[point])/sx)**2 + ((donor_y+.5-v[point])/sy)**2
                nearest = int(np.argmin(distances))
                distance = math.sqrt(float(distances[nearest]))
                if distance > distance_cap+1e-12:
                    raise ValueError(f'{expected_name}/{NAMES[cls]}: fixed donor distance exceeded')
                px[point], py[point] = donor_x[nearest], donor_y[nearest]
                maximum_distance = max(maximum_distance, distance)
            rgba[yy, xx, :3] = raw_cell[py, px, :3]
            reports.append(dict(body=expected_name, material=NAMES[cls], material_class=cls,
                                samples=len(xx), repaired=int((~direct).sum()),
                                missing_fraction=missing, maximum_donor_logical_distance=maximum_distance,
                                raw_donors=len(donor_x)))
    if not np.array_equal(owned, source4 < 256):
        raise ValueError('fixed windows do not exhaust all SourceScale4 support')
    if np.any(visible & ~raw_owned):
        raise ValueError('unbound generated body alpha>=128 outside six declared bodies')
    faces = frame['functional_original_cells']
    if (type(faces) is not list or any(type(xy) is not list or len(xy) != 2 or any(type(v) is not int for v in xy) for xy in faces) or faces != sorted(expected_faces) or len(faces) != 6
            or 4*len(faces) > int((source < 256).sum())):
        raise ValueError('exact six functional Original cells within quarter-painted limit required')
    before_retention = rgba.copy()
    for x, y in faces:
        region = source4[y*4:(y+1)*4, x*4:(x+1)*4]
        target = rgba[y*4:(y+1)*4, x*4:(x+1)*4]
        target[:, :, :3] = source_colors[region]
        target[:, :, 3] = np.where(region < 256, 255, 0)
    if not np.array_equal(rgba[:, :, 3], np.where(source4 < 256, 255, 0)):
        raise ValueError('functional Original retention changed support')
    return rgba, dict(components=reports, functional_Original_cells=faces,
                      functional_Original_master_samples=96,
                      SourceScale4_alpha_exact=True,
                      restored_black_is_functional_support_not_generated_detail=True,
                      Original_RGBA_changed_samples=int(np.any(before_retention != rgba, axis=2).sum()))


def run_recipe(recipe_path, output, project_root=None):
    recipe_path, output = Path(recipe_path).absolute(), Path(output).absolute()
    if output.exists() or output.is_symlink():
        raise ValueError('fresh absent output directory required')
    for parent in output.parents:
        if parent.is_symlink():
            raise ValueError('symlink output parent')
    tool_sha = sha(regular_bytes(Path(__file__)))
    rb = regular_bytes(recipe_path)
    recipe = json.loads(rb)
    keys(recipe, {'format_version', 'method', 'raw_png', 'palette', 'frames'}, 'recipe')
    if type(recipe['format_version']) is not int or recipe['format_version'] != 1 or recipe['method'] != METHOD:
        raise ValueError('fixed recipe method/version required')
    frames = recipe['frames']
    if type(frames) is not list or len(frames) != 6 or [f.get('asset') for f in frames if type(f) is dict] != ASSETS:
        raise ValueError('complete ordered six-frame PLATOON1 required')
    decoder = verified_decoder(Path(project_root) if project_root else Path(__file__).resolve().parents[1])
    raw_payload = checked(recipe['raw_png'], recipe_path.parent)
    with Image.open(io.BytesIO(raw_payload)) as opened:
        if opened.format != 'PNG' or opened.size != (1536, 1024) or opened.mode != 'RGBA':
            raise ValueError('exact1536x1024 RGBA three-by-two parent required')
        raw = np.asarray(opened).copy()
    pb = checked(recipe['palette'], recipe_path.parent)
    if len(pb) != 768 or max(pb) > 63:
        raise ValueError('genuine VGA palette required')
    sixbit = np.frombuffer(pb, np.uint8).reshape(256, 3).astype(np.uint16)
    palette = ((sixbit << 2) | (sixbit >> 4)).astype(np.uint8)
    sources = []
    for frame in frames:
        keys(frame, {'asset', 'source', 'components', 'functional_original_cells'}, 'frame')
        if type(frame['components']) is not list or len(frame['components']) != 6:
            raise ValueError('six exact bodies per frame required')
        payload = checked(frame['source'], recipe_path.parent)
        width, height, indices = decoder(payload)
        if (width, height) != (24, 24):
            raise ValueError('exact24x24 Source canvas required')
        source = np.array(indices, np.uint16).reshape(24, 24)
        sources.append(source)
    # All outputs stay buffered until the entire complete6 validates.
    payloads, reports = [], []
    for i, (frame, source) in enumerate(zip(frames, sources)):
        rgba, report = render_frame(frame, source, palette,
            raw[i//3*512:(i//3+1)*512, i%3*512:(i%3+1)*512])
        stream = io.BytesIO()
        Image.fromarray(rgba).save(stream, format='PNG', compress_level=9)
        payloads.append((frame['asset'], stream.getvalue()))
        reports.append({'asset': frame['asset'], **report, 'RGBA_sha256': sha(rgba.tobytes())})
    for cls in (0, 1, 2):
        rows = [r for report in reports for r in report['components'] if r['material_class'] == cls]
        aggregate = sum(r['repaired'] for r in rows)/sum(r['samples'] for r in rows)
        if aggregate > CAPS[cls][1]+1e-12:
            raise ValueError('fixed complete6 aggregate material cap exceeded')
    if sha(regular_bytes(Path(__file__))) != tool_sha:
        raise ValueError('executing helper changed during render')
    execution = dict(status='success', method=METHOD, recipe_sha256=sha(rb),
                     tool_sha256=tool_sha,
                     source_sha256={f['asset']: f['source']['sha256'] for f in frames},
                     parent_raw_sha256=[sha(raw_payload)],
                     output_sha256={asset: sha(png) for asset, png in payloads})
    receipt = dict(execution=execution, decoder_sha256=DECODER_SHA,
                   dependencies_consumed_from_verified_buffers=True, reports=reports,
                   Python=sys.version.split()[0], NumPy=np.__version__, Pillow=PILLOW_VERSION,
                   limits=['Original support and six faces are not new generated detail.',
                           'Black completion is substantial functional Source-shape restoration.',
                           'Reproduction and numerical caps do not confer artistic approval.'])
    output.mkdir(parents=True)
    for asset, payload in payloads:
        (output/f'{asset}.png').write_bytes(payload)
    (output/'execution-receipt.json').write_text(json.dumps(receipt, indent=2, sort_keys=True)+'\n')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recipe', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--project-root', type=Path)
    args = parser.parse_args()
    result = run_recipe(args.recipe, args.output, args.project_root)
    print(json.dumps(result['execution'], sort_keys=True))


if __name__ == '__main__':
    main()
