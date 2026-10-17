import copy
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import numpy as np
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parent))
import hd_terrain_cleanup as c

class TerrainCleanupTests(unittest.TestCase):
    def setUp(self):
        self.palette = np.zeros((256, 3), np.uint8)
        for i in range(32): self.palette[i] = [4*i]*3
        self.palette[60:64] = [[56,52,4],[40,40,0],[24,24,0],[12,12,0]]
        self.palette[200:208] = [[85,40,36],[81,36,32],[73,32,28],[69,28,24],[60,24,20],[56,16,16],[40,12,8],[20,0,0]]
        self.palette[231] = [81,60,52]
        self.p = copy.deepcopy(c.DEFAULTS); self.p['output_side'] = 64

    def test_constant_parent_has_no_retained_texture(self):
        source = np.full((4,4),63,np.uint8)
        out, base, labels, m = c.reconstruct(source,self.palette,np.full((64,64,3),180,np.uint8),self.p)
        np.testing.assert_array_equal(out,base)
        self.assertEqual(m['pixels_changed_from_Source_guided_base'],0)
        np.testing.assert_array_equal(out,np.broadcast_to(self.palette[63],out.shape))

    def test_parent_colour_and_constant_lighting_are_not_carried(self):
        source = np.full((4,4),63,np.uint8)
        a = np.full((64,64,3),[200,5,50],np.uint8)
        b = np.full((64,64,3),[10,240,70],np.uint8)
        np.testing.assert_array_equal(c.reconstruct(source,self.palette,a,self.p)[0],c.reconstruct(source,self.palette,b,self.p)[0])

    def test_fine_generated_detail_is_retained_but_bounded(self):
        yy,xx = np.indices((64,64)); raw = np.repeat((120+40*np.sin(xx*1.9)+20*np.sin(yy*2.1))[...,None],3,2).clip(0,255).astype(np.uint8)
        out,base,labels,m = c.reconstruct(np.full((4,4),202,np.uint8),self.palette,raw,self.p)
        self.assertGreater(m['pixels_changed_from_Source_guided_base'],1500)
        self.assertGreater(m['mean_absolute_generated_residual'],0.5)
        self.assertLessEqual(np.abs(out.astype(float)-base).max(),3)
        self.assertLessEqual(m['maximum_retained_luma_residual'],2.5)

    def test_exact_family_geometry_and_thin_L_are_preserved(self):
        source = np.array([[27,27,231,63],[27,27,231,63],[27,27,231,231],[27,27,27,27]],np.uint8)
        raw = np.random.default_rng(9).integers(0,256,(80,80,3),dtype=np.uint8)
        out,base,labels,m = c.reconstruct(source,self.palette,raw,self.p)
        expected = c.material_families(c.scale_nx(source,4))
        np.testing.assert_array_equal(labels,np.repeat(np.repeat(expected,4,0),4,1))
        self.assertTrue(np.all(out[labels==0].max(axis=1)-out[labels==0].min(axis=1)==0))
        self.assertTrue(np.all(out[labels==1,2] <= 2))
        self.assertTrue(np.all(out[labels==3,0] > out[labels==3,1]))

    def test_smooth_source_guidance_is_not_nearest_source_copy(self):
        source = np.array([[200,200,205,205]]*4,np.uint8)
        out,base,_,m = c.reconstruct(source,self.palette,np.full((64,64,3),128,np.uint8),self.p)
        nearest=np.repeat(np.repeat(self.palette[source],16,0),16,1)
        self.assertGreater(np.any(base!=nearest,axis=2).sum(),0)
        self.assertGreater(len(np.unique(base.reshape(-1,3),axis=0)),2)

    def test_deterministic_pixels_and_geometry(self):
        src=np.array([[27,27,27,27],[27,63,202,27],[27,231,231,27],[27,27,27,27]],np.uint8)
        raw=np.random.default_rng(7).integers(0,256,(61,61,3),dtype=np.uint8)
        a=c.reconstruct(src,self.palette,raw,self.p);b=c.reconstruct(src,self.palette,raw,self.p)
        for x,y in zip(a[:3],b[:3]):np.testing.assert_array_equal(x,y)
        self.assertEqual(a[3],b[3])

    def test_scale4_is_two_scale2_and_non_nearest(self):
        src=np.array([[1,1,2],[1,2,2],[3,3,2]],np.uint8)
        np.testing.assert_array_equal(c.scale_nx(src,4),c.scale_nx(c.scale_nx(src,2),2))
        self.assertFalse(np.array_equal(c.scale_nx(src,2),np.repeat(np.repeat(src,2,0),2,1)))

    def test_decode_rejects_reserved_and_malformed_source(self):
        good=struct.pack('<5i',1,1,0,2,2)+bytes([27,63,202,231])
        self.assertEqual(c.decode_source(good).shape,(2,2))
        for bad in [good[:-1],good[:20]+bytes([27,63,240,231]),struct.pack('<5i',2,1,0,2,2)+good[20:]]:
            with self.assertRaises(ValueError):c.decode_source(bad)

    def test_rejects_unknown_family_and_unsafe_parameters(self):
        with self.assertRaises(ValueError):c.material_families(np.array([[100]],np.uint8))
        for name,value in [('output_side',True),('output_side',15),('source_sigma',float('nan')),('residual_sigma_coarse',0.1)]:
            p=copy.deepcopy(self.p);p[name]=value
            with self.assertRaises(ValueError):c.reconstruct(np.full((4,4),63,np.uint8),self.palette,np.zeros((64,64,3),np.uint8),p)

    def test_stable_reader_rejects_symlinks(self):
        with tempfile.TemporaryDirectory()as d:
            p=Path(d);(p/'a').write_bytes(b'fixed');(p/'link').symlink_to(p/'a')
            with self.assertRaises(OSError):c.read_regular(p/'link')

    def test_actual_cli_lineage_and_bad_crop_stops_before_mkdir(self):
        import hashlib
        with tempfile.TemporaryDirectory()as d:
            p=Path(d);src=p/'source.pic';src.write_bytes(struct.pack('<5i',1,1,0,4,4)+bytes([63]*16))
            pal=p/'palette';pal.write_bytes(bytes([0,0,0])*60+bytes([14,13,1,10,10,0,6,6,0,3,3,0])+bytes([0,0,0])*(256-64))
            raw=p/'parent.png';yy,xx=np.indices((64,64));Image.fromarray(np.repeat((80+(xx%2)*80)[...,None],3,2).astype(np.uint8)).save(raw)
            def binding(q):return dict(path=str(q),sha256=hashlib.sha256(q.read_bytes()).hexdigest())
            recipe=dict(method=c.METHOD,palette=binding(pal),parameters=self.p,frames=[dict(asset='20400',Source=binding(src),parent_raw=binding(raw),crop=[0,0,64,64])])
            rp=p/'recipe.json';rp.write_text(json.dumps(recipe));out=p/'result';c.main(['--recipe',str(rp),'--output',str(out)])
            report=json.loads((out/'DERIVED-LINEAGE-AND-ACTUAL-RECONSTRUCTION-METRICS.json').read_text());row=report['frames'][0]
            self.assertEqual(row['output']['sha256'],hashlib.sha256(Path(row['output']['path']).read_bytes()).hexdigest())
            self.assertEqual(row['parent_raw']['sha256'],binding(raw)['sha256'])
            self.assertIn('DERIVED',row['lineage'])
            with Image.open(row['output']['path']) as saved:
                self.assertEqual(saved.size,(64,64))
            self.assertEqual(report['execution']['status'],'success')
            self.assertEqual(report['execution']['source_sha256'],{'20400':binding(src)['sha256']})
            self.assertEqual(report['execution']['output_sha256'],{'20400':row['output']['sha256']})
            self.assertEqual(report['execution']['parent_raw_sha256'],[binding(raw)['sha256']])
            portable=copy.deepcopy(recipe)
            portable['palette']['path']=pal.name
            portable['frames'][0]['Source']['path']=src.name
            portable['frames'][0]['parent_raw']['path']=raw.name
            portable_path=p/'portable.json';portable_path.write_text(json.dumps(portable))
            moved=p/'relative-result';c.main(['--recipe',str(portable_path),'--output',str(moved)])
            self.assertEqual((moved/Path(row['output']['path']).name).read_bytes(),Path(row['output']['path']).read_bytes())
            recipe['frames'][0]['crop']=[1,0,64,64];rp.write_text(json.dumps(recipe));bad=p/'bad'
            with self.assertRaises(ValueError):c.main(['--recipe',str(rp),'--output',str(bad)])
            self.assertFalse(bad.exists())

if __name__ == '__main__':unittest.main()
