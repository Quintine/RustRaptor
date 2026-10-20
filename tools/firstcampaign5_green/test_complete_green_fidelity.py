import unittest,json,tempfile,hashlib,struct,io
from pathlib import Path
from unittest.mock import patch
import numpy as np
from PIL import Image
import terrain_component_cleanup as m
class CompleteGreenFidelityTests(unittest.TestCase):
 def source(self):
  a=np.full((32,32),197,np.uint8);a[8,8]=a[8,9]=a[9,8]=105;return a
 def rgb(self):
  y,x=np.indices((512,512));return np.stack([(x*11+y*7)%256,(x*17+y*3)%256,(x*5+y*23)%256],-1).astype(np.uint8)
 def palette(self):return np.repeat(np.arange(256,dtype=np.uint8)[:,None],3,axis=1)
 def test_complete_allscale_union_includes_spill_owner(self):
  self.assertEqual(m.green_fidelity_union(self.source()),[[8,8],[8,9],[9,8],[9,9]])
 def test_exact_original_owners_and_byteexact_genuine_outside(self):
  p=self.rgb();src=self.source();out,owners,s=m.restore_green_fidelity(p,src,self.palette());exact=np.repeat(np.repeat(self.palette()[m.scale_nx(src,4)],4,0),4,1);self.assertTrue(np.array_equal(out[owners],exact[owners]));self.assertTrue(np.array_equal(out[~owners],p[~owners]));self.assertEqual(s['outside_parent_pixels_changed'],0);self.assertEqual(s['inside_SourceNx_RGB_mismatches'],0);self.assertEqual(s['outside_parent_bytes_sha256'],s['outside_successor_bytes_sha256']);self.assertEqual(s['Original_fidelity_HD_credit'],0)
 def test_empty_or_overquarter_semantic_mask_rejected(self):
  for a in [np.full((32,32),197,np.uint8),np.full((32,32),105,np.uint8)]:
   with self.assertRaises(ValueError):m.restore_green_fidelity(self.rgb(),a,self.palette())
 def test_wrong_parent_geometry_or_dtype_rejected(self):
  for p in [self.rgb()[:511],self.rgb().astype(float)]:
   with self.assertRaises(ValueError):m.restore_green_fidelity(p,self.source(),self.palette())
 def test_actual_all54_source_features_have_complete105owner_union(self):
  a=m.decode_source32((Path(__file__).parent/'inputs/105a4.pic').read_bytes());mask=(a>=100)&(a<=111);cells={(int(x),int(y))for y,x in zip(*np.where(mask))};union={tuple(p)for p in m.green_fidelity_union(a)};self.assertEqual(union,cells);self.assertEqual(len(union),105);remaining=set(cells);components=[]
  while remaining:
   todo=[remaining.pop()];group=set(todo)
   while todo:
    x,y=todo.pop()
    for p in [(x-1,y),(x+1,y),(x,y-1),(x,y+1)]:
     if p in remaining:remaining.remove(p);group.add(p);todo.append(p)
   components.append(group)
  self.assertEqual(len(components),54);self.assertTrue(all(group<=union for group in components));self.assertEqual(len(union)*256,26880)
 def test_existing_v3_policy_accepts_complete105Source_cells(self):
  import sys;sys.path.insert(0,str(m.ROOT/'tools'));import hd_frame_policy as f
  source=(Path(__file__).parent/'inputs/105a4.pic').read_bytes();cells=m.green_fidelity_union(m.decode_source32(source));frame={'frame':0,'file':'105a4.png','logical_width':32,'logical_height':32,'origin':[0,0],'source_sha256':hashlib.sha256(source).hexdigest(),'original_detail_cells':cells};f.validate_frame_policy(frame,source);self.assertTrue(f.retained_review_version_ok(f.EXTENDED_RETAINED_POLICY,{'105a4':cells}));self.assertFalse(f.retained_review_version_ok(f.LEGACY_RETAINED_POLICY,{'105a4':cells}))
 def negative_recipe(self,mutation):
  with tempfile.TemporaryDirectory()as d:
   d=Path(d);pal=bytes(768);source=struct.pack('<5i',1,1,0,32,32)+self.source().tobytes();bio=io.BytesIO();Image.fromarray(self.rgb()).save(bio,format='PNG');png=bio.getvalue();files={'pal':pal,'source':source,'parent.png':png,'raw.png':png};sha=lambda b:hashlib.sha256(b).hexdigest();old={'implementation':{'sha256':'reviewedparent'},'operation':'further-first-tiles','method':m.METHOD,'palette':{'sha256':sha(pal)},'input_pins':[{'sha256':sha(source)},{'sha256':sha(png)}],'outputs':[{'file':'105a4-derived.png','sha256':sha(png)}],'metrics':{'assets':[{'asset':'105a4','original_detail_cells':[],'genuine_RGB_band_changed_nonfunctional_HDR_pixels':100000}]}};mutation(old);files['receipt.json']=json.dumps(old).encode()
   for n,b in files.items():(d/n).write_bytes(b)
   bind=lambda n:{'path':n,'sha256':sha(files[n])};rec={'method':m.METHOD,'operation':'restore-105a4-green','palette':bind('pal'),'source':dict(bind('source'),asset='105a4'),'parent':bind('parent.png'),'parent_execution_receipt':bind('receipt.json'),'generation_raw':bind('raw.png'),'expected_parent_implementation_sha256':'reviewedparent'};(d/'recipe.json').write_text(json.dumps(rec))
   with patch('sys.argv',['tool','--recipe',str(d/'recipe.json'),'--output',str(d/'none')]),self.assertRaises(ValueError):m.main()
   self.assertFalse((d/'none').exists())
 def test_false_actual_parent_output_binding_rejected_before_art(self):self.negative_recipe(lambda old:old['outputs'][0].update(sha256='bad'))
 def test_false_parent_source_or_palette_binding_rejected_before_art(self):
  self.negative_recipe(lambda old:old['palette'].update(sha256='bad'));self.negative_recipe(lambda old:old['input_pins'].pop(0))
if __name__=='__main__':unittest.main()
