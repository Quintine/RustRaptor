from pathlib import Path
import copy,hashlib,json,struct,tempfile,unittest,importlib.util
from unittest import mock
import numpy as np
from PIL import Image
import hd_terrain_group_retexture as c

ROOT=Path(__file__).resolve().parents[1]
DEP={'path':str(ROOT/'tools/hd_terrain_retexture.py'),'sha256':c.DEPENDENCY_SHA256}

class DeclaredGroupsTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.kernel,cls.dep_pin=c.load_dependency(DEP,Path('.'))
 def setUp(self):
  self.groups=[dict(name='gray',indices=[30,31],texture_log_gain=.2,quiet_from_source_variance=False),dict(name='olive',indices=[62],texture_log_gain=.35,quiet_from_source_variance=True),dict(name='forest',indices=list(range(96,112)),texture_log_gain=.48,quiet_from_source_variance=True),dict(name='brown',indices=[237,238,239],texture_log_gain=.18,quiet_from_source_variance=True)]
  self.params=dict(output_side=64,source_sigma=3.,residual_sigma_fine=.65,residual_sigma_coarse=10.,residual_percentile=80.)
  self.pal=np.zeros((256,3),np.uint8)
  self.pal[:32]=np.arange(31,-1,-1)[:,None]*8
  self.pal[62]=[24,24,0]
  for i in range(96,112):self.pal[i]=[max(0,100-(i-96)*7),max(12,140-(i-96)*8),0]
  self.pal[111]=[0,12,0];self.pal[237:240]=[[48,32,28],[32,16,12],[16,8,4]]
  yy,xx=np.indices((64,64));self.wave=120+40*np.sin(xx*2*np.pi/20)+24*np.cos(yy*2*np.pi/27)
  self.parent=np.stack([self.wave*.9,self.wave*.3,self.wave*1.2],2).clip(0,255).astype(np.uint8)
 def render(self,src,groups=None):return c.reconstruct(src,self.pal,self.parent,self.params,self.groups if groups is None else groups,self.kernel)
 def fixture(self,p,frames=1):
  palette=p/'palette.dat';palette.write_bytes((self.pal//4).tobytes());parent=p/'parent.png';Image.fromarray(self.parent).save(parent)
  ref=lambda q:dict(path=q.name,sha256=hashlib.sha256(q.read_bytes()).hexdigest())
  source=p/'source.pic';source.write_bytes(struct.pack('<5i',1,1,0,4,4)+bytes([111,111,31,31,103,103,62,62,237,237,111,111,31,31,111,111]))
  recipe=dict(format_version=2,method=c.METHOD,dependency=DEP,palette=ref(palette),material_groups=self.groups,parameters=self.params,
   frames=[dict(asset=format(0x2061d+i,'x'),Source=ref(source),parent_raw=ref(parent),crop=[0,0,64,64],origin=[0,0]) for i in range(frames)])
  rp=p/'recipe.json';rp.write_text(json.dumps(recipe));return recipe,rp,source
 def test_explicit_forest_support_and_legacy_globals_unchanged(self):
  before=copy.deepcopy(self.kernel.DEFAULTS);names=self.kernel.FAMILY_NAMES
  with self.assertRaisesRegex(ValueError,'unsupported material'):self.kernel.material_families(np.full((4,4),100,np.uint8))
  out,base,owners,m=self.render(np.full((4,4),100,np.uint8))
  self.assertGreater(m['pixels_changed_from_Source_guided_base'],40);self.assertTrue(np.all(owners==2))
  self.assertEqual(self.kernel.DEFAULTS,before);self.assertEqual(self.kernel.FAMILY_NAMES,names)
 def test_disjoint_complete_used_coverage_and_reserved_rejection(self):
  for mutate in ('overlap','missing','reserved','duplicate','bool','unsorted'):
   g=copy.deepcopy(self.groups)
   if mutate=='overlap':g[-1]['indices']=[31,237,238,239]
   if mutate=='missing':g[2]['indices'].remove(111)
   if mutate=='reserved':g[-1]['indices'].append(240)
   if mutate=='duplicate':g[-1]['indices']=[237,237,238,239]
   if mutate=='bool':g[0]['indices']=[False,30,31]
   if mutate=='unsorted':g[0]['indices']=[31,30]
   with self.assertRaises(ValueError):c.groups_validated(g,[111])
 def test_names_gains_and_flags_are_strict(self):
  for name,value in [('name','../green'),('texture_log_gain',True),('texture_log_gain',float('nan')),('texture_log_gain',.71),('quiet_from_source_variance',1)]:
   g=copy.deepcopy(self.groups);g[2][name]=value
   with self.assertRaises(ValueError):c.groups_validated(g)
  g=copy.deepcopy(self.groups);g[-1]['name']=g[0]['name']
  with self.assertRaises(ValueError):c.groups_validated(g)
 def test_SourceNx_material_owner_geometry_and_determinism(self):
  src=np.array([[31,31,103,103],[31,62,62,103],[237,237,103,111],[239,239,111,111]],np.uint8)
  a=self.render(src);b=self.render(src);lookup=np.full(240,-1,np.int16)
  for i,g in enumerate(self.groups):lookup[g['indices']]=i
  expected=np.repeat(np.repeat(lookup[self.kernel.scale_nx(src,4)],4,0),4,1)
  np.testing.assert_array_equal(a[2],expected);np.testing.assert_array_equal(a[0],b[0]);self.assertEqual(a[3],b[3])
 def test_coherent_generated_fine_mid_structure_is_retained(self):
  out,base,_,m=self.render(np.full((4,4),100,np.uint8))
  self.assertGreater(float(np.corrcoef(out[:,:,1].ravel(),self.wave.ravel())[0,1]),.9)
  self.assertGreater(float(out[:,:,1].std()),1);self.assertGreater(m['mean_absolute_parent_tone_modulation'],.3)
 def test_Source_color_family_zero_channels_and_gray_preserved(self):
  for idx in [30,62,111]:
   out,base,_,m=self.render(np.full((4,4),idx,np.uint8))
   if idx==30:np.testing.assert_array_equal(out[:,:,0],out[:,:,2])
   if idx==62:np.testing.assert_array_equal(out[:,:,0],out[:,:,1]);self.assertTrue(np.all(out[:,:,2]==0))
   if idx==111:self.assertTrue(np.all(out[:,:,[0,2]]==0));self.assertGreater(out[:,:,1].max(),out[:,:,1].min())
   self.assertGreaterEqual(m['actual_tone_gain_min'],np.exp(-.7));self.assertLessEqual(m['actual_tone_gain_max'],np.exp(.7))
 def test_flat_parent_and_zero_gain_do_not_silently_return_Source(self):
  with self.assertRaisesRegex(ValueError,'lacks coherent'):c.reconstruct(np.full((4,4),111,np.uint8),self.pal,np.full((64,64,3),90,np.uint8),self.params,self.groups,self.kernel)
  g=copy.deepcopy(self.groups)
  for z in g:z['texture_log_gain']=0
  with self.assertRaisesRegex(ValueError,'modulation too small'):self.render(np.full((4,4),111,np.uint8),g)
 def test_old_four_family_declaration_reproduces_old_math_exactly(self):
  groups=[dict(name='gray',indices=list(range(32)),texture_log_gain=.38,quiet_from_source_variance=False),dict(name='olive',indices=list(range(60,64)),texture_log_gain=.55,quiet_from_source_variance=False),dict(name='soil',indices=list(range(192,224))+[239],texture_log_gain=.34,quiet_from_source_variance=True),dict(name='rim',indices=list(range(224,239)),texture_log_gain=.06,quiet_from_source_variance=False)]
  palette=self.pal.copy();palette[202]=[60,24,20];palette[231]=[81,60,52];palette[63]=[12,12,0]
  src=np.array([[30,30,231,63],[30,30,231,202],[30,30,231,231],[30,30,30,30]],np.uint8)
  p=dict(self.params,texture_log_gain=dict(gray=.38,olive=.55,soil=.34,rim=.06))
  a=self.kernel.reconstruct(src,palette,self.parent,p);b=c.reconstruct(src,palette,self.parent,self.params,groups,self.kernel)
  for i in range(3):np.testing.assert_array_equal(a[i],b[i])
 def test_Source_reserved_wrong_format_and_float_planes_fail(self):
  for src in [np.full((4,4),240,np.uint8),np.full((4,4),111.,float),np.ones((3,4),np.uint8)]:
   with self.assertRaises(ValueError):self.render(src)
  with self.assertRaises(ValueError):self.kernel.decode_source(struct.pack('<5i',0,1,0,4,4)+bytes([111]*16))
 def test_relative_atomic_success_normalized_receipt_and_all_bindings(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);r,rp,src=self.fixture(p,2);out=p/'new';result=c.run(rp,out)
   execution=result['execution'];self.assertEqual(set(execution),{'status','method','recipe_sha256','tool_sha256','source_sha256','parent_raw_sha256','output_sha256'})
   self.assertEqual(result['dependency']['sha256'],c.DEPENDENCY_SHA256);self.assertEqual(result['decoder']['module_sha256'],c.DEPENDENCY_SHA256)
   self.assertTrue(result['runtime']['numpy']);self.assertTrue(result['runtime']['Pillow']);self.assertTrue(result['runtime']['python'])
   for asset,want in execution['output_sha256'].items():self.assertEqual(hashlib.sha256((out/(asset+'-DERIVED-declared-material-v1.png')).read_bytes()).hexdigest(),want)
   self.assertEqual(json.loads((out/'normalized-execution-object.json').read_text()),dict(execution=execution))
   before={x.name:x.read_bytes() for x in out.iterdir()}
   with self.assertRaisesRegex(ValueError,'never overwrite'):c.run(rp,out)
   self.assertEqual(before,{x.name:x.read_bytes() for x in out.iterdir()});self.assertFalse(list(p.glob('.new.stage-*')))
 def test_typed_asset_path_escape_and_source_sentinels_preserved(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);r,rp,src=self.fixture(p);sentinel=p/'sentinel-DERIVED-declared-material-v1.png';sentinel.write_bytes(b'EXISTING')
   for i,bad in enumerate(['../sentinel',str(p/'sentinel'),'0x2061d','2061D','02061d',False,17,'',None]):
    z=copy.deepcopy(r);z['frames'][0]['asset']=bad;rp.write_text(json.dumps(z));out=p/('absent'+str(i))
    with self.assertRaisesRegex(ValueError,'canonical'):c.run(rp,out)
    self.assertFalse(out.exists());self.assertEqual(sentinel.read_bytes(),b'EXISTING')
 def test_boolean_version_origin_crop_and_duplicate_ids_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   r,_,_=self.fixture(Path(d),2)
   for mutate in ('version','origin','crop','duplicate','order'):
    z=copy.deepcopy(r)
    if mutate=='version':z['format_version']=True
    if mutate=='origin':z['frames'][0]['origin']=[False,0]
    if mutate=='crop':z['frames'][0]['crop'][0]=False
    if mutate=='duplicate':z['frames'][1]['asset']=z['frames'][0]['asset']
    if mutate=='order':z['frames'].reverse()
    with self.assertRaises(ValueError):c.validate_recipe(z)
 def test_dependency_forgery_and_symlink_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);fake=p/'fake.py';fake.write_text('raise RuntimeError("MUST NEVER EXECUTE")')
   with self.assertRaisesRegex(ValueError,'hash mismatch'):c.load_dependency(dict(path=str(fake),sha256=c.DEPENDENCY_SHA256),p)
   with self.assertRaisesRegex(ValueError,'only exact'):c.load_dependency(dict(path=str(fake),sha256='0'*64),p)
   link=p/'link.py';link.symlink_to(DEP['path'])
   with self.assertRaises(OSError):c.load_dependency(dict(path=str(link),sha256=c.DEPENDENCY_SHA256),p)
 def test_bad_raw_hash_transparency_crop_and_Source_symlink_leave_no_outputs(self):
  for mutation in ('hash','alpha','crop','symlink'):
   with tempfile.TemporaryDirectory() as d:
    p=Path(d);r,rp,src=self.fixture(p);out=p/'absent'
    if mutation=='hash':r['frames'][0]['parent_raw']['sha256']='0'*64
    if mutation=='alpha':
     im=np.concatenate([self.parent,np.full((64,64,1),254,np.uint8)],2);Image.fromarray(im).save(p/'parent.png');r['frames'][0]['parent_raw']['sha256']=hashlib.sha256((p/'parent.png').read_bytes()).hexdigest()
    if mutation=='crop':r['frames'][0]['crop']=[1,0,64,64]
    if mutation=='symlink':
     link=p/'link.pic';link.symlink_to(src);r['frames'][0]['Source']['path']=link.name
    rp.write_text(json.dumps(r))
    with self.assertRaises((ValueError,OSError)):c.run(rp,out)
    self.assertFalse(out.exists());self.assertFalse(list(p.glob('.absent.stage-*')))
 def test_atomic_publish_failure_rolls_back_stage_only(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);r,rp,src=self.fixture(p);raw_before=(p/'parent.png').read_bytes();source_before=src.read_bytes()
   with mock.patch.object(c,'publish_no_replace',side_effect=OSError('synthetic atomic failure')):
    with self.assertRaisesRegex(OSError,'synthetic atomic'):c.run(rp,p/'absent')
   self.assertFalse((p/'absent').exists());self.assertFalse(list(p.glob('.absent.stage-*')));self.assertEqual(src.read_bytes(),source_before);self.assertEqual((p/'parent.png').read_bytes(),raw_before)
 def test_racing_existing_directory_is_never_replaced(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);stage=p/'stage';stage.mkdir();(stage/'new').write_bytes(b'NEW');target=p/'target';target.mkdir();ino=target.stat().st_ino
   with self.assertRaises(OSError):c.publish_no_replace(stage,target)
   self.assertEqual(target.stat().st_ino,ino);self.assertFalse(list(target.iterdir()));self.assertTrue((stage/'new').exists())
 def test_input_changed_during_prepare_prevents_publication(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);r,rp,src=self.fixture(p);real=c.reconstruct
   def mutate(*args,**kwargs):
    result=real(*args,**kwargs);src.write_bytes(src.read_bytes()+b'CHANGED');return result
   with mock.patch.object(c,'reconstruct',side_effect=mutate):
    with self.assertRaisesRegex(ValueError,'changed across'):c.run(rp,p/'absent')
   self.assertFalse((p/'absent').exists());self.assertFalse(list(p.glob('.absent.stage-*')))

 def test_reflection_integer_geometry_no_edge_repeat(self):
  np.testing.assert_array_equal(c.reflect_axis(np.arange(-2,7),3),[2,1,0,1,2,1,0,1,2])
  np.testing.assert_array_equal(c.reflect_axis(np.arange(-3,4),1),np.zeros(7,int))
  with self.assertRaises(ValueError):c.reflect_axis(np.array([.5]),3)

 def test_original_donor_location_and_all_RGB_samples_match_before_resize(self):
  y,x=np.indices((20,22));parent=np.stack([x*7,y*9,(x+y)*5],2).astype(np.uint8)
  crop=[2,3,14,13];donor=[6,7,5,4];field,proof=c.reflect_parent_region(parent,crop,donor)
  self.assertEqual(field.shape,(13,14,3));np.testing.assert_array_equal(field[4:8,4:9],parent[7:11,6:11])
  self.assertEqual(proof['donor_RGB_sha256'],hashlib.sha256(parent[7:11,6:11].tobytes()).hexdigest())
  self.assertFalse(proof['resampling_before_native_frame_field'])
  xs=6+c.reflect_axis(np.arange(14)+2-6,5);ys=7+c.reflect_axis(np.arange(13)+3-7,4)
  np.testing.assert_array_equal(field,parent[ys[:,None],xs[None,:]])

 def test_reflection_keeps_original_pixel_density_not_stretched_donor(self):
  y,x=np.indices((80,80));parent=np.stack([x,x+y,y],2).astype(np.uint8)
  field,_=c.reflect_parent_region(parent,[1,1,64,64],[20,20,16,16])
  # Thirty sample period, unit steps; a donor enlarged to64 first cannot satisfy.
  np.testing.assert_array_equal(field[20,0:30],field[20,30:60])
  self.assertTrue(set(np.abs(np.diff(field[20,:,0].astype(int))))<={1})

 def test_no_region_and_empty_region_arrays_exact_frozen_v1(self):
  path=ROOT/'tools/fixtures/hd_terrain_group_retexture_v1.py'
  self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),'425db50b811edec71568bc82e7aca7cbfacc330e5dd78f276951062bee18c8d7')
  spec=importlib.util.spec_from_file_location('frozen_groups_v1',path);v1=importlib.util.module_from_spec(spec);spec.loader.exec_module(v1)
  src=np.array([[31,31,103,103],[31,62,62,103],[237,237,103,111],[239,239,111,111]],np.uint8)
  old=v1.reconstruct(src,self.pal,self.parent,self.params,self.groups,self.kernel)
  for fields in (None,{}):
   new=c.reconstruct(src,self.pal,self.parent,self.params,self.groups,self.kernel,fields)
   for i in range(3):np.testing.assert_array_equal(new[i],old[i])

 def test_only_declared_Source_owner_receives_its_changed_region_band(self):
  src=np.full((4,4),100,np.uint8);src[:,2:]=31
  y,x=np.indices((64,64));one=np.repeat((110+30*np.sin(x/3.))[...,None],3,2).astype(np.uint8)
  two=np.repeat((110+30*np.cos(y/4.))[...,None],3,2).astype(np.uint8)
  a=c.reconstruct(src,self.pal,self.parent,self.params,self.groups,self.kernel,{'forest':one})
  b=c.reconstruct(src,self.pal,self.parent,self.params,self.groups,self.kernel,{'forest':two})
  changed=np.any(a[0]!=b[0],2);self.assertGreater(int(changed.sum()),20)
  self.assertTrue(np.all(a[2][changed]==2));np.testing.assert_array_equal(a[0][a[2]==0],b[0][b[2]==0])

 def test_fullcrop_wrong_edge_changes_cannot_enter_complete_regional_fields(self):
  y,x=np.indices((64,64));wave=8*np.sin(x/2.)+6*np.cos(y/3.)
  level=np.where(x+y<63,35,145)+wave;parent=np.repeat(level[...,None],3,2).clip(0,255).astype(np.uint8)
  crop=[0,0,64,64];regions={'dark':[3,3,16,16],'light':[45,45,16,16]}
  altered=parent.copy();keep=np.zeros((64,64),bool)
  for xx,yy,w,h in regions.values():keep[yy:yy+h,xx:xx+w]=True
  altered[~keep]=np.repeat(((x*5+y*3)%240)[...,None],3,2)[~keep]
  groups=[dict(name='dark',indices=list(range(26,32)),texture_log_gain=.38,quiet_from_source_variance=False),dict(name='light',indices=list(range(26)),texture_log_gain=.38,quiet_from_source_variance=False)]
  src=np.array([[28,28,28,21],[28,28,21,21],[28,28,21,21],[28,21,21,21]],np.uint8)
  fields_a={k:c.reflect_parent_region(parent,crop,r)[0] for k,r in regions.items()};fields_b={k:c.reflect_parent_region(altered,crop,r)[0] for k,r in regions.items()}
  for name in fields_a:np.testing.assert_array_equal(fields_a[name],fields_b[name])
  a=c.reconstruct(src,self.pal,parent,self.params,groups,self.kernel,fields_a);b=c.reconstruct(src,self.pal,altered,self.params,groups,self.kernel,fields_b)
  np.testing.assert_array_equal(a[0],b[0]);np.testing.assert_array_equal(a[2],b[2])
  self.assertLessEqual(a[3]['actual_tone_gain_max'],np.exp(.38));self.assertGreaterEqual(a[3]['actual_tone_gain_min'],np.exp(-.38))

 def test_region_keys_rectangles_and_strict_interior_are_validated(self):
  crop=[10,20,60,60]
  for regions in [None,[],{'unknown':[12,22,5,5]},{'forest':[10,22,5,5]},{'forest':[12,20,5,5]},{'forest':[12,22,58,5]},{'forest':[12,22,5,58]},{'forest':[12,22,0,5]},{'forest':[False,22,5,5]},{'forest':[12.,22,5,5]},{'forest':{'rect':[12,22,5,5]}}]:
   with self.assertRaises(ValueError):c.validate_regions(regions,crop,self.groups)
  c.validate_regions({},crop,self.groups);c.validate_regions({'forest':[12,22,5,5]},crop,self.groups)

 def test_material_field_dtype_shape_and_unknown_key_reject(self):
  src=np.full((4,4),100,np.uint8)
  for fields in [{'unknown':self.parent},{'forest':self.parent.astype(float)},{'forest':self.parent[:16,:16]},[]]:
   with self.assertRaises(ValueError):c.reconstruct(src,self.pal,self.parent,self.params,self.groups,self.kernel,fields)

 def test_regional_CLI_receipt_binds_actual_raw_donor_and_reflected_field(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);r,rp,src=self.fixture(p);r['frames'][0]['material_parent_regions']={'forest':[4,4,20,20]};rp.write_text(json.dumps(r))
   receipt=c.run(rp,p/'new');proof=receipt['frames'][0]['metrics']['material_parent_region_proofs']['forest']
   raw=np.array(Image.open(p/'parent.png').convert('RGB'));field,expected=c.reflect_parent_region(raw,[0,0,64,64],[4,4,20,20])
   self.assertEqual(proof,expected);self.assertEqual(proof['donor_RGB_sha256'],hashlib.sha256(raw[4:24,4:24].tobytes()).hexdigest())
   self.assertEqual(proof['reflected_native_field_RGB_sha256'],hashlib.sha256(field.tobytes()).hexdigest())
   self.assertEqual(set(receipt['execution']),{'status','method','recipe_sha256','tool_sha256','source_sha256','parent_raw_sha256','output_sha256'})

 def test_invalid_region_never_creates_output_or_changes_parent(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);r,rp,src=self.fixture(p);raw=(p/'parent.png').read_bytes();s=src.read_bytes();r['frames'][0]['material_parent_regions']={'forest':[62,62,5,5]};rp.write_text(json.dumps(r))
   with self.assertRaisesRegex(ValueError,'strictly inside'):c.run(rp,p/'absent')
   self.assertFalse((p/'absent').exists());self.assertEqual((p/'parent.png').read_bytes(),raw);self.assertEqual(src.read_bytes(),s)

if __name__=='__main__':unittest.main()
