import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
S=ROOT/'.reference/hd-SHIP09G2-all-Source-cyan-ownership-code-successor-20261019-v2'
OLD=ROOT/'.reference/hd-SHIP09G2-wake-only-buffered-cleanup-code-proposal-20261019-v1'
spec=importlib.util.spec_from_file_location('focused_tests',S/'test_hd_ship09_wake_cleanup.py')
tests=importlib.util.module_from_spec(spec);spec.loader.exec_module(tests)
tool=tests.tool

class Independent(unittest.TestCase):
    def setUp(self):
        self.f=tests.RecipeTests();self.f.setUp()
    def tearDown(self):self.f.tearDown()
    def test_verified_buffers_and_three_way_partition(self):
        f=self.f
        # A noncyan structural hole is intentional. A stray parent sample in
        # transparent Source is intentionally cleared, even if parent is solid.
        s4=tool.scale2(tool.scale2(f.sources[0]));non=(s4<256)&~tool.water(s4)
        y,x=np.argwhere(non)[20];f.bank[0]['scales'][3]['indices'][int(y)*288+int(x)]=256
        f.bank[0]['scales'][3]['indices'][0]=16
        f.write()
        with patch.object(Path,'read_bytes',side_effect=AssertionError('unbuffered Path reopen')):
            receipt=tool.run_recipe(f.path,f.output,f.project)
        self.assertEqual(receipt['execution']['status'],'success')
        for i,a in enumerate(tool.ASSETS):
            out=np.asarray(Image.open(f.output/(a+'.png')))
            src=tool.scale2(tool.scale2(f.sources[i]));cyan=(src>=144)&(src<=159)
            non=(src<256)&~cyan;clear=src==256
            idx=np.array(f.bank[i]['scales'][3]['indices']).reshape(src.shape)
            lut=np.zeros((257,4),np.uint8);lut[:256,:3]=f.palette;lut[:256,3]=255
            self.assertTrue(np.array_equal(out[non],lut[idx][non]))
            self.assertTrue(np.all(out[clear]==0));self.assertTrue(np.all(out[cyan,3]==255))
            cx,cy,w,h=f.crops[i];r=f.raw[cy:cy+h,cx:cx+w]
            caps=tool.source_caps(f.sources,f.palette)
            eligible=(r[:,:,3]>=128)&tool.cyan_donors(r[:,:,:3],caps)
            genuine=set(map(tuple,r[:,:,:3][eligible]));self.assertTrue(all(tuple(v) in genuine for v in out[:,:,:3][cyan]))
            self.assertEqual(receipt['reports'][i]['Original_RGB_samples_painted'],0)
    def test_pure_gray_cyan_canary_repaired_without_changing_engine(self):
        f=self.f;caps=tool.source_caps(f.sources,f.palette)
        src=tool.scale2(tool.scale2(f.sources[0]));b=np.array(f.bank[0]['scales'][3]['indices']).reshape(src.shape)
        cyan=(src>=144)&(src<=159);b[cyan]=1
        result,report=tool.render_frame(f.sources[0],f.palette,f.raw,f.crops[0],b,caps)
        non=(src<256)&~cyan
        self.assertTrue(np.all(tool.cyan_donors(result[:,:,:3],caps)[cyan]))
        self.assertTrue(np.array_equal(result[:,:,:3][non],f.palette[b[non]]))
        self.assertTrue(np.all(result[:,:,3][src==16]==255))
        self.assertLessEqual(report['maximum_donor_logical_distance'],5.5)
    def test_only_own_phase_donor_material_can_change(self):
        f=self.f;caps=tool.source_caps(f.sources,f.palette)
        baselines=[np.array(b['scales'][3]['indices']).reshape(160,288) for b in f.bank]
        before=[tool.render_frame(f.sources[i],f.palette,f.raw,f.crops[i],baselines[i],caps)[0] for i in range(2)]
        changed=f.raw.copy();x,y,w,h=f.crops[0];reg=changed[y:y+h,x:x+w]
        good=(reg[:,:,3]>=128)&tool.cyan_donors(reg[:,:,:3],caps)
        yy,xx=np.indices((h,w));r=(20+(xx+yy)%40).astype(np.uint8)
        colors=np.stack((r,r+53,r+60),axis=2);reg[good,:3]=colors[good]
        after=[tool.render_frame(f.sources[i],f.palette,changed,f.crops[i],baselines[i],caps)[0] for i in range(2)]
        self.assertTrue(np.array_equal(before[1],after[1]));self.assertFalse(np.array_equal(before[0],after[0]))
        s4=tool.scale2(tool.scale2(f.sources[0]));non=(s4<256)&~tool.water(s4)
        self.assertTrue(np.array_equal(before[0][non],after[0][non]))
    def test_unchanged_verified_IO_caps_and_Source_math(self):
        def funcs(p):return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(p.read_text()).body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
        old,new=funcs(OLD/'hd_ship09_wake_cleanup.py'),funcs(S/'hd_ship09_wake_cleanup.py')
        changed={name for name in old if old[name]!=new[name]}
        self.assertEqual(changed,{'render_frame','run_recipe'})
        for key in ['DISTANCE_CAP','MISSING_CAP','AGGREGATE_CAP','MIN_DONORS','MIN_DONOR_COLORS']:
            # Compare literal assignments even if a limit's public name changes.
            def assignment(p):
                for n in ast.parse(p.read_text()).body:
                    if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==key for t in n.targets):return ast.dump(n.value)
            self.assertEqual(assignment(OLD/'hd_ship09_wake_cleanup.py'),assignment(S/'hd_ship09_wake_cleanup.py'))

if __name__=='__main__':
    suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(tests.RecipeTests),unittest.defaultTestLoader.loadTestsFromTestCase(tests.DescriptorTests),unittest.defaultTestLoader.loadTestsFromTestCase(Independent)])
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())
