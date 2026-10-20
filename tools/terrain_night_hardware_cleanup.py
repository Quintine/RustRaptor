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

METHOD='Source-night-hardware-fine-material-v1'
COHORTS={'hardware2':('2054d','2054e'),'dark3':('2057f','20581','20588')}

def decode_source32(payload):
    if len(payload)!=1044 or struct.unpack_from('<5i',payload)!=(1,1,0,32,32):
        raise ValueError('exact opaque single32x32 Source PIC required')
    return np.frombuffer(payload[20:],np.uint8).reshape(32,32).copy()

def source_labels(a):
    if a.ndim!=2 or a.dtype!=np.uint8:raise ValueError('indexed Source plane required')
    labels=np.full(a.shape,-1,np.int8)
    labels[a==31]=0
    labels[(a>=24)&(a<=30)]=1
    labels[a<24]=2
    labels[(a>=54)&(a<=58)]=3
    labels[a>=240]=4
    if np.any(labels<0):raise ValueError('unsupported Source index')
    return labels

def support_union(indices):
    cells=set()
    for factor in range(1,5):
        ys,xs=np.where(scale_nx(indices,factor)>=240)
        cells.update((int(x)//factor,int(y)//factor)for x,y in zip(xs,ys))
    return [list(p)for p in sorted(cells)]

def donor_field(rgb,box):
    if len(box)!=4 or any(type(v)is not int for v in box):raise ValueError('integer donor box required')
    x,y,w,h=box
    if min(x,y)<0 or min(w,h)<1 or x+w>rgb.shape[1]or y+h>rgb.shape[0]:
        raise ValueError('donor box outside genuine PNG')
    return np.array(Image.fromarray(rgb[y:y+h,x:x+w]).resize((512,512),Image.Resampling.LANCZOS),float)

def derive(indices,palette,fields):
    if indices.shape!=(32,32)or indices.dtype!=np.uint8:raise ValueError('exact Source32 required')
    if not {1,2}.issubset(fields)or set(fields)-{1,2,3}:raise ValueError('invalid donor components')
    guide=scale_nx(indices,4)
    labels=source_labels(guide)
    owners=np.repeat(np.repeat(labels,4,0),4,1)
    exact=np.repeat(np.repeat(palette[guide],4,0),4,1)
    base_output=exact.astype(float).copy();output=base_output.copy()
    source_rgb=palette[guide].astype(float)
    for component in (1,2,3):
        mask=(labels==component).astype(float)
        if not np.any(mask):continue
        if component not in fields:raise ValueError('missing actual Source material donor')
        weight=resize_float(gaussian(mask,0.65),(512,512))
        numerator=resize_float(gaussian(source_rgb*mask[...,None],0.65),(512,512))
        base=numerator/np.maximum(weight[...,None],1e-12)
        donor=np.asarray(fields[component],float)
        if donor.shape!=(512,512,3)or not np.isfinite(donor).all():raise ValueError('finite registered donor field required')
        # Use only fine genuine RGB material. Coarse donor geometry is discarded.
        band=np.clip(donor-gaussian(donor,2.0),-12,12)*0.5
        selected=owners==component
        output[selected]=(base+band)[selected];base_output[selected]=base[selected]
    output=np.clip(np.rint(output),0,255).astype(np.uint8)
    base8=np.clip(np.rint(base_output),0,255).astype(np.uint8)
    exact_mask=(owners==0)|(owners==4)
    if not np.array_equal(output[exact_mask],exact[exact_mask]):raise ValueError('black/functional ownership drift')
    union=support_union(indices)
    retained=np.zeros((32,32),bool)
    for x,y in union:retained[y,x]=True
    excluded=np.repeat(np.repeat(retained,16,0),16,1)|(owners==0)
    changed=np.any(output!=base8,axis=2)
    if not np.any(changed&~excluded):raise ValueError('no genuine material contribution outside excluded cells')
    metrics={'original_detail_cells':union,'functional_retention_HD_credit':0,'opaque_black_HD_credit':0,'functional_HDR_pixels':int((owners==4).sum()),'opaque_black_HDR_pixels':int((owners==0).sum()),'black_and_functional_RGB_exact':True,'genuine_fine_RGB_changed_nonexcluded_pixels':int((changed&~excluded).sum()),'nonexcluded_material_pixels':int((~excluded).sum()),'source_geometry_owners_sha256':hashlib.sha256(owners.tobytes()).hexdigest()}
    return output,metrics

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--recipe',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    payload,rpin=read_contained(args.recipe.parent,args.recipe.name,MAX_RECIPE_BYTES);recipe=json.loads(payload)
    if recipe['method']!=METHOD or recipe['cohort']not in COHORTS:raise ValueError('unknown method/cohort')
    if tuple(x['asset']for x in recipe['sources'])!=COHORTS[recipe['cohort']]:raise ValueError('exact complete cohort required')
    if (recipe['output_side'],recipe['band_sigma'],recipe['band_clip'],recipe['band_strength'])!=(512,2.0,12.0,0.5):raise ValueError('reviewed material constants changed')
    if args.output.exists():raise ValueError('new output directory required')
    inputs=BufferedInputs(args.recipe.parent);pb,ppin=inputs.read(recipe['palette']);palette=palette_rgb(pb)
    fields={};pins=[ppin]
    for key,binding in recipe['donors'].items():
        b,pin=inputs.read(binding);fields[int(key)]=donor_field(decode_png(b),binding['box']);pins.append(pin)
    prepared=[]
    for binding in recipe['sources']:
        b,pin=inputs.read(binding);result,metrics=derive(decode_source32(b),palette,fields);pins.append(pin);prepared.append((binding['asset'],result,metrics))
    _,tool_pin=read_contained(Path(__file__).parent,Path(__file__).name,1024*1024)
    args.output.mkdir(parents=True)
    for aid,result,metrics in prepared:Image.fromarray(result).save(args.output/f'{aid}-derived.png')
    receipt={'implementation':tool_pin,'executed_dependency':_dependency_pin,'recipe':rpin,'authenticated_input_reads':inputs.physical_reads,'input_pins':pins,'method':METHOD,'cohort':recipe['cohort'],'output_is_derived_not_untouched':True,'global_Original_nearest_fallback':False,'metrics':[dict(asset=aid,**metrics)for aid,result,metrics in prepared],'outputs':[{'file':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}for p in sorted(args.output.glob('*.png'))]}
    (args.output/'ACTUAL-DERIVATION-RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({'cohort':recipe['cohort'],'derived':len(prepared),'receipt':str(args.output/'ACTUAL-DERIVATION-RECEIPT.json')}))

if __name__=='__main__':main()

