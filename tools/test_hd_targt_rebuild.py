"""Portable synthetic behavioural tests; no engine, image service or old corpus."""
from pathlib import Path
import hashlib, json, tempfile, unittest, struct
import numpy as np
from PIL import Image
import hd_targt_rebuild as t

class RebuildTests(unittest.TestCase):
    def test_main_component_excludes_disconnected_fringe(self):
        a=np.zeros((20,30,4),dtype='uint8');a[4:18,7:26,3]=255;a[0,0,3]=255
        self.assertEqual(t.main_painted_bounds(a),[7,4,26,18])

    def test_nonuniform_mapping_keeps_source_canvas_alpha_region(self):
        a=np.zeros((12,30,4),dtype='uint8');a[2:10,4:28,:3]=[90,70,50];a[2:10,4:28,3]=255
        s=np.full((32,32),256,dtype='uint16');s[4:29,3:28]=195
        image,b,sb=t.map_parent(a,s,4)
        self.assertEqual(b,[4,2,28,10]);self.assertEqual(sb,[3,4,28,29])
        self.assertEqual(image.shape,(128,128,3));self.assertTrue(np.all(image[16:116,12:112]==[90,70,50]))
        self.assertEqual(int(image[:16].sum()),0)

    def test_generated_correlated_texture_survives_quiet_soil(self):
        y,x=np.indices((128,128));v=80+20*np.sin(x*.35)+10*np.cos(y*.8)
        g=np.stack([v,v*.65,v*.5],2);src=np.full((32,32,3),[100,60,45],dtype='uint8')
        out=t.broad_soil(g,src,np.ones((32,32),bool),4)
        self.assertGreater(float(out[:,:,0].std()),1)
        self.assertLess(float(out[:,:,0].std()),float(g[:,:,0].std()))
        self.assertGreater(float(np.corrcoef((g-g.mean((0,1)))[:,:,0].ravel(),(out-out.mean((0,1)))[:,:,0].ravel())[0,1]),.8)

    def test_source_pixel_checker_not_copied_into_broad_material(self):
        y,x=np.indices((32,32));src=np.repeat((((x+y)%2)*140+40)[:,:,None],3,2).astype('uint8')
        g=np.full((128,128,3),90.,dtype=float);out=t.broad_soil(g,src,np.ones((32,32),bool),4)
        self.assertLess(float(out[:,:,0].std()),1)

    def test_core_sampling_rejects_distant_warm_brown_rim(self):
        a=np.zeros((128,128,3),float);a[16:120,12:16]=[110,55,12]
        a[68:80,60:68]=[100,35,3]
        mask=t.core_donor_mask(a,[15,17,17,20],4)
        self.assertEqual(t.box(mask),[60,68,68,80])

    def fixture(self,root):
        def ref(p):return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
        pal=np.zeros((256,3),dtype='uint8');pal[:32]=np.arange(31,-1,-1)[:,None]*2
        pal[195]=[26,15,11];pal[81]=[59,44,7];pal[95]=[16,4,0]
        pp=root/'palette';pp.write_bytes(pal.tobytes())
        sources=[];frames=[]
        for i in range(4):
            s=np.full((32,32),256,dtype='uint16')
            if i==0:s[:]=195
            else:
                s[4:29,3:28]=195
                if i>=2:s[5:28,4:27]=31;s[12:25,10:22]=14;s[17:20,15:17]=95
                if i==2:s[5:16,4:27]=195;s[16,4:27:2]=81;s[17:19,4:7]=10
            p=root/('TEST_PIC'+('.'+str(i) if i else ''))
            payload=struct.pack('<iiiii',0,0,0,32,32)
            for y in range(32):
                xs=np.flatnonzero(s[y]<256)
                if len(xs):
                    l,r=int(xs[0]),int(xs[-1]+1);payload+=struct.pack('<iiii',l,y,0,r-l)+s[y,l:r].astype('uint8').tobytes()
            payload+=struct.pack('<iiii',0,0,-1,0);p.write_bytes(payload)
            sources.append(s);frames.append(dict(asset=str(i),source=ref(p),origin=[0,0]))
        raw=np.zeros((80,4*80,4),dtype='uint8')
        for i in range(4):
            x=i*80;a=raw[:,x:x+80];y0,y1,x0,x1=(5,75,4,76) if i==0 else (10,70,10,70)
            a[y0:y1,x0:x1,:3]=[100,62,45];a[y0:y1,x0:x1,3]=255
            if i>=2:
                a[12:68,12:68,:3]=[8,8,8];a[32:56,28:56,:3]=[110,110,110]
                a[37:49,35:47,:3]=[8,8,8];a[39:47,38:44,:3]=[90,30,3]
            if i==2:
                a[12:40,12:68,:3]=[100,62,45];a[40:43,12:68,:3]=[235,170,25];a[43:49,12:22,:3]=[100,100,100]
        rp=root/'raw.png';Image.fromarray(raw).save(rp)
        recipe=dict(format_version=1,method=t.METHOD,output_scale=4,palette=ref(pp),raw_png=ref(rp),layout=dict(columns=4,rows=1),
                    frames=frames,soil_donor_frame=0,closed_donor_frame=1,module_donor_frame=3,warning_donor_frame=2)
        return recipe,sources

    def test_full_assembly_exact_alpha_warning_position_static_and_normalized_execution(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);recipe,sources=self.fixture(p);outputs,result=t.render(recipe,p)
            for o,s in zip(outputs,sources):self.assertTrue(np.array_equal(o[:,:,3],np.repeat(np.repeat(s<256,4,0),4,1)*255))
            self.assertEqual(result['frames'][2]['warning_Source_y'],16)
            strip=outputs[2][16*4:17*4,4*4:27*4,:3]
            self.assertGreater(float(strip[:,:,0].mean()),float(strip[:,:,2].mean())*2)
            static=np.all(np.stack(sources)[1:]==sources[1],axis=0)&(sources[1]<256);big=np.repeat(np.repeat(static,4,0),4,1)
            self.assertTrue(np.array_equal(outputs[1][big],outputs[3][big]))
            rp=p/'recipe.json';rp.write_text(json.dumps(recipe));result=t.run(rp,p/'new')
            self.assertEqual(set(result['execution']),{'status','method','recipe_sha256','tool_sha256','source_sha256','parent_raw_sha256','output_sha256'})
            self.assertEqual(result['execution']['parent_raw_sha256'],[recipe['raw_png']['sha256']])
            self.assertEqual(len(result['execution']['output_sha256']),4)
            bindings=result['implementation_bindings']
            decoder=Path(bindings['decoder']['path'])
            self.assertEqual(bindings['decoder']['sha256'],hashlib.sha256(decoder.read_bytes()).hexdigest())
            self.assertEqual(set(bindings['runtime']),{'python','numpy','pillow','executable'})
            self.assertTrue(all(type(v) is str and v for v in bindings['runtime'].values()))
            with self.assertRaisesRegex(ValueError,'no overwrite'):t.run(rp,p/'new')

    def test_bad_hash_fails_before_creating_output(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);recipe,_=self.fixture(p);recipe['frames'][2]['source']['sha256']='0'*64
            rp=p/'recipe.json';rp.write_text(json.dumps(recipe))
            with self.assertRaisesRegex(ValueError,'SHA mismatch'):t.run(rp,p/'absent')
            self.assertFalse((p/'absent').exists())

    def test_duplicate_partition_origin_and_bool_scale_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            recipe,_=self.fixture(Path(td))
            for mutation in ('duplicate','partition','origin','boolscale'):
                r=json.loads(json.dumps(recipe))
                if mutation=='duplicate':r['frames'][1]['asset']=r['frames'][0]['asset']
                if mutation=='partition':r['frames'].pop()
                if mutation=='origin':r['frames'][0]['origin']=[1,0]
                if mutation=='boolscale':r['output_scale']=True
                with self.assertRaises(ValueError):t.validate_recipe(r)

    def test_path_escape_and_absolute_asset_fail_before_output_or_sentinel_write(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);recipe,_=self.fixture(p)
            sentinels=[p/'sentinel-derived.png',p/'absolute-sentinel-derived.png']
            for sentinel in sentinels:sentinel.write_bytes(b'KEEP-EXISTING-ART-EXACT')
            for i,bad in enumerate(['../sentinel',str(p/'absolute-sentinel'),'0/../sentinel','../0','',None,False,'0x10152','ABC','0001','100000000']):
                r=json.loads(json.dumps(recipe));r['frames'][0]['asset']=bad
                rp=p/('bad'+str(i)+'.json');rp.write_text(json.dumps(r));out=p/('absent'+str(i))
                with self.assertRaisesRegex(ValueError,'canonical lowercase'):t.run(rp,out)
                self.assertFalse(out.exists())
                for sentinel in sentinels:self.assertEqual(sentinel.read_bytes(),b'KEEP-EXISTING-ART-EXACT')

    def test_boolean_version_and_origin_are_not_integer_identity(self):
        with tempfile.TemporaryDirectory() as td:
            recipe,_=self.fixture(Path(td))
            for mutate in ('version','origin'):
                r=json.loads(json.dumps(recipe))
                if mutate=='version':r['format_version']=True
                else:r['frames'][0]['origin']=[False,0]
                with self.assertRaises(ValueError):t.validate_recipe(r)

    def test_complete_numeric_asset_and_Source_picture_order(self):
        with tempfile.TemporaryDirectory() as td:
            recipe,_=self.fixture(Path(td))
            for mutate in ('gap','reversed','source_swapped'):
                r=json.loads(json.dumps(recipe))
                if mutate=='gap':r['frames'][-1]['asset']='5'
                if mutate=='reversed':r['frames'][0]['asset'],r['frames'][1]['asset']=r['frames'][1]['asset'],r['frames'][0]['asset']
                if mutate=='source_swapped':r['frames'][1]['source'],r['frames'][2]['source']=r['frames'][2]['source'],r['frames'][1]['source']
                with self.assertRaisesRegex(ValueError,'order'):t.validate_recipe(r)

    def test_repeated_synthetic_render_is_byte_deterministic(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);recipe,_=self.fixture(p)
            a,ma=t.render(recipe,p);b,mb=t.render(recipe,p)
            self.assertEqual(ma,mb)
            for x,y in zip(a,b):self.assertEqual(x.tobytes(),y.tobytes())

if __name__=='__main__':unittest.main()
