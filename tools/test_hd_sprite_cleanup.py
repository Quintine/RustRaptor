"""Synthetic proofs for derived alpha/material/static-animation cleanup."""
import copy
import io
import json
import struct
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image
import hd_frame_policy

from hd_sprite_cleanup import digest, palette_rgb, render_family, run_recipe, viewport_numbers


class SpriteCleanupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        palette = bytearray(768)
        for index, rgb in {1: [3, 3, 3], 2: [20, 10, 6], 3: [40, 30, 20], 4: [0, 0, 12]}.items():
            palette[index*3:index*3+3] = bytes(rgb)
        self.palette = self.put("palette", bytes(palette))

    def put(self, name, data):
        path = self.root / name
        path.write_bytes(data)
        return {"path": str(path), "sha256": digest(data)}

    def source(self, name, values):
        values = np.array(values)
        height, width = values.shape
        data = bytearray(struct.pack("<iiiii", 0, 0, 0, width, height))
        for y in range(height):
            for x in range(width):
                if values[y, x] != 256:
                    data += struct.pack("<iiii", x, y, y*width+x, 1)
                    data.append(int(values[y, x]))
        data += struct.pack("<iiii", 0, 0, -1, 0)
        return self.put(name, bytes(data))

    def frame(self, asset, source, seed=7):
        rgb = np.random.default_rng(seed).integers(20, 230, (32, 32, 4), dtype=np.uint8)
        rgb[:, :, 3] = 255
        buffer = io.BytesIO()
        Image.fromarray(rgb).save(buffer, format="PNG")
        return dict(asset=asset, source=source, raw_png=self.put(f"raw{seed}.png", buffer.getvalue()),
                    viewport=[0, 0, 32, 32], origin=[0, 0])

    def recipe(self, frames):
        return dict(format_version=1, palette=self.palette, output_scale=8, frames=frames)

    def test_alpha_is_exact_source_geometry_not_generated_opaque_background(self):
        frame = self.frame("a", self.source("a.pic", [[1, 256], [2, 3]]))
        images, report = render_family(self.recipe([frame]), self.root)
        expected = np.repeat(np.repeat(np.array([[255, 0], [255, 255]], dtype=np.uint8), 8, 0), 8, 1)
        np.testing.assert_array_equal(images[0][:, :, 3], expected)
        self.assertTrue(np.all(images[0][:8, 8:] == 0))
        self.assertGreater(report["frames"][0]["nonzero_generated_detail_pixels"], 0)

    def test_static_backing_exact_despite_different_generated_texture_and_animated_cell_survives(self):
        frames = [self.frame("a", self.source("a.pic", [[1, 2], [256, 3]]), 7),
                  self.frame("b", self.source("b.pic", [[1, 4], [256, 3]]), 8)]
        images, report = render_family(self.recipe(frames), self.root)
        self.assertEqual(report["Source_identical_shared_cells"], 2)
        np.testing.assert_array_equal(images[0][:8, :8], images[1][:8, :8])
        np.testing.assert_array_equal(images[0][8:, 8:], images[1][8:, 8:])
        self.assertFalse(np.array_equal(images[0][:8, 8:, :3], images[1][:8, 8:, :3]))
        palette = palette_rgb((self.root / "palette").read_bytes())
        for image, value in zip(images, [2, 4]):
            self.assertLess(np.max(np.abs(image[:8, 8:, :3].mean(axis=(0, 1))-palette[value])), 1.0)

    def test_deterministic_pngs_and_RGBA_receipts_without_input_mutation(self):
        recipe = self.recipe([self.frame("a", self.source("a.pic", [[1, 2], [256, 3]]))])
        path = self.root / "recipe.json"
        path.write_text(json.dumps(recipe))
        before = {p: p.read_bytes() for p in self.root.iterdir() if p.is_file()}
        first = run_recipe(path, self.root / "first")
        second = run_recipe(path, self.root / "second")
        self.assertEqual((self.root / "first/a-derived.png").read_bytes(), (self.root / "second/a-derived.png").read_bytes())
        self.assertEqual(first, second)
        pixels = np.asarray(Image.open(self.root / "first/a-derived.png"))
        self.assertEqual(first["frames"][0]["output"]["RGBA_sha256"], digest(pixels.tobytes()))
        self.assertEqual(first["output_class"], "DERIVED_SCRIPTED_CLEANUP_NOT_UNTOUCHED_GENERATION")
        self.assertEqual(first["decoder_module"]["sha256"], digest(Path(hd_frame_policy.__file__).read_bytes()))
        execution = first["execution"]
        self.assertEqual(execution["status"], "success")
        self.assertEqual(execution["output_sha256"]["a"], digest((self.root / "first/a-derived.png").read_bytes()))
        self.assertEqual(execution["source_sha256"], {"a": recipe["frames"][0]["source"]["sha256"]})
        self.assertEqual(execution["parent_raw_sha256"], [recipe["frames"][0]["raw_png"]["sha256"]])
        for file, blob in before.items():
            self.assertEqual(file.read_bytes(), blob)
        with self.assertRaisesRegex(ValueError, "already exists"):
            run_recipe(path, self.root / "first")

    def test_hash_mismatch_stops_before_output_write(self):
        frame = self.frame("a", self.source("a.pic", [[1, 2], [256, 3]]))
        frame["raw_png"]["sha256"] = "0" * 64
        path = self.root / "recipe.json"
        path.write_text(json.dumps(self.recipe([frame])))
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            run_recipe(path, self.root / "output")
        self.assertFalse((self.root / "output").exists())

    def test_fractional_viewport_and_bounds(self):
        self.assertEqual(str(viewport_numbers(["1/2", 0, "63/2", 32], [32, 32])[0]), "1/2")
        for viewport in [[0, 0, 0, 2], [-1, 0, 2, 2], [0, 0, 33, 32]]:
            with self.assertRaisesRegex(ValueError, "viewport"):
                viewport_numbers(viewport, [32, 32])

    def test_invalid_scale_unknown_fields_and_mismatched_canvases(self):
        frame = self.frame("a", self.source("a.pic", [[1, 2], [256, 3]]))
        recipe = self.recipe([frame])
        for value in [3, 17, True]:
            broken = dict(recipe, output_scale=value)
            with self.assertRaisesRegex(ValueError, "output_scale"):
                render_family(broken, self.root)
        with self.assertRaisesRegex(ValueError, "unknown cleanup"):
            render_family(dict(recipe, guessed_mask=[]), self.root)
        other = self.frame("b", self.source("b.pic", [[1, 2, 3]]), 8)
        with self.assertRaisesRegex(ValueError, "consistent logical"):
            render_family(self.recipe([frame, other]), self.root)

    def test_donor_only_moves_texture_while_source_geometry_and_color_remain_authority(self):
        frame = self.frame("a", self.source("a.pic", [[1, 2], [256, 3]]))
        frame["detail_donors"] = [dict(target=[0, 0], source=[1, 0])]
        images, report = render_family(self.recipe([frame]), self.root)
        self.assertEqual(report["frames"][0]["detail_donor_cells"], 1)
        self.assertLess(np.max(np.abs(images[0][:8, :8, :3].mean(axis=(0, 1)) - [12, 12, 12])), 1)
        broken = copy.deepcopy(frame)
        broken["detail_donors"] = [dict(target=[0, 1], source=[1, 0])]
        with self.assertRaisesRegex(ValueError, "painted Original"):
            render_family(self.recipe([broken]), self.root)

    def test_constant_raw_cannot_be_relabelled_as_new_HD(self):
        frame = self.frame("a", self.source("a.pic", [[1, 2], [256, 3]]))
        image = Image.new("RGBA", (32, 32), (100, 100, 100, 255))
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        frame["raw_png"] = self.put("constant.png", buffer.getvalue())
        with self.assertRaisesRegex(ValueError, "no generated interior detail"):
            render_family(self.recipe([frame]), self.root)


if __name__ == "__main__":
    unittest.main()
