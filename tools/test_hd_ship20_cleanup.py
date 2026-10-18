"""Synthetic dispatcher/portable-lineage tests; no real assets or engine calls."""
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
spec = importlib.util.spec_from_file_location("ship_cleanup", Path(__file__).with_name("hd_ship20_cleanup.py"))
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


class PortableShipDispatcherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.assets = c.ASSETS
        self.cells = dict(zip(self.assets, [[], [[14, 25]], [[25, 19]], [[36, 23]]]))
        y, x = np.indices((224, 192))
        rgba = np.empty((224, 192, 4), np.uint8)
        rgba[:, :, :3] = np.stack([(x * 3 + y) % 256, (x + y * 5) % 256,
                                  (x * 7 + y * 11) % 256], axis=-1)
        rgba[:, :, 3] = 255
        Image.fromarray(rgba).save(self.root / "parent.png")
        self.palette_bytes = bytes((np.arange(768) % 64).astype(np.uint8))
        (self.root / "palette").write_bytes(self.palette_bytes)
        frames = []
        for asset in self.assets:
            source = np.full((56, 48), 10, np.uint16)
            for xx, yy in self.cells[asset]:
                source[yy, xx] = 82
            payload = bytearray(struct.pack("<5i", 0, 1, 31, 48, 56))
            for yy in range(56):
                payload.extend(struct.pack("<4i", 0, yy, yy * 48, 48))
                payload.extend(bytes(source[yy].tolist()))
            payload.extend(struct.pack("<4i", 0, 0, -1, 0))
            (self.root / asset).write_bytes(payload)
            frames.append(dict(asset=asset, source=self.bind(asset), raw_png=self.bind("parent.png"),
                               viewport=[0, 0, 192, 224], sampling_offset_native=[0, 0], origin=[0, 0]))
        self.geometry = dict(format_version=1, output_scale=4, max_fill_distance_pixels=12,
                             shared_backing_anchor=1, palette=self.bind("palette"), frames=frames)
        # Independent sequential reference: published geometry stage, then the
        # unchanged pure Original stage; PNG compression matches the actual CLI.
        arrays, _ = c.functional.base.render_family(self.geometry, self.root)
        self.reference = {}
        for f, array in zip(frames, arrays):
            _, sb = c.functional.base.checked(f["source"], self.root)
            w, h, indices = c.functional.base._indices(sb)
            if self.cells[f["asset"]]:
                p6 = np.frombuffer(self.palette_bytes, np.uint8).reshape(256, 3).astype(np.uint16)
                palette = ((p6 << 2) | (p6 >> 4)).astype(np.uint8)
                array, _ = c.functional.retain_functional_original(
                    array, np.asarray(indices, np.uint16).reshape(h, w), palette, self.cells[f["asset"]])
            buffer = io.BytesIO()
            Image.fromarray(array).save(buffer, format="PNG", compress_level=9)
            self.reference[f["asset"]] = buffer.getvalue()
        self.recipe = dict(format_version=1, method=c.METHOD, geometry_recipe=self.geometry,
                           functional_original_cells=self.cells,
                           expected_output_sha256={a: c.digest(b) for a, b in self.reference.items()})

    def bind(self, name):
        return dict(path=name, sha256=hashlib.sha256((self.root / name).read_bytes()).hexdigest())

    def recipe_path(self, recipe=None):
        path = self.root / "recipe.json"
        path.write_text(json.dumps(self.recipe if recipe is None else recipe))
        return path

    def test_relative_recipe_from_other_cwd_reproduces_sequential_bytes_and_receipt(self):
        rp = self.recipe_path()
        before = {p: p.read_bytes() for p in self.root.iterdir()}
        old_cwd = Path.cwd()
        try:
            os.chdir("/")
            report = c.run_recipe(rp, self.root / "actual")
        finally:
            os.chdir(old_cwd)
        for asset, expected in self.reference.items():
            self.assertEqual((self.root / "actual" / (asset + "-derived.png")).read_bytes(), expected)
        self.assertEqual(report["execution"]["tool_sha256"], c.digest(Path(c.__file__).read_bytes()))
        self.assertEqual(report["execution"]["parent_raw_sha256"], [self.bind("parent.png")["sha256"]])
        self.assertEqual(report["actual_geometry_renderer_calls"], 1)
        self.assertEqual(report["actual_pure_retention_calls"], 3)
        self.assertEqual(report["frames"][0]["functional_Original"]["actual_Original_Scale4_RGBA_samples"], 0)
        self.assertIn("pillow_version", report)
        self.assertIn("numpy_version", report)
        for p, value in before.items():
            self.assertEqual(p.read_bytes(), value)
        with self.assertRaisesRegex(ValueError, "fresh absent"):
            c.run_recipe(rp, self.root / "actual")

    def test_wrong_expected_png_rejected_before_output_mkdir(self):
        r = copy.deepcopy(self.recipe)
        r["expected_output_sha256"]["200c7"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "reviewed PNG not reproduced"):
            c.run_recipe(self.recipe_path(r), self.root / "absent")
        self.assertFalse((self.root / "absent").exists())

    def test_wrong_order_duplicate_bool_unpainted_and_unsorted_cells_reject(self):
        cases = []
        r = copy.deepcopy(self.recipe)
        r["geometry_recipe"]["frames"].reverse()
        cases.append(r)
        for cells in ([[14, 25], [14, 25]], [[True, 25]], [[0, 0]], [[14, 26], [14, 25]]):
            r = copy.deepcopy(self.recipe)
            r["functional_original_cells"]["200c5"] = cells
            cases.append(r)
        for r in cases:
            with self.subTest(recipe=r), self.assertRaises(ValueError):
                c.run_recipe(self.recipe_path(r), self.root / "absent")
            self.assertFalse((self.root / "absent").exists())

    def test_corrupt_declared_input_or_dependency_rejects_before_output(self):
        r = copy.deepcopy(self.recipe)
        r["geometry_recipe"]["frames"][0]["raw_png"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            c.run_recipe(self.recipe_path(r), self.root / "absent")
        with patch.object(c, "FUNCTIONAL_SHA", "0" * 64), self.assertRaisesRegex(ValueError, "implementation changed"):
            c.run_recipe(self.recipe_path(), self.root / "absent")
        self.assertFalse((self.root / "absent").exists())

    def test_retention_cannot_change_alpha(self):
        original = c.functional.retain_functional_original
        def wrong_alpha(*args):
            out, report = original(*args)
            out[0, 0, 3] = 0
            return out, report
        with patch.object(c.functional, "retain_functional_original", wrong_alpha), self.assertRaisesRegex(ValueError, "alpha"):
            c.run_recipe(self.recipe_path(), self.root / "absent")
        self.assertFalse((self.root / "absent").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
