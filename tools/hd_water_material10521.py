"""10521 water-only Source-shaped fine RGB material; never a generator return."""
from pathlib import Path
import argparse,hashlib,io,json,os,stat,struct
import numpy as np
from PIL import Image
METHOD='10521-Source-water-only-quiet-genuine-RGB-fineband-preserve-nonwater-v1'
PARAMS=dict(source_sigma=1.0,donor_band_sigma=3.0,donor_band_clip=16.0,donor_band_gain=0.5)
DEPENDENCY='3284cf6f85ced107dfc364ea90e15aed341d478bea7e308024b5bc5218b03092'
MAX_INPUT=16*1024*1024

def read_contained(root,name,limit=MAX_INPUT):
 if not isinstance(name,str)or name.startswith('/')or any(x in('','.','..')for x in name.split('/')):raise ValueError('contained canonical relative route required')
 root=Path(root).absolute()
 if'..'in root.parts:raise ValueError('canonical root required')
 flags=os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW|os.O_NONBLOCK;fd=os.open('/',flags|os.O_DIRECTORY)
 try:
  for part in root.parts[1:]+tuple(name.split('/')[:-1]):n=os.open(part,flags|os.O_DIRECTORY,dir_fd=fd);os.close(fd);fd=n
  source=os.open(name.split('/')[-1],flags,dir_fd=fd)
  try:
   before=os.fstat(source)
   if not stat.S_ISREG(before.st_mode)or not 0<=before.st_size<=limit:raise ValueError('bounded regular input required')
   chunks=[];size=0
   while True:
    chunk=os.read(source,min(65536,limit+1-size))
    if not chunk:break
    chunks.append(chunk);size+=len(chunk)
    if size>limit:raise ValueError('bounded EOF required')
   after=os.fstat(source);key=lambda v:(v.st_dev,v.st_ino,v.st_size,v.st_mtime_ns,v.st_mode)
   if key(before)!=key(after)or size!=before.st_size:raise ValueError('input changed during read')
   return b''.join(chunks)
  finally:os.close(source)
 finally:os.close(fd)

ROOT=next((p for p in Path(__file__).resolve().parents if(p/'tools/hd_terrain_cleanup.py').is_file()),None)
if ROOT is None:raise RuntimeError('game root containing reviewed math required')
b=read_contained(ROOT,'tools/hd_terrain_cleanup.py',1024*1024)
if hashlib.sha256(b).hexdigest()!=DEPENDENCY:raise RuntimeError('reviewed math dependency changed')
ns={'__name__':'reviewed_water_math','__file__':str(ROOT/'tools/hd_terrain_cleanup.py')};exec(compile(b,ns['__file__'],'exec'),ns)
scale_nx,gaussian,resize_float,palette_rgb=(ns[n]for n in('scale_nx','gaussian','resize_float','palette_rgb'))

def decode_png(payload):
 with Image.open(io.BytesIO(payload))as im:
  if im.format!='PNG'or im.width*im.height>4*1024*1024 or getattr(im,'n_frames',1)!=1 or im.mode not in('RGB','RGBA'):raise ValueError('bounded single opaque PNG required')
  if im.mode=='RGBA'and im.getchannel('A').getextrema()!=(255,255):raise ValueError('opaque PNG required')
  return np.array(im.convert('RGB'))

def derive(indices,palette,old,donor):
 if indices.shape!=(32,32)or indices.dtype!=np.uint8 or old.shape!=(724,724,3)or old.dtype!=np.uint8:raise ValueError('exact Source32 and724RGB required')
 if palette.shape!=(256,3)or palette.dtype!=np.uint8 or donor.shape!=(887,887,3)or donor.dtype!=np.uint8:raise ValueError('exact palette and frozen water donor field required')
 water=((indices>=149)&(indices<=159))|((indices>=240)&(indices<=244))
 if not water[:16].all()or water[16:].any()or (indices>=245).any():raise ValueError('Source10521 straight upper-water geometry required')
 guide=scale_nx(indices,4);mask=(((guide>=149)&(guide<=159))|((guide>=240)&(guide<=244))).astype(float)
 owner=np.array(Image.fromarray(mask.astype(np.uint8)).resize((724,724),Image.Resampling.NEAREST),dtype=bool)
 if not owner[:362].all()or owner[362:].any():raise ValueError('Source ownership changed dock anchor')
 weights=resize_float(gaussian(mask,1.0),(724,724));numerator=resize_float(gaussian(palette[guide].astype(float)*mask[...,None],1.0),(724,724));base=numerator/np.maximum(weights[...,None],1e-12)
 field=np.array(Image.fromarray(donor).resize((724,724),Image.Resampling.LANCZOS),dtype=float)
 band=np.clip(field-gaussian(field,3.0),-16.0,16.0)*0.5
 candidate=np.clip(np.rint(base+band),0,255).astype(np.uint8);result=old.copy();result[owner]=candidate[owner]
 protected=np.array(Image.fromarray((guide>=240).astype(np.uint8)).resize((724,724),Image.Resampling.NEAREST),dtype=bool)
 exact=np.array(Image.fromarray(palette[guide]).resize((724,724),Image.Resampling.NEAREST));result[protected]=exact[protected]
 retained=set()
 for s in range(1,5):
  yy,xx=np.where(scale_nx(indices,s)>=240);retained.update((int(x)//s,int(y)//s)for x,y in zip(xx,yy))
 changed=int(np.any(result!=np.clip(np.rint(base),0,255).astype(np.uint8),axis=2)[owner&~protected].sum())
 if changed==0 or not np.array_equal(result[~owner],old[~owner]):raise ValueError('genuine fine detail and unchanged nonwater required')
 return result,dict(water_pixels=int(owner.sum()),nonwater_changed_pixels=0,genuine_fine_band_changed_water_pixels=changed,old_to_new_water_changed_pixels=int(np.any(result!=old,axis=2)[owner].sum()),Original_protected_RGB_exact=bool(np.array_equal(result[protected],exact[protected])),original_detail_cells=[list(p)for p in sorted(retained)],Original_coarse_geometry_and_retained_cells_HD_credit=0,donor_coarse_shapes_colors_not_copied=True)

def run(recipe_path,output):
 recipe_path=Path(recipe_path).absolute();root=recipe_path.parent;raw=read_contained(root,recipe_path.name,64*1024);recipe=json.loads(raw)
 if set(recipe)!= {'method','asset','inputs','donor_box','parameters','dependency','scope'}or recipe['method']!=METHOD or recipe['asset']!='10521'or recipe['parameters']!=PARAMS or any(type(v)is not float for v in recipe['parameters'].values())or recipe['donor_box']!=[0,0,887,887]or recipe['dependency']!={'path':'tools/hd_terrain_cleanup.py','sha256':DEPENDENCY}:raise ValueError('exact reviewed10521 recipe required')
 if set(recipe['inputs'])!={'source','palette','old_png','donor'}:raise ValueError('exact input roles required')
 payloads={};pins={}
 for name,binding in recipe['inputs'].items():
  if set(binding)!={'path','sha256'}:raise ValueError('exact path/SHA input binding required')
  payload=read_contained(root,binding['path']);digest=hashlib.sha256(payload).hexdigest()
  if digest!=binding['sha256']:raise ValueError('input hash differs')
  payloads[name]=payload;pins[name]=digest
 source=payloads['source']
 if len(source)!=1044 or struct.unpack_from('<5i',source)!=(1,1,0,32,32):raise ValueError('exact opaque Source32 PIC required')
 donor=decode_png(payloads['donor'])
 if donor.shape[0]<887 or donor.shape[1]<887:raise ValueError('donor crop outside image')
 result,metrics=derive(np.frombuffer(source[20:],np.uint8).reshape(32,32),palette_rgb(payloads['palette']),decode_png(payloads['old_png']),donor[:887,:887])
 out=Path(output).absolute()
 if '..'in out.parts or out.exists()or not out.is_relative_to(root)or any(p.is_symlink()for p in[out,*out.parents]):raise ValueError('fresh contained output directory required')
 tool=read_contained(Path(__file__).parent,Path(__file__).name,1024*1024)
 out.mkdir();p=out/'10521-water-remediated.png';Image.fromarray(result).save(p)
 record=dict(status='success',method=METHOD,recipe_sha256=hashlib.sha256(raw).hexdigest(),tool_sha256=hashlib.sha256(tool).hexdigest(),inputs=pins,output_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),metrics=metrics,new_generation_calls=0,derived_not_generator_return=True)
 (out/'execution-receipt.json').write_text(json.dumps(record,indent=2)+'\n');return record
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--recipe',required=True);ap.add_argument('--output',required=True);a=ap.parse_args();print(json.dumps(run(a.recipe,a.output),indent=2))
