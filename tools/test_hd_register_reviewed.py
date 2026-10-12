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
        self.entries = ["1052f 0 tiles/STARTG1TILES"]
        self.jobs = []
        self.pictures = []
        all_bindings = {}
        for number, selected in enumerate(self.SELECTED):
            start = 0x10530 + number * 16
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
        self.entries.append("10550 0 tiles/ENDG1TILES")
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
        self.audit = {"assets": self.pictures, "sequences": {"Terrain": [{"name": "Terrain set 1", "frames": list(range(0x10530, 0x10550))}]},
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


if __name__ == "__main__":
    unittest.main()
