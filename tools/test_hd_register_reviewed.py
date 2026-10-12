"""Explicit standalone Terrain selections never approve omitted or animated art."""
import argparse
import contextlib
import copy
import hashlib
import io
import json
import os
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
import hd_job_queue as queue
import hd_register_reviewed as registrar
from hd_candidate_review import binding_digest, proposal_frames


class StandaloneTerrainRegistrationTest(unittest.TestCase):
    # Exact safe12/safe13 membership from the frozen independent source plan.
    SELECTED = [
        ["10530", "10532", "10533", "10534", "10537", "10538", "10539", "1053a", "1053b", "1053c", "1053d", "1053f"],
        ["10540", "10541", "10542", "10543", "10545", "10546", "10547", "10548", "10549", "1054a", "1054b", "1054d", "1054e"],
    ]
    START_ASSET = 0x10530

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name) / "project"
        self.data = Path(temporary.name) / "data"
        self.hd = self.data / "hd"
        self.hd.mkdir(parents=True)
        (self.data / "misc").mkdir()
        (self.project / "src").mkdir(parents=True)
        for name in ["assets.rs", "hd.rs"]:
            (self.project / "src" / name).write_text("synthetic source freshness fixture")
        self.library = self.project / "target/fixture.rlib"
        self.library.parent.mkdir()
        self.library.write_bytes(b"synthetic immutable library; not a real runtime claim")
        os.utime(self.library, ns=(2_000_000_000_000_000_000,) * 2)
        palette = bytes(value // 4 for value in range(256) for _ in range(3))
        self.palette = self.data / "misc/PALETTE_DAT"
        self.palette.write_bytes(palette)
        self.entries = [f"{self.START_ASSET-1:05x} 0 tiles/STARTG1TILES"]
        self.jobs = []
        self.pictures = []
        all_bindings = {}
        for number, selected in enumerate(self.SELECTED):
            start = self.START_ASSET + number * 16
            identity = f"terrain-{start:05x}-{start+15:05x}"
            directory = self.hd / "jobs" / identity
            directory.mkdir(parents=True)
            targets, sequences, records, approvals, masks, artwork = [], [], [], {}, [], {}
            for offset in range(16):
                asset = f"{start + offset:05x}"
                relative = f"misc/source-{asset}"
                payload = struct.pack("<iiiii", 1, 0, 0, 4, 4) + bytes([offset + 1] * 16)
                (self.data / relative).write_bytes(payload)
                self.entries.append(f"{asset} {len(payload)} {relative}")
                target = {"asset": asset, "source_path": relative, "source_sha256": self.sha(payload),
                          "logical_canvas": [4, 4], "source_palette": "PALETTE_DAT",
                          "source_palette_sha256": self.sha(palette), "origin": [0, 0],
                          "terrain_context": {"roles": [], "samples": []}}
                targets.append(target)
                self.pictures.append({**target, "path": relative, "category": "Terrain", "hd": False,
                                      "header_options": 0, "decoded_rgba_sha256": "b" * 64,
                                      "registry_or_layout_referenced": False})
                filename = f"jobs/{identity}/generated/{asset}.png"
                raw = self.hd / filename
                raw.parent.mkdir(exist_ok=True)
                Image.new("RGBA", (8, 8), (offset + 1, offset + 1, offset + 1, 255)).save(raw)
                frame = {"frame": 0, "file": filename, "logical_width": 4, "logical_height": 4,
                         "origin": [0, 0], "source_sha256": target["source_sha256"]}
                record = {"asset": asset, "standalone_verdict": "QUALIFIED_APPROVE" if asset in selected else "HOLD",
                          "selected_frame_binding": frame, "source_payload_sha256": target["source_sha256"],
                          "full_untouched_raw_sha256": self.sha(raw.read_bytes()), "actual_scales": [1, 2, 3, 4]}
                records.append(record)
                if asset not in selected:
                    continue
                all_bindings[asset] = frame
                sequences.append({"base_asset": start + offset, "frame_count": 1, "frames": [frame]})
                artwork[filename] = self.sha(raw.read_bytes())
                approvals[asset] = {"status": "approved", "frame_bindings_sha256": binding_digest({asset: frame}),
                                    "source_sha256": target["source_sha256"], "raw_sha256": artwork[filename],
                                    "record_index": offset}
                mask = {"palette_indices_240_to_255_counts": [0] * 16}
                masks.append({"asset": asset, "source_sha256": target["source_sha256"], "logical_canvas": [4, 4],
                              "source_mask": mask, "hd_masks": [{"scale": scale, "mask": mask} for scale in range(1, 5)]})
            self.write(directory / "peer.json", {"reviewer": "/different_peer", "author": "/author", "records": records})
            peer_ref = self.ref(directory / "peer.json")
            for approval in approvals.values():
                approval["independent_review"] = peer_ref
            inventory = [row["asset"] for row in targets]
            selection = {"full_inventory": inventory, "selected_assets": selected,
                         "original_fallback_assets": sorted(set(inventory) - set(selected))}
            candidate = {"format_version": 1, "job_id": identity, "category": "Terrain",
                         "kind": "contextual_terrain_shard", "complete_family": False,
                         "complete_standalone_selection": True, **selection, "sequences": sequences}
            job = {"format_version": 1, "job_id": identity, "category": "Terrain",
                   "kind": "contextual_terrain_shard", "owner": "/author", "targets": targets}
            self.write(directory / "candidate.json", candidate)
            self.write(directory / "job.json", job)
            candidate_sha = self.sha((directory / "candidate.json").read_bytes())
            digest = binding_digest(proposal_frames(candidate))
            qa = {"candidate_sha256": candidate_sha, "frame_bindings_sha256": digest, "diagnostics": [],
                  "library": "target/fixture.rlib", "library_modified_ns": self.library.stat().st_mtime_ns,
                  "library_sha256": self.sha(self.library.read_bytes()), "source_newer_than_library": False,
                  "any_game_source_newer_than_library": False, "frames": masks, "artwork_sha256": artwork}
            self.write(directory / "runtime-qa.json", qa)
            review = {"status": "approved", "candidate_sha256": candidate_sha, "frame_bindings_sha256": digest,
                      "runtime_qa": f"jobs/{identity}/runtime-qa.json", "source_and_all_scale_visual_review": True,
                      "independent_review": peer_ref,
                      "standalone_selection": {**selection, "material_approvals": approvals}}
            self.jobs.append({"id": identity, "directory": directory, "candidate": candidate,
                              "job": job, "review": review, "qa": qa})
        end = self.START_ASSET + len(self.SELECTED) * 16
        self.entries.append(f"{end:05x} 0 tiles/ENDG1TILES")
        (self.data / "INDEX").write_text("\n".join(self.entries) + "\n")
        self.context_candidate_path = self.hd / "context-candidate.json"
        self.write(self.context_candidate_path, {"sequences": sum([row["candidate"]["sequences"] for row in self.jobs], [])})
        self.context_path = self.hd / "combined-context.json"
        authority = {"candidate": self.ref(self.context_candidate_path), "selected_assets": sorted(all_bindings),
                     "frame_bindings_sha256": binding_digest(all_bindings), "technical_verdict": "QUALIFIED_CONTEXT_INTEGRATION"}
        for key in ["baseline", "future_projection"]:
            path = self.hd / f"context-{key}.json"
            self.write(path, {"scope": "Synthetic proof contract only; no real artwork or gameplay acceptance."})
            authority[key] = self.ref(path)
        proof = self.hd / "actual-synthetic-changed-case-proof.json"
        self.write(proof, {"scope": "Synthetic declared-case fixture; no game pixels or real artistic approval."})
        closure_path = self.hd / "context-changed_case_closure.json"
        self.write(closure_path, {"status": "CLOSED_QUALIFIED_CONTEXT", "candidate_sha256": authority["candidate"]["sha256"],
                                 "frame_bindings_sha256": binding_digest(all_bindings),
                                 "baseline_sha256": authority["baseline"]["sha256"], "future_projection_sha256": authority["future_projection"]["sha256"],
                                 "changed_case_proof": self.ref(proof)})
        authority["changed_case_closure"] = self.ref(closure_path)
        self.write(self.context_path, {"reviewer": "/context_peer", "author": "/author", "standalone_selection_context": authority})
        for row in self.jobs:
            row["review"]["standalone_selection"]["contextual_approval"] = {
                "receipt": self.ref(self.context_path), "selected_assets": row["candidate"]["selected_assets"],
                "selected_frame_bindings_sha256": binding_digest(proposal_frames(row["candidate"]))}
            self.write(row["directory"] / "coordinator-review.json", row["review"])
        self.audit = {"assets": self.pictures, "sequences": {"Terrain": [{"name": "Terrain set 1", "frames": list(range(self.START_ASSET, end))}]},
                      "terrain": {"runtime_hd_composition_supported": True}}
        self.write(self.hd / "coverage-audit.json", self.audit)
        self.write(self.hd / "runtime-content-audit.json", {})

    @staticmethod
    def sha(payload):
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def write(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2) + "\n")

    def ref(self, path):
        return {"path": str(path.relative_to(self.hd)), "sha256": self.sha(path.read_bytes())}

    def approve(self, number=0):
        return registrar.approved_job(self.hd, self.jobs[number]["id"], self.project)

    def save(self, field, value, number=0):
        row = self.jobs[number]
        self.write(row["directory"] / {"candidate": "candidate.json", "job": "job.json", "review": "coordinator-review.json", "qa": "runtime-qa.json"}[field], value)

    def build(self):
        args = argparse.Namespace(data=self.data, audit=self.hd / "coverage-audit.json", runtime=self.hd / "runtime-content-audit.json",
                                  jobs=self.hd / "jobs", ledger=self.hd / "ledger.json", terrain_batch=16)
        with patch.object(queue, "__file__", str(self.project / "tools/hd_job_queue.py")), contextlib.redirect_stdout(io.StringIO()):
            queue.build(args)
        return json.loads(args.ledger.read_text())

    def test_safe12_plus13_register_exactly25_and_leave_seven_fallbacks_unapproved(self):
        approved = set()
        for number in [0, 1]:
            candidate, review, rows = self.approve(number)
            self.assertFalse(candidate["complete_family"])
            approved.update(rows)
            self.assertEqual(len(rows), [12, 13][number])
        self.assertEqual(len(approved), 25)
        ledger = self.build()
        for asset, row in ledger["assets"].items():
            self.assertEqual(row["status"], "reviewed" if asset in approved else "inprogress")
            self.assertEqual("coordinator_review_ref" in row, asset in approved)
            self.assertFalse(row["registry_or_layout_referenced"])
        self.assertEqual(ledger["picture_status_counts"], {"reviewed": 25, "inprogress": 7})

    def test_registration_only_adds_selected_sequences_and_records_honest_scope(self):
        # The real registrar extends an already nonempty accepted pack.
        seed = {"base_asset": 0x20001, "frame_count": 1, "frames": [{"frame": 0,
                "file": "existing.png", "logical_width": 4, "logical_height": 4, "origin": [0, 0], "source_sha256": "a" * 64}]}
        self.write(self.hd / "hd.json", {"format_version": 1, "sequences": [seed]})
        self.write(self.hd / "provenance.json", {})
        argv = ["registrar", "--hd-root", str(self.hd)]
        for row in self.jobs:
            argv.extend(["--job", row["id"]])
        with patch.object(registrar, "__file__", str(self.project / "tools/hd_register_reviewed.py")), patch("sys.argv", argv), contextlib.redirect_stdout(io.StringIO()):
            registrar.main()
        active = proposal_frames(json.loads((self.hd / "hd.json").read_text()))
        self.assertEqual(set(active), set(sum(self.SELECTED, [])) | {"20001"})
        additions = json.loads((self.hd / "provenance.json").read_text())["reviewed_sequence_additions"]
        self.assertEqual([row["frames"] for row in additions], [12, 13])
        self.assertEqual(sum(len(row["original_fallback_assets"]) for row in additions), 7)
        self.assertTrue(all(row["approval_scope"] == "complete_standalone_terrain_selection" for row in additions))

    def test_bad_partitions_categories_sequences_and_sources_are_rejected(self):
        for mutation in ["duplicate_selected", "duplicate_fallback", "missing_fallback", "overlap", "extra_inventory", "omitted_inventory",
                         "omitted_original_job_target", "wrong_category", "wrong_kind", "job_wrong_category", "animation", "partial_animation",
                         "no_explicit_claim", "whole_claim", "wrong_source", "wrong_canvas", "origin", "extra_sequence", "duplicate_sequence"]:
            with self.subTest(mutation=mutation):
                candidate, job = copy.deepcopy(self.jobs[0]["candidate"]), copy.deepcopy(self.jobs[0]["job"])
                if mutation == "duplicate_selected": candidate["selected_assets"].append(candidate["selected_assets"][0])
                elif mutation == "duplicate_fallback": candidate["original_fallback_assets"].append(candidate["original_fallback_assets"][0])
                elif mutation == "missing_fallback": candidate["original_fallback_assets"].pop()
                elif mutation == "overlap": candidate["original_fallback_assets"].append(candidate["selected_assets"][0])
                elif mutation == "extra_inventory": candidate["full_inventory"].append("10550")
                elif mutation == "omitted_inventory": candidate["full_inventory"].pop()
                elif mutation == "omitted_original_job_target":
                    candidate["full_inventory"].remove("10531"); candidate["original_fallback_assets"].remove("10531"); job["targets"].pop(1)
                elif mutation == "wrong_category": candidate["category"] = "Enemies and ground objects"
                elif mutation == "wrong_kind": candidate["kind"] = "complete_family"
                elif mutation == "job_wrong_category": job["category"] = "Enemies and ground objects"
                elif mutation in ["animation", "partial_animation"]:
                    candidate["sequences"][0]["frame_count"] = 2
                    if mutation == "animation": candidate["sequences"][0]["frames"].append({**candidate["sequences"][0]["frames"][0], "frame": 1})
                elif mutation == "no_explicit_claim": candidate.pop("complete_standalone_selection")
                elif mutation == "whole_claim": candidate["complete_family"] = True
                elif mutation == "wrong_source": candidate["sequences"][0]["frames"][0]["source_sha256"] = "0" * 64
                elif mutation == "wrong_canvas": candidate["sequences"][0]["frames"][0]["logical_width"] = 8
                elif mutation == "origin": candidate["sequences"][0]["frames"][0]["origin"] = [1, 0]
                elif mutation == "extra_sequence": candidate["sequences"].append({"base_asset": 0x10550, "frame_count": 1, "frames": candidate["sequences"][0]["frames"]})
                else: candidate["sequences"].append(candidate["sequences"][0])
                self.save("candidate", candidate); self.save("job", job)
                with self.assertRaises((ValueError, KeyError)):
                    self.approve()

    def test_missing_peer_held_decision_wrong_binding_and_unsafe_decision_index_reject(self):
        asset = self.SELECTED[0][0]
        for mutation in ["missing_peer", "stale_peer", "missing_material", "held_decision", "self_review", "wrong_record_binding", "wrong_record_raw",
                         "negative_index", "boolean_index", "oversize_index", "wrong_asset_index", "wrong_material_binding", "wrong_material_raw", "missing_context", "context_hold", "context_wrong_binding"]:
            with self.subTest(mutation=mutation):
                review = copy.deepcopy(self.jobs[0]["review"])
                approval = review["standalone_selection"]["material_approvals"][asset]
                peer_path = self.jobs[0]["directory"] / "peer.json"
                original_peer = peer_path.read_bytes()
                peer = json.loads(original_peer)
                original_context = self.context_path.read_bytes()
                if mutation == "missing_peer": approval["independent_review"]["path"] = "missing.json"
                elif mutation == "stale_peer": approval["independent_review"]["sha256"] = "0" * 64
                elif mutation == "missing_material": review["standalone_selection"]["material_approvals"].pop(asset)
                elif mutation == "held_decision": peer["records"][0]["standalone_verdict"] = "HOLD"
                elif mutation == "self_review": peer["reviewer"] = peer["author"]
                elif mutation == "wrong_record_binding": peer["records"][0]["selected_frame_binding"]["origin"] = [1, 0]
                elif mutation == "wrong_record_raw": peer["records"][0]["full_untouched_raw_sha256"] = "0" * 64
                elif mutation == "negative_index": approval["record_index"] = -1
                elif mutation == "boolean_index": approval["record_index"] = True
                elif mutation == "oversize_index": approval["record_index"] = 10000
                elif mutation == "wrong_asset_index": approval["record_index"] = 1
                elif mutation == "wrong_material_binding": approval["frame_bindings_sha256"] = "0" * 64
                elif mutation == "wrong_material_raw": approval["raw_sha256"] = "0" * 64
                elif mutation == "missing_context": review["standalone_selection"].pop("contextual_approval")
                else:
                    context = json.loads(original_context)
                    if mutation == "context_hold": context["standalone_selection_context"]["technical_verdict"] = "HOLD"
                    else:
                        context["standalone_selection_context"]["frame_bindings_sha256"] = "0" * 64
                    self.write(self.context_path, context)
                    review["standalone_selection"]["contextual_approval"]["receipt"] = self.ref(self.context_path)
                if peer != json.loads(original_peer):
                    self.write(peer_path, peer)
                    for item in review["standalone_selection"]["material_approvals"].values():
                        item["independent_review"] = self.ref(peer_path)
                self.save("review", review)
                with self.assertRaises((ValueError, KeyError, OSError)):
                    self.approve()
                peer_path.write_bytes(original_peer); self.context_path.write_bytes(original_context)

    def test_stale_missing_duplicate_and_changed_qa_reject(self):
        for mutation in ["stale_source", "stale_any_source", "missing_library_hash", "changed_library", "missing_scale", "duplicate_scale", "duplicate_asset", "missing_asset", "wrong_source", "wrong_canvas", "stale_candidate", "diagnostics"]:
            with self.subTest(mutation=mutation):
                qa = copy.deepcopy(self.jobs[0]["qa"])
                if mutation == "stale_source": qa["source_newer_than_library"] = True
                elif mutation == "stale_any_source": qa["any_game_source_newer_than_library"] = True
                elif mutation == "missing_library_hash": qa.pop("library_sha256")
                elif mutation == "changed_library": qa["library_sha256"] = "0" * 64
                elif mutation == "missing_scale": qa["frames"][0]["hd_masks"].pop()
                elif mutation == "duplicate_scale": qa["frames"][0]["hd_masks"].append(qa["frames"][0]["hd_masks"][0])
                elif mutation == "duplicate_asset": qa["frames"].append(qa["frames"][0])
                elif mutation == "missing_asset": qa["frames"].pop()
                elif mutation == "wrong_source": qa["frames"][0]["source_sha256"] = "0" * 64
                elif mutation == "wrong_canvas": qa["frames"][0]["logical_canvas"] = [8, 4]
                elif mutation == "stale_candidate": qa["candidate_sha256"] = "0" * 64
                else: qa["diagnostics"] = ["actual loader failure"]
                self.save("qa", qa)
                with self.assertRaises(ValueError): self.approve()

    def test_unsafe_original_index_and_wrong_inventory_reject_even_with_matching_candidate_and_qa(self):
        original = (self.data / "INDEX").read_text()
        for mutation in ["duplicate_id", "unsafe_path", "not_terrain", "wrong_size", "changed_original", "changed_palette", "wrong_original_canvas"]:
            with self.subTest(mutation=mutation):
                job = copy.deepcopy(self.jobs[0]["job"])
                source = self.data / job["targets"][0]["source_path"]
                payload, palette = source.read_bytes(), self.palette.read_bytes()
                index = original
                if mutation == "duplicate_id": index += self.entries[1] + "\n"
                elif mutation == "unsafe_path": index = index.replace("misc/source-10530", "../escaped")
                elif mutation == "not_terrain": index = index.replace("1052f 0", "10531 0")
                elif mutation == "wrong_size": index = index.replace("10530 36", "10530 37")
                elif mutation == "changed_original": source.write_bytes(payload[:-1] + b"\x02")
                elif mutation == "changed_palette": self.palette.write_bytes(b"x" * 768)
                else: job["targets"][0]["logical_canvas"] = [8, 4]
                (self.data / "INDEX").write_text(index); self.save("job", job)
                with self.assertRaises(ValueError): self.approve()
                source.write_bytes(payload); self.palette.write_bytes(palette)

    def test_invalid_review_keeps_only_candidate_status_and_historical_hold_is_untouched(self):
        history = self.hd / "old-whole-hold.json"
        history.write_text('{"status":"HOLD","scope":"whole16 old artwork"}\n')
        before = history.read_bytes()
        review = copy.deepcopy(self.jobs[0]["review"])
        review["standalone_selection"]["material_approvals"].pop(self.SELECTED[0][0])
        self.save("review", review)
        ledger = self.build()
        self.assertEqual(ledger["assets"]["10530"]["status"], "candidate")
        self.assertEqual(ledger["assets"]["10531"]["status"], "inprogress")
        self.assertNotIn("coordinator_review_ref", ledger["assets"]["10530"])
        self.assertEqual(history.read_bytes(), before)

    def test_corrupted_truncated_undersized_and_wrong_aspect_pngs_reject_despite_fake_matching_hash_claims(self):
        asset = self.SELECTED[0][0]
        for mutation in ["corrupt", "truncated", "undersized", "wrong_aspect"]:
            with self.subTest(mutation=mutation):
                qa, review = copy.deepcopy(self.jobs[0]["qa"]), copy.deepcopy(self.jobs[0]["review"])
                filename = self.jobs[0]["candidate"]["sequences"][0]["frames"][0]["file"]
                raw = self.hd / filename
                original = raw.read_bytes()
                if mutation == "corrupt": raw.write_bytes(b"not a PNG")
                elif mutation == "truncated": raw.write_bytes(original[:20])
                else: Image.new("RGBA", (4, 4) if mutation == "undersized" else (9, 8), (40, 40, 40, 255)).save(raw)
                digest = self.sha(raw.read_bytes())
                qa["artwork_sha256"][filename] = digest
                peer_path = self.jobs[0]["directory"] / "peer.json"
                original_peer = peer_path.read_bytes()
                peer = json.loads(original_peer)
                peer["records"][0]["full_untouched_raw_sha256"] = digest
                self.write(peer_path, peer)
                for approval in review["standalone_selection"]["material_approvals"].values():
                    approval["independent_review"] = self.ref(peer_path)
                review["standalone_selection"]["material_approvals"][asset]["raw_sha256"] = digest
                self.save("qa", qa); self.save("review", review)
                with self.assertRaises((ValueError, OSError)): self.approve()
                raw.write_bytes(original); peer_path.write_bytes(original_peer)

    def test_context_restriction_candidate_baseline_and_closure_hashes_are_bound(self):
        for mutation in ["wrong_subset", "wrong_subset_digest", "changed_candidate", "changed_baseline", "changed_closure", "missing_projection"]:
            with self.subTest(mutation=mutation):
                review = copy.deepcopy(self.jobs[0]["review"])
                context = review["standalone_selection"]["contextual_approval"]
                payloads = {}
                if mutation == "wrong_subset": context["selected_assets"].pop()
                elif mutation == "wrong_subset_digest": context["selected_frame_bindings_sha256"] = "0" * 64
                elif mutation == "missing_projection":
                    peer = json.loads(self.context_path.read_text())
                    peer["standalone_selection_context"].pop("future_projection")
                    payloads[self.context_path] = self.context_path.read_bytes()
                    self.write(self.context_path, peer); context["receipt"] = self.ref(self.context_path)
                else:
                    path = self.context_candidate_path if mutation == "changed_candidate" else self.hd / ("context-baseline.json" if mutation == "changed_baseline" else "context-changed_case_closure.json")
                    payloads[path] = path.read_bytes()
                    path.write_text('{"changed":"proof does not match its immutable receipt"}')
                self.save("review", review)
                with self.assertRaises((ValueError, OSError)): self.approve()
                for path, payload in payloads.items(): path.write_bytes(payload)

    def test_forged_terrain_classification_cannot_admit_actual_nonterrain_catalog_id(self):
        # Metadata relabeling alone cannot turn an animation's ID into Terrain.
        index = (self.data / "INDEX").read_text()
        (self.data / "INDEX").write_text(index.replace("1052f 0 tiles/STARTG1TILES", "1053f 0 tiles/STARTG1TILES"))
        with self.assertRaises(ValueError): self.approve()

    def test_recursive_game_source_change_cannot_reuse_old_standalone_qa(self):
        source = self.project / "src/nested/simulation.rs"
        source.parent.mkdir()
        source.write_text("changed after review")
        os.utime(source, ns=(self.library.stat().st_mtime_ns + 1,) * 2)
        with self.assertRaisesRegex(ValueError, "game source changed"): self.approve()

    def test_original_fallback_cannot_silently_keep_an_existing_hd_binding(self):
        target = self.jobs[0]["job"]["targets"][1]
        seed = {"base_asset": 0x10531, "frame_count": 1, "frames": [{"frame": 0,
                "file": "already-registered.png", "logical_width": 4, "logical_height": 4,
                "origin": [0, 0], "source_sha256": target["source_sha256"]}]}
        self.write(self.hd / "hd.json", {"format_version": 1, "sequences": [seed]})
        self.write(self.hd / "provenance.json", {})
        before = {name: (self.hd / name).read_bytes() for name in ["hd.json", "provenance.json"]}
        argv = ["registrar", "--hd-root", str(self.hd), "--job", self.jobs[0]["id"]]
        with patch.object(registrar, "__file__", str(self.project / "tools/hd_register_reviewed.py")), patch("sys.argv", argv):
            with self.assertRaisesRegex(ValueError, "original fallback already"): registrar.main()
        self.assertEqual(before, {name: (self.hd / name).read_bytes() for name in before})

    def test_booleans_duplicate_targets_and_duplicate_sequences_are_not_complete_definitions(self):
        for mutation in ["boolean_frame_count", "boolean_frame", "boolean_scale", "duplicate_candidate_target", "duplicate_job_target", "duplicate_sequence"]:
            with self.subTest(mutation=mutation):
                candidate, job, qa = [copy.deepcopy(self.jobs[0][key]) for key in ["candidate", "job", "qa"]]
                if mutation == "boolean_frame_count": candidate["sequences"][0]["frame_count"] = True
                elif mutation == "boolean_frame": candidate["sequences"][0]["frames"][0]["frame"] = False
                elif mutation == "boolean_scale": qa["frames"][0]["hd_masks"][0]["scale"] = True
                elif mutation == "duplicate_candidate_target":
                    candidate["targets"] = [{"asset": f"{sequence['base_asset']:05x}", **sequence["frames"][0]} for sequence in candidate["sequences"]]
                    candidate["targets"].append(candidate["targets"][0])
                elif mutation == "duplicate_job_target": job["targets"].append(job["targets"][0])
                else: candidate["sequences"].append(candidate["sequences"][0])
                self.save("candidate", candidate); self.save("job", job); self.save("qa", qa)
                with self.assertRaises(ValueError): self.approve()

    def test_stale_actual_raw_or_library_bytes_reject_and_do_not_write_pack(self):
        for mutation in ["raw", "library"]:
            with self.subTest(mutation=mutation):
                path = self.hd / self.jobs[0]["candidate"]["sequences"][0]["frames"][0]["file"] if mutation == "raw" else self.library
                payload, timestamp = path.read_bytes(), path.stat().st_mtime_ns
                path.write_bytes(payload + b"changed after exact review")
                # Even preserved mtime cannot disguise a different byte hash.
                os.utime(path, ns=(timestamp, timestamp))
                with self.assertRaisesRegex(ValueError, "raw artwork changed|library bytes changed"): self.approve()
                path.write_bytes(payload); os.utime(path, ns=(timestamp, timestamp))

    def test_original_index_symlink_cannot_escape_data_with_matching_size_and_hash(self):
        source = self.data / self.jobs[0]["job"]["targets"][0]["source_path"]
        payload = source.read_bytes()
        outside = self.data.parent / "outside-original"
        outside.write_bytes(payload)
        source.unlink(); source.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "INDEX path escapes"): self.approve()

    def test_correctly_hashed_unrelated_future_projection_or_closure_cannot_satisfy_context(self):
        for mutation in ["future_projection", "closure_candidate", "closure_bindings", "closure_baseline", "closure_proof"]:
            with self.subTest(mutation=mutation):
                review = copy.deepcopy(self.jobs[0]["review"])
                context = json.loads(self.context_path.read_text())
                original_context = self.context_path.read_bytes()
                closure_path = self.hd / "context-changed_case_closure.json"
                original_closure = closure_path.read_bytes()
                authority = context["standalone_selection_context"]
                closure = json.loads(original_closure)
                if mutation == "future_projection":
                    path = self.hd / "different-future.json"
                    self.write(path, {"different": "future scope not closed by the actual case receipt"})
                    authority["future_projection"] = self.ref(path)
                elif mutation == "closure_candidate": closure["candidate_sha256"] = "0" * 64
                elif mutation == "closure_bindings": closure["frame_bindings_sha256"] = "0" * 64
                elif mutation == "closure_baseline": closure["baseline_sha256"] = "0" * 64
                else: closure["changed_case_proof"]["sha256"] = "0" * 64
                if mutation != "future_projection":
                    self.write(closure_path, closure); authority["changed_case_closure"] = self.ref(closure_path)
                self.write(self.context_path, context)
                review["standalone_selection"]["contextual_approval"]["receipt"] = self.ref(self.context_path)
                self.save("review", review)
                with self.assertRaises(ValueError): self.approve()
                self.context_path.write_bytes(original_context); closure_path.write_bytes(original_closure)

    def test_complete_family_legacy_path_still_accepts_all_frames_and_rejects_partial_animation(self):
        row = self.jobs[0]
        candidate = copy.deepcopy(row["candidate"])
        candidate.pop("complete_standalone_selection")
        candidate["complete_family"] = True
        candidate["sequences"] = [{"base_asset": 0x10530, "frame_count": 16, "frames": []}]
        for index, target in enumerate(row["job"]["targets"]):
            candidate["sequences"][0]["frames"].append({"frame": index,
                "file": f"jobs/{row['id']}/generated/{target['asset']}.png", "logical_width": 4, "logical_height": 4,
                "origin": [0, 0], "source_sha256": target["source_sha256"]})
        frames = proposal_frames(candidate)
        qa = copy.deepcopy(row["qa"])
        qa["frame_bindings_sha256"] = binding_digest(frames)
        qa["frames"] = [{"asset": asset, "source_sha256": frame["source_sha256"], "logical_canvas": [4, 4],
                        "source_mask": {"palette_indices_240_to_255_counts": [0] * 16},
                        "hd_masks": [{"scale": n, "mask": {"palette_indices_240_to_255_counts": [0] * 16}} for n in range(1, 5)]} for asset, frame in frames.items()]
        qa["artwork_sha256"] = {frame["file"]: self.sha((self.hd / frame["file"]).read_bytes()) for frame in frames.values()}
        review = copy.deepcopy(row["review"])
        review["frame_bindings_sha256"] = binding_digest(frames)
        review.pop("standalone_selection")
        self.save("candidate", candidate); self.save("review", review); self.save("qa", qa)
        self.assertEqual(len(self.approve()[2]), 16)
        candidate["sequences"][0]["frames"].pop()
        self.save("candidate", candidate)
        with self.assertRaisesRegex(ValueError, "omits source IDs"): self.approve()


class CarriedRegisteredTerrainRegistrationTest(unittest.TestCase):
    """Master74 adds two definitions while its fourteen active siblings stay exact."""
    START_ASSET = 0x2059d
    SELECTED = [["205a3", "205a4"]]
    sha = staticmethod(StandaloneTerrainRegistrationTest.sha)
    write = staticmethod(StandaloneTerrainRegistrationTest.write)
    ref = StandaloneTerrainRegistrationTest.ref
    approve = StandaloneTerrainRegistrationTest.approve
    save = StandaloneTerrainRegistrationTest.save

    def setUp(self):
        StandaloneTerrainRegistrationTest.setUp(self)
        row = self.jobs[0]
        peer = json.loads((row["directory"] / "peer.json").read_text())
        carried = [record for record in peer["records"] if record["asset"] not in self.SELECTED[0]]
        self.carried = {record["asset"]: record["selected_frame_binding"] for record in carried}
        self.baseline = {"format_version": 1, "sequences": [
            {"base_asset": int(asset, 16), "frame_count": 1, "frames": [frame]}
            for asset, frame in self.carried.items()]}
        self.write(self.hd / "hd.json", self.baseline)
        accepted = copy.deepcopy(row["qa"])
        accepted["frame_bindings_sha256"] = binding_digest(self.carried)
        accepted["frames"] = [{"asset": asset, "source_sha256": frame["source_sha256"], "logical_canvas": [4, 4],
                              "hd_masks": [{"scale": n} for n in range(1, 5)]}
                             for asset, frame in self.carried.items()]
        accepted["artwork_sha256"] = {frame["file"]: self.sha((self.hd / frame["file"]).read_bytes())
                                      for frame in self.carried.values()}
        self.accepted_path = self.hd / "accepted-carried-runtime-qa.json"
        self.write(self.accepted_path, accepted)
        self.write(self.hd / "provenance.json", {"registered_frame_count": 14, "reviewed_sequence_additions": [{
            "job_id": row["id"], "assets": sorted(self.carried), "frames": 14,
            "frame_bindings_sha256": binding_digest(self.carried), "runtime_qa": self.ref(self.accepted_path)["path"]}]})
        candidate = copy.deepcopy(row["candidate"])
        candidate["original_fallback_assets"] = []
        candidate["carried_registered_assets"] = sorted(self.carried)
        candidate["carried_registered_identity"] = {
            "baseline": self.ref(self.hd / "hd.json"), "provenance": self.ref(self.hd / "provenance.json"),
            "registration_record_index": 0, "accepted_runtime_qa": self.ref(self.accepted_path),
            "frame_bindings_sha256": binding_digest(self.carried),
            "frames": {record["asset"]: {"frame_binding": record["selected_frame_binding"],
                        "source_sha256": record["source_payload_sha256"], "raw_sha256": record["full_untouched_raw_sha256"]}
                       for record in carried}}
        self.resign(candidate)
        self.write(self.hd / "context-future_projection.json", {
            "format_version": 1, "sequences": self.baseline["sequences"] + candidate["sequences"]})
        self.reseal_context(baseline=self.ref(self.hd / "hd.json"),
                            future=self.ref(self.hd / "context-future_projection.json"))

    def resign(self, candidate):
        """Reseal hypothetical claims so tests reach the actual semantic guards."""
        digest = binding_digest(proposal_frames(candidate))
        for key in ["qa", "review"]:
            self.jobs[0][key]["frame_bindings_sha256"] = digest
        self.resign_identity(candidate)

    def resign_identity(self, candidate):
        row = self.jobs[0]
        row["candidate"] = candidate
        self.save("candidate", candidate)
        candidate_sha = self.ref(row["directory"] / "candidate.json")["sha256"]
        for key in ["qa", "review"]:
            row[key]["candidate_sha256"] = candidate_sha
        evidence = row["review"]["standalone_selection"]
        for key in ["full_inventory", "selected_assets", "original_fallback_assets", "carried_registered_assets", "carried_registered_identity"]:
            if key in candidate:
                evidence[key] = copy.deepcopy(candidate[key])
            else:
                evidence.pop(key, None)
        self.save("qa", row["qa"]); self.save("review", row["review"])

    def reseal_context(self, baseline=None, future=None, proposal=None):
        context = json.loads(self.context_path.read_text())
        authority = context["standalone_selection_context"]
        if baseline is not None: authority["baseline"] = baseline
        if future is not None: authority["future_projection"] = future
        if proposal is not None:
            self.write(self.context_candidate_path, proposal)
            authority["candidate"] = self.ref(self.context_candidate_path)
            bindings = proposal_frames(proposal)
            authority["selected_assets"] = sorted(bindings)
            authority["frame_bindings_sha256"] = binding_digest(bindings)
        closure_path = self.hd / "context-changed_case_closure.json"
        closure = json.loads(closure_path.read_text())
        for field, value in [("candidate_sha256", authority["candidate"]["sha256"]),
                             ("frame_bindings_sha256", authority["frame_bindings_sha256"]),
                             ("baseline_sha256", authority["baseline"]["sha256"]),
                             ("future_projection_sha256", authority["future_projection"]["sha256"])]:
            closure[field] = value
        self.write(closure_path, closure)
        authority["changed_case_closure"] = self.ref(closure_path)
        self.write(self.context_path, context)
        self.jobs[0]["review"]["standalone_selection"]["contextual_approval"]["receipt"] = self.ref(self.context_path)
        self.save("review", self.jobs[0]["review"])

    @contextlib.contextmanager
    def original_fixture(self):
        files = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in self.hd.rglob("*") if path.is_file()}
        jobs = copy.deepcopy(self.jobs)
        try:
            yield
        finally:
            for path in self.hd.rglob("*"):
                if path.is_file() and path not in files: path.unlink()
            for path, (payload, stamp) in files.items():
                path.write_bytes(payload); os.utime(path, ns=(stamp, stamp))
            self.jobs = jobs

    def test_exact_two_new_fourteen_carried_contract_passes_without_approving_siblings_again(self):
        candidate, review, rows = self.approve()
        self.assertEqual(set(rows), {"205a3", "205a4"})
        self.assertEqual(len(candidate["full_inventory"]), 16)
        self.assertEqual(len(candidate["carried_registered_assets"]), 14)
        self.assertEqual(candidate["original_fallback_assets"], [])
        self.assertEqual(set(review["standalone_selection"]["material_approvals"]), set(rows))

    def test_real_registration_adds_only_two_and_preserves_all_fourteen_complete_frames(self):
        before = proposal_frames(json.loads((self.hd / "hd.json").read_text()))
        argv = ["registrar", "--hd-root", str(self.hd), "--job", self.jobs[0]["id"]]
        with patch.object(registrar, "__file__", str(self.project / "tools/hd_register_reviewed.py")), patch("sys.argv", argv), contextlib.redirect_stdout(io.StringIO()):
            registrar.main()  # Temporary synthetic pack only; no production invocation.
        active = proposal_frames(json.loads((self.hd / "hd.json").read_text()))
        self.assertEqual(len(active), 16)
        self.assertEqual({asset: active[asset] for asset in before}, before)
        additions = json.loads((self.hd / "provenance.json").read_text())["reviewed_sequence_additions"]
        self.assertEqual([row["frames"] for row in additions], [14, 2])
        self.assertEqual(additions[-1]["assets"], ["205a3", "205a4"])
        self.assertEqual(additions[-1]["approval_scope"], "complete_standalone_terrain_selection_with_unchanged_registered_siblings")
        self.assertEqual(additions[-1]["carried_registered_assets"], sorted(before))

    def test_duplicate_new_request_is_rejected_without_pack_write(self):
        before = {name: (self.hd / name).read_bytes() for name in ["hd.json", "provenance.json"]}
        argv = ["registrar", "--hd-root", str(self.hd), "--job", self.jobs[0]["id"], "--job", self.jobs[0]["id"]]
        with patch.object(registrar, "__file__", str(self.project / "tools/hd_register_reviewed.py")), patch("sys.argv", argv):
            with self.assertRaisesRegex(ValueError, "duplicate registered ID"): registrar.main()
        self.assertEqual(before, {name: (self.hd / name).read_bytes() for name in before})

    def test_carried_partition_category_cross_job_and_animation_mismatches_reject(self):
        for mutation in ["missing_carried", "duplicate_carried", "new_overlap", "fallback_overlap", "fallback_instead_of_carry",
                         "foreign_carried", "short_inventory", "cross_job", "category", "kind", "whole_family",
                         "no_explicit_selection", "animation", "partial_animation", "boolean_count", "boolean_frame",
                         "duplicate_sequence", "duplicate_target"]:
            with self.subTest(mutation=mutation), self.original_fixture():
                candidate = copy.deepcopy(self.jobs[0]["candidate"])
                if mutation == "missing_carried": candidate["carried_registered_assets"].pop()
                elif mutation == "duplicate_carried": candidate["carried_registered_assets"].append("2059d")
                elif mutation == "new_overlap": candidate["carried_registered_assets"].append("205a3")
                elif mutation == "fallback_overlap": candidate["original_fallback_assets"] = ["2059d"]
                elif mutation == "fallback_instead_of_carry":
                    candidate["original_fallback_assets"] = candidate.pop("carried_registered_assets"); candidate.pop("carried_registered_identity")
                elif mutation == "foreign_carried": candidate["carried_registered_assets"][0] = "10530"
                elif mutation == "short_inventory": candidate["full_inventory"].pop()
                elif mutation == "cross_job":
                    self.jobs[0]["job"]["job_id"] = "terrain-10530-1053f"
                    self.save("job", self.jobs[0]["job"])
                elif mutation == "category": candidate["category"] = "Enemies"
                elif mutation == "kind": candidate["kind"] = "animation_sequence"
                elif mutation == "whole_family": candidate["complete_family"] = True
                elif mutation == "no_explicit_selection": candidate.pop("complete_standalone_selection")
                elif mutation == "animation":
                    candidate["sequences"][0]["frame_count"] = 2
                    candidate["sequences"][0]["frames"].append({**candidate["sequences"][0]["frames"][0], "frame": 1})
                elif mutation == "partial_animation": candidate["sequences"][0]["frame_count"] = 2
                elif mutation == "boolean_count": candidate["sequences"][0]["frame_count"] = True
                elif mutation == "boolean_frame": candidate["sequences"][0]["frames"][0]["frame"] = False
                elif mutation == "duplicate_sequence": candidate["sequences"].append(candidate["sequences"][0])
                else:
                    self.jobs[0]["job"]["targets"].append(self.jobs[0]["job"]["targets"][0]); self.save("job", self.jobs[0]["job"])
                self.resign_identity(candidate)
                if mutation == "fallback_instead_of_carry":
                    # The legacy original-fallback schema still parses, but
                    # cannot register over already active siblings.
                    argv = ["registrar", "--hd-root", str(self.hd), "--job", self.jobs[0]["id"]]
                    with patch.object(registrar, "__file__", str(self.project / "tools/hd_register_reviewed.py")), patch("sys.argv", argv):
                        with self.assertRaisesRegex(ValueError, "original fallback already"): registrar.main()
                else:
                    with self.assertRaises(ValueError): self.approve()

    def test_changed_carried_complete_binding_rejects_even_with_rehashed_candidate(self):
        for mutation in ["raw_path", "crop", "canvas", "origin", "source", "optional_policy", "frame_index", "omitted_record", "extra_record", "digest"]:
            with self.subTest(mutation=mutation), self.original_fixture():
                candidate = copy.deepcopy(self.jobs[0]["candidate"])
                identity = candidate["carried_registered_identity"]
                record = identity["frames"]["2059d"]
                frame = record["frame_binding"]
                if mutation == "raw_path": frame["file"] = identity["frames"]["2059e"]["frame_binding"]["file"]
                elif mutation == "crop": frame["crop"] = [0, 0, 4, 4]
                elif mutation == "canvas": frame["logical_width"] = 8
                elif mutation == "origin": frame["origin"] = [1, 0]
                elif mutation == "source": record["source_sha256"] = "0" * 64
                elif mutation == "optional_policy": frame["native_nearest_cues"] = [[0, 0]]
                elif mutation == "frame_index": frame["frame"] = 1
                elif mutation == "omitted_record": identity["frames"].pop("2059d")
                elif mutation == "extra_record": identity["frames"]["205a3"] = record
                else: identity["frame_bindings_sha256"] = "0" * 64
                self.resign(candidate)
                with self.assertRaises(ValueError): self.approve()

    def test_actual_carried_raw_change_rejects_even_with_forged_new_raw_hash_and_preserved_mtime(self):
        candidate = copy.deepcopy(self.jobs[0]["candidate"])
        record = candidate["carried_registered_identity"]["frames"]["2059d"]
        raw = self.hd / record["frame_binding"]["file"]
        stamp = raw.stat().st_mtime_ns
        raw.write_bytes(raw.read_bytes() + b"changed carried art")
        os.utime(raw, ns=(stamp, stamp))
        record["raw_sha256"] = self.sha(raw.read_bytes())
        self.resign(candidate)
        with self.assertRaisesRegex(ValueError, "carried raw artwork changed"): self.approve()

    def test_matching_carried_raw_symlink_cannot_escape_hd_root(self):
        raw = self.hd / self.carried["2059d"]["file"]
        outside = self.hd.parent / "outside-carried.png"
        outside.write_bytes(raw.read_bytes())
        raw.unlink(); raw.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "escapes HD root"): self.approve()

    def test_candidate_and_review_carried_identities_must_agree(self):
        review = copy.deepcopy(self.jobs[0]["review"])
        review["standalone_selection"]["carried_registered_identity"]["frame_bindings_sha256"] = "0" * 64
        self.save("review", review)
        with self.assertRaisesRegex(ValueError, "review carried identity differs"): self.approve()

    def test_rehashed_actual_baseline_changes_cannot_replace_accepted_carry_identity(self):
        for mutation in ["raw_path", "crop", "canvas", "origin", "source", "optional_policy"]:
            with self.subTest(mutation=mutation), self.original_fixture():
                baseline = copy.deepcopy(self.baseline)
                frame = baseline["sequences"][0]["frames"][0]
                if mutation == "raw_path": frame["file"] = baseline["sequences"][1]["frames"][0]["file"]
                elif mutation == "crop": frame["crop"] = [0, 0, 4, 4]
                elif mutation == "canvas": frame["logical_width"] = 8
                elif mutation == "origin": frame["origin"] = [1, 0]
                elif mutation == "source": frame["source_sha256"] = "0" * 64
                else: frame["preserve_reserved_coverage"] = True
                self.write(self.hd / "hd.json", baseline)
                candidate = copy.deepcopy(self.jobs[0]["candidate"])
                identity = candidate["carried_registered_identity"]
                identity["baseline"] = self.ref(self.hd / "hd.json")
                identity["frames"]["2059d"]["frame_binding"] = frame
                identity["frame_bindings_sha256"] = binding_digest({**self.carried, "2059d": frame})
                self.resign(candidate)
                with self.assertRaises(ValueError): self.approve()

    def test_current_baseline_and_accepted_registration_receipts_are_exact(self):
        for mutation in ["wrong_baseline_path", "stale_baseline_hash", "missing_baseline", "wrong_provenance_path",
                         "stale_provenance", "wrong_record_index", "boolean_record_index", "other_job_record", "wrong_count",
                         "wrong_accepted_path", "changed_accepted_hash", "changed_accepted_digest", "changed_accepted_source",
                         "changed_accepted_scale", "duplicate_accepted_scale", "duplicate_accepted_id"]:
            with self.subTest(mutation=mutation), self.original_fixture():
                candidate = copy.deepcopy(self.jobs[0]["candidate"])
                identity = candidate["carried_registered_identity"]
                if mutation == "wrong_baseline_path": identity["baseline"] = self.ref(self.hd / "context-baseline.json")
                elif mutation == "stale_baseline_hash": identity["baseline"]["sha256"] = "0" * 64
                elif mutation == "missing_baseline": identity.pop("baseline")
                elif mutation == "wrong_provenance_path": identity["provenance"] = self.ref(self.hd / "context-baseline.json")
                elif mutation == "stale_provenance": identity["provenance"]["sha256"] = "0" * 64
                elif mutation == "wrong_record_index": identity["registration_record_index"] = -1
                elif mutation == "boolean_record_index": identity["registration_record_index"] = False
                elif mutation in ["other_job_record", "wrong_count"]:
                    path = self.hd / "provenance.json"; provenance = json.loads(path.read_text())
                    entry = provenance["reviewed_sequence_additions"][0]
                    if mutation == "other_job_record": entry["job_id"] = "terrain-10530-1053f"
                    else: entry["frames"] = 13
                    self.write(path, provenance); identity["provenance"] = self.ref(path)
                elif mutation == "wrong_accepted_path": identity["accepted_runtime_qa"] = self.ref(self.jobs[0]["directory"] / "runtime-qa.json")
                elif mutation == "changed_accepted_hash": identity["accepted_runtime_qa"]["sha256"] = "0" * 64
                else:
                    accepted = json.loads(self.accepted_path.read_text())
                    if mutation == "changed_accepted_digest": accepted["frame_bindings_sha256"] = "0" * 64
                    elif mutation == "changed_accepted_source": accepted["frames"][0]["source_sha256"] = "0" * 64
                    elif mutation == "changed_accepted_scale": accepted["frames"][0]["hd_masks"][0]["scale"] = True
                    elif mutation == "duplicate_accepted_scale": accepted["frames"][0]["hd_masks"].append({"scale": 4})
                    else: accepted["frames"].append(accepted["frames"][0])
                    self.write(self.accepted_path, accepted); identity["accepted_runtime_qa"] = self.ref(self.accepted_path)
                self.resign(candidate)
                with self.assertRaises((ValueError, OSError)): self.approve()

    def test_baseline_cannot_hide_carried_tile_in_boolean_or_partial_animation(self):
        for mutation in ["boolean_count", "boolean_frame", "partial_animation", "full_animation", "empty_sequence", "missing_sibling", "duplicate_sibling", "already_selected"]:
            with self.subTest(mutation=mutation), self.original_fixture():
                baseline = copy.deepcopy(self.baseline)
                if mutation == "boolean_count": baseline["sequences"][0]["frame_count"] = True
                elif mutation == "boolean_frame": baseline["sequences"][0]["frames"][0]["frame"] = False
                elif mutation == "partial_animation": baseline["sequences"][0]["frame_count"] = 2
                elif mutation == "full_animation":
                    baseline["sequences"][0]["frame_count"] = 2
                    baseline["sequences"][0]["frames"].append({**baseline["sequences"][1]["frames"][0], "frame": 1})
                    baseline["sequences"].pop(1)
                elif mutation == "empty_sequence": baseline["sequences"].append({"base_asset": 0x2059d, "frame_count": 1, "frames": []})
                elif mutation == "missing_sibling": baseline["sequences"].pop()
                elif mutation == "duplicate_sibling": baseline["sequences"].append(baseline["sequences"][0])
                else: baseline["sequences"].append(self.jobs[0]["candidate"]["sequences"][0])
                self.write(self.hd / "hd.json", baseline)
                candidate = copy.deepcopy(self.jobs[0]["candidate"])
                candidate["carried_registered_identity"]["baseline"] = self.ref(self.hd / "hd.json")
                self.resign(candidate)
                with self.assertRaises(ValueError): self.approve()

    def test_correctly_rehashed_future_projection_cannot_change_any_carried_or_new_binding(self):
        for mutation in ["omitted_carry", "omitted_new", "foreign_asset", "changed_carry", "changed_new", "boolean_frame", "boolean_count", "partial_animation", "empty_sequence", "duplicate_id", "wrong_baseline", "registered_context_overlap"]:
            with self.subTest(mutation=mutation), self.original_fixture():
                path = self.hd / "context-future_projection.json"
                future = json.loads(path.read_text())
                if mutation == "omitted_carry": future["sequences"].pop(0)
                elif mutation == "omitted_new": future["sequences"].pop()
                elif mutation == "foreign_asset": future["sequences"][0]["base_asset"] = 0x10530
                elif mutation == "changed_carry": future["sequences"][0]["frames"][0]["crop"] = [0, 0, 4, 4]
                elif mutation == "changed_new": future["sequences"][-1]["frames"][0]["origin"] = [1, 0]
                elif mutation == "boolean_frame": future["sequences"][0]["frames"][0]["frame"] = False
                elif mutation == "boolean_count": future["sequences"][0]["frame_count"] = True
                elif mutation == "partial_animation": future["sequences"][0]["frame_count"] = 2
                elif mutation == "empty_sequence": future["sequences"].append({"base_asset": 0x205a3, "frame_count": 1, "frames": []})
                elif mutation == "duplicate_id": future["sequences"].append(future["sequences"][0])
                elif mutation == "wrong_baseline":
                    self.reseal_context(baseline=self.ref(self.hd / "context-baseline.json"))
                else:
                    proposal = json.loads(self.context_candidate_path.read_text())
                    proposal["sequences"].append(self.baseline["sequences"][0])
                    self.reseal_context(proposal=proposal)
                if mutation not in ["wrong_baseline", "registered_context_overlap"]:
                    self.write(path, future); self.reseal_context(future=self.ref(path))
                with self.assertRaises((ValueError, KeyError)): self.approve()

    def test_carried_original_source_symlink_or_bytes_cannot_be_replaced(self):
        target = self.jobs[0]["job"]["targets"][0]
        source = self.data / target["source_path"]
        payload = source.read_bytes()
        source.write_bytes(payload[:-1] + b"\xff")
        with self.assertRaisesRegex(ValueError, "original inventory source differs"): self.approve()
        source.write_bytes(payload)
        outside = self.data.parent / "outside-carried-source"
        outside.write_bytes(payload)
        source.unlink(); source.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "INDEX path escapes"): self.approve()

    def test_pending_or_missing_new_material_and_context_are_not_authorized_by_carried_content(self):
        for mutation in ["pending", "missing_material", "missing_context", "wrong_material", "same_reviewer"]:
            with self.subTest(mutation=mutation), self.original_fixture():
                review = copy.deepcopy(self.jobs[0]["review"])
                if mutation == "pending": review["status"] = "PENDING"
                elif mutation == "missing_material": review["standalone_selection"]["material_approvals"].pop("205a3")
                elif mutation == "missing_context": review["standalone_selection"].pop("contextual_approval")
                elif mutation == "wrong_material": review["standalone_selection"]["material_approvals"]["205a3"]["source_sha256"] = "0" * 64
                else:
                    peer_path = self.jobs[0]["directory"] / "peer.json"; peer = json.loads(peer_path.read_text()); peer["reviewer"] = peer["author"]
                    self.write(peer_path, peer)
                    for approval in review["standalone_selection"]["material_approvals"].values(): approval["independent_review"] = self.ref(peer_path)
                self.save("review", review)
                with self.assertRaises(ValueError): self.approve()


if __name__ == "__main__":
    unittest.main()
