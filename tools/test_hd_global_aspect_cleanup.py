import hashlib
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw
import hd_global_aspect_cleanup as cleanup


def encode(image):
    b = io.BytesIO(); image.save(b, format="PNG"); return b.getvalue()


class GlobalAspectCleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def ink(self):
        image = Image.new("RGBA", (34, 16))
        draw = ImageDraw.Draw(image)
        # Countered glyph, detached dot and comma, ring touching both crop edges.
        draw.rectangle((2, 5, 5, 10), fill=(20, 20, 20, 255))
        draw.rectangle((3, 6, 4, 9), fill=(0, 0, 0, 0))
        draw.point((8, 10), fill=(24, 24, 24, 255))
        draw.line((10, 10, 10, 11), fill=(18, 18, 18, 255))
        draw.ellipse((15, 4, 22, 11), outline=(24, 24, 24, 255))
        return image

    def test_only_global_crop_and_refit_retains_counter_dot_comma_and_ring(self):
        parent = self.ink()
        output, report = cleanup.global_crop_refit(encode(parent), [0, 4, 34, 8], [68, 16], 0)
        actual = Image.open(io.BytesIO(output)).convert("RGBA")
        self.assertEqual(actual.size, (68, 16))
        self.assertEqual(actual.tobytes(), parent.crop((0, 4, 34, 12)).resize((68, 16), Image.Resampling.LANCZOS).tobytes())
        self.assertLess(actual.getpixel((7, 7))[3], 16)  # counter remains below ink cutoff
        self.assertGreater(actual.getpixel((16, 12))[3], 128)  # separate full stop
        self.assertGreater(actual.getpixel((20, 14))[3], 128)  # descending comma
        self.assertTrue(report["all_alpha16_ink_retained"])

    def test_occupied_ink_outside_window_rejected(self):
        parent = self.ink(); parent.putpixel((2, 0), (22, 22, 22, 16))
        with self.assertRaisesRegex(ValueError, "occupied alpha>=16"):
            cleanup.global_crop_refit(encode(parent), [0, 4, 34, 8], [68, 16], 0)

    def test_low_alpha_noise_is_exactly_declared_not_silently_removed(self):
        parent = self.ink(); parent.putpixel((2, 0), (22, 22, 22, 15))
        with self.assertRaisesRegex(ValueError, "noise count differs"):
            cleanup.global_crop_refit(encode(parent), [0, 4, 34, 8], [68, 16], 0)
        _, r = cleanup.global_crop_refit(encode(parent), [0, 4, 34, 8], [68, 16], 1)
        self.assertEqual(r["omitted_alpha1_to15_samples"], 1)

    def test_no_genuine_RGB_tone_gain_or_Source_reinsertion_when_size_unchanged(self):
        parent = self.ink(); parent.putpixel((2, 5), (14, 19, 23, 255))
        out, _ = cleanup.global_crop_refit(encode(parent), [0, 4, 34, 8], [34, 8], 0)
        self.assertEqual(Image.open(io.BytesIO(out)).getpixel((2, 1)), (14, 19, 23, 255))

    def test_invalid_bounds_boolean_dimensions_and_output_limit_rejected(self):
        raw = encode(self.ink())
        for window, size in [([0, 4, 35, 8], [68, 16]), ([True, 4, 34, 8], [68, 16]),
                             ([0, 4, 34, 8], [4097, 16]), ([0, 4, 34, 8], [68, 0])]:
            with self.assertRaises(ValueError): cleanup.global_crop_refit(raw, window, size, 0)

    @unittest.skipUnless(cleanup.SECURE_OPENAT_AVAILABLE, "requires secure POSIX openat")
    def test_wrong_hash_or_path_escape_rejected_before_decoding(self):
        (self.root / "input").write_bytes(b"hello")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            cleanup.checked(dict(path="input", sha256="0" * 64), self.root)
        for path in ["../input", "/input", "a//input", "a/./input", "C:input", "a\\input"]:
            with self.assertRaisesRegex(ValueError, "unsafe"):
                cleanup.checked(dict(path=path, sha256="0" * 64), self.root)

    @unittest.skipUnless(cleanup.SECURE_OPENAT_AVAILABLE, "requires secure POSIX openat")
    def test_regular_file_byte_limit_and_symlink_rejected(self):
        p = self.root / "input"; p.write_bytes(b"12345")
        with patch.object(cleanup, "MAX_BYTES", 4):
            with self.assertRaisesRegex(ValueError, "bounded regular"):
                cleanup.regular_bytes(p)
        link = self.root / "link"
        try: link.symlink_to(p)
        except OSError: self.skipTest("symlinks unavailable")
        with self.assertRaisesRegex(ValueError, "symlink"):
            cleanup.regular_bytes(link)

    @unittest.skipUnless(cleanup.SECURE_OPENAT_AVAILABLE, "requires secure POSIX openat")
    def test_buffer_consumed_once_and_changed_descriptor_rejected(self):
        p = self.root / "input"; p.write_bytes(b"old")
        actual_open = os.open
        def replace(name, flags, **kwargs):
            if str(name) == "input":
                replacement = self.root / "replacement"; replacement.write_bytes(b"new")
                replacement.replace(p)
            return actual_open(name, flags, **kwargs)
        with patch.object(cleanup.os, "open", replace):
            with self.assertRaisesRegex(ValueError, "opened input changed"):
                cleanup.regular_bytes(p)

    @unittest.skipUnless(cleanup.SECURE_OPENAT_AVAILABLE, "requires secure POSIX openat")
    def test_parent_swap_before_legacy_lstat_cannot_authenticate_outside_bytes(self):
        pack = self.root / "pack"; folder = pack / "inputs"; folder.mkdir(parents=True)
        (folder / "input").write_bytes(b"inside")
        outside = self.root / "outside"; outside.mkdir(); (outside / "input").write_bytes(b"outside")
        actual_lstat = Path.lstat
        swapped = []; file_lstat_calls = []
        def swap_before_legacy_lstat(path, *args, **kwargs):
            if path == folder / "input":
                file_lstat_calls.append(True)
            # First call belongs to the legacy is_symlink precheck; the second
            # is its unchecked initial metadata read after all parent prechecks.
            if path == folder / "input" and len(file_lstat_calls) == 2 and not swapped:
                folder.rename(pack / "original-inputs"); folder.symlink_to(outside, target_is_directory=True)
                swapped.append(True)
            return actual_lstat(path, *args, **kwargs)
        binding = dict(path="inputs/input", sha256=hashlib.sha256(b"outside").hexdigest())
        with patch.object(Path, "lstat", swap_before_legacy_lstat):
            with self.assertRaises(ValueError): cleanup.checked(binding, pack)
        # V1 follows the replaced parent and returns outside bytes matching the hash.
        # V2 never uses this unchecked absolute lstat and reads the legitimate tree.

    @unittest.skipUnless(cleanup.SECURE_OPENAT_AVAILABLE, "requires secure POSIX openat")
    def test_actual_openat_parent_component_swap_rejects_symlink(self):
        pack = self.root / "pack"; folder = pack / "inputs"; folder.mkdir(parents=True)
        (folder / "input").write_bytes(b"inside")
        outside = self.root / "outside"; outside.mkdir(); (outside / "input").write_bytes(b"outside")
        actual_open = os.open; swapped = []
        def swap_component(name, flags, **kwargs):
            if str(name) == "inputs" and not swapped:
                folder.rename(pack / "original-inputs"); folder.symlink_to(outside, target_is_directory=True)
                swapped.append(True)
            return actual_open(name, flags, **kwargs)
        with patch.object(cleanup.os, "open", swap_component):
            with self.assertRaisesRegex(ValueError, "traversal rejected"):
                cleanup.checked(dict(path="inputs/input", sha256=hashlib.sha256(b"outside").hexdigest()), pack)
        self.assertEqual(swapped, [True])

    def test_existing_output_refused_before_recipe_read(self):
        out = self.root / "occupied"; out.mkdir()
        with self.assertRaisesRegex(ValueError, "fresh absent"):
            cleanup.run_recipe(self.root / "missing", self.root, out)


if __name__ == "__main__": unittest.main()
