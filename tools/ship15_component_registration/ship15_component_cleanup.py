"""Private SHIP15G1 complete3 component registration; not artistic approval.

Genuine generated RGB is sampled only from the same phase/material. Literal
Source support supplies derived alpha; exactly29 declared logical cells supply
baked Original RGB. Parent PNG/Source files are never changed. This file is
prepared code only until Root releases an actual recipe execution.
"""
from __future__ import annotations
import argparse
from collections import deque
import hashlib
import io
import json
import math
from pathlib import Path
import platform

import numpy as np
from PIL import Image, __version__ as PILLOW_VERSION

METHOD = 'derived-generated-ship15-component-mast-pods-wake-source-support-v1'
DECODER_SHA = '66184a4758027dadbadb5e20fe90b2add2b9fc218b7810304b1a1ea2de74f58e'
CAPS = dict(metal_max_logical_distance=1.0, metal_max_missing_fraction=0.13,
            wake_max_logical_distance=2.75, wake_max_missing_fraction=0.18)
AXES = {
    'main_machinery_mast_hull': ([36, 39, 42, 53], [4, 7, 15, 18]),
    'left_pod': ([21, 29], [7, 15]),
    'right_pod': ([55, 63], [7, 15]),
    'teal_wake': ([0, 21, 29, 36, 53, 55, 63, 72], [2, 4, 7, 15, 18, 20]),
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def exact_keys(value, keys, label):
    if type(value) is not dict or set(value) != set(keys):
        raise ValueError(f'{label}: unknown/missing fields')


def checked(binding, base):
    exact_keys(binding, {'path', 'sha256'}, 'input binding')
    if type(binding['path']) is not str or not binding['path'] or type(binding['sha256']) is not str:
        raise ValueError('input path/hash types')
    path = Path(binding['path'])
    if not path.is_absolute():
        path = Path(base) / path
    data = path.read_bytes()
    if sha(data) != binding['sha256']:
        raise ValueError(f'input hash mismatch: {path}')
    return path.resolve(), data


def finite_number(v):
    return type(v) in (int, float) and math.isfinite(v)


def validate_model(model, name, width, height):
    exact_keys(model, {'source_x', 'raw_x', 'source_y', 'raw_y', 'donor_bounds'}, name)
    expected_x, expected_y = AXES[name]
    for key, expected in [('source_x', expected_x), ('source_y', expected_y)]:
        if type(model[key]) is not list or model[key] != expected or any(type(v) is not int for v in model[key]):
            raise ValueError(f'{name}: Source knots differ')
    for source_key, raw_key, maximum in [('source_x', 'raw_x', width), ('source_y', 'raw_y', height)]:
        values = model[raw_key]
        if (type(values) is not list or len(values) != len(model[source_key]) or
                any(not finite_number(v) for v in values) or
                not all(0 <= v <= maximum for v in values) or
                not all(b > a for a, b in zip(values, values[1:]))):
            raise ValueError(f'{name}: nonfinite/nonmonotone/outside raw knots')
    bounds = model['donor_bounds']
    if (type(bounds) is not list or len(bounds) != 4 or any(type(v) is not int for v in bounds) or
            not (0 <= bounds[0] < bounds[2] <= width and 0 <= bounds[1] < bounds[3] <= height)):
        raise ValueError(f'{name}: invalid donor bounds')
    if not (bounds[0] <= model['raw_x'][0] <= model['raw_x'][-1] <= bounds[2] and
            bounds[1] <= model['raw_y'][0] <= model['raw_y'][-1] <= bounds[3]):
        raise ValueError(f'{name}: knots escape same-component donor bounds')


def nearest_owners(trusted):
    """Raster seeds, N/W/E/S BFS; owners always refer to initial trusted pixels."""
    if not trusted.any():
        raise ValueError('no genuine parent donors for component/material')
    h, w = trusted.shape
    distance = np.full((h, w), np.iinfo(np.int32).max, np.int32)
    owner_y = np.full((h, w), -1, np.int32)
    owner_x = np.full((h, w), -1, np.int32)
    seeds = np.argwhere(trusted)
    todo = deque()
    for y, x in seeds:
        y, x = int(y), int(x)
        distance[y, x] = 0
        owner_y[y, x], owner_x[y, x] = y, x
        todo.append((x, y))
    while todo:
        x, y = todo.popleft()
        n = int(distance[y, x]) + 1
        for nx, ny in ((x, y-1), (x-1, y), (x+1, y), (x, y+1)):
            if 0 <= nx < w and 0 <= ny < h and distance[ny, nx] > n:
                distance[ny, nx] = n
                owner_y[ny, nx], owner_x[ny, nx] = owner_y[y, x], owner_x[y, x]
                todo.append((nx, ny))
    return distance, owner_y, owner_x


def sample_component(parent, source_mask, model, name, scale, caps):
    """Nearest genuine raw RGB at declared inverse-map coordinates, no gains."""
    h, w = source_mask.shape
    output_mask = np.repeat(np.repeat(source_mask, scale, axis=0), scale, axis=1)
    yy, xx = np.nonzero(output_mask)
    if len(xx) == 0:
        raise ValueError(f'{name}: empty Source component')
    u = np.interp((xx+0.5)/scale, model['source_x'], model['raw_x'])
    v = np.interp((yy+0.5)/scale, model['source_y'], model['raw_y'])
    px, py = np.floor(u).astype(int), np.floor(v).astype(int)
    l, t, r, b = model['donor_bounds']
    if np.any(px < l) or np.any(px >= r) or np.any(py < t) or np.any(py >= b):
        raise ValueError(f'{name}: mapped sample outside donor bounds')
    # Donor tests are performed on an untouched crop of this exact phase only.
    patch = parent[t:b, l:r]
    rgb = patch[:, :, :3].astype(np.int16)
    trusted = patch[:, :, 3] >= 128
    if name == 'teal_wake':
        trusted &= (rgb[:, :, 1] > rgb[:, :, 0]+10) & (rgb[:, :, 2] > rgb[:, :, 0]+10)
        kind = 'wake'
    else:
        trusted &= rgb.max(axis=2)-rgb.min(axis=2) <= 18
        kind = 'metal'
    distance, oy, ox = nearest_owners(trusted)
    qx, qy = px-l, py-t
    d = distance[qy, qx].astype(float)
    direct = trusted[qy, qx]
    minimum_raw_per_logical = min(
        min(np.diff(model['raw_x'])/np.diff(model['source_x'])),
        min(np.diff(model['raw_y'])/np.diff(model['source_y'])))
    logical_distance = d/minimum_raw_per_logical
    missing_fraction = float((~direct).mean())
    if missing_fraction > caps[f'{kind}_max_missing_fraction'] + 1e-12:
        raise ValueError(f'{name}: genuine donor missing fraction exceeds cap')
    if float(logical_distance.max()) > caps[f'{kind}_max_logical_distance'] + 1e-12:
        raise ValueError(f'{name}: genuine donor distance exceeds cap')
    sy, sx = oy[qy, qx], ox[qy, qx]
    if not np.all(trusted[sy, sx]):
        raise AssertionError('owner is not an original genuine donor')
    # No interpolated/new pixel can become a donor; all reads use the parent.
    values = patch[sy, sx, :3].copy()
    return output_mask, values, dict(component=name, Source_cells=int(source_mask.sum()),
                                    output_samples=len(xx), direct_genuine_samples=int(direct.sum()),
                                    nearest_parent_extension_samples=int((~direct).sum()),
                                    missing_fraction=missing_fraction,
                                    max_raw_Manhattan_distance=float(d.max()),
                                    max_equivalent_logical_distance=float(logical_distance.max()),
                                    same_phase_material_and_bounds=True, cascading_fill=False)


def validate_recipe(recipe):
    exact_keys(recipe, {'format_version', 'label', 'decoder_module', 'palette', 'parent_raw',
                        'output_scale', 'caps', 'frames'}, 'recipe')
    if type(recipe['format_version']) is not int or recipe['format_version'] != 1:
        raise ValueError('recipe format version')
    if type(recipe['label']) is not str or not recipe['label'].strip():
        raise ValueError('recipe label')
    if type(recipe['output_scale']) is not int or recipe['output_scale'] != 8:
        raise ValueError('this complete3 recipe requires declared8x master')
    exact_keys(recipe['caps'], CAPS, 'caps')
    if any(not finite_number(recipe['caps'][k]) or recipe['caps'][k] != v for k, v in CAPS.items()):
        raise ValueError('caps must equal reviewed proposed hard limits')
    frames = recipe['frames']
    if type(frames) is not list or len(frames) != 3:
        raise ValueError('complete3 required')
    for i, frame in enumerate(frames):
        exact_keys(frame, {'asset', 'frame', 'source', 'logical_canvas', 'origin', 'raw_crop',
                           'components', 'functional_original_cells'}, 'frame')
        if (frame['asset'] != f'{0x1030b+i:05x}' or type(frame['frame']) is not int or frame['frame'] != i or
                frame['logical_canvas'] != [72, 24] or any(type(v) is not int for v in frame['logical_canvas']) or
                frame['origin'] != [0, 0] or any(type(v) is not int for v in frame['origin'])):
            raise ValueError('Source family/order/native/origin changed')
        exact_keys(frame['components'], AXES, 'components')
    return frames


def render_family(recipe, base):
    frames = validate_recipe(recipe)
    decoder_path, decoder_bytes = checked(recipe['decoder_module'], base)
    if sha(decoder_bytes) != DECODER_SHA:
        raise ValueError('unreviewed decoder module')
    decoder_namespace = {'__name__': '_verified_ship15_decoder', '__file__': str(decoder_path)}
    exec(compile(decoder_bytes, str(decoder_path), 'exec'), decoder_namespace)
    decode = decoder_namespace['_indices']
    palette_path, palette_bytes = checked(recipe['palette'], base)
    if len(palette_bytes) != 768 or max(palette_bytes) > 63:
        raise ValueError('literal256 six-bit palette required')
    palette = np.frombuffer(palette_bytes, np.uint8).reshape(256, 3).astype(np.uint16)
    palette = ((palette << 2) | (palette >> 4)).astype(np.uint8)
    parent_path, parent_bytes = checked(recipe['parent_raw'], base)
    if len(parent_bytes) > 32*1024*1024:
        raise ValueError('parent exceeds32MiB')
    with Image.open(io.BytesIO(parent_bytes)) as opened:
        if (opened.format != 'PNG' or opened.width != opened.height or opened.height % 3 or
                opened.width*opened.height > 4_194_304 or opened.width < 72):
            raise ValueError('parent must be a bounded square three-full-strip PNG')
        parent = np.array(opened.convert('RGBA'))
    if parent[:, :, 3].min() != 0:
        raise ValueError('parent must have genuine transparent alpha')
    height, width = parent.shape[:2]
    strip_height = height//3
    sources, input_hashes = [], {str(parent_path): sha(parent_bytes), str(palette_path): sha(palette_bytes)}
    for i, frame in enumerate(frames):
        crop = frame['raw_crop']
        if (type(crop) is not list or crop != [0, i*strip_height, width, strip_height] or
                any(type(v) is not int for v in crop)):
            raise ValueError('only three literal full strips permitted, no crop fit')
        path, payload = checked(frame['source'], base)
        sw, sh, indices = decode(payload)
        if [sw, sh] != [72, 24]:
            raise ValueError('Original canvas differs')
        source = np.asarray(indices, np.uint16).reshape(sh, sw)
        if not np.all((source < 32) | ((source >= 144) & (source <= 157)) | (source == 255) | (source == 256)):
            raise ValueError('Source class outside exact declared family partition')
        if np.any((source[:2] < 256)) or np.any((source[20:] < 256)):
            raise ValueError('Source painted support outside declared full wake region')
        if np.argwhere(source == 255).tolist() != [[10, 37], [11, 37]]:
            raise ValueError('Source255 indicator changed')
        for name, model in frame['components'].items():
            validate_model(model, name, width, strip_height)
        sources.append(source)
        input_hashes[str(path)] = sha(payload)
    gray = sources[0] < 32
    if any(not np.array_equal(s < 32, gray) for s in sources[1:]):
        raise ValueError('stationary Source gray footprint changed')
    phase_cells = np.any(np.stack(sources) != sources[0], axis=0) & gray
    if int(phase_cells.sum()) != 12:
        raise ValueError('Source phase12 tone coordinates changed')
    arrays, reports = [], []
    yy, xx = np.indices((24, 72))
    gray_regions = dict(main_machinery_mast_hull=(xx >= 36)&(xx < 53)&(yy >= 4)&(yy < 18),
                        left_pod=(xx >= 21)&(xx < 29)&(yy >= 7)&(yy < 15),
                        right_pod=(xx >= 55)&(xx < 63)&(yy >= 7)&(yy < 15))
    gray_region_union = np.logical_or.reduce(list(gray_regions.values()))
    if np.any(gray & ~gray_region_union):
        raise ValueError('gray Source support outside three declared components')
    for i, (frame, source) in enumerate(zip(frames, sources)):
        occupied = source < 256
        functional = (source == 31) | phase_cells | (source == 255)
        expected = [[int(x), int(y)] for y, x in np.argwhere(functional)]
        cells = frame['functional_original_cells']
        if (type(cells) is not list or cells != expected or len(cells) != 29 or
                any(type(cell) is not list or len(cell) != 2 or any(type(v) is not int for v in cell) for cell in cells)):
            raise ValueError('exact row-major29 explicit Original cells required')
        masks = {name: (source < 32)&region for name, region in gray_regions.items()}
        masks['teal_wake'] = (source >= 144)&(source <= 157)
        assigned = np.logical_or.reduce(list(masks.values())) | (source == 255)
        if not np.array_equal(assigned, occupied):
            raise ValueError('Source support partition mismatch')
        rgba = np.zeros((192, 576, 4), np.uint8)
        parent_phase = parent[i*strip_height:(i+1)*strip_height]
        counts = []
        for name, mask in masks.items():
            outmask, values, record = sample_component(parent_phase, mask, frame['components'][name], name, 8, recipe['caps'])
            rgba[:, :, :3][outmask] = values
            counts.append(record)
        alpha = np.repeat(np.repeat(occupied, 8, axis=0), 8, axis=1)
        rgba[:, :, 3][alpha] = 255
        before_functional = rgba.copy()
        functional8 = np.repeat(np.repeat(functional, 8, axis=0), 8, axis=1)
        source_rgb8 = np.repeat(np.repeat(palette[np.minimum(source, 255)], 8, axis=0), 8, axis=1)
        rgba[:, :, :3][functional8] = source_rgb8[functional8]
        if (not np.array_equal(rgba[:, :, 3] == 255, alpha) or np.any(rgba[~alpha]) or
                not np.array_equal(rgba[:, :, :3][functional8], source_rgb8[functional8]) or
                not np.array_equal(rgba[~functional8], before_functional[~functional8])):
            raise AssertionError('Source alpha/functional/outside-original support invariant failed')
        arrays.append(rgba)
        reports.append(dict(asset=frame['asset'], frame=i, logical_canvas=[72, 24], origin=[0, 0],
                            component_donor_metrics=counts, Source_occupied_cells=int(occupied.sum()),
                            baked_Original_cells=cells, baked_Original_RGBA_pixels=29*64,
                            generated_detail_not_claimed_for_baked_Original=True,
                            alpha_contract='Literal SourceNN8 occupied support, not OriginalScaleNx alpha',
                            Source_alpha_and_outside_support_exact=True,
                            functional_Original_RGB_exact=True, outside_29_functional_RGBA_unchanged=True))
    report = dict(method=METHOD, input_hashes=input_hashes, frames=reports,
                  decoder_module=dict(path=str(decoder_path), sha256=sha(decoder_bytes)),
                  python_version=platform.python_version(), python_implementation=platform.python_implementation(),
                  numpy_version=np.__version__, pillow_version=PILLOW_VERSION,
                  scope='Derived geometry/RGB registration only; no native QA or artistic approval',
                  generated_RGB_never_replaced_by_SourceRGB_outside_declared29=True,
                  parent_and_Source_unchanged=True, output_scale=8)
    return arrays, report


def run_recipe(recipe_path, output):
    recipe_path, output = Path(recipe_path), Path(output)
    if output.exists() or output.is_symlink():
        raise ValueError('output exists; never overwrite prior artwork')
    data = recipe_path.read_bytes()
    arrays, report = render_family(json.loads(data), recipe_path.resolve().parent)
    files = []
    for pixels, frame in zip(arrays, report['frames']):
        buffer = io.BytesIO()
        Image.fromarray(pixels).save(buffer, format='PNG', compress_level=9)
        payload = buffer.getvalue()
        name = frame['asset']+'-derived.png'
        frame['output'] = dict(file=name, sha256=sha(payload), bytes=len(payload), RGBA_sha256=sha(pixels.tobytes()))
        files.append((name, payload))
    report['execution'] = dict(status='success', method=METHOD, recipe_sha256=sha(data),
                               tool_sha256=sha(Path(__file__).read_bytes()),
                               source_sha256={f['asset']: f['source']['sha256'] for f in json.loads(data)['frames']},
                               parent_raw_sha256=sorted({json.loads(data)['parent_raw']['sha256']}),
                               output_sha256={f['asset']: f['output']['sha256'] for f in report['frames']})
    output.mkdir(parents=True, exist_ok=False)
    for name, payload in files:
        (output/name).write_bytes(payload)
    (output/'derived-provenance.json').write_text(json.dumps(report, indent=2, sort_keys=True)+'\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recipe', type=Path)
    parser.add_argument('output_new_directory', type=Path)
    args = parser.parse_args()
    report = run_recipe(args.recipe, args.output_new_directory)
    print(json.dumps(dict(execution=report['execution'])))


if __name__ == '__main__':
    main()
