"""Private derived-RGB singleton cleanup with declared Original functional cells.

The reviewed DSHP renderer preserves broad parent RGB and supplies SourceScale4
coverage. Only explicitly listed painted logical cells then receive actual
Original Scale4 RGBA. This is derived artwork, never untouched generation.
"""
import argparse
import hashlib
import io
import json
import sys
from pathlib import Path
import numpy as np
from PIL import Image

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / 'tools'))
import hd_dshp20_cleanup as base

BASE_SHA = 'c6123e9591f0a169846677019ddcb944bf9c2b4c9184a7d8ab02a08546de409b'
DECODER_SHA = '66184a4758027dadbadb5e20fe90b2add2b9fc218b7810304b1a1ea2de74f58e'
METHOD = 'derived-parent-full-RGB-SourceScale4-geometry-explicit-functional-Original-v1'

def digest(b): return hashlib.sha256(b).hexdigest()

def dependency_pins():
    tool = Path(base.__file__).resolve()
    decoder = Path(base.hd_frame_policy.__file__).resolve()
    assert digest(tool.read_bytes()) == BASE_SHA
    assert digest(decoder.read_bytes()) == DECODER_SHA
    return dict(RGB_geometry_tool=dict(path=str(tool), sha256=BASE_SHA),
                Source_decoder=dict(path=str(decoder), sha256=DECODER_SHA))

def retain_functional_original(rgba, source, palette, cells):
    """Copy the whole actual Scale4 kernel footprint, including transparency."""
    h, w = source.shape
    if not isinstance(cells, list) or not 1 <= len(cells) <= 64:
        raise ValueError('need1..64 explicit functional Original cells')
    for xy in cells:
        if (not isinstance(xy, list) or len(xy) != 2 or any(type(v) is not int for v in xy)
                or not 0 <= xy[0] < w or not 0 <= xy[1] < h or not 0 <= source[xy[1], xy[0]] < 256):
            raise ValueError('functional cell must be exact integer inbounds painted Source')
    if cells != sorted(cells) or len({tuple(xy) for xy in cells}) != len(cells):
        raise ValueError('functional cells must be sorted and unique')
    if rgba.shape != (h*4, w*4, 4) or rgba.dtype != np.uint8:
        raise ValueError('need complete native-times4 uint8 RGBA canvas')
    s4 = base.scale2(base.scale2(source))
    mask = np.zeros(s4.shape, bool)
    for x, y in cells: mask[y*4:(y+1)*4, x*4:(x+1)*4] = True
    original = np.zeros_like(rgba)
    painted = s4 < 256
    original[:,:,:3][painted] = palette[s4[painted]]
    original[:,:,3][painted] = 255
    out = rgba.copy()
    out[mask] = original[mask]
    assert np.array_equal(out[~mask], rgba[~mask])
    assert np.array_equal(out[mask], original[mask])
    return out, dict(cells=cells, Source_indices=[int(source[y,x]) for x,y in cells],
        actual_Original_Scale4_RGBA_samples=int(mask.sum()),
        actual_Original_transparent_samples=int((mask & ~painted).sum()),
        RGBA_changes=int(np.any(out != rgba, axis=2).sum()),
        outside_explicit_footprints_RGBA_exact=True,
        retained_Original_not_generated_HD=True)

def run_recipe(recipe_path, output):
    recipe_path, output = Path(recipe_path), Path(output)
    if output.exists(): raise ValueError('fresh absent output directory required')
    dependencies = dependency_pins()
    rb = recipe_path.read_bytes(); recipe = json.loads(rb)
    if (not isinstance(recipe, dict) or set(recipe) != {'format_version','geometry_recipe','functional_original_cells'}
            or type(recipe['format_version']) is not int or recipe['format_version'] != 1):
        raise ValueError('exact wrapper recipe fields/version required')
    geometry = recipe['geometry_recipe']
    if not isinstance(geometry, dict) or not isinstance(geometry.get('frames'), list) or len(geometry['frames']) != 1:
        raise ValueError('this private wrapper supports one complete singleton per recipe')
    arrays, report = base.render_family(geometry, recipe_path.resolve().parent)
    frame = geometry['frames'][0]
    _, payload = base.checked(frame['source'], recipe_path.resolve().parent)
    w,h,cells = base._indices(payload)
    source = np.asarray(cells,np.uint16).reshape(h,w)
    _, pb = base.checked(geometry['palette'], recipe_path.resolve().parent)
    p6 = np.frombuffer(pb,np.uint8).reshape(256,3).astype(np.uint16)
    palette = ((p6 << 2) | (p6 >> 4)).astype(np.uint8)
    rgba, functional = retain_functional_original(arrays[0], source, palette, recipe['functional_original_cells'])
    encoded = io.BytesIO(); Image.fromarray(rgba).save(encoded, format='PNG', compress_level=9)
    png = encoded.getvalue(); asset = frame['asset']
    execution = dict(status='success', method=METHOD, recipe_sha256=digest(rb),
        tool_sha256=digest(Path(__file__).read_bytes()), source_sha256={asset:frame['source']['sha256']},
        parent_raw_sha256=[frame['raw_png']['sha256']], output_sha256={asset:digest(png)})
    report.update(method=METHOD, geometry_method=base.METHOD, dependencies=dependencies,
        functional_Original=functional, execution=execution,
        output=dict(asset=asset, file=asset+'-derived.png', sha256=digest(png),
                    RGBA_sha256=digest(rgba.tobytes()), size=[w*4,h*4]),
        scope='DERIVED broad generated RGB, SourceScale4 geometry and explicit retained Original functional cells; no game-context or art acceptance.')
    output.mkdir(parents=True)
    (output/(asset+'-derived.png')).write_bytes(png)
    (output/'derived-provenance.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    (output/'normalized-execution.json').write_text(json.dumps(execution,indent=2,sort_keys=True)+'\n')
    return report

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recipe',type=Path);parser.add_argument('output_new_directory',type=Path)
    args=parser.parse_args(); result=run_recipe(args.recipe,args.output_new_directory)
    print(json.dumps(result['execution'],sort_keys=True))
