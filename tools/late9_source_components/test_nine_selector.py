import unittest,json,tempfile,hashlib
from pathlib import Path
from unittest.mock import patch
import numpy as np
import terrain_component_cleanup as m
from test_late_selector import original_pic
class NineSelectorTests(unittest.TestCase):
 def source(self):
  a=np.full((32,32),152,np.uint8);a[:12,:12]=197;a[:12,12:]=226;a[12:24,12:]=82;a[24:,12:]=18
  for i,value in enumerate([240,244,245,249,250,255]):a[2+i,2]=value
  return a
 def palette(self):return np.stack([np.arange(256,dtype=np.uint8),np.arange(256,dtype=np.uint8)[::-1],np.arange(256,dtype=np.uint8)],-1)
 def fields(self):
  y,x=np.indices((512,512));return {i:np.stack([(x*19+y*11+i*7)%256,(x*13+y*17)%256,(x*3+y*7)%256],-1).astype(float)for i in range(5)}
 def test_explicit_actual_148_191_and_all_protected_classes(self):
  a=np.array([[148,191,173,82,240,244,245,249,250,255]],np.uint8);self.assertEqual(m.nine_material_labels(a).tolist(),[[0,2,1,4,0,0,5,5,5,5]])
 def test_unknown_ordinary_material_rejected(self):
  for index in [32,64,96,147,160,181]:
   with self.assertRaises(ValueError):m.nine_material_labels(np.array([[index]],np.uint8))
 def test_full_functional_union_covers_scalenx_spill(self):
  a=np.full((32,32),152,np.uint8);a[8,8]=a[8,9]=a[9,8]=244;cells=m.functional_support_union(a);self.assertIn([9,9],cells);self.assertEqual(len(cells),4)
 def test_actual_nine_source_union_counts_match_independent_source_plan(self):
  root=Path(__file__).parent/'inputs';expected={'10502':6,'10504':31,'10506':6,'10508':9,'10509':0,'1050a':11,'1050b':34,'1050c':36,'1050e':33}
  for aid,count in expected.items():self.assertEqual(len(m.functional_support_union(m.decode_source32(original_pic(aid)))),count,aid)
 def test_registered_geometry_protection_and_positive_genuine_band(self):
  a=self.source();pal=self.palette();out,owners,protected,stats=m.derive_nine_tile(a,pal,self.fields());guide=m.scale_nx(a,4);self.assertTrue(np.array_equal(owners,np.repeat(np.repeat(m.nine_material_labels(guide),4,0),4,1)));exact=np.repeat(np.repeat(pal[guide],4,0),4,1);self.assertTrue(np.array_equal(out[protected],exact[protected]));self.assertGreater(stats['genuine_RGB_band_changed_nonfunctional_HDR_pixels'],0);self.assertEqual(stats['Original_functional_HD_credit'],0)
 def test_zero_generated_band_rejected_not_named_HD(self):
  with self.assertRaisesRegex(ValueError,'Original-only'):m.derive_nine_tile(self.source(),self.palette(),{i:np.full((512,512,3),90.,float)for i in range(5)})
 def test_field_selector_missing_component_rejected(self):
  fields=self.fields();del fields[4]
  with self.assertRaises(ValueError):m.derive_nine_tile(self.source(),self.palette(),fields)
 def test_foreign_or_incomplete_source_cohort_rejected_before_art(self):
  with tempfile.TemporaryDirectory()as d:
   root=Path(d);pb=bytes(768);(root/'pal').write_bytes(pb);recipe={'method':m.METHOD,'operation':'nine-tiles','palette':{'path':'pal','sha256':hashlib.sha256(pb).hexdigest()},'sources':[{'asset':'10501'}]};(root/'recipe.json').write_text(json.dumps(recipe));argv=['tool','--recipe',str(root/'recipe.json'),'--output',str(root/'no-output')]
   with patch('sys.argv',argv),self.assertRaisesRegex(ValueError,'complete selected cohort'):m.main()
   self.assertFalse((root/'no-output').exists())
if __name__=='__main__':unittest.main()
