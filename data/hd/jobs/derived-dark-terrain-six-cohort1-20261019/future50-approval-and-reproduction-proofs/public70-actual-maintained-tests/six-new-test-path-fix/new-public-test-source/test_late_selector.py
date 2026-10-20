import unittest,json,tempfile,hashlib
from pathlib import Path
from unittest.mock import patch
import numpy as np
import terrain_component_cleanup as m


def original_pic(asset):
    """Read an authentic, already bundled Original catalogue fixture by ID."""
    data = Path(__file__).resolve().parents[2] / "data"
    matches = [parts for line in (data / "INDEX").read_text().splitlines()
               if len(parts := line.split()) == 3 and int(parts[0], 16) == int(asset, 16)]
    if len(matches) != 1:
        raise ValueError("Original fixture must have exactly one catalogue entry")
    relative = Path(matches[0][2])
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Original fixture escapes bundled catalogue")
    path = (data / relative).resolve()
    if not path.is_relative_to(data.resolve()):
        raise ValueError("Original fixture escapes bundled catalogue")
    payload = path.read_bytes()
    if len(payload) != int(matches[0][1]):
        raise ValueError("Original fixture length differs from catalogue")
    return payload

class LateSelectorTests(unittest.TestCase):
 def source(self):
  a=np.full((32,32),197,np.uint8);a[:8,:8]=15;a[:8,8:16]=173;a[:8,16:]=154;a[8:16,:]=82;a[16:24,:]=43;a[24:,:]=55;a[2,24]=241;a[2,25]=249;a[10,10]=109;a[12,12]=79;a[12,13]=181;return a
 def palette(self):return np.repeat(np.arange(256,dtype=np.uint8)[:,None],3,axis=1)
 def fields(self):
  y,x=np.indices((512,512));return{i:np.stack([(x*19+y*11+i*7)%256,(x*13+y*17)%256,(x*3+y*7)%256],-1).astype(float)for i in range(6)}
 def test_actual_special_classes_are_honest_not_reserved(self):
  self.assertEqual(m.late_material_labels(np.array([[79,181,169,171,173,174,175,109,241,249]],np.uint8)).tolist(),[[2,2,0,0,0,0,0,6,1,6]])
 def test_unknown_ordinary_classes_rejected(self):
  for v in [64,78,96,108,110,147,160,168,170,172,176,180]:
   with self.assertRaises(ValueError):m.late_material_labels(np.array([[v]],np.uint8))
 def test_actual_nine_sources_and_full_fidelity_union(self):
  d=Path(__file__).parent/'inputs';expected={'105e0':4,'105e8':2,'105e9':2,'105ef':11,'105e6':4,'105e7':7,'105eb':5,'105ed':1,'105f3':0}
  for aid,count in expected.items():
   a=m.decode_source32(original_pic(aid));m.late_material_labels(a);self.assertEqual(len(m.late_fidelity_union(a)),count,aid)
 def test_exact_source_ownership_and_reserved_plus_green_retention(self):
  a=self.source();p=self.palette();out,owners,protected,s=m.derive_late_tile(a,p,self.fields());guide=m.scale_nx(a,4);self.assertTrue(np.array_equal(owners,np.repeat(np.repeat(m.late_material_labels(guide),4,0),4,1)));self.assertTrue(np.array_equal(out[protected],np.repeat(np.repeat(p[guide],4,0),4,1)[protected]));self.assertEqual(s['Source109_ordinary_green_cells'],1);self.assertGreater(s['Source_fidelity_owner_union_cells'],s['functional_support_union_cells']);self.assertGreater(s['genuine_RGB_band_changed_nonfunctional_HDR_pixels'],0);self.assertEqual(s['Original_functional_HD_credit'],0)
 def test_water_donor_only_changes_water_not_topcap_markers_or_fidelity(self):
  a=self.source();f=self.fields();p=self.palette();out,owners,prot,_=m.derive_late_tile(a,p,f);f[1]=255-f[1];other,_,_,_=m.derive_late_tile(a,p,f);self.assertTrue(np.array_equal(out[owners!=1],other[owners!=1]));self.assertTrue(np.array_equal(out[prot],other[prot]));self.assertTrue(np.any(out[(owners==1)&~prot]!=other[(owners==1)&~prot]))
 def test_actual_source_topcap_seven_pathmarks_three_fixturemarks_and_two_green(self):
  d=Path(__file__).parent/'inputs';a=m.decode_source32(original_pic('105e7'));labels=m.late_material_labels(a);self.assertTrue(np.all(labels[0,12:15]==0));self.assertTrue(np.all(labels[1,10:17]==0));a=m.decode_source32(original_pic('105ef'));points={(int(x),int(y))for y,x in zip(*np.where((a>=80)&(a<=95)))};self.assertEqual(points,{(12,1),(6,5),(5,12),(6,19),(9,25),(15,28),(24,30)});a=m.decode_source32(original_pic('105ed'));self.assertEqual([(29,y)for y in [5,7,9]if 80<=int(a[y,29])<=95],[(29,5),(29,7),(29,9)]);a=m.decode_source32(original_pic('105e9'));self.assertEqual(m.late_fidelity_union(a),[[6,22],[8,22]])
 def test_zero_generated_detail_rejected(self):
  with self.assertRaisesRegex(ValueError,'Original-only'):m.derive_late_tile(self.source(),self.palette(),{i:np.full((512,512,3),80.,float)for i in range(6)})
 def test_foreign_or_partial_cohorts_rejected_before_art(self):
  for ids in [['105e0'],['105e1'],['105e6','105ed']]:
   with tempfile.TemporaryDirectory()as d:
    d=Path(d);p=bytes(768);(d/'pal').write_bytes(p);rec={'method':m.METHOD,'operation':'late-first-tiles','palette':{'path':'pal','sha256':hashlib.sha256(p).hexdigest()},'sources':[{'asset':x}for x in ids]};(d/'recipe.json').write_text(json.dumps(rec))
    with patch('sys.argv',['tool','--recipe',str(d/'recipe.json'),'--output',str(d/'none')]),self.assertRaisesRegex(ValueError,'complete selected late cohort'):m.main()
    self.assertFalse((d/'none').exists())
if __name__=='__main__':unittest.main()
