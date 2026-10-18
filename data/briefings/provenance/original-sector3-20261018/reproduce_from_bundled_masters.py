"""Offline exact regeneration from bundled Sector3 masters and checked recipes."""
from pathlib import Path,PurePosixPath
import argparse,hashlib,io,json,os,platform,shutil,stat,zlib
from PIL import Image,__version__ as PILLOW_VERSION
BUNDLE='data/briefings/provenance/original-sector3-20261018'
RECIPE_SHA256={'1': '90511315f02117950a903582df9b94db7105b1985149375c83f864b04c48547f', '2': 'b1256169f0af006c954933452a07c0e986a37af166b42ae5a66a534624f2e120', '3': '00a0af132ad17889b54ac720a9940036796f70e9406161d4c8d00d33e3743a95', '4': 'f32aeb1312addfc60946d4b87370222feae4c49153f2b74aff69088ff6b73554', '5': '566a75a0b41d48b0fdfbb911b60285ae1ff5760c04e5107c8eeef201c419b29f', '6': 'b7041b093933354ff369eb6d47109c66f16443ccd41738fc01f1619f3a664493', '7': '1780304867a6bc3fde55d17ec5ad88556a9727ec9a1092ce04d639a6b88c6872', '8': 'b9bf0848c86ae452a465e497bcfa9f10e982fd67470968152808796174ea6b70', '9': 'bffc8702a45025c0aec029ccf3a9e56e340afcae300ab38f8316c16e45416f4c'}

def digest(b):return hashlib.sha256(b).hexdigest()
def relative(name):
 if type(name)is not str or not name or '\\'in name or ':'in name:raise ValueError('normalized POSIX relative path required')
 p=PurePosixPath(name)
 if p.is_absolute() or any(x in ('','.','..')for x in name.split('/'))or str(p)!=name:raise ValueError('contained relative path required')
 return p

def contained(root,name):
 p=root
 for part in relative(name).parts:
  p=p/part
  if p.is_symlink():raise ValueError('symlink component rejected')
 if not p.resolve(strict=False).is_relative_to(root):raise ValueError('path escaped project')
 return p

def checked(root,name,expected):
 p=contained(root,name);fd=os.open(p,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
 try:
  before=os.fstat(fd)
  if not stat.S_ISREG(before.st_mode)or before.st_size>32*1024*1024:raise ValueError('bounded regular file required')
  with os.fdopen(fd,'rb',closefd=False)as f:body=f.read()
  after=os.fstat(fd)
 finally:os.close(fd)
 key=lambda s:(s.st_dev,s.st_ino,s.st_mode,s.st_size,s.st_mtime_ns)
 if key(before)!=key(after)or digest(body)!=expected:raise ValueError('input changed or SHA mismatch')
 return body

def regenerate(project,output_relative):
 project=Path(project).resolve(strict=True);output=contained(project,output_relative)
 if output.exists()or output.is_symlink():raise ValueError('fresh output directory required; no overwrite')
 if not output.parent.is_dir():raise ValueError('output parent must exist')
 payloads={};records=[]
 for wave in range(1,10):
  stem=f'sector_3_wave_{wave}';recipe_path=BUNDLE+f'/provenance/{stem}-derivation.json'
  recipe=json.loads(checked(project,recipe_path,RECIPE_SHA256[str(wave)]))
  if recipe['wave']!=wave or recipe['master']['path']!=f'masters/{stem}-untouched-master.png':raise ValueError('recipe identity changed')
  master_path=BUNDLE+'/'+recipe['master']['path'];body=checked(project,master_path,recipe['master']['sha256'])
  with Image.open(io.BytesIO(body))as image:
   if image.format!='PNG'or list(image.size)!=recipe['master']['size']or image.width*image.height>4194304:raise ValueError('master PNG dimensions changed')
   rgb=image.convert('RGB');hd=rgb.resize((1280,800),Image.Resampling.LANCZOS,box=tuple(recipe['HD_float_source_crop_box']));sd=hd.resize((320,200),Image.Resampling.LANCZOS)
  outputs={}
  for label,image in [('HD',hd),('SD',sd)]:
   name=f'{stem}_{label.lower()}.png'
   if recipe[label]['path']!='data/briefings/'+name:raise ValueError('runtime asset identity changed')
   buf=io.BytesIO();image.save(buf,format='PNG');png=buf.getvalue()
   if digest(png)!=recipe[label]['sha256']:raise ValueError('reproduced PNG differs; use matching Pillow/PNG compression runtime')
   payloads[name]=png;outputs[label]={'file':name,'PNG_sha256':digest(png),'RGB_sha256':digest(image.tobytes()),'size':list(image.size)}
  records.append({'wave':wave,'recipe':recipe_path,'recipe_sha256':RECIPE_SHA256[str(wave)],'master':master_path,'master_sha256':recipe['master']['sha256'],'outputs':outputs})
 # All18 outputs pass before writing any files. Provider paths/receipts are never accessed.
 report={'status':'PASS_OFFLINE_ALL9_HD_SD_PNG_BYTES_EXACT','records':records,'provider_access_required':False,'only_inputs':'9 bundled masters +9 checked crop recipes','runtime':{'python':platform.python_version(),'pillow':PILLOW_VERSION,'zlib':zlib.ZLIB_RUNTIME_VERSION}}
 output.mkdir()
 try:
  for name,body in payloads.items():(output/name).write_bytes(body)
  (output/'OFFLINE-REPRODUCTION.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
 except BaseException:
  shutil.rmtree(output);raise
 return report

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('project_root',type=Path);p.add_argument('fresh_output_relative');a=p.parse_args();r=regenerate(a.project_root,a.fresh_output_relative);print(json.dumps({'status':r['status'],'images':18,'provider_access_required':False}))
