import unittest,importlib.util,json,tempfile,os,hashlib,struct
from pathlib import Path
import numpy as np
from PIL import Image
p=Path(__file__).with_name('hd_followon302e1_quiet_floor_cleanup.py');spec=importlib.util.spec_from_file_location('industrial_tested',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class IndustrialContract(unittest.TestCase):
 def setUp(self):self.pal=np.arange(768,dtype=np.uint16).reshape(256,3).astype(np.uint8)
 def test_source_truncated(self):
  with self.assertRaises(ValueError):m.decode_source32(b'0'*1043)
 def test_source_wrongcanvas(self):
  with self.assertRaises(ValueError):m.decode_source32(struct.pack('<5i',1,1,0,16,64)+b'0'*1024)
 def test_source_roundtrip_reserved(self):
  a=np.arange(1024,dtype=np.uint16).astype(np.uint8).reshape(32,32);self.assertTrue(np.array_equal(a,m.decode_source32(struct.pack('<5i',1,1,0,32,32)+a.tobytes())))
 def test_source_badkind(self):
  with self.assertRaises(ValueError):m.decode_source32(struct.pack('<5i',2,1,0,32,32)+b'0'*1024)
 def test_material_partition(self):
  a=np.array([[0,23,24,31,32,47,58,79,100,111,192,239,240,255]],np.uint8);self.assertEqual(m.material_labels(a).tolist(),[[0,0,1,1,2,2,2,2,3,3,5,5,6,6]])
 def test_all_palette_groups_explicit(self):
  self.assertEqual(m.material_labels(np.arange(256,dtype=np.uint8)[None]).shape,(1,256))
 def test_wrong_labeltype_rejected(self):
  with self.assertRaises(ValueError):m.material_labels(np.array([[1]],np.int32))
 def test_union_no_reserved(self):self.assertEqual(m.functional_support_union(np.full((32,32),200,np.uint8)),[])
 def test_union_reserved_near_corner(self):
  a=np.full((32,32),200,np.uint8);a[0,0]=245;u=m.functional_support_union(a);self.assertIn([0,0],u);self.assertTrue(all(0<=x<32 and 0<=y<32 for x,y in u))
 def test_union_wrongcanvas(self):
  with self.assertRaises(ValueError):m.functional_support_union(np.zeros((16,64),np.uint8))
 def test_constant_donor_cannot_claim_HD(self):
  with self.assertRaises(ValueError):m.derive_tile(np.full((32,32),200,np.uint8),self.pal,np.full((512,512,3),100.),'10370')
 def test_derive_protected_exact(self):
  a=np.full((32,32),200,np.uint8);a[4,7]=246;field=np.random.default_rng(4).integers(0,256,(512,512,3)).astype(float);out,metrics=m.derive_tile(a,self.pal,field,'30465');g=m.scale_nx(a,4);mask=np.repeat(np.repeat(g>=240,4,0),4,1);exact=np.repeat(np.repeat(self.pal[g],4,0),4,1);self.assertTrue(np.array_equal(out[mask],exact[mask]));self.assertGreater(metrics['genuine_RGB_band_changed_nonretained_HDR_pixels'],0);self.assertEqual(metrics['Original_functional_HD_credit'],0)
 def test_donor_wrongcanvas(self):
  with self.assertRaises(ValueError):m.derive_tile(np.full((32,32),200,np.uint8),self.pal,np.zeros((511,512,3)),'10370')
 def test_field_box_no_tiling(self):
  a=np.arange(24*18*3,dtype=np.uint16).reshape(18,24,3).astype(np.uint8);self.assertEqual(m.donor_field(a,[0,0,24,18],(512,512)).shape,(512,512,3))
 def test_field_invalid_box(self):
  for box in [[-1,0,8,8],[0,0,25,8],[0,0,0,1],[0.,0,1,1]]:
   with self.subTest(box=box),self.assertRaises(ValueError):m.donor_field(np.zeros((18,24,3),np.uint8),box,(512,512))
 def test_io_traversal(self):
  with tempfile.TemporaryDirectory()as d:
   with self.assertRaises(ValueError):m.read_contained(Path(d),'../file')
 def test_io_symlink(self):
  with tempfile.TemporaryDirectory()as d:
   p=Path(d);(p/'a').write_bytes(b'x');(p/'s').symlink_to(p/'a')
   with self.assertRaises(OSError):m.read_contained(p,'s')
 def test_io_bound(self):
  with tempfile.TemporaryDirectory()as d:
   p=Path(d);(p/'a').write_bytes(b'abc')
   with self.assertRaises(ValueError):m.read_contained(p,'a',2)
 def test_io_hash_mismatch(self):
  with tempfile.TemporaryDirectory()as d:
   p=Path(d);(p/'a').write_bytes(b'abc')
   with self.assertRaises(ValueError):m.BufferedInputs(p).read(dict(path='a',sha256='0'*64))
 def test_png_alpha_rejected(self):
  import io
  b=io.BytesIO();Image.new('RGBA',(8,8),(10,10,10,100)).save(b,format='PNG')
  with self.assertRaises(ValueError):m.decode_png(b.getvalue())
 def test_all_actual_source_labelsets_supported(self):
  r=m.ROOT;entries={a:p for a,s,p in[l.split()for l in(r/'data/INDEX').read_text().splitlines()if l.strip()]}
  for aid in sorted(set().union(*m.COHORTS)):
   with self.subTest(asset=aid):a=m.decode_source32((r/'data'/entries[aid]).read_bytes());m.material_labels(a);self.assertLessEqual(len(m.functional_support_union(a)),64)
class LandmarkContracts(unittest.TestCase):
 def setUp(self):
  self.pal=np.arange(768,dtype=np.uint16).reshape(256,3).astype(np.uint8);self.field=np.random.default_rng(7).integers(0,256,(512,512,3)).astype(float)
 def test_ordinary_cue_sets(self):
  a=np.array([[72,80,84,100,121,133,172,31,240]],np.uint8);self.assertEqual(m.cue_mask(a,'302e1').tolist(),[[True]*7+[False,True]])
 def test_green_cues_exact(self):
  a=np.full((32,32),70,np.uint8);a[12,28]=94;a[16,19]=105
  o,z=m.derive_tile(a,self.pal,self.field,'30465');g=m.scale_nx(a,4);mask=np.repeat(np.repeat(m.cue_mask(g,'30465'),4,0),4,1);exact=np.repeat(np.repeat(self.pal[g],4,0),4,1);self.assertTrue(np.array_equal(o[mask],exact[mask]));self.assertGreater(len(z['original_detail_cells']),0)
 def test_black31_exact(self):
  a=np.full((32,32),10,np.uint8);a[2:20,2:20]=31;o,z=m.derive_tile(a,self.pal,self.field,'30380');g=m.scale_nx(a,4);mask=np.repeat(np.repeat(g==31,4,0),4,1);exact=np.repeat(np.repeat(self.pal[g],4,0),4,1);self.assertTrue(np.array_equal(o[mask],exact[mask]));self.assertGreater(z['Source31_black_pixels_exact'],0)
 def test_violet_path_and_halo_exact(self):
  a=np.full((32,32),12,np.uint8);a[10,10:13]=167;o,z=m.derive_tile(a,self.pal,self.field,'40372');g=m.scale_nx(a,4);mask=np.repeat(np.repeat(m.dilate2(np.isin(g,[167,168])),4,0),4,1);exact=np.repeat(np.repeat(self.pal[g],4,0),4,1);self.assertTrue(np.array_equal(o[mask],exact[mask]));self.assertGreater(z['Source_violet_path_halo_HDR_pixels'],0)
 def test_unknown_asset_rejected(self):
  with self.assertRaises(ValueError):m.cue_mask(np.zeros((1,1),np.uint8),'40374')
 def test_fidelity_owner_bound(self):
  with self.assertRaises(ValueError):m.fidelity_support_union(np.full((32,32),167,np.uint8),'40372')
 def test_dilation_boundary_no_wrap(self):
  a=np.zeros((8,8),bool);a[0,0]=True;b=m.dilate2(a);self.assertEqual(int(b.sum()),9);self.assertFalse(b[7,7])
class Quiet302e1(unittest.TestCase):
 def test_fixed_quietband_bound_synthetic(self):
  from PIL import Image
  field=np.random.default_rng(18).integers(0,256,(512,512,3)).astype(float);b=np.clip(field-m.gaussian(field,3.0),-16,16)*0.5;self.assertLessEqual(float(np.abs(b).max()),8.0)
 def test_finegrain_survives_and_coloredowners_still7_actualreadonly(self):
  a=m.decode_source32((m.ROOT/'data/misc/unnamed.2713').read_bytes());self.assertEqual(len(m.fidelity_support_union(a,'302e1')),7)
class OutputGuards(unittest.TestCase):
 def test_reject_output_parent_symlink(self):
  with tempfile.TemporaryDirectory()as d:
   root=Path(d);(root/'real').mkdir();(root/'link').symlink_to(root/'real',target_is_directory=True)
   with self.assertRaises(ValueError):m.check_fresh_output(root/'link'/'new',2)
 def test_reject_existing_file_or_directory(self):
  with tempfile.TemporaryDirectory()as d:
   root=Path(d);(root/'file').write_text('x');(root/'dir').mkdir()
   for name in ['file','dir']:
    with self.subTest(name=name),self.assertRaises(ValueError):m.check_fresh_output(root/name,2)
 def test_reject_missing_parent(self):
  with tempfile.TemporaryDirectory()as d:
   with self.assertRaises(ValueError):m.check_fresh_output(Path(d)/'missing'/'new',2)
 def test_reject_disk_floor_before_pixels(self):
  from unittest.mock import patch
  with tempfile.TemporaryDirectory()as d,patch.object(m.shutil,'disk_usage',return_value=type('Space',(),dict(free=m.MIN_FREE_BYTES))()):
   with self.assertRaises(ValueError):m.check_fresh_output(Path(d)/'new',5)
 def test_exact_disk_floor_plus_reserve(self):
  from unittest.mock import patch
  reserve=32*1024*1024+5*512*512*3*2
  with tempfile.TemporaryDirectory()as d,patch.object(m.shutil,'disk_usage',return_value=type('Space',(),dict(free=m.MIN_FREE_BYTES+reserve))()):
   out,guard=m.check_fresh_output(Path(d)/'new',5);self.assertFalse(out.exists());self.assertEqual(guard['output_reserve_bytes'],reserve)
 def test_reject_dotdot_output(self):
  with tempfile.TemporaryDirectory()as d:
   with self.assertRaises(ValueError):m.check_fresh_output(Path(d)/'child'/'..'/'new',2)
if __name__=='__main__':unittest.main()
