"""Focused synthetic-only tests. Never load production input artwork or QA."""
import copy
from fractions import Fraction
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import numpy as np
from PIL import Image

Q=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('stag03_private_test',Q/'hd_stag03_cleanup.py')
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)

class AffineCleanup(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.source=np.full((32,32),256,np.uint16);self.source[5:30,1:30]=10
        for x in list(range(1,11))+list(range(20,30)):self.source[14,x]=[85,28,82,28,80][(x-1)%5]
        self.write_source()
        self.palette_bytes=bytes((np.arange(768)%64).astype(np.uint8));(self.root/'palette').write_bytes(self.palette_bytes)
        y,x=np.indices((160,160));rgba=np.zeros((160,160,4),np.uint8)
        rgba[:,:,:3]=np.stack([(x*3+y)%255,(x+y*2)%255,(x*7+y*5)%255],axis=-1)
        rgba[5:150,2:150,3]=255;rgba[rgba[:,:,3]==0,:3]=0
        Image.fromarray(rgba).save(self.root/'parent.png')
        self.dep_names={'decoder':'hd_frame_policy.py','geometry':'hd_dshp20_cleanup.py','functional':'hd_other_functional_cleanup.py'}
        (self.root/'deps').mkdir()
        for name in self.dep_names.values():shutil.copyfile(Q/name,self.root/'deps'/name)
        self.recipe=dict(format_version=1,method=c.METHOD,asset='300ae',source=self.bind('Source.pic'),
            parent_raw=self.bind('parent.png'),palette=self.bind('palette'),logical_canvas=[32,32],origin=[0,0],output_scale=4,
            alignment=dict(raw_painted_bounds=[2,5,150,150],source_painted_bounds=[1,5,30,30],
                inverse_affine=['37/29','0','-90/29','0','29/20','-24']),
            max_fill_distance_pixels=12,functional_groups=copy.deepcopy(c.GROUPS),
            dependencies={k:self.bind('deps/'+name)for k,name in self.dep_names.items()},expected_tool_sha256=c.sha(c.TOOL_BYTES))

    def write_source(self):
        b=bytearray(struct.pack('<5i',0,1,31,32,32))
        for y in range(32):
            x=0
            while x<32:
                if self.source[y,x]>=256:x+=1;continue
                start=x
                while x<32 and self.source[y,x]<256:x+=1
                b.extend(struct.pack('<4i',start,y,y*32+start,x-start));b.extend(bytes(self.source[y,start:x].tolist()))
        b.extend(struct.pack('<4i',0,0,-1,0));(self.root/'Source.pic').write_bytes(b)

    def bind(self,name):return dict(path=name,sha256=c.sha((self.root/name).read_bytes()))
    def rp(self,recipe=None):
        path=self.root/'recipe.json';path.write_text(json.dumps(self.recipe if recipe is None else recipe));return path
    def modules(self):return c.verified_modules({k:(Q/n).read_bytes()for k,n in self.dep_names.items()})
    def assert_no_output(self):
        self.assertFalse((self.root/'derived').exists())
        self.assertFalse(list(self.root.glob('.stag03-derived-*')))

    def test_valid_fullcanvas_negative_virtual_coordinates_and_receipt(self):
        rp=self.rp();before={p:p.read_bytes()for p in self.root.rglob('*')if p.is_file()}
        report=c.run_recipe(rp,self.root/'derived')
        self.assertEqual(report['actual_functional_calls'],2)
        self.assertEqual(report['functional_Original_cells'],66)
        self.assertEqual(report['actual_Original_Scale4_RGBA_samples'],1056)
        self.assertEqual(report['execution']['source_sha256'],{'300ae':self.bind('Source.pic')['sha256']})
        self.assertEqual(report['authenticated_dependency_bytes'],c.PINS)
        self.assertTrue(report['alpha_exact_SourceScale4'])
        self.assertLess(float(Fraction(report['fullcanvas_inverse_affine'][2])),0)
        out=np.asarray(Image.open(self.root/'derived/300ae-derived.png'))
        _,g,_=self.modules();s4=g.scale2(g.scale2(self.source))
        self.assertTrue(np.array_equal(out[:,:,3]>0,s4<256))
        self.assertTrue(np.all(out[s4==256,:3]==0))
        self.assertEqual(c.sha((self.root/'derived/300ae-derived.png').read_bytes()),report['execution']['output_sha256']['300ae'])
        for p,b in before.items():self.assertEqual(p.read_bytes(),b)
        with self.assertRaisesRegex(ValueError,'fresh absent'):c.run_recipe(rp,self.root/'derived')

    def test_bad_nonfinite_and_malformed_affines_fail_without_outputs(self):
        cases=[]
        for values in ([float('nan'),0,0,0,1,0],['nan','0','0','0','1','0'],['1/0','0','0','0','1','0'],
                       ['1e100','0','0','0','1','0'],[True,0,0,0,1,0],['-1','0','0','0','1','0'],
                       ['37/29','1','-90/29','0','29/20','-24'],['1']):
            r=copy.deepcopy(self.recipe);r['alignment']['inverse_affine']=values;cases.append(r)
        for index,r in enumerate(cases):
            with self.subTest(case=index),self.assertRaises(ValueError):c.run_recipe(self.rp(r),self.root/'derived')
            self.assert_no_output()

    def test_bounds_must_match_complete_source_and_parent(self):
        for key,value in [('raw_painted_bounds',[-1,5,150,150]),('raw_painted_bounds',[2,5,161,150]),
            ('raw_painted_bounds',[2,5,2,150]),('raw_painted_bounds',[2,6,150,150]),
            ('source_painted_bounds',[1,4,30,30]),('source_painted_bounds',[True,5,30,30])]:
            r=copy.deepcopy(self.recipe);r['alignment'][key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):c.run_recipe(self.rp(r),self.root/'derived')
            self.assert_no_output()

    def test_exact_functional_sets_reject_extra_missing_bool_or_duplicate_cells(self):
        for kind in ('extra','missing','bool','duplicate'):
            r=copy.deepcopy(self.recipe)
            if kind=='extra':r['functional_groups'][0].append([12,14])
            if kind=='missing':r['functional_groups'][0].pop()
            if kind=='bool':r['functional_groups'][0][0]=[True,13]
            if kind=='duplicate':r['functional_groups'][0][1]=r['functional_groups'][0][0]
            with self.subTest(kind=kind),self.assertRaises(ValueError):c.run_recipe(self.rp(r),self.root/'derived')
            self.assert_no_output()

    def test_selected_cells_must_have_authentic_source_support(self):
        self.source[13,1]=256;self.write_source();self.recipe['source']=self.bind('Source.pic')
        with self.assertRaisesRegex(ValueError,'painted Source'):c.run_recipe(self.rp(),self.root/'derived')
        self.assert_no_output()

    def test_dependency_bytes_are_verified_then_isolated_not_imported_by_path(self):
        before=list(sys.path);a=self.modules();b=self.modules()
        self.assertEqual(sys.path,before)
        self.assertIsNot(a[0],b[0]);self.assertIsNot(a[1],b[1]);self.assertIsNot(a[2],b[2])
        self.assertIs(a[2].base,a[1]);self.assertIs(a[1].hd_frame_policy,a[0])
        payloads={k:(Q/n).read_bytes()for k,n in self.dep_names.items()};payloads['geometry']+=b'\n'
        with self.assertRaisesRegex(ValueError,'dependency bytes'):c.verified_modules(payloads)

    def test_processing_never_reopens_dependency_or_input_paths(self):
        rp=self.rp();actual_render=c.render
        def render_buffered(*args):
            # Every payload already passed its declared hash. Path-reopening
            # would fail, including dependency SourceFileLoader habits.
            with patch.object(Path,'read_bytes',side_effect=AssertionError('processing reopened a path')):
                return actual_render(*args)
        with patch.object(c,'render',render_buffered):c.run_recipe(rp,self.root/'derived')
        self.assertTrue((self.root/'derived/300ae-derived.png').is_file())

    def test_buffered_verified_dependency_survives_later_path_change(self):
        rp=self.rp();actual=c.safe_read
        def read_then_change(base,binding,limit):
            result=actual(base,binding,limit)
            if binding['path']=='deps/hd_other_functional_cleanup.py':
                (base/binding['path']).write_text('raise RuntimeError("unverified later path")')
            return result
        with patch.object(c,'safe_read',read_then_change):report=c.run_recipe(rp,self.root/'derived')
        self.assertEqual(report['authenticated_dependency_bytes']['functional'],c.PINS['functional'])

    def test_no_parent_absolute_backslash_or_symlink_input_escape(self):
        for value in ('../Source.pic','/absolute','deps/../Source.pic','Source\\pic'):
            r=copy.deepcopy(self.recipe);r['source']['path']=value
            with self.subTest(value=value),self.assertRaises(ValueError):c.run_recipe(self.rp(r),self.root/'derived')
            self.assert_no_output()
        (self.root/'Source-link').symlink_to(self.root/'Source.pic')
        r=copy.deepcopy(self.recipe);r['source']['path']='Source-link'
        with self.assertRaises(OSError):c.run_recipe(self.rp(r),self.root/'derived')
        self.assert_no_output()
        (self.root/'outside-dir').symlink_to(self.root/'deps',target_is_directory=True)
        r=copy.deepcopy(self.recipe);r['dependencies']['decoder']['path']='outside-dir/hd_frame_policy.py'
        with self.assertRaises(OSError):c.run_recipe(self.rp(r),self.root/'derived')
        self.assert_no_output()

    def test_hash_failure_and_tool_mismatch_stop_before_output(self):
        for key in ('source','palette','parent_raw'):
            r=copy.deepcopy(self.recipe);r[key]['sha256']='0'*64
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'SHA256 mismatch'):c.run_recipe(self.rp(r),self.root/'derived')
            self.assert_no_output()
        r=copy.deepcopy(self.recipe);r['expected_tool_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'tool bytes'):c.run_recipe(self.rp(r),self.root/'derived')
        self.assert_no_output()

    def test_twelve_pixel_generated_fill_never_cascades(self):
        _,g,_=self.modules();rgb=np.zeros((1,27,3),np.uint8);rgb[0,0]=[3,4,5]
        trusted=np.zeros((1,27),bool);trusted[0,0]=True;mask=np.ones_like(trusted);s=np.zeros((1,27),np.uint16)
        with self.assertRaisesRegex(ValueError,'donor'):g.fill_generated_rgb(rgb,trusted,mask,s,12)
        self.assertEqual(rgb[0,1].tolist(),[0,0,0])

    def test_bad_support_needs_generated_donor_and_cannot_be_sourcenn_relabel(self):
        a=np.zeros((160,160,4),np.uint8);a[5:150,2:150]=[100,100,100,255]
        Image.fromarray(a).save(self.root/'parent.png');self.recipe['parent_raw']=self.bind('parent.png')
        with self.assertRaisesRegex(ValueError,'interior detail'):c.run_recipe(self.rp(),self.root/'derived')
        self.assert_no_output()

    def test_write_failure_leaves_no_outputs_and_no_false_receipt(self):
        rp=self.rp();before={p:p.read_bytes()for p in self.root.rglob('*')if p.is_file()}
        with patch.object(c.os,'fsync',side_effect=OSError('synthetic write failure')):
            with self.assertRaises(OSError):c.run_recipe(rp,self.root/'derived')
        self.assert_no_output()
        for p,b in before.items():self.assertEqual(p.read_bytes(),b)

    def test_publication_race_does_not_replace_existing_even_empty_directory(self):
        rp=self.rp();actual=c.publish_no_replace
        def race(staging,output):output.mkdir();return actual(staging,output)
        with patch.object(c,'publish_no_replace',race),self.assertRaises(FileExistsError):c.run_recipe(rp,self.root/'derived')
        self.assertEqual(list((self.root/'derived').iterdir()),[])
        self.assertFalse(list(self.root.glob('.stag03-derived-*')))

    def test_output_cannot_escape_recipe_root(self):
        with tempfile.TemporaryDirectory()as other:
            with self.assertRaisesRegex(ValueError,'direct child'):c.run_recipe(self.rp(),Path(other)/'derived')
            self.assertFalse((Path(other)/'derived').exists())
        self.assert_no_output()

    def test_free_floor_stops_before_dependency_or_artwork_reads(self):
        with patch.object(c.shutil,'disk_usage',return_value=types.SimpleNamespace(free=3_000_000_000)):
            with patch.object(c,'safe_read',side_effect=AssertionError('input read before floor guard')):
                with self.assertRaisesRegex(ValueError,'free floor'):c.run_recipe(self.rp(),self.root/'derived')
        self.assert_no_output()

if __name__=='__main__':unittest.main(verbosity=2)
