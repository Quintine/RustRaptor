import sys
sys.dont_write_bytecode=True
from pathlib import Path
import hashlib,importlib.util,json,tempfile,unittest
from PIL import Image

OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import hd_art_audit as audit

class PythonRoundingMirror(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='python-fixture-',dir=OUT)
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.payload=b'synthetic original payload'
        self.picture=Image.new('RGBA',(8,5),(80,100,120,255))
        self.frame={'source_sha256':hashlib.sha256(self.payload).hexdigest(),'logical_width':8,'logical_height':5,'origin':[0,0],'file':'fixture.png'}
    def artwork(self,size,alpha=255):
        Image.new('RGBA',size,(80,100,120,alpha)).save(self.root/'fixture.png')
    def check(self):
        return audit.validate_hd_frame(self.root,self.frame,self.payload,self.picture)
    def test_full_opaque_landscape_has_only_integer_aspect_rounding(self):
        self.picture=Image.new('RGBA',(320,200),(80,100,120,255))
        self.frame.update(logical_width=320,logical_height=200,crop=[0,0,1586,992])
        self.artwork((1586,992))
        self.assertEqual(self.check(),1280*800*4)
    def test_full_image_none_and_explicit_crop_accept_rounding(self):
        self.artwork((17,11))
        self.assertEqual(self.check(),17*11*4)
        self.frame['crop']=[0,0,17,11]
        self.assertEqual(self.check(),17*11*4)
    def test_portrait_rounding_accepts_and_arbitrary_aspect_rejects(self):
        self.picture=Image.new('RGBA',(5,8),(0,0,0,255))
        self.frame.update(logical_width=5,logical_height=8)
        self.artwork((11,17));self.assertEqual(self.check(),11*17*4)
        self.artwork((12,17))
        with self.assertRaisesRegex(ValueError,'aspect differs'):self.check()
    def test_nonopaque_raw_rejected_before_resampling(self):
        for alpha in (0,128,254):
            with self.subTest(alpha=alpha):
                raw=Image.new('RGBA',(161,101),(0,0,0,255));raw.putpixel((160,100),(0,0,0,alpha))
                raw.save(self.root/'fixture.png')
                with self.assertRaisesRegex(ValueError,'fully opaque'):self.check()
    def test_transparent_original_cannot_use_rounding(self):
        self.picture.putpixel((0,0),(0,0,0,0));self.artwork((17,11))
        with self.assertRaisesRegex(ValueError,'aspect differs'):self.check()
    def test_partial_crop_never_gets_exception(self):
        self.artwork((18,12))
        for crop in ([0,0,17,11],[1,1,17,11]):
            with self.subTest(crop=crop):
                self.frame['crop']=crop
                with self.assertRaisesRegex(ValueError,'aspect differs'):self.check()
    def test_exact_aspect_transparent_source_and_cropped_atlas_are_unchanged(self):
        self.picture.putpixel((0,0),(0,0,0,0));self.artwork((20,12))
        raw=Image.open(self.root/'fixture.png').convert('RGBA');raw.putpixel((2,2),(0,0,0,0));raw.save(self.root/'fixture.png')
        self.frame['crop']=[2,2,16,10]
        self.assertEqual(self.check(),16*10*4)
    def test_half_tie_wrong_aspect_low_resolution_hash_and_origin_stay_rejected(self):
        self.assertFalse(audit.integer_rounded_aspect(5,6,2,2))
        self.artwork((15,10))
        with self.assertRaisesRegex(ValueError,'twice'):self.check()
        self.artwork((17,11));self.frame['source_sha256']='wrong'
        with self.assertRaisesRegex(ValueError,'hash'):self.check()
        self.frame['source_sha256']=hashlib.sha256(self.payload).hexdigest();self.frame['origin']=[1,0]
        with self.assertRaisesRegex(ValueError,'anchor'):self.check()
    def test_common_scale_nearest_integer_fixtures(self):
        checked=0
        for w in range(1,17):
            for h in range(1,17):
                for numerator in range(128,1025):
                    self.assertTrue(audit.integer_rounded_aspect((w*numerator+32)//64,(h*numerator+32)//64,w,h))
                    checked+=1
        self.assertEqual(checked,229632)

if __name__=='__main__':unittest.main(verbosity=2)
