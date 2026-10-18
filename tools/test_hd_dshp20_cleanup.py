import hashlib
import importlib.util
import json
import pathlib
import struct
import sys
import tempfile
import unittest
import numpy as np
from PIL import Image, __version__ as PILLOW_VERSION

_spec=importlib.util.spec_from_file_location('dshp20_cleanup',pathlib.Path(__file__).with_name('hd_dshp20_cleanup.py'))
c=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(c)

class RGBGeometryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name)
        self.palette=self.root/'palette';self.palette.write_bytes(bytes([i%64 for i in range(768)]))
    def tearDown(self):self.tmp.cleanup()
    def binding(self,p):return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
    def source(self,values,name):
        h,w=values.shape;data=bytearray(struct.pack('<5i',0,1,31,w,h))
        for y,row in enumerate(values):
            x=0
            while x<w:
                if row[x]==256:x+=1;continue
                stop=x
                while stop<w and row[stop]<256:stop+=1
                data.extend(struct.pack('<4i',x,y,y*w+x,stop-x));data.extend(bytes(row[x:stop].tolist()));x=stop
        data.extend(struct.pack('<4i',0,0,-1,0));p=self.root/name;p.write_bytes(data);return p
    def frame(self,values,rgb,asset,alpha=None):
        p=self.root/(asset+'.png');h,w=values.shape
        arr=np.zeros((h*4,w*4,4),np.uint8);arr[:,:,:3]=rgb;arr[:,:,3]=255 if alpha is None else alpha
        Image.fromarray(arr).save(p)
        return {'asset':asset,'source':self.binding(self.source(values,asset+'.pic')),'raw_png':self.binding(p),'viewport':[0,0,w*4,h*4],'sampling_offset_native':[0,0],'origin':[0,0]}
    def recipe(self,frames):return {'format_version':1,'palette':self.binding(self.palette),'output_scale':4,'max_fill_distance_pixels':12,'shared_backing_anchor':0,'frames':frames}
    def pattern(self,h,w,offset=0):
        y,x=np.indices((h*4,w*4));return np.stack([(x*7+80+offset)%230,(y*11+90+offset)%230,((x//4+y//4)*23+50+offset)%230],axis=-1).astype(np.uint8)
    def test_broad_generated_panels_and_RGB_are_preserved_not_highpass_noise(self):
        s=np.full((4,6),10);rgb=self.pattern(4,6)
        out,report=c.render_family(self.recipe([self.frame(s,rgb,'a')]),self.root)
        self.assertTrue(np.array_equal(out[0][:,:,:3],rgb));self.assertEqual(report['frames'][0]['filled_generated_RGB_samples'],0)
    def test_source_scale4_mask_removes_overflow_and_holes_use_generated_RGB(self):
        s=np.full((5,5),10);s[0,0]=256;s[4,4]=256;rgb=self.pattern(5,5);alpha=np.full((20,20),255,np.uint8);alpha[8,8]=0
        out,report=c.render_family(self.recipe([self.frame(s,rgb,'a',alpha)]),self.root);mask=c.scale2(c.scale2(s))<256
        self.assertTrue(np.array_equal(out[0][:,:,3]>0,mask));self.assertTrue(np.array_equal(out[0][2,10,:3],rgb[2,10]));self.assertEqual(report['frames'][0]['filled_generated_RGB_samples'],1);self.assertGreater(report['frames'][0]['removed_generated_outside_SourceScale4'],0)
        self.assertTrue(any(np.array_equal(out[0][8,8,:3],v)for v in rgb.reshape(-1,3)))
    def test_stationary_RGB_shared_but_changed_Source_phase_is_not_frozen(self):
        a=np.full((6,6),10);b=a.copy();b[3,3]=11
        out,report=c.render_family(self.recipe([self.frame(a,self.pattern(6,6),'a'),self.frame(b,self.pattern(6,6,33),'b')]),self.root)
        self.assertTrue(np.array_equal(out[0][0,0],out[1][0,0]));self.assertFalse(np.array_equal(out[0][13,13],out[1][13,13]));self.assertGreater(report['frames'][1]['stationary_full_RGB_replacements'],0)
        # Unchanged labels inside a coherent moving part keep its whole RGB.
        self.assertFalse(np.array_equal(out[0][9,9],out[1][9,9]))
    def test_functional_Source_palette_RGB_replaces_wrong_parent_marker(self):
        s=np.full((3,4),10);s[1,1]=252;s[1,2]=253;out,_=c.render_family(self.recipe([self.frame(s,self.pattern(3,4),'a')]),self.root)
        p=np.frombuffer(self.palette.read_bytes(),np.uint8).reshape(256,3);p=(p<<2)|(p>>4)
        self.assertTrue(np.all(out[0][4:8,4:8,:3]==p[252]));self.assertTrue(np.all(out[0][4:8,8:12,:3]==p[253]))
    def test_scale2_has_actual_kernel_corner_not_nearest_replication(self):
        s=np.array([[1,2],[2,2]],np.uint16)
        expected=np.array([[1,1,2,2],[1,2,2,2],[2,2,2,2],[2,2,2,2]],np.uint16)
        self.assertTrue(np.array_equal(c.scale2(s),expected))
    def test_normalized_execution_hashes_and_input_immutability(self):
        s=np.full((3,4),10);recipe=self.recipe([self.frame(s,self.pattern(3,4),'a')]);rp=self.root/'recipe.json';rp.write_text(json.dumps(recipe));before={p:p.read_bytes()for p in self.root.iterdir()if p.is_file()};report=c.run_recipe(rp,self.root/'out');e=report['execution']
        self.assertEqual(set(e),{'status','method','recipe_sha256','tool_sha256','source_sha256','parent_raw_sha256','output_sha256'});self.assertEqual(e['status'],'success');self.assertEqual(e['output_sha256']['a'],hashlib.sha256((self.root/'out/a-derived.png').read_bytes()).hexdigest());self.assertEqual(e['parent_raw_sha256'],sorted(set(e['parent_raw_sha256'])))
        self.assertEqual(report['decoder_module'],{'path':str(pathlib.Path(c.hd_frame_policy.__file__).resolve()),'sha256':hashlib.sha256(pathlib.Path(c.hd_frame_policy.__file__).read_bytes()).hexdigest()})
        self.assertEqual(report['python_version'],sys.version);self.assertEqual(report['numpy_version'],np.__version__);self.assertEqual(report['pillow_version'],PILLOW_VERSION)
        for p,data in before.items():self.assertEqual(p.read_bytes(),data)
        with self.assertRaisesRegex(ValueError,'already exists'):c.run_recipe(rp,self.root/'out')
    def test_missing_generated_donor_refuses_SourceNN_or_noise_fallback(self):
        s=np.full((3,4),10);f=self.frame(s,self.pattern(3,4),'a',np.zeros((12,16),np.uint8))
        with self.assertRaisesRegex(ValueError,'no generated RGB donor'):c.render_family(self.recipe([f]),self.root)
    def test_bad_hash_and_bool_scale_rejected_before_output(self):
        f=self.frame(np.full((3,4),10),self.pattern(3,4),'a');r=self.recipe([f]);r['output_scale']=True
        with self.assertRaises(ValueError):c.render_family(r,self.root)
        r['output_scale']=4;r['frames'][0]['source']['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'hash mismatch'):c.render_family(r,self.root)

if __name__=='__main__':unittest.main(verbosity=2)
