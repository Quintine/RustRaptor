"""Synthetic only: no actual SHIP15 image, Source or recipe is rendered."""
from pathlib import Path
import copy
import importlib.util
import json
import struct
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('private_ship15', HERE/'ship15_component_cleanup.py')
tool=importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)
DECODER=HERE.parent.parent/'tools/hd_frame_policy.py'
TONE=[(38,7,7,6),(42,7,3,1),(43,7,4,3),(46,13,31,30),(47,13,30,28),(48,13,29,27),
      (49,13,28,26),(50,13,29,27),(51,13,27,24),(42,14,27,25),(43,14,29,27),(44,14,27,25)]


def binding(p):
    return dict(path=str(p),sha256=tool.sha(p.read_bytes()))


def encode_source(arr):
    out=bytearray(struct.pack('<5i',0,2,18,72,24))
    for y in range(24):
        x=0
        while x<72:
            if arr[y,x]==256:
                x+=1
                continue
            end=x+1
            while end<72 and arr[y,end]<256:end+=1
            out.extend(struct.pack('<4i',x,y,y*72+x,end-x))
            out.extend(bytes(arr[y,x:end].tolist()))
            x=end
    out.extend(struct.pack('<4i',0,0,-1,0))
    return bytes(out)


class SyntheticFamily(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.palette=np.zeros((256,3),np.uint8)
        for i in range(32):self.palette[i]=63-2*i
        self.palette[144:158]=[5,25,30]
        self.palette[255]=[54,54,54]
        pp=self.root/'PALETTE';pp.write_bytes(self.palette.tobytes())
        base=np.full((24,72),256,np.uint16)
        base[2:20]=144
        base[7:15,36:53]=10
        base[4:7,39:42]=10
        base[15:18,39:42]=10
        base[7:15,21:29]=10
        base[7:15,55:63]=10
        base[10:12,37]=255
        tone_set={(x,y)for x,y,_,_ in TONE}
        black=[]
        for y,x in np.argwhere(base<32):
            if (int(x),int(y))not in tone_set:
                black.append((int(x),int(y)))
            if len(black)==15:break
        for x,y in black:base[y,x]=31
        self.sources=[]
        self.raw=np.zeros((144,144,4),np.uint8)
        frames=[]
        for i in range(3):
            s=base.copy()
            for x,y,v0,v1 in TONE:s[y,x]=v0 if i==0 else v1
            self.sources.append(s)
            p=self.root/f'SOURCE{i}';p.write_bytes(encode_source(s))
            alpha=np.repeat(np.repeat(s<256,2,axis=0),2,axis=1)
            gray=np.repeat(np.repeat(s<32,2,axis=0),2,axis=1)
            yy,xx=np.indices(alpha.shape)
            phase=np.zeros((48,144,4),np.uint8)
            phase[:,:,:3][alpha]=np.stack([10+xx%5,90+yy%10,110+xx%10],axis=2)[alpha]
            neutral=(60+xx%70+yy%11+i*7).astype(np.uint8)
            for c in range(3):phase[:,:,c][gray]=neutral[gray]
            phase[:,:,3][alpha]=255
            self.raw[i*48:(i+1)*48]=phase
            comps={}
            for name,(sx,sy)in tool.AXES.items():
                comps[name]=dict(source_x=sx,raw_x=[v*2 for v in sx],source_y=sy,raw_y=[v*2 for v in sy],
                                 donor_bounds=[sx[0]*2,sy[0]*2,sx[-1]*2,sy[-1]*2])
            frames.append(dict(asset=f'{0x1030b+i:05x}',frame=i,source=binding(p),logical_canvas=[72,24],origin=[0,0],
                               raw_crop=[0,i*48,144,48],components=comps,functional_original_cells=[]))
        phases=np.any(np.stack(self.sources)!=self.sources[0],axis=0)&(self.sources[0]<32)
        for f,s in zip(frames,self.sources):
            f['functional_original_cells']=[[int(x),int(y)]for y,x in np.argwhere((s==31)|phases|(s==255))]
            self.assertEqual(len(f['functional_original_cells']),29)
        self.parent=self.root/'parent.png'
        Image.fromarray(self.raw).save(self.parent)
        self.recipe=dict(format_version=1,label='SYNTHETIC ONLY',decoder_module=binding(DECODER),palette=binding(pp),
                         parent_raw=binding(self.parent),output_scale=8,caps=copy.deepcopy(tool.CAPS),frames=frames)

    def tearDown(self):
        self.temp.cleanup()

    def save_parent(self):
        Image.fromarray(self.raw).save(self.parent)
        self.recipe['parent_raw']=binding(self.parent)

    def save_source(self,i):
        p=self.root/f'SOURCE{i}';p.write_bytes(encode_source(self.sources[i]));self.recipe['frames'][i]['source']=binding(p)

    def assert_fails_without_output(self,recipe,pattern):
        rp=self.root/'bad-recipe.json';rp.write_text(json.dumps(recipe))
        out=self.root/'MUST-NOT-EXIST'
        with self.assertRaisesRegex((ValueError,AssertionError),pattern):tool.run_recipe(rp,out)
        self.assertFalse(out.exists())

    def test_identity_preserves_genuine_RGB_alpha_and29_Original_only(self):
        arrays,report=tool.render_family(self.recipe,self.root)
        pal=((self.palette.astype(np.uint16)<<2)|(self.palette.astype(np.uint16)>>4)).astype(np.uint8)
        for i,(s,out)in enumerate(zip(self.sources,arrays)):
            alpha=np.repeat(np.repeat(s<256,8,axis=0),8,axis=1)
            self.assertTrue(np.array_equal(out[:,:,3]==255,alpha))
            self.assertFalse(out[~alpha].any())
            yy,xx=np.indices(alpha.shape);expected=self.raw[i*48+(yy//4),xx//4,:3]
            f=np.zeros((24,72),bool)
            for x,y in self.recipe['frames'][i]['functional_original_cells']:f[y,x]=True
            fm=np.repeat(np.repeat(f,8,axis=0),8,axis=1)
            srgb=np.repeat(np.repeat(pal[np.minimum(s,255)],8,axis=0),8,axis=1)
            self.assertTrue(np.array_equal(out[:,:,:3][alpha&~fm],expected[alpha&~fm]))
            self.assertTrue(np.array_equal(out[:,:,:3][fm],srgb[fm]))
            self.assertEqual(sum(m['nearest_parent_extension_samples']for m in report['frames'][i]['component_donor_metrics']),0)
        self.assertFalse(np.array_equal(arrays[0],arrays[1]))

    def test_nonuniform_left_pod_transform_keeps_own_genuine_donor(self):
        for i in range(3):
            ph=self.raw[i*48:(i+1)*48]
            original=ph[14:30,42:58].copy()
            ph[14:30,42:60,:3]=[10,95,115]
            ph[14:30,42:60,3]=255
            ph[14:30,44:60]=original
            m=self.recipe['frames'][i]['components']['left_pod']
            m['raw_x']=[44,60];m['donor_bounds']=[44,14,60,30]
        self.save_parent()
        arrays,_=tool.render_family(self.recipe,self.root)
        # An ordinary non-functional bottom-right pod point reads translated raw.
        x,y=28*8+2,14*8+2
        self.assertNotIn([28,14],self.recipe['frames'][0]['functional_original_cells'])
        self.assertEqual(arrays[0][y,x,:3].tolist(),self.raw[28,58,:3].tolist())
        self.assertEqual(int(arrays[0][y,x,3]),255)

    def test_malformed_knots_and_relaxed_caps_fail_before_output(self):
        mutations=[('raw_x',[72,78,78,106]),('raw_y',[8,float('nan'),30,36]),('source_x',[36,39,42,54]),
                   ('raw_x',[True,78,84,106]),('donor_bounds',[73,8,106,36])]
        for key,value in mutations:
            with self.subTest(key=key,value=value):
                r=copy.deepcopy(self.recipe);r['frames'][0]['components']['main_machinery_mast_hull'][key]=value
                self.assert_fails_without_output(r,'knots|bounds')
        r=copy.deepcopy(self.recipe);r['caps']['metal_max_logical_distance']=2
        self.assert_fails_without_output(r,'caps')
        r=copy.deepcopy(self.recipe);r['caps']['metal_max_logical_distance']=True
        self.assert_fails_without_output(r,'caps')

    def test_missing_alpha_no_donor_and_wrong_material_fail(self):
        original=self.raw.copy()
        self.raw[14:30,42:58,3]=0;self.save_parent()
        self.assert_fails_without_output(self.recipe,'no genuine')
        self.raw=original.copy();self.raw[14:30,42:58,:3]=[0,130,150];self.save_parent()
        self.assert_fails_without_output(self.recipe,'no genuine')
        self.raw=original.copy();self.raw[:,:,3]=255;self.save_parent()
        self.assert_fails_without_output(self.recipe,'transparent alpha')

    def test_donor_fraction_and_distance_are_separate_hard_stops(self):
        original=self.raw.copy()
        self.raw[14:30,42:46,3]=0;self.save_parent()
        self.assert_fails_without_output(self.recipe,'missing fraction')
        self.raw=original.copy();self.raw[18:24,86:92,3]=0;self.save_parent()
        self.assert_fails_without_output(self.recipe,'distance exceeds')

    def test_Original_selectors_and_Source_support_are_fail_closed(self):
        for value in [self.recipe['frames'][0]['functional_original_cells'][:-1],
                      self.recipe['frames'][0]['functional_original_cells']+[self.recipe['frames'][0]['functional_original_cells'][0]]]:
            r=copy.deepcopy(self.recipe);r['frames'][0]['functional_original_cells']=value
            self.assert_fails_without_output(r,'Original cells')
        original=self.sources[0].copy()
        self.sources[0][1,20]=144;self.save_source(0)
        self.assert_fails_without_output(self.recipe,'support outside')
        self.sources[0]=original.copy();self.sources[0][10,37]=10;self.save_source(0)
        self.assert_fails_without_output(self.recipe,'indicator changed')
        self.sources[0]=original.copy();self.sources[0][5,5]=10;self.save_source(0)
        self.assert_fails_without_output(self.recipe,'footprint changed|support outside')
        self.sources[0]=original.copy();self.sources[0][5,5]=100;self.save_source(0)
        self.assert_fails_without_output(self.recipe,'class outside')

    def test_source_tone12_family_order_and_full_crop_not_optional(self):
        r=copy.deepcopy(self.recipe);r['frames'][0]['frame']=False
        self.assert_fails_without_output(r,'order')
        r=copy.deepcopy(self.recipe);r['frames'][1]['raw_crop']=[0,49,144,47]
        self.assert_fails_without_output(r,'full strips')
        for i in (1,2):
            self.sources[i]=self.sources[0].copy();self.save_source(i)
        self.assert_fails_without_output(self.recipe,'phase12')

    def test_hash_check_precedes_any_output_and_preserves_parent(self):
        before={p:tool.sha(p.read_bytes())for p in self.root.iterdir()if p.is_file()}
        r=copy.deepcopy(self.recipe);r['parent_raw']['sha256']='0'*64
        self.assert_fails_without_output(r,'hash mismatch')
        for p,sha in before.items():self.assertEqual(tool.sha(p.read_bytes()),sha)

    def test_nearest_ties_are_raster_seeded_and_never_cascade(self):
        trust=np.zeros((5,5),bool);trust[0,0]=True;trust[4,4]=True
        distance,oy,ox=tool.nearest_owners(trust)
        self.assertTrue(np.all(trust[oy,ox]))
        self.assertEqual((int(oy[2,2]),int(ox[2,2])),(0,0))
        self.assertEqual(int(distance[2,2]),4)
        for y in range(5):
            for x in range(5):self.assertEqual(int(distance[y,x]),min(x+y,8-x-y))

    def test_verified_decoder_bytes_execute_after_temporary_path_replacement(self):
        # Only a temporary decoder copy is replaced; no shared input is changed.
        decoder_copy=self.root/'copied_decoder.py'
        verified_bytes=DECODER.read_bytes()
        decoder_copy.write_bytes(verified_bytes)
        self.recipe['decoder_module']=binding(decoder_copy)
        expected,_=tool.render_family(self.recipe,self.root)
        checked_original=tool.checked
        replaced=[]
        malicious=b"raise RuntimeError('UNVERIFIED_TEMP_DECODER_MUST_NOT_EXECUTE')\n"

        def verify_then_replace(binding_value,base):
            path,data=checked_original(binding_value,base)
            if path==decoder_copy.resolve():
                self.assertEqual(data,verified_bytes)
                self.assertEqual(tool.sha(data),tool.DECODER_SHA)
                path.write_bytes(malicious)
                replaced.append(path)
            return path,data

        with patch.object(tool,'checked',side_effect=verify_then_replace):
            actual,report=tool.render_family(self.recipe,self.root)
        self.assertEqual(replaced,[decoder_copy.resolve()])
        self.assertEqual(decoder_copy.read_bytes(),malicious)
        self.assertEqual(report['decoder_module']['sha256'],tool.DECODER_SHA)
        for before,after in zip(expected,actual):
            self.assertTrue(np.array_equal(before,after))
        self.assertFalse(any(p.name.endswith('-derived.png')for p in self.root.iterdir()))

    def test_deterministic_recipe_receipts_and_new_output_only(self):
        rp=self.root/'recipe.json';rp.write_text(json.dumps(self.recipe,sort_keys=True))
        before={p:tool.sha(p.read_bytes())for p in self.root.iterdir()if p.is_file()}
        first=tool.run_recipe(rp,self.root/'first')
        second=tool.run_recipe(rp,self.root/'second')
        self.assertEqual(first,second)
        self.assertEqual(set(first['execution']),{'status','method','recipe_sha256','tool_sha256','source_sha256','parent_raw_sha256','output_sha256'})
        self.assertEqual(first['decoder_module']['sha256'],tool.DECODER_SHA)
        self.assertIn('numpy_version',first)
        for name in ['1030b-derived.png','1030c-derived.png','1030d-derived.png','derived-provenance.json']:
            self.assertEqual((self.root/'first'/name).read_bytes(),(self.root/'second'/name).read_bytes())
        with self.assertRaisesRegex(ValueError,'output exists'):tool.run_recipe(rp,self.root/'first')
        for p,sha in before.items():self.assertEqual(tool.sha(p.read_bytes()),sha)


if __name__=='__main__':unittest.main()
