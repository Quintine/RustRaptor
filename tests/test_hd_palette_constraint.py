import unittest,sys,struct,copy,importlib.util
from pathlib import Path
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import hd_frame_policy as policy
import hd_candidate_review as candidate
import hd_register_reviewed as registrar
def frame():return dict(frame=0,file='raw.png',logical_width=2,logical_height=2,origin=[0,0],source_sha256='0'*64)
def payload(indices):return struct.pack('<iiiii',1,0,0,2,2)+bytes(indices)
class PalettePolicyTests(unittest.TestCase):
 def test_default_dictionary_unchanged(self):
  f=frame();before=copy.deepcopy(f);policy.validate_frame_policy(f,payload([10,20,10,20]));self.assertEqual(f,before);self.assertNotIn('palette_constraint',f)
 def test_null_remains_default(self):
  f=frame();f['palette_constraint']=None;policy.validate_frame_policy(f,payload([240,255,10,20]));self.assertIsNone(f['palette_constraint'])
 def test_exact_enum_source_is_valid(self):
  f=frame();f['palette_constraint']='original-painted-ordinary-v1';policy.validate_frame_policy(f,payload([0,20,239,20]))
 def test_wrong_types_names_and_lists_reject(self):
  for value in [True,False,0,1,1.0,[],{},'ordinary','original-painted-ordinary-v2']:
   with self.subTest(value=value),self.assertRaises(ValueError):
    f=frame();f['palette_constraint']=value;policy.validate_frame_policy(f,payload([10]*4))
 def test_reserved_240_to255_reject(self):
  for i in range(240,256):
   with self.subTest(i=i),self.assertRaises(ValueError):
    f=frame();f['palette_constraint']='original-painted-ordinary-v1';policy.validate_frame_policy(f,payload([10,20,i,20]))
 def test_transparent_rle_source_rejects(self):
  f=frame();f['palette_constraint']='original-painted-ordinary-v1';p=struct.pack('<iiiii',0,0,0,2,2)+struct.pack('<iiii',0,0,-1,0)
  with self.assertRaises(ValueError):policy.validate_frame_policy(f,p)
 def test_canvas_mismatch_rejects(self):
  f=frame();f['palette_constraint']='original-painted-ordinary-v1';p=struct.pack('<iiiii',1,0,0,1,4)+bytes([10]*4)
  with self.assertRaises(ValueError):policy.validate_frame_policy(f,p)
 def test_malformed_authentic_source_payloads_reject_before_palette_derivation(self):
  f=frame();f['palette_constraint']='original-painted-ordinary-v1'
  invalid=[b'',payload([10,20,10]),struct.pack('<iiiii',2,0,0,2,2)+bytes([10]*4),
           struct.pack('<iiiii',1,0,0,0,2),
           struct.pack('<iiiii',0,0,0,2,2)+struct.pack('<iiii',1,0,0,2)+bytes([10,20])]
  for p in invalid:
   with self.subTest(payload=p),self.assertRaises(ValueError):policy.validate_frame_policy(f,p)
 def test_metadata_only_does_not_claim_source_validation(self):
  f=frame();f['palette_constraint']='original-painted-ordinary-v1';policy.validate_frame_policy(f)
 def test_unknown_fields_stay_rejected(self):
  f=frame();f['allowed_palette_colors']=[10]
  with self.assertRaises(ValueError):policy.validate_frame_policy(f,payload([10]*4))
 def test_retained_and_nearest_existing_policies_still_validate(self):
  f=frame();f.update(palette_constraint='original-painted-ordinary-v1',original_detail_cells=[[0,0]],native_nearest_cues=[[1,1]])
  policy.validate_frame_policy(f,payload([10]*4))

# The registrar entry point is exercised in memory with synthetic catalog/QA
# identities. No PNG decode, process, registrar main or writer is permitted.
import json,hashlib,tempfile
from unittest import mock
import test_hd_retained_original_policy as retained_fixture
from PIL import Image

class PaletteBindingAndRegistrarTests(unittest.TestCase):
 write_json=staticmethod(retained_fixture.ActualRegistrarProvenance.write_json)
 def setUp(self):
  retained_fixture.ActualRegistrarProvenance.setUp(self)
  raw=payload([10,20,10,20]);self.f=frame();self.f['source_sha256']=hashlib.sha256(raw).hexdigest();self.f['palette_constraint']='original-painted-ordinary-v1'
  self.candidate['sequences'][0]['frames']=[self.f];self.rows=candidate.proposal_frames(self.candidate);digest=candidate.binding_digest(self.rows)
  self.review.pop('retained_original_detail_review');self.review['frame_bindings_sha256']=digest
  self.review['palette_constraint_review']=dict(policy_version='original-painted-ordinary-v1',frame_bindings_sha256=digest,unchanged_generated_raw=True,independent_allscale_and_genuine_context_review=True)
  self.write_json(self.job_dir/'candidate.json',self.candidate)
  self.write_json(self.job_dir/'job.json',dict(job_id='synthetic-complete1',targets=[dict(asset='00001',source_sha256=self.f['source_sha256'],logical_canvas=[2,2])]))
  data=self.project/'data';(data/'misc').mkdir(parents=True);(data/'tile').write_bytes(raw);(data/'INDEX').write_text(f'1 {len(raw)} tile\n');(data/'misc/PALETTE_DAT').write_bytes(bytes(i%64 for i in range(256) for _ in range(3)))
  def color(i):v=(i%64<<2)|(i%64>>4);return dict(index=i,RGB=[v,v,v])
  qa=json.loads((self.root/'qa.json').read_text());qa['frame_bindings_sha256']=digest
  report=dict(asset='00001',source_sha256=self.f['source_sha256'],source_palette='PALETTE_DAT',logical_canvas=[2,2],source_mask=dict(palette_indices_240_to_255_counts=[0]*16),hd_masks=[dict(scale=s,mask=dict(visible_pixels=4*s*s,palette_indices_240_to_255_counts=[0]*16)) for s in range(1,5)],palette_constraint=dict(policy='original-painted-ordinary-v1',applied=True,source_indices=[10,20],source_colors=[color(10),color(20)],scales=[dict(scale=s,visible_pixels=4*s*s,outside_original_palette=0) for s in range(1,5)]))
  qa['frames']=[report];self.qa=qa;self.write_json(self.root/'qa.json',qa)
 def approve(self):return retained_fixture.ActualRegistrarProvenance.approve(self)
 def test_real_approved_job_exact_palette_scope_passes_under_all_writer_process_image_traps(self):
  _,review,rows=self.approve();self.assertEqual(rows,self.rows);self.assertIs(review['palette_constraint_review']['unchanged_generated_raw'],True)
 def test_old_raw_review_or_default_sampler_evidence_cannot_approve_the_new_mode(self):
  original=self.review.pop('palette_constraint_review')
  with self.assertRaisesRegex(ValueError,'explicit palette'):self.approve()
  self.review['palette_constraint_review']=original;del self.qa['frames'][0]['palette_constraint'];self.write_json(self.root/'qa.json',self.qa)
  with self.assertRaisesRegex(ValueError,'exact SourceClasses'):self.approve()
 def test_each_treatment_scope_boolean_version_and_binding_is_required(self):
  base=self.review['palette_constraint_review']
  for key,value in dict(policy_version='other',frame_bindings_sha256='0'*64,unchanged_generated_raw=1,independent_allscale_and_genuine_context_review='yes').items():
   self.review['palette_constraint_review']=dict(base,**{key:value})
   with self.subTest(key=key),self.assertRaises(ValueError):self.approve()
  self.review['palette_constraint_review']=base
 def test_measured_indices_colors_static_mode_and_typed_scales_cannot_alias(self):
  original=copy.deepcopy(self.qa)
  mutations=[lambda e:e.update(source_indices=[True,20]),lambda e:e.update(source_indices=[20,10]),lambda e:e.update(source_colors=[dict(index=10,RGB=[0,0,0]),e['source_colors'][1]]),lambda e:e.update(applied=1),lambda e:e['scales'][0].update(scale=True),lambda e:e['scales'][1].update(visible_pixels=16.0),lambda e:e['scales'][2].update(outside_original_palette=1),lambda e:e.update(scales=[{},None])]
  for change in mutations:
   self.qa=copy.deepcopy(original);change(self.qa['frames'][0]['palette_constraint']);self.write_json(self.root/'qa.json',self.qa)
   with self.subTest(change=change),self.assertRaises(ValueError):self.approve()
 def test_actual_source_and_rgb_domain_are_checked_from_catalog_not_supplied_qa(self):
  (self.project/'data/tile').write_bytes(payload([10,240,10,20]))
  with self.assertRaisesRegex(ValueError,'authentic opaque ordinary'):self.approve()
 def test_candidate_digest_binds_policy_while_default_dictionary_stays_unchanged(self):
  plain=copy.deepcopy(self.candidate);plain['sequences'][0]['frames'][0].pop('palette_constraint')
  self.assertNotEqual(candidate.binding_digest(candidate.proposal_frames(plain)),candidate.binding_digest(self.rows))
  self.assertNotIn('palette_constraint',candidate.proposal_frames(plain)['00001'])

if __name__=="__main__":unittest.main(verbosity=2)
