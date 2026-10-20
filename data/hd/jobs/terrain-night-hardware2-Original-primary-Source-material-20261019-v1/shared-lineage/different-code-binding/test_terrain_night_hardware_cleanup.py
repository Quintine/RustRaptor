from pathlib import Path
import importlib.util, unittest, tempfile, hashlib
import numpy as np
from PIL import Image
p=Path(__file__).with_name('terrain_night_hardware_cleanup.py')
s=importlib.util.spec_from_file_location('night',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Night(unittest.TestCase):
 def setUp(self):
  self.idx=np.full((32,32),25,np.uint8);self.idx[:,0]=31;self.idx[4,4]=252;self.idx[10:15,12:15]=54
  self.pal=np.stack([np.arange(256,dtype=np.uint8)]*3,axis=1);self.pal[31]=[4,4,4];self.pal[252]=[247,56,69]
  yy,xx=np.indices((512,512));self.donor=np.repeat((80+((xx*3+yy*7)%17))[...,None],3,2).astype(float);self.fields={1:self.donor,2:self.donor,3:self.donor}
 def test_exact_black_functional_and_genuine_band(self):
  out,met=m.derive(self.idx,self.pal,self.fields);guide=m.scale_nx(self.idx,4);labels=m.source_labels(guide);owners=np.repeat(np.repeat(labels,4,0),4,1);exact=np.repeat(np.repeat(self.pal[guide],4,0),4,1);mask=(owners==0)|(owners==4)
  self.assertTrue(np.array_equal(out[mask],exact[mask]));self.assertGreater(met['genuine_fine_RGB_changed_nonexcluded_pixels'],0);self.assertEqual(out.shape,(512,512,3));self.assertEqual(met['functional_retention_HD_credit'],0);self.assertEqual(met['opaque_black_HD_credit'],0)
 def test_reject_unhandled_color_or_missing_olive(self):
  bad=self.idx.copy();bad[0,0]=200
  with self.assertRaises(ValueError):m.derive(bad,self.pal,self.fields)
  with self.assertRaises(ValueError):m.derive(self.idx,self.pal,{1:self.donor,2:self.donor})
 def test_unsupported_donor_and_crop(self):
  with self.assertRaises(ValueError):m.donor_field(np.zeros((4,4,3),np.uint8),[0,0,5,3])
  with self.assertRaises(ValueError):m.donor_field(np.zeros((4,4,3),np.uint8),[0.0,0,3,3])
  with self.assertRaises(ValueError):m.decode_source32(b'X'*1044)
 def test_contained_authenticated_io(self):
  with tempfile.TemporaryDirectory(dir=p.parent)as t:
   root=Path(t);(root/'a').write_bytes(b'abc');inputs=m.BufferedInputs(root);binding={'path':'a','sha256':hashlib.sha256(b'abc').hexdigest()};self.assertEqual(inputs.read(binding)[0],b'abc');self.assertEqual(inputs.read(binding)[0],b'abc');self.assertEqual(inputs.physical_reads,1)
   for rel in ('../a','/a','./a','a//b'):
    with self.assertRaises(ValueError):m.read_contained(root,rel)
   (root/'sym').symlink_to(root/'a')
   with self.assertRaises(OSError):m.read_contained(root,'sym')
   with self.assertRaises(ValueError):m.BufferedInputs(root).read({'path':'a','sha256':'0'*64})
 def test_deterministic_synthetic_and_functional_union(self):
  a,one=m.derive(self.idx,self.pal,self.fields);b,two=m.derive(self.idx,self.pal,self.fields);self.assertTrue(np.array_equal(a,b));self.assertEqual(one,two);self.assertEqual(one['original_detail_cells'],sorted(one['original_detail_cells']));self.assertIn([4,4],one['original_detail_cells'])
if __name__=='__main__':unittest.main()
