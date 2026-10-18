"""Focused synthetic alignment/form/animation/provenance checks, no game data."""
import copy
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest

import numpy as np
from PIL import Image

import hd_worm_cleanup as cleanup


class WormCleanup(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sources = []
        for phase in range(2):
            cells = np.full((8, 8), 256, dtype=np.uint16)
            cells[1:7, 1:7] = 10
            cells[2:6, 2:6] = 20+phase
            cells[3, 6] = 30
            cells[6, 2] = 30
            self.sources.append(cells)
            payload = bytearray(struct.pack('<5i', 0, 0, 0, 8, 8))
            for y, x in np.argwhere(cells < 256):
                payload += struct.pack('<4i', int(x), int(y), int(y*8+x), 1)+bytes([cells[y, x]])
            payload += struct.pack('<4i', 0, 0, -1, 0)
            (self.root/f'Source{phase}').write_bytes(payload)
        palette = bytearray(768)
        for index, rgb in [(10, [12, 12, 12]), (20, [25, 15, 12]), (21, [36, 24, 18]), (30, [0, 0, 14])]:
            palette[index*3:index*3+3] = bytes(rgb)
        (self.root/'palette').write_bytes(palette)
        self.raw = np.zeros((64, 128, 4), dtype=np.uint8)
        for phase in range(2):
            for y in range(8, 56):
                for x in range(8, 56):
                    warm = 16 <= x < 48 and 16 <= y < 48
                    rgb = [70+x*2, 30+y, 25+x//2] if warm else [25+x//2+phase*8, 25+y//2+phase*8, 25+(x+y)//4+phase*8]
                    self.raw[y, x+phase*64] = [*rgb, 255]
        self.save_raw()
        bind = lambda p: {'path':p,'sha256':cleanup.sha((self.root/p).read_bytes())}
        self.recipe = dict(format_version=1, label='synthetic only', palette=bind('palette'), output_scale=8,
                           feather_logical_pixels=1, frames=[dict(asset=f'3003{phase}', source=bind(f'Source{phase}'),
                               parent_raw=bind('raw.png'), logical_canvas=[8,8], origin=[0,0],
                               atlas_grid=dict(columns=2,rows=1,column=phase,row=0),
                               raw_painted_bounds=[8+phase*64,8,56+phase*64,56]) for phase in range(2)])

    def save_raw(self):
        Image.fromarray(self.raw).save(self.root/'raw.png')

    def rebind_raw(self, recipe):
        for frame in recipe['frames']:
            frame['parent_raw']['sha256'] = cleanup.sha((self.root/'raw.png').read_bytes())

    def test_source_alpha_cues_and_continuous_generated_form_survive(self):
        outputs, report = cleanup.render_family(self.recipe, self.root)
        self.assertFalse(report['per_Source_cell_RGB_reconstruction'])
        for source, output, frame in zip(self.sources, outputs, report['frames']):
            occupied = cleanup.up(source<256,8)
            self.assertTrue(np.array_equal(output[:,:,3]==255,occupied))
            self.assertTrue(np.all(output[~occupied]==0))
            self.assertTrue(np.all(output[24:32,48:56,:3]==[0,0,56]))
            # Source warm cells are one flat color, but generated gradients must
            # remain different across cells and within each cell after cleanup.
            self.assertGreater(np.ptp(output[24:40,24:40,0]),15)
            self.assertNotEqual(float(output[24:32,24:32,0].mean()),float(output[24:32,32:40,0].mean()))
            self.assertEqual(frame['functional_blue_Source_RGB_cells'],2)

    def test_stationary_generated_backing_shared_and_early_phase_dimmer(self):
        outputs, report = cleanup.render_family(self.recipe, self.root)
        common = cleanup.up(self.sources[0]==self.sources[1],8)
        self.assertTrue(np.array_equal(outputs[0][common],outputs[1][common]))
        self.assertLess(outputs[0][24:40,24:40,:3].mean(),outputs[1][24:40,24:40,:3].mean())
        self.assertEqual(report['Source_changing_union_cells'],16)

    def test_generated_gap_fill_is_local_and_never_source_rgb(self):
        rgb=np.array([[[10,20,30],[90,80,70]],[[60,50,40],[1,2,3]]],dtype=np.uint8)
        trusted=np.array([[True,False],[False,True]])
        filled,count=cleanup.nearest_generated_fill(rgb,trusted,np.ones((2,2),dtype=bool))
        self.assertEqual(count,2)
        self.assertTrue(np.array_equal(filled[trusted],rgb[trusted]))
        self.assertTrue(np.array_equal(filled[0,1],rgb[0,0]))
        self.assertTrue(np.array_equal(filled[1,0],rgb[0,0]))

    def test_blend_never_modifies_stationary_region(self):
        mask=np.zeros((12,12),dtype=bool);mask[2:10,2:10]=True
        weight=cleanup.inner_weight(mask,4)
        self.assertTrue(np.all(weight[~mask]==0))
        self.assertEqual(weight[2,2],0.25)
        self.assertEqual(weight[5,5],1)

    def test_invalid_identity_bounds_grid_origin_fail_before_output(self):
        mutations=[lambda r:r['frames'][0]['source'].update(sha256='0'*64),
                   lambda r:r['frames'][0].update(origin=[False,0]),
                   lambda r:r['frames'][0].update(origin=[1,0]),
                   lambda r:r['frames'][0].update(raw_painted_bounds=[9,8,56,56]),
                   lambda r:r['frames'][0]['atlas_grid'].update(column=2),
                   lambda r:r['frames'][0]['atlas_grid'].update(rows=2),
                   lambda r:r.update(output_scale=True)]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                recipe=copy.deepcopy(self.recipe);mutate(recipe)
                with self.assertRaises(ValueError):cleanup.render_family(recipe,self.root)

    def test_opaque_and_detail_free_parents_rejected(self):
        self.raw[:,:,3]=255;self.save_raw();r=copy.deepcopy(self.recipe);self.rebind_raw(r)
        with self.assertRaisesRegex(ValueError,'transparent alpha'):cleanup.render_family(r,self.root)
        self.raw[:]=0
        self.raw[8:56,8:56]=[80,50,40,255];self.raw[8:56,72:120]=[80,50,40,255]
        self.save_raw();self.rebind_raw(r)
        with self.assertRaisesRegex(ValueError,'no generated spatial RGB'):cleanup.render_family(r,self.root)

    def test_repeatability_and_full_execution_decoder_version_bindings(self):
        recipe=self.root/'recipe.json';recipe.write_text(json.dumps(self.recipe,sort_keys=True)+'\n')
        original={p.name:p.read_bytes() for p in self.root.iterdir() if p.is_file()}
        reports=[cleanup.run_recipe(recipe,self.root/f'derived{i}') for i in range(2)]
        self.assertEqual(reports[0],reports[1])
        report=reports[0];execution=report['execution']
        self.assertEqual(execution['status'],'success')
        self.assertEqual(execution['method'],cleanup.METHOD)
        self.assertEqual(execution['recipe_sha256'],hashlib.sha256(recipe.read_bytes()).hexdigest())
        self.assertEqual(execution['tool_sha256'],cleanup.sha(Path(cleanup.__file__).read_bytes()))
        self.assertEqual(report['decoder_module']['sha256'],cleanup.sha(Path(cleanup.hd_frame_policy.__file__).read_bytes()))
        for field in ['python_version','numpy_version','pillow_version']:self.assertTrue(report[field])
        self.assertEqual(execution['source_sha256'],{f['asset']:f['source']['sha256'] for f in self.recipe['frames']})
        self.assertEqual(len(execution['parent_raw_sha256']),1)
        for frame in self.recipe['frames']:
            name=frame['asset']+'-derived.png';p=self.root/'derived0'/name
            self.assertEqual(p.read_bytes(),(self.root/'derived1'/name).read_bytes())
            self.assertEqual(execution['output_sha256'][frame['asset']],cleanup.sha(p.read_bytes()))
        for name,data in original.items():self.assertEqual((self.root/name).read_bytes(),data)
        with self.assertRaisesRegex(ValueError,'output exists'):cleanup.run_recipe(recipe,self.root/'derived0')


if __name__=='__main__':unittest.main()
