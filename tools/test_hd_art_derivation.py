"""Synthetic lineage checks; these fixtures do not claim generated art approval."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from hd_art_derivation import validate_derivation


class DerivationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        self.root = self.project / "data/hd"
        self.root.mkdir(parents=True)
        self.method = "synthetic-fixture-not-art-acceptance"
        raw = self.put("parent.png", b"\x89PNG\r\n\x1a\nfixture-parent")
        tool = self.put("tools/fixture.py", b"# synthetic recipe tool\n", self.project)
        recipe = self.put("recipe.json", b'{"scope":"synthetic"}')
        output = self.put("derived.png", b"\x89PNG\r\n\x1a\nfixture-output")
        self.rows = {"12345": {"file": output["path"], "source_sha256": "a" * 64}}
        self.execution = {"execution": {"status": "success", "method": self.method,
            "recipe_sha256": recipe["sha256"], "tool_sha256": tool["sha256"],
            "source_sha256": {"12345": "a" * 64}, "parent_raw_sha256": [raw["sha256"]],
            "output_sha256": {"12345": output["sha256"]}}}
        self.lineage = {"format_version": 1, "kind": "deterministic_cleanup", "method": self.method,
            "parents": [{"raw_png": raw, "prompt": self.put("prompt.txt", b"Synthetic prompt fixture"),
                "imagegen_receipt": self.put("parent-receipt.json", b'{"scope":"synthetic"}')}],
            "tools": [tool], "recipe": recipe,
            "execution_receipt": self.put_json("execution.json", self.execution),
            "sources": {"12345": "a" * 64}, "outputs": {output["path"]: output["sha256"]}}
        self.candidate, self.review = {}, {}
        self.qa = {"artwork_sha256": self.lineage["outputs"].copy()}
        self.bind()

    def put(self, path, payload, root=None):
        destination = (root or self.root) / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
        return {"path": path, "sha256": hashlib.sha256(payload).hexdigest()}

    def put_json(self, path, value):
        return self.put(path, (json.dumps(value, sort_keys=True) + "\n").encode())

    def bind(self):
        ref = self.put_json("lineage.json", self.lineage)
        self.candidate["artwork_derivation"] = ref
        self.review["artwork_derivation"] = ref.copy()

    def validate(self):
        return validate_derivation(self.root, self.project, self.candidate, self.review, self.rows, self.qa)

    def test_exact_lineage_is_read_only_and_legacy_is_optional(self):
        before = {str(p): p.read_bytes() for p in self.project.rglob("*") if p.is_file()}
        self.assertEqual(self.validate(), self.candidate["artwork_derivation"])
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.project.rglob("*") if p.is_file()})
        self.assertIsNone(validate_derivation(self.root, self.project, {}, {}, {}, {}))

    def test_review_cannot_use_parent_or_another_derivation(self):
        self.review["artwork_derivation"]["sha256"] = "0" * 64
        with self.assertRaises(ValueError): self.validate()
        self.review.pop("artwork_derivation")
        with self.assertRaises(ValueError): self.validate()

    def test_every_input_and_output_is_hash_bound(self):
        refs = [self.lineage["parents"][0][k] for k in ["raw_png", "prompt", "imagegen_receipt"]]
        refs += [self.lineage[k] for k in ["recipe", "execution_receipt"]]
        refs += [{"path": "derived.png"}, {"path": "lineage.json"}]
        for ref in refs:
            path = self.root / ref["path"]
            original = path.read_bytes()
            with self.subTest(path=path.name):
                path.write_bytes(original + b"changed")
                with self.assertRaises(ValueError): self.validate()
                path.write_bytes(original)
        tool = self.project / self.lineage["tools"][0]["path"]
        tool.write_bytes(b"changed")
        with self.assertRaises(ValueError): self.validate()

    def test_rehashed_execution_cannot_change_recipe_tool_sources_parents_outputs_or_success(self):
        for key in self.execution["execution"]:
            altered = copy.deepcopy(self.execution)
            altered["execution"][key] = "wrong"
            with self.subTest(key=key):
                self.lineage["execution_receipt"] = self.put_json("execution.json", altered)
                self.bind()
                with self.assertRaises(ValueError): self.validate()

    def test_source_output_inventory_and_stale_qa_reject(self):
        original = copy.deepcopy(self.lineage)
        for field in ["sources", "outputs"]:
            for value in [{}, {"extra": "0" * 64}]:
                self.lineage = copy.deepcopy(original)
                self.lineage[field] = value
                self.bind()
                with self.subTest(field=field, value=value), self.assertRaises(ValueError): self.validate()
        self.lineage = original
        self.bind()
        self.qa["artwork_sha256"]["derived.png"] = original["parents"][0]["raw_png"]["sha256"]
        with self.assertRaises(ValueError): self.validate()

    def test_absolute_traversal_and_symlink_escape_reject(self):
        outside = self.project / "outside.json"
        outside.write_text('{"scope":"outside"}')
        (self.root / "link.json").symlink_to(outside)
        for path in [str(outside), "../../outside.json", "link.json"]:
            self.lineage["recipe"] = {"path": path, "sha256": hashlib.sha256(outside.read_bytes()).hexdigest()}
            self.bind()
            with self.subTest(path=path), self.assertRaises(ValueError): self.validate()

    def test_malformed_and_non_object_receipts_reject_as_validation_errors(self):
        for value in [None, [], 1, {"execution": []}]:
            self.lineage["execution_receipt"] = self.put_json("execution.json", value)
            self.bind()
            with self.subTest(value=value), self.assertRaises(ValueError): self.validate()
        self.candidate["artwork_derivation"] = self.put_json("lineage.json", [])
        self.review["artwork_derivation"] = self.candidate["artwork_derivation"]
        with self.assertRaises(ValueError): self.validate()


if __name__ == "__main__":
    unittest.main()
