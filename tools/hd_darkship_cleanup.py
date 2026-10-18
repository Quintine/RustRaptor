"""Narrow reviewed-math dispatcher: full genuine RGB with Original Scale4 support.

No generation, engine, acceptance or canonical writes. Dependencies and artwork
are read once as authenticated bytes before geometry; outputs use a fresh folder.
"""
from __future__ import annotations
import argparse,builtins,hashlib,io,json,os,re,shutil,stat,sys,types
from pathlib import Path
import numpy as np
from PIL import Image
PINS={'hd_frame_policy':'66184a4758027dadbadb5e20fe90b2add2b9fc218b7810304b1a1ea2de74f58e','hd_dshp20_cleanup':'c6123e9591f0a169846677019ddcb944bf9c2b4c9184a7d8ab02a08546de409b','hd_other_functional_cleanup':'f8078284e300947aec4d2c9e70cbc7198fa3cb5d34de6b36c07cacc5f3820a84'}
SPEC={'102fc':([40,32],'f0357eded395029e0740c49d408a3475a9831cadcfd9dd626633bdff03e574fb','d65014c2023a3004067b3fdb8708d219de92355bd4663358b5b9984aca754791',[57,28,1377,1084],[[27,12],[28,12]]),'2009a':([48,32],'8408802c346c81ecb2062d8f4b0ef580a646a7547cb963f1b8e76d8d934305c2','50190a5588a581300232fd0bb11b98955fce30c50e35ea7e59be95d66904ad60',[132,124,894,632],[[x,y]for x in range(22,27)for y in range(13,16)]),'2009b':([48,32],'6888dd1bd06dd176b5450b431ff422220bf32541f2a2fed097ee3604c36fe725','50190a5588a581300232fd0bb11b98955fce30c50e35ea7e59be95d66904ad60',[132,891,894,1399],[[x,y]for x in range(22,27)for y in range(13,16)])}
PALETTE='1cf6adb926d1dee1888b3e3d33b51a7049b3e5eb5f90a3067ef71c8970547204'
METHOD='derived-existing-generated-RGB-SHIP05-singleton-SHIP03-rotor2-SourceScale4-v1'
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

def validate_recipe(recipe):
 if type(recipe)is not dict or set(recipe)!={'format_version','family','palette','frames','dependencies'}or type(recipe['format_version'])is not int or recipe['format_version']!=1:raise ValueError('exact recipe fields/version required')
 ids={'SHIP05-singleton':['102fc'],'SHIP03-rotor2':['2009a','2009b']}.get(recipe['family'])
 if ids is None or type(recipe['frames'])is not list or [f.get('asset')for f in recipe['frames']]!=ids:raise ValueError('complete family required')
 if recipe['palette'].get('sha256')!=PALETTE:raise ValueError('Original palette differs')
 if set(recipe['dependencies'])!=set(PINS)or any(recipe['dependencies'][k].get('sha256')!=v for k,v in PINS.items()):raise ValueError('dependency binding differs')
 for f in recipe['frames']:
  if set(f)!={'asset','source','raw_png','viewport','origin','functional_original_cells'}:raise ValueError('exact frame fields required')
  canvas,source,raw,viewport,cells=SPEC[f['asset']]
  if any(type(x)is not int for x in f['origin']+f['viewport'])or any(type(x)is not int for xy in f['functional_original_cells']for x in xy):raise ValueError('literal integer geometry/functional cells required')
  if f['source'].get('sha256')!=source or f['raw_png'].get('sha256')!=raw or f['viewport']!=viewport or f['origin']!=[0,0] or f['functional_original_cells']!=cells:raise ValueError('Source/raw/geometry/functional declaration differs')
 return ids

def derive(recipe,base=None,shared_cache=None):
 ids=validate_recipe(recipe)
 base=Path.cwd()if base is None else Path(base)
 shared_cache={}if shared_cache is None else shared_cache
 def load(binding,limit=32*1024*1024):
  key=(binding['path'],binding['sha256'])
  if key not in shared_cache:shared_cache[key]=read(binding,base,limit)
  return shared_cache[key]
 dep={k:load(v,1024*1024)for k,v in recipe['dependencies'].items()};mods=modules(dep)
 decoder,g,functional=(mods[n]for n in PINS)
 # The pinned geometry dependency records its decoder's source identity at the
 # end. Supply that receipt from the already authenticated buffer as well.
 decoder.__file__=recipe['dependencies']['hd_frame_policy']['path']
 class BufferedDecoderReceiptPath:
  def __init__(self,value):
   if value!=decoder.__file__:raise ValueError('unbuffered dependency receipt path refused')
  def resolve(self):return self
  def read_bytes(self):return dep['hd_frame_policy']
  def __str__(self):return decoder.__file__
 g.Path=BufferedDecoderReceiptPath
 bindings=[recipe['palette']]+[f[k]for f in recipe['frames']for k in ('source','raw_png')]
 cache={}
 for b in bindings:
  key=(b['path'],b['sha256'])
  if key not in cache:cache[key]=load(b)
 def checked(binding,base):
  key=(binding['path'],binding['sha256'])
  if key not in cache:raise ValueError('unbuffered input refused')
  return Path(binding['path']),cache[key]
 g.checked=checked
 geom=dict(format_version=1,label=METHOD,palette=recipe['palette'],output_scale=4,max_fill_distance_pixels=12,shared_backing_anchor=0,frames=[{k:f[k]for k in ('asset','source','raw_png','viewport','origin')}|{'sampling_offset_native':[0,0]}for f in recipe['frames']])
 arrays,geometry=g.render_family(geom,Path('/'))
 pb=cache[(recipe['palette']['path'],PALETTE)];p6=np.frombuffer(pb,np.uint8).reshape(256,3).astype(np.uint16);palette=((p6<<2)|(p6>>4)).astype(np.uint8)
 outputs=[];records=[]
 for f,rgba in zip(recipe['frames'],arrays):
  w,h,cells=decoder._indices(cache[(f['source']['path'],f['source']['sha256'])]);s=np.asarray(cells,np.uint16).reshape(h,w)
  if [w,h]!=SPEC[f['asset']][0]:raise ValueError('Source canvas differs')
  out,retention=functional.retain_functional_original(rgba,s,palette,f['functional_original_cells'])
  outputs.append(out);records.append(dict(asset=f['asset'],functional_original=retention))
 return outputs,dict(method=METHOD,geometry=geometry,functional=records,limits=['Derived material, never untouched generation.','Functional Original2/15 cells are not generated HD.','Whole native material and context acceptance remain separate.'])

def derive_bundle(bundle,base):
 if type(bundle)is not dict or set(bundle)!={'format_version','families'}or type(bundle['format_version'])is not int or bundle['format_version']!=1:raise ValueError('exact bundle fields/version required')
 if type(bundle['families'])is not list or len(bundle['families'])!=2 or [f.get('family')for f in bundle['families']]!=['SHIP05-singleton','SHIP03-rotor2']:raise ValueError('exact complete singleton plus rotor2 bundle required')
 for family in bundle['families']:validate_recipe(family)
 cache={};outputs={};reports=[]
 for family in bundle['families']:
  arrays,report=derive(family,base,cache)
  for f,a in zip(family['frames'],arrays):outputs[f['asset']]=a
  reports.append(report)
 return outputs,dict(method=METHOD,family_reports=reports,unique_buffered_inputs=len(cache),scope='One portable bundled execution of unchanged two complete-family pixel computations; no engine or artistic authority.')

def main(recipe_path,output,project_root=None):
 base=Path(__file__).resolve().parent.parent if project_root is None else Path(project_root).resolve(strict=True)
 recipe_path=Path(recipe_path);recipe_path=recipe_path if recipe_path.is_absolute()else base/recipe_path
 if not recipe_path.resolve().is_relative_to(base):raise ValueError('recipe must be contained in supplied project root')
 output=Path(output);output=output if output.is_absolute()else base/output
 if output.exists()or output.is_symlink():raise ValueError('fresh output required')
 if not output.parent.is_dir()or output.parent.resolve()!=output.parent.absolute():raise ValueError('existing non-symlink output parent required')
 if shutil.disk_usage(output.parent).free<2_208_000_000:raise ValueError('2.2-billion-byte free floor plus bounded output reserve required')
 rb=recipe_path.read_bytes();bundle=json.loads(rb);arrays,report=derive_bundle(bundle,base)
 encoded={}
 for asset,a in arrays.items():
  b=io.BytesIO();Image.fromarray(a).save(b,format='PNG',compress_level=9);encoded[asset]=b.getvalue()
 output.mkdir()
 for asset,b in encoded.items():(output/(asset+'-derived.png')).write_bytes(b)
 frames=[f for family in bundle['families']for f in family['frames']]
 report['execution']=dict(status='success',method=METHOD,tool_sha256=sha(Path(__file__).read_bytes()),recipe_sha256=sha(rb),source_sha256={f['asset']:f['source']['sha256']for f in frames},parent_raw_sha256=sorted(set(f['raw_png']['sha256']for f in frames)),output_sha256={a:sha(b)for a,b in encoded.items()})
 (output/'derived-provenance.json').write_text(json.dumps(report,indent=2)+'\n');(output/'normalized-execution.json').write_text(json.dumps(report['execution'],indent=2)+'\n')
 print(json.dumps(report['execution']))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('recipe');p.add_argument('output');p.add_argument('--project-root');a=p.parse_args();main(a.recipe,a.output,a.project_root)
