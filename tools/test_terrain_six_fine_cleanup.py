import unittest,importlib.util,json,tempfile,os,hashlib,struct
from pathlib import Path
import numpy as np
from PIL import Image
p=Path(__file__).with_name('terrain_six_fine_cleanup.py');spec=importlib.util.spec_from_file_location('terrain_six_tested',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
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
  a=np.array([[0,23,24,31,32,47,58,79,100,111,192,239,240,255]],np.uint8);self.assertEqual(m.material_labels(a).tolist(),[[0,0,1,1,2,2,4,5,6,6,3,3,7,7]])
 def test_unknown_index_rejected(self):
  for label in [48,49,57]:
   with self.subTest(label=label),self.assertRaises(ValueError):m.material_labels(np.array([[label]],np.uint8))
 def test_wrong_labeltype_rejected(self):
  with self.assertRaises(ValueError):m.material_labels(np.array([[1]],np.int32))
 def test_union_no_reserved(self):self.assertEqual(m.functional_support_union(np.full((32,32),200,np.uint8)),[])
 def test_union_reserved_near_corner(self):
  a=np.full((32,32),200,np.uint8);a[0,0]=245;u=m.functional_support_union(a);self.assertIn([0,0],u);self.assertTrue(all(0<=x<32 and 0<=y<32 for x,y in u))
 def test_union_wrongcanvas(self):
  with self.assertRaises(ValueError):m.functional_support_union(np.zeros((16,64),np.uint8))
 def test_constant_donor_cannot_claim_HD(self):
  with self.assertRaises(ValueError):m.derive_tile(np.full((32,32),200,np.uint8),self.pal,np.full((512,512,3),100.))
 def test_derive_protected_exact(self):
  a=np.full((32,32),200,np.uint8);a[4,7]=246;field=np.random.default_rng(4).integers(0,256,(512,512,3)).astype(float);out,metrics=m.derive_tile(a,self.pal,field);g=m.scale_nx(a,4);mask=np.repeat(np.repeat(g>=240,4,0),4,1);exact=np.repeat(np.repeat(self.pal[g],4,0),4,1);self.assertTrue(np.array_equal(out[mask],exact[mask]));self.assertGreater(metrics['genuine_RGB_band_changed_nonfunctional_HDR_pixels'],0);self.assertEqual(metrics['Original_functional_HD_credit'],0)
 def test_donor_wrongcanvas(self):
  with self.assertRaises(ValueError):m.derive_tile(np.full((32,32),200,np.uint8),self.pal,np.zeros((511,512,3)))
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


class SixSourceSemantics(unittest.TestCase):
 def test_olive_rust_green_owners_stay_separate(self):
  a=np.array([[58,63,64,79,100,111]],np.uint8);self.assertEqual(m.material_labels(a).tolist(),[[4,4,5,5,6,6]])
 def test_tiny_ordinary_and_cycling_partition(self):
  a=np.array([[80,95,112,134,147,152,171,183,191,240,255]],np.uint8)
  self.assertTrue(np.all(m.material_labels(a)==7));self.assertTrue(np.all(m.protected_indices(a)))
 def test_tiny_ordinary_is_exact_retention_not_generated_band(self):
  a=np.full((32,32),108,np.uint8);a[3,4]=134;a[9,12]=152;a[22,29]=183
  yy,xx=np.indices((512,512));field=np.stack([(xx%5)*40,(yy%7)*32,((xx+yy)%9)*24],axis=2)
  pal=np.arange(768,dtype=np.uint16).reshape(256,3).astype(np.uint8);out,proof=m.derive_tile(a,pal,field);g=m.scale_nx(a,4);mask=np.repeat(np.repeat(m.protected_indices(g),4,0),4,1);exact=np.repeat(np.repeat(pal[g],4,0),4,1)
  self.assertTrue(np.array_equal(out[mask],exact[mask]));self.assertTrue({(4,3),(12,9),(29,22)}<=set(map(tuple,proof['original_detail_cells'])));self.assertEqual(proof['Original_functional_HD_credit'],0)
 def test_union_covers_all_native_scales_for_rare_and_cycling(self):
  a=np.full((32,32),62,np.uint8);a[5,5]=82;a[5,6]=82;a[6,5]=82;a[18,20]=250;u=set(map(tuple,m.functional_support_union(a)))
  for scale in range(1,5):
   yy,xx=np.where(m.protected_indices(m.scale_nx(a,scale)));self.assertTrue({(int(x)//scale,int(y)//scale)for x,y in zip(xx,yy)}<=u)
 def test_nonmatching_crop_uses_own_pixels(self):
  rgb=np.zeros((8,16,3),np.uint8);rgb[:,:8]=[50,70,90];rgb[:,8:]=[160,140,120]
  self.assertTrue(np.all(m.donor_field(rgb,[0,0,8,8],(512,512))==[50,70,90]));self.assertTrue(np.all(m.donor_field(rgb,[8,0,8,8],(512,512))==[160,140,120]))
 def test_real_buffered_complete6_subprocess_receipt(self):
  import subprocess,sys
  with tempfile.TemporaryDirectory()as d:
   root=Path(d);(root/'inputs').mkdir();pal=np.arange(768,dtype=np.uint16).astype(np.uint8).tobytes();(root/'inputs/pal').write_bytes(pal)
   yy,xx=np.indices((128,192));raw=np.stack([(xx%3)*90,(yy%5)*50,((xx+yy)%7)*35],axis=2).astype(np.uint8);Image.fromarray(raw).save(root/'inputs/raw.png')
   h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();frames=[]
   for n,aid in enumerate(['2069f','206a2','206a7','301fc','301fd','30201']):
    src=root/f'inputs/{aid}.bin';a=np.full((32,32),200,np.uint8);a[7,8]=250;a[20,21]=147;src.write_bytes(struct.pack('<5i',1,1,0,32,32)+a.tobytes());frames.append(dict(asset=aid,source=dict(path=f'inputs/{aid}.bin',sha256=h(src)),donor=dict(path='inputs/raw.png',sha256=h(root/'inputs/raw.png'),box=[(n%3)*64,(n//3)*64,64,64])))
   recipe=dict(method=m.METHOD,palette=dict(path='inputs/pal',sha256=h(root/'inputs/pal')),frames=frames,lineage='synthetic true32x32 PIC and structured RGB donor; not production artwork',functional_contract='tests only');r=root/'recipe.json';r.write_text(json.dumps(recipe));out=root/'fresh';z=subprocess.run([sys.executable,str(p),'--recipe',str(r),'--output',str(out)],capture_output=True,text=True,timeout=60);self.assertEqual(z.returncode,0,z.stderr);receipt=json.loads((out/'ACTUAL-DERIVATION-RECEIPT.json').read_text());e=receipt['execution'];self.assertEqual(e['status'],'success');self.assertEqual(e['tool_sha256'],h(p));self.assertEqual(e['recipe_sha256'],h(r));self.assertEqual(e['parent_raw_sha256'],[h(root/'inputs/raw.png')]);self.assertEqual(receipt['physical_authenticated_input_reads'],8);self.assertEqual(len(list(out.glob('*-derived.png'))),6)
   for f in frames:
    aid=f['asset'];self.assertEqual(e['source_sha256'][aid],f['source']['sha256']);self.assertEqual(e['output_sha256'][aid],h(out/(aid+'-derived.png')))

class NewGreenRange(unittest.TestCase):
 def test_entire96_to111_range_is_green_not_retained_Original(self):
  a=np.arange(96,112,dtype=np.uint8).reshape(1,16);self.assertTrue(np.all(m.material_labels(a)==6));self.assertFalse(m.protected_indices(a).any())
 def test_green_low96_keeps_genuine_band_not_Original_only(self):
  a=np.full((32,32),96,np.uint8);yy,xx=np.indices((512,512));field=np.stack([(xx%5)*40,(yy%7)*32,((xx+yy)%9)*24],axis=2);pal=np.arange(768,dtype=np.uint16).reshape(256,3).astype(np.uint8);out,proof=m.derive_tile(a,pal,field);self.assertEqual(proof['original_detail_cells'],[]);self.assertGreater(proof['genuine_RGB_band_changed_nonfunctional_HDR_pixels'],0)
if __name__=='__main__':unittest.main()
