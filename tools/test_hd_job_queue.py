"""Family review references preserve queue decisions and external evidence."""
import argparse
import contextlib
import copy
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import hd_job_queue as queue
from hd_candidate_review import binding_digest, proposal_frames


class FamilyReviewLedgerTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.data = Path(self.temporary.name) / "data"
        self.hd = self.data / "hd"
        self.jobs = self.hd / "jobs"
        self.job_id = "enemies-11000-11002"
        self.directory = self.jobs / self.job_id
        self.directory.mkdir(parents=True)
        pictures = []
        entries = []
        for asset in [0x11000, 0x11001, 0x11002, 0x21000]:
            identity = f"{asset:05x}"
            terrain = asset == 0x21000
            name = "unused_ground" if terrain else f"flanker.{asset - 0x11000}"
            payload = name.encode()
            (self.data / name).write_bytes(payload)
            entries.append(f"{identity} {len(payload)} {name}")
            pictures.append({
                "asset": identity, "path": name, "category": "Terrain" if terrain else "Enemies and ground objects",
                "source_sha256": self.sha(payload), "logical_canvas": [32, 32],
                "header_options": 0, "source_palette": "PALETTE_DAT",
                "source_palette_sha256": "a" * 64, "decoded_rgba_sha256": "b" * 64,
                "hd": asset == 0x11002, "registry_or_layout_referenced": not terrain,
            })
        for asset, name in [(0x31000, "intro_AGX.0"), (0x31001, "small_FNT")]:
            (self.data / name).write_bytes(name.encode())
            entries.append(f"{asset:05x} {len(name)} {name}")
        (self.data / "INDEX").write_text("\n".join(entries) + "\n")
        self.expected = {row["asset"]: row for row in pictures[:3]}
        audit = {
            "assets": pictures,
            "sequences": {
                "Enemies and ground objects": [{"name": "Flanker", "base_asset": 0x11000,
                                                 "frames": [0x11000, 0x11001, 0x11002]}],
                "Terrain": [{"name": "Terrain set 1", "frames": [0x21000]}],
            }, "terrain": {"runtime_hd_composition_supported": True},
        }
        self.write(self.hd / "coverage-audit.json", audit)
        self.write(self.hd / "runtime-content-audit.json", {})
        self.candidate = {"job_id": self.job_id, "complete_family": True, "sequences": [{
            "base_asset": 0x11000, "frame_count": 3, "frames": [],
        }]}
        for offset, source in enumerate(pictures[:3]):
            relative = f"jobs/{self.job_id}/generated/frame-{offset}.png"
            artwork = self.hd / relative
            artwork.parent.mkdir(parents=True, exist_ok=True)
            # The queue deliberately checks presence/metadata, not PNG artistry.
            artwork.write_bytes(b"synthetic artwork presence")
            self.candidate["sequences"][0]["frames"].append({
                "frame": offset, "file": relative, "logical_width": 32, "logical_height": 32,
                "origin": [0, 0], "source_sha256": source["source_sha256"], "crop": [0, 0, 128, 128],
            })
        self.candidate_path = self.directory / "candidate.json"
        self.write(self.candidate_path, self.candidate)
        self.review = {
            "status": "approved", "candidate_sha256": self.sha(self.candidate_path.read_bytes()),
            "frame_bindings_sha256": binding_digest(proposal_frames(self.candidate, self.expected)),
            "runtime_qa": f"jobs/{self.job_id}/runtime-review/runtime-qa.json",
            "source_and_all_scale_visual_review": {"description": "retained full visual receipt " * 100},
            "independent_review": {"report_sha256": "c" * 64},
        }
        self.review_path = self.directory / "coordinator-review.json"
        self.write(self.review_path, self.review)
        self.write(self.directory / "job.json", {"owner": "/root/fixture", "targets": []})
        self.ledger_path = Path(self.temporary.name) / "ledger.json"
        self.write(self.ledger_path, {"format_version": 1, "assets": {
            "11002": {"source_sha256": pictures[2]["source_sha256"], "status": "renderreachable",
                      "renderer": {"availability": "verified", "evidence": ["existing exact scene"]}},
        }})
        self.args = argparse.Namespace(data=self.data, audit=self.hd / "coverage-audit.json",
                                      runtime=self.hd / "runtime-content-audit.json", jobs=self.jobs,
                                      ledger=self.ledger_path, terrain_batch=16)

    @staticmethod
    def sha(payload):
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def write(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2) + "\n")

    def build(self, legacy=False):
        with contextlib.redirect_stdout(io.StringIO()):
            if legacy:
                with patch.object(queue, "normalize_ledger", side_effect=lambda ledger, *_: ledger):
                    queue.build(self.args)
            else:
                queue.build(self.args)
        return json.loads(self.ledger_path.read_text())

    def test_round_trip_keeps_decisions_sources_and_complete_external_receipt(self):
        before_receipt = self.review_path.read_bytes()
        legacy = self.build(legacy=True)
        normalized = self.build()
        self.assertEqual(normalized["format_version"], 1)
        self.assertEqual(normalized["ledger_schema"], queue.LEDGER_SCHEMA)
        self.assertEqual(set(normalized["family_reviews"]), {self.job_id})
        family = normalized["family_reviews"][self.job_id]
        self.assertEqual(family["receipt"], {"path": f"jobs/{self.job_id}/coordinator-review.json",
                                            "sha256": self.sha(before_receipt)})
        self.assertEqual(family["frame_bindings_sha256"], self.review["frame_bindings_sha256"])
        self.assertNotIn("source_and_all_scale_visual_review", family)
        for identity, old in legacy["assets"].items():
            new = normalized["assets"][identity]
            self.assertEqual(queue.coordinator_review_for_asset(legacy, identity, self.hd),
                             queue.coordinator_review_for_asset(normalized, identity, self.hd))
            self.assertEqual({k: v for k, v in old.items() if k != "coordinator_review"},
                             {k: v for k, v in new.items() if k != "coordinator_review_ref"})
            self.assertNotIn("coordinator_review", new)
        self.assertEqual(legacy["picture_status_counts"], normalized["picture_status_counts"])
        self.assertEqual(normalized, queue.normalize_ledger(normalized, self.hd))
        self.assertEqual(normalized, self.build())
        self.assertEqual(self.review_path.read_bytes(), before_receipt)
        local_job = json.loads((self.directory / "job.json").read_text())
        self.assertEqual(local_job["coordinator_review"], self.review)
        self.assertLess(len(json.dumps(normalized)), len(json.dumps(legacy)))

    def test_unreviewed_unused_and_native_preservation_entries_remain(self):
        self.review["status"] = "hold"
        self.write(self.review_path, self.review)
        ledger = self.build()
        self.assertEqual(ledger["assets"]["11000"]["status"], "candidate")
        self.assertEqual(ledger["family_reviews"][self.job_id]["status"], "hold")
        self.assertEqual(ledger["assets"]["11002"]["status"], "renderreachable")
        unused = ledger["assets"]["21000"]
        self.assertEqual(unused["status"], "missing")
        self.assertFalse(unused["registry_or_layout_referenced"])
        self.assertNotIn("coordinator_review_ref", unused)
        self.assertEqual(ledger["assets"]["31000"]["kind"], "cinematic_delta")
        self.assertEqual(ledger["assets"]["31001"]["kind"], "bitmap_font")
        self.assertFalse(ledger["assets"]["31000"]["remaster_required"])
        self.review_path.unlink()
        without_review = self.build()
        self.assertEqual(without_review["family_reviews"], {})
        self.assertNotIn("coordinator_review_ref", without_review["assets"]["11000"])
        self.assertEqual(without_review["assets"]["11000"]["status"], "candidate")

    def test_missing_changed_and_stale_candidates_cannot_reuse_approval(self):
        for mutation in ["missing", "changed_binding", "stale_review_hash"]:
            with self.subTest(mutation=mutation):
                candidate = copy.deepcopy(self.candidate)
                review = copy.deepcopy(self.review)
                if mutation == "changed_binding":
                    candidate["sequences"][0]["frames"][0]["crop"] = [0, 0, 256, 256]
                if mutation == "stale_review_hash":
                    review.pop("frame_bindings_sha256")
                    review["candidate_sha256"] = "0" * 64
                self.write(self.candidate_path, candidate)
                self.write(self.review_path, review)
                if mutation == "missing":
                    self.candidate_path.unlink()
                ledger = self.build()
                self.assertEqual(ledger["family_reviews"], {})
                self.assertNotIn("coordinator_review_ref", ledger["assets"]["11000"])
                self.assertNotEqual(ledger["assets"]["11000"]["status"], "reviewed")
                self.assertEqual(ledger["assets"]["11002"]["status"], "renderreachable")

    def test_complete_family_binds_every_job_target_and_rejects_wrong_sources(self):
        for mutation in ["omitted_target", "foreign_target", "changed_source", "wrong_job"]:
            with self.subTest(mutation=mutation):
                candidate = copy.deepcopy(self.candidate)
                if mutation == "omitted_target":
                    candidate["sequences"][0]["frames"].pop()
                elif mutation == "foreign_target":
                    candidate["sequences"][0]["base_asset"] += 1
                elif mutation == "changed_source":
                    candidate["sequences"][0]["frames"][0]["source_sha256"] = "0" * 64
                else:
                    candidate["job_id"] = "another-job"
                self.write(self.candidate_path, candidate)
                ledger = self.build()
                self.assertEqual(ledger["family_reviews"], {})
                self.assertNotEqual(ledger["assets"]["11000"]["status"], "reviewed")
                job = json.loads((self.directory / "job.json").read_text())
                self.assertIn("candidate_error", job)

    def test_metadata_only_candidate_change_retains_exact_frame_map_approval(self):
        self.candidate["review_notes"] = "new artist notes; renderer bindings unchanged"
        self.write(self.candidate_path, self.candidate)
        ledger = self.build()
        self.assertEqual(ledger["assets"]["11000"]["status"], "reviewed")
        self.assertNotEqual(ledger["assets"]["11000"]["candidate"]["sha256"], self.review["candidate_sha256"])
        self.assertEqual(ledger["family_reviews"][self.job_id]["candidate_sha256"], self.review["candidate_sha256"])
        self.assertEqual(ledger["family_reviews"][self.job_id]["frame_bindings_sha256"], self.review["frame_bindings_sha256"])

    def test_derivation_removed_from_candidate_or_review_cannot_bypass_registration_guard(self):
        for location in ["candidate", "review", "both"]:
            candidate, review = copy.deepcopy(self.candidate), copy.deepcopy(self.review)
            if location in ["candidate", "both"]:
                candidate["artwork_derivation"] = {"path": "lineage.json", "sha256": "d" * 64}
            if location in ["review", "both"]:
                review["artwork_derivation"] = {"path": "lineage.json", "sha256": "d" * 64}
            self.write(self.candidate_path, candidate)
            self.write(self.review_path, review)
            with self.subTest(location=location), patch("hd_register_reviewed.approved_job", side_effect=ValueError("bad lineage")) as guard:
                ledger = self.build()
                guard.assert_called_once()
                self.assertEqual(ledger["assets"]["11000"]["status"], "candidate")
                self.assertEqual(ledger["assets"]["11002"]["status"], "renderreachable")
                self.assertEqual(ledger["family_reviews"], {})

    def test_missing_changed_receipt_and_conflicting_identities_fail_safely(self):
        legacy = self.build(legacy=True)
        normalized = queue.normalize_ledger(legacy, self.hd)
        changed = copy.deepcopy(legacy)
        changed["assets"]["11001"]["candidate"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "different candidate identities"):
            queue.normalize_ledger(changed, self.hd)
        changed = copy.deepcopy(legacy)
        changed["assets"]["11001"]["coordinator_review"]["status"] = "hold"
        with self.assertRaisesRegex(ValueError, "external review differ"):
            queue.normalize_ledger(changed, self.hd)
        changed = copy.deepcopy(normalized)
        changed["assets"]["11000"]["coordinator_review_ref"] = "another-job"
        with self.assertRaisesRegex(ValueError, "differs from its job"):
            queue.normalize_ledger(changed, self.hd)
        self.write(self.review_path, {**self.review, "status": "hold"})
        with self.assertRaisesRegex(ValueError, "receipt changed"):
            queue.coordinator_review_for_asset(normalized, "11000", self.hd)
        self.review_path.unlink()
        with self.assertRaises(FileNotFoundError):
            queue.normalize_ledger(legacy, self.hd)
        with self.assertRaises(FileNotFoundError):
            queue.coordinator_review_for_asset(normalized, "11000", self.hd)


if __name__ == "__main__":
    unittest.main()
