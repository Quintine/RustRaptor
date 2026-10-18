"""Synthetic packing checks; no production copies or compiler required."""
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from assemble_runtime import default_data_source, select_data_files


class RuntimeDataSelectionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.package = self.root / "RustRaptor"
        self.data = self.package / "data"
        self.catalog(self.data)
        self.briefings(self.data)

    def write(self, root, name, payload):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        return path

    def catalog(self, root):
        self.write(root, "INDEX", b"00001 4 sprites/a.bin\n")
        self.write(root, "sprites/a.bin", b"base")

    def briefings(self, root):
        for sector in range(1, 4):
            for wave in range(1, 10):
                for mode in ("sd", "hd"):
                    self.write(root, f"briefings/sector_{sector}_wave_{wave}_{mode}.png",
                               f"briefing {sector}/{wave}/{mode}".encode())

    def hd(self, root, name="frames/new.png", payload=b"new frame"):
        self.write(root, name, payload)
        self.write(root, "hd.json", json.dumps({"sequences": [
            {"frames": [{"file": name}]}]}).encode())

    def test_bundled_catalog_wins_over_parent_legacy_catalog(self):
        external = self.root / "data"
        self.catalog(external)
        self.write(external, "legacy-only", b"obsolete")
        self.assertEqual(default_data_source(self.package), self.data)
        files, entries, count = select_data_files(self.package)
        self.assertNotIn("legacy-only", files)
        self.assertEqual((len(entries), count), (1, 0))
        (self.data / "INDEX").unlink()
        self.assertEqual(default_data_source(self.package), external)

    def test_complete_tree_roundtrips_briefings_provenance_and_hd_jobs(self):
        self.hd(self.data / "hd")
        extras = {
            "briefings/provenance.json": b"briefing provenance",
            "hd/provenance.json": b"HD lineage",
            "hd/jobs/family/derived/accepted.png": b"derived payload",
            "hd/jobs/family/raw/source.png": b"raw lineage",
            "hd/jobs/family/recipe.json": b"recipe",
            "misc/runtime-extra": b"extra data",
        }
        for name, payload in extras.items():
            self.write(self.data, name, payload)
        files, _, count = select_data_files(self.package)
        self.assertEqual(count, 1)
        self.assertEqual(len([n for n in files if n.startswith("briefings/") and n.endswith(".png")]), 54)
        self.assertTrue(set(extras) <= set(files))
        relocated = self.root / "Portable Runtime Ω" / "data"
        for name, path in files.items():
            destination = relocated / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
        self.assertEqual({p.relative_to(self.data).as_posix(): p.read_bytes()
                          for p in self.data.rglob("*") if p.is_file()},
                         {p.relative_to(relocated).as_posix(): p.read_bytes()
                          for p in relocated.rglob("*") if p.is_file()})

    def test_external_catalog_fallback_preserves_existing_briefing(self):
        external = self.root / "external"
        self.catalog(external)
        override = "briefings/sector_1_wave_1_sd.png"
        self.write(external, override, b"external briefing")
        self.write(external, "provenance.json", b"external metadata")
        self.write(self.data, "briefings/provenance.json", b"bundled briefing lineage")
        files, _, _ = select_data_files(self.package, external)
        self.assertEqual(files[override].read_bytes(), b"external briefing")
        self.assertEqual(files["briefings/sector_3_wave_9_hd.png"].read_bytes(), b"briefing 3/9/hd")
        self.assertEqual(files["provenance.json"].read_bytes(), b"external metadata")
        self.assertEqual(len([n for n in files if n.startswith("briefings/") and n.endswith(".png")]), 54)
        self.assertEqual(files["briefings/provenance.json"].read_bytes(), b"bundled briefing lineage")

    def test_explicit_hd_replaces_entire_old_subtree(self):
        self.hd(self.data / "hd", "old.png", b"obsolete frame")
        self.write(self.data, "hd/jobs/old/receipt.json", b"obsolete metadata")
        replacement = self.root / "approved-HD"
        self.hd(replacement)
        self.write(replacement, "jobs/new/raw/source.png", b"new lineage")
        self.write(replacement, "provenance.json", b"new provenance")
        files, _, count = select_data_files(self.package, hd_source=replacement)
        self.assertEqual(count, 1)
        self.assertEqual({n for n in files if n.startswith("hd/")},
                         {"hd/hd.json", "hd/frames/new.png", "hd/jobs/new/raw/source.png", "hd/provenance.json"})
        self.assertEqual(files["hd/provenance.json"].read_bytes(), b"new provenance")

    def test_missing_required_briefing_or_explicit_manifest_fails(self):
        (self.data / "briefings/sector_3_wave_9_hd.png").unlink()
        with self.assertRaisesRegex(ValueError, "required mission briefing"):
            select_data_files(self.package)
        self.briefings(self.data)
        empty = self.root / "empty-hd"
        empty.mkdir()
        with self.assertRaises(FileNotFoundError):
            select_data_files(self.package, hd_source=empty)

    def test_unlisted_file_and_directory_symlinks_cannot_escape_source(self):
        outside = self.write(self.root, "outside", b"private")
        link = self.data / "unlisted-link"
        link.symlink_to(outside)
        with self.assertRaises(ValueError):
            select_data_files(self.package)
        link.unlink()
        link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink directory"):
            select_data_files(self.package)

    def test_catalog_and_hd_manifest_traversal_and_size_are_checked(self):
        for catalog in (b"00001 4 ../outside\n", b"00001 999 sprites/a.bin\n"):
            self.write(self.data, "INDEX", catalog)
            with self.subTest(catalog=catalog), self.assertRaises(ValueError):
                select_data_files(self.package)
        self.catalog(self.data)
        replacement = self.root / "unsafe-HD"
        self.hd(replacement, "../outside", b"private")
        with self.assertRaises(ValueError):
            select_data_files(self.package, hd_source=replacement)

    def test_external_fallback_briefing_symlink_cannot_escape_bundled_data(self):
        external = self.root / "external"
        self.catalog(external)
        missing = self.data / "briefings/sector_1_wave_1_sd.png"
        missing.unlink()
        missing.symlink_to(self.write(self.root, "outside", b"private"))
        with self.assertRaises(ValueError):
            select_data_files(self.package, external)


    def test_external_fallback_briefing_root_symlink_is_rejected(self):
        external = self.root / "external"
        self.catalog(external)
        outside = self.root / "outside-private"
        self.briefings(outside)
        bundled_briefings = self.data / "briefings"
        shutil.rmtree(bundled_briefings)
        bundled_briefings.symlink_to(outside / "briefings", target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink directory in bundled mission briefings"):
            select_data_files(self.package, external)

    def test_unreadable_unlisted_lineage_directory_fails_instead_of_being_omitted(self):
        proof = self.write(self.data, "hd/jobs/family/proofs/lineage.json", b"required lineage")
        denied = proof.parent
        real_scandir = os.scandir

        def checked_scandir(path):
            if Path(path) == denied:
                raise PermissionError("synthetic unreadable lineage directory")
            return real_scandir(path)

        with patch("assemble_runtime.os.scandir", side_effect=checked_scandir):
            with self.assertRaisesRegex(PermissionError, "synthetic unreadable lineage directory"):
                select_data_files(self.package)



if __name__ == "__main__":
    unittest.main()
