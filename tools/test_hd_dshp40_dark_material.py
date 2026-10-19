import importlib.util,unittest,tempfile,hashlib,os,subprocess,sys,json,struct,io,copy
from pathlib import Path
from unittest.mock import patch
import numpy as np
from PIL import Image
HERE=Path(__file__).resolve().parent;R=HERE.parent
spec=importlib.util.spec_from_file_location('subject',HERE/'hd_dshp40_dark_material.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Tests(unittest.TestCase):
 def setUp(self):self.t=tempfile.TemporaryDirectory();self.p=Path(self.t.name)
 def tearDown(self):self.t.cleanup()
 def b(self,name='input',data=b'hello'):
  (self.p/name).write_bytes(data);return {'path':name,'sha256':m.sha(data)}
 def test_read_regular(self):self.assertEqual(m.read(self.b(),self.p),b'hello')
 def test_read_hash(self):
  b=self.b();b['sha256']='0'*64
  with self.assertRaises(ValueError):m.read(b,self.p)
 def test_absolute(self):
  b=self.b();b['path']=str(self.p/'input')
  with self.assertRaises(ValueError):m.read(b,self.p)
 def test_parent_traversal(self):
  with self.assertRaises(ValueError):m.read({'path':'../x','sha256':'0'*64},self.p)
 def test_symlink_final(self):
  b=self.b();(self.p/'link').symlink_to('input');b['path']='link'
  with self.assertRaises(OSError):m.read(b,self.p)
 def test_symlink_directory(self):
  (self.p/'real').mkdir();(self.p/'link').symlink_to('real');(self.p/'real/x').write_bytes(b'x')
  with self.assertRaises(OSError):m.read({'path':'link/x','sha256':m.sha(b'x')},self.p)
 def test_directory(self):
  (self.p/'d').mkdir()
  with self.assertRaises(ValueError):m.read({'path':'d','sha256':'0'*64},self.p)
 def test_bound(self):
  with self.assertRaises(ValueError):m.read(self.b(data=b'abcd'),self.p,3)
 def test_FIFO_bounded(self):
  os.mkfifo(self.p/'pipe');code="import importlib.util,sys;from pathlib import Path;s=importlib.util.spec_from_file_location('x',sys.argv[1]);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);m.read({'path':'pipe','sha256':'0'*64},Path(sys.argv[2]))"
  z=subprocess.run([sys.executable,'-c',code,str(HERE/'hd_dshp40_dark_material.py'),str(self.p)],capture_output=True,timeout=3);self.assertNotEqual(z.returncode,0);self.assertIn(b'bounded regular',z.stderr)
 def cap(self,rgb,label=1,source_rgb=(10,20,30)):
  a=np.array([[list(rgb)+[255]]],np.uint8);s=np.array([[label]],np.uint16);pal=np.zeros((256,3),np.uint8);pal[label]=source_rgb;return a,s,pal
 def test_integer_cap(self):
  a,s,p=self.cap((100,50,25));o,r=m.cap_material(a,s,p);self.assertEqual(o[0,0].tolist(),[42,21,10,255]);self.assertEqual(r['literal_Original_RGB_replacements'],0)
 def test_below_unchanged(self):
  a,s,p=self.cap((42,1,0));o,r=m.cap_material(a,s,p);self.assertTrue(np.array_equal(a,o));self.assertEqual(r['changed_generated_RGB_samples'],0)
 def test_black_occupied(self):
  a,s,p=self.cap((90,45,0),source_rgb=(0,0,0));o,r=m.cap_material(a,s,p);self.assertEqual(o[0,0].tolist(),[12,6,0,255])
 def test_transparent_exact(self):
  a=np.array([[[23,24,25,0]]],np.uint8);o,r=m.cap_material(a,np.array([[256]],np.uint16),np.zeros((256,3),np.uint8));self.assertTrue(np.array_equal(a,o))
 def test_uint32_no_overflow(self):
  a,s,p=self.cap((255,254,253),source_rgb=(180,170,170));o,r=m.cap_material(a,s,p);self.assertEqual(o[0,0].tolist(),[192,191,190,255])
 def test_wrong_alpha(self):
  a,s,p=self.cap((100,50,0));a[0,0,3]=254
  with self.assertRaises(ValueError):m.cap_material(a,s,p)
 def test_unclipped_high_Source(self):
  a,s,p=self.cap((255,220,200),source_rgb=(255,255,255));o,r=m.cap_material(a,s,p);self.assertTrue(np.array_equal(a,o))
 def test_input_immutable(self):
  a,s,p=self.cap((200,150,100));old=a.copy();m.cap_material(a,s,p);self.assertTrue(np.array_equal(old,a))
 def test_dependency_auth(self):
  with self.assertRaises(ValueError):m.modules({k:b'x'for k in m.PINS})
 def recipe_for_asset(self,asset):return dict(format_version=1,asset=asset,palette={'path':'pal','sha256':m.PALETTE},source={'path':'source','sha256':m.SPEC[asset][0]},raw_png={'path':'raw.png','sha256':m.SPEC[asset][1]},dependencies={k:{'path':'tools/'+k+'.py','sha256':v}for k,v in m.PINS.items()},viewport=[0,0,1402,1122],origin=[0,0],brightness_slack=12,donor_bound=m.DONOR_BOUND[asset])
 def recipe(self):return self.recipe_for_asset('30097')
 def test_refuse_recipe_tuning(self):
  r=self.recipe();r['brightness_slack']=13
  with self.assertRaises(ValueError):m.validate_recipe(r)
 def test_refuse_alias(self):
  r=self.recipe();r['asset']='30096'
  with self.assertRaises(ValueError):m.validate_recipe(r)
 def test_per_actor_donor_bound_is_source_fixed(self):
  for asset,bound in [('30097',14),('30099',12),('3009e',14)]:
   r=self.recipe_for_asset(asset);self.assertEqual(r['donor_bound'],bound);m.validate_recipe(r)
 def test_refuse_wrong_actor_donor_bound(self):
  r=self.recipe();r['donor_bound']=12
  with self.assertRaises(ValueError):m.validate_recipe(r)
 def test_actual_dependency_synthetic_derive_no_Path_reopen(self):
  # Actual authenticated dependency CODE, synthetic Source/raw only.
  deps={}
  for k in m.PINS:deps[k]=self.b(k+'.py',(R/'tools'/f'{k}.py').read_bytes())
  pb=bytes([1])*768;pal=self.b('pal',pb) # Synthetic six-bit palette only.
  source=struct.pack('<iiiii',0,0,0,40,32)+b''.join(struct.pack('<iiii',0,y,y*40,40)+bytes([31])*40 for y in range(32))+struct.pack('<iiii',0,0,-1,0);sb=self.b('source',source)
  rgba=np.empty((1122,1402,4),np.uint8);rgba[:]=[100,50,25,255];bio=io.BytesIO();Image.fromarray(rgba).save(bio,format='PNG');raw=self.b('raw.png',bio.getvalue())
  r=dict(format_version=1,palette=pal,source=sb,raw_png=raw,dependencies=deps,asset='30097',viewport=[0,0,1402,1122],origin=[0,0],brightness_slack=12,donor_bound=14)
  with patch.object(m,'PALETTE',pal['sha256']),patch.dict(m.SPEC,{'30097':(sb['sha256'],raw['sha256'])}),patch.object(Path,'read_bytes',side_effect=AssertionError('unexpected Path reopen')):
   out,report=m.derive(r,self.p)
  self.assertEqual(out.shape,(128,160,4));self.assertTrue(np.all(out==np.array([16,8,4,255],np.uint8)));self.assertEqual(report['unique_authenticated_buffered_inputs'],5);self.assertEqual(report['geometry']['frames'][0]['filled_generated_RGB_samples'],0)
if __name__=='__main__':unittest.main(verbosity=2)
