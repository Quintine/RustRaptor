"""Small archive fixtures; no game build or production data copy required."""
import hashlib
from pathlib import Path
import tempfile
import unittest
import zipfile

from assemble_runtime import iter_archive_files


class RuntimeArchiveTests(unittest.TestCase):
    def test_manifest_derived_payload_survives_cache_filter_and_relocation(self):
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / "package"
            payload = "data/hd/jobs/reviewed-family/derived/200a2-derived.png"
            required = ["data/INDEX", "data/hd/hd.json", payload]
            fixtures = {
                "data/INDEX": b"catalog",
                "data/hd/hd.json": b"manifest",
                payload: b"accepted derived PNG bytes",
                "data/hd/jobs/reviewed-family/derived/rejected-preview.png": b"not admitted",
                "derived/preview.png": b"private cache",
                "target/build-cache": b"build",
                ".reference/private": b"private",
                "mods/demo/art/source/parent.png": b"authoring reference",
                "mods/demo/art/runtime.png": b"mod runtime",
                "bin/raptor-rust": b"Linux only",
                "bin/raptor-rust.exe": b"Windows",
            }
            for name, data in fixtures.items():
                path = package / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            archive = Path(directory) / "windows.zip"
            skipped = {"target", "dist", ".reference", "derived", "lib"}
            selected = list(iter_archive_files(
                package, archive, skipped, excluded_files=(Path("bin/raptor-rust"),),
                required_files=required))
            names = {path.relative_to(package).as_posix() for path in selected}
            self.assertTrue(set(required) <= names)
            self.assertEqual(names - set(required), {"mods/demo/art/runtime.png", "bin/raptor-rust.exe"})
            with zipfile.ZipFile(archive, "w") as output:
                for path in selected:
                    output.write(path, "RustRaptor/" + path.relative_to(package).as_posix())
            relocated = Path(directory) / "Portable Windows Ω folder"
            with zipfile.ZipFile(archive) as packed:
                packed.extractall(relocated)
            for name in required:
                original = package / name
                copied = relocated / "RustRaptor" / name
                self.assertEqual(hashlib.sha256(copied.read_bytes()).digest(),
                                 hashlib.sha256(original.read_bytes()).digest())

    def test_missing_manifest_payload_fails_before_yielding_files(self):
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory)
            with self.assertRaises(FileNotFoundError):
                next(iter_archive_files(package, package / "out.zip", {"derived"},
                                        required_files=["data/hd/missing.png"]))

    def test_explicit_exclusion_cannot_silently_drop_manifest_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory)
            path = package / "data/required"
            path.parent.mkdir()
            path.write_bytes(b"required")
            with self.assertRaisesRegex(ValueError, "missing required files"):
                list(iter_archive_files(package, package / "out.zip", set(),
                                        excluded_files=(Path("data/required"),),
                                        required_files=["data/required"]))

    def test_manifest_path_cannot_escape_package(self):
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory)
            for name in ("../outside", str(package / "absolute")):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    list(iter_archive_files(package, package / "out.zip", set(),
                                            required_files=[name]))


if __name__ == "__main__":
    unittest.main()
