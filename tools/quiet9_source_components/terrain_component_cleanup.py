"""Private Source-shaped genuine-RGB derivation proposal. Never a generator return.
The single32x32 opaque format is decoded here honestly, including protected labels;
the ordinary-only decoder in hd_terrain_cleanup is neither called nor bypassed.
"""
from pathlib import Path
import argparse, hashlib, json, sys, struct, os, stat, io
import numpy as np
from PIL import Image
ROOT=next((p for p in Path(__file__).resolve().parents if (p/'tools/hd_terrain_cleanup.py').is_file()),None)
if ROOT is None: raise RuntimeError('place this portable helper under the game root containing tools/hd_terrain_cleanup.py')
MAX_INPUT_BYTES=16*1024*1024
MAX_RECIPE_BYTES=64*1024
MAX_PNG_PIXELS=4*1024*1024

def read_contained(root,relative,limit=MAX_INPUT_BYTES):
    if not isinstance(relative,str) or relative.startswith('/') or any(x in ('','.','..') for x in relative.split('/')):
        raise ValueError('strict contained relative path required')
    root=Path(root).absolute()
    if '..' in root.parts:raise ValueError('noncanonical root path')
    flags=os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW|os.O_NONBLOCK
    fd=os.open('/',flags|os.O_DIRECTORY)
    try:
        for part in root.parts[1:]+tuple(relative.split('/')[:-1]):
            following=os.open(part,flags|os.O_DIRECTORY,dir_fd=fd);os.close(fd);fd=following
        source=os.open(relative.split('/')[-1],flags,dir_fd=fd)
        try:
            before=os.fstat(source)
            if not stat.S_ISREG(before.st_mode) or not 0<=before.st_size<=limit:raise ValueError('regular bounded input required')
            chunks=[];size=0
            while True:
                chunk=os.read(source,min(65536,limit+1-size))
                if not chunk:break
                chunks.append(chunk);size+=len(chunk)
                if size>limit:raise ValueError('bounded EOF limit exceeded')
            after=os.fstat(source)
            identity=lambda x:(x.st_dev,x.st_ino,x.st_size,x.st_mtime_ns,x.st_mode)
            if identity(before)!=identity(after) or size!=before.st_size:raise ValueError('input changed or non-EOF read')
            payload=b''.join(chunks)
            return payload,dict(path=str(root/relative),sha256=hashlib.sha256(payload).hexdigest(),size=size,mtime_ns=before.st_mtime_ns,mode=before.st_mode)
        finally:os.close(source)
    finally:os.close(fd)

class BufferedInputs:
    def __init__(self,root):self.root=Path(root);self.cache={};self.physical_reads=0
    def read(self,binding):
        rel=binding['path']
        if rel not in self.cache:
            self.cache[rel]=read_contained(self.root,rel);self.physical_reads+=1
        payload,pin=self.cache[rel]
        if pin['sha256']!=binding['sha256']:raise ValueError('input SHA mismatch')
        return payload,pin

def decode_png(payload):
    if len(payload)>MAX_INPUT_BYTES:raise ValueError('encoded PNG too large')
    with Image.open(io.BytesIO(payload)) as im:
        if im.format!='PNG' or im.width<1 or im.height<1 or im.width*im.height>MAX_PNG_PIXELS:raise ValueError('bounded PNG required')
        if getattr(im,'n_frames',1)!=1 or im.mode not in ('RGB','RGBA'):raise ValueError('single RGB/RGBA PNG required')
        if im.mode=='RGBA' and im.getchannel('A').getextrema()!=(255,255):raise ValueError('opaque PNG donor required')
        return np.array(im.convert('RGB'))

EXPECTED_DEPENDENCY_SHA256='3284cf6f85ced107dfc364ea90e15aed341d478bea7e308024b5bc5218b03092'
_dependency_bytes,_dependency_pin=read_contained(ROOT/'tools','hd_terrain_cleanup.py',1024*1024)
if _dependency_pin['sha256']!=EXPECTED_DEPENDENCY_SHA256:raise RuntimeError('reviewed terrain math dependency changed')
_dependency_namespace={'__name__':'reviewed_component_terrain_math','__file__':str(ROOT/'tools/hd_terrain_cleanup.py')}
exec(compile(_dependency_bytes,_dependency_namespace['__file__'],'exec'),_dependency_namespace)
scale_nx,gaussian,resize_float,palette_rgb=(_dependency_namespace[x]for x in ('scale_nx','gaussian','resize_float','palette_rgb'))

PAIR_IDS=('103d5','103d6')
METHOD='Source-shape-component-material-RGB-band-and-finite-T-landmark-warp-v1'

def decode_source32(payload):
    if len(payload)!=1044 or struct.unpack_from('<5i',payload)!=(1,1,0,32,32):
        raise ValueError('requires exact opaque single32x32 Source PIC')
    return np.frombuffer(payload[20:],np.uint8).reshape(32,32).copy()

def material_labels(indices,approach_rows):
    a=np.asarray(indices)
    if a.ndim!=2 or a.dtype!=np.uint8 or not 0<=approach_rows<=a.shape[0]:
        raise ValueError('requires an indexed plane and bounded approach rows')
    out=np.full(a.shape,-1,np.int8)
    out[((a>=149)&(a<=159))|((a>=240)&(a<=244))]=0 # water and actual water cycling only
    out[(a<32)|(a==173)]=1 # grey rail/shadow
    out[((a>=182)&(a<=190))|((a>=192)&(a<=218))]=2 # red bank / edge earth
    out[(a>=219)&(a<=238)]=3 # deck; upper approach separately registered
    if np.any(out<0): raise ValueError('unsupported Source material or protected class')
    out[:approach_rows][out[:approach_rows]==3]=4
    return out

def donor_field(rgb,box,size,tile_size=None):
    if len(box)!=4 or any(type(v)is not int for v in box):raise ValueError('integer donor box required')
    x,y,w,h=box
    if min(x,y)<0 or min(w,h)<1 or x+w>rgb.shape[1]or y+h>rgb.shape[0]:raise ValueError('donor crop outside genuine image')
    im=Image.fromarray(rgb[y:y+h,x:x+w])
    if tile_size:
        sw,sh=tile_size
        if min(sw,sh)<1:raise ValueError('bad texture period')
        tile=np.array(im.resize((sw,sh),Image.Resampling.LANCZOS))
        return np.tile(tile,(int(np.ceil(size[1]/sh)),int(np.ceil(size[0]/sw)),1))[:size[1],:size[0]].astype(float)
    return np.array(im.resize(size,Image.Resampling.LANCZOS),dtype=float)

def derive_pair(sources,palette,fields,audit=None):
    if len(sources)!=2 or set(fields)!=set(range(5)):raise ValueError('complete pair and all five donor components required')
    guide=np.concatenate([scale_nx(x,4)for x in sources],axis=1)
    # Material ownership is classified FROM the exact SourceNx index plane, not independently scaled label edges.
    labels=material_labels(guide,48)
    owners=np.repeat(np.repeat(labels,4,0),4,1)
    source_rgb=palette[guide].astype(float);output=np.zeros((512,1024,3),float);base_output=np.zeros_like(output)
    for component in range(5):
        mask=(labels==component).astype(float)
        weight=resize_float(gaussian(mask,1.0),(1024,512))
        numerator=resize_float(gaussian(source_rgb*mask[...,None],1.0),(1024,512))
        base=numerator/np.maximum(weight[...,None],1e-12)
        donor=np.asarray(fields[component],float)
        if donor.shape!=output.shape:raise ValueError('registered donor field size mismatch')
        # Preserve genuine bounded RGB texture, never donor coarse shape/color drift.
        band=np.clip(donor-gaussian(donor,8.0),-26,26)*0.75
        output[owners==component]=(base+band)[owners==component]
        base_output[owners==component]=base[owners==component]
    output=np.clip(np.rint(output),0,255).astype(np.uint8)
    protected=np.repeat(np.repeat(guide>=240,4,0),4,1)
    exact=np.repeat(np.repeat(palette[guide],4,0),4,1)
    output[protected]=exact[protected]
    base8=np.clip(np.rint(base_output),0,255).astype(np.uint8)
    if audit is not None:
        audit.update(genuine_RGB_band_changed_nonfunctional_pixels=int(np.any(output!=base8,axis=2)[~protected].sum()),nonfunctional_pixels=int((~protected).sum()))
    return output,owners,protected,guide

def validate_knots(knots):
    if len(knots)<2 or knots[0]!=0 or knots[-1]!=1 or any(not np.isfinite(x)for x in knots)or any(a>=b for a,b in zip(knots,knots[1:])):raise ValueError('strict finite0..1 knot partition required')

def warp_landmarks(rgb,tx,ty,sx,sy):
    for knots in (tx,ty,sx,sy):validate_knots(knots)
    if len(tx)!=len(sx)or len(ty)!=len(sy):raise ValueError('paired knot counts required')
    h,w,_=rgb.shape;mesh=[]
    xs=[round(v*w)for v in tx];ys=[round(v*h)for v in ty]
    for yi in range(len(ty)-1):
        for xi in range(len(tx)-1):
            rect=(xs[xi],ys[yi],xs[xi+1],ys[yi+1])
            if rect[2]<=rect[0]or rect[3]<=rect[1]:raise ValueError('empty mesh cell')
            l,r=sx[xi]*w,sx[xi+1]*w;t,b=sy[yi]*h,sy[yi+1]*h
            mesh.append((rect,(l,t,l,b,r,b,r,t)))
    return np.array(Image.fromarray(rgb).transform((w,h),Image.Transform.MESH,mesh,Image.Resampling.BICUBIC))


NINE_IDS={'10502','10504','10506','10508','10509','1050a','1050b','1050c','1050e'}
COHORTS={('10502','10506','10508','10509','1050a'),('10504','1050b','1050c','1050e')}

def nine_material_labels(a):
    a=np.asarray(a)
    if a.ndim!=2 or a.dtype!=np.uint8:raise ValueError('indexed Source plane required')
    labels=np.full(a.shape,-1,np.int8)
    labels[((a>=148)&(a<=159))|((a>=240)&(a<=244))]=0
    labels[(a<32)|(a==173)]=1
    labels[(a>=182)&(a<=218)]=2
    labels[(a>=219)&(a<=239)]=3
    labels[(a>=80)&(a<=95)]=4
    labels[a>=245]=5 # exact protected fire/individual, never ordinary material
    if np.any(labels<0):raise ValueError('unsupported actual Source material')
    return labels

def functional_support_union(indices):
    if indices.shape!=(32,32)or indices.dtype!=np.uint8:raise ValueError('exact Source32 plane required')
    cells=set()
    for factor in range(1,5):
        y,x=np.where(scale_nx(indices,factor)>=240)
        cells.update((int(xx)//factor,int(yy)//factor)for xx,yy in zip(x,y))
    return [list(p)for p in sorted(cells)]

def derive_nine_tile(indices,palette,fields):
    if set(fields)!=set(range(5)):raise ValueError('five genuine material donor fields required')
    if indices.shape!=(32,32)or indices.dtype!=np.uint8:raise ValueError('exact Source32 plane required')
    guide=scale_nx(indices,4);labels=nine_material_labels(guide)
    owners=np.repeat(np.repeat(labels,4,0),4,1)
    source_rgb=palette[guide].astype(float);output=np.zeros((512,512,3),float);base_output=np.zeros_like(output)
    for component in range(5):
        mask=(labels==component).astype(float)
        if not np.any(mask):continue
        weights=resize_float(gaussian(mask,1.0),(512,512))
        numerator=resize_float(gaussian(source_rgb*mask[...,None],1.0),(512,512))
        base=numerator/np.maximum(weights[...,None],1e-12)
        donor=np.asarray(fields[component],float)
        if donor.shape!=output.shape:raise ValueError('registered donor field size mismatch')
        band=np.clip(donor-gaussian(donor,8.0),-26,26)*0.75
        output[owners==component]=(base+band)[owners==component]
        base_output[owners==component]=base[owners==component]
    output=np.clip(np.rint(output),0,255).astype(np.uint8)
    exact=np.repeat(np.repeat(palette[guide],4,0),4,1);protected=np.repeat(np.repeat(guide>=240,4,0),4,1)
    output[protected]=exact[protected]
    # All logical owners that contain any Scale1..4 functional support are excluded from HD credit.
    union=functional_support_union(indices);retained=np.zeros((32,32),bool)
    for x,y in union:retained[y,x]=True
    owner_retained=np.repeat(np.repeat(retained,16,0),16,1)
    base8=np.clip(np.rint(base_output),0,255).astype(np.uint8)
    changed=int(np.any(output!=base8,axis=2)[~owner_retained].sum())
    if changed==0:raise ValueError('no surviving genuine generated RGB contribution; Original-only is not HD')
    metrics={'original_detail_cells':union,'raw_Source_reserved_cells':int((indices>=240).sum()),'functional_support_union_cells':len(union),'all_functional_SourceNx_RGB_exact':bool(np.array_equal(output[protected],exact[protected])),'nonfunctional_HDR_pixels':int((~owner_retained).sum()),'genuine_RGB_band_changed_nonfunctional_HDR_pixels':changed,'geometry_owner_sha256':hashlib.sha256(owners.tobytes()).hexdigest(),'Original_functional_HD_credit':0}
    return output,owners,protected,metrics

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--recipe',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args();recipe_bytes,recipe_pin=read_contained(args.recipe.parent,args.recipe.name,MAX_RECIPE_BYTES);recipe=json.loads(recipe_bytes);inputs=BufferedInputs(args.recipe.parent);out=args.output
    _,tool_pin=read_contained(Path(__file__).parent,Path(__file__).name,1024*1024)
    if out.exists():raise ValueError('new output directory required')
    if recipe['method']!=METHOD:raise ValueError('unknown method')
    pb,ppin=inputs.read(recipe['palette']);pal=palette_rgb(pb);aud=[]
    sources=[]
    if recipe['operation']=='nine-tiles':
        ids=tuple(x['asset']for x in recipe['sources'])
        if ids not in COHORTS:raise ValueError('exact complete selected cohort required')
        fields={}
        for key,binding in recipe['donors'].items():
            payload,pin=inputs.read(binding);rgb=decode_png(payload);fields[int(key)]=donor_field(rgb,binding['box'],(512,512),binding.get('texture_period'));aud.append(pin)
        prepared=[]
        for source in recipe['sources']:
            b,pin=inputs.read(source);idx=decode_source32(b);result,owners,protected,one=derive_nine_tile(idx,pal,fields);prepared.append((source['asset'],result,one));aud.append(pin)
        out.mkdir(parents=True)
        for aid,result,one in prepared:Image.fromarray(result).save(out/f'{aid}-derived.png')
        metrics={'selected_ids':list(ids),'assets':[dict(asset=aid,**one)for aid,result,one in prepared],'global_SourceNx_nearest_fallback':False}
    elif recipe['operation']=='pair':
        if [x['asset']for x in recipe['sources']]!=list(PAIR_IDS):raise ValueError('only complete selected pair supported')
        for x in recipe['sources']:
            b,pin=inputs.read(x);sources.append(decode_source32(b));aud.append(pin)
        donors={}
        for key,binding in recipe['donors'].items():
            payload,pin=inputs.read(binding);rgb=decode_png(payload);donors[int(key)]=donor_field(rgb,binding['box'],(1024,512),binding.get('texture_period'));aud.append(pin)
        band_audit={};result,owners,protected,guide=derive_pair(sources,pal,donors,band_audit);out.mkdir(parents=True)
        Image.fromarray(result).save(out/'derived-pair1024x512.png')
        for j,aid in enumerate(PAIR_IDS):Image.fromarray(result[:,j*512:(j+1)*512]).save(out/f'{aid}-derived.png')
        metrics=dict(band_audit);metrics.update({'protected_native4_samples':int((guide>=240).sum()),'protected_HDraw_pixels':int(protected.sum()),'protected_source_Nx_RGBA_exact':bool(np.array_equal(result[protected],np.repeat(np.repeat(pal[guide],4,0),4,1)[protected])),'geometry_component_owner_sha256':hashlib.sha256(owners.tobytes()).hexdigest(),'retained_generated_texture_nonprotected_pixels':int(np.any(result!=np.repeat(np.repeat(pal[guide],4,0),4,1),axis=2)[~protected].sum())})
    elif recipe['operation']=='T-landmark':
        source=recipe['source'];assert source['asset']=='104fd';b,pin=inputs.read(source);idx=decode_source32(b);aud.append(pin)
        # The measured Source has a full-width ochre top line at row9 and its lower arm at23.
        if sum(80<=i<=95 for i in idx[9])!=32 or sum(80<=i<=95 for i in idx[23])!=19:raise ValueError('Source T topology changed')
        payload,pin=inputs.read(recipe['donor']);rgb=decode_png(payload);x,y,w,h=recipe['donor']['box']
        if min(x,y)<0 or min(w,h)<1 or x+w>rgb.shape[1]or y+h>rgb.shape[0]:raise ValueError('bad T donor crop')
        result=warp_landmarks(rgb[y:y+h,x:x+w],**recipe['knots']);out.mkdir(parents=True);Image.fromarray(result).save(out/'104fd-derived.png');aud.append(pin);metrics={'source_top_yellow_row':9,'source_lower_yellow_row':23,'knots':recipe['knots'],'genuine_RGB_only_warp':True,'protected_Source_cells_to_declare_original_detail':[[int(x),int(y)]for y,x in zip(*np.where(idx>=240))]}
    else:raise ValueError('unknown operation')
    receipt={'implementation':tool_pin,'executed_dependency':_dependency_pin,'recipe_input':recipe_pin,'physical_authenticated_input_reads':inputs.physical_reads,'method':METHOD,'operation':recipe['operation'],'input_pins':aud,'palette':ppin,'recipe_sha256':hashlib.sha256(recipe_bytes).hexdigest(),'metrics':metrics,'output_is_derived_not_untouched':True,'functional_retention_no_HD_credit':'Original protected cells>=240 retain exact SourceNx RGB/labels. No global Original-nearest fallback is claimed as HD.','outputs':[{'file':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}for p in sorted(out.glob('*.png'))]};(out/'ACTUAL-DERIVATION-RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt['metrics']))
if __name__=='__main__':main()
