"""Private narrow 30096 derived-dark-wreck recipe. No art acceptance or engine writes."""
from __future__ import annotations
import argparse,builtins,hashlib,io,json,os,re,shutil,stat,sys,types
from pathlib import Path
import numpy as np
from PIL import Image
PINS={'hd_frame_policy':'66184a4758027dadbadb5e20fe90b2add2b9fc218b7810304b1a1ea2de74f58e','hd_dshp20_cleanup':'c6123e9591f0a169846677019ddcb944bf9c2b4c9184a7d8ab02a08546de409b'}
SOURCE='25c7daca9d1f00b9f9f6580ec73e6de193bf719c956cda9155c933c2f2d1c1ee'
RAW='815bdcb76d075d1af5b21816c20937f645027ca65ec74d7347a532346cb1d85b'
PALETTE='1cf6adb926d1dee1888b3e3d33b51a7049b3e5eb5f90a3067ef71c8970547204'
METHOD='derived-30096-generated-fullRGB-SourceScale4-darken-only-Source-max-plus12-v1'
def sha(b):return hashlib.sha256(b).hexdigest()

def read(binding,base=None,limit=32*1024*1024):
 if type(binding)is not dict or set(binding)!={'path','sha256'} or re.fullmatch('[0-9a-f]{64}',binding['sha256'])is None:raise ValueError('exact binding required')
 p=Path(binding['path'])
 if p.is_absolute()or '..'in p.parts or '\\'in str(p)or str(p)!=binding['path']or not p.parts:raise ValueError('canonical project-relative input required')
 base=Path.cwd()if base is None else Path(base)
 directory=os.open(base,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
 try:
  for part in p.parts[:-1]:
   nxt=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=directory);os.close(directory);directory=nxt
  fd=os.open(p.name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=directory)
  try:
   before=os.fstat(fd)
   if not stat.S_ISREG(before.st_mode) or before.st_size>limit:raise ValueError('bounded regular input required')
   chunks=[];count=0
   while True:
    b=os.read(fd,min(65536,limit+1-count))
    if not b:break
    chunks.append(b);count+=len(b)
    if count>limit:raise ValueError('input too large')
   payload=b''.join(chunks);after=os.fstat(fd)
   if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):raise ValueError('input changed')
  finally:os.close(fd)
 finally:os.close(directory)
 if sha(payload)!=binding['sha256']:raise ValueError('input hash mismatch')
 return payload

def modules(payloads):
 if set(payloads)!=set(PINS)or any(sha(payloads[k])!=v for k,v in PINS.items()):raise ValueError('dependency bytes differ')
 loaded={};real_import=builtins.__import__;proxy=types.SimpleNamespace(path=list(sys.path),version=sys.version)
 def importer(name,globals=None,locals=None,fromlist=(),level=0):
  if name in loaded:return loaded[name]
  if name=='sys':return proxy
  return real_import(name,globals,locals,fromlist,level)
 for name in PINS:
  m=types.ModuleType(name);m.__file__='/authenticated-buffered/'+name+'.py';m.__dict__['__builtins__']={**vars(builtins),'__import__':importer}
  exec(compile(payloads[name],m.__file__,'exec'),m.__dict__);loaded[name]=m
 return loaded

def cap_material(rgba,source4,palette):
 if rgba.dtype!=np.uint8 or rgba.shape!=(*source4.shape,4):raise ValueError('matching complete uint8 RGBA required')
 if np.any(source4>256) or palette.shape!=(256,3) or palette.dtype!=np.uint8:raise ValueError('valid Original labels/palette required')
 mask=source4<256
 if not np.array_equal(rgba[:,:,3],np.where(mask,255,0).astype(np.uint8)):raise ValueError('SourceScale4 coverage required')
 out=rgba.copy();rgb=rgba[:,:,:3].astype(np.uint32);peak=rgb.max(axis=2)
 limits=np.zeros(source4.shape,np.uint32);limits[mask]=np.minimum(255,palette[source4[mask]].max(axis=1).astype(np.uint32)+12)
 change=mask&(peak>limits)
 out[:,:,:3][change]=(rgb[change]*limits[change,None]//peak[change,None]).astype(np.uint8)
 assert np.array_equal(out[:,:,3],rgba[:,:,3]) and np.all(out[:,:,:3]<=rgba[:,:,:3])
 assert np.array_equal(out[~change],rgba[~change])
 return out,dict(changed_generated_RGB_samples=int(change.sum()),opaque_samples=int(mask.sum()),literal_Original_RGB_replacements=0,Original_RGB_only_sets_brightness_ceiling=True,integer_math='floor(parent_channel * min(255,max(OriginalRGB[SourceScale4label])+12) / parent_RGB_max) iff parent_RGB_max exceeds ceiling',brightness_slack=12,alpha_unchanged=True,darken_only=True)

def validate_recipe(recipe):
 if type(recipe)is not dict or set(recipe)!={'format_version','palette','source','raw_png','dependencies','asset','viewport','origin','brightness_slack','donor_bound'}:raise ValueError('exact recipe required')
 if type(recipe['format_version'])is not int or recipe['format_version']!=1 or recipe['asset']!='30096':raise ValueError('exact singleton required')
 if recipe['viewport']!=[0,0,1254,1254] or recipe['origin']!=[0,0] or any(type(x)is not int for x in recipe['viewport']+recipe['origin']):raise ValueError('literal full canvas/origin required')
 if type(recipe['brightness_slack'])is not int or recipe['brightness_slack']!=12 or type(recipe['donor_bound'])is not int or recipe['donor_bound']!=12:raise ValueError('fixed bounds required')
 if set(recipe['dependencies'])!=set(PINS) or any(recipe['dependencies'][k].get('sha256')!=v for k,v in PINS.items()):raise ValueError('dependency pins differ')
 for k,h in [('palette',PALETTE),('source',SOURCE),('raw_png',RAW)]:
  if recipe[k].get('sha256')!=h:raise ValueError('Original or parent pin differs')

def derive(recipe,base):
 validate_recipe(recipe);cache={}
 def load(b,limit=32*1024*1024):
  key=(b['path'],b['sha256'])
  if key not in cache:cache[key]=read(b,base,limit)
  return cache[key]
 deps={k:load(v,1024*1024)for k,v in recipe['dependencies'].items()};mods=modules(deps);decoder,g=(mods[n]for n in PINS)
 decoder.__file__=recipe['dependencies']['hd_frame_policy']['path']
 class ReceiptPath:
  def __init__(self,value):
   if value!=decoder.__file__:raise ValueError('unbuffered receipt refused')
  def resolve(self):return self
  def read_bytes(self):return deps['hd_frame_policy']
  def __str__(self):return decoder.__file__
 g.Path=ReceiptPath
 for b in [recipe[k]for k in ['palette','source','raw_png']]:load(b)
 def checked(b,unused):
  key=(b['path'],b['sha256'])
  if key not in cache:raise ValueError('unbuffered input refused')
  return Path(b['path']),cache[key]
 g.checked=checked
 frame={k:recipe[k]for k in ['asset','source','raw_png','viewport','origin']};frame['sampling_offset_native']=[0,0]
 arrays,geometry=g.render_family(dict(format_version=1,label=METHOD,palette=recipe['palette'],output_scale=4,max_fill_distance_pixels=12,shared_backing_anchor=0,frames=[frame]),Path('/'))
 w,h,cells=decoder._indices(load(recipe['source']))
 if [w,h]!=[32,32]:raise ValueError('Original canvas differs')
 source4=g.scale2(g.scale2(np.asarray(cells,np.uint16).reshape(h,w)));p6=np.frombuffer(load(recipe['palette']),np.uint8).reshape(256,3).astype(np.uint16);palette=((p6<<2)|(p6>>4)).astype(np.uint8)
 out,cap=cap_material(arrays[0],source4,palette)
 return out,dict(method=METHOD,geometry=geometry,material_cap=cap,unique_authenticated_buffered_inputs=len(cache),scope='DERIVED generated RGB with brightness changed; not untouched generation, no Source RGB copied, no context or art acceptance.')

def main(recipe_relative,recipe_sha,project_root,output):
 base=Path(project_root).resolve(strict=True);rb=read({'path':recipe_relative,'sha256':recipe_sha},base,1024*1024);recipe=json.loads(rb)
 output=Path(output)
 if not output.is_absolute():output=base/output
 if output.exists()or output.is_symlink()or not output.parent.is_dir()or output.parent.resolve()!=output.parent.absolute():raise ValueError('fresh output below existing nonsymlink parent required')
 if shutil.disk_usage(output.parent).free<1_808_000_000:raise ValueError('1.8-billion-byte floor plus output reserve required')
 out,report=derive(recipe,base);buf=io.BytesIO();Image.fromarray(out).save(buf,format='PNG',compress_level=9);png=buf.getvalue()
 report['execution']=dict(status='success',tool_sha256=sha(Path(__file__).read_bytes()),recipe_sha256=sha(rb),source_sha256=SOURCE,parent_raw_sha256=RAW,output_sha256=sha(png),RGBA_sha256=sha(out.tobytes()))
 output.mkdir();(output/'30096-derived.png').write_bytes(png);(output/'derived-provenance.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report['execution']))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('recipe_relative');p.add_argument('recipe_sha');p.add_argument('project_root');p.add_argument('output');a=p.parse_args();main(a.recipe_relative,a.recipe_sha,a.project_root,a.output)
