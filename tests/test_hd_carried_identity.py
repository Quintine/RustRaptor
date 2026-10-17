"""Portable synthetic identity tests; no engine, image generation or registration."""
import copy
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import hd_register_reviewed as reg


def sha(data):
    return hashlib.sha256(data).hexdigest()


class CarriedFixture:
    def __init__(self, directory, legacy=False):
        self.base = Path(directory)
        self.root = self.base / "data/hd"
        self.project = self.base / "project"
        self.root.mkdir(parents=True)
        (self.project / "src").mkdir(parents=True)
        (self.project / "target").mkdir()
        for name in ["assets.rs", "hd.rs"]:
            p = self.project / "src" / name
            p.write_text("// synthetic fixture, never compiled\n")
            os.utime(p, ns=(1000000000, 1000000000))
        self.library = self.project / "target/test.rlib"
        self.library.write_bytes(b"synthetic QA identity, not an engine library")
        self.legacy = legacy
        self.ids = [f"{x:05x}" for x in range(0x2059d, 0x205ad)] if legacy else [f"{x:05x}" for x in range(0x17400, 0x17406)]
        self.selected = ["205a3", "205a4"] if legacy else self.ids[:2]
        self.carried = [a for a in self.ids if a not in self.selected] if legacy else self.ids[2:4]
        self.fallback = [] if legacy else self.ids[4:]
        self.job_id = f"terrain-{self.ids[0]}-{self.ids[-1]}"
        self.payload = struct.pack("<5i", 1, 0, 0, 32, 32) + bytes([31]) * 1024
        palette = bytes([1]) * 768
        self.targets, self.frames = {}, {}
        lines = ["10000 0 misc/STARTG1TILES", "20000 0 misc/ENDG1TILES",
                 "20000 0 misc/STARTG2TILES", "30000 0 misc/ENDG2TILES"]
        # One non-overlapping actual Terrain marker pair suffices per fixture.
        lines = lines[2:] if legacy else lines[:2]
        (self.base / "data/misc").mkdir()
        (self.base / "data/misc/PALETTE_DAT").write_bytes(palette)
        (self.base / "data/sprites").mkdir()
        for asset in self.ids:
            rel = f"sprites/tile-{asset}"
            (self.base / "data" / rel).write_bytes(self.payload)
            lines.append(f"{asset} {len(self.payload)} {rel}")
            self.targets[asset] = dict(asset=asset, source_path=rel, source_sha256=sha(self.payload),
                    logical_canvas=[32, 32], origin=[0, 0], source_palette="PALETTE_DAT",
                    source_palette_sha256=sha(palette))
            raw = f"raw-{asset}.bin"
            (self.root / raw).write_bytes(f"synthetic untouched raw {asset}".encode())
            self.frames[asset] = dict(frame=0, file=raw, logical_width=32, logical_height=32,
                    origin=[0, 0], source_sha256=sha(self.payload))
        (self.base / "data/INDEX").write_text("\n".join(lines) + "\n")
        if not legacy:
            self.frames[self.carried[0]].update(crop=None, preserve_reserved_coverage=False,
                                               original_detail_cells=[[0, 0]])
            self.frames[self.carried[1]].update(native_nearest_cues=[])
        self.job = dict(job_id=self.job_id, category="Terrain", kind="contextual_terrain_shard",
                        targets=list(self.targets.values()))
        self.active = {a: copy.deepcopy(self.frames[a]) for a in self.carried}
        self.manifest = self.pack(self.active)
        groups = [self.carried] if legacy else [[self.carried[0]], [self.carried[1]]]
        self.additions = []
        self.accepted = []
        for index, group in enumerate(groups):
            bindings = {a: self.active[a] for a in group}
            qa = self.qa(bindings)
            path = f"accepted-{index}.json"
            self.write(path, qa)
            self.accepted.append(qa)
            self.additions.append(dict(job_id=self.job_id if legacy else f"different-prior-job-{index}",
                    assets=group, frames=len(group), runtime_qa=path,
                    frame_bindings_sha256=reg.binding_digest(bindings)))
        self.provenance = dict(reviewed_sequence_additions=self.additions)
        self.write("hd.json", self.manifest)
        self.write("provenance.json", self.provenance)
        identity = dict(baseline=self.receipt("hd.json"), provenance=self.receipt("provenance.json"),
                        frames={}, frame_bindings_sha256=reg.binding_digest(self.active))
        for index, group in enumerate(groups):
            for asset in group:
                identity["frames"][asset] = dict(frame_binding=copy.deepcopy(self.active[asset]),
                        source_sha256=sha(self.payload), raw_sha256=sha((self.root / self.active[asset]["file"]).read_bytes()))
                if not legacy:
                    identity["frames"][asset]["registration_record_index"] = index
        if legacy:
            identity.update(registration_record_index=0, accepted_runtime_qa=self.receipt("accepted-0.json"))
        else:
            identity.update(contract_version=reg.CARRIED_TERRAIN_V2, registration_records=[dict(
                    registration_record_index=i, registration_record_sha256=reg.binding_digest(r),
                    assets=r["assets"], frame_bindings_sha256=r["frame_bindings_sha256"],
                    accepted_runtime_qa=self.receipt(r["runtime_qa"])) for i, r in enumerate(self.additions)])
        self.candidate = dict(job_id=self.job_id, category="Terrain", kind="contextual_terrain_shard",
                complete_family=False, complete_standalone_selection=True, full_inventory=self.ids,
                selected_assets=self.selected, original_fallback_assets=self.fallback,
                carried_registered_assets=self.carried, carried_registered_identity=identity,
                sequences=self.pack({a:self.frames[a] for a in self.selected})["sequences"])
        self.rows = reg.proposal_frames(self.candidate)
        self.review = {"standalone_selection": dict(reg.standalone_selection(self.candidate, self.job, self.rows),
                    carried_registered_identity=copy.deepcopy(identity))}

    @staticmethod
    def pack(rows):
        return dict(format_version=1, sequences=[dict(name=f"tile-{a}", base_asset=int(a,16),
                    frame_count=1, frames=[copy.deepcopy(f)]) for a,f in rows.items()])

    def write(self, name, value):
        p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value)+"\n")

    def receipt(self, name):
        return dict(path=name, sha256=sha((self.root/name).read_bytes()))

    def qa(self, rows):
        return dict(frame_bindings_sha256=reg.binding_digest(rows), diagnostics=[], frames=[dict(
                    asset=a, source_sha256=f["source_sha256"], logical_canvas=[32,32],
                    source_mask=dict(palette_indices_240_to_255_counts=[0]*16),
                    hd_masks=[dict(scale=s,mask=dict(palette_indices_240_to_255_counts=[0]*16)) for s in [1,2,3,4]])
                    for a,f in rows.items()], artwork_sha256={f["file"]:sha((self.root/f["file"]).read_bytes()) for f in rows.values()})

    def sync_identity(self):
        self.review["standalone_selection"]["carried_registered_identity"] = copy.deepcopy(self.candidate["carried_registered_identity"])

    def validate(self):
        return reg.validate_carried_registered_identity(self.root,self.candidate,self.job,self.rows,self.review)

    def approved_setup(self):
        directory=f"jobs/{self.job_id}"
        self.write(f"{directory}/candidate.json",self.candidate)
        qa=self.qa(self.rows)
        qa.update(candidate_sha256=self.receipt(f"{directory}/candidate.json")["sha256"],
                  source_newer_than_library=False,any_game_source_newer_than_library=False,
                  library="target/test.rlib",library_sha256=sha(self.library.read_bytes()),
                  library_modified_ns=self.library.stat().st_mtime_ns)
        self.write(f"{directory}/runtime-qa.json",qa)
        approvals={}
        for asset,frame in self.rows.items():
            peer=dict(reviewer="synthetic-different-peer",author="synthetic-artist",records=[dict(
                asset=asset,standalone_verdict="QUALIFIED_APPROVE",selected_frame_binding=frame,
                source_payload_sha256=frame["source_sha256"],full_untouched_raw_sha256=qa["artwork_sha256"][frame["file"]],actual_scales=[1,2,3,4])])
            path=f"peer-{asset}.json";self.write(path,peer)
            approvals[asset]=dict(status="approved",frame_bindings_sha256=reg.binding_digest({asset:frame}),
                source_sha256=frame["source_sha256"],raw_sha256=qa["artwork_sha256"][frame["file"]],independent_review=self.receipt(path),record_index=0)
        self.write("context-candidate.json",self.pack(self.rows))
        future=copy.deepcopy(self.manifest);future["sequences"].extend(self.pack(self.rows)["sequences"])
        self.write("future.json",future);self.write("changed-proof.json",dict(synthetic=True))
        authority=dict(candidate=self.receipt("context-candidate.json"),selected_assets=list(self.rows),
            frame_bindings_sha256=reg.binding_digest(self.rows),technical_verdict="QUALIFIED_CONTEXT_INTEGRATION",
            baseline=self.receipt("hd.json"),future_projection=self.receipt("future.json"))
        closure=dict(status="CLOSED_QUALIFIED_CONTEXT",candidate_sha256=authority["candidate"]["sha256"],
            frame_bindings_sha256=authority["frame_bindings_sha256"],baseline_sha256=authority["baseline"]["sha256"],
            future_projection_sha256=authority["future_projection"]["sha256"],changed_case_proof=self.receipt("changed-proof.json"))
        self.write("closure.json",closure);authority["changed_case_closure"]=self.receipt("closure.json")
        self.write("context-peer.json",dict(reviewer="synthetic-context-peer",author="synthetic-producer",standalone_selection_context=authority))
        self.review.update(status="approved",frame_bindings_sha256=reg.binding_digest(self.rows),
            candidate_sha256=qa["candidate_sha256"],source_and_all_scale_visual_review="synthetic review fixture, not real approval",
            independent_review="synthetic material/context fixture",runtime_qa=f"{directory}/runtime-qa.json")
        self.review["standalone_selection"].update(material_approvals=approvals,contextual_approval=dict(
            selected_assets=list(self.rows),selected_frame_bindings_sha256=reg.binding_digest(self.rows),receipt=self.receipt("context-peer.json")))
        self.write(f"{directory}/coordinator-review.json",self.review);self.write(f"{directory}/job.json",self.job)


class CarriedIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.f=CarriedFixture(self.temp.name)
        self.process_trap=patch('subprocess.run',side_effect=AssertionError('external process forbidden'))
        self.process_trap.start();self.addCleanup(self.process_trap.stop)

    def test_new_multi_record_partition_and_optional_policies(self):
        before={p:p.read_bytes()for p in self.f.root.rglob('*')if p.is_file()}
        self.f.validate()
        self.assertEqual(before,{p:p.read_bytes()for p in self.f.root.rglob('*')if p.is_file()})

    def test_legacy_master74_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            f=CarriedFixture(d,legacy=True);before=copy.deepcopy(f.candidate)
            f.validate();self.assertEqual(before,f.candidate)
            self.assertNotIn('contract_version',f.candidate['carried_registered_identity'])

    def test_legacy_full_approved_job_readonly_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            f=CarriedFixture(d,legacy=True);f.approved_setup()
            before={p:p.read_bytes()for p in f.root.rglob('*')if p.is_file()}
            with patch.object(reg,'atomic_json',side_effect=AssertionError('writer forbidden')),patch.object(reg,'main',side_effect=AssertionError('main forbidden')),patch.object(reg,'validate_hd_frame',return_value=None) as decoder:
                _,_,rows=reg.approved_job(f.root,f.job_id,f.project)
            self.assertEqual(set(rows),set(f.selected));self.assertEqual(decoder.call_count,2)
            self.assertEqual(before,{p:p.read_bytes()for p in f.root.rglob('*')if p.is_file()})

    def test_partial_carried_subset_authenticates_whole_prior_record(self):
        extra='17ff0';frame=copy.deepcopy(self.f.active[self.f.carried[0]])
        frame['file']='unrelated-prior-raw.bin';(self.f.root/frame['file']).write_bytes(b'unchanged unrelated prior raw')
        self.f.active[extra]=frame;self.f.manifest=self.f.pack(self.f.active)
        record=self.f.additions[0];record['assets'].append(extra);record['frames']=2
        bindings={a:self.f.active[a]for a in record['assets']};record['frame_bindings_sha256']=reg.binding_digest(bindings)
        self.f.write('accepted-0.json',self.f.qa(bindings));self.f.write('hd.json',self.f.manifest);self.f.write('provenance.json',self.f.provenance)
        identity=self.f.candidate['carried_registered_identity'];identity['baseline']=self.f.receipt('hd.json');identity['provenance']=self.f.receipt('provenance.json')
        descriptor=identity['registration_records'][0];descriptor.update(registration_record_sha256=reg.binding_digest(record),assets=record['assets'],frame_bindings_sha256=record['frame_bindings_sha256'],accepted_runtime_qa=self.f.receipt('accepted-0.json'))
        self.f.sync_identity();self.f.validate()
        descriptor['assets']=[self.f.carried[0]];self.f.sync_identity()
        with self.assertRaisesRegex(ValueError,'asset set'):self.f.validate()

    def test_unversioned_generic_scope_is_still_rejected(self):
        self.f.candidate['carried_registered_identity'].pop('contract_version')
        with self.assertRaisesRegex(ValueError,'master74'):reg.standalone_selection(self.f.candidate,self.f.job,self.f.rows)

    def test_unknown_version_rejected(self):
        self.f.candidate['carried_registered_identity']['contract_version']='future'
        with self.assertRaisesRegex(ValueError,'unknown'):reg.standalone_selection(self.f.candidate,self.f.job,self.f.rows)

    def test_optional_absent_is_not_null(self):
        self.f.candidate['carried_registered_identity']['frames'][self.f.carried[0]]['frame_binding'].pop('crop')
        self.f.sync_identity()
        with self.assertRaisesRegex(ValueError,'binding/policy'):self.f.validate()

    def test_optional_false_is_not_absent(self):
        self.f.candidate['carried_registered_identity']['frames'][self.f.carried[0]]['frame_binding'].pop('preserve_reserved_coverage')
        self.f.sync_identity()
        with self.assertRaisesRegex(ValueError,'binding/policy'):self.f.validate()

    def test_changed_raw_bytes(self):
        (self.f.root/self.f.active[self.f.carried[0]]['file']).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'raw artwork'):self.f.validate()

    def test_forged_registration_record_hash(self):
        self.f.candidate['carried_registered_identity']['registration_records'][0]['registration_record_sha256']='0'*64
        self.f.sync_identity()
        with self.assertRaisesRegex(ValueError,'record changed'):self.f.validate()

    def test_wrong_registration_assignment(self):
        self.f.candidate['carried_registered_identity']['frames'][self.f.carried[0]]['registration_record_index']=1
        self.f.sync_identity()
        with self.assertRaisesRegex(ValueError,'foreign registration'):self.f.validate()

    def test_duplicate_record_index_bool_and_wrong_asset_set(self):
        for field,value in [('registration_record_index',True),('assets',[self.f.carried[1]])]:
            with self.subTest(field=field):
                old=copy.deepcopy(self.f.candidate['carried_registered_identity'])
                self.f.candidate['carried_registered_identity']['registration_records'][0][field]=value;self.f.sync_identity()
                with self.assertRaises(ValueError):self.f.validate()
                self.f.candidate['carried_registered_identity']=old;self.f.sync_identity()

    def test_bad_partition_overlap_or_omission(self):
        for fallback in [[self.f.carried[0]],self.f.fallback[:-1]]:
            with self.subTest(fallback=fallback):
                self.f.candidate['original_fallback_assets']=fallback
                with self.assertRaisesRegex(ValueError,'partition'):self.f.validate()

    def test_selected_already_registered(self):
        self.f.manifest['sequences']+=self.f.pack({self.f.selected[0]:self.f.frames[self.f.selected[0]]})['sequences']
        self.f.write('hd.json',self.f.manifest)
        self.f.candidate['carried_registered_identity']['baseline']=self.f.receipt('hd.json');self.f.sync_identity()
        with self.assertRaisesRegex(ValueError,'partition'):self.f.validate()

    def test_fallback_already_registered(self):
        self.f.manifest['sequences']+=self.f.pack({self.f.fallback[0]:self.f.frames[self.f.fallback[0]]})['sequences']
        self.f.write('hd.json',self.f.manifest)
        self.f.candidate['carried_registered_identity']['baseline']=self.f.receipt('hd.json');self.f.sync_identity()
        with self.assertRaisesRegex(ValueError,'partition'):self.f.validate()

    def test_carried_animation_or_partial_sequence(self):
        self.f.manifest['sequences'][0]['frame_count']=2
        self.f.write('hd.json',self.f.manifest)
        self.f.candidate['carried_registered_identity']['baseline']=self.f.receipt('hd.json');self.f.sync_identity()
        with self.assertRaisesRegex(ValueError,'animation'):self.f.validate()

    def test_source_payload_and_palette_mutations(self):
        for path in [self.f.base/'data'/self.f.targets[self.f.carried[0]]['source_path'],self.f.base/'data/misc/PALETTE_DAT']:
            with self.subTest(path=str(path)):
                old=path.read_bytes();path.write_bytes(old+b'x')
                with self.assertRaisesRegex(ValueError,'source differs|palette changed'):self.f.validate()
                path.write_bytes(old)

    def test_false_terrain_source_inventory(self):
        index=self.f.base/'data/INDEX';index.write_text(index.read_text().replace('20000 0 misc/ENDG1TILES','173ff 0 misc/ENDG1TILES'))
        with self.assertRaisesRegex(ValueError,'not catalog Terrain'):self.f.validate()

    def test_source_origin_and_native_canvas_are_literal(self):
        for key,value in [('origin',[False,0]),('logical_canvas',[31,32])]:
            with self.subTest(key=key):
                target=next(t for t in self.f.job['targets']if t['asset']==self.f.carried[0]);old=target[key];target[key]=value
                with self.assertRaises(ValueError):self.f.validate()
                target[key]=old

    def test_selected_animation_is_rejected(self):
        self.f.candidate['sequences'][0]['frame_count']=2
        with self.assertRaisesRegex(ValueError,'animation'):self.f.validate()

    def test_independent_review_cannot_omit_or_change_identity(self):
        self.f.review['standalone_selection']['carried_registered_identity']['frame_bindings_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'independent review'):self.f.validate()

    def test_receipt_hash_and_current_pair_are_mandatory(self):
        self.f.candidate['carried_registered_identity']['provenance']['path']='other.json';self.f.sync_identity()
        with self.assertRaisesRegex(ValueError,'canonical pair'):self.f.validate()

    def test_accepted_allscale_qa_and_raw_mapping_are_not_invented(self):
        qa=self.f.accepted[0];qa['frames'][0]['hd_masks'][3]['scale']=3
        self.f.write('accepted-0.json',qa)
        self.f.candidate['carried_registered_identity']['registration_records'][0]['accepted_runtime_qa']=self.f.receipt('accepted-0.json');self.f.sync_identity()
        with self.assertRaisesRegex(ValueError,'Source/scales'):self.f.validate()

    def test_complete_approved_job_reaches_all_existing_selected_gates(self):
        self.f.approved_setup();seen=[]
        with patch.object(reg,'atomic_json',side_effect=AssertionError('writer forbidden')),patch.object(reg,'main',side_effect=AssertionError('main forbidden')),patch.object(reg,'validate_hd_frame',side_effect=lambda root,frame,payload,picture:seen.append((payload,picture.size))):
            result=reg.approved_job(self.f.root,self.f.job_id,self.f.project)
        self.assertEqual(set(result[2]),set(self.f.selected));self.assertEqual(seen,[(self.f.payload,(32,32))]*2)
        self.assertEqual(set(reg.proposal_frames(json.loads((self.f.root/'hd.json').read_text()))),set(self.f.carried))

    def test_selected_freshness_and_material_context_remain_required(self):
        self.f.approved_setup();directory=f'jobs/{self.f.job_id}';qa=json.loads((self.f.root/f'{directory}/runtime-qa.json').read_text())
        qa['any_game_source_newer_than_library']=True;self.f.write(f'{directory}/runtime-qa.json',qa)
        with self.assertRaisesRegex(ValueError,'freshness'):reg.approved_job(self.f.root,self.f.job_id,self.f.project)
        qa['any_game_source_newer_than_library']=False;self.f.write(f'{directory}/runtime-qa.json',qa)
        review=copy.deepcopy(self.f.review);review['standalone_selection']['material_approvals']={};self.f.write(f'{directory}/coordinator-review.json',review)
        with patch.object(reg,'validate_hd_frame',return_value=None),self.assertRaisesRegex(ValueError,'material map'):
            reg.approved_job(self.f.root,self.f.job_id,self.f.project)
        review=copy.deepcopy(self.f.review);review['standalone_selection'].pop('contextual_approval');self.f.write(f'{directory}/coordinator-review.json',review)
        with patch.object(reg,'validate_hd_frame',return_value=None),self.assertRaises(ValueError):reg.approved_job(self.f.root,self.f.job_id,self.f.project)


if __name__=='__main__':
    unittest.main()
