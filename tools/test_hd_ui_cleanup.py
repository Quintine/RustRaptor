"""Synthetic behavioral checks only: no Original catalog or generated-parent art."""
import copy
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

import hd_ui_cleanup as cleanup


class UICleanup(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def fixture(self,cells,raw=None,regions=None,classes=None,scale=4):
        h,w=len(cells),len(cells[0])
        source=bytearray(struct.pack('<5i',0,0,11,w,h))
        for y,row in enumerate(cells):
            for x,value in enumerate(row):
                if value<256:
                    source+=struct.pack('<4i',x,y,y*w+x,1)+bytes([value])
        source+=struct.pack('<4i',0,0,-1,0)
        (self.root/'Source').write_bytes(source)
        palette=bytearray(768)
        for i,value in [(10,[30,20,10]),(11,[45,30,15]),(31,[1,1,1]),(146,[21,37,39])]:
            palette[3*i:3*i+3]=bytes(value)
        (self.root/'palette').write_bytes(palette)
        if raw is None:
            yy,xx=np.indices((h*scale,w*scale))
            raw=np.stack([80+xx*3,60+yy*2,40+xx+yy,np.full_like(xx,255)],axis=2).astype(np.uint8)
        Image.fromarray(raw).save(self.root/'raw.png')
        bind=lambda name:dict(path=name,sha256=cleanup.sha((self.root/name).read_bytes()))
        if regions is None:
            regions=[dict(name='whole synthetic UI',source_bounds=[0,0,w,h],raw_bounds=[0,0,raw.shape[1],raw.shape[0]])]
        if classes is None:
            classes=[dict(index=i,max_channel_delta=16) for i in sorted({x for row in cells for x in row if x<256})]
        return dict(format_version=1,label='Synthetic fixture only',asset='1010f',
                    source=bind('Source'),palette=bind('palette'),parent_raw=bind('raw.png'),
                    logical_canvas=[w,h],origin=[0,0],output_scale=scale,
                    regions=regions,classes=classes)

    def test_counter_gaps_and_missing_filled_slot_keep_exact_original_semantics(self):
        # Literal ring/counter plus a separate filled slot and one empty slot.
        cells=[[10,10,10,256,10,256],
               [10,256,10,256,256,256],
               [10,10,10,256,10,256]]
        yy,xx=np.indices((12,24))
        raw=np.stack([80+xx*3,60+yy*2,40+xx+yy,np.full_like(xx,255)],axis=2).astype(np.uint8)
        raw[0:4,16:20]=[255,0,255,0]  # Genuine Source-filled slot absent from raw.
        recipe=self.fixture(cells,raw)
        rgba,report=cleanup.render(recipe,self.root)
        expected=np.zeros((12,24),dtype=bool)
        expected[0:4,0:12]=True;expected[4:8,0:4]=True;expected[4:8,8:12]=True
        expected[8:12,0:12]=True;expected[0:4,16:20]=True;expected[8:12,16:20]=True
        self.assertTrue(np.array_equal(rgba[:,:,3]==255,expected))
        self.assertTrue(np.all(rgba[~expected]==0),'raw ghost widgets and counters stay empty')
        self.assertTrue(np.all(rgba[0:4,16:20,:3]==[121,81,40]))
        self.assertEqual(report['restored_flat_Original_functional_pixels'],16)
        self.assertEqual(report['restored_Original_cells'],[[4,0]])
        self.assertEqual(report['direct_generated_support_fraction'],0.9)
        self.assertGreater(report['generated_fine_RGB_pixels'],0)

    def test_two_rails_keep_canvas_edge_and_full_lower_right_endpoint(self):
        cells=[[146]*8,[256]*8,[256]*8,[256,31,31,31,31,31,31,256],[256]*8]
        yy,xx=np.indices((12,40))
        raw=np.stack([80+xx,70+yy*2,60+xx//2,np.full_like(xx,255)],axis=2).astype(np.uint8)
        recipe=self.fixture(cells,raw,
             regions=[dict(name='upper rail',source_bounds=[0,0,8,1],raw_bounds=[2,0,38,4]),
                      dict(name='lower rail',source_bounds=[1,3,7,4],raw_bounds=[6,8,34,12])],
             classes=[dict(index=31,max_channel_delta=2),dict(index=146,max_channel_delta=16)])
        rgba,report=cleanup.render(recipe,self.root)
        self.assertTrue(np.all(rgba[0:4,:,3]==255),'top rail includes both canvas edges')
        self.assertTrue(np.all(rgba[12:16,4:28,3]==255),'last lower endpoint remains present')
        self.assertTrue(np.all(rgba[12:16,:4]==0))
        self.assertTrue(np.all(rgba[12:16,28:]==0))
        self.assertTrue(np.all(rgba[4:12]==0));self.assertTrue(np.all(rgba[16:]==0))
        self.assertLessEqual(int(rgba[12:16,4:28,:3].max()),6,'nearblack rail cannot become gray')
        self.assertEqual(report['painted_output_pixels'],224)
        self.assertEqual(report['runtime_crop'],None)

    def test_distinct_light_dark_classes_retain_generated_chroma_and_spatial_detail(self):
        recipe=self.fixture([[10,10,11,11],[10,10,11,11]])
        rgba,report=cleanup.render(recipe,self.root)
        light=rgba[:,8:,:3];dark=rgba[:,:8,:3]
        self.assertGreater(float(light.mean()),float(dark.mean())+15)
        self.assertGreater(int(dark[0,-1,0]),int(dark[0,0,0]),'real horizontal red variation survives')
        self.assertEqual(int(dark[0,-1,1]),int(dark[0,0,1]),'no invented horizontal green variation')
        self.assertGreater(int(dark[-1,0,1]),int(dark[0,0,1]),'real vertical green variation survives')
        self.assertTrue(all(c['generated_supported_pixels']>0 for c in report['class_tone_controls']))
        self.assertTrue(report['raw_RGB_is_shifted_and_bounded_not_claimed_byte_exact'])

    def test_hidden_transparent_rgb_is_not_used_to_paint_missing_strokes(self):
        yy,xx=np.indices((8,8));raw=np.stack([80+xx*3,60+yy*2,40+xx+yy,np.full_like(xx,255)],axis=2).astype(np.uint8)
        raw[:4,:4]=[0,255,255,0]
        recipe=self.fixture([[10,10],[10,10]],raw)
        rgba,report=cleanup.render(recipe,self.root)
        self.assertTrue(np.all(rgba[:4,:4,:3]==[121,81,40]))
        self.assertEqual(report['restored_flat_Original_functional_pixels'],16)

    def test_flat_raw_cannot_borrow_source_class_contrast_as_generated_hd_credit(self):
        raw=np.full((8,16,4),[110,90,70,255],dtype=np.uint8)
        recipe=self.fixture([[10,10,11,11],[10,10,11,11]],raw)
        with self.assertRaisesRegex(ValueError,'no generated fine RGB'):
            cleanup.render(recipe,self.root)

    def test_flat_visible_parent_feather_and_hidden_rgb_cannot_gain_detail_from_resampling(self):
        # Literal independent-review geometry:17x15 parent onto16x8 output.
        for style in ['feather boundary','hidden transparent RGB','constant semitransparency']:
            with self.subTest(style=style):
                raw=np.full((15,17,4),[110,90,70,255],dtype=np.uint8)
                if style=='feather boundary':raw[:3,:,3]=80;raw[:,:2,3]=0
                elif style=='hidden transparent RGB':raw[:3]=[0,255,255,0]
                else:raw[:,:,3]=150
                recipe=self.fixture([[10,10,11,11],[10,10,11,11]],raw)
                self.assertEqual(len(np.unique(raw[raw[:,:,3]>=128,:3],axis=0)),1)
                with patch.object(Image.Image,'resize',side_effect=AssertionError('flat material must fail before any resize')):
                    with self.assertRaisesRegex(ValueError,'no pre-resample visible parent material variance'):
                        cleanup.render(recipe,self.root)

    def test_nearopaque252_253_textured_parent_is_visible_material_not_artificially_required255(self):
        for alpha in [252,253]:
            with self.subTest(alpha=alpha):
                yy,xx=np.indices((15,17))
                raw=np.stack([70+xx*3,60+yy*2,30+xx+yy,np.full_like(xx,alpha)],axis=2).astype(np.uint8)
                recipe=self.fixture([[10,10,11,11],[10,10,11,11]],raw)
                rgba,report=cleanup.render(recipe,self.root)
                self.assertTrue(np.all(rgba[:,:,3]==255),'Original controls output occupancy independently of parent opacity')
                self.assertGreater(report['pre_resample_visible_parent_material_witnesses'],0)
                self.assertGreater(report['registered_certified_parent_material_pixels'],0)
                self.assertGreater(report['generated_fine_RGB_pixels'],0)
                self.assertEqual(report['parent_material_visibility']['alpha_min'],128)

    def test_visibility_boundary_128_is_eligible_and_127_is_excluded_before_resampling(self):
        yy,xx=np.indices((12,16))
        for alpha in [127,128]:
            raw=np.stack([70+xx*3,60+yy*2,30+xx+yy,np.full_like(xx,alpha)],axis=2).astype(np.uint8)
            recipe=self.fixture([[10,10,11,11],[10,10,11,11]],raw)
            if alpha==127:
                with patch.object(Image.Image,'resize',side_effect=AssertionError('low-alpha material must fail before any resize')):
                    with self.assertRaisesRegex(ValueError,'no pre-resample visible parent material variance'):
                        cleanup.render(recipe,self.root)
            else:
                rgba,report=cleanup.render(recipe,self.root)
                self.assertGreater(report['pre_resample_visible_parent_material_witnesses'],0)

    def test_rgb_variance_only_below_visible_alpha_or_across_classes_cannot_certify_parent(self):
        classes=np.full((7,7),10,dtype=np.uint16)
        raw=np.full((7,7,4),[110,90,70,253],dtype=np.uint8)
        raw[3,4]=[210,120,90,127]
        self.assertFalse(cleanup.parent_material_witnesses(raw,classes).any())
        raw[3,4,3]=128
        self.assertTrue(cleanup.parent_material_witnesses(raw,classes)[3,3])
        classes[3,4]=11
        self.assertFalse(cleanup.parent_material_witnesses(raw,classes)[3,3])

    def test_material_only_in_source_empty_gaps_cannot_authorize_flat_painted_glyphs(self):
        raw=np.full((16,24,4),[110,90,70,255],dtype=np.uint8)
        yy,xx=np.indices((16,8))
        raw[:,8:16,:3]=np.stack([100+xx*3,90+yy*2,70+xx+yy],axis=2)
        recipe=self.fixture([[10,256,10],[10,256,10]],raw)
        with self.assertRaisesRegex(ValueError,'no pre-resample visible parent material variance'):
            cleanup.render(recipe,self.root)

    def test_flat_palette_class_boundaries_do_not_count_as_material_detail(self):
        raw=np.full((12,24,4),[110,90,70,255],dtype=np.uint8)
        raw[:,12:,:3]=[150,100,80]
        recipe=self.fixture([[10,10,11,11],[10,10,11,11]],raw)
        with self.assertRaisesRegex(ValueError,'no pre-resample visible parent material variance'):
            cleanup.render(recipe,self.root)

    def test_valid_uncompressed_kind1_source_keeps_byte_palette_values_and_renders(self):
        recipe=self.fixture([[10,10],[10,10]])
        source=struct.pack('<5i',1,1,0,2,2)+bytes([10,10,10,10])
        (self.root/'Source').write_bytes(source)
        recipe['source']['sha256']=cleanup.sha(source)
        rgba,report=cleanup.render(recipe,self.root)
        self.assertEqual(rgba.shape,(8,8,4))
        self.assertTrue(np.all(rgba[:,:,3]==255))
        self.assertEqual(report['Original_painted_cells'],4)
        self.assertGreater(report['pre_resample_visible_parent_material_witnesses'],0)
        self.assertGreater(report['registered_certified_parent_material_pixels'],0)
        self.assertGreater(report['generated_fine_RGB_pixels'],0)

    def test_majority_missing_support_is_rejected(self):
        yy,xx=np.indices((8,8));raw=np.stack([80+xx*3,60+yy*2,40+xx+yy,np.zeros_like(xx)],axis=2).astype(np.uint8)
        raw[:4,:4,3]=255
        recipe=self.fixture([[10,10],[10,10]],raw)
        with self.assertRaisesRegex(ValueError,'most generated UI support'):
            cleanup.render(recipe,self.root)

    def test_overlapping_or_incomplete_registrations_fail_closed(self):
        recipe=self.fixture([[10,10],[10,10]])
        duplicate=copy.deepcopy(recipe);duplicate['regions'].append(copy.deepcopy(duplicate['regions'][0]))
        with self.assertRaisesRegex(ValueError,'overlap'):cleanup.render(duplicate,self.root)
        missing=copy.deepcopy(recipe);missing['regions'][0]['source_bounds']=[0,0,1,2]
        with self.assertRaisesRegex(ValueError,'do not cover'):cleanup.render(missing,self.root)

    def test_identity_canvas_origin_classes_and_numeric_types_fail_closed(self):
        recipe=self.fixture([[10,10],[10,10]])
        mutations=[lambda r:r['source'].update(sha256='0'*64),
                   lambda r:r.update(logical_canvas=[3,2]),
                   lambda r:r.update(origin=[1,0]),
                   lambda r:r.update(origin=[False,0]),
                   lambda r:r.update(output_scale=True),
                   lambda r:r['classes'][0].update(index=True),
                   lambda r:r['classes'][0].update(max_channel_delta=float('nan')),
                   lambda r:r['classes'][0].update(max_channel_delta=33),
                   lambda r:r['classes'].append(dict(index=11,max_channel_delta=16)),
                   lambda r:r['regions'][0].update(raw_bounds=[0,0,9,8]),
                   lambda r:r.update(unrecognized_policy=True)]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                bad=copy.deepcopy(recipe);mutate(bad)
                with self.assertRaises(ValueError):cleanup.render(bad,self.root)

    def test_empty_or_reserved_original_is_not_silently_repaired(self):
        empty=self.fixture([[256,256],[256,256]])
        with self.assertRaisesRegex(ValueError,'no painted UI'):cleanup.render(empty,self.root)
        reserved=self.fixture([[240,10],[10,10]])
        with self.assertRaisesRegex(ValueError,'ordinary Original palette'):cleanup.render(reserved,self.root)

    def test_resource_bounds_stop_before_output_allocation_or_decoding_large_inputs(self):
        recipe=self.fixture([[10,10],[10,10]])
        with patch.object(cleanup,'MAX_PIXELS',63):
            with self.assertRaisesRegex(ValueError,'derived image exceeds pixel ceiling'):
                cleanup.render(recipe,self.root)
        with self.assertRaisesRegex(ValueError,'input byte limit exceeded'):
            cleanup.checked_input(recipe['parent_raw'],self.root,byte_limit=1)

    def test_repeatable_new_output_full_lineage_and_inputs_unchanged(self):
        recipe=self.fixture([[10,10,11],[10,256,11]])
        p=self.root/'recipe.json';p.write_text(json.dumps(recipe,sort_keys=True))
        before={n:(self.root/n).read_bytes() for n in ['Source','palette','raw.png']}
        reports=[cleanup.run_recipe(p,self.root/f'output{i}') for i in range(2)]
        images=[(self.root/f'output{i}/1010f-derived.png').read_bytes() for i in range(2)]
        self.assertEqual(images[0],images[1]);self.assertEqual(reports[0],reports[1])
        execution=reports[0]['execution']
        self.assertEqual(execution['status'],'success')
        self.assertEqual(execution['method'],cleanup.METHOD)
        self.assertEqual(execution['source_sha256'],{'1010f':recipe['source']['sha256']})
        self.assertEqual(execution['parent_raw_sha256'],[recipe['parent_raw']['sha256']])
        self.assertEqual(execution['recipe_sha256'],cleanup.sha(p.read_bytes()))
        self.assertEqual(execution['tool_sha256'],cleanup.sha(Path(cleanup.__file__).read_bytes()))
        self.assertEqual(execution['output_sha256'],{'1010f':cleanup.sha(images[0])})
        self.assertEqual(reports[0]['Source_decoder_sha256'],cleanup.sha(Path(cleanup.hd_frame_policy.__file__).read_bytes()))
        self.assertEqual(before,{n:(self.root/n).read_bytes() for n in before})
        with self.assertRaisesRegex(ValueError,'output exists'):
            cleanup.run_recipe(p,self.root/'output0')


if __name__=='__main__':
    unittest.main()
