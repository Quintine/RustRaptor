"""Source-guided DERIVED hatch reconstruction with generated continuous RGB.

Source supplies alpha, cover/core geometry and broad material/exposure statistics.
Generated RGB supplies continuous mechanism form, warning/contact detail and real
soil mid/fine structure. No random texture or per-cell Source RGB copying occurs.
Every input is SHA-bound; every output is new and explicitly derived.
"""
from pathlib import Path
from collections import deque
import argparse, hashlib, io, json, platform, re, sys
import numpy as np
import PIL
from PIL import Image, ImageFilter
from hd_frame_policy import _indices

METHOD = 'derived-continuous-generated-hatch-Source-broad-tone-phase-rebuild-v1'

def sha(body): return hashlib.sha256(body).hexdigest()

def checked(ref, base):
    if type(ref) is not dict or set(ref) != {'path', 'sha256'}:
        raise ValueError('input requires exactly path/sha256')
    p = Path(ref['path']); p = p if p.is_absolute() else base/p
    if p.is_symlink() or not p.is_file(): raise ValueError('regular nonsymlink input required')
    b = p.read_bytes()
    if sha(b) != ref['sha256']: raise ValueError('input SHA mismatch')
    return b

def box(mask):
    y,x = np.nonzero(mask)
    if not len(x): raise ValueError('empty required region')
    return [int(x.min()), int(y.min()), int(x.max()+1), int(y.max()+1)]

def main_painted_bounds(rgba):
    """Largest alpha>=128 four-connected component; disconnected fringe excluded."""
    mask = rgba[:,:,3] >= 128
    seen = np.zeros(mask.shape, bool); h,w = mask.shape; best=[]
    for sy,sx in zip(*np.nonzero(mask)):
        if seen[sy,sx]: continue
        todo=deque([(int(sy),int(sx))]); seen[sy,sx]=True; comp=[]
        while todo:
            y,x=todo.popleft(); comp.append((y,x))
            for yy,xx in ((y-1,x),(y,x-1),(y,x+1),(y+1,x)):
                if 0<=yy<h and 0<=xx<w and mask[yy,xx] and not seen[yy,xx]:
                    seen[yy,xx]=True; todo.append((yy,xx))
        if len(comp)>len(best): best=comp
    if len(best)<16: raise ValueError('no substantial painted component')
    ys,xs=np.array(best).T
    return [int(xs.min()),int(ys.min()),int(xs.max()+1),int(ys.max()+1)]

def resize_rgb(a, size):
    return np.asarray(Image.fromarray(np.clip(a,0,255).astype('uint8'), 'RGB').resize(size, Image.Resampling.LANCZOS)).astype(float)

def blur(a, radius):
    return np.asarray(Image.fromarray(np.clip(a,0,255).astype('uint8'), 'RGB').filter(ImageFilter.GaussianBlur(radius))).astype(float)

def broad_soil(generated, source_rgb, source_mask, scale):
    """Source mean/broad modulation + correlated generated low/mid/fine detail.

    Radius4 logical cells explicitly removes Source pixel-grid colour changes.
    The generated residuals are deterministic RGB texture, never random noise.
    """
    if not source_mask.any(): raise ValueError('no authentic soil palette samples')
    mean=source_rgb[source_mask].mean(0)
    filled=np.broadcast_to(mean, source_rgb.shape).copy(); filled[source_mask]=source_rgb[source_mask]
    source_low=resize_rgb(blur(filled,4), (generated.shape[1],generated.shape[0]))
    gen_small=blur(generated, max(1,scale*.35)); gen_large=blur(generated, scale*3)
    low=gen_large-gen_large.mean((0,1)); mid=gen_small-gen_large; fine=generated-gen_small
    return np.clip(mean + .30*(source_low-mean) + .18*low + .38*mid + .48*fine,0,255)

def warning_rows(source):
    return np.flatnonzero(((source>=75)&(source<=95)).sum(1) >= max(4,source.shape[1]//6))

def core_donor_mask(image, core_bounds, scale):
    """Only the center neighbourhood can donate core RGB, never warm rim soil."""
    warm=(image[:,:,0]>image[:,:,1]*1.1)&(image[:,:,1]>image[:,:,2]*1.8)&(image[:,:,0]>35)
    b=core_bounds; region=np.zeros(warm.shape,bool)
    region[max(0,(b[1]-3)*scale):min(image.shape[0],(b[3]+3)*scale),
           max(0,(b[0]-3)*scale):min(image.shape[1],(b[2]+3)*scale)]=True
    return warm&region

def map_parent(rgba, source, scale):
    b=main_painted_bounds(rgba); sb=box(source<256)
    out=np.zeros((source.shape[0]*scale,source.shape[1]*scale,3),float)
    out[sb[1]*scale:sb[3]*scale,sb[0]*scale:sb[2]*scale]=resize_rgb(rgba[b[1]:b[3],b[0]:b[2],:3],((sb[2]-sb[0])*scale,(sb[3]-sb[1])*scale))
    return out,b,sb

def validate_recipe(recipe):
    keys={'format_version','method','output_scale','palette','raw_png','layout','frames','soil_donor_frame','closed_donor_frame','module_donor_frame','warning_donor_frame'}
    if type(recipe) is not dict or set(recipe)!=keys or type(recipe['format_version']) is not int or recipe['format_version']!=1 or recipe['method']!=METHOD:
        raise ValueError('unknown recipe format/method')
    s=recipe['output_scale']
    if type(s) is not int or not 4<=s<=16: raise ValueError('scale must be integer4..16')
    layout=recipe['layout']
    if type(layout) is not dict or set(layout)!={'columns','rows'} or any(type(v) is not int or v<=0 for v in layout.values()):
        raise ValueError('invalid layout')
    frames=recipe['frames']
    if not isinstance(frames,list) or not 2<=len(frames)<=32 or len(frames)!=layout['columns']*layout['rows']:
        raise ValueError('complete exact slot inventory required')
    assets=[];source_paths=[]
    for f in frames:
        if type(f) is not dict or set(f)!={'asset','source','origin'}: raise ValueError('frame fields invalid')
        asset=f['asset']
        if type(asset) is not str or not re.fullmatch(r'(?:0|[1-9a-f][0-9a-f]{0,7})',asset) or int(asset,16)>0xffffffff:
            raise ValueError('asset must be a canonical lowercase u32 hex ID, never a path')
        assets.append(int(asset,16))
        origin=f['origin']
        if type(origin) is not list or len(origin)!=2 or any(type(v) is not int or v!=0 for v in origin):
            raise ValueError('origin must contain two literal integer zeros')
        source=f['source']
        if type(source) is not dict or set(source)!={'path','sha256'} or type(source['path']) is not str or not source['path']:
            raise ValueError('Source needs literal path/sha256')
        source_paths.append(Path(source['path']))
    if len(set(assets))!=len(assets): raise ValueError('duplicate asset')
    if assets!=list(range(assets[0],assets[0]+len(assets))): raise ValueError('asset IDs must follow complete contiguous numeric Source order')
    base=str(source_paths[0])
    if source_paths!=[Path(base+('.'+str(i) if i else '')) for i in range(len(frames))]:
        raise ValueError('Source picture paths must follow base,base.1,... family order')
    for name in ('soil_donor_frame','closed_donor_frame','module_donor_frame','warning_donor_frame'):
        if type(recipe[name]) is not int or not 0<=recipe[name]<len(frames): raise ValueError('bad donor frame')

def render(recipe, base):
    validate_recipe(recipe); scale=recipe['output_scale']
    pb=checked(recipe['palette'],base)
    if len(pb)!=768: raise ValueError('exact VGA palette required')
    p=np.minimum(np.frombuffer(pb,dtype='uint8').astype('uint16'),63)
    palette=((p<<2)|(p>>4)).astype('uint8').reshape(256,3)
    raw=Image.open(io.BytesIO(checked(recipe['raw_png'],base)))
    if raw.format!='PNG' or raw.width*raw.height>8_000_000: raise ValueError('bounded PNG required')
    rgba=np.asarray(raw.convert('RGBA')); cols=recipe['layout']['columns']; rows=recipe['layout']['rows']
    sources=[]; mapped=[]; transforms=[]
    for i,f in enumerate(recipe['frames']):
        w,h,c=_indices(checked(f['source'],base)); src=np.asarray(c,dtype='uint16').reshape(h,w)
        if (w,h)!=(32,32): raise ValueError('this method requires authentic32x32 hatch canvases')
        if np.any((src<256)&~(((src>=194)&(src<=239))|(src<32)|((src>=75)&(src<=95)))):
            raise ValueError('unsupported Source materials')
        c0=i%cols; r0=i//cols; x0=c0*raw.width//cols; x1=(c0+1)*raw.width//cols; y0=r0*raw.height//rows; y1=(r0+1)*raw.height//rows
        m,b,sb=map_parent(rgba[y0:y1,x0:x1],src,scale)
        sources.append(src); mapped.append(m)
        transforms.append(dict(asset=f['asset'],declared_raw_slot=[x0,y0,x1,y1],own_painted_bounds=[b[0]+x0,b[1]+y0,b[2]+x0,b[3]+y0],Source_painted_bounds=sb,
                               nonuniform_scale_xy=[(sb[2]-sb[0])*scale/(b[2]-b[0]),(sb[3]-sb[1])*scale/(b[3]-b[1])]))
    source=np.stack(sources); h,w=source.shape[1:]
    if not np.all(source[0]<256): raise ValueError('first frame must be a full opaque soil tile')
    static=np.all(source[1:]==source[1],axis=0)&(source[1]<256)
    # Broad phase statistics below exclude the moving support teeth and border.
    yy,xx=np.indices((h,w))
    module=mapped[recipe['module_donor_frame']].copy()
    # Remove the donor's luminous center before inserting each authentic phase's
    # own core. The surrounding generated dark well supplies the replacement;
    # otherwise the donor core would leak around a smaller/dimmer Source core.
    donor_source=source[recipe['module_donor_frame']]
    donor_core=(donor_source>=75)&(donor_source<=95)
    for row in warning_rows(donor_source): donor_core[row]=False
    if not donor_core.any(): raise ValueError('module donor needs authentic core')
    donor_warm=core_donor_mask(module,box(donor_core),scale)
    if donor_warm.any():
        db=box(donor_warm); near=np.zeros(donor_warm.shape,bool)
        near[max(0,db[1]-scale):db[3]+scale,max(0,db[0]-scale):db[2]+scale]=True
        dark=near&(module.max(2)<30)&~donor_warm
        if not dark.any(): raise ValueError('no generated dark-well donor')
        module[donor_warm]=np.median(module[dark],axis=0)
    reference_roi=(xx>=7)&(xx<26)&(yy>=6)&(yy<28)&(source[-1]<32)
    big_ref=np.repeat(np.repeat(reference_roi,scale,0),scale,1)
    donor_p90=max(1,float(np.percentile(module[big_ref].mean(1),90)))
    soil_donor=mapped[recipe['soil_donor_frame']]
    soil0=broad_soil(soil_donor,palette[np.minimum(source[0],255)],(source[0]>=194)&(source[0]<=239),scale)
    closed=mapped[recipe['closed_donor_frame']]
    quiet=broad_soil(closed,palette[np.minimum(source[1],255)],(source[1]>=194)&(source[1]<=239),scale)
    # Shared rim keeps the generated continuous edge texture but matches one
    # family-wide authentic brown mean; its pixels never vary across phases.
    border_source=palette[source[1][static]].mean(0)
    border_pixels=closed[np.repeat(np.repeat(static,scale,0),scale,1)]
    border_ratio=np.clip(border_source/np.maximum(1,border_pixels.mean(0)),.25,1.5)
    common_border=closed*border_ratio
    # Reuse one complete generated warning/contact assembly. Moving the entire
    # strip avoids Source-pixel brick reconstruction and phase-to-phase drift.
    warning_image=mapped[recipe['warning_donor_frame']]
    rr,gg,bb=warning_image[:,:,0],warning_image[:,:,1],warning_image[:,:,2]
    warm=(rr>gg*1.1)&(gg>bb*1.8)&(gg>45)&(rr>80)
    found=np.flatnonzero(warm.sum(1)>scale*8)
    if not len(found): raise ValueError('generated warning assembly missing')
    wy0,wy1=int(found.min()),int(found.max()+1)
    warning_strip=resize_rgb(warning_image[wy0:wy1,4*scale:27*scale],(23*scale,scale))
    contact_strip=resize_rgb(warning_image[wy1:min(warning_image.shape[0],wy1+3*scale),4*scale:27*scale],(23*scale,2*scale))
    outputs=[]; metrics=[]
    for i,src in enumerate(sources):
        if i==0:
            rgb=soil0.copy(); gain=0.; warn=None; core_bounds=None
        else:
            warnrows=warning_rows(src); warn=int(warnrows[0]) if len(warnrows) else None
            start=max(6,warn+4) if warn is not None else 6
            roi=(xx>=7)&(xx<26)&(yy>=start)&(yy<28)&(src<32)
            values=palette[src[roi]].mean(1)
            target_p90=float(np.percentile(values,90)) if len(values) else 4.
            gain=float(np.clip(target_p90/donor_p90,0,1.6))
            rgb=np.clip(module*gain,0,255)
            end=warn if warn is not None else (28 if i in (1,2) else 5)
            if end>5:
                # A single generated soil cover translates upward, exposing the
                # shared fixed mechanism rather than a new render in each slot.
                offset=(28-end)*scale
                rgb[5*scale:end*scale,4*scale:27*scale]=quiet[5*scale+offset:28*scale,4*scale:27*scale]
                if i>=2:
                    topmean=palette[src[5,4:27]].mean(0); soilmean=palette[src[(src>=194)&(src<=239)]].mean(0)
                    ratio=np.clip(topmean/np.maximum(1,soilmean),.35,1.3)
                    rgb[5*scale:6*scale,4*scale:27*scale]*=ratio
            if warn is not None:
                strip=warning_strip.copy()
                actual_values=palette[src[warn][(src[warn]>=75)&(src[warn]<=95)]]
                target=actual_values.mean(0)
                donor=strip[(strip[:,:,0]>strip[:,:,1]*1.1)&(strip[:,:,1]>strip[:,:,2]*1.8)]
                if not len(donor): raise ValueError('empty warning color')
                ratio=np.clip(target/np.maximum(1,donor.mean(0)),.1,2)
                strip=np.clip(strip*ratio,0,255)
                rgb[warn*scale:(warn+1)*scale,4*scale:27*scale]=strip
                rgb[(warn+1)*scale:(warn+3)*scale,4*scale:27*scale]=contact_strip
            core=((src>=75)&(src<=95))
            if warn is not None: core[warn]=False
            core_bounds=None
            if core.any():
                cb=box(core); core_bounds=cb
                own=mapped[i]; wr=core_donor_mask(own,cb,scale)
                wr[:(warn+3)*scale if warn is not None else 7*scale]=False
                if not wr.any(): raise ValueError('generated own-phase core missing')
                ob=box(wr); patch=resize_rgb(own[ob[1]:ob[3],ob[0]:ob[2]],((cb[2]-cb[0])*scale,(cb[3]-cb[1])*scale))
                target=palette[src[core]].mean(0); patch*=target/np.maximum(1,patch.mean((0,1)))
                rgb[cb[1]*scale:cb[3]*scale,cb[0]*scale:cb[2]*scale]=np.clip(patch,0,255)
            bigstatic=np.repeat(np.repeat(static,scale,0),scale,1)
            rgb[bigstatic]=common_border[bigstatic]
        alpha=np.repeat(np.repeat(src<256,scale,0),scale,1)
        out=np.zeros((h*scale,w*scale,4),dtype='uint8');out[alpha,:3]=np.rint(np.clip(rgb[alpha],0,255)).astype('uint8');out[alpha,3]=255
        outputs.append(out)
        metrics.append(dict(asset=recipe['frames'][i]['asset'],Source_alpha_exact=True,warning_Source_y=warn,body_broad_exposure_gain=gain,Source_core_bounds=core_bounds,
                            meaningful_generated_content='continuous module RGB, complete generated warning/contact assembly, own-phase core texture, correlated generated soil mid/fine details',
                            RGB_not_untouched='interpolation, broad material color correction and phase gain are intentional derived edits'))
    shared=np.repeat(np.repeat(static,scale,0),scale,1)
    assert all(np.array_equal(o[shared],outputs[1][shared]) for o in outputs[2:])
    return outputs,dict(method=METHOD,transforms=transforms,frames=metrics,static_Source_cells=int(static.sum()),
                        reference_shape=[w,h],output_scale=scale,Source_RGB_nearest_or_random_noise=False,
                        broad_Source_radius_logical_cells=4,shared_module_donor_frame=recipe['module_donor_frame'])

def run(recipe_path,output):
    recipe_path=Path(recipe_path);output=Path(output)
    if output.exists(): raise ValueError('output exists; no overwrite')
    body=recipe_path.read_bytes(); recipe=json.loads(body); arrays,result=render(recipe,recipe_path.parent)
    payloads={}
    for f,a in zip(recipe['frames'],arrays):
        stream=io.BytesIO();Image.fromarray(a,'RGBA').save(stream,format='PNG',compress_level=9);payloads[f['asset']]=stream.getvalue()
    output.mkdir(parents=True)
    for asset,b in payloads.items(): (output/(asset+'-derived.png')).write_bytes(b)
    result['execution']=dict(status='success',method=METHOD,recipe_sha256=sha(body),tool_sha256=sha(Path(__file__).read_bytes()),
                            source_sha256={f['asset']:f['source']['sha256'] for f in recipe['frames']},
                            parent_raw_sha256=sorted({recipe['raw_png']['sha256']}),output_sha256={k:sha(v) for k,v in payloads.items()})
    decoder=Path(sys.modules[_indices.__module__].__file__).resolve()
    result['implementation_bindings']=dict(
        decoder=dict(path=str(decoder),sha256=sha(decoder.read_bytes())),
        runtime=dict(python=platform.python_version(),numpy=np.__version__,pillow=PIL.__version__,executable=sys.executable),
        pixel_math_parent_tool_sha256='2ba29bea099d30105f61541504ba882712bda42be2d1c363e668226035bc23d2',
        successor_scope='input validation and receipt metadata only; rendering math unchanged')
    (output/'execution-and-derived-provenance.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('recipe',type=Path);parser.add_argument('new_output',type=Path)
    args=parser.parse_args();print(json.dumps(run(args.recipe,args.new_output)))
