import unittest,json,tempfile,hashlib
from pathlib import Path
from unittest.mock import patch
import numpy as np
import terrain_component_cleanup as m
class SingletonSelectorTests(unittest.TestCase):
 def source(self):
  a=np.full((32,32),225,np.uint8);a[:8,:]=154;a[8:16,:]=15;a[16:24,:]=82;a[24:,:16]=43;a[1,1]=245;a[1,2]=250;a[10,10]=102;return a
 def palette(self):return np.stack([np.arange(256,dtype=np.uint8),np.arange(256,dtype=np.uint8)[::-1],np.arange(256,dtype=np.uint8)],-1)
 def fields(self):
  y,x=np.indices((512,512));return{i:np.stack([(x*19+y*11+i*7)%256,(x*13+y*17)%256,(x*3+y*7)%256],-1).astype(float)for i in range(5)}
 def test_explicit_green_orange_red_and_protected(self):
  self.assertEqual(m.singleton_material_labels(np.array([[102,69,70,73,75,82,38,40,41,43,245,250,255]],np.uint8)).tolist(),[[5,3,3,3,3,3,4,4,4,4,5,5,5]])
 def test_unknown_classes_rejected(self):
  for v in [32,34,37,44,65,68,71,72,74,76,101,103,147,160,181]:
   with self.assertRaises(ValueError):m.singleton_material_labels(np.array([[v]],np.uint8))
 def test_actual_original_support_and_isolated_fixture_contract(self):
  d=Path(__file__).parent/'inputs'
  for aid,count,rawfun in [('1054f',13,12),('10561',1,1)]:
   a=m.decode_source32((d/(aid+'.pic')).read_bytes());m.singleton_material_labels(a);self.assertEqual(len(m.singleton_fidelity_union(a)),count);self.assertEqual(len(m.functional_support_union(a)),rawfun)
  a=m.decode_source32((d/'1054f.pic').read_bytes());self.assertEqual(int(a[4,1]),102);self.assertIn([1,4],m.singleton_fidelity_union(a))
 def test_green_and_fire_exact_with_positive_generated_fine_band(self):
  a=self.source();p=self.palette();out,own,protected,stats=m.derive_singleton_tile(a,p,self.fields());guide=m.scale_nx(a,4);exact=np.repeat(np.repeat(p[guide],4,0),4,1);self.assertTrue(np.array_equal(out[protected],exact[protected]));self.assertEqual(stats['Original_functional_HD_credit'],0);self.assertGreater(stats['genuine_RGB_band_changed_nonfunctional_HDR_pixels'],0);self.assertEqual(stats['Source102_raw_original_retention_cells'],1);self.assertGreater(stats['Source_fidelity_owner_union_cells'],stats['functional_support_union_cells'])
 def test_gray_donor_changes_only_gray_owners_not_earth_water_or_fire(self):
  a=self.source();f=self.fields();p=self.palette();out,owners,protected,_=m.derive_singleton_tile(a,p,f);f[1]=255-f[1];changed,_,_,_=m.derive_singleton_tile(a,p,f);self.assertTrue(np.array_equal(out[owners!=1],changed[owners!=1]));self.assertTrue(np.any(out[owners==1]!=changed[owners==1]));self.assertTrue(np.array_equal(out[protected],changed[protected]))
 def test_no_generated_band_is_original_only_rejected(self):
  with self.assertRaisesRegex(ValueError,'Original-only'):m.derive_singleton_tile(self.source(),self.palette(),{i:np.full((512,512,3),90.,float)for i in range(5)})
 def test_two_singletons_or_wrong_id_rejected_before_output(self):
  for ids in [['1054f','10561'],['1054e']]:
   with tempfile.TemporaryDirectory()as d:
    d=Path(d);p=bytes(768);(d/'pal').write_bytes(p);rec={'method':m.METHOD,'operation':'first-singleton-tiles','palette':{'path':'pal','sha256':hashlib.sha256(p).hexdigest()},'sources':[{'asset':x}for x in ids]};(d/'recipe.json').write_text(json.dumps(rec))
    with patch('sys.argv',['tool','--recipe',str(d/'recipe.json'),'--output',str(d/'none')]),self.assertRaisesRegex(ValueError,'selected singleton'):m.main()
    self.assertFalse((d/'none').exists())
 def test_source_red_gap_mask_is_exact_no_implicit_red_rectangle(self):
  d=Path(__file__).parent/'inputs';a=m.decode_source32((d/'10561.pic').read_bytes());labels=m.singleton_material_labels(a);self.assertTrue(np.array_equal(labels==4,np.isin(a,[38,39,40,41,42,43])))
  for x,y in [(25,0),(27,0),(30,0)]:self.assertNotEqual(int(labels[y,x]),4)
  for x,y in [(27,6),(30,10)]:self.assertEqual(int(labels[y,x]),4)
if __name__=='__main__':unittest.main()
