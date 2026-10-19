"""Reproduce PERSON01's exact Source-alias crop of generated PLATOON1 detail.

All6 are required. Parent rendering uses unchanged authenticated code in memory;
child output is its fixed pixel-exact crop. No Source painting, resampling, gains,
new donors or new image generation. Reproduction alone is not art approval.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import os
import stat
from pathlib import Path
import sys

import numpy as np
from PIL import Image, __version__ as PILLOW_VERSION

METHOD = 'derived-PERSON01-complete6-exact-Source-crop-of-PLATOON1-generated-top-bodies-v1'
PARENT_SHA = '5368774adb98af834df4fddb7ebe24310e6b35be110adf56b9961a6d36edd866'
DECODER_SHA = '66184a4758027dadbadb5e20fe90b2add2b9fc218b7810304b1a1ea2de74f58e'
ASSETS = [f'{0x200f8+i:05x}' for i in range(6)]


def digest(payload):
    return hashlib.sha256(payload).hexdigest()


def exact(value, fields, label):
    if type(value) is not dict or set(value) != set(fields):
        raise ValueError(f'{label}: exact fields required')


def bootstrap_regular_bytes(path):
    """Bounded nonblocking descriptor read before the verified parent can help."""
    path = Path(path)
    if path.is_symlink() or any(p.is_symlink() for p in path.parents):
        raise ValueError('symlink dependency')
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_size > 1_048_576:
        raise ValueError('regular bounded parent dependency required')
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
    with os.fdopen(os.open(path, flags), 'rb') as stream:
        opened = os.fstat(stream.fileno())
        if not stat.S_ISREG(opened.st_mode) or opened.st_size > 1_048_576:
            raise ValueError('regular bounded parent dependency required')
        payload = stream.read(1_048_577)
        after = os.fstat(stream.fileno())
    def identity(value):
        return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_mode
    if (len(payload) > 1_048_576 or identity(before) != identity(opened)
            or identity(opened) != identity(after) or identity(path.lstat()) != identity(before)):
        raise ValueError('parent dependency changed during bounded read')
    return payload


def dependencies(project):
    """Use the checked parent reader, then execute only verified buffers."""
    parent_path = Path(project)/'tools/hd_infantry_cleanup.py'
    data = bootstrap_regular_bytes(parent_path)
    if digest(data) != PARENT_SHA:
        raise ValueError('parent helper hash mismatch')
    scope = {'__name__': '_verified_infantry_buffer', '__file__': str(parent_path)}
    exec(compile(data, '<verified-infantry-buffer>', 'exec'), scope)
    decoder_bytes = scope['checked']({'path': 'tools/hd_frame_policy.py', 'sha256': DECODER_SHA}, project)
    decoder = {'__name__': '_verified_decoder_buffer', '__file__': '<verified-decoder-buffer>'}
    exec(compile(decoder_bytes, '<verified-decoder-buffer>', 'exec'), decoder)
    return scope, decoder['_indices']


def png_bytes(rgba):
    target = io.BytesIO()
    Image.fromarray(rgba).save(target, format='PNG', compress_level=9)
    return target.getvalue()


def run_recipe(recipe_path, output, project_root=None):
    recipe_path, output = Path(recipe_path).absolute(), Path(output).absolute()
    if output.exists() or output.is_symlink() or any(p.is_symlink() for p in output.parents):
        raise ValueError('fresh nonsymlink output required')
    project = Path(project_root) if project_root else Path(__file__).resolve().parents[1]
    parent, decode = dependencies(project)
    checked, regular, keys = parent['checked'], parent['regular_bytes'], parent['keys']
    rb = regular(recipe_path)
    own_sha = digest(regular(Path(__file__)))
    recipe = json.loads(rb)
    exact(recipe, {'format_version', 'method', 'parent_recipe', 'parent_execution_receipt', 'frames'}, 'recipe')
    if type(recipe['format_version']) is not int or recipe['format_version'] != 1 or recipe['method'] != METHOD:
        raise ValueError('fixed PERSON01 recipe version/method required')
    frames = recipe['frames']
    if type(frames) is not list or len(frames) != 6 or [f.get('asset') for f in frames if type(f) is dict] != ASSETS:
        raise ValueError('complete ordered PERSON01 family required')
    parent_payload = checked(recipe['parent_recipe'], recipe_path.parent)
    parent_recipe = json.loads(parent_payload)
    exact(parent_recipe, {'format_version', 'method', 'raw_png', 'palette', 'frames'}, 'parent recipe')
    if type(parent_recipe['format_version']) is not int or parent_recipe['format_version'] != 1 or parent_recipe['method'] != parent['METHOD']:
        raise ValueError('parent method/version mismatch')
    pf = parent_recipe['frames']
    if type(pf) is not list or len(pf) != 6 or [f.get('asset') for f in pf if type(f) is dict] != parent['ASSETS']:
        raise ValueError('complete ordered parent family required')
    parent_base = (recipe_path.parent/recipe['parent_recipe']['path']).parent
    raw_payload = checked(parent_recipe['raw_png'], parent_base)
    with Image.open(io.BytesIO(raw_payload)) as opened:
        if opened.format != 'PNG' or opened.size != (1536, 1024) or opened.mode != 'RGBA':
            raise ValueError('exact parent atlas layout required')
        raw = np.asarray(opened).copy()
    palette_payload = checked(parent_recipe['palette'], parent_base)
    if len(palette_payload) != 768 or max(palette_payload) > 63:
        raise ValueError('genuine VGA palette required')
    p6 = np.frombuffer(palette_payload, np.uint8).reshape(256, 3).astype(np.uint16)
    palette = ((p6 << 2) | (p6 >> 4)).astype(np.uint8)
    receipt = json.loads(checked(recipe['parent_execution_receipt'], recipe_path.parent))
    if type(receipt) is not dict or type(receipt.get('execution')) is not dict:
        raise ValueError('parent execution receipt required')
    execution = receipt['execution']
    exact(execution, {'status', 'method', 'recipe_sha256', 'tool_sha256', 'source_sha256',
                      'parent_raw_sha256', 'output_sha256'}, 'parent execution')
    if (execution['status'] != 'success' or execution['method'] != parent['METHOD']
            or execution['tool_sha256'] != PARENT_SHA
            or execution['recipe_sha256'] != digest(parent_payload)
            or execution['parent_raw_sha256'] != [digest(raw_payload)]
            or type(execution['output_sha256']) is not dict
            or set(execution['output_sha256']) != set(parent['ASSETS'])
            or any(not parent['hash_string'](v) for v in execution['output_sha256'].values())):
        raise ValueError('parent execution provenance mismatch')
    child_sources, parent_sources = [], []
    for i, (frame, parent_frame) in enumerate(zip(frames, pf)):
        exact(frame, {'asset', 'parent_asset', 'source', 'functional_original_cells'}, 'child frame')
        keys(parent_frame, {'asset', 'source', 'components', 'functional_original_cells'}, 'parent frame')
        if (frame['parent_asset'] != parent['ASSETS'][i]
                or type(parent_frame['components']) is not list or len(parent_frame['components']) != 6
                or frame['functional_original_cells'] != [[3, 3]]
                or any(type(v) is not int for v in frame['functional_original_cells'][0])):
            raise ValueError('fixed corresponding parent phase and one child face required')
        width, height, pixels = decode(checked(parent_frame['source'], parent_base))
        if (width, height) != (24, 24):
            raise ValueError('parent24x24 required')
        ps = np.array(pixels, np.uint16).reshape(24, 24)
        width, height, pixels = decode(checked(frame['source'], recipe_path.parent))
        if (width, height) != (8, 8):
            raise ValueError('child8x8 required')
        cs = np.array(pixels, np.uint16).reshape(8, 8)
        if (not np.array_equal(cs, ps[0:8, 5:13]) or cs[3, 3] >= 256
                or 4 > int((cs < 256).sum())):
            raise ValueError('entire64-index Source crop/face/quarter bound mismatch')
        if not np.array_equal(parent['scale2'](cs), parent['scale2'](ps)[0:16, 10:26]):
            raise ValueError('SourceScale2 crop mismatch')
        if not np.array_equal(parent['scale2'](parent['scale2'](cs)),
                              parent['scale2'](parent['scale2'](ps))[0:32, 20:52]):
            raise ValueError('SourceScale4 crop mismatch')
        child_sources.append(cs)
        parent_sources.append(ps)
    if execution['source_sha256'] != {f['asset']: f['source']['sha256'] for f in pf}:
        raise ValueError('parent source provenance mismatch')
    payloads, reports = [], []
    for i, (frame, parent_frame, ps, cs) in enumerate(zip(frames, pf, parent_sources, child_sources)):
        rgba, material_report = parent['render_frame'](parent_frame, ps, palette,
            raw[i//3*512:(i//3+1)*512, i%3*512:(i%3+1)*512])
        reproduced_parent = png_bytes(rgba)
        if digest(reproduced_parent) != execution['output_sha256'][parent_frame['asset']]:
            raise ValueError('parent PNG not exactly reproduced')
        crop = rgba[0:32, 20:52].copy()
        child_scale4 = parent['scale2'](parent['scale2'](cs))
        if not np.array_equal(crop[:, :, 3], np.where(child_scale4 < 256, 255, 0)):
            raise ValueError('child alpha differs from own SourceScale4')
        child_png = png_bytes(crop)
        payloads.append((frame['asset'], child_png))
        reports.append(dict(asset=frame['asset'], parent_asset=parent_frame['asset'],
            exact_parent_RGBA_crop=[20, 0, 32, 32], parent_PNG_sha256=digest(reproduced_parent),
            own_source_sha256=frame['source']['sha256'], own_SourceScale4_alpha_exact=True,
            functional_Original_cells=[[3, 3]], Original_master_samples=16,
            RGBA_sha256=digest(crop.tobytes()), parent_material_report=material_report))
    for cls in (0, 1, 2):
        rows = [c for report in reports for c in report['parent_material_report']['components'] if c['material_class'] == cls]
        if sum(c['repaired'] for c in rows)/sum(c['samples'] for c in rows) > parent['CAPS'][cls][1]+1e-12:
            raise ValueError('complete parent aggregate cap exceeded')
    if digest(regular(Path(__file__))) != own_sha:
        raise ValueError('dispatcher changed during execution')
    final = dict(execution=dict(status='success', method=METHOD, recipe_sha256=digest(rb),
        tool_sha256=own_sha, source_sha256={f['asset']: f['source']['sha256'] for f in frames},
        parent_raw_sha256=[digest(raw_payload)], output_sha256={a: digest(p) for a, p in payloads}),
        parent_helper_sha256=PARENT_SHA, decoder_sha256=DECODER_SHA,
        parent_recipe_sha256=digest(parent_payload), parent_execution_receipt_sha256=recipe['parent_execution_receipt']['sha256'],
        reports=reports, Python=sys.version.split()[0], NumPy=np.__version__, Pillow=PILLOW_VERSION,
        limits=['Source crop aliases are not encoded-payload aliases.',
                'Original alpha and one Source face per frame get zero generated detail credit.',
                'Substantial inherited near-black functional support is not new generated texture.',
                'Parent and child material/context approval remain separate.'])
    output.mkdir(parents=True)
    for asset, payload in payloads:
        (output/f'{asset}.png').write_bytes(payload)
    (output/'execution-receipt.json').write_text(json.dumps(final, indent=2, sort_keys=True)+'\n')
    return final


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recipe', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--project-root', type=Path)
    args = parser.parse_args()
    print(json.dumps(run_recipe(args.recipe, args.output, args.project_root)['execution'], sort_keys=True))


if __name__ == '__main__':
    main()
