import copy
from fractions import Fraction
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

from PIL import Image

PROJECT = Path(__file__).resolve().parents[1]
Q = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT / 'tools'))
import hd_frame_policy as policy
import hd_art_audit as audit
import hd_candidate_review as candidate
import hd_register_reviewed as registration
from grid_sampler_reference import axis_weights, sample_fractional

def frame(columns=2, rows=2, column=0, row=0, size=(1, 1)):
    return dict(frame=0, file='synthetic.png', logical_width=size[0], logical_height=size[1],
                origin=[0, 0], source_sha256='0' * 64,
                atlas_grid=dict(columns=columns, rows=rows, column=column, row=row))

class Geometry(unittest.TestCase):
    def test_exact_fractional_extents(self):
        item = frame(4, 2, 3, 1, (32, 32))
        result = policy.atlas_grid_geometry(item, 1774, 887)
        self.assertEqual(result['bounds'], (Fraction(2661, 2), Fraction(887, 2), Fraction(1774), Fraction(887)))
        self.assertEqual(result['pixels'], (1330, 443, 1774, 887))
        self.assertEqual(result['resident'], (128, 128))

    def test_no_strip_gaps_or_omissions(self):
        for count in range(1, 17):
            extent = count * 5 + 1
            spans = [policy.atlas_grid_geometry(frame(count, count, cell, 0), extent, extent)['bounds'] for cell in range(count)]
            self.assertEqual(spans[0][0], 0)
            self.assertEqual(spans[-1][2], extent)
            self.assertTrue(all(left[2] == right[0] for left, right in zip(spans, spans[1:])))
            self.assertTrue(all(span[2] - span[0] == Fraction(extent, count) for span in spans))

    def test_last_cell_bounds_never_exceed_atlas(self):
        for cols, rows, width, height in [(2, 2, 5, 5), (4, 2, 1774, 887), (7, 7, 31, 31), (1, 1, 9, 9)]:
            g = policy.atlas_grid_geometry(frame(cols, rows, cols-1, rows-1), width, height)
            self.assertEqual(g['pixels'][2:], (width, height))
            for output in [1, 2, 4, 16]:
                for weights in axis_weights(g['bounds'][0], g['bounds'][2], output):
                    self.assertTrue(all(g['pixels'][0] <= index < width for index, _ in weights))

    def test_resolution_is_common_bounded_factor(self):
        self.assertEqual(policy.atlas_grid_geometry(frame(), 5, 5)['resident'], (2, 2))
        self.assertEqual(policy.atlas_grid_geometry(frame(), 7, 7)['resident'], (3, 3))
        self.assertEqual(policy.atlas_grid_geometry(frame(), 13, 13)['resident'], (4, 4))

    def test_non_square_logical_aspect(self):
        self.assertEqual(policy.atlas_grid_geometry(frame(2, 2, size=(2, 1)), 10, 5)['resident'], (4, 2))

    def test_odd_grid_size_does_not_mutate_frame(self):
        item = frame(4, 2, 1, 0, (32, 32)); old = copy.deepcopy(item)
        policy.atlas_grid_geometry(item, 1774, 887)
        self.assertEqual(item, old)

    def test_grid_and_crop_are_mutually_exclusive(self):
        item = frame(); item['crop'] = [0, 0, 2, 2]
        with self.assertRaises(ValueError): policy.validate_frame_policy(item)

    def test_absent_grid_is_noop_and_adds_no_default_key(self):
        item = frame(); item.pop('atlas_grid'); old = copy.deepcopy(item)
        policy.validate_frame_policy(item)
        self.assertIsNone(policy.atlas_grid_geometry(item, 5, 4))
        self.assertEqual(item, old)
        self.assertNotIn('atlas_grid', item)

    def test_null_grid_is_noop_without_adding_or_removing_keys(self):
        item = frame(); item['atlas_grid'] = None; old = copy.deepcopy(item)
        self.assertIsNone(policy.validate_atlas_grid(item)); self.assertEqual(item, old)

    def test_invalid_typed_grid_fields(self):
        for field, value in [('columns', 0), ('rows', 0), ('columns', -1), ('rows', 2**32),
                             ('column', True), ('row', 0.0), ('columns', '2'), ('column', 2), ('row', 2)]:
            with self.subTest(field=field, value=value):
                item = frame(); item['atlas_grid'][field] = value
                with self.assertRaises(ValueError): policy.validate_frame_policy(item)

    def test_grid_cell_budget_and_unknown_fields(self):
        for grid in [{}, [], 7, dict(columns=129, rows=129, column=0, row=0),
                     dict(columns=2, rows=2, column=0, row=0, extra=1)]:
            item = frame(); item['atlas_grid'] = grid
            with self.assertRaises(ValueError): policy.validate_frame_policy(item)

    def test_bad_aspect_resolution_and_dimensions(self):
        for size in [(5, 6), (3, 3), (0, 5), (5, 0), (-1, 5), (True, 5)]:
            with self.subTest(size=size):
                with self.assertRaises(ValueError): policy.atlas_grid_geometry(frame(), *size)

class Sampler(unittest.TestCase):
    def test_constant_rgba_preserved(self):
        g = policy.atlas_grid_geometry(frame(), 5, 5)
        pixels = [[(40, 80, 120, 255)] * 5 for _ in range(5)]
        self.assertEqual(sample_fractional(pixels, g), [[(40, 80, 120, 255)] * 2 for _ in range(2)])

    def test_half_boundary_pixel_participates_on_both_sides(self):
        for start, end in [(Fraction(0), Fraction(5, 2)), (Fraction(5, 2), Fraction(5))]:
            weights = axis_weights(start, end, 2)
            self.assertTrue(any(index == 2 and weight != 0 for row in weights for index, weight in row))

    def test_no_neighbor_pixel_bleed(self):
        pixels = [[(255, 0, 0, 255), (255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255), (0, 0, 255, 255)] for _ in range(5)]
        left = sample_fractional(pixels, policy.atlas_grid_geometry(frame(), 5, 5))
        right = sample_fractional(pixels, policy.atlas_grid_geometry(frame(column=1), 5, 5))
        self.assertTrue(all(pixel[2] == 0 for row in left for pixel in row))
        self.assertTrue(all(pixel[0] == 0 for row in right for pixel in row))

    def test_alpha_is_sampled_as_raw_channel(self):
        pixels = [[(0, 0, 0, 1)] * 5 for _ in range(5)]
        self.assertTrue(all(pixel[3] == 1 for row in sample_fractional(pixels, policy.atlas_grid_geometry(frame(), 5, 5)) for pixel in row))

    def test_weight_normalization(self):
        for extent, output in [(Fraction(5, 2), 2), (Fraction(887, 2), 128), (Fraction(31, 7), 4)]:
            for weights in axis_weights(0, extent, output):
                self.assertAlmostEqual(sum(value for _, value in weights), 1, places=6)

class Consumers(unittest.TestCase):
    def test_candidate_retains_grid_and_source_identity(self):
        item = frame(); proposal = dict(sequences=[dict(name='Synthetic', base_asset=1, frame_count=1, frames=[item])])
        rows = candidate.proposal_frames(proposal)
        self.assertEqual(rows['00001']['atlas_grid'], item['atlas_grid'])
        changed = copy.deepcopy(rows); changed['00001']['atlas_grid']['column'] = 1
        self.assertNotEqual(candidate.binding_digest(rows), candidate.binding_digest(changed))
        self.assertEqual(candidate.binding_digest(rows), candidate.binding_digest(candidate.proposal_frames(proposal)))

    def test_registration_typed_identity_cannot_ignore_grid_changes(self):
        original = frame()
        changed = copy.deepcopy(original); changed['atlas_grid']['row'] = 1
        self.assertFalse(registration.same_json(original, changed))
        changed = copy.deepcopy(original); changed['atlas_grid']['row'] = False
        self.assertFalse(registration.same_json(original, changed))
        self.assertTrue(registration.same_json(original, copy.deepcopy(original)))

    def test_grid_policy_does_not_silently_drop_unknown_metadata(self):
        original = frame(); original['atlas_grid']['automatic_fit'] = True
        with self.assertRaises(ValueError): policy.validate_frame_policy(original)
        original = frame(); original['crop'] = [0, 0, 2, 2]
        with self.assertRaises(ValueError): candidate.proposal_frames(dict(sequences=[
            dict(name='Synthetic', base_asset=1, frame_count=1, frames=[original])]))

    def test_candidate_targets_must_bind_same_grid(self):
        item = frame(); target = copy.deepcopy(item); target['asset'] = '00001'; target['atlas_grid']['column'] = 1
        proposal = dict(targets=[target], sequences=[dict(name='Synthetic', base_asset=1, frame_count=1, frames=[item])])
        with self.assertRaises(ValueError): candidate.proposal_frames(proposal)

    def test_audit_rejects_bad_grid_and_accepts_fractional_without_modifying_png(self):
        payload = struct.pack('<5i', 1, 0, 0, 1, 1) + b'\x01'
        picture = Image.new('RGBA', (1, 1), (1, 1, 1, 255))
        with tempfile.TemporaryDirectory(prefix='synthetic-', dir=Q) as directory:
            root = Path(directory); path = root / 'synthetic.png'
            Image.new('RGBA', (5, 5), (30, 50, 70, 255)).save(path)
            previous = path.read_bytes(); item = frame(); item['source_sha256'] = hashlib.sha256(payload).hexdigest()
            self.assertEqual(audit.validate_hd_frame(root, item, payload, picture), 16)
            self.assertEqual(path.read_bytes(), previous)
            item['crop'] = [0, 0, 2, 2]
            with self.assertRaises(ValueError): audit.validate_hd_frame(root, item, payload, picture)

    def test_audit_transparent_original_needs_raw_transparency(self):
        payload = struct.pack('<5i', 1, 0, 0, 1, 1) + b'\x01'
        picture = Image.new('RGBA', (1, 1), (0, 0, 0, 0))
        with tempfile.TemporaryDirectory(prefix='synthetic-', dir=Q) as directory:
            root = Path(directory); path = root / 'synthetic.png'
            Image.new('RGBA', (5, 5), (30, 50, 70, 255)).save(path)
            item = frame(); item['source_sha256'] = hashlib.sha256(payload).hexdigest()
            with self.assertRaises(ValueError): audit.validate_hd_frame(root, item, payload, picture)

if __name__ == '__main__':
    unittest.main(verbosity=2)
