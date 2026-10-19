"""Restore ALL SHIP09G2 Source-cyan owners using genuine bounded cyan only.

The protected noncyan hull is the literal existing G2 native4 palette projection.
Source supplies every cyan owner/support (wake, halo, interior paint) and limits,
never replacement RGB. No gains, synthetic grain, new generation or cascading
fills. Reproduction is not independent artwork or publication approval.
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

METHOD = 'derived-SHIP09G2-complete2-all-Source-cyan-noncyan-hull-v2'
DECODER_SHA = '66184a4758027dadbadb5e20fe90b2add2b9fc218b7810304b1a1ea2de74f58e'
G2_HELPER_SHA = '0338a925ccf26f856c9d5cc2230a3878ecafe6cd3a3d25903742d9e819ac8d12'
G2_LIBRARY_SHA = '5b6bbd03874da298dae953dc1c0f472d24f27031df4f46616368faefb0801676'
ASSETS = ['2009f', '200a0']
MAX_BYTES = 32 * 1024 * 1024
DISTANCE_CAP = 5.5
MISSING_CAP = .90
AGGREGATE_CAP = .85
COLOR_TOLERANCE = 4
MIN_DONORS = 128
MIN_DONOR_COLORS = 32


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def keys(value, fields, label):
    if type(value) is not dict or set(value) != set(fields):
        raise ValueError(f'{label}: exact fields required')


def hash_string(value):
    return type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def regular_bytes(path):
    """Bounded nonblocking no-follow regular-descriptor read, consumed once."""
    path = Path(path)
    if any(p.is_symlink() for p in [path, *path.parents]):
        raise ValueError('symlink input path')
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_BYTES:
        raise ValueError('bounded regular input required')
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
    with os.fdopen(os.open(path, flags), 'rb') as stream:
        opened = os.fstat(stream.fileno())
        if not stat.S_ISREG(opened.st_mode) or opened.st_size > MAX_BYTES:
            raise ValueError('bounded regular input required')
        data = stream.read(MAX_BYTES + 1)
        after = os.fstat(stream.fileno())
    def identity(v):
        return v.st_dev, v.st_ino, v.st_size, v.st_mtime_ns, v.st_mode
    if (len(data) > MAX_BYTES or identity(before) != identity(opened)
            or identity(opened) != identity(after) or identity(path.lstat()) != identity(before)):
        raise ValueError('input changed during bounded read')
    return data


def checked(binding, root):
    keys(binding, {'path', 'sha256'}, 'binding')
    name = binding['path']
    if type(name) is not str or not name or '\\' in name or ':' in name:
        raise ValueError('portable relative path required')
    path = PurePosixPath(name)
    if path.is_absolute() or any(p in ('', '.', '..') for p in name.split('/')):
        raise ValueError('unsafe relative path')
    if not hash_string(binding['sha256']):
        raise ValueError('sha256 required')
    data = regular_bytes(Path(root).joinpath(*path.parts))
    if sha(data) != binding['sha256']:
        raise ValueError('input hash mismatch: ' + name)
    return data


def verified_decoder(project):
    data = checked(dict(path='tools/hd_frame_policy.py', sha256=DECODER_SHA), project)
    scope = dict(__name__='_verified_source_decoder', __file__='<verified-source-decoder-buffer>')
    exec(compile(data, '<verified-source-decoder-buffer>', 'exec'), scope)
    return scope['_indices']


def scale2(source):
    b = np.concatenate([source[:1], source[:-1]], axis=0)
    d = np.concatenate([source[:, :1], source[:, :-1]], axis=1)
    f = np.concatenate([source[:, 1:], source[:, -1:]], axis=1)
    g = np.concatenate([source[1:], source[-1:]], axis=0)
    condition = (b != g) & (d != f)
    out = np.empty((source.shape[0]*2, source.shape[1]*2), np.uint16)
    out[0::2, 0::2] = np.where(condition & (d == b), d, source)
    out[0::2, 1::2] = np.where(condition & (b == f), f, source)
    out[1::2, 0::2] = np.where(condition & (d == g), d, source)
    out[1::2, 1::2] = np.where(condition & (g == f), f, source)
    return out


def water(source):
    return (source >= 144) & (source <= 159)


def hull_guard(source):
    """Source noncyan row envelope plus exactly one logical-cell halo."""
    solid = (source < 256) & ~water(source)
    core = np.zeros(source.shape, bool)
    for y in range(40):
        xs = np.where(solid[y])[0]
        if len(xs):
            core[y, xs.min():xs.max()+1] = True
    if not core.any():
        raise ValueError('missing Source hull')
    guard = core.copy()
    yy, xx = np.where(core)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            guard[np.clip(yy+dy, 0, 39), np.clip(xx+dx, 0, 71)] = True
    return guard


def source_caps(sources, palette):
    colors = np.concatenate([palette[s[water(s)]] for s in sources]).astype(np.int32)
    if not len(colors):
        raise ValueError('missing authentic Source cyan')
    chroma = colors[:, 2]-colors[:, 0]
    if np.any(chroma <= 0) or np.any(colors[:, 1] <= colors[:, 0]) or np.any(colors[:, 1] > colors[:, 2]):
        raise ValueError('Source cyan hue domain required')
    fractions = [(int(c[1]-c[0]), int(c[2]-c[0])) for c in colors]
    minimum = min(fractions, key=lambda q:q[0]/q[1])
    maximum = max(fractions, key=lambda q:q[0]/q[1])
    light = colors @ np.array([54, 183, 19], np.int32)
    return dict(rgb_min=np.maximum(0, colors.min(axis=0)-COLOR_TOLERANCE),
                rgb_max=np.minimum(255, colors.max(axis=0)+COLOR_TOLERANCE),
                hue_min_fraction=list(minimum), hue_max_fraction=list(maximum),
                chroma_min=max(1, int(chroma.min())-COLOR_TOLERANCE),
                luminance_min=int(light.min())-COLOR_TOLERANCE*256,
                luminance_max=int(light.max())+COLOR_TOLERANCE*256)


def cyan_donors(rgb, caps):
    c = rgb.astype(np.int32)
    green = c[:, :, 1]-c[:, :, 0]
    blue = c[:, :, 2]-c[:, :, 0]
    low, high = caps['hue_min_fraction'], caps['hue_max_fraction']
    light = c @ np.array([54, 183, 19], np.int32)
    return (np.all((c >= caps['rgb_min']) & (c <= caps['rgb_max']), axis=2)
            & (blue >= caps['chroma_min']) & (green > 0) & (green <= blue)
            & (green*low[1] >= blue*low[0])
            & (green*high[1] <= blue*high[0])
            & (light >= caps['luminance_min']) & (light <= caps['luminance_max']))


def index_array(value, width, height, label):
    if (type(value) is not dict or type(value.get('width')) is not int or type(value.get('height')) is not int
            or value.get('width') != width or value.get('height') != height
            or type(value.get('indices')) is not list or len(value['indices']) != width*height
            or any(type(v) is not int or not 0 <= v <= 256 for v in value['indices'])):
        raise ValueError(label + ': invalid indexed canvas')
    return np.array(value['indices'], np.uint16).reshape(height, width)


def render_frame(source, palette, raw, crop, baseline_indices, caps):
    """Pure buffers; same-phase raw donors only, never derived output donors."""
    source4 = scale2(scale2(source))
    guard4 = (source4 < 256) & ~water(source4)
    wake4 = water(source4)
    if not wake4.any():
        raise ValueError('missing Source cyan owners')
    lut = np.zeros((257, 4), np.uint8)
    lut[:256, :3] = palette
    lut[:256, 3] = 255
    baseline = lut[baseline_indices]
    # All noncyan Source structural owners retain exact prior G2 RGBA.
    # Source-cyan owners ALL receive eligible genuine RGB, including interior
    # paint and the old halo. Source-transparent owners are never fabricated.
    result = np.zeros(baseline.shape, np.uint8)
    result[guard4] = baseline[guard4]
    l, t, w, h = crop
    sx, sy = w/72, h/40
    region = raw[t:t+h, l:l+w]
    eligible = ((region[:, :, 3] >= 128)
                & cyan_donors(region[:, :, :3], caps))
    donor_count = int(eligible.sum())
    donor_colors = len(np.unique(region[:, :, :3][eligible], axis=0))
    if donor_count < MIN_DONORS or donor_colors < MIN_DONOR_COLORS:
        raise ValueError('insufficient genuine same-phase cyan texture')
    out_y, out_x = np.where(wake4)
    u = ((out_x+.5)/4)*sx
    v = ((out_y+.5)/4)*sy
    px, py = np.floor(u).astype(int), np.floor(v).astype(int)
    direct = eligible[py, px]
    fraction = float(np.mean(~direct))
    if fraction > MISSING_CAP + 1e-12:
        raise ValueError('fixed missing fraction exceeded')
    maximum = 0.0
    for point in np.where(~direct)[0]:
        x0 = max(0, int(math.floor(u[point]-DISTANCE_CAP*sx-1)))
        x1 = min(w, int(math.ceil(u[point]+DISTANCE_CAP*sx+1)))
        y0 = max(0, int(math.floor(v[point]-DISTANCE_CAP*sy-1)))
        y1 = min(h, int(math.ceil(v[point]+DISTANCE_CAP*sy+1)))
        dy, dx = np.where(eligible[y0:y1, x0:x1])
        if not len(dx):
            raise ValueError('no bounded same-phase cyan donor')
        dx, dy = dx+x0, dy+y0
        distance2 = ((dx+.5-u[point])/sx)**2 + ((dy+.5-v[point])/sy)**2
        nearest = int(np.argmin(distance2))  # row-major y/x tie order is fixed
        distance = math.sqrt(float(distance2[nearest]))
        if distance > DISTANCE_CAP + 1e-12:
            raise ValueError('fixed donor distance exceeded')
        px[point], py[point] = dx[nearest], dy[nearest]
        maximum = max(maximum, distance)
    chosen = region[py, px, :3]
    result[out_y, out_x, :3] = chosen
    result[out_y, out_x, 3] = 255
    if (not np.array_equal(result[guard4], baseline[guard4])
            or not np.array_equal(result[:, :, 3][~guard4], np.where(wake4, 255, 0)[~guard4])):
        raise ValueError('noncyan hull or Source-cyan support changed')
    return result, dict(samples=int(len(out_x)), repaired=int((~direct).sum()),
        missing_fraction=fraction, maximum_donor_logical_distance=maximum,
        raw_donors=donor_count, raw_donor_RGB_colors=donor_colors,
        used_donor_RGB_colors=len(np.unique(chosen, axis=0)),
        noncyan_structural_hull_RGBA_sha256=sha(result[guard4].tobytes()),
        noncyan_structural_hull_exact_to_existing_G2_projection=True,
        all_Source_cyan_alpha_exact_to_SourceScale4=True,
        Original_RGB_samples_painted=0,
        Source_cyan_RGB_outside_original_raw_donor_tuples=0)


def run_recipe(recipe_path, output, project_root=None):
    recipe_path, output = Path(recipe_path).absolute(), Path(output).absolute()
    if output.exists() or any(p.is_symlink() for p in [output, *output.parents]):
        raise ValueError('fresh nonsymlink output required')
    if not output.parent.is_dir():
        raise ValueError('existing output parent required')
    own_sha = sha(regular_bytes(Path(__file__)))
    rb = regular_bytes(recipe_path)
    recipe = json.loads(rb)
    keys(recipe, {'format_version', 'method', 'raw_png', 'palette', 'candidate',
                  'runtime_qa', 'indexed_bank', 'actual_invocation', 'frames'}, 'recipe')
    if type(recipe['format_version']) is not int or recipe['format_version'] != 1 or recipe['method'] != METHOD:
        raise ValueError('fixed method/version required')
    frames = recipe['frames']
    if type(frames) is not list or len(frames) != 2 or [f.get('asset') for f in frames if type(f) is dict] != ASSETS:
        raise ValueError('complete ordered SHIP09G2 pair required')
    project = Path(project_root) if project_root else Path(__file__).resolve().parents[1]
    decode = verified_decoder(project)
    raw_payload = checked(recipe['raw_png'], recipe_path.parent)
    with Image.open(io.BytesIO(raw_payload)) as im:
        if im.format != 'PNG' or im.mode != 'RGBA' or im.size != (1536, 1024):
            raise ValueError('exact1536x1024 RGBA raw atlas required')
        raw = np.asarray(im).copy()
    pb = checked(recipe['palette'], recipe_path.parent)
    if len(pb) != 768 or max(pb) > 63:
        raise ValueError('genuine VGA palette required')
    p6 = np.frombuffer(pb, np.uint8).reshape(256, 3).astype(np.uint16)
    palette = ((p6 << 2) | (p6 >> 4)).astype(np.uint8)
    candidate_bytes = checked(recipe['candidate'], recipe_path.parent)
    candidate = json.loads(candidate_bytes)
    seqs = candidate.get('sequences')
    if (type(seqs) is not list or len(seqs) != 1 or seqs[0].get('base_asset') != 0x2009f
            or type(seqs[0]['base_asset']) is not int or seqs[0].get('frame_count') != 2
            or type(seqs[0].get('frame_count')) is not int
            or candidate.get('complete_family') is not True):
        raise ValueError('literal complete candidate required')
    cf = seqs[0].get('frames')
    if type(cf) is not list or len(cf) != 2:
        raise ValueError('candidate complete2 frame order required')
    qa = json.loads(checked(recipe['runtime_qa'], recipe_path.parent))
    rows = {asset: f for asset, f in zip(ASSETS, cf)}
    binding = sha(json.dumps(rows, sort_keys=True, separators=(',', ':')).encode())
    files = {f.get('file') for f in cf}
    if (len(files) != 1 or any(type(f) is not str for f in files)
            or qa.get('candidate_sha256') != sha(candidate_bytes)
            or qa.get('frame_bindings_sha256') != binding
            or type(qa.get('validated_frames')) is not int or qa.get('validated_frames') != 2 or qa.get('diagnostics') != []
            or qa.get('actual_sourceG2_helper_sha256') != G2_HELPER_SHA
            or qa.get('library_sha256') != G2_LIBRARY_SHA
            or qa.get('source_newer_than_library') is not False
            or qa.get('any_game_source_newer_than_library') is not False
            or qa.get('artwork_sha256') != {next(iter(files)): sha(raw_payload)}):
        raise ValueError('literal currentG2 QA/candidate/raw binding mismatch')
    invocation = json.loads(checked(recipe['actual_invocation'], recipe_path.parent))
    if (type(invocation.get('exit_code')) is not int or invocation.get('exit_code') != 0
            or invocation.get('runtime_QA_sha256') != recipe['runtime_qa']['sha256']
            or invocation.get('indexed_bank_sha256') != recipe['indexed_bank']['sha256']):
        raise ValueError('actual invocation does not bind literal QA/indexed bank')
    bank = json.loads(checked(recipe['indexed_bank'], recipe_path.parent))
    if type(bank) is not list or len(bank) != 2 or [r.get('asset') for r in bank if type(r) is dict] != ASSETS:
        raise ValueError('complete ordered actual bank required')
    qr = qa.get('frames')
    if type(qr) is not list or len(qr) != 2 or [r.get('asset') for r in qr if type(r) is dict] != ASSETS:
        raise ValueError('complete ordered QA Source frames required')
    sources, baselines, crops = [], [], []
    for i, (frame, c, row) in enumerate(zip(frames, cf, bank)):
        keys(frame, {'asset', 'source', 'crop'}, 'frame')
        keys(c, {'frame', 'file', 'logical_width', 'logical_height', 'origin', 'source_sha256', 'crop'}, 'literal frame')
        crop = frame['crop']
        name = c['file']
        if (type(name) is not str or not name or '\\' in name or ':' in name
                or PurePosixPath(name).is_absolute() or any(p in ('', '.', '..') for p in name.split('/'))):
            raise ValueError('portable literal artwork path required')
        if (type(crop) is not list or len(crop) != 4 or any(type(v) is not int for v in crop)
                or not 0 <= crop[0] < crop[0]+crop[2] <= 1536
                or not 0 <= crop[1] < crop[1]+crop[3] <= 1024
                or crop[2]*40 != crop[3]*72 or crop[2] < 288
                or c['frame'] != i or type(c['frame']) is not int or c['crop'] != crop
                or type(c['logical_width']) is not int or type(c['logical_height']) is not int
                or type(c['origin']) is not list or any(type(v) is not int for v in c['origin'])
                or c['logical_width'] != 72 or c['logical_height'] != 40 or c['origin'] != [0, 0]
                or c['source_sha256'] != frame['source']['sha256']):
            raise ValueError('exact canvas/crop/source binding required')
        if (qr[i].get('source_sha256') != frame['source']['sha256'] or qr[i].get('logical_canvas') != [72, 40]):
            raise ValueError('QA Source identity differs')
        excluded = raw[:, i*768:(i+1)*768, 3].copy()
        x, y, cw, ch = crop
        excluded[y:y+ch, max(x, i*768)-i*768:min(x+cw, (i+1)*768)-i*768] = 0
        if np.any(excluded >= 128):
            raise ValueError('crop clips meaningful own-phase alpha')
        if i == 1 and x < 768 and np.any(raw[y:y+ch, x:768, 3] >= 128):
            raise ValueError('crop includes foreign phase alpha')
        if not (i*768 <= crop[0] < crop[0]+crop[2] <= (i+1)*768):
            # The authentic selected second crop starts5px before midpoint;
            # neither crop may include the OTHER phase's alpha128 content.
            if i != 1 or not 760 <= crop[0] < 768:
                raise ValueError('crop escapes its own phase cell')
        w, h, idx = decode(checked(frame['source'], recipe_path.parent))
        if (w, h) != (72, 40) or any(v != 256 and not 0 <= v < 240 for v in idx):
            raise ValueError('original72x40 ordinary Source required')
        source = np.array(idx, np.uint16).reshape(40, 72)
        if not np.array_equal(index_array(row.get('source'), 72, 40, 'bank Source'), source):
            raise ValueError('bank Source differs from authenticated Source')
        scales = row.get('scales')
        if type(scales) is not list or len(scales) != 4 or [s.get('scale') for s in scales if type(s) is dict] != [1, 2, 3, 4]:
            raise ValueError('ordered actual native1..4 bank required')
        for k, s in enumerate(scales, 1):
            if type(s.get('scale')) is not int:
                raise ValueError('integer native scale required')
            indexed = index_array(s, 72*k, 40*k, 'bank scale')
            if np.any((indexed >= 240) & (indexed < 256)):
                raise ValueError('ordinary Source bank gained reserved labels')
        sources.append(source); baselines.append(indexed); crops.append(crop)
    a = np.where(water(sources[0]), 256, sources[0])
    b = np.where(water(sources[1]), 256, sources[1])
    if not np.array_equal(a, b):
        raise ValueError('authentic shared hull material differs between phases')
    if not np.array_equal(hull_guard(sources[0]), hull_guard(sources[1])):
        raise ValueError('shared hull envelope differs')
    caps = source_caps(sources, palette)
    payloads, reports = [], []
    for frame, source, baseline, crop in zip(frames, sources, baselines, crops):
        rgba, report = render_frame(source, palette, raw, crop, baseline, caps)
        stream = io.BytesIO();Image.fromarray(rgba).save(stream, format='PNG', compress_level=9)
        payloads.append((frame['asset'], stream.getvalue()))
        reports.append(dict(asset=frame['asset'], RGBA_sha256=sha(rgba.tobytes()), **report))
    if sum(r['repaired'] for r in reports)/sum(r['samples'] for r in reports) > AGGREGATE_CAP + 1e-12:
        raise ValueError('complete2 aggregate repair cap exceeded')
    if sha(regular_bytes(Path(__file__))) != own_sha:
        raise ValueError('executing helper changed')
    receipt = dict(execution=dict(status='success', method=METHOD, recipe_sha256=sha(rb),
        tool_sha256=own_sha, source_sha256={f['asset']: f['source']['sha256'] for f in frames},
        parent_raw_sha256=[sha(raw_payload)], output_sha256={a: sha(p) for a, p in payloads}),
        decoder_sha256=DECODER_SHA, candidate_sha256=sha(candidate_bytes),
        literal_QA_sha256=recipe['runtime_qa']['sha256'], indexed_bank_sha256=recipe['indexed_bank']['sha256'],
        caps={k:v.tolist() if isinstance(v, np.ndarray) else v for k,v in caps.items()}, reports=reports,
        Python=sys.version.split()[0], NumPy=np.__version__, Pillow=PILLOW_VERSION,
        limits=['Every noncyan structural Source4 owner keeps exact existing G2 native4 palette RGBA of genuine raw, not an unquantized raw RGB identity claim.',
                'All Source-cyan support/partition and Source-derived caps get zero generated-HD credit; every restored cyan RGB tuple comes unchanged from this phase raw.',
                'Final alpha is exactly Source4cyan support plus baseline alpha at noncyan Source4 owners; Source4transparent owners are clear. Whole Original-alpha identity is not promised. Fresh G2allscale review required.',
                'No generator invocation, grain or RGB gain; numerical reproduction does not confer independent art approval.'])
    payloads.append(('execution-receipt', (json.dumps(receipt, indent=2, sort_keys=True)+'\n').encode()))
    output.mkdir()  # exclusive; every input/frame/cap already validated in memory
    for name, payload in payloads:
        suffix = '.json' if name == 'execution-receipt' else '.png'
        with (output/(name+suffix)).open('xb') as stream:
            stream.write(payload)
    return receipt


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('recipe', type=Path);p.add_argument('output', type=Path)
    p.add_argument('--project-root', type=Path)
    a = p.parse_args()
    print(json.dumps(run_recipe(a.recipe, a.output, a.project_root)['execution'], sort_keys=True))


if __name__ == '__main__':
    main()
