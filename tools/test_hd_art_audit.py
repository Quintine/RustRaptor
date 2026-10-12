"""Full-canvas integer rounding eligibility; this is not artwork approval."""
import hashlib
import struct
import tempfile
import unittest
from pathlib import Path

from PIL import Image
from hd_art_audit import integer_rounded_aspect, validate_hd_frame
from hd_art_source import decode


class FullCanvasRoundingAuditTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def case(self, logical=(8, 5), natural=(101, 63), transparent=True):
        width, height = logical
        payload = bytearray(struct.pack("<iiiii", 0 if transparent else 1, 0, 0, width, height))
        if transparent:
            # Real legacy span payload with both occupied and empty source cells.
            start = 1 if width > 2 else 0
            length = max(1, width - 2)
            rows = range(1, height - 1) if height > 2 else range(1)
            for y in rows:
                payload.extend(struct.pack("<iiii", start, y, y * width + start, length))
                payload.extend(bytes([7] * length))
            payload.extend(struct.pack("<iiii", 0, 0, -1, 0))
        else:
            payload.extend(bytes([7] * (width * height)))
        payload = bytes(payload)
        source = self.root / "source.bin"
        source.write_bytes(payload)
        picture = decode(source, [(80, 100, 120)] * 256)
        raw = Image.new("RGBA", natural, (80, 100, 120, 0 if transparent else 255))
        if transparent:
            x0, y0 = natural[0] // 4, natural[1] // 4
            raw.paste((80, 100, 120, 255), (x0, y0, natural[0] - x0, natural[1] - y0))
        raw.save(self.root / "ship.png")
        frame = {"frame": 0, "file": "ship.png", "logical_width": width,
                 "logical_height": height, "origin": [0, 0],
                 "source_sha256": hashlib.sha256(payload).hexdigest()}
        return frame, payload, picture

    def validate(self, frame, payload, picture):
        return validate_hd_frame(self.root, frame, payload, picture)

    def test_full_canvas_and_explicit_full_crop_accept_both_original_alpha_classes(self):
        for logical, natural in [((8, 5), (101, 63)), ((5, 8), (63, 101)),
                                 ((40, 32), (1402, 1122))]:
            for transparent in [False, True]:
                with self.subTest(logical=logical, natural=natural, transparent=transparent):
                    frame, payload, picture = self.case(logical, natural, transparent)
                    expected = min(natural[0], logical[0] * 4) * min(natural[1], logical[1] * 4) * 4
                    self.assertEqual(self.validate(frame, payload, picture), expected)
                    frame["crop"] = [0, 0, *natural]
                    self.assertEqual(self.validate(frame, payload, picture), expected)

    def test_inexact_partial_crop_rejected_but_exact_partial_crop_unchanged(self):
        for transparent in [False, True]:
            frame, payload, picture = self.case(transparent=transparent)
            for crop in [[0, 0, 100, 63], [1, 0, 100, 63], [0, 0, 101, 62]]:
                with self.subTest(transparent=transparent, crop=crop):
                    changed = {**frame, "crop": crop}
                    with self.assertRaisesRegex(ValueError, "aspect differs"):
                        self.validate(changed, payload, picture)
            frame["crop"] = [1, 1, 80, 50]
            self.assertEqual(self.validate(frame, payload, picture), 32 * 20 * 4)

    def test_strict_ties_aspect_and_minimum_resolution_are_not_relaxed(self):
        self.assertFalse(integer_rounded_aspect(5, 6, 2, 2))
        self.assertFalse(integer_rounded_aspect(0, 6, 2, 2))
        self.assertFalse(integer_rounded_aspect(5, 6, 0, 2))
        for logical, natural, message in [((2, 2), (5, 6), "aspect differs"),
                                           ((8, 5), (101, 64), "aspect differs"),
                                           ((8, 5), (15, 10), "twice")]:
            with self.subTest(logical=logical, natural=natural):
                frame, payload, picture = self.case(logical, natural)
                with self.assertRaisesRegex(ValueError, message):
                    self.validate(frame, payload, picture)

    def test_transparent_original_keeps_background_and_visible_alpha_checks(self):
        frame, payload, picture = self.case()
        for alpha, message in [(255, "transparent HD background"),
                               (0, "no visible pixels"), (127, "no visible pixels")]:
            with self.subTest(alpha=alpha):
                raw = Image.new("RGBA", (101, 63), (80, 100, 120, alpha))
                if alpha == 127:
                    raw.putpixel((0, 0), (0, 0, 0, 0))
                raw.save(self.root / "ship.png")
                with self.assertRaisesRegex(ValueError, message):
                    self.validate(frame, payload, picture)

    def test_rounded_opaque_original_still_requires_every_raw_alpha_to_be_255(self):
        frame, payload, picture = self.case(transparent=False)
        for alpha in [0, 128, 254]:
            with self.subTest(alpha=alpha):
                raw = Image.new("RGBA", (101, 63), (80, 100, 120, 255))
                raw.putpixel((100, 62), (80, 100, 120, alpha))
                raw.save(self.root / "ship.png")
                with self.assertRaisesRegex(ValueError, "fully opaque"):
                    self.validate(frame, payload, picture)

    def test_source_canvas_anchor_hash_path_and_crop_contracts_are_retained(self):
        frame, payload, picture = self.case()
        for fields, message in [({"logical_width": 9}, "logical canvas"),
                                ({"origin": [1, 0]}, "top-left anchor"),
                                ({"source_sha256": "changed"}, "source hash"),
                                ({"file": "../escape.png"}, "stay relative"),
                                ({"crop": [1, 0, 101, 63]}, "crop exceeds"),
                                ({"crop": [0, 0, 0, 63]}, "crop exceeds")]:
            with self.subTest(fields=fields):
                with self.assertRaisesRegex(ValueError, message):
                    self.validate({**frame, **fields}, payload, picture)

    def test_malformed_or_non_png_art_stays_rejected(self):
        frame, payload, picture = self.case()
        (self.root / "ship.png").write_bytes(b"not an image")
        with self.assertRaises(OSError):
            self.validate(frame, payload, picture)
        Image.new("RGB", (101, 63), (80, 100, 120)).save(self.root / "ship.png", format="JPEG")
        with self.assertRaisesRegex(ValueError, "must be PNG"):
            self.validate(frame, payload, picture)


if __name__ == "__main__":
    unittest.main()
