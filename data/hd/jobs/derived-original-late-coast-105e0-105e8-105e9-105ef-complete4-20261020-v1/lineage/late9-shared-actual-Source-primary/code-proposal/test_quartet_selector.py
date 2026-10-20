import unittest,json,tempfile,hashlib
from pathlib import Path
from unittest.mock import patch
import numpy as np
import terrain_component_cleanup as m
class QuartetSelectorTests(unittest.TestCase):
 def source(self):
  a=np.full((32,32),197,np.uint8);a[:8,:8]=15;a[:8,8:16]=31;a[:8,16:]=154;a[8:16,:]=82;a[16:24,:]=43;a[24:,:]=55;a[2,24]=241;return a
 def palette(self):return np.repeat(np.arange(256,dtype=np.uint8)[:,None],3,axis=1)
 def fields(self):
  y,x=np.indices((512,512));return{i:np.stack([(x*19+y*11+i*7)%256,(x*13+y*17)%256,(x*3+y*7)%256],-1).astype(float)for i in range(6)}
 def test_explicit_six_material_classes_and_protected(self):
  self.assertEqual(m.quartet_material_labels(np.array([[15,31,154,241,197,220,82,43,55,245,255]],np.uint8)).tolist(),[[0,0,1,1,2,2,3,4,5,6,6]])
 def test_unknown_ordinary_rejected(self):
  for v in [64,79,96,100,111,147,160,181]:
   with self.assertRaises(ValueError):m.quartet_material_labels(np.array([[v]],np.uint8))
 def test_actual_four_source_material_and_complete_functional_union(self):
  d=Path(__file__).parent/'inputs'
  for aid in m.QUARTET_IDS:
   a=m.decode_source32((d/(aid+'.pic')).read_bytes());m.quartet_material_labels(a);self.assertEqual(m.functional_support_union(a),[[6,28]]if aid=='105dd'else[])
 def test_exact_source_owners_and_functional_water(self):
  a=self.source();p=self.palette();out,owners,protected,stats=m.derive_quartet_tile(a,p,self.fields());guide=m.scale_nx(a,4);self.assertTrue(np.array_equal(owners,np.repeat(np.repeat(m.quartet_material_labels(guide),4,0),4,1)));self.assertTrue(np.array_equal(out[protected],np.repeat(np.repeat(p[guide],4,0),4,1)[protected]));self.assertGreater(stats['genuine_RGB_band_changed_nonfunctional_HDR_pixels'],0);self.assertEqual(stats['Original_functional_HD_credit'],0)
 def test_yellow_donor_does_not_change_painted_forks_or_water_or_braces(self):
  a=self.source();f=self.fields();p=self.palette();out,owners,_,_=m.derive_quartet_tile(a,p,f);f[5]=255-f[5];other,_,_,_=m.derive_quartet_tile(a,p,f);self.assertTrue(np.array_equal(out[owners!=5],other[owners!=5]));self.assertTrue(np.any(out[owners==5]!=other[owners==5]))
 def test_gray_structure_stays_achromatic(self):
  out,owners,_,_=m.derive_quartet_tile(self.source(),self.palette(),self.fields());x=out[owners==0];self.assertTrue(np.array_equal(x[:,0],x[:,1]));self.assertTrue(np.array_equal(x[:,1],x[:,2]))
 def test_zero_generated_band_is_original_only_rejected(self):
  with self.assertRaisesRegex(ValueError,'Original-only'):m.derive_quartet_tile(self.source(),self.palette(),{i:np.full((512,512,3),80.,float)for i in range(6)})
 def test_incomplete_quartet_rejected_before_output(self):
  with tempfile.TemporaryDirectory()as d:
   d=Path(d);p=bytes(768);(d/'pal').write_bytes(p);rec={'method':m.METHOD,'operation':'first-quartet-tiles','palette':{'path':'pal','sha256':hashlib.sha256(p).hexdigest()},'sources':[{'asset':'105d3'}]};(d/'recipe.json').write_text(json.dumps(rec))
   with patch('sys.argv',['tool','--recipe',str(d/'recipe.json'),'--output',str(d/'none')]),self.assertRaisesRegex(ValueError,'complete selected quartet'):m.main()
   self.assertFalse((d/'none').exists())
if __name__=='__main__':unittest.main()
