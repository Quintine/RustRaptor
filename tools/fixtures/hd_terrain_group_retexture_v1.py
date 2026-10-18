"""PRIVATE new recipe: explicit Source palette groups + coherent generated detail.

Never imports a moving dependency or patches legacy material_families. The exact
reviewed 0e4d source is loaded from checked bytes, and only its audited reader,
decoder, palette, ScaleNx and filtering primitives are reused. Old recipes keep
their own entrypoint and behaviour. No engine/registration/World operations.
"""
from __future__ import annotations
from pathlib import Path
import argparse, ctypes, errno, hashlib, io, json, math, os, re, shutil, stat, sys, tempfile, types
import numpy as np
import PIL
from PIL import Image

METHOD='source-declared-material-groups-coherent-parent-fine-mid-logtexture-v1'
DEPENDENCY_SHA256='0e4d7d5a4f7a7ddf6e396e757691156dfc74d231d9925744c342078532b89a98'
PARAMETERS={'output_side','source_sigma','residual_sigma_fine','residual_sigma_coarse','residual_percentile'}

def digest(b): return hashlib.sha256(b).hexdigest()

def binding(value):
    if type(value) is not dict or set(value)!={'path','sha256'} or type(value['path']) is not str or not value['path'] or type(value['sha256']) is not str or not re.fullmatch('[0-9a-f]{64}',value['sha256']):
        raise ValueError('input needs exactly nonempty path and lowercase SHA256')
    return value

def load_dependency(ref,base):
    binding(ref)
    if ref['sha256']!=DEPENDENCY_SHA256: raise ValueError('only exact reviewed0e4d dependency is allowed')
    p=Path(ref['path']);p=p if p.is_absolute() else base/p
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        a=os.fstat(fd)
        if not stat.S_ISREG(a.st_mode) or a.st_size>100_000: raise ValueError('bounded regular dependency required')
        with os.fdopen(fd,'rb',closefd=False) as stream:body=stream.read()
        b=os.fstat(fd)
        if (a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns)!=(b.st_dev,b.st_ino,b.st_size,b.st_mtime_ns):raise ValueError('dependency changed during read')
    finally:os.close(fd)
    if digest(body)!=DEPENDENCY_SHA256:raise ValueError('dependency hash mismatch')
    module=types.ModuleType('private_exact_0e4d_terrain_primitives');module.__file__=str(p.absolute())
    exec(compile(body,str(p),'exec'),module.__dict__)
    _,pin=module.read_regular(p)
    if pin['sha256']!=DEPENDENCY_SHA256:raise ValueError('dependency changed after load')
    return module,pin

def groups_validated(groups,used=None):
    if type(groups) is not list or not 1<=len(groups)<=32:raise ValueError('material_groups must contain1..32 explicit groups')
    names=set();members=set()
    for group in groups:
        if type(group) is not dict or set(group)!={'name','indices','texture_log_gain','quiet_from_source_variance'}:raise ValueError('exact group fields required')
        name=group['name']
        if type(name) is not str or not re.fullmatch('[a-z][a-z0-9_]{0,31}',name) or name in names:raise ValueError('unique slug material names required')
        names.add(name);indices=group['indices']
        if type(indices) is not list or not indices or any(type(i) is not int or not 0<=i<240 for i in indices):raise ValueError('group indices must be literal ordinary0..239 integers')
        if indices!=sorted(set(indices)):raise ValueError('group index sets must be sorted unique')
        if members.intersection(indices):raise ValueError('material index sets overlap')
        members.update(indices);gain=group['texture_log_gain']
        if type(gain) not in (int,float) or not math.isfinite(gain) or not 0<=gain<=.7:raise ValueError('bounded finite texture gain required')
        if type(group['quiet_from_source_variance']) is not bool:raise ValueError('quiet control must be boolean')
    if used is not None and not set(map(int,used))<=members:raise ValueError('used Source indices not completely covered by declared groups')
    return groups

def validate_parameters(p,shape):
    if type(p) is not dict or set(p)!=PARAMETERS:raise ValueError('exact reconstruction parameters required')
    side=p['output_side']
    if type(side) is not int or not 4*max(shape)<=side<=1024 or side%(4*max(shape)):raise ValueError('output side must be bounded integer expansion of SourceNx4')
    for key in ('source_sigma','residual_sigma_fine','residual_sigma_coarse'):
        v=p[key]
        if type(v) not in (int,float) or not math.isfinite(v) or not 0<v<=16:raise ValueError('invalid positive finite sigma')
    if p['residual_sigma_fine']>=p['residual_sigma_coarse']:raise ValueError('fine band must be narrower than coarse')
    v=p['residual_percentile']
    if type(v) not in (int,float) or not math.isfinite(v) or not 50<=v<=100:raise ValueError('invalid percentile')

def validate_recipe(r):
    if type(r) is not dict or set(r)!={'format_version','method','dependency','palette','material_groups','parameters','frames'} or type(r['format_version']) is not int or r['format_version']!=1 or r['method']!=METHOD:raise ValueError('new versioned recipe required')
    binding(r['dependency']);binding(r['palette']);groups_validated(r['material_groups'])
    frames=r['frames']
    if type(frames) is not list or not 1<=len(frames)<=64:raise ValueError('bounded nonempty frame inventory required')
    seen=[]
    for f in frames:
        if type(f) is not dict or set(f)!={'asset','Source','parent_raw','crop','origin'}:raise ValueError('exact frame fields required')
        asset=f['asset']
        if type(asset) is not str or not re.fullmatch('(0|[1-9a-f][0-9a-f]{0,7})',asset) or int(asset,16)>0xffffffff:raise ValueError('canonical lowercase u32 hex asset required, never a path')
        seen.append(int(asset,16));binding(f['Source']);binding(f['parent_raw'])
        if type(f['origin']) is not list or len(f['origin'])!=2 or any(type(v) is not int or v!=0 for v in f['origin']):raise ValueError('literal zero origin required')
        crop=f['crop']
        if type(crop) is not list or len(crop)!=4 or any(type(v) is not int for v in crop) or min(crop[:2])<0 or min(crop[2:])<=0:raise ValueError('exact positive integer crop required')
    if len(set(seen))!=len(seen) or seen!=sorted(seen):raise ValueError('unique numeric asset order required')
    validate_parameters(r['parameters'],(1,1))
    if len(frames)*r['parameters']['output_side']**2>16_777_216:raise ValueError('prepared output pixel budget exceeded')

def reconstruct(indices,palette,generated_rgb,parameters,groups,kernel):
    a=np.asarray(indices);palette=np.asarray(palette);raw=np.asarray(generated_rgb)
    if a.ndim!=2 or a.shape[0]!=a.shape[1] or not a.size or a.dtype.kind not in 'iu' or np.any(a<0) or np.any(a>=240):raise ValueError('square opaque ordinary integer Source required')
    if palette.shape!=(256,3) or palette.dtype!=np.uint8:raise ValueError('exact RGB uint8 palette required')
    if raw.ndim!=3 or raw.shape[2]!=3 or raw.dtype!=np.uint8 or not raw.size:raise ValueError('generated RGB uint8 required')
    validate_parameters(parameters,a.shape);groups_validated(groups,np.unique(a));p=parameters
    guide_indices=kernel.scale_nx(a,4)
    lookup=np.full(240,-1,np.int16)
    for i,g in enumerate(groups):lookup[g['indices']]=i
    labels=lookup[guide_indices];guide=palette[guide_indices].astype(float);side=p['output_side'];factor=side//labels.shape[0]
    owners=np.repeat(np.repeat(labels,factor,0),factor,1);base=np.zeros((side,side,3),float);quiet=np.ones((side,side),float)
    guide_luma=guide@np.array([.2126,.7152,.0722])
    for i in np.unique(labels):
        mask=(labels==i).astype(float)
        weights=kernel.resize_float(kernel.gaussian(mask,p['source_sigma']),(side,side))
        numerator=kernel.resize_float(kernel.gaussian(guide*mask[...,None],p['source_sigma']),(side,side))
        field=numerator/np.maximum(weights[...,None],1e-12);area=owners==i;base[area]=field[area]
        if groups[int(i)]['quiet_from_source_variance']:
            second=kernel.resize_float(kernel.gaussian(guide_luma**2*mask,p['source_sigma']),(side,side))/np.maximum(weights,1e-12)
            first=field@np.array([.2126,.7152,.0722]);std=np.sqrt(np.maximum(second-first**2,0))
            quiet[area]=(.35+.65*np.clip(std/8.,0,1))[area]
    parent=np.asarray(Image.fromarray(raw).resize((side,side),Image.Resampling.LANCZOS),float)
    luma=parent@np.array([.2126,.7152,.0722]);band=kernel.gaussian(luma,p['residual_sigma_fine'])-kernel.gaussian(luma,p['residual_sigma_coarse'])
    if float(band.std())<.25:raise ValueError('parent lacks coherent fine/mid generated detail; Source-only fallback forbidden')
    texture=np.zeros_like(band);normalizers={}
    for i in np.unique(owners):
        area=owners==i;centered=band-band[area].mean();divisor=max(float(np.percentile(np.abs(centered[area]),p['residual_percentile'])),1.)
        texture[area]=np.tanh(centered[area]/divisor);normalizers[groups[int(i)]['name']]=divisor
    strengths=np.array([g['texture_log_gain'] for g in groups])[owners]*quiet;gain=np.exp(strengths*texture)
    output=np.clip(np.rint(base*gain[...,None]),0,255).astype(np.uint8);base8=np.clip(np.rint(base),0,255).astype(np.uint8)
    changed=int(np.any(output!=base8,axis=2).sum())
    if changed<max(1,math.ceil(side*side*.01)):raise ValueError('generated modulation too small; no Source-only output')
    metrics=dict(method=METHOD,source_shape=list(a.shape),sourceNx4_indices_sha256=digest(guide_indices.astype('<u2').tobytes()),
        material_labels_sha256=digest(owners.astype('<i2').tobytes()),group_output_pixels={groups[int(i)]['name']:int((owners==i).sum()) for i in np.unique(owners)},
        used_Source_indices_by_group={g['name']:sorted(set(g['indices'])&set(map(int,np.unique(a)))) for g in groups},coherent_parent_band_std=float(band.std()),
        per_group_normalizers=normalizers,actual_tone_gain_min=float(gain.min()),actual_tone_gain_max=float(gain.max()),pixels_changed_from_Source_guided_base=changed,
        mean_absolute_parent_tone_modulation=float(np.abs(output.astype(float)-base8).mean()),output_RGB_sha256=digest(output.tobytes()),
        limits='Explicit Source palette groups/SourceNx geometry and broad masked RGB; coherent actual generated fine+mid luminance retained multiplicatively. No random noise/SourceNN fallback, material/context approval or reserved semantics.')
    return output,base8,owners,metrics

def publish_no_replace(stage,target):
    """Atomic fresh-directory publication; unsupported platforms fail closed."""
    if os.name=='nt':os.rename(stage,target);return
    if not sys.platform.startswith('linux'):raise OSError(errno.ENOTSUP,'atomic no-replace publication unsupported')
    libc=ctypes.CDLL(None,use_errno=True)
    if not hasattr(libc,'renameat2'):raise OSError(errno.ENOTSUP,'renameat2 unavailable')
    fn=libc.renameat2;fn.argtypes=[ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint];fn.restype=ctypes.c_int
    if fn(-100,os.fsencode(stage),-100,os.fsencode(target),1)!=0:
        code=ctypes.get_errno();raise OSError(code,os.strerror(code),str(target))

def run(recipe_path,output):
    recipe_path=Path(recipe_path).absolute();output=Path(output).absolute()
    if output.exists() or output.is_symlink():raise ValueError('output exists; never overwrite')
    if not output.parent.is_dir():raise ValueError('output parent must already exist')
    # JSON is read with no-follow before loading the exact allowlisted primitive.
    fd=os.open(recipe_path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):raise ValueError('regular recipe required')
        with os.fdopen(fd,'rb',closefd=False) as stream:body=stream.read(1_000_001)
    finally:os.close(fd)
    if len(body)>1_000_000:raise ValueError('recipe too large')
    r=json.loads(body);validate_recipe(r);kernel,dependency_pin=load_dependency(r['dependency'],recipe_path.parent)
    _,recipe_pin=kernel.read_regular(recipe_path)
    if recipe_pin['sha256']!=digest(body):raise ValueError('recipe changed during load')
    _,tool_pin=kernel.read_regular(__file__)
    inputs=[recipe_pin,dependency_pin,tool_pin]
    def checked(ref):
        binding(ref);p=Path(ref['path']);p=p if p.is_absolute() else recipe_path.parent/p
        b,pin=kernel.read_regular(p)
        if pin['sha256']!=ref['sha256']:raise ValueError('input SHA mismatch')
        inputs.append(pin);return b,pin
    pb,palette_pin=checked(r['palette']);palette=kernel.palette_rgb(pb);prepared=[]
    for f in r['frames']:
        sb,source_pin=checked(f['Source']);indices=kernel.decode_source(sb);parent_bytes,parent_pin=checked(f['parent_raw'])
        if len(parent_bytes)>32*1024*1024:raise ValueError('parent byte ceiling exceeded')
        im=Image.open(io.BytesIO(parent_bytes))
        if im.format!='PNG' or im.width*im.height>8_000_000:raise ValueError('bounded PNG parent required')
        if im.convert('RGBA').getchannel('A').getextrema()!=(255,255):raise ValueError('opaque parent required; alpha repair forbidden')
        x,y,w,h=f['crop']
        if x+w>im.width or y+h>im.height:raise ValueError('crop outside parent')
        raw=np.asarray(im.convert('RGB').crop((x,y,x+w,y+h)));derived,_,_,metrics=reconstruct(indices,palette,raw,r['parameters'],r['material_groups'],kernel)
        stream=io.BytesIO();Image.fromarray(derived).save(stream,format='PNG');prepared.append((f,stream.getvalue(),metrics,source_pin,parent_pin))
    output_hashes={f['asset']:digest(png) for f,png,_,_,_ in prepared}
    execution=dict(status='success',method=METHOD,recipe_sha256=recipe_pin['sha256'],tool_sha256=tool_pin['sha256'],
        source_sha256={f['asset']:s['sha256'] for f,_,_,s,_ in prepared},parent_raw_sha256=sorted({p['sha256'] for _,_,_,_,p in prepared}),output_sha256=output_hashes)
    receipt=dict(status='DERIVED_OUTPUTS_NOT_MATERIAL_APPROVAL',execution=execution,recipe=recipe_pin,tool=tool_pin,dependency=dependency_pin,
        decoder=dict(name='decode_source',module_sha256=dependency_pin['sha256']),runtime=dict(python=sys.version,executable=sys.executable,numpy=np.__version__,Pillow=PIL.__version__,platform=sys.platform),
        material_groups=r['material_groups'],material_groups_sha256=digest(json.dumps(r['material_groups'],sort_keys=True,separators=(',',':')).encode()),
        frames=[dict(asset=f['asset'],Source=s,parent_raw=p,crop=f['crop'],metrics=m) for f,_,m,s,p in prepared])
    stage=Path(tempfile.mkdtemp(prefix='.'+output.name+'.stage-',dir=output.parent))
    try:
        for f,png,_,_,_ in prepared:(stage/(f['asset']+'-DERIVED-declared-material-v1.png')).write_bytes(png)
        (stage/'normalized-execution-object.json').write_text(json.dumps(dict(execution=execution),indent=2)+'\n')
        (stage/'DERIVED-LINEAGE-AND-MATERIAL-GROUP-METRICS.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
        for old in inputs:
            _,now=kernel.read_regular(old['path'])
            if now!=old:raise ValueError('input changed across reconstruction')
        publish_no_replace(stage,output)
    except BaseException:
        shutil.rmtree(stage,ignore_errors=True);raise
    return receipt

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--recipe',required=True);parser.add_argument('--output',required=True);args=parser.parse_args(argv)
    result=run(args.recipe,args.output);print(json.dumps(dict(status='success',output=str(Path(args.output).absolute()),frames=len(result['frames']),method=METHOD)))

if __name__=='__main__':main()
