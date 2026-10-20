import copy,hashlib,importlib.util,io,json,os,struct,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from PIL import Image
HERE=Path(__file__).parent
spec=importlib.util.spec_from_file_location('subject',HERE/'hd_dark_terrain_six.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
R=next(p for p in HERE.parents if(p/'tools/hd_terrain_retexture.py').is_file())
RECIPE={'format_version': 1, 'method': 'six-dark-Source-gray-lavender-generated-fine-mid-buffered-v1', 'dependencies': {'hd_terrain_retexture': {'path': 'tools/hd_terrain_retexture.py', 'sha256': '0e4d7d5a4f7a7ddf6e396e757691156dfc74d231d9925744c342078532b89a98'}, 'hd_terrain_group_retexture': {'path': 'tools/hd_terrain_group_retexture.py', 'sha256': '24e3751d26090699f2d8d317ed98f73e05f51f3caa6dc2bf21fc40a109068a27'}}, 'palette': {'path': 'synthetic-palette.rgb', 'sha256': '1cf6adb926d1dee1888b3e3d33b51a7049b3e5eb5f90a3067ef71c8970547204'}, 'parameters': {'output_side': 512, 'source_sigma': 3.0, 'residual_sigma_fine': 0.65, 'residual_sigma_coarse': 10.0, 'residual_percentile': 80.0}, 'material_groups': [{'name': 'pale', 'indices': [1], 'texture_log_gain': 0.06, 'quiet_from_source_variance': True}, {'name': 'gray', 'indices': [16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27], 'texture_log_gain': 0.38, 'quiet_from_source_variance': True}, {'name': 'floor', 'indices': [28, 29, 30, 31], 'texture_log_gain': 0.38, 'quiet_from_source_variance': True}, {'name': 'lavender', 'indices': [113], 'texture_log_gain': 0.06, 'quiet_from_source_variance': True}], 'frames': [{'asset': '301c3', 'Source': {'path': 'synthetic-Source-301c3.pic', 'sha256': '9c370900214a601e40200cb67e959f042323d001f7a2e6de3627e5044a2078b5'}, 'parent_raw': {'path': 'synthetic-parent-301c3.png', 'sha256': 'dc4244108b9e760f324f4279e530ef2e02a799b087fe21570668c345fbe37b43'}, 'origin': [0, 0], 'crop': [0, 0, 1254, 1254]}, {'asset': '301c8', 'Source': {'path': 'synthetic-Source-301c8.pic', 'sha256': '4d87a0251b8b064c6ab5835ae31f5eaabfec405f56b0408980f93484b70470d1'}, 'parent_raw': {'path': 'synthetic-parent-301c8.png', 'sha256': '8b6d719ecd4762156a81e9f0173ccea0dcfd9d1967b3fae6f04f82d6aba9297d'}, 'origin': [0, 0], 'crop': [0, 0, 1254, 1254]}, {'asset': '301cc', 'Source': {'path': 'synthetic-Source-301cc.pic', 'sha256': 'be151484d73ebe4461115391c3fcea20f109a14b0f2eee1ce13f1cbb34014355'}, 'parent_raw': {'path': 'synthetic-parent-301cc.png', 'sha256': 'e2cf0453dfc61b5729ef9c968bf48dc6dc3deb42e1fa6e1e520904ebf4f6e502'}, 'origin': [0, 0], 'crop': [0, 0, 1254, 1254]}]}
def ref(path,payload):return {'path':path,'sha256':m.sha(payload)}
class Inputs(unittest.TestCase):
 def setUp(self):self.t=tempfile.TemporaryDirectory();self.root=Path(self.t.name);self.payload=b'abc';(self.root/'a').write_bytes(self.payload)
 def tearDown(self):self.t.cleanup()
 def test_regular(self):self.assertEqual(m.read_contained(self.root,'a'),b'abc')
 def test_absolute(self):
  with self.assertRaises(ValueError):m.read_contained(self.root,str(self.root/'a'))
 def test_parent(self):
  with self.assertRaises(ValueError):m.read_contained(self.root,'../a')
 def test_dot(self):
  with self.assertRaises(ValueError):m.read_contained(self.root,'./a')
 def test_double_slash(self):
  with self.assertRaises(ValueError):m.read_contained(self.root,'a//b')
 def test_backslash(self):
  with self.assertRaises(ValueError):m.read_contained(self.root,'x\\a')
 def test_leaf_symlink(self):
  (self.root/'link').symlink_to(self.root/'a')
  with self.assertRaises(OSError):m.read_contained(self.root,'link')
 def test_directory_symlink(self):
  (self.root/'real').mkdir();(self.root/'link').symlink_to(self.root/'real',target_is_directory=True)
  with self.assertRaises(OSError):m.read_contained(self.root,'link/a')
 def test_directory(self):
  with self.assertRaises(ValueError):m.read_contained(self.root,'a/..')
 def test_fifo_cli_bounded(self):
  os.mkfifo(self.root/'fifo');cmd=[sys.executable,str(HERE/'hd_dark_terrain_six.py'),'fifo','0'*64,str(self.root),str(self.root/'out')];p=subprocess.run(cmd,capture_output=True,timeout=3);self.assertNotEqual(p.returncode,0);self.assertIn(b'bounded regular',p.stderr)
 def test_size(self):
  with self.assertRaises(ValueError):m.read_contained(self.root,'a',2)
 def test_hash(self):
  with self.assertRaises(ValueError):m.BufferedInputs(self.root).read(ref('a',b'bad'))
 def test_buffer_after_path_replacement(self):
  b=m.BufferedInputs(self.root);f=ref('a',b'abc');self.assertEqual(b.read(f),b'abc');(self.root/'a').unlink();(self.root/'a').write_bytes(b'new');self.assertEqual(b.read(f),b'abc');self.assertEqual(b.physical_reads,1)
  with self.assertRaises(ValueError):b.read(ref('a',b'new'))
class Math(unittest.TestCase):
 def test_fixed_parameters(self):
  r=copy.deepcopy(RECIPE);r['parameters']['source_sigma']=2
  with self.assertRaises(ValueError):m.validate_recipe(r)
 def test_old_raw_rejected(self):
  r=copy.deepcopy(RECIPE);r['frames'][0]['parent_raw']['sha256']='0'*64
  with self.assertRaises(ValueError):m.validate_recipe(r)
 def test_cohort_order(self):
  r=copy.deepcopy(RECIPE);r['frames'].reverse()
  with self.assertRaises(ValueError):m.validate_recipe(r)
 def test_source_and_origin(self):
  r=copy.deepcopy(RECIPE);r['frames'][0]['origin']=[1,0]
  with self.assertRaises(ValueError):m.validate_recipe(r)
 def test_no_dependency_substitution(self):
  with self.assertRaises(ValueError):m.modules({k:b'x'for k in m.DEPENDENCIES})
 def test_alpha_hole(self):
  a=np.full((1254,1254,4),255,np.uint8);a[1,1,3]=0;b=io.BytesIO();Image.fromarray(a).save(b,format='PNG')
  with self.assertRaises(ValueError):m.decode_png(b.getvalue())
 def test_synthetic_full_derive_real_dependencies_no_reopen(self):
  with tempfile.TemporaryDirectory()as t:
   root=Path(t);(root/'tools').mkdir();r=copy.deepcopy(RECIPE);pins={};deps={}
   for name in m.DEPENDENCIES:
    b=(R/'tools'/f'{name}.py').read_bytes();deps[name]=b;(root/'tools'/f'{name}.py').write_bytes(b)
   # Authentic code; entirely synthetic Original PIC/palette/provider data.
   pal=np.tile(np.arange(64,dtype=np.uint8),12).reshape(256,3).tobytes();(root/'pal').write_bytes(pal);r['palette']=ref('pal',pal)
   y,x=np.indices((1254,1254));rgb=np.stack(((x*7+y*11)%256,(x*5+y*3)%256,(x*13+y*9)%256),axis=2).astype(np.uint8);b=io.BytesIO();Image.fromarray(rgb).save(b,format='PNG');raw=b.getvalue();(root/'raw.png').write_bytes(raw)
   for n,f in enumerate(r['frames']):
    a=np.full((32,32),25,np.uint8);a[2:14,3:17]=18+n;a[15:17,4:6]=113;source=struct.pack('<5i',1,1,0,32,32)+a.tobytes();name='source'+str(n);(root/name).write_bytes(source);f['Source']=ref(name,source);f['parent_raw']=ref('raw.png',raw);pins[f['asset']]=[m.sha(source),m.sha(raw)]
   with patch.object(m,'PINS',pins),patch.object(m,'PALETTE',m.sha(pal)),patch.object(Path,'read_bytes',side_effect=AssertionError('path reopen forbidden')):
    outputs,report=m.derive(r,root)
   self.assertEqual(len(outputs),3);self.assertEqual(report['physical_authenticated_input_reads'],7)
   self.assertFalse(np.array_equal(outputs[0][1],outputs[1][1]))
   for aid,out in outputs:self.assertEqual(out.shape,(512,512,3))
   for f in report['assets']:
    self.assertGreater(f['metrics']['pixels_changed_from_Source_guided_base'],2621);self.assertGreater(f['metrics']['coherent_parent_band_std'],.25);self.assertTrue(f['original_detail_cells']);self.assertEqual(f['retained_Source_cells_HD_credit'],0)
   # Low-level authentic pure reconstruction: zero/flat parents cannot pretend HD.
   k,g=(m.modules(deps)[n]for n in ('hd_terrain_retexture','hd_terrain_group_retexture'));idx=np.full((32,32),25,np.uint8);palette=k.palette_rgb(pal)
   with self.assertRaises(ValueError):g.reconstruct(idx,palette,np.zeros((1254,1254,3),np.uint8),m.PARAMETERS,m.GROUPS,k)
if __name__=='__main__':unittest.main(verbosity=2)
