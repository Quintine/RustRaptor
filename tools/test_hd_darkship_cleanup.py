import hashlib,io,json,os,struct,subprocess,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from PIL import Image
import hd_darkship_cleanup as m
class Contract(unittest.TestCase):
 def family(self,name):
  ids=['102fc']if name=='SHIP05-singleton'else['2009a','2009b']
  return dict(format_version=1,family=name,palette={'path':'data/misc/PALETTE_DAT','sha256':m.PALETTE},dependencies={k:{'path':'tools/'+k+'.py','sha256':v}for k,v in m.PINS.items()},frames=[dict(asset=a,source={'path':'data/source'+a,'sha256':m.SPEC[a][1]},raw_png={'path':'data/raw-singleton.png'if a=='102fc'else'data/raw-rotor.png','sha256':m.SPEC[a][2]},viewport=m.SPEC[a][3],origin=[0,0],functional_original_cells=m.SPEC[a][4])for a in ids])
 def bundle(self):return dict(format_version=1,families=[self.family(n)for n in ('SHIP05-singleton','SHIP03-rotor2')])
 def test_exact_two_families(self):
  for f in self.bundle()['families']:self.assertEqual(m.validate_recipe(f),[x['asset']for x in f['frames']])
 def test_partial_rotor_rejected(self):
  r=self.family('SHIP03-rotor2');r['frames'].pop()
  with self.assertRaises(ValueError):m.validate_recipe(r)
 def test_bundle_wrong_order_before_reads(self):
  b=self.bundle();b['families'].reverse()
  with patch.object(m,'read',side_effect=AssertionError('not read')):
   with self.assertRaises(ValueError):m.derive_bundle(b,Path('/'))
 def test_origin_crop_selectors_fixed(self):
  for key,value in [('origin',[1,0]),('viewport',[57,29,1377,1084]),('functional_original_cells',[[27,12]])]:
   r=self.family('SHIP05-singleton');r['frames'][0][key]=value
   with self.assertRaises(ValueError):m.validate_recipe(r)
 def test_bool_geometry_rejected(self):
  r=self.family('SHIP05-singleton');r['frames'][0]['origin']=[False,0]
  with self.assertRaises(ValueError):m.validate_recipe(r)
 def test_wrong_dependency_hash(self):
  r=self.family('SHIP05-singleton');r['dependencies']['hd_frame_policy']['sha256']='0'*64
  with self.assertRaises(ValueError):m.validate_recipe(r)
 def test_read_relative_sha_bound(self):
  with tempfile.TemporaryDirectory()as d:
   p=Path(d)/'source';p.write_bytes(b'abc');b={'path':'source','sha256':m.sha(b'abc')};self.assertEqual(m.read(b,d),b'abc')
   with self.assertRaises(ValueError):m.read(b,d,2)
   with self.assertRaises(ValueError):m.read(b|{'sha256':'0'*64},d)
 def test_bad_routes_rejected(self):
  for route in ('/tmp/a','../a','a/../b','a\\b','a//b','a/./b',''):
   with self.subTest(route=route),self.assertRaises(ValueError):m.read({'path':route,'sha256':'0'*64},'/')
 def test_symlinks_rejected(self):
  with tempfile.TemporaryDirectory()as d:
   p=Path(d);(p/'actual').mkdir();(p/'actual/f').write_bytes(b'x');(p/'alias').symlink_to('actual',target_is_directory=True);(p/'last').symlink_to('actual/f')
   for route in ('alias/f','last'):
    with self.assertRaises(OSError):m.read({'path':route,'sha256':m.sha(b'x')},p)
 def test_fifo_rejected_without_blocking(self):
  with tempfile.TemporaryDirectory()as d:
   os.mkfifo(Path(d)/'fifo')
   code="import sys;sys.path.insert(0,sys.argv[1]);import hd_darkship_cleanup as m\ntry:m.read({'path':'fifo','sha256':'0'*64},sys.argv[2])\nexcept ValueError:print('REJECTED');sys.exit(0)\nraise SystemExit('FIFO unexpectedly accepted')"
   z=subprocess.run([sys.executable,'-c',code,str(Path(m.__file__).parent),d],capture_output=True,text=True,timeout=2)
   self.assertEqual(z.returncode,0,z.stderr);self.assertEqual(z.stdout.strip(),'REJECTED')
 def test_existing_output_before_recipe_read(self):
  with tempfile.TemporaryDirectory()as d:
   with self.assertRaises(ValueError):m.main('absent',d,d)
 def test_outside_recipe_rejected(self):
  with tempfile.TemporaryDirectory()as d:
   with self.assertRaises(ValueError):m.main('/outside/recipe',str(Path(d)/'new'),d)
 def test_disk_floor_before_recipe_read(self):
  with tempfile.TemporaryDirectory()as d,patch.object(m.shutil,'disk_usage',return_value=types.SimpleNamespace(free=2_207_999_999)):
   with self.assertRaises(ValueError):m.main('absent',str(Path(d)/'new'),d)
 def test_actual_reviewed_dependencies_bundle_synthetic_assets_no_reopen(self):
  toolroot=Path(m.__file__).resolve().parent;payloads={n:(toolroot/(n+'.py')).read_bytes()for n in m.PINS};self.assertTrue(all(m.sha(payloads[n])==h for n,h in m.PINS.items()))
  def source(w):return struct.pack('<iiiii',0,0,0,w,32)+b''.join(struct.pack('<iiii',0,y,y*w,w)+bytes([10])*w for y in range(32))+struct.pack('<iiii',0,0,-1,0)
  def raw(w,h):
   a=np.zeros((h,w,4),np.uint8);a[:,:,0]=120;a[:,:,1]=80;a[:,:,2]=150;a[:,:,3]=255;b=io.BytesIO();Image.fromarray(a).save(b,format='PNG');return b.getvalue()
  data={'data/misc/PALETTE_DAT':bytes(768),'data/source102fc':source(40),'data/source2009a':source(48),'data/source2009b':source(48),'data/raw-singleton.png':raw(1402,1122),'data/raw-rotor.png':raw(1024,1536)}|{'tools/'+n+'.py':b for n,b in payloads.items()};calls=[]
  def read(binding,*args):calls.append(binding['path']);return data[binding['path']]
  with patch.object(m,'read',side_effect=read),patch.object(Path,'read_bytes',side_effect=AssertionError('no path reopen')):
   out,report=m.derive_bundle(self.bundle(),Path('/synthetic'))
  self.assertEqual(set(out),{'102fc','2009a','2009b'});self.assertEqual(len(calls),9);self.assertEqual(len(set(calls)),9);self.assertEqual(report['unique_buffered_inputs'],9)
  self.assertEqual(report['family_reports'][0]['geometry']['decoder_module']['sha256'],m.PINS['hd_frame_policy']);self.assertEqual(report['family_reports'][1]['geometry']['decoder_module']['path'],'tools/hd_frame_policy.py')
 def test_dependency_bytes_rejected(self):
  with self.assertRaises(ValueError):m.modules({k:b'wrong'for k in m.PINS})
if __name__=='__main__':unittest.main()
