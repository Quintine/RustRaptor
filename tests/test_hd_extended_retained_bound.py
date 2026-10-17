"""Maintained Source-density, namespace and read-only registrar regressions."""
import ast, copy, hashlib, importlib.util, json, pathlib, struct, sys, tempfile, unittest
from unittest import mock
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'));sys.path.insert(0,str(ROOT/'tests'))
import hd_frame_policy as policy
import hd_art_audit as audit
import hd_register_reviewed as registrar
import hd_candidate_review as candidate
import test_hd_retained_original_policy as old
from PIL import Image

def raw_source(painted, width=32, height=32):
    data=struct.pack('<5i',0,0,0,width,height)
    for y in range(height):
        n=max(0,min(width,painted-y*width))
        if n: data+=struct.pack('<4i',0,y,y*width,n)+bytes((y*width+x)%256 for x in range(n))
    return data+struct.pack('<4i',0,0,-1,0)

def frame(count, painted=625, width=32, height=32):
    raw=raw_source(painted,width,height)
    cells=sorted([[i%width,i//width] for i in range(painted)])[:count]
    return dict(frame=0,file='synthetic.png',logical_width=width,logical_height=height,origin=[0,0],source_sha256=hashlib.sha256(raw).hexdigest(),original_detail_cells=cells)

class ExtendedPolicy(unittest.TestCase):
    def test_exact_quarter_and_maximum_boundaries(self):
        for n,painted,ok in [(64,64,True),(65,260,True),(65,259,False),(73,625,True),(128,512,True),(128,511,False),(129,516,True),(129,515,False),(150,600,True),(150,599,False),(150,1024,True),(256,1024,True),(256,1023,False)]:
            with self.subTest(n=n,painted=painted):
                if ok: policy.validate_frame_policy(frame(n,painted),raw_source(painted))
                else:
                    with self.assertRaises(ValueError): policy.validate_frame_policy(frame(n,painted),raw_source(painted))
    def test_legacy_full_small_source_still_valid_without_new_density_rule(self):
        f=old.frame();f['original_detail_cells']=[[0,0],[0,1],[1,0],[1,1]]
        policy.validate_frame_policy(f,old.payload())
    def test_transparent_canvas_area_is_never_denominator(self):
        f=frame(65,259)
        self.assertEqual(f['logical_width']*f['logical_height'],1024)
        with self.assertRaisesRegex(ValueError,'quarter'): policy.validate_frame_policy(f,raw_source(259))
    def test_schema_preparation_is_not_final_density_approval(self):
        f=frame(65,259);policy.validate_frame_policy(f)
        rows=candidate.proposal_frames({'sequences':[dict(base_asset=1,frame_count=1,frames=[f])]})
        self.assertEqual(len(rows['00001']['original_detail_cells']),65)
        with self.assertRaises(ValueError):policy.validate_frame_policy(f,raw_source(259))
    def test_sorted_unique_inbounds_typed_and_painted_guards_remain(self):
        mutations=[lambda c:c[::-1],lambda c:c[:64]+[c[0]],lambda c:c[:64]+[[32,0]],lambda c:c[:64]+[[True,0]],lambda c:c[:64]+[[31,31]]]
        for mutate in mutations:
            f=frame(65);f['original_detail_cells']=mutate(f['original_detail_cells'])
            with self.subTest(cells=f['original_detail_cells'][-1]),self.assertRaises(ValueError):policy.validate_frame_policy(f,raw_source(625))
    def test_extended_reserved_painted_domain_and_nearest_cue_overlap(self):
        f=frame(128,512);policy.validate_frame_policy(f,raw_source(512))
        #256 is transparency, while raw labels0 and240..255 remain painted.
        self.assertEqual(sum(0<=p<=255 for p in policy._indices(raw_source(512))[2]),512)
        f['native_nearest_cues']=[f['original_detail_cells'][0]]
        with self.assertRaises(ValueError):policy.validate_frame_policy(f,raw_source(512))
    def test_legacy_v2_cannot_authorize_extended_and_v3_can_keep_legacy(self):
        for n in [1,64]:
            self.assertTrue(policy.retained_review_version_ok(policy.LEGACY_RETAINED_POLICY,{'00001':[[0,0]]*n}))
            self.assertTrue(policy.retained_review_version_ok(policy.EXTENDED_RETAINED_POLICY,{'00001':[[0,0]]*n}))
        self.assertFalse(policy.retained_review_version_ok(policy.LEGACY_RETAINED_POLICY,{'00001':[[0,0]]*65}))
        self.assertTrue(policy.retained_review_version_ok(policy.EXTENDED_RETAINED_POLICY,{'00001':[[0,0]]*65}))
        for bad in [None,True,'retained-original-details-v1',[]]:self.assertFalse(policy.retained_review_version_ok(bad,{'00001':[[0,0]]*65}))
    def test_audit_rejects_density_before_png_access(self):
        raw=raw_source(259);f=frame(65,259)
        with mock.patch.object(audit.Image,'open',side_effect=AssertionError('PNG read forbidden')):
            with self.assertRaisesRegex(ValueError,'quarter'):audit.validate_hd_frame(pathlib.Path('/absent'),f,raw,Image.new('RGBA',(32,32)))
    def test_real_synthetic_audit_accepts128_of512_without_raw_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            q=pathlib.Path(temp);raw=raw_source(512);src=q/'Source';src.write_bytes(raw)
            picture=audit.decode(src,[(i,i,i) for i in range(256)])
            image=Image.new('RGBA',(64,64),(40,50,60,255));image.putpixel((63,63),(0,0,0,0));image.save(q/'synthetic.png')
            before=(q/'synthetic.png').read_bytes()
            self.assertEqual(audit.validate_hd_frame(q,frame(128,512),raw,picture),64*64*4)
            self.assertEqual(before,(q/'synthetic.png').read_bytes())
    def test_malformed_source_and_canvas_still_rejected(self):
        f=frame(65)
        for raw in [b'',struct.pack('<5i',1,0,0,32,32),raw_source(625,25,25)]:
            with self.subTest(length=len(raw)),self.assertRaises(ValueError):policy.validate_frame_policy(f,raw)

class ExtendedRegistrar(old.ActualRegistrarProvenance):
    # Inherited legacy tests exercise actual approved_job unmodified call surface.
    def extended(self, painted=625, count=73, layout='project'):
        self.f=frame(count,painted);self.f['file']='raw.png';raw=raw_source(painted)
        self.candidate['sequences'][0]['frames']=[self.f];self.rows=candidate.proposal_frames(self.candidate);digest=candidate.binding_digest(self.rows)
        self.review['frame_bindings_sha256']=digest
        decl=self.review['retained_original_detail_review'];decl.update(cells_by_asset={'00001':self.f['original_detail_cells']},frame_bindings_sha256=digest,policy_version=(policy.MAX256_RETAINED_POLICY if count>128 else policy.EXTENDED_RETAINED_POLICY))
        self.write_json(self.job_dir/'candidate.json',self.candidate)
        self.write_json(self.job_dir/'job.json',dict(job_id='synthetic-complete1',targets=[dict(asset='00001',source_sha256=self.f['source_sha256'],logical_canvas=[32,32])]))
        qa=json.loads((self.root/'qa.json').read_text());qa['frame_bindings_sha256']=digest;qa['frames'][0].update(source_sha256=self.f['source_sha256'],logical_canvas=[32,32]);self.write_json(self.root/'qa.json',qa)
        data=(self.project/'data') if layout=='project' else self.project.parent/'data'
        (data/'sprites').mkdir(parents=True,exist_ok=True);(data/'sprites/fixture.pic').write_bytes(raw);(data/'INDEX').write_text(f'00001 {len(raw)} sprites/fixture.pic\n');return data
    def test_extended_actual_approved_job_both_catalog_layouts(self):
        data=self.extended();self.assertEqual(len(self.approve()[2]['00001']['original_detail_cells']),73)
        #Identical authenticated payload under the other product layout, no larger raw copies.
        (data/'INDEX').unlink();self.extended(layout='parent');self.assertEqual(len(self.approve()[2]['00001']['original_detail_cells']),73)
    def test_extended_old_version_rejected(self):
        self.extended();d=copy.deepcopy(self.review['retained_original_detail_review']);d['policy_version']=policy.LEGACY_RETAINED_POLICY
        with self.assertRaisesRegex(ValueError,'provenance'):self.approve(d)
    def test_extended_actual_source_density_beats_forged_claim(self):
        self.extended(259,65);self.review['retained_original_detail_review']['claimed_painted_Source_cell_count']=1024
        with self.assertRaisesRegex(ValueError,'quarter'):self.approve()
    def test_extended_actual_source_hash_required(self):
        data=self.extended();(data/'sprites/fixture.pic').write_bytes(raw_source(624))
        with self.assertRaisesRegex(ValueError,'authentic catalog Source'):self.approve()
    def test_extended_missing_source_rejected(self):
        data=self.extended();(data/'INDEX').unlink()
        with self.assertRaisesRegex(ValueError,'authentic catalog Source'):self.approve()
    def test_extended_source_path_escape_rejected(self):
        data=self.extended();(data/'INDEX').write_text('00001 4 ../outside.pic\n')
        with self.assertRaisesRegex(ValueError,'escapes catalog'):self.approve()
    def test_extended_genuine_context_and_retained_not_generated_still_required(self):
        self.extended()
        for key in ['hybrid_allscale_and_genuine_context_independent_review','retained_original_not_generated_HD']:
            d=copy.deepcopy(self.review['retained_original_detail_review']);d[key]=False
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'provenance'):self.approve(d)
    def test_density_helper_legacy_path_needs_no_catalog_io(self):
        with mock.patch.object(pathlib.Path,'read_text',side_effect=AssertionError('legacy catalog read')):
            registrar.validate_extended_retained_sources(pathlib.Path('/absent'),{'00001':old.selected()})


class Max256Policy(unittest.TestCase):
    def test_257_rejects_even_with4096_painted_cells(self):
        f=frame(257,4096,64,64)
        with self.assertRaisesRegex(ValueError,'at most256'):
            policy.validate_frame_policy(f,raw_source(4096,64,64))
    def test_all_rows_inspected_in_both_mixed_map_orders(self):
        rows=[('00001',frame(1,1024)['original_detail_cells']),
              ('00002',frame(128,1024)['original_detail_cells']),
              ('00003',frame(150,1024)['original_detail_cells'])]
        for ordered in (rows,list(reversed(rows))):
            mapping=dict(ordered)
            self.assertFalse(policy.retained_review_version_ok(policy.LEGACY_RETAINED_POLICY,mapping))
            self.assertFalse(policy.retained_review_version_ok(policy.EXTENDED_RETAINED_POLICY,mapping))
            self.assertTrue(policy.retained_review_version_ok(policy.MAX256_RETAINED_POLICY,mapping))
        for n in [129,150,256]:
            mapping={'00001':frame(n,1024)['original_detail_cells']}
            self.assertFalse(policy.retained_review_version_ok(policy.EXTENDED_RETAINED_POLICY,mapping))
            self.assertTrue(policy.retained_review_version_ok(policy.MAX256_RETAINED_POLICY,mapping))
        self.assertFalse(policy.retained_review_version_ok(policy.MAX256_RETAINED_POLICY,{'00001':[[0,0]]*257}))
        self.assertTrue(policy.retained_review_version_ok(policy.EXTENDED_RETAINED_POLICY,dict(rows[:2])))
    def test_new_tier_density_audit_before_image_and_exact256_png(self):
        with mock.patch.object(audit.Image,'open',side_effect=AssertionError('PNG read forbidden')):
            with self.assertRaisesRegex(ValueError,'quarter'):
                audit.validate_hd_frame(pathlib.Path('/absent'),frame(150,599),raw_source(599),Image.new('RGBA',(32,32)))
        with tempfile.TemporaryDirectory() as temp:
            q=pathlib.Path(temp);raw=raw_source(1024);(q/'Source').write_bytes(raw)
            picture=audit.decode(q/'Source',[(i,i,i) for i in range(256)])
            Image.new('RGBA',(64,64),(40,50,60,255)).save(q/'synthetic.png')
            before=(q/'synthetic.png').read_bytes()
            self.assertEqual(audit.validate_hd_frame(q,frame(256,1024),raw,picture),16384)
            self.assertEqual(before,(q/'synthetic.png').read_bytes())
    def test_default_serialization_digest_and_new_cell_list_binding(self):
        f=old.frame();f['file']='raw.png'
        c=dict(sequences=[dict(base_asset=1,frame_count=1,frames=[f])])
        default=candidate.proposal_frames(c)
        empty=copy.deepcopy(c);empty['sequences'][0]['frames'][0]['original_detail_cells']=[]
        self.assertNotEqual(candidate.binding_digest(default),candidate.binding_digest(candidate.proposal_frames(empty)),
                            'Python native binding keeps literal optional presence; Rust serde omits empty')
        a=frame(128,1024);b=frame(150,1024)
        self.assertNotEqual(candidate.binding_digest({'00001':a}),candidate.binding_digest({'00001':b}))

class Max256Registrar(ExtendedRegistrar):
    def test_actual150_and256_read_only_approved_job(self):
        for n,painted in [(150,600),(256,1024)]:
            with self.subTest(n=n):
                self.extended(painted,n)
                self.assertEqual(len(self.approve()[2]['00001']['original_detail_cells']),n)
    def test_old_v3_cannot_approve150_or256(self):
        for n in [150,256]:
            self.extended(1024,n)
            for version in [policy.LEGACY_RETAINED_POLICY,policy.EXTENDED_RETAINED_POLICY]:
                d=copy.deepcopy(self.review['retained_original_detail_review']);d['policy_version']=version
                with self.subTest(n=n,version=version),self.assertRaisesRegex(ValueError,'provenance'):self.approve(d)
    def test_150_claimed_painted_count_does_not_override_authentic599(self):
        self.extended(599,150);self.review['retained_original_detail_review']['claimed_painted_Source_cell_count']=1024
        with self.assertRaisesRegex(ValueError,'quarter'):self.approve()
    def test_exact_new_frame_cells_source_and_old_qa_binding_required(self):
        self.extended(1024,150)
        declaration=copy.deepcopy(self.review['retained_original_detail_review'])
        declaration['cells_by_asset']['00001'][-1]=[31,31]
        with self.assertRaisesRegex(ValueError,'provenance'):self.approve(declaration)
        qa_path=self.root/'qa.json';qa=json.loads(qa_path.read_text());qa['frame_bindings_sha256']='0'*64
        self.write_json(qa_path,qa)
        with self.assertRaisesRegex(ValueError,'runtime evidence differs'):self.approve()
    def mixed(self,reverse=False):
        raw=raw_source(1024);counts=[1,128,150]
        sequences=[dict(name='synthetic mixed tier',base_asset=i+1,frame_count=1,frames=[dict(frame(n,1024),file='raw.png')]) for i,n in enumerate(counts)]
        if reverse:sequences.reverse()
        self.candidate['sequences']=sequences
        self.rows=candidate.proposal_frames(self.candidate);digest=candidate.binding_digest(self.rows)
        self.review['frame_bindings_sha256']=digest
        self.review['retained_original_detail_review'].update(policy_version=policy.MAX256_RETAINED_POLICY,
            cells_by_asset={a:f['original_detail_cells'] for a,f in self.rows.items()},frame_bindings_sha256=digest)
        self.write_json(self.job_dir/'candidate.json',self.candidate)
        self.write_json(self.job_dir/'job.json',dict(job_id='synthetic-complete1',targets=[dict(asset=a,source_sha256=f['source_sha256'],logical_canvas=[32,32]) for a,f in self.rows.items()]))
        qa=json.loads((self.root/'qa.json').read_text());base=qa['frames'][0]
        qa['frames']=[dict(copy.deepcopy(base),asset=a,source_sha256=f['source_sha256'],logical_canvas=[32,32]) for a,f in self.rows.items()]
        qa['frame_bindings_sha256']=digest;self.write_json(self.root/'qa.json',qa)
        data=self.project/'data';(data/'sprites').mkdir(parents=True,exist_ok=True);(data/'sprites/fixture.pic').write_bytes(raw)
        (data/'INDEX').write_text(''.join(f'{a} {len(raw)} sprites/fixture.pic\n' for a in self.rows))
    def test_real_approved_job_mixed_1_128_150_both_map_orders(self):
        for reverse in [False,True]:
            self.mixed(reverse)
            for version in [policy.LEGACY_RETAINED_POLICY,policy.EXTENDED_RETAINED_POLICY]:
                d=copy.deepcopy(self.review['retained_original_detail_review']);d['policy_version']=version
                with self.subTest(reverse=reverse,version=version),self.assertRaisesRegex(ValueError,'provenance'):self.approve(d)
            self.assertEqual({a:len(f['original_detail_cells']) for a,f in self.approve()[2].items()},
                             {'00001':1,'00002':128,'00003':150})

class RustSourceCompatibility(unittest.TestCase):
    def test_legacy_hd_function_bodies_and_normalized_key_tags_remain_exact(self):
        # Exact pre-bounds atlas baseline (36b3502e), formerly read from the
        # private proposal's sibling original/src/hd.rs. Inline fingerprints
        # preserve those exact guards in an ordinary standalone checkout.
        expected = {'source_reference_budget': '1e544a7639fd123a6e813fbb34f1ded100a1db192973faeb7ce1b96ad54339a0', 'retain_original_detail_samples': '5b1516291d05de782f4d81242f38686be1dca24d00ab0ee4858e3b92729a73b4', 'sprite_with_policy': '7def63d10f179c30ad71c02b3670ca457a7652a976b4c97c1a9098388655fed5', 'terrain_sprite': 'b5d713c0ed8e5327d96c1dae464b2aca4b5e8c9450f85c53928bdde5c99b6e99', 'frame_key': '3605c9fc321571dbc777036ff500f8c436ebb1e717343c056e363c4b634ea1a1', 'original_detail_cache_identity': 'bb9baa84ba832e34dea5274866ddbde52b35f48634cff0ff80533a4dc6d81ffc'}
        new=(ROOT/'src/hd.rs').read_text()
        def function(s,name):
            start=s.index('fn '+name+'(');left=s.index('{',start);depth=1;end=left+1
            while depth:depth+=(s[end]=='{')-(s[end]=='}');end+=1
            return s[start:end]
        # Keep the old fingerprints. Strip only the explicit new opt-in branch;
        # the None/default sampler and Original-retention kernel must remain exact.
        for name in ['source_reference_budget','retain_original_detail_samples']:
            self.assertEqual(expected[name],hashlib.sha256(function(new,name).encode()).hexdigest(),name)
        sampler = function(new,'sprite_with_policy')
        opt_in = """PalettePolicy::SourceClasses | PalettePolicy::SourceClassesBaseline =>
                        replacement.original_palette.as_ref().map_or_else(
                            || closest(palette,rgb,source_label),
                            |domain| domain.closest(palette,rgb.map(i32::from))),"""
        self.assertEqual(sampler.count(opt_in),1)
        sampler=sampler.replace(opt_in,'PalettePolicy::SourceClasses | PalettePolicy::SourceClassesBaseline => closest(palette, rgb, source_label),')
        self.assertEqual(expected['sprite_with_policy'],hashlib.sha256(sampler.encode()).hexdigest())
        implementation=function(new,'terrain_sprite_impl')
        signature='fn terrain_sprite(&mut self, id: u32, scale: usize, palette: &[[u8; 3]; 256])\n        -> Result<Option<(Sprite, Option<OriginalDetailCells>)>>\n    {'
        normalized=signature+implementation[implementation.index('{')+1:]
        self.assertEqual(expected['terrain_sprite'],hashlib.sha256(normalized.encode()).hexdigest())
        wrapper=function(new,'terrain_sprite')
        self.assertIn('palette_constraint.is_some()',wrapper)
        self.assertIn('self.terrain_sprite_impl(id,scale,palette)',wrapper)
        for name,old_bytes,call in [('frame_key','b"raptor-retained-original-details-v2-painted0255"','original_detail_policy_tag(frame.original_detail_cells.len(), false)'),('original_detail_cache_identity','b"retained-original-rejected-fallback-v2-painted0255"','original_detail_policy_tag(frame.original_detail_cells.len(), true)')]:
            body=function(new,name)
            if name=='frame_key':
                branch='        if frame.palette_constraint.is_some() {\n            digest.update(b"raptor-hd-original-painted-ordinary-palette-v1");\n        }\n'
                self.assertEqual(body.count(branch),1);body=body.replace(branch,'')
            self.assertEqual(expected[name],hashlib.sha256(body.replace(call,old_bytes).encode()).hexdigest(),name)
    def test_audit_still_calls_actual_payload_validator(self):
        tree=ast.parse((ROOT/'tools/hd_art_audit.py').read_text())
        node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='validate_hd_frame')
        self.assertIsInstance(node.body[1],ast.Expr)
        self.assertEqual(ast.unparse(node.body[1]),'validate_frame_policy(frame, payload)')

if __name__=='__main__':unittest.main(verbosity=2)
