import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
import numpy as np
from PIL import Image

spec=importlib.util.spec_from_file_location('other_cleanup',Path(__file__).with_name('hd_other_functional_cleanup.py'))
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)

class FunctionalOriginalTests(unittest.TestCase):
    def palette(self):
        p=np.arange(768,dtype=np.uint16).reshape(256,3)%64
        return ((p<<2)|(p>>4)).astype(np.uint8)
    def pattern(self,h,w):
        y,x=np.indices((h*4,w*4));a=np.zeros((h*4,w*4,4),np.uint8)
        a[:,:,:3]=np.stack([(x//4)*33+25,(y//4)*27+40,(x*7+y*3)%230],axis=-1);a[:,:,3]=255
        return a
    def test_only_declared_ordinary31_and_gray15_footprints_replace_full_RGB(self):
        s=np.full((4,5),15,np.uint16);s[:,:2]=31;a=self.pattern(4,5);p=self.palette()
        out,report=c.retain_functional_original(a,s,p,[[1,1],[3,2]])
        mask=np.zeros((16,20),bool);mask[4:8,4:8]=True;mask[8:12,12:16]=True
        self.assertTrue(np.array_equal(out[~mask],a[~mask]));self.assertTrue(np.array_equal(a,self.pattern(4,5)))
        self.assertTrue(np.all(out[4:8,4:8,:3]==p[31]));self.assertTrue(np.all(out[8:12,12:16,:3]==p[15]))
        self.assertEqual(report['actual_Original_Scale4_RGBA_samples'],32)
    def test_kernel_footprint_retains_real_Original_transparency_not_NN_point_color(self):
        s=np.array([[256,256,1],[256,31,1],[1,1,1]],np.uint16);a=self.pattern(3,3)
        out,r=c.retain_functional_original(a,s,self.palette(),[[1,1]])
        s4=c.base.scale2(c.base.scale2(s));expected=np.zeros((4,4,4),np.uint8);q=s4[4:8,4:8];painted=q<256
        expected[:,:,:3][painted]=self.palette()[q[painted]];expected[:,:,3][painted]=255
        self.assertTrue(np.array_equal(out[4:8,4:8],expected));self.assertGreater(r['actual_Original_transparent_samples'],0)
        self.assertLess(int((out[4:8,4:8,3]>0).sum()),16)
    def test_zero_typed_out_of_bounds_transparent_duplicate_or_unsorted_selectors_rejected(self):
        s=np.full((4,5),10,np.uint16);s[0,0]=256;a=self.pattern(4,5)
        invalid=[[],[[True,1]],[[1.0,1]],[[5,1]],[[-1,1]],[[1,4]],[[0,0]],[[1,1],[1,1]],[[3,2],[1,1]]]
        for cells in invalid:
            with self.subTest(cells=cells),self.assertRaises(ValueError):c.retain_functional_original(a,s,self.palette(),cells)
        self.assertTrue(np.array_equal(a,self.pattern(4,5)))
    def test_broad_gradient_and_panel_edges_are_exact_outside_small_retention(self):
        s=np.full((10,12),10,np.uint16);s[9,2]=31;a=self.pattern(10,12)
        out,_=c.retain_functional_original(a,s,self.palette(),[[2,9]])
        self.assertTrue(np.array_equal(out[:36],a[:36]));self.assertTrue(np.array_equal(out[36:,:8],a[36:,:8]))
        self.assertGreater(len(np.unique(out[:36,:,:3].reshape(-1,3),axis=0)),100)
    def test_reviewed_base_and_decoder_dependencies_are_bound(self):
        d=c.dependency_pins();self.assertEqual(d['RGB_geometry_tool']['sha256'],c.BASE_SHA);self.assertEqual(d['Source_decoder']['sha256'],c.DECODER_SHA)
    def test_once_output_normalized_lineage_input_immutability_and_deterministic_PNG(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);source=np.full((3,4),10,np.uint16);source[1,1]=31
            b=bytearray(struct.pack('<5i',0,1,31,4,3))
            for y in range(3):b.extend(struct.pack('<4i',0,y,y*4,4));b.extend(bytes(source[y].tolist()))
            b.extend(struct.pack('<4i',0,0,-1,0));(root/'source.pic').write_bytes(b)
            (root/'palette').write_bytes(bytes((np.arange(768)%64).astype(np.uint8)))
            Image.fromarray(self.pattern(3,4)).save(root/'parent.png')
            def bind(n):return dict(path=n,sha256=hashlib.sha256((root/n).read_bytes()).hexdigest())
            geometry=dict(format_version=1,palette=bind('palette'),output_scale=4,max_fill_distance_pixels=12,shared_backing_anchor=0,
                frames=[dict(asset='102f7',source=bind('source.pic'),raw_png=bind('parent.png'),viewport=[0,0,16,12],sampling_offset_native=[0,0],origin=[0,0])])
            recipe=dict(format_version=1,geometry_recipe=geometry,functional_original_cells=[[1,1]])
            rp=root/'recipe.json';rp.write_text(json.dumps(recipe));before={p:p.read_bytes()for p in root.iterdir()}
            report=c.run_recipe(rp,root/'out1');c.run_recipe(rp,root/'out2')
            self.assertEqual((root/'out1/102f7-derived.png').read_bytes(),(root/'out2/102f7-derived.png').read_bytes())
            self.assertEqual(set(report['execution']),{'status','method','recipe_sha256','tool_sha256','source_sha256','parent_raw_sha256','output_sha256'})
            self.assertEqual(report['functional_Original']['Source_indices'],[31])
            for p,data in before.items():self.assertEqual(p.read_bytes(),data)
            with self.assertRaisesRegex(ValueError,'fresh absent'):c.run_recipe(rp,root/'out1')

if __name__=='__main__':unittest.main(verbosity=2)
