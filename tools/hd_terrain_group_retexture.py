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

METHOD='source-declared-material-regions-coherent-parent-fine-mid-logtexture-v2'
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
    if type(r) is not dict or set(r)!={'format_version','method','dependency','palette','material_groups','parameters','frames'} or type(r['format_version']) is not int or r['format_version']!=2 or r['method']!=METHOD:raise ValueError('new versioned recipe required')
    binding(r['dependency']);binding(r['palette']);groups_validated(r['material_groups'])
    frames=r['frames']
    if type(frames) is not list or not 1<=len(frames)<=64:raise ValueError('bounded nonempty frame inventory required')
    seen=[]
    for f in frames:
        required={'asset','Source','parent_raw','crop','origin'}
        if type(f) is not dict or not required<=set(f) or set(f)-required-{'material_parent_regions'}:raise ValueError('exact frame fields required')
        asset=f['asset']
        if type(asset) is not str or not re.fullmatch('(0|[1-9a-f][0-9a-f]{0,7})',asset) or int(asset,16)>0xffffffff:raise ValueError('canonical lowercase u32 hex asset required, never a path')
        seen.append(int(asset,16));binding(f['Source']);binding(f['parent_raw'])
        if type(f['origin']) is not list or len(f['origin'])!=2 or any(type(v) is not int or v!=0 for v in f['origin']):raise ValueError('literal zero origin required')
        crop=f['crop']
        if type(crop) is not list or len(crop)!=4 or any(type(v) is not int for v in crop) or min(crop[:2])<0 or min(crop[2:])<=0:raise ValueError('exact positive integer crop required')
        validate_regions(f.get('material_parent_regions',{}),crop,r['material_groups'])
    if len(set(seen))!=len(seen) or seen!=sorted(seen):raise ValueError('unique numeric asset order required')
    validate_parameters(r['parameters'],(1,1))
    if len(frames)*r['parameters']['output_side']**2>16_777_216:raise ValueError('prepared output pixel budget exceeded')

def validate_donor(donor,crop):
    if type(donor) is not list or len(donor)!=4 or any(type(v) is not int for v in donor) or min(donor[2:])<=0:
        raise ValueError('donor must be four literal integers with positive dimensions')
    x,y,w,h=donor;fx,fy,fw,fh=crop
    if not (fx<x and fy<y and x+w<fx+fw and y+h<fy+fh):
        raise ValueError('donor must lie strictly inside its authenticated frame crop')

def validate_regions(regions,crop,groups):
    if type(regions) is not dict:raise ValueError('material_parent_regions must be an object')
    names={g['name'] for g in groups}
    if any(type(name) is not str or name not in names for name in regions):raise ValueError('region key must name a declared group')
    for donor in regions.values():validate_donor(donor,crop)

def reflect_axis(coordinates,length):
    if type(length) is not int or length<=0:raise ValueError('positive reflection length required')
    a=np.asarray(coordinates)
    if a.dtype.kind not in 'iu':raise ValueError('integer reflection coordinates required')
    if length==1:return np.zeros(a.shape,np.int64)
    phase=np.mod(a,2*(length-1))
    return np.where(phase<length,phase,2*(length-1)-phase).astype(np.int64)

def reflect_parent_region(parent,crop,donor):
    """Exact raw-density reflection, anchored at the donor's original offset.

    No resize precedes the full-frame field. In the donor's original rectangle
    the field is byte-identical to raw RGB; outside it, reflect without repeating
    edge samples. Final output resizing happens only in reconstruct().
    """
    parent=np.asarray(parent)
    if parent.ndim!=3 or parent.shape[2]!=3 or parent.dtype!=np.uint8:raise ValueError('raw parent RGB uint8 required')
    if type(crop) is not list or len(crop)!=4 or any(type(v) is not int for v in crop):raise ValueError('integer frame crop required')
    fx,fy,fw,fh=crop
    if min(fx,fy)<0 or min(fw,fh)<=0 or fx+fw>parent.shape[1] or fy+fh>parent.shape[0]:raise ValueError('frame crop outside parent')
    validate_donor(donor,crop);x,y,w,h=donor
    xs=x+reflect_axis(np.arange(fw,dtype=np.int64)+fx-x,w)
    ys=y+reflect_axis(np.arange(fh,dtype=np.int64)+fy-y,h)
    field=parent[ys[:,None],xs[None,:],:].copy()
    original=parent[y:y+h,x:x+w]
    if not np.array_equal(field[y-fy:y-fy+h,x-fx:x-fx+w],original):raise AssertionError('native donor samples moved')
    return field,dict(parent_crop=crop,raw_donor=donor,original_donor_offset=[x-fx,y-fy],native_reflected_field_dimensions=[fw,fh],
        donor_RGB_sha256=digest(original.tobytes()),reflected_native_field_RGB_sha256=digest(field.tobytes()),
        donor_original_position_samples_exact=True,reflection='original-offset reflect101, no edge repetition; length1 repeats sole sample',
        resampling_before_native_frame_field=False)

def reconstruct(indices,palette,generated_rgb,parameters,groups,kernel,material_parent_fields=None):
    a=np.asarray(indices);palette=np.asarray(palette);raw=np.asarray(generated_rgb)
    if a.ndim!=2 or a.shape[0]!=a.shape[1] or not a.size or a.dtype.kind not in 'iu' or np.any(a<0) or np.any(a>=240):raise ValueError('square opaque ordinary integer Source required')
    if palette.shape!=(256,3) or palette.dtype!=np.uint8:raise ValueError('exact RGB uint8 palette required')
    if raw.ndim!=3 or raw.shape[2]!=3 or raw.dtype!=np.uint8 or not raw.size:raise ValueError('generated RGB uint8 required')
    validate_parameters(parameters,a.shape);groups_validated(groups,np.unique(a));p=parameters
    fields={} if material_parent_fields is None else material_parent_fields
    if type(fields) is not dict or set(fields)-{g['name'] for g in groups}:raise ValueError('texture fields require declared group keys')
    for field in fields.values():
        if not isinstance(field,np.ndarray) or field.dtype!=np.uint8 or field.shape!=raw.shape:raise ValueError('native material field must match the full raw frame crop shape/density')
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
    if not fields and float(band.std())<.25:raise ValueError('parent lacks coherent fine/mid generated detail; Source-only fallback forbidden')
    texture=np.zeros_like(band);normalizers={};band_stds={}
    for i in np.unique(owners):
        name=groups[int(i)]['name'];group_band=band
        if name in fields:
            material_parent=np.asarray(Image.fromarray(fields[name]).resize((side,side),Image.Resampling.LANCZOS),float)
            material_luma=material_parent@np.array([.2126,.7152,.0722])
            group_band=kernel.gaussian(material_luma,p['residual_sigma_fine'])-kernel.gaussian(material_luma,p['residual_sigma_coarse'])
        band_stds[name]=float(group_band.std())
        if band_stds[name]<.25:raise ValueError('parent lacks coherent fine/mid generated detail for group '+name)
        area=owners==i;centered=group_band-group_band[area].mean();divisor=max(float(np.percentile(np.abs(centered[area]),p['residual_percentile'])),1.)
        texture[area]=np.tanh(centered[area]/divisor);normalizers[groups[int(i)]['name']]=divisor
    strengths=np.array([g['texture_log_gain'] for g in groups])[owners]*quiet;gain=np.exp(strengths*texture)
    output=np.clip(np.rint(base*gain[...,None]),0,255).astype(np.uint8);base8=np.clip(np.rint(base),0,255).astype(np.uint8)
    changed=int(np.any(output!=base8,axis=2).sum())
    if changed<max(1,math.ceil(side*side*.01)):raise ValueError('generated modulation too small; no Source-only output')
    metrics=dict(method=METHOD,source_shape=list(a.shape),sourceNx4_indices_sha256=digest(guide_indices.astype('<u2').tobytes()),
        material_labels_sha256=digest(owners.astype('<i2').tobytes()),group_output_pixels={groups[int(i)]['name']:int((owners==i).sum()) for i in np.unique(owners)},
        used_Source_indices_by_group={g['name']:sorted(set(g['indices'])&set(map(int,np.unique(a)))) for g in groups},coherent_parent_band_std=float(band.std()),
        per_group_normalizers=normalizers,per_group_parent_band_std=band_stds,material_parent_field_names=sorted(fields),actual_tone_gain_min=float(gain.min()),actual_tone_gain_max=float(gain.max()),pixels_changed_from_Source_guided_base=changed,
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
        parent_rgb=np.asarray(im.convert('RGB'));raw=parent_rgb[y:y+h,x:x+w].copy();fields={};region_proofs={}
        for name,donor in f.get('material_parent_regions',{}).items():
            fields[name],region_proofs[name]=reflect_parent_region(parent_rgb,f['crop'],donor)
        derived,_,_,metrics=reconstruct(indices,palette,raw,r['parameters'],r['material_groups'],kernel,fields)
        metrics['material_parent_region_proofs']=region_proofs
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
