"""Synthetic whole-animation dormant admission; no real art/engine/registrar main."""
import copy
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
import hd_dormant_enemy_review as dormant
import hd_register_reviewed as registrar
from hd_candidate_review import binding_digest


class DormantEnemyAnimationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / "Renamed 游戏 bundle"
        self.data = self.project / "data"
        self.root = self.data / "hd"
        self.directory = self.root / "jobs/dormant"
        for p in [self.directory / "raw", self.root / "proof", self.data / "sprites",
                  self.data / "misc", self.data / "maps", self.project / "src", self.project / "target"]:
            p.mkdir(parents=True, exist_ok=True)
        for name in ["assets", "content", "simulation", "hd"]:
            (self.project / f"src/{name}.rs").write_text(f"synthetic {name} Source gate fixture")
        gates = {p: self.sha(self.project / p) for p in dormant.SUPPORTED_GATE_SOURCES}
        gate_patch = patch.dict(dormant.SUPPORTED_GATE_SOURCES, gates, clear=True)
        gate_patch.start()
        self.addCleanup(gate_patch.stop)
        lib = self.project / "target/fixture.rlib"
        lib.write_bytes(b"synthetic immutable library, not an actual game execution")
        os.utime(lib, ns=(2_000_000_000_000_000_000,) * 2)
        palette = self.data / "misc/PALETTE_DAT"
        palette.write_bytes(bytes(v // 4 for v in range(256) for _ in range(3)))
        self.index = [(1, "misc/PALETTE_DAT")]
        self.assets = [f"{0x100+i:05x}" for i in range(6)]
        self.rows, targets, reports, artwork = {}, [], [], {}
        for i, asset in enumerate(self.assets):
            route = "sprites/DORMANT_PIC" + (f".{i}" if i else "")
            source = self.data / route
            source.write_bytes(struct.pack("<5i", 1, 0, 0, 4, 4) + bytes([i+1] * 16))
            self.index.append((0x100+i, route))
            target = dict(asset=asset, source_path=route, source_sha256=self.sha(source),
                          logical_canvas=[4, 4], origin=[0, 0], source_palette="PALETTE_DAT",
                          source_palette_sha256=self.sha(palette))
            targets.append(target)
            raw = self.directory / f"raw/{asset}.png"
            Image.new("RGBA", (8, 8), (4*(i+1),)*3 + (255,)).save(raw)
            frame = dict(frame=i, file=f"jobs/dormant/raw/{asset}.png", logical_width=4,
                         logical_height=4, origin=[0, 0], source_sha256=self.sha(source),
                         original_detail_cells=[[0, 0]])
            self.rows[asset] = frame
            artwork[frame["file"]] = self.sha(raw)
            mask = dict(palette_indices_240_to_255_counts=[0]*16, visible_pixels=16)
            reports.append(dict(asset=asset, source_sha256=frame["source_sha256"], logical_canvas=[4, 4],
                                source_mask=mask, source_palette="PALETTE_DAT", hd_masks=[dict(scale=k, mask=mask) for k in range(1, 5)]))
        self.sprite = bytearray(528)
        self.sprite[:11] = b"DORMANT_PIC"
        struct.pack_into("<i", self.sprite, 44, 6)
        for game in range(4):
            route = f"misc/SPRITE{game+1}_ITM"
            (self.data / route).write_bytes(bytes(self.sprite) if game == 0 else bytes(528))
            self.index.append((0x200+game, route))
        for sector in range(1, 4):
            for wave in range(1, 10):
                route = f"maps/MAP{wave}G{sector}_MAP"
                spawn = struct.pack("<6i", -1, 0, 0, 31, 0, 1) if (sector, wave) == (1, 1) else b""
                payload = struct.pack("<3i", 5412+len(spawn), 5412, len(spawn)//24) + bytes(5400) + spawn
                (self.data / route).write_bytes(payload)
                self.index.append((0x300+16*sector+wave, route))
        (self.data / "INDEX").write_text("".join(f"{i:x} {(self.data/r).stat().st_size} {r}\n" for i, r in self.index))
        self.candidate = dict(format_version=1, job_id="dormant", complete_family=True,
                              category="Enemies and ground objects", kind="complete_family",
                              approval_scope=dormant.DORMANT_ENEMY_SCOPE,
                              sequences=[dict(name="DORMANT", base_asset=0x100, frame_count=6,
                                              frames=list(self.rows.values()))])
        self.job = dict(job_id="dormant", kind="complete_family", category="Enemies and ground objects",
                        owner="artist", targets=targets)
        self.qa = dict(frame_bindings_sha256=binding_digest(self.rows), validated_frames=6, diagnostics=[], static_card_palette_mode=False,
                       library="target/fixture.rlib", library_sha256=self.sha(lib),
                       library_modified_ns=lib.stat().st_mtime_ns, source_newer_than_library=False,
                       any_game_source_newer_than_library=False, frames=reports, artwork_sha256=artwork,
                       current_game_source_sha256={p.relative_to(self.project).as_posix(): self.sha(p)
                           for p in (self.project / "src").rglob("*.rs")})
        self.trace = dict(contract_version=dormant.DORMANT_ENEMY_TRACE,
                          no_genuine_original_runtime_context_claimed=True,
                          family=dict(name="DORMANT_PIC", assets=self.assets, frame_count=6),
                          catalogue=self.pin("data/INDEX"), palette=self.pin("data/misc/PALETTE_DAT"),
                          phases=[dict(asset=a, Source=self.pin("data/"+t["source_path"]),
                                       header_le_i32=[1, 0, 0, 4, 4]) for a, t in zip(self.assets, targets)],
                          sprite_libraries=[self.pin(f"data/misc/SPRITE{g}_ITM") for g in range(1, 5)],
                          sprite_callers=[dict(game=0, ordinal=0, name="DORMANT_PIC", base_asset="00100",
                                               frame_count=6, enemy_id="base:enemy_0_0",
                                               record_sha256=hashlib.sha256(self.sprite).hexdigest())],
                          current_rust_sources=[self.pin(p.relative_to(self.project).as_posix())
                                                for p in sorted((self.project / "src").rglob("*.rs"))],
                          current_library=self.pin("target/fixture.rlib"),
                          maps=[self.pin(f"data/maps/MAP{w}G{s}_MAP") for s in range(1, 4) for w in range(1, 10)],
                          map_declarations=[dict(map="data/maps/MAP1G1_MAP", ordinal=0, byte_offset=5412,
                                                 fields=[-1, 0, 0, 31, 0, 1],
                                                 raw_bytes_hex=struct.pack("<6i", -1, 0, 0, 31, 0, 1).hex(),
                                                 enabled_by_pilot_difficulty=[False]*4)],
                          counts=dict(maps=27, sprite_libraries=4, sprite_records=4, family_library_callers=1,
                                      spawn_records=1, family_map_declarations=1, ordinary_difficulty_callers=0))
        self.common = dict(scope=dormant.DORMANT_ENEMY_SCOPE, assets=self.assets,
                           frame_bindings_sha256=binding_digest(self.rows),
                           source_sha256_by_asset={a: f["source_sha256"] for a, f in self.rows.items()},
                           artwork_sha256=artwork, original_generated_raw_sha256=sorted(set(artwork.values())),
                           retained_cells_by_asset={a: f["original_detail_cells"] for a, f in self.rows.items()},
                           native_scales=[1, 2, 3, 4], all_frames_whole_viewed=True,
                           no_genuine_original_runtime_context_claimed=True)
        self.peer = dict(**self.common, contract_version=dormant.DORMANT_ENEMY_MATERIAL, status="qualified",
                         artist="artist", preparer="preparer", reviewer="different", qualified_frames=6,
                         held_frames=0, different_from_artist_and_preparer=True,
                         native_decisions=[dict(asset=a, scale=k, status="qualified", retained_SourceNx_exact=True,
                                                retained_samples=k*k) for a in self.assets for k in range(1, 5)])
        self.actual = dict(status="QUALIFIED_COMPLETE_ANIMATION_INTRINSIC", reviewer="different",
                           decisions=[dict(asset=a, intrinsic="QUALIFIED_WITH_LIMITS") for a in self.assets],
                           physical_views=[dict(asset=a, kind="native1to4", whole_frame_personally_viewed=True)
                                           for a in self.assets])
        self.approval = dict(**self.common, status="approved", authority_role="project_root", reviewer="root")

    @staticmethod
    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def pin(self, route):
        path = self.project / route
        return dict(path=route, sha256=self.sha(path), bytes=path.stat().st_size)

    def proof(self, route, value):
        path = self.root / route
        path.write_text(json.dumps(value, indent=2) + "\n")
        return dict(path=route, sha256=self.sha(path))

    def declarations(self):
        self.proof("jobs/dormant/job.json", self.job)
        candidate = self.proof("jobs/dormant/candidate.json", self.candidate)
        qa_ref = self.proof("proof/qa.json", self.qa)
        trace_ref = self.proof("proof/trace.json", self.trace)
        peer = copy.deepcopy(self.peer)
        peer.update(candidate=candidate, runtime_qa_sha256=qa_ref["sha256"],
                    actual_whole_material_review=self.proof("proof/actual.json", self.actual))
        peer_ref = self.proof("proof/peer.json", peer)
        approval = dict(self.approval, runtime_qa_sha256=qa_ref["sha256"], source_trace_sha256=trace_ref["sha256"],
                        independent_material_sha256=peer_ref["sha256"])
        declaration = dict(hybrid_review_scope=dormant.DORMANT_ENEMY_SCOPE,
                            hybrid_allscale_and_genuine_context_independent_review=False,
                            catalog_dormant_no_genuine_runtime_context_claimed=True,
                            catalog_only_independent_whole_material_and_allscale_review=True,
                            cells_by_asset=self.common["retained_cells_by_asset"], retained_original_not_generated_HD=True,
                            policy_version="retained-original-details-v2-painted0255",
                            painted_Source_palette_domain=[0, 255], functional_palette_effects_are_retained_Original=True,
                            frame_bindings_sha256=binding_digest(self.rows), dormant_source_trace=trace_ref,
                            dormant_independent_material=peer_ref, dormant_actual_allscale_QA=qa_ref,
                            dormant_root_approval=self.proof("proof/root.json", approval))
        review = dict(status="approved", source_and_all_scale_visual_review=True, independent_review=peer_ref,
                      frame_bindings_sha256=binding_digest(self.rows), runtime_qa="proof/qa.json",
                      retained_original_detail_review=declaration)
        self.proof("jobs/dormant/coordinator-review.json", review)
        return review

    def check(self, review=None):
        return dormant.approved_dormant_enemy_animation(self.root, self.project, self.candidate, self.job,
                                                        self.declarations() if review is None else review,
                                                        self.rows, self.qa)

    def test_whole_synthetic_six_phase_secret_only_family_accepts_relocated_unicode(self):
        result = self.check()
        self.assertEqual(result["family_map_declarations"], 1)
        self.assertEqual(result["ordinary_difficulty_callers"], 0)

    def test_actual_registrar_dispatch_accepts_explicit_whole_family(self):
        self.declarations()
        _, _, rows = registrar.approved_job(self.root, "dormant", self.project)
        self.assertEqual(set(rows), set(self.assets))

    def test_normal_caller_rejected_even_with_updated_pin_and_false_zero_claim(self):
        path = self.data / "maps/MAP1G1_MAP"
        payload = bytearray(path.read_bytes())
        struct.pack_into("<i", payload, 5412+20, 3)
        path.write_bytes(payload)
        self.trace["maps"][0] = self.pin("data/maps/MAP1G1_MAP")
        with self.assertRaisesRegex(ValueError, "ordinary or unsupported"): self.check()

    def test_partial_sequence_singleton_and_phase_limit_rejected(self):
        for count in [1, 5, 97, True]:
            with self.subTest(count=count):
                self.candidate["sequences"][0]["frame_count"] = count
                with self.assertRaises(ValueError): self.check()

    def test_six_singletons_cannot_fake_whole_animation(self):
        self.candidate["sequences"] = [dict(base_asset=0x100+i, frame_count=1, frames=[dict(f, frame=0)])
                                       for i, f in enumerate(self.rows.values())]
        with self.assertRaisesRegex(ValueError, "one complete"): self.check()

    def test_phase_header_false_or_bool_rejected(self):
        for value in [True, 2]:
            self.trace["phases"][0]["header_le_i32"][0] = value
            with self.assertRaisesRegex(ValueError, "phase header"): self.check()

    def test_duplicate_map_or_missing_fourth_library_rejected(self):
        self.trace["maps"][-1] = self.trace["maps"][0]
        with self.assertRaisesRegex(ValueError, "all27"): self.check()
        self.trace["maps"][-1] = self.pin("data/maps/MAP9G3_MAP")
        self.trace["sprite_libraries"].pop()
        with self.assertRaisesRegex(ValueError, "all four"): self.check()

    def test_wrong_sprite_frame_count_and_alias_rejected(self):
        path = self.data / "misc/SPRITE1_ITM"
        payload = bytearray(path.read_bytes())
        struct.pack_into("<i", payload, 44, 5)
        path.write_bytes(payload)
        self.trace["sprite_libraries"][0] = self.pin("data/misc/SPRITE1_ITM")
        with self.assertRaisesRegex(ValueError, "partial, aliased or boss"): self.check()

    def test_updated_gate_source_receipt_cannot_bypass_supported_source_epoch(self):
        path = self.project / "src/simulation.rs"
        path.write_text("changed normal gate predicate")
        for row in self.trace["current_rust_sources"]:
            if row["path"] == "src/simulation.rs": row.update(self.pin("src/simulation.rs"))
        self.qa["current_game_source_sha256"]["src/simulation.rs"] = self.sha(path)
        with self.assertRaisesRegex(ValueError, "gate Source changed"): self.check()

    def test_missing_source_or_stale_qa_rejected(self):
        self.trace["current_rust_sources"].pop()
        with self.assertRaisesRegex(ValueError, "Rust Source inventory"): self.check()

    def test_qa_false_freshness_and_wrong_source_hash_rejected(self):
        self.qa["any_game_source_newer_than_library"] = None
        with self.assertRaisesRegex(ValueError, "current QA"): self.check()

    def test_old_material_cannot_bind_different_runtime_raw(self):
        self.peer["artwork_sha256"] = dict(self.peer["artwork_sha256"])
        self.peer["artwork_sha256"][next(iter(self.peer["artwork_sha256"]))] = "0"*64
        with self.assertRaisesRegex(ValueError, "different whole-family"): self.check()

    def test_peer_not_independent_or_held_cannot_qualify(self):
        self.peer["reviewer"] = "preparer"
        with self.assertRaisesRegex(ValueError, "different whole-family"): self.check()

    def test_missing_scale_face_counts_and_boolean_view_rejected(self):
        self.peer["native_decisions"].pop()
        with self.assertRaisesRegex(ValueError, "native-scale"): self.check()

    def test_root_cannot_claim_fabricated_context_or_false_whole_view(self):
        self.approval["no_genuine_original_runtime_context_claimed"] = False
        with self.assertRaisesRegex(ValueError, "Root whole-family"): self.check()

    def test_actual_review_missing_whole_phase_rejected(self):
        self.actual["physical_views"].pop()
        with self.assertRaisesRegex(ValueError, "actual whole-native"): self.check()

    def test_source_and_proof_paths_cannot_escape_or_use_symlink(self):
        self.trace["phases"][0]["Source"]["path"] = "../outside"
        with self.assertRaisesRegex(ValueError, "portable file pin"): self.check()

    def test_dormant_scope_cannot_silently_replace_ordinary_retained_contract(self):
        self.declarations()
        path = self.directory / "coordinator-review.json"
        review = json.loads(path.read_text())
        review["retained_original_detail_review"]["hybrid_review_scope"] = "ordinary"
        path.write_text(json.dumps(review))
        with self.assertRaisesRegex(ValueError, "explicit in candidate and review"):
            registrar.approved_job(self.root, "dormant", self.project)


    def test_false_census_and_boolean_count_are_not_status_authority(self):
        for value in [0, True]:
            self.trace["counts"]["family_map_declarations"] = value
            with self.assertRaisesRegex(ValueError, "caller census"): self.check()

    def test_classic_secret_code_zero_and_two_remain_dormant(self):
        for code in [0, 2]:
            path = self.data / "maps/MAP1G1_MAP"
            payload = bytearray(path.read_bytes())
            struct.pack_into("<i", payload, 5412+20, code)
            path.write_bytes(payload)
            self.trace["maps"][0] = self.pin("data/maps/MAP1G1_MAP")
            self.trace["map_declarations"][0]["fields"][-1] = code
            self.trace["map_declarations"][0]["raw_bytes_hex"] = bytes(payload[5412:5436]).hex()
            self.check()

    def test_static_card_palette_bypass_is_not_enemy_qa(self):
        self.qa["static_card_palette_mode"] = True
        with self.assertRaisesRegex(ValueError, "runtime QA differs"): self.check()

    def test_missing_root_and_untrue_whole_view_rejected(self):
        review = self.declarations()
        review["retained_original_detail_review"].pop("dormant_root_approval")
        with self.assertRaisesRegex(ValueError, "portable hash-bound"): self.check(review)

    def test_fake_context_declaration_rejected_even_without_retention_dispatch(self):
        review = self.declarations()
        review["retained_original_detail_review"]["hybrid_allscale_and_genuine_context_independent_review"] = True
        with self.assertRaisesRegex(ValueError, "cannot claim genuine"): self.check(review)

    def test_boolean_native_sample_count_is_not_one_source_sample(self):
        self.peer["native_decisions"][0]["retained_samples"] = True
        with self.assertRaisesRegex(ValueError, "native-scale"): self.check()

    def test_numeric_one_cannot_fake_whole_family_view(self):
        self.peer["all_frames_whole_viewed"] = 1
        with self.assertRaisesRegex(ValueError, "different whole-family"): self.check()

    def test_ordinary_source_cannot_gain_functional_palette_labels(self):
        self.qa["frames"][0]["hd_masks"][0]["mask"] = dict(self.qa["frames"][0]["hd_masks"][0]["mask"])
        self.qa["frames"][0]["hd_masks"][0]["mask"]["palette_indices_240_to_255_counts"] = [1] + [0]*15
        with self.assertRaisesRegex(ValueError, "functional palette"): self.check()

    def test_changed_raw_artwork_and_stale_source_mask_rejected(self):
        raw = self.root / self.rows[self.assets[0]]["file"]
        Image.new("RGBA", (8, 8), (50, 50, 50, 255)).save(raw)
        with self.assertRaisesRegex(ValueError, "hash differs"): self.check()

    def test_direct_native_family_or_activation_code_requires_new_review(self):
        path = self.project / "src/hd.rs"
        path.write_text("DORMANT_PIC")
        for row in self.trace["current_rust_sources"]:
            if row["path"] == "src/hd.rs": row.update(self.pin("src/hd.rs"))
        with self.assertRaisesRegex(ValueError, "direct family caller"): self.check()

    def test_source_symlink_and_library_hash_cannot_bypass_epoch(self):
        source = self.data / "sprites/DORMANT_PIC"
        payload = source.read_bytes()
        outside = self.project.parent / "outside"
        outside.write_bytes(payload)
        source.unlink()
        source.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "symlink"): self.check()

    def test_extra_named_source_phase_cannot_be_omitted(self):
        path = self.data / "sprites/DORMANT_PIC.6"
        payload = (self.data / "sprites/DORMANT_PIC").read_bytes()
        path.write_bytes(payload)
        index = self.data / "INDEX"
        index.write_text(index.read_text() + f"106 {len(payload)} sprites/DORMANT_PIC.6\n")
        self.trace["catalogue"] = self.pin("data/INDEX")
        with self.assertRaisesRegex(ValueError, "additional phases"): self.check()



    def test_pending_phase_material_word_is_not_whole_qualification(self):
        self.actual["decisions"][0]["intrinsic"] = "QUALIFIED_PENDING"
        with self.assertRaisesRegex(ValueError, "actual whole-native"): self.check()

    def test_global_not_qualified_cannot_match_qualified_substring(self):
        self.actual["status"] = "QUALIFIED_NOT_APPROVED"
        with self.assertRaisesRegex(ValueError, "actual whole-native"): self.check()

    def test_not_approved_hyphen_separator_cannot_qualify(self):
        self.actual["status"] = "QUALIFIED_NOT-APPROVED"
        with self.assertRaisesRegex(ValueError, "actual whole-native"): self.check()

    def test_hold_number_hyphen_separator_cannot_qualify(self):
        self.actual["status"] = "QUALIFIED_WITH_HOLD-1"
        with self.assertRaisesRegex(ValueError, "actual whole-native"): self.check()

    @unittest.skipUnless(hasattr(os, "mkfifo"), "requires POSIX FIFO")
    def test_swapped_fifo_is_rejected_before_read_without_blocking(self):
        path = self.directory / "proof-fifo-race.bin"
        path.write_bytes(b"original")
        code = r"""
import hashlib,os,sys
from pathlib import Path
from unittest.mock import patch
import hd_dormant_enemy_review as d
root=Path(sys.argv[1]); path=root/"proof-fifo-race.bin"
record=dict(path=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
actual_open=os.open

def swap_to_fifo(name,flags):
    path.unlink();os.mkfifo(path)
    return actual_open(name,flags)

with patch.object(d.os,"open",swap_to_fifo):
    try:d._read(root,record)
    except ValueError as error:
        assert "bounded, regular and unchanged" in str(error),str(error)
        print("actual swapped FIFO rejected before descriptor read")
    else:raise AssertionError("FIFO accepted")
"""
        env = dict(os.environ, PYTHONPATH=os.pathsep.join(
            [str(Path(dormant.__file__).parent)] + sys.path))
        try:
            actual = subprocess.run([sys.executable, "-B", "-c", code, str(self.directory)],
                                    capture_output=True, text=True, env=env, timeout=3,
                                    cwd=Path(dormant.__file__).parent)
        except subprocess.TimeoutExpired:
            self.fail("swapped FIFO blocked while opening the descriptor")
        self.assertEqual(actual.returncode, 0, actual.stderr)
        self.assertIn("actual swapped FIFO rejected", actual.stdout)

    def test_file_growth_is_rejected_with_a_bounded_read(self):
        path = self.directory / "proof-growth.bin"
        path.write_bytes(b"old")
        record = dict(path=path.name, sha256=self.sha(path))
        actual_fdopen = os.fdopen
        read_sizes = []

        class GrowDuringRead:
            def __init__(self, stream): self.stream = stream
            def __enter__(self): return self
            def __exit__(self, *unused): self.stream.close()
            def fileno(self): return self.stream.fileno()
            def read(self, size=-1):
                read_sizes.append(size)
                if len(read_sizes) == 1:
                    with path.open("ab") as writer: writer.write(b"x" * 65)
                return self.stream.read(size)

        with patch.object(dormant, "_MAX_FILE_BYTES", 64, create=True), \
                patch.object(dormant.os, "fdopen", lambda *args: GrowDuringRead(actual_fdopen(*args))):
            with self.assertRaisesRegex(ValueError, "exceeds bounded read|file changed"):
                dormant._read(self.directory, record)
        self.assertEqual(read_sizes, [65], "growth must never use an unbounded read")
        self.assertEqual(path.stat().st_size, 68)

    def test_palette_constraint_cannot_bypass_existing_genuine_context_contract(self):
        self.rows[self.assets[0]]["palette_constraint"] = "original-painted-ordinary-v1"
        with self.assertRaisesRegex(ValueError, "ordinary genuine-context"): self.check()

    def test_current_library_replacement_is_detected_without_trusting_qa_flags(self):
        path = self.project / "target/fixture.rlib"
        path.write_bytes(b"replacement library")
        with self.assertRaisesRegex(ValueError, "hash differs"): self.check()

    def test_wrong_category_and_boolean_origin_rejected(self):
        self.candidate["category"] = "Terrain"
        with self.assertRaisesRegex(ValueError, "complete Original enemy"): self.check()
        self.candidate["category"] = "Enemies and ground objects"
        self.job["targets"][0]["origin"] = [False, False]
        with self.assertRaisesRegex(ValueError, "phase header"): self.check()



    def test_actual_sourceG2_qa_field_is_accepted_without_relabeling_old_sourceF(self):
        self.qa["actual_sourceG2_source18_sha256"] = self.qa.pop("current_game_source_sha256")
        self.check()

    def test_source_mask_visible_count_must_come_from_actual_source_bytes(self):
        self.qa["frames"][0]["source_mask"] = dict(self.qa["frames"][0]["source_mask"], visible_pixels=15)
        with self.assertRaisesRegex(ValueError, "Source palette/mask"): self.check()

    def test_standalone_selection_cannot_use_animation_exception(self):
        self.candidate["complete_standalone_selection"] = True
        with self.assertRaisesRegex(ValueError, "one complete"): self.check()

    def test_normal_retained_path_still_requires_its_own_genuine_context_declaration(self):
        self.candidate.pop("approval_scope")
        review = self.declarations()
        review["retained_original_detail_review"]["hybrid_review_scope"] = "ordinary"
        self.proof("jobs/dormant/coordinator-review.json", review)
        with self.assertRaisesRegex(ValueError, "retained Original detail provenance"):
            registrar.approved_job(self.root, "dormant", self.project)



if __name__ == "__main__":
    unittest.main()
