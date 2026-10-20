import unittest,json,tempfile,hashlib
from pathlib import Path
from unittest.mock import patch
import numpy as np
import terrain_component_cleanup as m
class FurtherSelectorTests(unittest.TestCase):
 def source(self):
  a=np.full((32,32),225,np.uint8);a[:8,:]=15;a[8:16,:]=31;a[16:24,:]=197;a[24:,:]=105;return a
 def palette(self):return np.repeat(np.arange(256,dtype=np.uint8)[:,None],3,axis=1)
 def fields(self):
  y,x=np.indices((512,512));return{i:np.stack([(x*19+y*11+i*7)%256,(x*13+y*17)%256,(x*3+y*7)%256],-1).astype(float)for i in range(5)}
 def test_explicit_five_material_owners(self):
  self.assertEqual(m.further_material_labels(np.array([[1,23,24,31,194,207,208,238,100,111]],np.uint8)).tolist(),[[0,0,1,1,2,2,3,3,4,4]])
 def test_all_unsupported_or_reserved_are_rejected(self):
  for v in [32,65,99,112,147,159,181,240,244,245,250,255]:
   with self.assertRaises(ValueError):m.further_material_labels(np.array([[v]],np.uint8))
 def test_actual_three_source_materials_and_no_functional_owners(self):
  d=Path(__file__).parent/'inputs'
  for aid in ['1059e','105a4','105a7']:
   a=m.decode_source32((d/(aid+'.pic')).read_bytes());m.further_material_labels(a);self.assertEqual(m.functional_support_union(a),[])
  a=m.decode_source32((d/'105a4.pic').read_bytes());self.assertEqual(int(((a>=100)&(a<=111)).sum()),105)
 def test_exact_ownership_and_real_generated_band(self):
  a=self.source();out,owners,prot,stats=m.derive_further_tile(a,self.palette(),self.fields());self.assertTrue(np.array_equal(owners,np.repeat(np.repeat(m.further_material_labels(m.scale_nx(a,4)),4,0),4,1)));self.assertFalse(np.any(prot));self.assertEqual(stats['original_detail_cells'],[]);self.assertGreater(stats['genuine_RGB_band_changed_nonfunctional_HDR_pixels'],0)
 def test_green_donor_changes_only_green_not_slots_or_structure(self):
  a=self.source();f=self.fields();out,owners,_,_=m.derive_further_tile(a,self.palette(),f);f[4]=255-f[4];other,_,_,_=m.derive_further_tile(a,self.palette(),f);self.assertTrue(np.array_equal(out[owners!=4],other[owners!=4]));self.assertTrue(np.any(out[owners==4]!=other[owners==4]))
 def test_dark_slot_band_stays_achromatic(self):
  out,owners,_,_=m.derive_further_tile(self.source(),self.palette(),self.fields());x=out[(owners==0)|(owners==1)];self.assertTrue(np.array_equal(x[:,0],x[:,1]));self.assertTrue(np.array_equal(x[:,1],x[:,2]))
 def test_no_generated_detail_is_rejected_original_only(self):
  with self.assertRaisesRegex(ValueError,'Original-only'):m.derive_further_tile(self.source(),self.palette(),{i:np.full((512,512,3),80.,float)for i in range(5)})
 def test_incomplete_or_foreign_cohort_rejected_before_output(self):
  for ids in [['105a4'],['105a7','105a4'],['1059f']]:
   with tempfile.TemporaryDirectory()as d:
    d=Path(d);p=bytes(768);(d/'pal').write_bytes(p);rec={'method':m.METHOD,'operation':'further-first-tiles','palette':{'path':'pal','sha256':hashlib.sha256(p).hexdigest()},'sources':[{'asset':x}for x in ids]};(d/'recipe.json').write_text(json.dumps(rec))
    with patch('sys.argv',['tool','--recipe',str(d/'recipe.json'),'--output',str(d/'none')]),self.assertRaisesRegex(ValueError,'complete further'):m.main()
    self.assertFalse((d/'none').exists())
if __name__=='__main__':unittest.main()
