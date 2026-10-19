"""Synthetic genuine-RLE72x40 pairs; unmocked buffered CLI/receipt path.

No real artwork is derived by these tests. Synthetic QA/bank records exercise
provenance linkage, not a claim of an actual Rust invocation or artistic review.
"""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('ship09_under_test', HERE/'hd_ship09_wake_cleanup.py')
tool = importlib.util.module_from_spec(spec);spec.loader.exec_module(tool)
PROJECT = HERE.parents[1] if HERE.parent.name == '.reference' else HERE.parent
if not (PROJECT/'tools/hd_frame_policy.py').is_file():
    PROJECT = next(p for p in HERE.parents if (p/'tools/hd_frame_policy.py').is_file())


def rle(source):
    h, w = source.shape
    out = bytearray(struct.pack('<5i', 0, 0, 0, w, h))
    for y in range(h):
        x = 0
        while x < w:
            if source[y, x] == 256:
                x += 1;continue
            start = x
            while x < w and source[y, x] < 256:x += 1
            out.extend(struct.pack('<4i', start, y, y*w+start, x-start))
            out.extend(bytes(int(z) for z in source[y, start:x]))
    out.extend(struct.pack('<4i', 0, 0, -1, 0))
    return bytes(out)


class RecipeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory();self.root = Path(self.tmp.name)
        self.project = self.root/'project';(self.project/'tools').mkdir(parents=True)
        shutil.copyfile(PROJECT/'tools/hd_frame_policy.py', self.project/'tools/hd_frame_policy.py')
        self.base = self.root/'inputs';self.base.mkdir();self.output = self.root/'derived'
        self.path = self.base/'recipe.json';self.crops = [[30,330,729,405],[763,330,729,405]]
        # Synthetic VGA palette: only the authentic cyan ramp and brown/gray
        # examples are material fixtures, not copies of an original sprite.
        p = np.zeros((256,3),np.uint8)
        for i in range(32):p[i] = [63-i*2]*3
        for i in range(16):p[144+i] = [max(0,27-2*i),max(5,42-2*i),max(7,44-2*i)]
        for i in range(209,240):p[i] = [42,27,15]
        self.pb = p.tobytes();(self.base/'palette.bin').write_bytes(self.pb)
        p16 = p.astype(np.uint16);self.palette = ((p16<<2)|(p16>>4)).astype(np.uint8)
        self.sources = []
        self.raw = np.zeros((1024,1536,4),np.uint8)
        self.bank = []
        for i in range(2):
            s = np.full((40,72),256,np.uint16);s[10:31,7:46] = 215
            s[14:27,34:43] = 16;s[18:20,15:30] = 151;s[9,15:20] = 151  # cyan hull paint
            for y,x0,x1 in [(3+i,14,66),(35+i,15,69),(17+i,49,69)]:
                s[y,x0:x1] = 144+(np.arange(x0,x1)+y)%16
            self.sources.append(s);(self.base/(tool.ASSETS[i]+'.bin')).write_bytes(rle(s))
            x,y,w,h = self.crops[i];yy,xx = np.indices((h,w));lx=np.floor((xx+.5)/(w/72)).astype(int);ly=np.floor((yy+.5)/(h/40)).astype(int)
            idx=s[ly,lx];region=self.raw[y:y+h,x:x+w];paint=idx<256;region[paint,3]=255;region[paint,:3]=self.palette[idx[paint]]
            blue=tool.water(idx);r=10+(xx*7+yy*11)%60;rgb=np.stack([r,r+53,r+60],axis=2).astype(np.uint8);region[blue,:3]=rgb[blue]
            # Ineligible pale samples force local bounded repair; immutable raw
            # still carries varied nearby darker generated-like cyan donors.
            pale=blue & ((xx//35)%5==0);region[pale,:3]=[245,250,255]
            scales=[]
            for k in range(1,5):
                b=np.repeat(np.repeat(s,k,axis=0),k,axis=1)
                # Deliberately wrong exterior baseline waves; hull is protected.
                guard=np.repeat(np.repeat(tool.hull_guard(s),k,axis=0),k,axis=1)
                b[~guard]=256;b[(~guard)&(np.indices(b.shape)[0]==2*k)]=6
                # Synthetic held pale glare exists on BOTH halo and internal
                # Source-cyan paint, while real gray engine owners stay gray.
                source_k=np.repeat(np.repeat(s,k,axis=0),k,axis=1)
                b[tool.water(source_k)&guard]=1
                scales.append(dict(scale=k,width=72*k,height=40*k,indices=b.ravel().tolist()))
            self.bank.append(dict(asset=tool.ASSETS[i],source=dict(width=72,height=40,indices=s.ravel().tolist()),scales=scales))
        self.save_raw();self.candidate=dict(format_version=1,job_id='synthetic-only',complete_family=True,sequences=[dict(name='SHIP09G2_PIC',base_asset=0x2009f,frame_count=2,frames=[dict(frame=i,file='raw.png',logical_width=72,logical_height=40,origin=[0,0],source_sha256='',crop=c)for i,c in enumerate(self.crops)])])
        self.qa=dict(validated_frames=2,diagnostics=[],actual_sourceG2_helper_sha256=tool.G2_HELPER_SHA,library_sha256=tool.G2_LIBRARY_SHA,source_newer_than_library=False,any_game_source_newer_than_library=False,frames=[])
        self.recipe=dict(format_version=1,method=tool.METHOD,frames=[dict(asset=a,source={},crop=c)for a,c in zip(tool.ASSETS,self.crops)])

    def tearDown(self):self.tmp.cleanup()

    def save_raw(self):Image.fromarray(self.raw).save(self.base/'raw.png')

    def bind(self,p):return dict(path=str(p.relative_to(self.base)),sha256=tool.sha(p.read_bytes()))

    def write(self):
        for i,a in enumerate(tool.ASSETS):
            self.recipe['frames'][i]['source']=self.bind(self.base/(a+'.bin'))
            self.candidate['sequences'][0]['frames'][i]['source_sha256']=self.recipe['frames'][i]['source']['sha256']
        (self.base/'candidate.json').write_text(json.dumps(self.candidate))
        rows={a:f for a,f in zip(tool.ASSETS,self.candidate['sequences'][0]['frames'])}
        self.qa.update(candidate_sha256=tool.sha((self.base/'candidate.json').read_bytes()),frame_bindings_sha256=tool.sha(json.dumps(rows,sort_keys=True,separators=(',',':')).encode()),artwork_sha256={'raw.png':tool.sha((self.base/'raw.png').read_bytes())},frames=[dict(asset=f['asset'],source_sha256=f['source']['sha256'],logical_canvas=[72,40])for f in self.recipe['frames']])
        (self.base/'qa.json').write_text(json.dumps(self.qa));(self.base/'bank.json').write_text(json.dumps(self.bank))
        inv=dict(exit_code=0,runtime_QA_sha256=tool.sha((self.base/'qa.json').read_bytes()),indexed_bank_sha256=tool.sha((self.base/'bank.json').read_bytes()))
        (self.base/'invocation.json').write_text(json.dumps(inv))
        for k,f in [('raw_png','raw.png'),('palette','palette.bin'),('candidate','candidate.json'),('runtime_qa','qa.json'),('indexed_bank','bank.json'),('actual_invocation','invocation.json')]:self.recipe[k]=self.bind(self.base/f)
        self.path.write_text(json.dumps(self.recipe))

    def run_real(self):self.write();return tool.run_recipe(self.path,self.output,self.project)

    def reject(self,pattern='.*'):
        self.write()
        with self.assertRaisesRegex((ValueError,FileNotFoundError),pattern):tool.run_recipe(self.path,self.output,self.project)
        self.assertFalse(self.output.exists())

    def test_unmocked_complete2_RLE_receipt_exact_hull_wake_support_and_raw_RGB(self):
        before=self.raw.copy();receipt=self.run_real();self.assertEqual(receipt,json.loads((self.output/'execution-receipt.json').read_text()));self.assertEqual(len(list(self.output.glob('*.png'))),2)
        caps=tool.source_caps(self.sources,self.palette)
        for i,a in enumerate(tool.ASSETS):
            out=np.asarray(Image.open(self.output/(a+'.png')));s4=tool.scale2(tool.scale2(self.sources[i]));g=(s4<256)&~tool.water(s4);wake=tool.water(s4)
            lut=np.zeros((257,4),np.uint8);lut[:256,:3]=self.palette;lut[:256,3]=255;baseline=lut[np.array(self.bank[i]['scales'][3]['indices']).reshape(160,288)]
            self.assertTrue(np.array_equal(out[g],baseline[g]));self.assertTrue(np.array_equal(out[:,:,3][~g],np.where(wake,255,0)[~g]));self.assertTrue(np.all(tool.cyan_donors(out[:,:,:3],caps)[wake]))
            x,y,w,h=self.crops[i];donors={tuple(z)for z in self.raw[y:y+h,x:x+w,:3].reshape(-1,3)};self.assertTrue(all(tuple(z)in donors for z in out[:,:,:3][wake]));self.assertGreater(receipt['reports'][i]['repaired'],0);self.assertEqual(receipt['reports'][i]['Original_RGB_samples_painted'],0)
        self.assertTrue(np.array_equal(before,self.raw));self.assertEqual(receipt['execution']['parent_raw_sha256'],[tool.sha((self.base/'raw.png').read_bytes())])

    def test_interior_and_halo_gray_glare_restored_while_gray_engine_is_unchanged(self):
        receipt=self.run_real()
        for i,a in enumerate(tool.ASSETS):
            source4=tool.scale2(tool.scale2(self.sources[i]));cyan=tool.water(source4);noncyan=(source4<256)&~cyan
            out=np.asarray(Image.open(self.output/(a+'.png')));parent=np.array(self.bank[i]['scales'][3]['indices']).reshape(160,288)
            hull=np.repeat(np.repeat(tool.hull_guard(self.sources[i]),4,axis=0),4,axis=1)
            self.assertTrue((cyan&hull&(parent==1)).any())
            caps=tool.source_caps(self.sources,self.palette)
            self.assertTrue(np.all(tool.cyan_donors(out[:,:,:3],caps)[cyan]))
            self.assertTrue(np.all(out[:,:,3][cyan]==255))
            engine=(source4==16);self.assertTrue(engine.any())
            self.assertTrue(np.array_equal(out[:,:,:3][engine],self.palette[parent[engine]]))
            self.assertTrue(np.array_equal(out[:,:,3][noncyan],np.where(parent[noncyan]<256,255,0)))
    def test_noncyan_baseline_hole_is_preserved_instead_of_fabricating_Source_alpha(self):
        s4=tool.scale2(tool.scale2(self.sources[0]));yy,xx=np.where(s4==16);pos=int(yy[0])*288+int(xx[0]);self.bank[0]['scales'][3]['indices'][pos]=256
        self.run_real();out=np.asarray(Image.open(self.output/'2009f.png'));self.assertEqual(out[int(yy[0]),int(xx[0])].tolist(),[0,0,0,0])
    def test_same_phase_raw_cyan_change_does_not_change_other_phase_or_noncyan_hull(self):
        self.run_real();first=[np.asarray(Image.open(self.output/(a+'.png'))).copy()for a in tool.ASSETS]
        shutil.rmtree(self.output);x,y,w,h=self.crops[0];region=self.raw[y:y+h,x:x+w];caps=tool.source_caps(self.sources,self.palette);eligible=(region[:,:,3]>=128)&tool.cyan_donors(region[:,:,:3],caps)
        # Both hues are genuine synthetic eligible inputs, not a code gain.
        yy,xx=np.indices((h,w));r=15+(xx*3+yy*7)%50;changed=np.stack([r,r+53,r+60],axis=2).astype(np.uint8);region[eligible,:3]=changed[eligible];self.save_raw();self.run_real();second=[np.asarray(Image.open(self.output/(a+'.png'))).copy()for a in tool.ASSETS]
        self.assertTrue(np.array_equal(first[1],second[1]));s4=tool.scale2(tool.scale2(self.sources[0]));non=(s4<256)&~tool.water(s4)
        self.assertTrue(np.array_equal(first[0][non],second[0][non]));self.assertFalse(np.array_equal(first[0],second[0]))
    def test_Source_hue_caps_accept_genuine_cyan_but_reject_gray_pale_and_wrong_hue(self):
        caps=tool.source_caps(self.sources,self.palette)
        values=np.array([[[40,93,100],[240,245,255],[100,100,100],[10,40,100],[10,100,105]]],np.uint8)
        self.assertEqual(tool.cyan_donors(values,caps).tolist(),[[True,False,False,False,False]])
    def test_boolean_QA_frame_count_rejected(self):self.qa['validated_frames']=True;self.reject('QA/candidate')
    def test_floating_indexed_dimensions_rejected(self):self.bank[0]['source']['width']=72.0;self.reject('indexed canvas')
    def test_floating_literal_dimensions_rejected(self):self.candidate['sequences'][0]['frames'][0]['logical_width']=72.0;self.reject('canvas/crop')
    def test_unsafe_literal_artwork_filename_rejected(self):
        for f in self.candidate['sequences'][0]['frames']:f['file']='../raw.png'
        # Bind the synthetic QA's raw name equally so its hash gate closes first.
        self.write();v=json.loads((self.base/'qa.json').read_text());v['artwork_sha256']={'../raw.png':tool.sha((self.base/'raw.png').read_bytes())};(self.base/'qa.json').write_text(json.dumps(v));self.recipe['runtime_qa']=self.bind(self.base/'qa.json');inv=json.loads((self.base/'invocation.json').read_text());inv['runtime_QA_sha256']=self.recipe['runtime_qa']['sha256'];(self.base/'invocation.json').write_text(json.dumps(inv));self.recipe['actual_invocation']=self.bind(self.base/'invocation.json');self.path.write_text(json.dumps(self.recipe))
        with self.assertRaisesRegex(ValueError,'portable literal'):tool.run_recipe(self.path,self.output,self.project)
        self.assertFalse(self.output.exists())
    def test_phase_order_rejected(self):self.recipe['frames'].reverse();self.reject('ordered')
    def test_unknown_recipe_fields_rejected(self):self.recipe['hue_gain']=1.2;self.reject('exact fields')
    def test_wrong_candidate_scale_or_anchor_rejected(self):self.candidate['sequences'][0]['frames'][0]['origin']=[1,0];self.reject('canvas/crop')
    def test_later_frame_white_only_fails_before_any_output(self):
        x,y,w,h=self.crops[1];a=self.raw[y:y+h,x:x+w];a[a[:,:,3]>=128,:3]=255;self.save_raw();self.reject('insufficient')
    def test_shared_hull_material_change_rejected(self):
        self.sources[1][20,10]=216;(self.base/'200a0.bin').write_bytes(rle(self.sources[1]));self.bank[1]['source']['indices']=self.sources[1].ravel().tolist();self.reject('shared hull')
    def test_crop_aspect_rejected(self):self.recipe['frames'][0]['crop'][2]-=1;self.reject('canvas/crop')
    def test_crop_meaningful_pixel_clipping_rejected(self):
        self.raw[2,100]=[40,110,120,255];self.save_raw();self.reject('clips meaningful')
    def test_foreign_cell_alpha_rejected(self):
        self.crops[0][0]=38
        self.raw[500,766]=[40,90,100,255];self.save_raw();self.reject('includes foreign')
    def test_bank_source_tampering_rejected(self):self.bank[0]['source']['indices'][0]=5;self.reject('bank Source differs')
    def test_bank_reserved_labels_rejected(self):self.bank[1]['scales'][2]['indices'][0]=244;self.reject('reserved')
    def test_bank_boolean_index_rejected(self):self.bank[0]['scales'][0]['indices'][0]=False;self.reject('indexed canvas')
    def test_bank_scale_missing_rejected(self):self.bank[0]['scales'].pop();self.reject('native1')
    def test_wrong_QA_epoch_rejected(self):self.qa['library_sha256']='0'*64;self.reject('QA/candidate')
    def test_wrong_QA_raw_hash_rejected(self):
        self.write();v=json.loads((self.base/'qa.json').read_text());v['artwork_sha256']['raw.png']='0'*64;(self.base/'qa.json').write_text(json.dumps(v));self.recipe['runtime_qa']=self.bind(self.base/'qa.json');self.path.write_text(json.dumps(self.recipe))
        with self.assertRaisesRegex(ValueError,'QA/candidate'):tool.run_recipe(self.path,self.output,self.project)
        self.assertFalse(self.output.exists())
    def test_invocation_does_not_bind_bank_rejected(self):
        self.write();v=json.loads((self.base/'invocation.json').read_text());v['indexed_bank_sha256']='0'*64;(self.base/'invocation.json').write_text(json.dumps(v));self.recipe['actual_invocation']=self.bind(self.base/'invocation.json');self.path.write_text(json.dumps(self.recipe))
        with self.assertRaisesRegex(ValueError,'actual invocation'):tool.run_recipe(self.path,self.output,self.project)
        self.assertFalse(self.output.exists())
    def test_source_binding_hash_rejected(self):
        self.write();(self.base/'2009f.bin').write_bytes(b'wrong')
        with self.assertRaisesRegex(ValueError,'hash mismatch'):tool.run_recipe(self.path,self.output,self.project)
        self.assertFalse(self.output.exists())
    def test_relative_escape_binding_rejected(self):
        self.write();self.recipe['raw_png']['path']='../inputs/raw.png';self.path.write_text(json.dumps(self.recipe))
        with self.assertRaisesRegex(ValueError,'relative path'):tool.run_recipe(self.path,self.output,self.project)
        self.assertFalse(self.output.exists())
    def test_decoder_hash_rejected(self):
        (self.project/'tools/hd_frame_policy.py').write_text('raise AssertionError("unverified code executed")');self.reject('hash mismatch')
    def test_existing_output_not_overwritten(self):
        self.output.mkdir();keep=self.output/'keep';keep.write_text('old');self.write()
        with self.assertRaisesRegex(ValueError,'fresh'):tool.run_recipe(self.path,self.output,self.project)
        self.assertEqual(keep.read_text(),'old')
    def test_symlink_input_and_output_rejected(self):
        self.write();raw=self.base/'raw.png';old=self.base/'old.png';raw.rename(old);raw.symlink_to(old)
        with self.assertRaisesRegex(ValueError,'symlink'):tool.run_recipe(self.path,self.output,self.project)
        self.assertFalse(self.output.exists())
        raw.unlink();old.rename(raw);self.output.symlink_to(self.root/'absent')
        with self.assertRaisesRegex(ValueError,'nonsymlink'):tool.run_recipe(self.path,self.output,self.project)
    def test_verified_decoder_buffer_used_after_path_replacement(self):
        self.write();original=tool.checked;mutated=[]
        def replace(binding,root):
            data=original(binding,root)
            if binding['path']=='tools/hd_frame_policy.py':
                (Path(root)/binding['path']).write_text('raise AssertionError("reopened dependency")');mutated.append(True)
            return data
        with patch.object(tool,'checked',side_effect=replace):receipt=tool.run_recipe(self.path,self.output,self.project)
        self.assertEqual(receipt['execution']['status'],'success');self.assertEqual(mutated,[True])
    def test_verified_raw_buffer_used_after_path_replacement(self):
        self.write();original=tool.checked;mutated=[]
        def replace(binding,root):
            data=original(binding,root)
            if binding['path']=='raw.png':
                (Path(root)/binding['path']).write_bytes(b'not reopened');mutated.append(True)
            return data
        with patch.object(tool,'checked',side_effect=replace):receipt=tool.run_recipe(self.path,self.output,self.project)
        self.assertEqual(receipt['execution']['status'],'success');self.assertEqual(mutated,[True])
    def test_wrong_png_layout_rejected(self):
        Image.new('RGBA',(10,10)).save(self.base/'raw.png');self.reject('RGBA raw atlas')
    def test_aggregate_missing_cap_cannot_pass_per_frame_caps(self):
        for x,y,w,h in self.crops:
            region=self.raw[y:y+h,x:x+w];yy,xx=np.indices((h,w));visible=region[:,:,3]>=128;region[visible & (xx%8!=0),:3]=255
        self.save_raw();self.reject('aggregate')
    def test_non_cascading_distance_bound_on_new_far_wake(self):
        s=self.sources[0].copy();s[1,71]=150;caps=tool.source_caps([s,self.sources[1]],self.palette);baseline=np.array(self.bank[0]['scales'][3]['indices']).reshape(160,288)
        with self.assertRaisesRegex(ValueError,'bounded same-phase|donor distance'):tool.render_frame(s,self.palette,self.raw,self.crops[0],baseline,caps)


class DescriptorTests(unittest.TestCase):
    def test_static_FIFO_does_not_block_in_real_subprocess(self):
        if not hasattr(os,'mkfifo'):self.skipTest('FIFO unavailable')
        with tempfile.TemporaryDirectory() as d:
            fifo=Path(d)/'fifo';os.mkfifo(fifo)
            code='import importlib.util,sys; s=importlib.util.spec_from_file_location("u",sys.argv[1]);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);m.regular_bytes(sys.argv[2])'
            z=subprocess.run([sys.executable,'-c',code,str(HERE/'hd_ship09_wake_cleanup.py'),str(fifo)],capture_output=True,timeout=3)
            self.assertNotEqual(z.returncode,0);self.assertIn(b'bounded regular input',z.stderr)
    def test_regular_file_swapped_to_FIFO_between_lstat_and_open(self):
        if not hasattr(os,'mkfifo'):self.skipTest('FIFO unavailable')
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'input';p.write_bytes(b'old');original=os.open
            def swap(path,flags,*a,**kw):
                if Path(path)==p:p.unlink();os.mkfifo(p)
                return original(path,flags,*a,**kw)
            with patch.object(tool.os,'open',side_effect=swap):
                with self.assertRaisesRegex(ValueError,'bounded regular'):tool.regular_bytes(p)
    def test_bound_rejects_large_regular_input_before_read(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'large';p.write_bytes(b'x'*65)
            with patch.object(tool,'MAX_BYTES',64):
                with self.assertRaisesRegex(ValueError,'bounded regular'):tool.regular_bytes(p)


if __name__ == '__main__':unittest.main()
