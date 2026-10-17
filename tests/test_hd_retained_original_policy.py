"""Pure Source/schema/registrar tests; no PNG body, compiler, renderer or writer."""
import ast
import copy
import hashlib
import importlib.util
import json
import pathlib
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import hd_frame_policy as policy
import hd_candidate_review as candidate
import hd_register_reviewed as registrar
from PIL import Image

VERSION = "retained-original-details-v2-painted0255"

def payload(values=(19, 20, 18, 18)):
    return struct.pack("<5i", 1, 0, 0, 2, 2) + bytes(values)

def frame(raw=None):
    return dict(frame=0, file="raw.png", logical_width=2, logical_height=2,
                origin=[0, 0], source_sha256=hashlib.sha256(raw or payload()).hexdigest())

def selected(raw=None):
    result = frame(raw)
    result["original_detail_cells"] = [[0, 0]]
    return result

class PaintedPolicy(unittest.TestCase):
    def test_every_painted_Source_label_accepted(self):
        for index in range(256):
            raw = payload((index, 20, 18, 18))
            with self.subTest(index=index):
                policy.validate_frame_policy(selected(raw), raw)

    def test_sparse_transparent_and_outofrange_Source_rejected(self):
        sparse = (struct.pack("<5i", 0, 0, 0, 2, 2)
                  + struct.pack("<4i", 1, 0, 1, 1) + bytes([19])
                  + struct.pack("<4i", 0, 0, -1, 0))
        with self.assertRaises(ValueError):
            policy.validate_frame_policy(selected(sparse), sparse)
        for invalid in (-1, 256, 257, 65535):
            with self.subTest(index=invalid), mock.patch.object(policy, "_indices", return_value=(2, 2, [invalid, 20, 18, 18])):
                with self.assertRaises(ValueError):
                    policy.validate_frame_policy(selected(), payload())

    def test_old_coordinate_order_bound_capacity_types_unchanged(self):
        for cells in (True, [[True, 0]], [[0.0, 0]], [[-1, 0]], [[2, 0]],
                      [[0, 2]], [[0, 0], [0, 0]], [[1, 0], [0, 0]], [[0, 0]] * 65):
            f = frame(); f["original_detail_cells"] = cells
            with self.subTest(cells=cells), self.assertRaises(ValueError):
                policy.validate_frame_policy(f, payload())
        f = selected(); f["native_nearest_cues"] = [[0, 0]]
        with self.assertRaises(ValueError):
            policy.validate_frame_policy(f, payload())

    def test_detail_domain_never_expands_PNG_nearest_domain(self):
        for index in range(240, 256):
            raw = payload((index, 20, 18, 18))
            policy.validate_frame_policy(selected(raw), raw)
            f = frame(raw); f["native_nearest_cues"] = [[0, 0]]
            with self.subTest(index=index), self.assertRaises(ValueError):
                policy.validate_frame_policy(f, raw)

    def test_absent_empty_defaults_and_Source_dimension_guard(self):
        policy.validate_frame_policy(frame(), payload())
        f = frame(); f["original_detail_cells"] = []
        policy.validate_frame_policy(f, payload())
        bad = selected(); bad["logical_width"] = 3
        with self.assertRaises(ValueError):
            policy.validate_frame_policy(bad, payload())

    def test_candidate_digest_binds_cells_and_default_fields(self):
        f = selected(payload((252, 253, 18, 18)))
        c = dict(format_version=1, sequences=[dict(name="synthetic retained Original", base_asset=1, frame_count=1, frames=[f])])
        rows = candidate.proposal_frames(c)
        self.assertEqual(rows["00001"]["original_detail_cells"], [[0, 0]])
        for changed in ([], [[1, 0]]):
            other = copy.deepcopy(c); other["sequences"][0]["frames"][0]["original_detail_cells"] = changed
            self.assertNotEqual(candidate.binding_digest(rows), candidate.binding_digest(candidate.proposal_frames(other)))

    def test_official_audit_and_schema_share_actual_validator(self):
        tree = ast.parse((TOOLS / "hd_art_audit.py").read_text())
        self.assertTrue(any(isinstance(n, ast.ImportFrom) and n.module == "hd_frame_policy"
                            and {"FRAME_KEYS", "validate_frame_policy"} <= {a.name for a in n.names} for n in tree.body))
        self.assertIn("original_detail_cells", policy.FRAME_KEYS)
        self.assertIn("carried master74 frame has an unreviewed optional policy", (TOOLS / "hd_register_reviewed.py").read_text())

class ActualRegistrarProvenance(unittest.TestCase):
    """Run the real unchanged entry point on a synthetic file-only complete family.

    The fixture is not an asset/QA approval. No standalone branch, Catalog decode,
    PNG body, registrar main or actual writer is exercised.
    """
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="painted-original-pure-")
        self.addCleanup(self.temp.cleanup)
        self.directory = pathlib.Path(self.temp.name)
        self.project = self.directory / "project"
        (self.project / "src").mkdir(parents=True)
        for name in ("assets.rs", "hd.rs"):
            (self.project / "src" / name).write_bytes(b"synthetic Source pin")
        (self.project / "target").mkdir()
        self.library = self.project / "target/synthetic.rlib"
        self.library.write_bytes(b"synthetic library identity, never executed")
        self.root = self.directory / "data/hd"
        self.job_dir = self.root / "jobs/synthetic-complete1"
        self.job_dir.mkdir(parents=True)
        self.f = selected(payload((252, 253, 18, 18)))
        self.candidate = dict(format_version=1, job_id="synthetic-complete1", complete_family=True,
                              sequences=[dict(name="synthetic retained Original", base_asset=1, frame_count=1, frames=[self.f])])
        self.rows = candidate.proposal_frames(self.candidate)
        digest = candidate.binding_digest(self.rows)
        self.review = dict(status="approved", frame_bindings_sha256=digest,
                           source_and_all_scale_visual_review="synthetic only; no asset approval",
                           independent_review="synthetic only; no actual reviewer",
                           runtime_qa="qa.json", retained_original_detail_review=dict(
                               cells_by_asset={"00001": [[0, 0]]}, retained_original_not_generated_HD=True,
                               policy_version=VERSION, painted_Source_palette_domain=[0, 255],
                               functional_palette_effects_are_retained_Original=True,
                               hybrid_allscale_and_genuine_context_independent_review=True,
                               frame_bindings_sha256=digest))
        counts = [0] * 16; counts[12] = 1
        qa = dict(frame_bindings_sha256=digest, diagnostics=[], source_newer_than_library=False,
                  any_game_source_newer_than_library=False, library="target/synthetic.rlib",
                  library_modified_ns=self.library.stat().st_mtime_ns,
                  library_sha256=hashlib.sha256(self.library.read_bytes()).hexdigest(),
                  frames=[dict(asset="00001", source_sha256=self.f["source_sha256"], logical_canvas=[2, 2],
                               source_mask=dict(palette_indices_240_to_255_counts=counts),
                               hd_masks=[dict(scale=s, mask=dict(palette_indices_240_to_255_counts=counts)) for s in range(1, 5)])],
                  artwork_sha256={"raw.png": hashlib.sha256(b"opaque synthetic non-image bytes; never decoded").hexdigest()})
        (self.root / "raw.png").write_bytes(b"opaque synthetic non-image bytes; never decoded")
        self.write_json(self.job_dir / "candidate.json", self.candidate)
        self.write_json(self.job_dir / "job.json", dict(job_id="synthetic-complete1", targets=[dict(asset="00001", source_sha256=self.f["source_sha256"], logical_canvas=[2, 2])]))
        self.write_json(self.root / "qa.json", qa)

    @staticmethod
    def write_json(path, value):
        path.write_text(json.dumps(value, sort_keys=True) + "\n")

    def approve(self, declaration=None):
        review = copy.deepcopy(self.review)
        if declaration is not None:
            review["retained_original_detail_review"] = declaration
        self.write_json(self.job_dir / "coordinator-review.json", review)
        with mock.patch.object(registrar, "main", side_effect=AssertionError("main forbidden")), \
             mock.patch.object(registrar, "atomic_json", side_effect=AssertionError("writer forbidden")), \
             mock.patch.object(registrar, "decode", side_effect=AssertionError("Source decoder forbidden")), \
             mock.patch.object(registrar, "validate_hd_frame", side_effect=AssertionError("art audit forbidden")), \
             mock.patch.object(subprocess, "run", side_effect=AssertionError("process forbidden")), \
             mock.patch.object(Image, "open", side_effect=AssertionError("PNG decoder forbidden")):
            return registrar.approved_job(self.root, "synthetic-complete1", self.project)

    def test_real_approved_job_accepts_exact_explicit_painted_provenance(self):
        _, review, rows = self.approve()
        self.assertEqual(rows, self.rows)
        self.assertIs(review["retained_original_detail_review"]["functional_palette_effects_are_retained_Original"], True)

    def test_real_approved_job_rejects_every_missing_provenance_field(self):
        declaration = self.review["retained_original_detail_review"]
        for key in declaration:
            bad = copy.deepcopy(declaration); del bad[key]
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "retained Original detail provenance"):
                self.approve(bad)

    def test_real_approved_job_rejects_wrong_version_domain_truth_and_cells(self):
        mutations = dict(policy_version="retained-original-details-v1", painted_Source_palette_domain=[False, 255],
                         functional_palette_effects_are_retained_Original=1, retained_original_not_generated_HD=1,
                         hybrid_allscale_and_genuine_context_independent_review=1,
                         cells_by_asset={"00001": [[1, 0]]}, frame_bindings_sha256="0" * 64)
        for key, value in mutations.items():
            bad = copy.deepcopy(self.review["retained_original_detail_review"]); bad[key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "retained Original detail provenance"):
                self.approve(bad)

    def test_real_approved_job_never_requires_provenance_for_default_frames(self):
        self.candidate["sequences"][0]["frames"][0].pop("original_detail_cells")
        rows = candidate.proposal_frames(self.candidate); digest = candidate.binding_digest(rows)
        self.write_json(self.job_dir / "candidate.json", self.candidate)
        self.review.pop("retained_original_detail_review")
        self.review["frame_bindings_sha256"] = digest
        qa = json.loads((self.root / "qa.json").read_text()); qa["frame_bindings_sha256"] = digest
        self.write_json(self.root / "qa.json", qa)
        _, review, actual = self.approve()
        self.assertNotIn("retained_original_detail_review", review)
        self.assertEqual(actual, rows)

if __name__ == "__main__":
    unittest.main(verbosity=2)
