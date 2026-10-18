"""Unused Terrain approval proves Source absence; it cannot invent a gameplay scene."""
from pathlib import Path
import copy, hashlib, json, struct, tempfile, unittest
from PIL import Image
import hd_register_reviewed as m


class UnusedTerrainRetained(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='unused-terrain-')
        self.project = Path(self.temp.name) / 'Renamed 游戏 bundle'
        self.data = self.project / 'data'
        self.root = self.data / 'hd'
        for folder in ('misc', 'maps', 'tiles', 'hd/proof', 'hd/raws'):
            (self.data / folder).mkdir(parents=True, exist_ok=True)
        self.asset = '00103'
        self.source = self.data / 'misc/unused.pic'
        self.source.write_bytes(struct.pack('<5i', 1, 0, 0, 32, 32) + bytes(1024))
        palette = self.data / 'misc/PALETTE_DAT'
        palette.write_bytes(bytes(768))
        self.index = []
        self.add(1, 'misc/PALETTE_DAT')
        self.add(0x103, 'misc/unused.pic')
        for game in range(1, 5):
            base = game * 0x100
            for name, identity in [(f'STARTG{game}TILES', base), (f'ENDG{game}TILES', base + 4)]:
                (self.data / 'tiles' / name).write_bytes(b'')
                self.add(identity, f'tiles/{name}')
            lib = self.data / f'misc/FLATSG{game}_ITM'
            lib.write_bytes(b''.join(struct.pack('<ihh', i, 0, 0) for i in range(3)))
            self.add(0x500 + game, f'misc/FLATSG{game}_ITM')
        for sector in range(1, 4):
            for wave in range(1, 10):
                route = f'maps/MAP{wave}G{sector}_MAP'
                (self.data / route).write_bytes(struct.pack('<iii', 5412, 5412, 0) + bytes(5400))
                self.add(0x600 + sector * 16 + wave, route)
        self.write_index()
        raw = self.root / 'raws/test.png'
        Image.new('RGBA', (64, 64), (0, 0, 0, 255)).save(raw)
        frame = dict(frame=0, file='raws/test.png', logical_width=32, logical_height=32,
                     origin=[0, 0], source_sha256=self.sha(self.source),
                     original_detail_cells=[[x, 31] for x in range(32)])
        self.rows = {self.asset: frame}
        self.job = dict(category='Terrain', targets=[dict(asset=self.asset,
            source_path='misc/unused.pic', source_sha256=self.sha(self.source),
            logical_canvas=[32, 32], origin=[0, 0], source_palette='PALETTE_DAT',
            source_palette_sha256=self.sha(palette))])
        self.candidate = dict(sequences=[dict(base_asset=0x103, frame_count=1, frames=[frame])])
        masks = [dict(scale=i, mask={}) for i in range(1, 5)]
        self.qa = dict(diagnostics=[], validated_frames=1,
                       frames=[dict(asset=self.asset, hd_masks=masks)],
                       artwork_sha256={'raws/test.png': self.sha(raw)})
        self.peer = dict(status='QUALIFIED', asset=self.asset, qualified_complete1=True,
            all4_scales_qualified=True, complete_native_frames=1, native_scales=[1, 2, 3, 4],
            actual_artist='artist', hybrid_trial_preparer='preparer', reviewer='different',
            different_from_artist_and_preparer=True, held_frames=0,
            raw={'sha256': self.sha(raw)}, exact_original_detail_cells=frame['original_detail_cells'])
        self.contract = dict(status='qualified', scope='complete_native_picture_intrinsic_all_scales',
            asset=self.asset, reviewer='different', artist='artist', preparer='preparer',
            qualified_frames=1, held_frames=0, retained_cell_count=32,
            native_frame=frame, retained_cells=frame['original_detail_cells'], native_scales=[1, 2, 3, 4])
        self.approval = dict(status='approved', authority_role='project_root', reviewer='root',
            scope='unused_original_terrain_intrinsic_all_scales', asset=self.asset,
            frame_bindings_sha256=m.binding_digest(self.rows), source_sha256=frame['source_sha256'],
            raw_sha256=self.sha(raw), retained_cells=frame['original_detail_cells'],
            native_scales=[1, 2, 3, 4], whole_picture_personally_viewed=True,
            no_genuine_original_gameplay_context_claimed=True)
        self.trace = dict(contract_version=m.UNUSED_TERRAIN_TRACE_V1,
            status='CLOSED_UNUSED_ORIGINAL_TERRAIN_ALL27_MAPS', asset=self.asset,
            direct_callers=[], destroyed_callers=[], no_genuine_original_gameplay_context_claimed=True,
            source_header_le_i32=[1, 0, 0, 32, 32],
            counts=dict(maps=27, layout_cells=36450, flat_libraries=4, spawn_records=0,
                        direct_callers=0, destroyed_callers=0))

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def add(self, identity, route):
        self.index.append([identity, (self.data / route).stat().st_size, route])

    def write_index(self):
        (self.data / 'INDEX').write_text(''.join(f'{i:x} {s} {p}\n' for i, s, p in self.index))

    def pin(self, route):
        path = self.data / route
        return dict(path=route, sha256=self.sha(path), bytes=path.stat().st_size)

    def receipt(self, route, value):
        path = self.root / route
        path.write_text(json.dumps(value, indent=2) + '\n')
        return dict(path=route, sha256=self.sha(path))

    def declaration(self):
        self.trace.setdefault('catalogue', self.pin('INDEX'))
        self.trace.setdefault('Source', self.pin('misc/unused.pic'))
        self.trace.setdefault('maps', [self.pin(f'maps/MAP{w}G{s}_MAP') for s in range(1, 4) for w in range(1, 10)])
        self.trace.setdefault('flat_libraries', [self.pin(f'misc/FLATSG{g}_ITM') for g in range(1, 5)])
        peer = copy.deepcopy(self.peer)
        peer['candidate'] = self.receipt('proof/candidate.json', self.candidate)
        return dict(catalog_only_source_trace=self.receipt('proof/trace.json', self.trace),
            catalog_only_independent_material=self.receipt('proof/peer.json', peer),
            catalog_only_material_contract=self.contract,
            catalog_only_actual_allscale_QA=self.receipt('proof/qa.json', self.qa),
            catalog_only_root_approval=self.receipt('proof/root.json', self.approval))

    def check(self, declaration=None):
        return m.approved_unused_terrain_retained_evidence(self.root, self.project,
            self.declaration() if declaration is None else declaration, self.rows, self.qa, self.job)

    def mutate(self, route, offset, fmt, value):
        path = self.data / route
        b = bytearray(path.read_bytes())
        struct.pack_into(fmt, b, offset, value)
        path.write_bytes(b)

    def test_real_checked_synthetic_bundle_all27_unused_accepts_relocated_unicode(self):
        self.check()

    def test_actual_direct_map_use_rejects_even_when_receipt_claims_zero(self):
        self.mutate('maps/MAP1G1_MAP', 12, '<h', 2)
        with self.assertRaisesRegex(ValueError, 'original caller'): self.check()

    def test_actual_destroyed_map_use_rejects_even_when_receipt_claims_zero(self):
        self.mutate('misc/FLATSG1_ITM', 0, '<i', 2)
        with self.assertRaisesRegex(ValueError, 'original caller'): self.check()

    def test_missing_trace_rejects(self):
        d = self.declaration(); d.pop('catalog_only_source_trace')
        with self.assertRaisesRegex(ValueError, 'hash-bound'): self.check(d)

    def test_false_census_or_boolean_count_rejects(self):
        for value in [26, True]:
            with self.subTest(value=value):
                self.trace['counts']['maps'] = value
                with self.assertRaisesRegex(ValueError, 'false Source census'): self.check()

    def test_missing_map_rejects(self):
        self.declaration(); self.trace['maps'].pop()
        with self.assertRaisesRegex(ValueError, 'omits or duplicates'): self.check()

    def test_duplicate_map_cannot_cover_missing_twentyseventh(self):
        self.declaration(); self.trace['maps'][-1] = self.trace['maps'][0]
        with self.assertRaisesRegex(ValueError, 'omits or duplicates'): self.check()

    def test_fourth_flat_library_required(self):
        self.declaration(); self.trace['flat_libraries'].pop()
        with self.assertRaisesRegex(ValueError, 'omits or duplicates'): self.check()

    def test_bad_hash_rejects(self):
        self.declaration(); self.trace['maps'][0]['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'Source bytes changed'): self.check()

    def test_wrong_pin_path_rejects(self):
        self.declaration(); self.trace['Source']['path'] = '../outside.pic'
        with self.assertRaisesRegex(ValueError, 'pin path'): self.check()

    def test_header_claim_or_boolean_header_rejects(self):
        for value in [2, True]:
            with self.subTest(value=value):
                self.trace['source_header_le_i32'][0] = value
                with self.assertRaisesRegex(ValueError, 'header differs'): self.check()

    def test_bad_MAP_header_offset_rejects(self):
        self.mutate('maps/MAP9G3_MAP', 4, '<i', 5411)
        with self.assertRaisesRegex(ValueError, 'MAP header'): self.check()

    def test_negative_spawn_count_rejects(self):
        self.mutate('maps/MAP9G3_MAP', 8, '<i', -1)
        with self.assertRaisesRegex(ValueError, 'MAP header'): self.check()

    def test_bad_tile_library_rejects(self):
        self.mutate('maps/MAP9G3_MAP', 14, '<h', 4)
        with self.assertRaisesRegex(ValueError, 'MAP tile reference'): self.check()

    def test_out_of_range_flat_rejects(self):
        self.mutate('maps/MAP9G3_MAP', 12, '<h', 3)
        with self.assertRaisesRegex(ValueError, 'MAP tile reference'): self.check()

    def test_out_of_range_destroyed_reference_rejects(self):
        self.mutate('misc/FLATSG1_ITM', 0, '<i', 3)
        with self.assertRaisesRegex(ValueError, 'destruction reference'): self.check()

    def test_missing_root_approval_rejects(self):
        d = self.declaration(); d.pop('catalog_only_root_approval')
        with self.assertRaisesRegex(ValueError, 'hash-bound'): self.check(d)

    def test_root_approval_requires_actual_whole_picture_view(self):
        self.approval['whole_picture_personally_viewed'] = False
        with self.assertRaisesRegex(ValueError, 'Root whole-intrinsic'): self.check()

    def test_root_approval_cannot_claim_fabricated_context(self):
        self.approval['no_genuine_original_gameplay_context_claimed'] = False
        with self.assertRaisesRegex(ValueError, 'Root whole-intrinsic'): self.check()

    def test_root_approval_frame_hash_cannot_change(self):
        self.approval['frame_bindings_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'Root whole-intrinsic'): self.check()

    def test_peer_must_be_independent_from_preparer(self):
        self.peer['reviewer'] = 'preparer'
        with self.assertRaisesRegex(ValueError, 'independent qualified'): self.check()

    def test_peer_pending_is_not_qualification(self):
        self.peer['status'] = 'QUALIFIED_PENDING'
        with self.assertRaisesRegex(ValueError, 'independent qualified'): self.check()

    def test_peer_cannot_approve_different_raw(self):
        self.peer['raw']['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'source, raw'): self.check()

    def test_peer_cannot_skip_native_scale(self):
        self.peer['native_scales'] = [1, 2, 4]
        with self.assertRaisesRegex(ValueError, 'independent qualified'): self.check()

    def test_two_asset_scope_rejects(self):
        self.rows['00102'] = self.rows['00103']
        with self.assertRaisesRegex(ValueError, 'one complete'): self.check()

    def test_original_nonterrain_catalog_branch_still_rejects_terrain(self):
        # New opt-in cannot weaken the separate existing non-Terrain policy.
        d = self.declaration()
        with self.assertRaises(ValueError):
            m.approved_catalog_only_retained_evidence(self.root, self.project, d, self.rows, self.qa)


if __name__ == '__main__':
    unittest.main()
