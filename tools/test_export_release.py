"""Small real-ZIP release fixtures; no production archives or game build."""
from pathlib import Path
import json
import os
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import export_release as release

COMMIT = "a" * 40


class ReleaseExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.package = self.root / "package"
        self.package.mkdir()
        fixtures = {"data/INDEX": b"10000 4 misc/pic\n", "data/misc/pic": b"base",
                    "data/hd/jobs/reviewed/derived/picture.png": b"accepted artwork",
                    "data/hd/jobs/reviewed/proofs/actual-proof.json": b"{}",
                    "bin/raptor-rust": b"Linux exe", "bin/raptor-rust.exe": b"Windows exe",
                    "bin/SDL2.dll": b"Windows SDL", "lib/libSDL2-2.0.so.0": b"Linux SDL",
                    "run.sh": b"#!/bin/sh\n", "run.cmd": b"@echo off\n",
                    "mods/example/mod.toml": b'id = "example"\n',
                    "mods/example/art/sd.png": b"SD", "mods/example/art/hd.png": b"HD",
                    "mods/example/sounds/fire.wav": b"sound", "mods/example/music/track.wav": b"music",
                    "mods/example/art/source/draft.png": b"private source art",
                    "src/main.rs": b"fn main() {}", "docs/modding.md": b"API docs",
                    "target/cache": b"build cache", ".reference/private": b"private review"}
        for name, value in fixtures.items():
            self.put(name, value)
        (self.package / "run.sh").chmod(0o755)
        self.put_json("data/hd/hd.json", {"sequences": [{"frames": [{"file": "jobs/reviewed/derived/picture.png"}]}]})
        data = {p.relative_to(self.package).as_posix(): release.digest(p)
                for p in (self.package / "data").rglob("*") if p.is_file()}
        self.put_json("runtime-manifest.json", {"files": data, "approved_hd_frames": 1,
                      "binary_sha256": release.digest(self.package / "bin/raptor-rust"),
                      "data_files": len(data), "data_bytes": sum((self.package / n).stat().st_size for n in data),
                      "catalog_entries": 1})
        self.put_json("runtime-windows-manifest.json", {"files": {
            n: release.digest(self.package / n) for n in ["bin/raptor-rust.exe", "bin/SDL2.dll", "run.cmd"]},
            "approved_hd_frames": 1})
        patch.object(release, "require_clean_workspace").start()
        self.mock_commit = patch.object(release, "git_commit", return_value=COMMIT).start()
        self.addCleanup(patch.stopall)

    def put(self, name, value):
        path = self.package / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)

    def put_json(self, name, value):
        self.put(name, (json.dumps(value) + "\n").encode())

    def plan(self):
        value = release.build_plan(self.package, COMMIT)
        path = self.root / "plan.json"
        release.write_new_json(path, value)
        return path, value

    def test_complete_data_mods_audio_and_platform_split(self):
        _, plan = self.plan()
        data, linux, windows = plan["assets"]
        self.assertIn("data/hd/jobs/reviewed/derived/picture.png", {r["name"] for r in data["files"]})
        self.assertIn("data/hd/jobs/reviewed/proofs/actual-proof.json", {r["name"] for r in data["files"]})
        for asset in (linux, windows):
            names = {r["name"] for r in asset["files"]}
            self.assertTrue({"mods/example/mod.toml", "mods/example/art/sd.png", "mods/example/art/hd.png",
                             "mods/example/sounds/fire.wav", "mods/example/music/track.wav", "src/main.rs"} <= names)
            self.assertFalse({"target/cache", ".reference/private", "mods/example/art/source/draft.png"} & names)
        self.assertIn("bin/raptor-rust", {r["name"] for r in linux["files"]})
        self.assertNotIn("bin/raptor-rust.exe", {r["name"] for r in linux["files"]})
        self.assertNotIn("lib/libSDL2-2.0.so.0", {r["name"] for r in windows["files"]})
        self.assertEqual(plan["bundled_mods"], 1)

    def test_partition_covers_every_file_once_under_budget(self):
        rows = [{"name": str(i), "bytes": i} for i in range(1, 7)]
        groups = release.partition(rows, 7)
        self.assertEqual([r for group in groups for r in group], rows)
        self.assertTrue(all(sum(r["bytes"] for r in group) <= 7 for group in groups))
        with self.assertRaises(ValueError):
            release.partition(rows, 5)

    def test_real_zip_relocation_complete_hashes_and_linux_permissions(self):
        path, plan = self.plan()
        relocated = self.root / "Portable Ω folder"
        for asset in plan["assets"]:
            archive = self.root / asset["name"]
            receipt = release.write_asset(path, asset["name"], archive)
            self.assertEqual(receipt["status"], "ZIP_CRC_AND_COMPLETE_PAYLOAD_SHA256_PASS")
            with zipfile.ZipFile(archive) as packed:
                self.assertIsNone(packed.testzip())
                packed.extractall(relocated)
                if asset["kind"] == "linux":
                    self.assertEqual((packed.getinfo("RustRaptor/run.sh").external_attr >> 16) & 0o777, 0o755)
            for row in asset["files"]:
                self.assertEqual(release.digest(relocated / "RustRaptor" / row["name"]), row["sha256"])

    def test_modified_same_size_data_is_rejected(self):
        path, plan = self.plan()
        self.put("data/misc/pic", b"evil")
        with self.assertRaisesRegex(ValueError, "differs from plan"):
            release.write_asset(path, plan["assets"][0]["name"], self.root / plan["assets"][0]["name"])

    def test_manifest_or_commit_change_rejected(self):
        path, plan = self.plan()
        self.mock_commit.return_value = "b" * 40
        with self.assertRaisesRegex(ValueError, "changed after"):
            release.write_asset(path, plan["assets"][0]["name"], self.root / plan["assets"][0]["name"])

    def test_no_overwrite_or_unplanned_output_name(self):
        path, plan = self.plan()
        asset = plan["assets"][0]["name"]
        with self.assertRaisesRegex(ValueError, "filename"):
            release.write_asset(path, asset, self.root / "wrong.zip")
        output = self.root / asset
        output.write_bytes(b"existing export")
        with self.assertRaisesRegex(ValueError, "already exists"):
            release.write_asset(path, asset, output)
        self.assertEqual(output.read_bytes(), b"existing export")

    def test_symlink_and_fifo_sources_are_rejected_without_blocking(self):
        outside = self.root / "outside"
        outside.write_bytes(b"base")
        source = self.package / "data/misc/pic"
        source.unlink()
        source.symlink_to(outside)
        with self.assertRaises(OSError):
            with release.opened_source(self.package, "data/misc/pic", 4):
                self.fail("symlink source was accepted")
        source.unlink()
        os.mkfifo(source)
        with self.assertRaisesRegex(ValueError, "regular file"):
            with release.opened_source(self.package, "data/misc/pic", 0):
                self.fail("FIFO source was accepted")

    def test_open_descriptor_growth_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "changed while"):
            with release.opened_source(self.package, "data/misc/pic", 4) as (stream, _):
                with (self.package / "data/misc/pic").open("ab") as growing:
                    growing.write(b"extra")
                self.assertEqual(stream.read(5), b"basee")

    def test_checksums_require_complete_matching_actual_receipts(self):
        path, plan = self.plan()
        receipts = self.root / "receipts"
        receipts.mkdir()
        with self.assertRaises(FileNotFoundError):
            release.checksums(path, receipts, self.root / "SHA256SUMS")
        for asset in plan["assets"]:
            result = release.write_asset(path, asset["name"], self.root / asset["name"])
            release.write_new_json(receipts / (asset["name"] + ".json"), result)
        release.checksums(path, receipts, self.root / "SHA256SUMS")
        self.assertEqual(len((self.root / "SHA256SUMS").read_text().splitlines()), len(plan["assets"]))
        record = receipts / (plan["assets"][0]["name"] + ".json")
        value = release.read_json(record)
        value["payload_sha256"] = {}
        record.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, "mismatched"):
            release.checksums(path, receipts, self.root / "bad-sums")

    def test_active_hd_missing_from_manifest_rejected(self):
        self.put_json("data/hd/hd.json", {"sequences": [{"frames": [{"file": "missing.png"}]}]})
        manifest = release.read_json(self.package / "runtime-manifest.json")
        manifest["files"]["data/hd/hd.json"] = release.digest(self.package / "data/hd/hd.json")
        manifest["data_bytes"] = sum((self.package / name).stat().st_size for name in manifest["files"])
        self.put_json("runtime-manifest.json", manifest)
        with self.assertRaises(FileNotFoundError):
            release.build_plan(self.package, COMMIT)

    def test_complete_physical_data_must_match_manifest(self):
        self.put("data/forgotten.wav", b"required sound")
        with self.assertRaisesRegex(ValueError, "complete physical"):
            self.plan()

    def test_nonportable_paths_rejected(self):
        for name in ("../outside", "RustRaptor/a/../b", "RustRaptor/C:evil", "RustRaptor/a\\b", "RustRaptor/CON.txt", "RustRaptor/a."):
            with self.subTest(name=name), self.assertRaises(ValueError):
                release.safe_member(name)

    def test_release_manifest_binds_all_payload_and_snapshot(self):
        path, plan = self.plan()
        receipts = self.root / "receipts"
        receipts.mkdir()
        for asset in plan["assets"]:
            result = release.write_asset(path, asset["name"], self.root / asset["name"])
            release.write_new_json(receipts / (asset["name"] + ".json"), result)
        manifest = self.root / "release-manifest.json"
        release.checksums(path, receipts, self.root / "SHA256SUMS", manifest, "v0.1.0-preview.test")
        actual = release.read_json(manifest)
        self.assertEqual(actual["checkpoint"], plan["snapshot"])
        self.assertEqual(actual["tag"], "v0.1.0-preview.test")
        self.assertEqual([a["files"] for a in actual["assets"]], [a["files"] for a in plan["assets"]])

    def test_data_directory_symlink_is_rejected(self):
        outside = self.root / "outside-data"
        outside.mkdir()
        (outside / "required.png").write_bytes(b"required")
        (self.package / "data/linked").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.plan()

    def test_mod_directory_symlink_is_rejected(self):
        outside = self.root / "outside-mod"
        outside.mkdir()
        (outside / "mod.toml").write_text('id="linked"')
        (self.package / "mods/linked").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.plan()

    def test_unmanifested_data_fifo_is_rejected_without_blocking(self):
        os.mkfifo(self.package / "data/fifo")
        with self.assertRaisesRegex(ValueError, "non-regular"):
            self.plan()

    def test_skipped_private_symlinks_and_fifo_do_not_enter_release(self):
        (self.package / "target/link").symlink_to(self.root, target_is_directory=True)
        os.mkfifo(self.package / ".reference/fifo")
        _, plan = self.plan()
        self.assertFalse(any("target/" in row["name"] or ".reference/" in row["name"]
                             for asset in plan["assets"] for row in asset["files"]))

    def test_selected_core_symlink_and_fifo_are_rejected(self):
        for kind in ("symlink", "fifo"):
            with self.subTest(kind=kind):
                path = self.package / "mods/example/bad"
                if kind == "symlink":
                    path.symlink_to(self.package / "src/main.rs")
                else:
                    os.mkfifo(path)
                try:
                    with self.assertRaisesRegex(ValueError, "symlink|non-regular"):
                        self.plan()
                finally:
                    path.unlink()

    def test_checksum_receipt_identity_and_invalid_tag_rejected_before_output(self):
        path, plan = self.plan()
        receipts = self.root / "receipts"
        receipts.mkdir()
        for asset in plan["assets"]:
            result = release.write_asset(path, asset["name"], self.root / asset["name"])
            release.write_new_json(receipts / (asset["name"] + ".json"), result)
        record = receipts / (plan["assets"][0]["name"] + ".json")
        original = release.read_json(record)
        for field, bad in (("checkpoint", {}), ("kind", "wrong"), ("payload_files", -1)):
            value = dict(original)
            value[field] = bad
            record.write_text(json.dumps(value))
            output = self.root / (field + "-SHA256SUMS")
            with self.assertRaisesRegex(ValueError, "mismatched"):
                release.checksums(path, receipts, output)
            self.assertFalse(output.exists())
        record.write_text(json.dumps(original))
        output = self.root / "invalid-tag-SHA256SUMS"
        with self.assertRaisesRegex(ValueError, "release tag"):
            release.checksums(path, receipts, output, self.root / "invalid-manifest.json", "../bad")
        self.assertFalse(output.exists())
        self.assertFalse((self.root / "invalid-manifest.json").exists())


class LinuxInstallerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        script = Path(__file__).parents[1] / "release/Install-Linux.sh"
        source = script.read_text().split("# BEGIN INSTALLER PYTHON\n", 1)[1].split("# END INSTALLER PYTHON", 1)[0]
        cls.api = {"__name__": "installer_test"}
        exec(compile(source, str(script), "exec"), cls.api)

    def test_real_long_path_payload_hash_and_executable_mode(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "one.zip"
            name = "data/" + ("long-component/" * 25) + "picture.png"
            body = b"complete accepted payload"
            with zipfile.ZipFile(archive, "w") as packed:
                info = zipfile.ZipInfo("RustRaptor/" + name)
                info.external_attr = 0o100755 << 16
                packed.writestr(info, body)
            row = {"name": name, "bytes": len(body), "sha256": release.hashlib.sha256(body).hexdigest()}
            self.api["extract"](archive, root, [row])
            actual = root / "RustRaptor" / name
            self.assertEqual(actual.read_bytes(), body)
            self.assertEqual(actual.stat().st_mode & 0o777, 0o755)
            with self.assertRaises(FileExistsError):
                self.api["extract"](archive, root, [row])

    def test_unexpected_member_symlink_and_bad_hash_rejected(self):
        for case in ("unexpected", "symlink", "hash", "traversal"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                archive = root / "one.zip"
                name = "RustRaptor/file" if case != "traversal" else "RustRaptor/../escape"
                with zipfile.ZipFile(archive, "w") as packed:
                    info = zipfile.ZipInfo(name)
                    info.external_attr = (0o120777 if case == "symlink" else 0o100644) << 16
                    packed.writestr(info, b"body")
                row = {"name": "other" if case == "unexpected" else name[len("RustRaptor/"):],
                       "bytes": 4, "sha256": "0" * 64 if case == "hash" else release.hashlib.sha256(b"body").hexdigest()}
                with self.assertRaises(ValueError):
                    self.api["extract"](archive, root, [row])

    def test_existing_symlink_parent_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            outside = root / "outside"
            outside.mkdir()
            (root / "RustRaptor").symlink_to(outside, target_is_directory=True)
            archive = root / "one.zip"
            with zipfile.ZipFile(archive, "w") as packed:
                packed.writestr("RustRaptor/file", b"body")
            row = {"name": "file", "bytes": 4, "sha256": release.hashlib.sha256(b"body").hexdigest()}
            with self.assertRaisesRegex(ValueError, "parent"):
                self.api["extract"](archive, root, [row])
            self.assertFalse((outside / "file").exists())


if __name__ == "__main__":
    unittest.main()
