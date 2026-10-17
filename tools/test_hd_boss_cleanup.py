"""Small synthetic geometry/lineage checks; no game or generated artwork."""
import copy
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest

import numpy as np
from PIL import Image

import hd_boss_cleanup as cleanup


class BossCleanup(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cells = [[256, 10, 11, 256], [12, 13, 10, 12],
                      [256, 10, 256, 256], [10, 256, 256, 11]]
        source = bytearray(struct.pack("<5i", 0, 0, 0, 4, 4))
        for y, row in enumerate(self.cells):
            for x, value in enumerate(row):
                if value < 256:
                    source += struct.pack("<4i", x, y, y*4+x, 1) + bytes([value])
        source += struct.pack("<4i", 0, 0, -1, 0)
        (self.root / "Source").write_bytes(source)
        palette = bytearray(768)
        for i in range(10, 14):
            palette[i*3:i*3+3] = bytes([25, 25, 25])
        (self.root / "palette").write_bytes(palette)
        self.raw = np.zeros((16, 16, 4), dtype=np.uint8)
        for y in range(16):
            for x in range(16):
                self.raw[y, x] = [170 + ((x+y) % 3)*20, 30 + (x % 2)*30, 45 + (y % 3)*20, 255]
        self.save_raw()
        bind = lambda name: dict(path=name, sha256=cleanup.sha((self.root/name).read_bytes()))
        self.recipe = dict(format_version=1, asset="200a2", label="synthetic only",
                           source=bind("Source"), palette=bind("palette"), parent_raw=bind("raw.png"),
                           logical_canvas=[4, 4], origin=[0, 0], output_scale=4,
                           alignment=dict(raw_painted_bounds=[0, 0, 16, 16], source_painted_bounds=[0, 0, 4, 4]),
                           patches=[], gap_fill=dict(generated_donor=[0, 0, 5, 5], detail_gain=0.6))

    def save_raw(self):
        Image.fromarray(self.raw).save(self.root / "raw.png")

    def test_exact_source_outline_feet_and_generated_body_rgb(self):
        pixels, report = cleanup.render(self.recipe, self.root)
        expected = np.repeat(np.repeat(np.array(self.cells) < 256, 4, axis=0), 4, axis=1)
        self.assertTrue(np.array_equal(pixels[:, :, 3] == 255, expected))
        self.assertTrue(np.array_equal(pixels[expected, :3], self.raw[expected, :3]))
        self.assertTrue(np.all(pixels[~expected] == 0))
        self.assertEqual(np.nonzero(pixels[-1, :, 3])[0].tolist(), list(range(4)) + list(range(12, 16)))
        self.assertEqual(report["direct_generated_fraction_of_painted"], 1)
        self.assertGreater(report["internally_nonconstant_pixels"], 0)
        self.assertFalse(np.all(pixels[expected, 0] == 101), "must preserve generated body, not Source NN")

    def test_source_gap_is_opaque_and_explicit_generated_texture_patch_is_local(self):
        self.raw[4:8, 4:8, 3] = 0
        self.save_raw()
        self.recipe["parent_raw"]["sha256"] = cleanup.sha((self.root/"raw.png").read_bytes())
        self.recipe["patches"] = [dict(name="steel support", target=[1, 0, 2, 1],
                                        generated_donor=[0, 0, 5, 5], detail_gain=0.5)]
        pixels, report = cleanup.render(self.recipe, self.root)
        self.assertEqual(report["gap_filled_pixels"], 16)
        self.assertIn([1, 1], report["gap_filled_cells"])
        self.assertTrue(np.all(pixels[4:8, 4:8, 3] == 255))
        self.assertLess(float(abs(pixels[4:8, 4:8, :3].mean() - 101)), 5)
        self.assertEqual(report["patches"][0]["cells"], [[1, 0]])
        self.assertTrue(np.array_equal(pixels[4:8, 8:12, :3], self.raw[4:8, 8:12, :3]))
        self.assertTrue(np.all(pixels[:4, :4] == 0), "Source-empty neighbor stays empty")

    def test_input_identity_geometry_and_existing_output_fail_closed(self):
        for mutation in [lambda r: r["source"].update(sha256="0"*64),
                         lambda r: r.update(format_version=True),
                         lambda r: r.update(logical_canvas=[5, 4]),
                         lambda r: r.update(origin=[False, 0]),
                         lambda r: r.update(origin=[1, 0]),
                         lambda r: r["alignment"].update(source_painted_bounds=[0, 1, 4, 4]),
                         lambda r: r["gap_fill"].update(generated_donor=[0, 0, 17, 4])]:
            with self.subTest(mutation=mutation):
                bad = copy.deepcopy(self.recipe)
                mutation(bad)
                with self.assertRaises(ValueError):
                    cleanup.render(bad, self.root)
        recipe = self.root/"recipe.json"
        recipe.write_text(json.dumps(self.recipe))
        with self.assertRaises(ValueError):
            cleanup.run_recipe(recipe, self.root)

    def test_missing_generated_body_is_rejected_instead_of_source_fill_relabel(self):
        self.raw[:, :, 3] = 0
        self.raw[0:4, 4:8, 3] = 255
        self.save_raw()
        self.recipe["parent_raw"]["sha256"] = cleanup.sha((self.root/"raw.png").read_bytes())
        with self.assertRaisesRegex(ValueError, "most generated body is missing"):
            cleanup.render(self.recipe, self.root)

    def test_repeatable_derived_output_and_complete_execution_binding(self):
        recipe = self.root/"recipe.json"
        recipe.write_text(json.dumps(self.recipe, sort_keys=True))
        before = {n: (self.root/n).read_bytes() for n in ["Source", "palette", "raw.png"]}
        reports = [cleanup.run_recipe(recipe, self.root/f"derived-{i}") for i in range(2)]
        images = [(self.root/f"derived-{i}/200a2-derived.png").read_bytes() for i in range(2)]
        self.assertEqual(images[0], images[1])
        self.assertEqual(reports[0], reports[1])
        execution = reports[0]["execution"]
        self.assertEqual(execution["status"], "success")
        self.assertEqual(execution["method"], cleanup.METHOD)
        self.assertEqual(execution["recipe_sha256"], hashlib.sha256(recipe.read_bytes()).hexdigest())
        self.assertEqual(execution["tool_sha256"], hashlib.sha256(Path(cleanup.__file__).read_bytes()).hexdigest())
        self.assertEqual(execution["source_sha256"], {"200a2": self.recipe["source"]["sha256"]})
        self.assertEqual(execution["parent_raw_sha256"], [self.recipe["parent_raw"]["sha256"]])
        self.assertEqual(execution["output_sha256"], {"200a2": hashlib.sha256(images[0]).hexdigest()})
        self.assertEqual(before, {n: (self.root/n).read_bytes() for n in before})


if __name__ == "__main__":
    unittest.main()
