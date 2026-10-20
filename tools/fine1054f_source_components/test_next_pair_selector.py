import unittest,json,tempfile,hashlib
from pathlib import Path
from unittest.mock import patch
import numpy as np
import terrain_component_cleanup as m
class NextPairTests(unittest.TestCase):
 def source(self):
  a=np.full((32,32),225,np.uint8);a[:,:10]=154;a[:10,10:20]=15;a[10:20,10:20]=82;a[20:,10:20]=43
  a[3,3]=a[3,4]=a[4,3]=243;return a
 def palette(self):return np.stack([np.arange(256,dtype=np.uint8),np.arange(256,dtype=np.uint8)[::-1],np.arange(256,dtype=np.uint8)],-1)
 def fields(self):
  y,x=np.indices((512,512));return{i:np.stack([(x*19+y*11+i*7)%256,(x*13+y*17)%256,(x*3+y*7)%256],-1).astype(float)for i in range(5)}
 def test_actual_materials_and_all_reserved_classes(self):
  a=np.array([[65,191,219,31,154,243,255,34,38,39,42,43,44]],np.uint8);self.assertEqual(m.next_pair_material_labels(a).tolist(),[[3,2,2,1,0,0,5,4,4,4,4,4,4]])
 def test_unknown_source_red_or_other_material_rejected(self):
  for v in [32,35,37,40,41,45,64,66,147,160,181]:
   with self.assertRaises(ValueError):m.next_pair_material_labels(np.array([[v]],np.uint8))
 def test_exact_geometry_protected_and_positive_real_band(self):
  a=self.source();p=self.palette();out,owners,prot,stats=m.derive_next_pair_tile(a,p,self.fields());guide=m.scale_nx(a,4)
  self.assertTrue(np.array_equal(owners,np.repeat(np.repeat(m.next_pair_material_labels(guide),4,0),4,1)));self.assertTrue(np.array_equal(out[prot],np.repeat(np.repeat(p[guide],4,0),4,1)[prot]));self.assertGreater(stats['genuine_RGB_band_changed_nonfunctional_HDR_pixels'],0);self.assertEqual(stats['Original_functional_HD_credit'],0)
 def test_red_donor_change_cannot_move_contacts_or_touch_other_components(self):
  f=self.fields();a=self.source();out,owners,_,_=m.derive_next_pair_tile(a,self.palette(),f);f[4]=255-f[4];changed,owners2,_,_=m.derive_next_pair_tile(a,self.palette(),f);self.assertTrue(np.array_equal(owners,owners2));self.assertTrue(np.array_equal(out[owners!=4],changed[owners!=4]));self.assertTrue(np.any(out[owners==4]!=changed[owners==4]))
 def test_constant_fields_rejected_as_original_only(self):
  with self.assertRaisesRegex(ValueError,'Original-only'):m.derive_next_pair_tile(self.source(),self.palette(),{i:np.full((512,512,3),60.,float)for i in range(5)})
 def test_missing_or_extra_field_rejected(self):
  for fs in [{i:np.zeros((512,512,3))for i in range(4)},{i:np.zeros((512,512,3))for i in range(6)}]:
   with self.assertRaises(ValueError):m.derive_next_pair_tile(self.source(),self.palette(),fs)
 def test_actual_originals_and_functional_union(self):
  d=Path(__file__).parent/'inputs'
  for aid in m.NEXT_PAIR_IDS:
   a=m.decode_source32((d/(aid+'.pic')).read_bytes());m.next_pair_material_labels(a)
   self.assertEqual(len(m.functional_support_union(a)),{'10536':1,'1053e':0}[aid])
 def test_wrong_order_rejected_without_output(self):
  with tempfile.TemporaryDirectory()as d:
   d=Path(d);p=bytes(768);(d/'pal').write_bytes(p);rec={'method':m.METHOD,'operation':'next-pair-tiles','palette':{'path':'pal','sha256':hashlib.sha256(p).hexdigest()},'sources':[{'asset':'1053e'},{'asset':'10536'}]};(d/'recipe.json').write_text(json.dumps(rec))
   with patch('sys.argv',['tool','--recipe',str(d/'recipe.json'),'--output',str(d/'none')]),self.assertRaisesRegex(ValueError,'complete next pair'):m.main()
   self.assertFalse((d/'none').exists())
if __name__=='__main__':unittest.main()
