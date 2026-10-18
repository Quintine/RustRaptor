"""Explicit DERIVED RGB-preserving Source-geometry cleanup for mechanical families.

Unlike a Source-color/high-pass reconstruction, this keeps complete generated RGB
panels. It registers a declared parent viewport, uses actual Original Scale4x
coverage, fills only uncovered boundary samples from nearby generated RGB, and
shares complete RGB on Source-identical stationary pixels. Functional Source
palette cells are explicit Original replacements. Inputs are never overwritten.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import sys
from fractions import Fraction
from pathlib import Path
import numpy as np
from PIL import Image, __version__ as PILLOW_VERSION
import hd_frame_policy
from hd_frame_policy import _indices

METHOD = "derived-generated-RGB-SourceScale4-geometry-coherent-dynamic-regions-v2"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def checked(binding, base):
    if not isinstance(binding, dict) or set(binding) != {"path", "sha256"}:
        raise ValueError("input binding needs exactly path and sha256")
    p = Path(binding["path"])
    if not p.is_absolute():
        p = base / p
    data = p.read_bytes()
    if digest(data) != binding["sha256"]:
        raise ValueError(f"input hash mismatch: {p}")
    return p.resolve(), data


def scale2(source):
    """Original render::upscale Scale2x; label256 remains transparent."""
    h, w = source.shape
    b = np.concatenate([source[:1], source[:-1]], axis=0)
    d = np.concatenate([source[:, :1], source[:, :-1]], axis=1)
    f = np.concatenate([source[:, 1:], source[:, -1:]], axis=1)
    g = np.concatenate([source[1:], source[-1:]], axis=0)
    condition = (b != g) & (d != f)
    out = np.empty((h * 2, w * 2), dtype=np.uint16)
    out[0::2, 0::2] = np.where(condition & (d == b), d, source)
    out[0::2, 1::2] = np.where(condition & (b == f), f, source)
    out[1::2, 0::2] = np.where(condition & (d == g), d, source)
    out[1::2, 1::2] = np.where(condition & (g == f), f, source)
    return out


def fill_generated_rgb(rgb, trusted, mask, source4, max_distance):
    """Deterministic nearest generated RGB, preferring matching Source labels.

    No Source RGB fallback or synthesized texture is used. A frame without a
    nearby generated donor is rejected. Decisions never cascade through fills.
    """
    donors = trusted & mask
    missing = mask & ~trusted
    result = rgb.copy()
    distances = []
    for y, x in np.argwhere(missing):
        y0, y1 = max(0, y - max_distance), min(mask.shape[0], y + max_distance + 1)
        x0, x1 = max(0, x - max_distance), min(mask.shape[1], x + max_distance + 1)
        dy, dx = np.nonzero(donors[y0:y1, x0:x1])
        if not len(dy):
            raise ValueError(f"no generated RGB donor within bound at ({x},{y})")
        yy, xx = dy + y0, dx + x0
        distance = (yy-y)**2 + (xx-x)**2
        allowed = distance <= max_distance**2
        if not np.any(allowed):
            raise ValueError(f"no generated RGB donor within distance at ({x},{y})")
        yy, xx, distance = yy[allowed], xx[allowed], distance[allowed]
        # Exact Source label preference prevents crossing an adjacent material
        # when an equally nearby native material donor actually exists.
        same = source4[yy, xx] == source4[y, x]
        if np.any(same):
            yy, xx, distance = yy[same], xx[same], distance[same]
        choice = np.lexsort((xx, yy, distance))[0]
        result[y, x] = rgb[yy[choice], xx[choice]]
        distances.append(int(distance[choice]))
    return result, dict(filled_generated_RGB_samples=int(missing.sum()),
                        maximum_donor_squared_distance=max(distances, default=0),
                        no_Source_RGB_or_noise_fallback=True)


def dynamic_regions(sources):
    """Source-observed changing parts, with a fixed one-native-cell halo.

    Keep whole parent RGB within each 8-connected changing component's bounding
    box. Otherwise isolated unchanged Source labels inside a changing cockpit
    can become a visible mosaic of stationary and phase-specific RGB.
    """
    changed = np.any(sources != sources[0], axis=0)
    h, w = changed.shape
    seen = set()
    rectangles = []
    for y, x in np.argwhere(changed):
        start = (int(y), int(x))
        if start in seen:
            continue
        todo, component = [start], []
        seen.add(start)
        while todo:
            yy, xx = todo.pop()
            component.append((yy, xx))
            for ny in range(max(0, yy-1), min(h, yy+2)):
                for nx in range(max(0, xx-1), min(w, xx+2)):
                    if changed[ny, nx] and (ny, nx) not in seen:
                        seen.add((ny, nx))
                        todo.append((ny, nx))
        rectangles.append([max(0, min(x for y,x in component)-1),
                           max(0, min(y for y,x in component)-1),
                           min(w, max(x for y,x in component)+2),
                           min(h, max(y for y,x in component)+2)])
    return sorted(set(tuple(r) for r in rectangles))


def render_family(recipe, base):
    if not isinstance(recipe, dict) or set(recipe) - {
        "format_version", "label", "palette", "output_scale", "max_fill_distance_pixels",
        "shared_backing_anchor", "frames"
    }:
        raise ValueError("unknown recipe fields")
    if type(recipe.get("format_version")) is not int or recipe["format_version"] != 1:
        raise ValueError("unsupported recipe version")
    if type(recipe.get("output_scale")) is not int or recipe["output_scale"] != 4:
        raise ValueError("output_scale must be exactly4 for actual SourceScale4 coverage")
    bound = recipe.get("max_fill_distance_pixels", 12)
    if type(bound) is not int or not 1 <= bound <= 24:
        raise ValueError("donor distance must be integer1..24 output pixels")
    frames = recipe.get("frames")
    if not isinstance(frames, list) or not 1 <= len(frames) <= 16:
        raise ValueError("need1..16 complete-family frames")
    anchor = recipe.get("shared_backing_anchor", 0)
    if type(anchor) is not int or not 0 <= anchor < len(frames):
        raise ValueError("invalid stationary backing anchor")
    palette_path, palette_bytes = checked(recipe["palette"], base)
    if len(palette_bytes) != 768 or max(palette_bytes) > 63:
        raise ValueError("need exact768-byte six-bit Original palette")
    p6 = np.frombuffer(palette_bytes, np.uint8).reshape(256,3).astype(np.uint16)
    palette = ((p6 << 2) | (p6 >> 4)).astype(np.uint8)
    loaded, inputs, assets = [], {str(palette_path): digest(palette_bytes)}, set()
    shape = None
    for f in frames:
        if not isinstance(f, dict) or set(f) != {
            "asset", "source", "raw_png", "viewport", "sampling_offset_native", "origin"
        }:
            raise ValueError("frame needs exact declared source/raw/viewport/offset/origin fields")
        asset = f["asset"]
        if not isinstance(asset, str) or not asset or any(c not in "0123456789abcdef" for c in asset) or asset in assets:
            raise ValueError("need unique lowercase hex asset IDs")
        assets.add(asset)
        sp, sb = checked(f["source"], base)
        w, h, cells = _indices(sb)
        if shape is None:
            shape = (h,w)
        if shape != (h,w) or w*h*16 > 4_194_304:
            raise ValueError("inconsistent or excessive complete-family canvas")
        if not isinstance(f["origin"], list) or len(f["origin"]) != 2 or any(type(x) is not int for x in f["origin"]):
            raise ValueError("need literal two-integer native origin")
        source = np.asarray(cells,np.uint16).reshape(h,w)
        source4 = scale2(scale2(source))
        mask = source4 < 256
        rp, rb = checked(f["raw_png"], base)
        if len(rb) > 32*1024*1024:
            raise ValueError("parent PNG exceeds32MiB")
        if not isinstance(f["viewport"], list) or len(f["viewport"]) != 4:
            raise ValueError("need four exact rational parent viewport bounds")
        l,t,r,b = [Fraction(x) for x in f["viewport"]]
        if not isinstance(f["sampling_offset_native"], list) or len(f["sampling_offset_native"]) != 2:
            raise ValueError("need exact rational two-coordinate registration offset")
        ox,oy = [Fraction(x) for x in f["sampling_offset_native"]]
        if abs(ox)>2 or abs(oy)>2:
            raise ValueError("registration exceeds two native cells")
        actual = [l+ox*(r-l)/w,t+oy*(b-t)/h,r+ox*(r-l)/w,b+oy*(b-t)/h]
        with Image.open(io.BytesIO(rb)) as image:
            if image.format != "PNG" or image.width*image.height > 4_194_304:
                raise ValueError("parent must be bounded PNG")
            if not 0<=l<r<=image.width or not 0<=t<b<=image.height:
                raise ValueError("declared parent viewport exceeds image")
            pixels = np.asarray(image.convert("RGBA").transform(
                (w*4,h*4),Image.Transform.EXTENT,tuple(map(float,actual)),Image.Resampling.BICUBIC)).copy()
        trusted = pixels[:,:,3]>=128
        rgb, filling = fill_generated_rgb(pixels[:,:,:3],trusted,mask,source4,bound)
        loaded.append(dict(frame=f,source=source,source4=source4,mask=mask,rgb=rgb,
                           sampled=pixels,trusted=trusted,filling=filling,
                           actual_sampling_bounds=[str(x)for x in actual]))
        inputs[str(sp)] = digest(sb)
        inputs[str(rp)] = digest(rb)
    # Whole RGB, not just high-frequency noise, is shared on truly identical
    # SourceScale4 labels. Changed Source labels keep each phase's parent RGB.
    s4 = np.stack([x['source4']for x in loaded])
    common = np.all(s4==s4[anchor],axis=0) & (s4[anchor]<256)
    regions = dynamic_regions(np.stack([x['source'] for x in loaded]))
    for l,t,r,b in regions:
        common[t*4:b*4,l*4:r*4] = False
    stationary_rgb = loaded[anchor]['rgb'].copy()
    outputs, reports = [], []
    for item in loaded:
        f, source, mask = item['frame'],item['source'],item['mask']
        h,w = source.shape
        rgb = item['rgb'].copy()
        shared_changed = int(np.any(rgb[common]!=stationary_rgb[common],axis=1).sum())
        rgb[common] = stationary_rgb[common]
        functional_samples = 0
        for y,x in np.argwhere((source>=240)&(source<256)):
            rgb[y*4:(y+1)*4,x*4:(x+1)*4] = palette[source[y,x]]
            functional_samples += int(mask[y*4:(y+1)*4,x*4:(x+1)*4].sum())
        rgba = np.zeros((h*4,w*4,4),np.uint8)
        rgba[:,:,:3][mask] = rgb[mask]
        rgba[:,:,3][mask] = 255
        source_nn = np.repeat(np.repeat(source,4,axis=0),4,axis=1)
        valid_nn = source_nn<256
        disagreement = np.zeros(mask.shape,bool)
        disagreement[mask&valid_nn] = np.any(rgb[mask&valid_nn]!=palette[source_nn[mask&valid_nn]],axis=1)
        if int(disagreement.sum()) < int(mask.sum())//4:
            raise ValueError("insufficient complete generated RGB variation; refusing SourceNN HD relabel")
        outputs.append(rgba)
        reports.append(dict(asset=f['asset'],logical_width=w,logical_height=h,origin=f['origin'],
                            Source_painted_cells=int((source<256).sum()),SourceScale4_opaque_samples=int(mask.sum()),
                            derived_alpha_exact_SourceScale4=True,actual_sampling_bounds=item['actual_sampling_bounds'],
                            removed_generated_outside_SourceScale4=int((item['trusted']&~mask).sum()),
                            original_sampled_RGB_preserved_before_stationary_share=int((item['trusted']&mask).sum()),
                            stationary_full_RGB_replacements=shared_changed,
                            functional_Original_RGB_samples=functional_samples,
                            generated_RGB_different_from_SourceNN_samples=int(disagreement.sum()),
                            **item['filling']))
    for rgba in outputs:
        assert np.array_equal(rgba[:,:,:3][common],outputs[anchor][:,:,:3][common])
    return outputs, dict(method=METHOD,output_class='DERIVED_SCRIPTED_RGBA_NOT_UNTOUCHED_GENERATION',
        input_hashes=inputs,output_scale=4,shared_SourceScale4_labels=int(common.sum()),stationary_anchor_asset=frames[anchor]['asset'],
        Source_derived_dynamic_component_halo_native=1,dynamic_regions_native=[list(r) for r in regions],
        RGB_policy='Preserve full generated RGB, except declared nearest generated-RGB fills, Source-identical full-RGB backing share, and literal functional Source palette cells; no noise/highpass reconstruction.',
        source_mask='Actual Original Scale4x = Scale2x twice; complete native canvas and origin retained.',
        frames=reports,
        decoder_module=dict(path=str(Path(hd_frame_policy.__file__).resolve()),
                            sha256=digest(Path(hd_frame_policy.__file__).read_bytes())),
        python_version=sys.version,numpy_version=np.__version__,pillow_version=PILLOW_VERSION)


def run_recipe(recipe_path, output):
    recipe_path, output = Path(recipe_path),Path(output)
    if output.exists():
        raise ValueError('output directory already exists; no inputs or old outputs overwritten')
    rb = recipe_path.read_bytes();recipe = json.loads(rb)
    arrays,report = render_family(recipe,recipe_path.resolve().parent)
    payloads=[]
    for f,array in zip(recipe['frames'],arrays):
        b=io.BytesIO();Image.fromarray(array).save(b,format='PNG',compress_level=9)
        payloads.append((f['asset'],b.getvalue(),array))
    output.mkdir(parents=True)
    for asset,data,array in payloads:
        (output/(asset+'-derived.png')).write_bytes(data)
    execution=dict(status='success',method=METHOD,recipe_sha256=digest(rb),tool_sha256=digest(Path(__file__).read_bytes()),
        source_sha256={f['asset']:f['source']['sha256']for f in recipe['frames']},
        parent_raw_sha256=sorted({f['raw_png']['sha256']for f in recipe['frames']}),
        output_sha256={asset:digest(data)for asset,data,_ in payloads})
    report['execution']=execution
    report['outputs']=[dict(asset=asset,file=asset+'-derived.png',sha256=digest(data),RGBA_sha256=digest(array.tobytes()),bytes=len(data))for asset,data,array in payloads]
    (output/'normalized-execution.json').write_text(json.dumps(execution,indent=2,sort_keys=True)+'\n')
    (output/'derived-provenance.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('recipe',type=Path);p.add_argument('output_new_directory',type=Path)
    a=p.parse_args();r=run_recipe(a.recipe,a.output_new_directory);print(json.dumps(r['execution'],sort_keys=True))

if __name__=='__main__':
    main()
