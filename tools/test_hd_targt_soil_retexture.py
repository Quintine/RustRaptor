"""Synthetic input containment, unchanged material, alpha and execution tests."""
from pathlib import Path
import copy,hashlib,struct,tempfile,types,unittest
import numpy as np
import hd_targt_soil_retexture as h
import hd_terrain_retexture as kernel
import hd_frame_policy as decoder

def recipe():
    ref=lambda name,digest='0'*64:dict(path=name,sha256=digest)
    r=dict(format_version=1,method=h.METHOD,parameters=copy.deepcopy(h.PARAMETERS),palette=ref('palette',h.PALETTE_SHA),donor=ref('donor.png',h.DONOR_SHA),phase0=ref('phase0.png',h.PHASE0_SHA),ancestor_raw=ref('ancestor.png',h.ANCESTOR_RAW_SHA),ancestor_recipe=ref('ancestor.json'),kernel=ref('tools/kernel.py',h.KERNEL_SHA),decoder=ref('tools/decoder.py',h.DECODER_SHA),frames=[])
    for i in range(14):r['frames'].append(dict(asset=f'{0x10152+i:x}',source=ref('sources/TARGT_PIC'+('.'+str(i)if i else '')),accepted803_RGBA=ref(f'parents/{i}.png'),origin=[0,0],original_detail_cells=h.selectors(i)))
    return r

class PortableInputTests(unittest.TestCase):
    def test_recipe_is_complete_and_runtime_retention_totals350(self):
        r=recipe();self.assertIs(h.validate_recipe(r),r);self.assertEqual(sum(len(f['original_detail_cells'])for f in r['frames']),350)
    def test_reject_asset_reordering_and_short_family(self):
        for mode in ['swap','short']:
            r=recipe()
            if mode=='swap':r['frames'][0],r['frames'][1]=r['frames'][1],r['frames'][0]
            else:r['frames'].pop()
            with self.assertRaises(ValueError):h.validate_recipe(r)
    def test_literal_parameter_types_and_unchanged_gains(self):
        for value in [1,True,.51]:
            r=recipe();r['parameters']['Source_macro_sigma_logical']=value
            with self.assertRaises(ValueError):h.validate_recipe(r)
    def test_runtime_retention_cannot_shift_or_grow(self):
        for i in [0,5,6,7,8,9,10]:
            r=recipe();r['frames'][i]['original_detail_cells'].append([1,1])
            with self.assertRaises(ValueError):h.validate_recipe(r)
    def test_boolean_origin_is_not_zero_coordinate(self):
        r=recipe();r['frames'][0]['origin']=[False,0]
        with self.assertRaises(ValueError):h.validate_recipe(r)
    def test_source_numbering_is_literal(self):
        r=recipe();r['frames'][2]['source']['path']='sources/another.2'
        with self.assertRaises(ValueError):h.validate_recipe(r)
    def test_fixed_raws_and_verified_dependencies_cannot_be_rebound(self):
        for name in ['palette','donor','phase0','ancestor_raw','kernel','decoder']:
            r=recipe();r[name]['sha256']='0'*64
            with self.assertRaises(ValueError):h.validate_recipe(r)
    def test_reject_nonportable_or_escaping_path(self):
        for p in ['/tmp/a','../a','a/../b','a//b','a/./b','C:/x','a\\b','', '.']:
            with self.assertRaises(ValueError,msg=p):h.relative(p)
    def test_exact_reference_shape_and_hash(self):
        for ref in [dict(path='x',sha256='A'*64),dict(path='x',sha256='0'*64,extra=True),dict(path='../x',sha256='0'*64)]:
            with self.assertRaises(ValueError):h.reference(ref)
    def test_project_symlink_file_and_directory_rejected(self):
        with tempfile.TemporaryDirectory()as td:
            p=Path(td);(p/'real').mkdir();(p/'real/x').write_text('hi');(p/'alias').symlink_to(p/'real',target_is_directory=True);(p/'file').symlink_to(p/'real/x')
            for name in ['alias/x','file']:
                with self.assertRaises(ValueError):h.contained(p,name)
    def test_read_hash_is_checked_on_same_regular_bytes(self):
        with tempfile.TemporaryDirectory()as td:
            p=Path(td)/'x';p.write_bytes(b'checked');self.assertEqual(h.read_regular(p,hashlib.sha256(b'checked').hexdigest()),b'checked')
            with self.assertRaises(ValueError):h.read_regular(p,'0'*64)
    def test_verified_module_executes_supplied_bytes_not_reopened_path(self):
        with tempfile.TemporaryDirectory()as td:
            p=Path(td)/'dep.py';p.write_text('value=1\n');verified=h.read_regular(p);p.write_text('value=999\n')
            self.assertEqual(h.load_verified(verified,p,'test_verified').value,1)
    def test_decoder_opaque_bytes_and_sparse_transparency(self):
        raw=struct.pack('<iiiii',1,0,0,32,32)+bytes([197])*1024
        self.assertTrue(np.all(h.decode_source(decoder,raw)==197))
        sparse=struct.pack('<iiiii',0,0,0,32,32)+struct.pack('<iiii',2,3,0,2)+bytes([80,82])+struct.pack('<iiii',0,0,-1,0)
        s=h.decode_source(decoder,sparse);self.assertEqual(int((s<256).sum()),2);self.assertEqual(s[3,2],80)
    def test_existing_output_is_never_replaced(self):
        with tempfile.TemporaryDirectory()as td:
            p=Path(td);(p/'recipe').write_text('{}');(p/'output').mkdir();(p/'output/keep').write_bytes(b'exact')
            with self.assertRaises(ValueError):h.run(p,'recipe','output')
            self.assertEqual((p/'output/keep').read_bytes(),b'exact')

class SyntheticMaterialTests(unittest.TestCase):
    def setup_material(self):
        source=np.full((32,32),197,np.uint16);source[:2]=256;source[10:14,10:14]=10
        palette=np.zeros((256,3),np.uint8);palette[197]=[103,55,46];palette[10]=[18,18,18]
        parent=np.zeros((256,256,4),np.uint8);alpha=h.expand(source<256,8);parent[alpha,:3]=[34,28,20];parent[alpha,3]=255
        static=np.zeros((32,32),bool);static[2,:]=True
        yy,xx=np.indices((256,256));fine=np.sin(xx/3.)*.75+np.cos(yy/5.)*.5
        return source,palette,parent,static,[fine]
    def test_retexture_preserves_every_protected_RGBA_and_alpha(self):
        s,p,a,static,bands=self.setup_material();out,metrics=h.apply_frame(a,s,p,static,bands,kernel)
        mutable=h.expand((s>=194)&(s<=239)&~static,8)
        np.testing.assert_array_equal(out[~mutable],a[~mutable]);np.testing.assert_array_equal(out[:,:,3],a[:,:,3]);self.assertTrue(metrics['protected_RGBA_exact']);self.assertGreater(metrics['changed_soil_pixels'],0)
    def test_retexture_is_deterministic_and_source_group_mean_is_stable(self):
        s,p,a,static,bands=self.setup_material();one,m=h.apply_frame(a,s,p,static,bands,kernel);two,_=h.apply_frame(a,s,p,static,bands,kernel)
        np.testing.assert_array_equal(one,two);self.assertLess(max(abs(x-y)for x,y in zip(m['Source_RGB_mean'],m['actual_RGB_mean'])),1.)
    def test_nonuniform_source_pattern_runs_finite_correlation_branch(self):
        s,p,a,static,bands=self.setup_material();yy,xx=np.indices(s.shape)
        s[(s==197)&((xx//4+yy//4)%2==0)]=198;p[198]=[115,67,58]
        out,m=h.apply_frame(a,s,p,static,bands,kernel)
        self.assertGreater(m['Source_luma_std'],.05)
        self.assertTrue(np.isfinite(m['Source_pattern_correlation']))
        self.assertGreater(m['Source_pattern_correlation'],.90)
        self.assertTrue(m['protected_RGBA_exact'])
    def test_no_soil_returns_exact_parent(self):
        s,p,a,static,bands=self.setup_material();s[s==197]=10;a[:,:,3]=h.expand(s<256,8)*255
        out,m=h.apply_frame(a,s,p,static,bands,kernel);np.testing.assert_array_equal(out,a);self.assertEqual(m['mutable_cells'],0)
    def test_wrong_alpha_or_nonfinite_fine_is_rejected(self):
        s,p,a,static,bands=self.setup_material();bad=a.copy();bad[0,0,3]=255
        with self.assertRaises(ValueError):h.apply_frame(bad,s,p,static,bands,kernel)
        bands[0][0,0]=np.nan
        with self.assertRaises(ValueError):h.apply_frame(a,s,p,static,bands,kernel)

if __name__=='__main__':unittest.main()
