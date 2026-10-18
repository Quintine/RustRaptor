"""Synthetic RLE complete6 exercises actual buffered recipe and receipt path."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import struct
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('infantry_under_test', HERE/'hd_infantry_cleanup.py')
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)
R = HERE.parents[1] if HERE.parent.name == '.reference' else HERE.parent
if not (R/'tools/hd_frame_policy.py').exists():
    R = next(p for p in HERE.parents if (p/'tools/hd_frame_policy.py').exists())


def rle(source):
    height, width = source.shape
    result = bytearray(struct.pack('<5i', 0, 0, 0, width, height))
    for y in range(height):
        x = 0
        while x < width:
            if source[y, x] == 256:
                x += 1
                continue
            start = x
            while x < width and source[y, x] < 256:
                x += 1
            result.extend(struct.pack('<4i', start, y, y*width+start, x-start))
            result.extend(bytes(int(v) for v in source[y, start:x]))
    result.extend(struct.pack('<4i', 0, 0, -1, 0))
    return bytes(result)


class CompleteRecipeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.project = self.root/'project'
        (self.project/'tools').mkdir(parents=True)
        shutil.copyfile(R/'tools/hd_frame_policy.py', self.project/'tools/hd_frame_policy.py')
        self.base = self.root/'inputs'
        self.base.mkdir()
        palette = np.zeros((256, 3), np.uint8)
        palette[16], palette[17], palette[18] = [10, 23, 8], [48, 39, 33], [1, 1, 1]
        (self.base/'palette.bin').write_bytes(palette.tobytes())
        p8 = ((palette.astype(np.uint16) << 2) | (palette.astype(np.uint16) >> 4)).astype(np.uint8)
        raw = np.zeros((1024, 1536, 4), np.uint8)
        frames = []
        self.sources = []
        self.palette = p8
        positions = [(7, 2), (4, 8), (15, 7), (7, 15), (3, 19), (17, 18)]
        pattern = np.array([[16, 16, 17], [256, 17, 256], [16, 16, 18], [18, 256, 256]], np.uint16)
        for i, asset in enumerate(tool.ASSETS):
            source = np.full((24, 24), 256, np.uint16)
            components, faces = [], []
            for (name, _), (x, y) in zip(tool.WINDOWS, positions):
                source[y:y+4, x:x+3] = pattern
                l, t, rr, b = x*20+16, y*20+16, (x+3)*20+16, (y+4)*20+16
                block = np.repeat(np.repeat(pattern, 20, axis=0), 20, axis=1)
                visible = block < 256
                rgba = np.zeros((80, 60, 4), np.uint8)
                rgba[:, :, :3][visible] = p8[block[visible]]
                rgba[:, :, 3][visible] = 255
                # Genuine synthetic material variation, preserved byte-for-byte by donors.
                gy, gx = np.where(block == 16)
                rgba[gy, gx, 1] += (gx % 5).astype(np.uint8)
                raw[i//3*512+t:i//3*512+b, i%3*512+l:i%3*512+rr] = rgba
                components.append(dict(name=name, source_bbox=[x, y, x+3, y+4], raw_bbox=[l, t, rr, b]))
                faces.append([x+1, y+1])
            path = self.base/f'{asset}.bin'
            path.write_bytes(rle(source))
            self.sources.append(source)
            frames.append(dict(asset=asset, source=self.bind(path), components=components,
                               functional_original_cells=sorted(faces)))
        Image.fromarray(raw).save(self.base/'raw.png')
        self.recipe = dict(format_version=1, method=tool.METHOD, palette=self.bind(self.base/'palette.bin'),
                           raw_png=self.bind(self.base/'raw.png'), frames=frames)
        self.path = self.base/'recipe.json'
        self.output = self.root/'output'
        self.write()

    def tearDown(self):
        self.tmp.cleanup()

    def bind(self, path):
        return dict(path=path.name, sha256=tool.sha(path.read_bytes()))

    def write(self):
        self.path.write_text(json.dumps(self.recipe))

    def run_real(self):
        self.write()
        return tool.run_recipe(self.path, self.output, self.project)

    def reject(self):
        self.write()
        with self.assertRaises((ValueError, FileNotFoundError)):
            tool.run_recipe(self.path, self.output, self.project)
        self.assertFalse(self.output.exists())

    def test_real_RLE_six_outputs_and_unmocked_execution_receipt(self):
        receipt = self.run_real()
        self.assertEqual(set(receipt['execution']), {'status', 'method', 'recipe_sha256', 'tool_sha256',
                         'source_sha256', 'parent_raw_sha256', 'output_sha256'})
        self.assertEqual(receipt, json.loads((self.output/'execution-receipt.json').read_text()))
        self.assertEqual(len(list(self.output.glob('*.png'))), 6)
        self.assertEqual(receipt['execution']['recipe_sha256'], tool.sha(self.path.read_bytes()))
        for i, frame in enumerate(self.recipe['frames']):
            path = self.output/(frame['asset']+'.png')
            self.assertEqual(tool.sha(path.read_bytes()), receipt['execution']['output_sha256'][frame['asset']])
            a = np.asarray(Image.open(path))
            s4 = tool.scale2(tool.scale2(self.sources[i]))
            self.assertTrue(np.array_equal(a[:, :, 3], np.where(s4 < 256, 255, 0)))
            for x, y in frame['functional_original_cells']:
                self.assertTrue(np.array_equal(a[y*4:(y+1)*4, x*4:(x+1)*4, :3],
                    self.palette[s4[y*4:(y+1)*4, x*4:(x+1)*4]]))

    def test_replay_is_byte_identical(self):
        first = self.run_real()
        self.output = self.root/'second'
        second = self.run_real()
        self.assertEqual(first['execution'], second['execution'])

    def test_missing_last_frame_has_no_output(self):
        self.recipe['frames'].pop()
        self.reject()

    def test_duplicate_or_reordered_frame_has_no_output(self):
        self.recipe['frames'][5]['asset'] = '200ec'
        self.reject()

    def test_late_Source_hash_mismatch_has_no_output(self):
        self.recipe['frames'][5]['source']['sha256'] = '0'*64
        self.reject()

    def test_raw_hash_mismatch_has_no_output(self):
        self.recipe['raw_png']['sha256'] = '0'*64
        self.reject()

    def test_traversal_and_absolute_paths_rejected(self):
        for path in ['../raw.png', '/raw.png', 'x/../raw.png', 'x\\raw.png', 'C:/raw.png', './raw.png']:
            self.recipe['raw_png']['path'] = path
            self.reject()

    def test_symlink_parent_rejected(self):
        (self.base/'link').symlink_to(self.base, target_is_directory=True)
        self.recipe['raw_png']['path'] = 'link/raw.png'
        self.reject()

    def test_Source_bbox_cannot_move_or_enlarge(self):
        self.recipe['frames'][5]['components'][0]['source_bbox'][0] -= 1
        self.reject()

    def test_raw_body_cannot_include_another_body(self):
        self.recipe['frames'][5]['components'][0]['raw_bbox'] = [0, 0, 512, 512]
        self.reject()

    def test_wrong_face_or_extra_Original_selection_rejected(self):
        self.recipe['frames'][5]['functional_original_cells'].append([0, 0])
        self.reject()

    def test_no_user_caps_or_unknown_fields(self):
        self.recipe['caps'] = {'distance': 1000}
        self.reject()

    def test_missing_green_donors_rejects_complete_family(self):
        raw = np.asarray(Image.open(self.base/'raw.png')).copy()
        g = tool.materials(raw[:, :, :3]) == 1
        raw[g, :3] = [4, 4, 4]
        Image.fromarray(raw).save(self.base/'raw.png')
        self.recipe['raw_png'] = self.bind(self.base/'raw.png')
        self.reject()

    def test_existing_output_never_overwritten(self):
        self.output.mkdir()
        (self.output/'sentinel').write_text('keep')
        self.write()
        with self.assertRaises(ValueError):
            tool.run_recipe(self.path, self.output, self.project)
        self.assertEqual((self.output/'sentinel').read_text(), 'keep')

    def test_decoder_hash_mismatch_before_any_output(self):
        (self.project/'tools/hd_frame_policy.py').write_text('raise RuntimeError("must not execute")')
        self.reject()

    def test_decoder_consumes_verified_buffer_without_path_reopen(self):
        original = tool.checked
        def changed_after_verified_read(binding, root):
            result = original(binding, root)
            if binding['path'] == 'tools/hd_frame_policy.py':
                (self.project/'tools/hd_frame_policy.py').write_text('raise RuntimeError("reopened path")')
            return result
        with patch.object(tool, 'checked', changed_after_verified_read):
            receipt = self.run_real()
        self.assertTrue(receipt['dependencies_consumed_from_verified_buffers'])
        self.assertEqual(receipt['execution']['status'], 'success')

    def test_raw_decode_consumes_verified_buffer_without_reopen(self):
        original = tool.checked
        def changed_after_verified_read(binding, root):
            result = original(binding, root)
            if binding['path'] == 'raw.png':
                (self.base/'raw.png').write_bytes(b'not a PNG')
            return result
        with patch.object(tool, 'checked', changed_after_verified_read):
            receipt = self.run_real()
        self.assertEqual(receipt['execution']['status'], 'success')

    def test_fixed_missing_fraction_cap_rejects_without_Original_fallback(self):
        raw = np.asarray(Image.open(self.base/'raw.png')).copy()
        c = self.recipe['frames'][5]['components'][0]
        l, t, r, b = c['raw_bbox']
        # Leave a small genuine green donor region, so absence of donors cannot
        # be the rejection reason. Most projected green samples become black.
        block = raw[512+t:512+b, 1024+l:1024+r]
        green = tool.materials(block[:, :, :3]) == 1
        yy, xx = np.where(green)
        block[yy[1:], xx[1:], :3] = [4, 4, 4]
        Image.fromarray(raw).save(self.base/'raw.png')
        self.recipe['raw_png'] = self.bind(self.base/'raw.png')
        self.write()
        with self.assertRaisesRegex(ValueError, 'fixed missing fraction exceeded'):
            tool.run_recipe(self.path, self.output, self.project)
        self.assertFalse(self.output.exists())

    def test_fixed_distance_cap_rejects_even_when_missing_fraction_is_small(self):
        raw = np.asarray(Image.open(self.base/'raw.png')).copy()
        l, t, r, b = self.recipe['frames'][5]['components'][0]['raw_bbox']
        # One of four green logical cells is blackened. Other genuine green
        # donors remain, but the deep corner is over the fixed .65-cell cap.
        raw[512+t:512+t+20, 1024+l:1024+l+20, :3] = [4, 4, 4]
        Image.fromarray(raw).save(self.base/'raw.png')
        self.recipe['raw_png'] = self.bind(self.base/'raw.png')
        self.write()
        with self.assertRaisesRegex(ValueError, 'fixed donor distance exceeded'):
            tool.run_recipe(self.path, self.output, self.project)
        self.assertFalse(self.output.exists())

    def test_scale2_preserves_label_identity_and_transparent_sentinel(self):
        source = np.array([[1, 256, 2], [256, 256, 256], [3, 256, 4]], np.uint16)
        output = tool.scale2(tool.scale2(source))
        self.assertEqual(output.shape, (12, 12))
        self.assertEqual(set(np.unique(output)), {1, 2, 3, 4, 256})
        self.assertEqual(int(output[0, 0]), 1)
        self.assertEqual(int(output[-1, -1]), 4)

    def test_Source_RLE_truncation_rejected(self):
        source = self.base/'200f1.bin'
        source.write_bytes(source.read_bytes()[:-8])
        self.recipe['frames'][5]['source'] = self.bind(source)
        self.reject()


if __name__ == '__main__':
    unittest.main()
