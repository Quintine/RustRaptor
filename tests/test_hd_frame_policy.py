import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import copy, struct, unittest, tempfile,hashlib
from pathlib import Path
from PIL import Image
from hd_frame_policy import validate_frame_policy, _indices

class FramePolicyTests(unittest.TestCase):
    def setUp(self):
        self.frame={"logical_width":2,"logical_height":2}
        self.raw=struct.pack("<iiiii",1,0,0,2,2)+bytes([5,239,0,30])
    def test_absent_or_explicit_default_metadata_is_valid(self):
        validate_frame_policy(self.frame,self.raw)
        self.frame.update(preserve_reserved_coverage=False,native_nearest_cues=[])
        validate_frame_policy(self.frame,self.raw)
    def test_valid_explicit_flags_and_sorted_ordinary_cells(self):
        self.frame.update(preserve_reserved_coverage=True,native_nearest_cues=[[0,0],[1,0]])
        validate_frame_policy(self.frame,self.raw)
    def test_coverage_type_is_strict(self):
        for value in [0,1,"yes",None,[],{}]:
            with self.subTest(value=value),self.assertRaises(ValueError):
                validate_frame_policy(dict(self.frame,preserve_reserved_coverage=value))
    def test_coordinate_structure_bounds_types_order_duplicates_limit(self):
        for value in [None,"yes",{},[[0]],[[0,0,0]],[[True,0]],[[0.0,0]],[[-1,0]],[[2,0]],[[0,2]],[[0,0],[0,0]],[[1,0],[0,0]],[[0,0]]*65]:
            with self.subTest(value=value),self.assertRaises(ValueError):
                validate_frame_policy(dict(self.frame,native_nearest_cues=value),self.raw)
    def test_ordinary_cues_never_use_reserved_source_indices(self):
        self.frame['native_nearest_cues']=[[0,0]]
        for label in [240,244,245,249,250,255]:
            with self.subTest(label=label),self.assertRaises(ValueError):
                validate_frame_policy(self.frame,self.raw[:20]+bytes([label,5,5,5]))
    def test_sparse_source_requires_actual_complete_coverage(self):
        header=struct.pack('<iiiii',0,0,0,2,2)
        end=struct.pack('<iiii',0,0,-1,0)
        sparse=header+struct.pack('<iiii',0,0,0,2)+bytes([5,5])+end
        self.frame['native_nearest_cues']=[[0,0]]
        with self.assertRaises(ValueError):validate_frame_policy(self.frame,sparse)
        complete=header+struct.pack('<iiii',0,0,0,2)+bytes([5,5])+struct.pack('<iiii',0,1,0,2)+bytes([5,5])+end
        validate_frame_policy(self.frame,complete)
    def test_checked_source_rejects_invalid_or_truncated_original(self):
        self.frame['native_nearest_cues']=[[0,0]]
        for payload in [b'',self.raw[:22],struct.pack('<iiiii',1,0,0,4096,4096),struct.pack('<iiiii',3,0,0,2,2)]:
            with self.subTest(payload=payload),self.assertRaises(ValueError):validate_frame_policy(self.frame,payload)
    def test_matched_candidate_tool_checks_flags_and_exact_target_bindings(self):
        from hd_candidate_review import proposal_frames
        f=dict(self.frame,frame=0,file='a.png',origin=[0,0],source_sha256='00',native_nearest_cues=[[0,0]])
        pack={'sequences':[{'name':'a','base_asset':1,'frame_count':1,'frames':[f]}]}
        self.assertEqual(set(proposal_frames(pack)),{'00001'})
        bad=copy.deepcopy(pack);bad['sequences'][0]['frames'][0]['preserve_reserved_coverage']=1
        with self.assertRaises(ValueError):proposal_frames(bad)
        bad=copy.deepcopy(pack);bad['targets']=[dict(f,asset='00001',native_nearest_cues=[])]
        with self.assertRaises(ValueError):proposal_frames(bad)
    def test_matched_art_audit_checks_original_index_and_transparency(self):
        from hd_art_audit import validate_hd_frame
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);Image.new('RGBA',(8,8),(10,20,30,255)).save(root/'a.png')
            f=dict(self.frame,frame=0,file='a.png',origin=[0,0],source_sha256=hashlib.sha256(self.raw).hexdigest(),native_nearest_cues=[[0,0]])
            picture=Image.new('RGBA',(2,2),(10,20,30,255))
            self.assertEqual(validate_hd_frame(root,f,self.raw,picture),8*8*4)
            reserved=self.raw[:20]+bytes([253,5,5,5]);f['source_sha256']=hashlib.sha256(reserved).hexdigest()
            with self.assertRaisesRegex(ValueError,'ordinary'):validate_hd_frame(root,f,reserved,picture)
    def test_unknown_frame_policy_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'unknown'):validate_frame_policy(dict(self.frame,imaginary_cue_rule=True))

if __name__=='__main__':unittest.main()
