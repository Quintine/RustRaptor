import unittest,tempfile
from pathlib import Path
import numpy as np
import hd_water_material10521 as m
class Water(unittest.TestCase):
 def setUp(self):
  self.idx=np.full((32,32),227,np.uint8);self.idx[:16]=157;self.idx[4,5]=241;self.pal=np.repeat(np.arange(256,dtype=np.uint8)[:,None],3,axis=1);self.old=np.random.default_rng(1).integers(0,256,(724,724,3),dtype=np.uint8);self.donor=np.random.default_rng(2).integers(0,256,(887,887,3),dtype=np.uint8)
 def test_nonwater_exact_and_generated_contribution(self):
  out,a=m.derive(self.idx,self.pal,self.old,self.donor);self.assertTrue(np.array_equal(out[362:],self.old[362:]));self.assertGreater(a['genuine_fine_band_changed_water_pixels'],0);self.assertEqual(a['nonwater_changed_pixels'],0);self.assertTrue(a['Original_protected_RGB_exact']);self.assertIn([5,4],a['original_detail_cells'])
 def test_determinism_and_genuine_donor_effect(self):
  a,_=m.derive(self.idx,self.pal,self.old,self.donor);b,_=m.derive(self.idx,self.pal,self.old,self.donor);self.assertTrue(np.array_equal(a,b));d=self.donor[::-1].copy();c,_=m.derive(self.idx,self.pal,self.old,d);self.assertTrue(np.any(a[:362]!=c[:362]));self.assertTrue(np.array_equal(a[362:],c[362:]))
 def test_mask_cannot_change_dock(self):
  self.idx[16,2]=157
  with self.assertRaises(ValueError):m.derive(self.idx,self.pal,self.old,self.donor)
 def test_reject_wrong_dimensions(self):
  with self.assertRaises(ValueError):m.derive(self.idx,self.pal,self.old[:512],self.donor)
 def test_symlink_and_escape_inputs_rejected(self):
  with tempfile.TemporaryDirectory()as t:
   p=Path(t);(p/'a').write_bytes(b'x');(p/'b').symlink_to(p/'a')
   with self.assertRaises(OSError):m.read_contained(p,'b')
   with self.assertRaises(ValueError):m.read_contained(p,'../a')
if __name__=='__main__':unittest.main()
