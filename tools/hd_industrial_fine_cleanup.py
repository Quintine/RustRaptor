"""Private Source-shaped genuine-RGB derivation proposal. Never a generator return.
The single32x32 opaque format is decoded here honestly, including protected labels;
the ordinary-only decoder in hd_terrain_cleanup is neither called nor bypassed.
"""
from pathlib import Path
import argparse, hashlib, json, sys, struct, os, stat, io
import shutil
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

METHOD="industrial-Source-shape-genuine-fine-RGB-band-v1"
COHORTS={("20593","20594","2059a","2059b","2059c"),("205fe","205ff")}

def decode_source32(payload):
    if len(payload)!=1044 or struct.unpack_from('<5i',payload)!=(1,1,0,32,32):
        raise ValueError('requires exact opaque single32x32 Source PIC')
    return np.frombuffer(payload[20:],np.uint8).reshape(32,32).copy()

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

def functional_support_union(indices):
    if indices.shape!=(32,32)or indices.dtype!=np.uint8:raise ValueError('exact Source32 plane required')
    cells=set()
    for factor in range(1,5):
        y,x=np.where(scale_nx(indices,factor)>=240)
        cells.update((int(xx)//factor,int(yy)//factor)for xx,yy in zip(x,y))
    return [list(p)for p in sorted(cells)]

def material_labels(a):
    a=np.asarray(a)
    if a.ndim!=2 or a.dtype!=np.uint8:raise ValueError('indexed Source plane required')
    labels=np.full(a.shape,-1,np.int8)
    labels[a<24]=0
    labels[(a>=24)&(a<32)]=1
    labels[(a>=32)&(a<=47)]=2
    labels[(a>=192)&(a<=239)]=3
    labels[((a>=58)&(a<=79))|((a>=100)&(a<=111))]=4
    labels[a>=240]=5 # protected palette fire/individual; never ordinary donor material
    if np.any(labels<0):raise ValueError('unsupported actual industrial Source label')
    return labels

def derive_tile(indices,palette,field):
    if indices.shape!=(32,32)or indices.dtype!=np.uint8:raise ValueError('exact Source32 plane required')
    if np.asarray(field).shape!=(512,512,3):raise ValueError('registered genuine donor field required')
    guide=scale_nx(indices,4);labels=material_labels(guide)
    owners=np.repeat(np.repeat(labels,4,0),4,1)
    source_rgb=palette[guide].astype(float);output=np.zeros((512,512,3),float);base_output=np.zeros_like(output)
    donor=np.asarray(field,float);band=np.clip(donor-gaussian(donor,3.0),-16,16)*0.5
    for component in range(5):
        mask=(labels==component).astype(float)
        if not np.any(mask):continue
        weights=resize_float(gaussian(mask,1.0),(512,512))
        numerator=resize_float(gaussian(source_rgb*mask[...,None],1.0),(512,512))
        base=numerator/np.maximum(weights[...,None],1e-12)
        detail=band if component not in (0,1)else np.repeat(np.mean(band,axis=2,keepdims=True),3,axis=2)
        output[owners==component]=(base+detail)[owners==component]
        base_output[owners==component]=base[owners==component]
    output=np.clip(np.rint(output),0,255).astype(np.uint8)
    exact=np.repeat(np.repeat(palette[guide],4,0),4,1)
    protected=np.repeat(np.repeat(guide>=240,4,0),4,1);output[protected]=exact[protected]
    union=functional_support_union(indices);retained=np.zeros((32,32),bool)
    for x,y in union:retained[y,x]=True
    owner_retained=np.repeat(np.repeat(retained,16,0),16,1)
    base8=np.clip(np.rint(base_output),0,255).astype(np.uint8)
    changed=int(np.any(output!=base8,axis=2)[~owner_retained].sum())
    if changed==0:raise ValueError('no generated detail survives; Original-only is not HD')
    metrics=dict(original_detail_cells=union,raw_Source_reserved_cells=int((indices>=240).sum()),functional_support_union_cells=len(union),all_functional_SourceNx_RGB_exact=bool(np.array_equal(output[protected],exact[protected])),nonfunctional_HDR_pixels=int((~owner_retained).sum()),genuine_RGB_band_changed_nonfunctional_HDR_pixels=changed,geometry_owner_sha256=hashlib.sha256(owners.tobytes()).hexdigest(),Original_functional_HD_credit=0)
    return output,metrics

MIN_FREE_BYTES=1_932_735_284 # conservative1.8GiB floor, plus separate bounded reserve

def check_fresh_output(path,frames):
    path=Path(path).absolute()
    if '..'in path.parts or path.name in ('','.','..'):raise ValueError('canonical fresh output required')
    parent=path.parent
    if not parent.is_dir():raise ValueError('existing output parent directory required')
    for ancestor in (parent,*parent.parents):
        if ancestor.is_symlink():raise ValueError('output parent symlink forbidden')
    if os.path.lexists(path):raise ValueError('new output directory required')
    reserve=32*1024*1024+frames*512*512*3*2
    free=shutil.disk_usage(parent).free
    if free<MIN_FREE_BYTES+reserve:raise ValueError('private HD1.8GiB disk floor plus bounded output reserve required')
    return path,dict(minimum_free_bytes=MIN_FREE_BYTES,output_reserve_bytes=reserve,actual_free_bytes=free,existing_nonsymlink_parent=str(parent))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--recipe',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    recipe_bytes,recipe_pin=read_contained(args.recipe.parent,args.recipe.name,MAX_RECIPE_BYTES);recipe=json.loads(recipe_bytes)
    if set(recipe)!={'method','palette','frames','lineage','functional_contract'}or recipe['method']!=METHOD:raise ValueError('exact industrial recipe required')
    frames=recipe['frames']
    if not isinstance(frames,list)or tuple(f['asset']for f in frames)not in COHORTS:raise ValueError('exact selected complete cohort required')
    out,output_guard=check_fresh_output(args.output,len(frames))
    inputs=BufferedInputs(args.recipe.parent);pb,ppin=inputs.read(recipe['palette']);pal=palette_rgb(pb);aud=[];prepared=[]
    _,tool_pin=read_contained(Path(__file__).parent,Path(__file__).name,1024*1024)
    for f in frames:
        if set(f)!={'asset','source','donor'}:raise ValueError('exact frame fields required')
        payload,sp=inputs.read(f['source']);idx=decode_source32(payload);rgb_payload,dp=inputs.read(f['donor']);rgb=decode_png(rgb_payload)
        box=f['donor']['box']
        field=donor_field(rgb,box,(512,512));result,metrics=derive_tile(idx,pal,field);prepared.append((f['asset'],result,metrics));aud.extend([sp,dp])
    out.mkdir(parents=True)
    for aid,result,metrics in prepared:Image.fromarray(result).save(out/f'{aid}-derived.png')
    receipt=dict(output_guard=output_guard,implementation=tool_pin,executed_dependency=_dependency_pin,recipe_input=recipe_pin,physical_authenticated_input_reads=inputs.physical_reads,method=METHOD,input_pins=aud,palette=ppin,recipe_sha256=hashlib.sha256(recipe_bytes).hexdigest(),metrics=dict(selected_ids=[f['asset']for f in frames],assets=[dict(asset=aid,**one)for aid,result,one in prepared],fine_band_sigma=3.0,fine_band_clip=16,fine_band_strength=0.5,donor_repetition=False,global_SourceNx_nearest_fallback=False),output_is_derived_not_untouched=True,functional_retention_no_HD_credit='Protected Source labels240..255 and union of logical owners supporting Scale1..4 retain exact SourceNx where protected, no original-only HD credit.',outputs=[dict(file=p.name,sha256=hashlib.sha256(p.read_bytes()).hexdigest())for p in sorted(out.glob('*.png'))])
    (out/'ACTUAL-DERIVATION-RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt['metrics']))

if __name__=='__main__':main()
