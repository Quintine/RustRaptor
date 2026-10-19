"""Synthetic inputs only: no game masters or real cleanup execution."""
import copy,io,json,os,struct,tempfile,unittest,subprocess,sys
from unittest import mock
from types import SimpleNamespace
from pathlib import Path
import numpy as np
from PIL import Image
import hd_grating_gray_cleanup as m

class GrayCastTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        pal=np.zeros((256,3),np.uint8);pal[11]=[18,18,18];pal[30]=[4,4,4]
        (self.root/'palette.bin').write_bytes(pal.tobytes())
        y,x=np.indices((128,256));rgb=np.stack([50+x%5+y%7,35+x%5+y%7,28+x%5+y%7],axis=2).astype('uint8')
        im=Image.fromarray(rgb);im.save(self.root/'parent.png')
        self.source=np.full((32,32),199,np.uint8);self.source[2:31,2:31]=11
        self.recipe=dict(format_version=1,method=m.METHOD,palette=self.bind('palette.bin'),parent_raw=self.bind('parent.png'),frames=[])
        for asset in ['203c6','203c7']:
            name=asset+'.bin';(self.root/name).write_bytes(struct.pack('<5i',1,1,0,32,32)+self.source.tobytes())
            self.recipe['frames'].append(dict(asset=asset,Source=self.bind(name),selected_cells_sha256=m.selected_digest(m.semantic_mask(asset,self.source))))
    def tearDown(self):self.temp.cleanup()
    def bind(self,n):return dict(path=n,sha256=m.sha((self.root/n).read_bytes()))
    def prepared(self):return m.prepare_inputs(self.recipe,self.root)
    def test_cast_neutral_preserves_generated_luminance(self):
        result=m.derive(*self.prepared());self.assertEqual(len(result),2)
        for a,out,metrics in result:
            self.assertEqual(out.shape,(128,128,4));self.assertTrue(np.all(out[:,:,3]==255))
            self.assertTrue(metrics['outside_resized_parent_exact']);self.assertEqual(metrics['exact_Original_pixel_copies'],0)
            self.assertLessEqual(metrics['max_luma_structure_rounding_error'],.5000001)
            self.assertGreater(metrics['generated_luma_variance'],1);self.assertGreater(metrics['output_luma_variance'],1)
            self.assertLess(abs(metrics['output_luma_variance']-metrics['generated_luma_variance']),2)
    def test_repeatability(self):
        a=m.derive(*self.prepared());b=m.derive(*self.prepared())
        self.assertTrue(all(np.array_equal(x[1],y[1])and x[2]==y[2]for x,y in zip(a,b)))
    def test_all_semantic_cells_not_error_picker(self):
        for asset in m.REGIONS:
            mask=m.semantic_mask(asset,self.source);x0,y0,x1,y1=m.REGIONS[asset]
            self.assertEqual(int(mask.sum()),int(np.count_nonzero(self.source[y0:y1,x0:x1]==11)))
    def test_missing_or_unknown_fields(self):
        for key in ['method','palette','frames']:
            r=copy.deepcopy(self.recipe);del r[key]
            with self.assertRaises(ValueError):m.validate_recipe(r)
        r=copy.deepcopy(self.recipe);r['gain']=1.2
        with self.assertRaises(ValueError):m.validate_recipe(r)
    def test_bool_version_rejected(self):
        r=copy.deepcopy(self.recipe);r['format_version']=True
        with self.assertRaises(ValueError):m.validate_recipe(r)
    def test_order_and_selector_are_fixed(self):
        r=copy.deepcopy(self.recipe);r['frames'].reverse()
        with self.assertRaises(ValueError):m.validate_recipe(r)
        p,raw,frames=self.prepared();frames[0][0]['selected_cells_sha256']='0'*64
        with self.assertRaises(ValueError):m.derive(p,raw,frames)
    def test_wrong_hash_and_escaping_paths(self):
        for ref in [dict(path='parent.png',sha256='0'*64),dict(path='../parent.png',sha256='0'*64),dict(path='/parent.png',sha256='0'*64),dict(path='a/../parent.png',sha256='0'*64)]:
            with self.assertRaises((ValueError,OSError)):m.read_bound(self.root,ref)
    def test_symlink_file_and_parent_rejected(self):
        (self.root/'alias.png').symlink_to(self.root/'parent.png')
        with self.assertRaises(OSError):m.read_bound(self.root,dict(path='alias.png',sha256=self.bind('parent.png')['sha256']))
        (self.root/'folder').symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(OSError):m.read_bound(self.root,dict(path='folder/parent.png',sha256=self.bind('parent.png')['sha256']))
    def test_bytes_are_not_reopened(self):
        prepared=self.prepared();first=m.derive(*prepared)
        (self.root/'parent.png').write_bytes(b'corrupted after authenticated read')
        for a,b in zip(first,m.derive(*prepared)):self.assertTrue(np.array_equal(a[1],b[1]))
    def test_flat_parent_rejected(self):
        p,_,f=self.prepared();stream=io.BytesIO();Image.new('RGB',(256,128),(50,35,28)).save(stream,format='PNG')
        with self.assertRaisesRegex(ValueError,'witness'):m.derive(p,stream.getvalue(),f)
    def test_transparency_size_and_shift_caps(self):
        p,_,f=self.prepared()
        for image in [Image.new('RGBA',(256,128),(50,40,30,0)),Image.new('RGB',(128,128)),Image.new('RGB',(256,64))]:
            stream=io.BytesIO();image.save(stream,format='PNG')
            with self.assertRaises(ValueError):m.derive(p,stream.getvalue(),f)
        p[11]=[240,240,240]
        with self.assertRaisesRegex(ValueError,'fixed32'):m.derive(p,self.prepared()[1],f)
    def test_source_and_palette_validation(self):
        for b in [b'',struct.pack('<5i',2,1,0,32,32)+self.source.tobytes(),struct.pack('<5i',1,1,0,32,32)+bytes([254])*1024]:
            with self.assertRaises(ValueError):m.source_indices(b)
        for b in [bytes(767),bytes([64])*768]:
            with self.assertRaises(ValueError):m.palette_rgb(b)
    def test_fresh_publication_receipt_and_no_overwrite(self):
        (self.root/'recipe.json').write_text(json.dumps(self.recipe));out=self.root/'new-output'
        result=m.run('recipe.json',self.root,out)
        self.assertEqual(set(result['execution']),{'status','method','recipe_sha256','tool_sha256','source_sha256','parent_raw_sha256','output_sha256'})
        self.assertEqual(set(result['execution']['output_sha256']),{'203c6','203c7'})
        before=sorted(p.name for p in out.iterdir())
        with self.assertRaises(ValueError):m.run('recipe.json',self.root,out)
        self.assertEqual(before,sorted(p.name for p in out.iterdir()))
    def test_existing_empty_directory_no_replace(self):
        stage=self.root/'stage';target=self.root/'target';stage.mkdir();target.mkdir()
        with self.assertRaises(OSError):m.publish_no_replace(stage,target)
        self.assertTrue(stage.is_dir());self.assertTrue(target.is_dir())

    def test_outside_and_alpha_exact_against_independent_baseline(self):
        palette,raw,frames=self.prepared();result=m.derive(palette,raw,frames)
        with Image.open(io.BytesIO(raw))as im:parent=np.asarray(im.convert('RGBA'))
        for col,((asset,out,_),(_,src))in enumerate(zip(result,frames)):
            baseline=np.asarray(Image.fromarray(parent[:,col*128:(col+1)*128]).resize((128,128),Image.Resampling.LANCZOS))
            area=np.repeat(np.repeat(m.semantic_mask(asset,src),4,0),4,1)
            np.testing.assert_array_equal(out[~area],baseline[~area])
            np.testing.assert_array_equal(out[:,:,3],baseline[:,:,3])
            ys,xs=np.nonzero(area);a=(ys[0],xs[0]);different=np.abs((baseline[:,:,:3]@m.LUMA)-(baseline[a][:3]@m.LUMA))>2
            by,bx=np.nonzero(area&different);b=(by[0],bx[0])
            original_difference=float((baseline[a][:3].astype(float)-baseline[b][:3])@m.LUMA)
            output_difference=float((out[a][:3].astype(float)-out[b][:3])@m.LUMA)
            self.assertLessEqual(abs(original_difference-output_difference),1.0000002)
    def test_gray_index_boundaries_and_exclusive_region_edges(self):
        for asset,(x0,y0,x1,y1)in m.REGIONS.items():
            source=np.full((32,32),11,np.uint8);source[y0,x0:x0+4]=[10,11,30,31]
            mask=m.semantic_mask(asset,source)
            self.assertEqual(mask[y0,x0:x0+4].tolist(),[False,True,True,False])
            self.assertTrue(mask[y1-1,x1-1]);self.assertFalse(mask[y1,x1-1]);self.assertFalse(mask[y0,x1])
            self.assertFalse(mask[y0,x0-1])
            if y0:self.assertFalse(mask[y0-1,x0])
    def test_clipping_is_rejected_without_luminance_compression(self):
        palette,raw,frames=self.prepared()
        with Image.open(io.BytesIO(raw))as im:a=np.asarray(im.convert('RGB')).copy()
        a[30,90]=255;stream=io.BytesIO();Image.fromarray(a).save(stream,format='PNG')
        with self.assertRaisesRegex(ValueError,'clipping'):m.derive(palette,stream.getvalue(),frames)
    def test_nonneutral_source_anchor_rejected(self):
        palette,raw,frames=self.prepared();palette[11]=[75,50,30]
        with self.assertRaisesRegex(ValueError,'near-neutral'):m.derive(palette,raw,frames)
    def test_non_rgb_parent_and_malformed_frames_rejected(self):
        p,raw,f=self.prepared()
        for mode in ['L','P']:
            stream=io.BytesIO();Image.new(mode,(256,128)).save(stream,format='PNG')
            with self.assertRaises(ValueError):m.derive(p,stream.getvalue(),f)
        for bad in [None,7,'203c6',[]]:
            r=copy.deepcopy(self.recipe);r['frames'][0]=bad
            with self.assertRaises(ValueError):m.validate_recipe(r)
        for bad in [None,7,[]]:
            with self.assertRaises(ValueError):m.read_regular(self.root,bad)
    def test_fifo_is_nonblocking_and_regular_rejected(self):
        os.mkfifo(self.root/'pipe')
        code="import hd_grating_gray_cleanup as m; m.read_regular(__import__('sys').argv[1], 'pipe')"
        env=dict(os.environ,PYTHONPATH=str(Path(m.__file__).parent))
        child=subprocess.run([sys.executable,'-c',code,str(self.root)],capture_output=True,timeout=3,env=env)
        self.assertNotEqual(child.returncode,0);self.assertIn(b'bounded regular input required',child.stderr)
    def test_oversize_short_and_changed_reads_rejected(self):
        with self.assertRaisesRegex(ValueError,'bounded regular'):m.read_regular(self.root,'parent.png',limit=2)
        with mock.patch.object(m.os,'fdopen',return_value=io.BytesIO(b'x')):
            with self.assertRaisesRegex(ValueError,'changed'):m.read_regular(self.root,'parent.png')
        real=m.os.fstat;calls=[0]
        def changed(fd):
            st=real(fd);calls[0]+=1
            values={k:getattr(st,k)for k in ['st_mode','st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns']}
            if calls[0]%2==0:values['st_mtime_ns']+=1
            return SimpleNamespace(**values)
        with mock.patch.object(m.os,'fstat',side_effect=changed):
            with self.assertRaisesRegex(ValueError,'changed'):m.read_regular(self.root,'parent.png')

if __name__=='__main__':unittest.main()
