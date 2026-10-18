"""Reproduce the reviewed TARGT14 soil stage with portable checked inputs.

Pixel math for frames1..13 is copied verbatim from the fixed V4 diagnostic.
Phase0 is the untouched genuine10375 PNG, not a generated substitute.
A successful reproduction never grants artistic approval or registration.
"""
from pathlib import Path, PurePosixPath
import argparse, hashlib, io, json, math, os, platform, re, shutil, stat, sys, tempfile, types
import numpy as np
import PIL
from PIL import Image
METHOD='derived-TARGT-shared-half-soil13-and-genuine10375-phase0-portable-v1'
KERNEL_SHA='0e4d7d5a4f7a7ddf6e396e757691156dfc74d231d9925744c342078532b89a98'
DECODER_SHA='66184a4758027dadbadb5e20fe90b2add2b9fc218b7810304b1a1ea2de74f58e'
DONOR_SHA='a3bfdc1b398539e133d97400940256400e295dbbf1ecbc978f202799a6916204'
PALETTE_SHA='1cf6adb926d1dee1888b3e3d33b51a7049b3e5eb5f90a3067ef71c8970547204'
ANCESTOR_RAW_SHA='207d3e613a66390a0025b3f824533d90a668c25a0808358137f7268401add9eb'
PHASE0_SHA='87a7476a06ebb210304c54e65d132cf2003ba43e4670459ca2155ed9bece945e'
PARAMETERS=dict(output_scale=8,Source_macro_sigma_logical=.5,Source_macro_sigma_output_pixels=4.,
 donor_fine_sigma_logical=.5,donor_fine_sigma_output_pixels=4.,absolute_luma_fine_gain=1.,
 Source_RGB_mean_control='additive-per-phase-group-only-no-variance-boost',
 donor_transfer='raw-fine-only-linear-Source-group-hue-no-mid-normalization-or-exp')
LUMA=np.array([.2126,.7152,.0722])
def sha(body):return hashlib.sha256(body).hexdigest()

def groups(source,soil):
    dark=soil&(source>=204)&(source<=206)
    return {'brown_field':soil&~dark,'dark_ordinary_brown':dark}

def expand(mask,scale):return np.repeat(np.repeat(mask,scale,0),scale,1)

def logical_average(rgb,scale=8):return rgb.reshape(32,scale,32,scale,3).mean((1,3))

def logical_masks(soil):
    padded=np.pad(soil,1,constant_values=False);eroded=soil.copy()
    for dy in range(3):
        for dx in range(3):eroded&=padded[dy:dy+32,dx:dx+32]
    boundary=soil&~eroded;top=np.zeros_like(soil)
    if soil.any():top[np.nonzero(soil)[0].min()]=soil[np.nonzero(soil)[0].min()]
    return boundary,eroded,top

def diagnostics(rgb,source,palette,soil):
    if not soil.any():return dict(mutable_cells=0,failures=[])
    actual=logical_average(rgb)@LUMA;original=palette[np.minimum(source,255)]@LUMA
    out=dict(mutable_cells=int(soil.sum()),Source_RGB_mean=palette[source[soil]].mean(0).tolist(),
        actual_RGB_mean=logical_average(rgb)[soil].mean(0).tolist(),
        Source_luma_std=float(original[soil].std()),actual_luma_std=float(actual[soil].std()),
        block_contrast={},edges={},failures=[])
    error=np.abs(np.array(out['actual_RGB_mean'])-out['Source_RGB_mean'])
    if np.any(error>1.):out['failures'].append('Source own-phase RGB mean exceeds1level')
    if original[soil].std()>.05:
        corr=float(np.corrcoef(original[soil],actual[soil])[0,1]) if actual[soil].std()>1e-12 else 0.;out['Source_pattern_correlation']=corr
        if not math.isfinite(corr) or corr<.90:out['failures'].append('Source own-phase pattern correlation below0.90')
    for side in [2,4,8]:
        a=[];b=[]
        for y in range(0,32,side):
            for x in range(0,32,side):
                if soil[y:y+side,x:x+side].all():
                    a.append(original[y:y+side,x:x+side].mean());b.append(actual[y:y+side,x:x+side].mean())
        target=float(np.std(a)) if a else 0.;measured=float(np.std(b)) if b else 0.;out['block_contrast'][str(side)]=dict(full_blocks=len(a),Source_std=target,actual_std=measured)
        if len(a)>=4 and target>.05 and measured<.90*target:out['failures'].append('Source coarse block contrast below90percent at'+str(side))
    boundary,interior,top=logical_masks(soil)
    for name,edge in [('all_inner_boundary',boundary),('top_inner_boundary',top)]:
        if not interior.any() or not edge.any():
            out['edges'][name]=dict(status='NOT_APPLICABLE_NO_ERODED_INTERIOR_OR_EDGE');continue
        target=float(original[edge].mean()-original[interior].mean());measured=float(actual[edge].mean()-actual[interior].mean())
        out['edges'][name]=dict(Source_minus_interior=target,actual_minus_interior=measured)
        bad=abs(measured-target)>2.
        if abs(target)>=1.:bad=bad or measured*target<=0 or abs(measured)<.90*abs(target)
        if bad:out['failures'].append('Source '+name+' tone/contrast not preserved')
    return out

def donor_bands(donor_rgb,kernel):
    donor=np.asarray(donor_rgb)
    if donor.ndim!=3 or donor.shape[2]!=3 or donor.dtype!=np.uint8:raise ValueError('donor RGB uint8 required')
    d=np.asarray(Image.fromarray(donor).resize((256,256),Image.Resampling.LANCZOS),float)@LUMA
    fine=d-kernel.gaussian(d,.5*8)
    if float(fine.std())<.25:raise ValueError('donor has no coherent generated material')
    # Absolute measured luma, not percentile-normalized/log lighting. No MID.
    return [fine],dict(fine=dict(std=float(fine.std()),mean=float(fine.mean()),absolute_luma_gain=1.,mid_used=False))

def apply_frame(accepted,source,palette,static,bands,kernel):
    if not isinstance(source,np.ndarray) or source.shape!=(32,32) or source.dtype.kind not in 'iu' or np.any(source<0) or np.any(source>256):raise ValueError('Source32 integer labels required')
    if not isinstance(palette,np.ndarray) or palette.shape!=(256,3) or palette.dtype!=np.uint8:raise ValueError('RGB uint8 palette required')
    if not isinstance(static,np.ndarray) or static.shape!=(32,32) or static.dtype!=np.bool_:raise ValueError('boolean static plane required')
    if not isinstance(accepted,np.ndarray) or accepted.shape!=(256,256,4) or accepted.dtype!=np.uint8:raise ValueError('accepted256RGBA required')
    if len(bands)!=1 or any(not isinstance(b,np.ndarray) or b.shape!=(256,256) or b.dtype.kind!='f' or not np.isfinite(b).all() or np.any(np.abs(b)>255.0000001) for b in bands):raise ValueError('one raw finite luma fine field required')
    if not np.array_equal(accepted[:,:,3],expand(source<256,8)*255):raise ValueError('accepted Source alpha mismatch')
    soil=(source>=194)&(source<=239)&~static;out=accepted.copy()
    if not soil.any():return out,dict(mutable_cells=0,protected_RGBA_exact=True,alpha_exact=True,failures=[])
    Source_rgb=palette[np.minimum(source,255)].astype(float)
    actual_groups=groups(source,soil)
    base=np.zeros((256,256,3),float);modulated=base.copy();group_metrics={}
    for name,logical in actual_groups.items():
        if not logical.any():continue
        area=expand(logical,8);gm=logical.astype(float)
        # Direct bilinear Source/group interpolation, then same-group0.5logical
        # smoothing. No ScaleNx contour lattice and no per-cell variance boost.
        weights=kernel.gaussian(kernel.resize_float(gm,(256,256)),.5*8)
        numerator=kernel.gaussian(kernel.resize_float(Source_rgb*gm[:,:,None],(256,256)),.5*8)
        field=numerator/np.maximum(weights[:,:,None],1e-12)
        target=palette[source[logical]].astype(float);means=target.mean(0)
        field+=means-field[area].mean(0)
        base[area]=field[area]
        mean_luma=float(means@LUMA)
        if mean_luma<=1e-9:raise ValueError('raw fine transfer requires positive Source group luma')
        fine=bands[0]-bands[0][area].mean()
        # Fixed group hue is Source-owned and has unit Rec709 luma. Adding the
        # genuine raw fine field therefore changes luma by EXACTLY fine, with
        # no relative-brightness amplification and zero group-mean RGB drift.
        direction=means/mean_luma
        candidate=field+fine[:,:,None]*direction
        modulated[area]=candidate[area]
        group_metrics[name]=dict(logical_cells=int(logical.sum()),Source_RGB_mean=means.tolist(),
            Source_macro_sigma_logical=.5,Source_variance_boost=False,absolute_fine_luma_gain=1.,fine_luma_std=float(fine[area].std()),
            fine_luma_mean=float(fine[area].mean()),Source_owned_RGB_direction=direction.tolist(),direction_luma=float(direction@LUMA),mid_used=False,
            linear_unit_luma_before_rounding_and_clipping=True,preclip_out_of_RGB_range_samples=int(np.sum((candidate[area]<0)|(candidate[area]>255))))
    mask=expand(soil,8);out[mask,:3]=np.clip(np.rint(modulated[mask]),0,255).astype(np.uint8)
    if not np.array_equal(out[~mask],accepted[~mask]) or not np.array_equal(out[:,:,3],accepted[:,:,3]):raise AssertionError('protected RGBA/alpha changed')
    d=diagnostics(out[:,:,:3],source,palette,soil)
    d.update(groups=group_metrics,protected_RGBA_exact=True,alpha_exact=True,
        protected_RGBA_pixels=int((~mask).sum()),changed_soil_pixels=int(np.any(out!=accepted,2).sum()),
        source_macro_base_RGB_sha256=sha(np.clip(np.rint(base),0,255).astype(np.uint8).tobytes()))
    return out,d

def relative(value):
    if type(value) is not str or not value or '\\' in value or ':' in value:
        raise ValueError('portable nonempty POSIX relative path required')
    p=PurePosixPath(value)
    if p.is_absolute() or any(x in ('','..','.') for x in value.split('/')) or str(p)!=value:
        raise ValueError('normalized contained relative path required')
    return p

def reference(ref):
    if type(ref) is not dict or set(ref)!={'path','sha256'} or type(ref['sha256']) is not str or not re.fullmatch('[0-9a-f]{64}',ref['sha256']):
        raise ValueError('exact portable path/lowercase64hex SHA required')
    relative(ref['path']);return ref

def contained(root,name,existing=True):
    root=Path(root).resolve(strict=True);p=root
    for piece in relative(name).parts:
        p=p/piece
        if p.is_symlink():raise ValueError('symlink component forbidden')
    if not p.resolve(strict=False).is_relative_to(root):raise ValueError('outside project root')
    if existing and not p.is_file():raise ValueError('regular file required')
    return p

def read_regular(path,expected=None):
    path=Path(path);flags=os.O_RDONLY|getattr(os,'O_NOFOLLOW',0);fd=os.open(path,flags)
    try:
        a=os.fstat(fd)
        if not stat.S_ISREG(a.st_mode) or a.st_size>32*1024*1024:raise ValueError('bounded regular file required')
        with os.fdopen(fd,'rb',closefd=False) as f:body=f.read()
        b=os.fstat(fd)
    finally:os.close(fd)
    state=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_mode)
    if state(a)!=state(b):raise ValueError('file changed during read')
    if expected is not None and sha(body)!=expected:raise ValueError('input SHA mismatch')
    return body

def load_verified(body,path,name):
    """Execute exactly bytes already authenticated, without reopening a path."""
    module=types.ModuleType(name);module.__file__=str(path)
    exec(compile(body,str(path),'exec'),module.__dict__);return module

def selectors(frame):
    if frame==0:return [[0,0],[0,31],[31,0],[31,30],[31,31]]
    if 5<=frame<=9:
        row=19-3*(frame-5);return [[x,y]for x in range(4,27)for y in range(row,row+3)]
    return []

def validate_recipe(r):
    keys={'format_version','method','parameters','palette','donor','phase0','ancestor_raw','ancestor_recipe','kernel','decoder','frames'}
    if type(r) is not dict or set(r)!=keys or type(r['format_version']) is not int or r['format_version']!=1 or r['method']!=METHOD:
        raise ValueError('exact versioned portable complete14 recipe required')
    if type(r['parameters']) is not dict or set(r['parameters'])!=set(PARAMETERS) or any(type(r['parameters'][k]) is not type(v) or r['parameters'][k]!=v for k,v in PARAMETERS.items()):
        raise ValueError('fixed V4 pixel parameters cannot be tuned')
    for key in keys-{'format_version','method','parameters','frames'}:reference(r[key])
    for key,digest in [('palette',PALETTE_SHA),('donor',DONOR_SHA),('phase0',PHASE0_SHA),('ancestor_raw',ANCESTOR_RAW_SHA),('kernel',KERNEL_SHA),('decoder',DECODER_SHA)]:
        if r[key]['sha256']!=digest:raise ValueError('fixed genuine input or code changed: '+key)
    frames=r['frames']
    if type(frames) is not list or len(frames)!=14:raise ValueError('complete14 frames required')
    for i,f in enumerate(frames):
        if type(f) is not dict or set(f)!={'asset','source','accepted803_RGBA','origin','original_detail_cells'} or f['asset']!=f'{0x10152+i:x}':
            raise ValueError('complete canonical numeric Source order required')
        reference(f['source']);reference(f['accepted803_RGBA'])
        if type(f['origin']) is not list or len(f['origin'])!=2 or any(type(x) is not int or x!=0 for x in f['origin']):raise ValueError('literal zero origin required')
        if f['original_detail_cells']!=selectors(i) or any(type(x) is not int for p in f['original_detail_cells']for x in p):raise ValueError('exact350 authentic runtime retention selectors required')
    source=frames[0]['source']['path']
    if [f['source']['path']for f in frames]!=[source+('.'+str(i)if i else '')for i in range(14)]:raise ValueError('Source paths must preserve complete family numbering')
    return r

def validate_ancestor(ancestor,frames):
    if type(ancestor) is not dict or type(ancestor.get('format_version')) is not int or ancestor['format_version']!=1 or ancestor.get('method')!='derived-continuous-generated-hatch-Source-broad-tone-phase-rebuild-v1':raise ValueError('accepted803 ancestor recipe required')
    if ancestor.get('palette',{}).get('sha256')!=PALETTE_SHA or ancestor.get('raw_png',{}).get('sha256')!=ANCESTOR_RAW_SHA:raise ValueError('ancestor genuine palette/raw identity changed')
    prior=ancestor.get('frames')
    if type(prior) is not list or len(prior)!=14:raise ValueError('complete14 ancestor required')
    for a,b in zip(prior,frames):
        if a.get('asset')!=b['asset'] or a.get('source',{}).get('sha256')!=b['source']['sha256']:raise ValueError('ancestor own Source identities changed')
        if type(a.get('origin')) is not list or len(a['origin'])!=2 or any(type(x)is not int or x!=0 for x in a['origin']):raise ValueError('ancestor origin changed')

def decode_source(decoder,payload):
    w,h,c=decoder._indices(payload)
    if (w,h)!=(32,32):raise ValueError("authentic Source32 canvas required")
    src=np.frombuffer(c,np.uint8).astype(np.uint16) if isinstance(c,bytes) else np.asarray(c,np.uint16)
    return src.reshape(h,w)

def run(project,recipe_path,output_path):
    """Read only contained inputs and publish a fresh reproduction directory."""
    project=Path(project).resolve(strict=True);recipe_file=contained(project,recipe_path)
    output=contained(project,output_path,existing=False)
    if output.exists() or output.is_symlink():raise ValueError('output exists; no overwrite')
    if not output.parent.is_dir():raise ValueError('output parent must exist')
    body=read_regular(recipe_file);r=validate_recipe(json.loads(body));inputs={}
    def checked(ref):
        reference(ref);p=contained(project,ref['path']);b=read_regular(p,ref['sha256']);inputs[ref['path']]=ref['sha256'];return b
    ancestor=json.loads(checked(r['ancestor_recipe']));validate_ancestor(ancestor,r['frames']);checked(r['ancestor_raw'])
    kb=checked(r['kernel']);db=checked(r['decoder'])
    kernel=load_verified(kb,contained(project,r['kernel']['path']),'_verified_targt_kernel')
    decoder=load_verified(db,contained(project,r['decoder']['path']),'_verified_targt_decoder')
    palette=kernel.palette_rgb(checked(r['palette']))
    donor=Image.open(io.BytesIO(checked(r['donor'])))
    phase0body=checked(r['phase0']);phase0=Image.open(io.BytesIO(phase0body))
    for im in [donor,phase0]:
        if im.format!='PNG' or im.size!=(1254,1254) or im.convert('RGBA').getchannel('A').getextrema()!=(255,255):raise ValueError('genuine whole opaque1254 PNG required')
    bands,band_metrics=donor_bands(np.asarray(donor.convert('RGB')),kernel)
    sources=[];parents=[]
    for frame in r['frames']:
        src=decode_source(decoder,checked(frame['source']));sources.append(src)
        image=Image.open(io.BytesIO(checked(frame['accepted803_RGBA'])))
        if image.format!='PNG' or image.size!=(256,256):raise ValueError('accepted803 parent256PNG required')
        parent=np.asarray(image.convert('RGBA'))
        if not np.array_equal(parent[:,:,3],expand(src<256,8)*255):raise ValueError('accepted803 Source alpha mismatch')
        parents.append(parent)
    if not np.all(sources[0]<256):raise ValueError('phase0 must be full opaque own Source')
    static=np.all(np.stack(sources)[1:]==sources[1],axis=0)&(sources[1]<256)
    if int(static.sum())!=96:raise ValueError('common96 Source static cells changed')
    payloads={r['frames'][0]['asset']:phase0body};metrics=[]
    for frame,src,parent in zip(r['frames'][1:],sources[1:],parents[1:]):
        out,metric=apply_frame(parent,src,palette,static,bands,kernel);metric['asset']=frame['asset'];metrics.append(metric)
        stream=io.BytesIO();Image.fromarray(out).save(stream,format='PNG',compress_level=9);payloads[frame['asset']]=stream.getvalue()
    execution=dict(status='success',method=METHOD,recipe_sha256=sha(body),tool_sha256=sha(read_regular(__file__)),source_sha256={f['asset']:f['source']['sha256']for f in r['frames']},parent_raw_sha256=sorted({ANCESTOR_RAW_SHA,DONOR_SHA,PHASE0_SHA}),output_sha256={a:sha(b)for a,b in payloads.items()})
    result=dict(execution=execution,parameters=PARAMETERS,phase0=dict(whole_genuine_raw_copied_exact=True,own_Source_used=True,retained_Original_cells=5),frames=metrics,warning_retained_Original_cells=345,retained_Original_cells_not_HD_credit=True,diagnostic_quality_failures_preserved=[dict(asset=m['asset'],failures=m['failures'])for m in metrics if m['failures']],band_metrics=band_metrics,inputs=inputs,verified_dependencies_executed_from_authenticated_bytes=True,runtime=dict(python=platform.python_version(),numpy=np.__version__,pillow=PIL.__version__),artistic_approval=False,registration=False,World=0,SourceF_helper=0,imagegen=0)
    stage=Path(tempfile.mkdtemp(prefix='.'+output.name+'.stage-',dir=output.parent))
    try:
        for asset,b in payloads.items():(stage/(asset+'-derived.png')).write_bytes(b)
        (stage/'execution-and-derived-provenance.json').write_text(json.dumps(result,indent=2)+'\n')
        for path,digest in inputs.items():read_regular(contained(project,path),digest)
        # The user owns this authoring process; mkdir gives portable no-overwrite
        # publication and a concurrent destination is never replaced.
        output.mkdir()
        try:
            for p in sorted(stage.iterdir()):shutil.move(str(p),str(output/p.name))
        except BaseException:
            shutil.rmtree(output);raise
    finally:shutil.rmtree(stage,ignore_errors=True)
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('project',type=Path);parser.add_argument('recipe_relative');parser.add_argument('new_output_relative')
    args=parser.parse_args();print(json.dumps(run(args.project,args.recipe_relative,args.new_output_relative),indent=2))
