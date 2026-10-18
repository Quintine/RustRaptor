"""Synthetic dispatcher tests; never execute cleanup pixel processing."""
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("batch", Path(__file__).with_name("hd_boss_cleanup_reproduce.py"))
batch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(batch)


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.project = self.root / "project"
        (self.project / "tools").mkdir(parents=True)
        self.base = self.root / "job"
        self.base.mkdir()
        for n in ["hd_boss_cleanup.py", "hd_frame_policy.py"]:
            (self.project / "tools" / n).write_text("# synthetic bound implementation\n")
        for n in ["source", "raw", "palette"]:
            (self.base / n).write_bytes(n.encode())
        def ref(p, base): return {"path": str(p.relative_to(base)), "sha256": batch.sha(p)}
        self.doc = {"format_version": 1, "kind": "boss_cleanup_reproduce_batch", "method": batch.METHOD,
                    "cleanup_tool": ref(self.project / "tools/hd_boss_cleanup.py", self.project),
                    "decoder": ref(self.project / "tools/hd_frame_policy.py", self.project), "frames": []}
        for asset in ["abc", "abd"]:
            sub = {"asset": asset, "source": ref(self.base / "source", self.base),
                   "parent_raw": ref(self.base / "raw", self.base), "palette": ref(self.base / "palette", self.base)}
            p = self.base / f"{asset}.json"
            p.write_text(json.dumps(sub))
            self.doc["frames"].append({"asset": asset, "recipe": ref(p, self.base),
                "expected_output_sha256": __import__('hashlib').sha256(asset.encode()).hexdigest()})
        self.recipe = self.base / "batch.json"
        self.save()

    def save(self): self.recipe.write_text(json.dumps(self.doc))

    def test_preflight_rejects_bad_tool_before_any_output(self):
        self.doc["cleanup_tool"]["sha256"] = "0" * 64
        self.save()
        with self.assertRaises(ValueError): batch.run_batch(self.recipe, self.base / "out", self.project)
        self.assertFalse((self.base / "out").exists())

    def test_duplicate_asset_rejected(self):
        self.doc["frames"][1] = self.doc["frames"][0].copy()
        self.save()
        with self.assertRaises(ValueError): batch.plan(self.recipe, self.project)

    def test_escaped_recipe_rejected(self):
        self.doc["frames"][0]["recipe"]["path"] = "../outside.json"
        self.save()
        with self.assertRaises(ValueError): batch.plan(self.recipe, self.project)

    def test_wrong_subrecipe_asset_rejected(self):
        self.doc["frames"][0]["asset"] = "abe"
        self.save()
        with self.assertRaises(ValueError): batch.plan(self.recipe, self.project)

    def test_changed_source_rejected_before_output(self):
        (self.base / "source").write_bytes(b"changed")
        with self.assertRaises(ValueError): batch.run_batch(self.recipe, self.base / "out", self.project)
        self.assertFalse((self.base / "out").exists())

    def fake_cleanup(self, subpath, output):
        sub = json.loads(subpath.read_text()); asset = sub["asset"]
        output.mkdir()
        (output / f"{asset}-derived.png").write_bytes(asset.encode())
        result = {"execution": {"status": "success", "method": "derived-generated-boss-source-geometry-rgb-preserved-v1", "recipe_sha256": batch.sha(subpath),
              "tool_sha256": self.doc["cleanup_tool"]["sha256"], "source_sha256": {asset: sub["source"]["sha256"]},
              "parent_raw_sha256": [sub["parent_raw"]["sha256"]],
              "output_sha256": {asset: batch.sha(output / f"{asset}-derived.png")}}}
        (output / "derived-provenance.json").write_text(json.dumps(result))
        return result

    def fake_import(self, name):
        return SimpleNamespace(__file__=str(self.project / "tools" / f"{name}.py"), run_recipe=self.fake_cleanup)

    def test_actual_aggregate_uses_unique_parent_and_per_asset_outputs(self):
        with patch.object(batch.importlib, "import_module", side_effect=self.fake_import):
            result = batch.run_batch(self.recipe, self.base / "out", self.project)
        e = result["execution"]
        self.assertEqual(result["actual_cleanup_subruns"], 2)
        self.assertEqual(e["recipe_sha256"], batch.sha(self.recipe))
        self.assertEqual(e["tool_sha256"], batch.sha(batch.__file__))
        self.assertEqual(e["parent_raw_sha256"], [batch.sha(self.base / "raw")])
        self.assertEqual(set(e["source_sha256"]), {"abc", "abd"})
        self.assertEqual(e["output_sha256"], {r["asset"]: r["expected_output_sha256"] for r in self.doc["frames"]})

    def test_wrong_accepted_png_does_not_write_success_receipt(self):
        self.doc["frames"][0]["expected_output_sha256"] = "0" * 64
        self.save()
        with patch.object(batch.importlib, "import_module", side_effect=self.fake_import):
            with self.assertRaises(ValueError): batch.run_batch(self.recipe, self.base / "out", self.project)
        self.assertFalse((self.base / "out/batch-execution.json").exists())

    def test_existing_output_is_never_overwritten(self):
        output = self.base / "out"; output.mkdir(); sentinel = output / "old"; sentinel.write_text("old")
        with self.assertRaises(ValueError): batch.run_batch(self.recipe, output, self.project)
        self.assertEqual(sentinel.read_text(), "old")

    def test_all_subrun_execution_fields_must_match_pinned_inputs(self):
        original = self.fake_cleanup
        fields = ["status", "method", "recipe_sha256", "tool_sha256", "source_sha256", "parent_raw_sha256", "output_sha256"]
        for number, field in enumerate(fields):
            with self.subTest(field=field):
                def contradictory(path, output):
                    report = original(path, output)
                    report['execution'][field] = "contradiction"
                    return report
                with patch.object(batch.importlib, "import_module", side_effect=self.fake_import), patch.object(self, "fake_cleanup", side_effect=contradictory):
                    output = self.base / f"bad-{number}"
                    with self.assertRaises(ValueError): batch.run_batch(self.recipe, output, self.project)
                self.assertFalse((output / 'batch-execution.json').exists())

    def test_batch_recipe_edit_during_subrun_prevents_success(self):
        original = self.fake_cleanup
        def changed(path, output):
            report = original(path, output)
            self.recipe.write_text(self.recipe.read_text() + ' ')
            return report
        with patch.object(batch.importlib, "import_module", side_effect=self.fake_import), patch.object(self, "fake_cleanup", side_effect=changed):
            with self.assertRaises(ValueError): batch.run_batch(self.recipe, self.base / "out", self.project)
        self.assertFalse((self.base / 'out/batch-execution.json').exists())

    def test_subrecipe_edit_during_subrun_prevents_success(self):
        original = self.fake_cleanup
        def changed(path, output):
            report = original(path, output)
            path.write_text(path.read_text() + ' ')
            return report
        with patch.object(batch.importlib, "import_module", side_effect=self.fake_import), patch.object(self, "fake_cleanup", side_effect=changed):
            with self.assertRaises(ValueError): batch.run_batch(self.recipe, self.base / "out", self.project)
        self.assertFalse((self.base / 'out/batch-execution.json').exists())


if __name__ == "__main__": unittest.main()
