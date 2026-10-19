"""Real synthetic RLE8/24 aliases and actual unmocked parent rendering/receipt."""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('person01_under_test', HERE/'hd_person01_cleanup.py')
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)
# Public tools layout uses its existing parent test fixture. The private CODE
# packet carries an exact small copy under dependency-project for review only.
PARENT_TOOLS = HERE if (HERE/'test_hd_infantry_cleanup.py').is_file() else HERE/'dependency-project/tools'
ps = importlib.util.spec_from_file_location('actual_synthetic_parent_fixture', PARENT_TOOLS/'test_hd_infantry_cleanup.py')
parent_fixture_module = importlib.util.module_from_spec(ps)
ps.loader.exec_module(parent_fixture_module)


class PersonRecipeTests(unittest.TestCase):
    def setUp(self):
        self.fixture = parent_fixture_module.CompleteRecipeTests(methodName='runTest')
        self.fixture.setUp()
        self.root, self.base, self.project = self.fixture.root, self.fixture.base, self.fixture.project
        shutil.copyfile(PARENT_TOOLS/'hd_infantry_cleanup.py', self.project/'tools/hd_infantry_cleanup.py')
        self.parent_output = self.root/'parent-output'
        parent_receipt = parent_fixture_module.tool.run_recipe(self.fixture.path, self.parent_output, self.project)
        receipt = self.base/'parent-execution.json'
        receipt.write_text(json.dumps(parent_receipt))
        frames = []
        for i, asset in enumerate(tool.ASSETS):
            child = self.fixture.sources[i][0:8, 5:13].copy()
            path = self.base/f'{asset}.bin'
            path.write_bytes(parent_fixture_module.rle(child))
            frames.append(dict(asset=asset, parent_asset=parent_fixture_module.tool.ASSETS[i],
                               source=self.fixture.bind(path), functional_original_cells=[[3, 3]]))
        self.recipe = dict(format_version=1, method=tool.METHOD,
            parent_recipe=self.fixture.bind(self.fixture.path),
            parent_execution_receipt=self.fixture.bind(receipt), frames=frames)
        self.path = self.base/'person-recipe.json'
        self.output = self.root/'child-output'

    def tearDown(self):
        self.fixture.tearDown()

    def write(self):
        self.path.write_text(json.dumps(self.recipe))

    def run_real(self):
        self.write()
        return tool.run_recipe(self.path, self.output, self.project)

    def reject(self, message=None):
        self.write()
        with self.assertRaisesRegex((ValueError, FileNotFoundError), message or '.*'):
            tool.run_recipe(self.path, self.output, self.project)
        self.assertFalse(self.output.exists())

    def mutate_receipt(self, operation):
        path = self.base/'parent-execution.json'
        value = json.loads(path.read_text())
        operation(value['execution'])
        path.write_text(json.dumps(value))
        self.recipe['parent_execution_receipt'] = self.fixture.bind(path)

    def test_real_six8x8_RLE_and_exact_parent_RGBA_crop_and_receipt(self):
        receipt = self.run_real()
        self.assertEqual(set(receipt['execution']), {'status', 'method', 'recipe_sha256', 'tool_sha256',
                         'source_sha256', 'parent_raw_sha256', 'output_sha256'})
        self.assertEqual(receipt, json.loads((self.output/'execution-receipt.json').read_text()))
        self.assertEqual(len(list(self.output.glob('*.png'))), 6)
        for i, frame in enumerate(self.recipe['frames']):
            actual = np.asarray(Image.open(self.output/(frame['asset']+'.png')))
            parent = np.asarray(Image.open(self.parent_output/(frame['parent_asset']+'.png')))
            self.assertEqual(actual.shape, (32, 32, 4))
            self.assertTrue(np.array_equal(actual, parent[0:32, 20:52]))
            source = self.fixture.sources[i][0:8, 5:13]
            s4 = parent_fixture_module.tool.scale2(parent_fixture_module.tool.scale2(source))
            self.assertTrue(np.array_equal(actual[:, :, 3], np.where(s4 < 256, 255, 0)))
            self.assertTrue(np.array_equal(actual[12:16, 12:16, :3], self.fixture.palette[s4[12:16, 12:16]]))

    def test_portable_replay_byte_identical(self):
        first = self.run_real()
        self.output = self.root/'replay'
        second = self.run_real()
        self.assertEqual(first['execution'], second['execution'])

    def test_one_child_Source_index_difference_rejected_before_output(self):
        source = self.fixture.sources[5][0:8, 5:13].copy()
        source[0, 0] = 16
        path = self.base/(tool.ASSETS[5]+'.bin')
        path.write_bytes(parent_fixture_module.rle(source))
        self.recipe['frames'][5]['source'] = self.fixture.bind(path)
        self.reject('entire64-index')

    def test_missing_or_reordered_child_rejected(self):
        self.recipe['frames'].reverse()
        self.reject('complete ordered')

    def test_actual_missing_child_rejected(self):
        self.recipe['frames'].pop()
        self.reject('complete ordered')

    def test_child_wrong8x8_canvas_rejected(self):
        source = self.fixture.sources[5][0:8, 5:12].copy()
        path = self.base/(tool.ASSETS[5]+'.bin')
        path.write_bytes(parent_fixture_module.rle(source))
        self.recipe['frames'][5]['source'] = self.fixture.bind(path)
        self.reject('child8x8')

    def test_parent_wrong_atlas_layout_rejected(self):
        raw = self.base/'raw.png'
        im = Image.open(raw)
        im.crop((0, 0, 1536, 1023)).save(raw)
        self.fixture.recipe['raw_png'] = self.fixture.bind(raw)
        self.fixture.write()
        self.recipe['parent_recipe'] = self.fixture.bind(self.fixture.path)
        self.reject('exact parent atlas layout')

    def test_parent_phase_swap_rejected(self):
        self.recipe['frames'][5]['parent_asset'] = '200ec'
        self.reject('fixed corresponding')

    def test_unknown_crop_or_transform_rejected(self):
        self.recipe['crop'] = [19, 0, 32, 32]
        self.reject('exact fields')

    def test_extra_Original_cells_rejected(self):
        self.recipe['frames'][5]['functional_original_cells'] = [[3, 3], [2, 2]]
        self.reject('fixed corresponding')

    def test_child_source_hash_mismatch_rejected(self):
        self.recipe['frames'][5]['source']['sha256'] = '0'*64
        self.reject('hash mismatch')

    def test_parent_tool_hash_mismatch_rejected_without_execution(self):
        (self.project/'tools/hd_infantry_cleanup.py').write_text('raise RuntimeError("must not execute")')
        self.reject('parent helper hash mismatch')

    def test_parent_receipt_recipe_hash_mismatch(self):
        self.mutate_receipt(lambda x: x.update(recipe_sha256='0'*64))
        self.reject('parent execution provenance')

    def test_parent_receipt_raw_hash_mismatch(self):
        self.mutate_receipt(lambda x: x.update(parent_raw_sha256=['0'*64]))
        self.reject('parent execution provenance')

    def test_parent_receipt_Source_map_mismatch(self):
        self.mutate_receipt(lambda x: x.update(source_sha256={}))
        self.reject('parent source provenance')

    def test_parent_PNG_provenance_mismatch_after_render_emits_no_child(self):
        self.mutate_receipt(lambda x: x['output_sha256'].update({'200f1': '0'*64}))
        self.reject('parent PNG not exactly reproduced')

    def test_traversal_absolute_and_symlink_inputs_rejected(self):
        original = self.recipe['parent_recipe']['path']
        for bad in ['../recipe.json', '/recipe.json', 'x/../recipe.json', 'C:/recipe.json']:
            self.recipe['parent_recipe']['path'] = bad
            self.reject('path')
        self.recipe['parent_recipe']['path'] = original
        link = self.base/'link.json'
        link.symlink_to(self.fixture.path)
        self.recipe['parent_recipe']['path'] = 'link.json'
        self.reject('symlink')

    def test_existing_child_output_not_overwritten(self):
        self.output.mkdir()
        (self.output/'sentinel').write_text('keep')
        self.write()
        with self.assertRaisesRegex(ValueError, 'fresh nonsymlink'):
            tool.run_recipe(self.path, self.output, self.project)
        self.assertEqual((self.output/'sentinel').read_text(), 'keep')

    @unittest.skipUnless(hasattr(os, 'mkfifo'), 'POSIX FIFO negative')
    def test_parent_bootstrap_FIFO_rejected_promptly_without_hash_read(self):
        path = self.project/'tools/hd_infantry_cleanup.py'
        path.unlink()
        os.mkfifo(path)
        self.write()
        completed = subprocess.run([sys.executable, str(HERE/'hd_person01_cleanup.py'),
            str(self.path), str(self.output), '--project-root', str(self.project)],
            capture_output=True, text=True, timeout=3)
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn('regular bounded parent dependency', completed.stderr)
        self.assertFalse(self.output.exists())

    def test_parent_bootstrap_directory_rejected_without_execution(self):
        path = self.project/'tools/hd_infantry_cleanup.py'
        path.unlink()
        path.mkdir()
        self.reject('regular bounded parent dependency')

    def test_parent_dependency_consumed_from_verified_buffer(self):
        original = tool.bootstrap_regular_bytes
        def mutate_after_read(path):
            data = original(path)
            path.write_text('raise RuntimeError("path reopened")')
            return data
        with patch.object(tool, 'bootstrap_regular_bytes', mutate_after_read):
            receipt = self.run_real()
        self.assertEqual(receipt['execution']['status'], 'success')


if __name__ == '__main__':
    unittest.main()
