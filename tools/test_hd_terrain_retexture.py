import pathlib,sys,copy,unittest
import numpy as np
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import hd_terrain_retexture as c
class CoherentTextureTests(unittest.TestCase):
 def setUp(self):
  self.palette=np.zeros((256,3),np.uint8)
  for i in range(32):self.palette[i]=[i*4]*3
  self.palette[60:64]=[[56,52,4],[40,40,0],[24,24,0],[12,12,0]]
  self.palette[200:208]=[[85,40,36],[81,36,32],[73,32,28],[69,28,24],[60,24,20],[56,16,16],[40,12,8],[20,0,0]];self.palette[231]=[81,60,52]
  self.p=copy.deepcopy(c.DEFAULTS);self.p['output_side']=64
 def test_coherent_midscale_structure_survives_not_random_noise(self):
  yy,xx=np.indices((64,64));lum=(120+45*np.sin(xx*2*np.pi/20)+25*np.cos(yy*2*np.pi/27));raw=np.repeat(lum[...,None],3,2).clip(0,255).astype(np.uint8)
  out,base,_,m=c.reconstruct(np.full((4,4),27,np.uint8),self.palette,raw,self.p)
  correlation=np.corrcoef(out[...,0].flatten(),lum.flatten())[0,1]
  self.assertGreater(correlation,.90);self.assertGreater(out[...,0].std(),3)
  self.assertGreater(m['mean_absolute_parent_tone_modulation'],2)
 def test_gray_achromatic_and_olive_hue_not_shifted(self):
  raw=np.random.default_rng(8).integers(0,256,(64,64,3),dtype=np.uint8)
  for index in [27,63]:
   out,_,_,m=c.reconstruct(np.full((4,4),index,np.uint8),self.palette,raw,self.p)
   if index==27:np.testing.assert_array_equal(out[...,0],out[...,2])
   else:self.assertTrue(np.all(out[...,2]==0));self.assertTrue(np.all(out[...,0]==out[...,1]))
   self.assertGreaterEqual(m['actual_tone_gain_min'],np.exp(-.55));self.assertLessEqual(m['actual_tone_gain_max'],np.exp(.55))
 def test_source_quiet_soil_receives_less_texture(self):
  raw=np.random.default_rng(1).integers(0,256,(64,64,3),dtype=np.uint8);calm=np.full((4,4),202,np.uint8);busy=np.array([[200,207]*2,[207,200]*2]*2,np.uint8)
  m1=c.reconstruct(calm,self.palette,raw,self.p)[3];m2=c.reconstruct(busy,self.palette,raw,self.p)[3]
  self.assertAlmostEqual(m1['Source_derived_soil_quiet_strength_max'],.35,places=5)
  self.assertGreater(m2['Source_derived_soil_quiet_strength_min'],.8)
 def test_source_L_and_material_geometry_exact_with_coherent_texture(self):
  src=np.array([[27,27,231,63],[27,27,231,202],[27,27,231,231],[27,27,27,27]],np.uint8);raw=np.random.default_rng(4).integers(0,256,(64,64,3),dtype=np.uint8)
  a=c.reconstruct(src,self.palette,raw,self.p);b=c.reconstruct(src,self.palette,raw,self.p)
  expected=np.repeat(np.repeat(c.material_families(c.scale_nx(src,4)),4,0),4,1)
  np.testing.assert_array_equal(a[2],expected);np.testing.assert_array_equal(a[0],b[0]);self.assertEqual(a[3],b[3])
 def test_constant_parent_does_not_invent_texture(self):
  out,base,_,m=c.reconstruct(np.full((4,4),63,np.uint8),self.palette,np.full((64,64,3),170,np.uint8),self.p)
  np.testing.assert_array_equal(out,base);self.assertEqual(m['pixels_changed_from_Source_guided_base'],0)
 def test_invalid_gain_and_material_fail(self):
  p=copy.deepcopy(self.p);p['texture_log_gain']['gray']=float('inf')
  with self.assertRaises(ValueError):c.reconstruct(np.full((4,4),27,np.uint8),self.palette,np.zeros((64,64,3),np.uint8),p)
  with self.assertRaises(ValueError):c.reconstruct(np.full((4,4),100,np.uint8),self.palette,np.zeros((64,64,3),np.uint8),self.p)
 def test_relative_cli_receipt_binds_runtime_versions(self):
  import tempfile,json,struct,hashlib,PIL
  from PIL import Image
  with tempfile.TemporaryDirectory()as d:
   root=pathlib.Path(d);src=root/'source.pic';src.write_bytes(struct.pack('<5i',1,1,0,4,4)+bytes([63]*16));pal=root/'palette.dat';pal.write_bytes((self.palette//4).tobytes());raw=root/'parent.png';Image.fromarray(np.full((64,64,3),100,np.uint8)).save(raw)
   def binding(p):return dict(path=p.name,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
   recipe=dict(method=c.METHOD,palette=binding(pal),parameters=self.p,frames=[dict(asset='20400',Source=binding(src),parent_raw=binding(raw),crop=[0,0,64,64])]);rp=root/'recipe.json';rp.write_text(json.dumps(recipe));out=root/'out';c.main(['--recipe',str(rp),'--output',str(out)])
   report=json.loads((out/'DERIVED-LINEAGE-AND-ACTUAL-RECONSTRUCTION-METRICS.json').read_text());expected=dict(python=sys.version,executable=sys.executable,numpy=np.__version__,Pillow=PIL.__version__,platform=sys.platform)
   self.assertEqual(report['runtime'],expected);self.assertEqual(report['execution']['runtime'],expected)
   self.assertEqual(report['execution']['output_sha256']['20400'],hashlib.sha256((out/'20400-DERIVED-source-guided-material-v1.png').read_bytes()).hexdigest())
if __name__=='__main__':unittest.main()
