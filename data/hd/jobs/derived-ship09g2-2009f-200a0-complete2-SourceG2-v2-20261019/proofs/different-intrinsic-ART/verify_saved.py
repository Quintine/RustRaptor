import hashlib,importlib.util,json
from pathlib import Path
import numpy as np
from PIL import Image
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent
S=R/'.reference/hd-SHIP09G2-actual-all-cyan-derived2-currentG2-author-20261019-v2'
C=R/'.reference/hd-SHIP09G2-all-Source-cyan-ownership-code-successor-20261019-v2'
H=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
seal=S/'FROZEN-COMPLETE2-ALL-CYAN-AUTHOR-QUAL-PEER-INPUTS.json';frozen=json.loads(seal.read_text())
for name,meta in frozen['files'].items():
    p=S/name;assert H(p)==meta['sha256'] and p.stat().st_size==meta['bytes'],name
sp=importlib.util.spec_from_file_location('approved_partition_math',C/'hd_ship09_wake_cleanup.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
recipe=json.loads((C/'PROPOSED-EXACT-PORTABLE-ALL-CYAN-RECIPE-NOT-EXECUTED.json').read_text());bank=json.loads((S/'actual-currentG2-intrinsic2/actual-indexed-source-and-scales.json').read_text());old=json.loads((C/'inputs/literal-currentG2-indexed-bank.json').read_text())
pb=(C/'inputs/PALETTE_DAT').read_bytes();p6=np.frombuffer(pb,np.uint8).reshape(256,3).astype(np.uint16);pal=((p6<<2)|(p6>>4)).astype(np.uint8);lut=np.zeros((257,4),np.uint8);lut[:256,:3]=pal;lut[:256,3]=255
sources=[np.asarray(row['source']['indices'],np.uint16).reshape(40,72) for row in bank];caps=m.source_caps(sources,pal)
raw=np.asarray(Image.open(C/'inputs/raw.png'));facts=[]
execution=json.loads((S/'derived2/execution-receipt.json').read_text());qa=json.loads((S/'actual-currentG2-intrinsic2/runtime-qa.json').read_text());inv=json.loads((S/'actual-currentG2-intrinsic2/ACTUAL-CURRENT-SOURCEG2-INVOCATION.json').read_text())
assert inv['exit_code']==0 and inv['runtime_QA_sha256']==H(S/'actual-currentG2-intrinsic2/runtime-qa.json') and inv['indexed_bank_sha256']==H(S/'actual-currentG2-intrinsic2/actual-indexed-source-and-scales.json')
assert qa['diagnostics']==[] and qa['validated_frames']==2 and qa['candidate_sha256']==H(S/'candidate.json')
for i,a in enumerate(m.ASSETS):
    s=sources[i];s4=m.scale2(m.scale2(s));cyan=(s4>=144)&(s4<=159);non=(s4<256)&~cyan;gray=s4<32;clear=s4==256
    baseline=np.asarray(old[i]['scales'][3]['indices'],np.uint16).reshape(160,288);rgba=np.asarray(Image.open(S/'derived2'/(a+'.png')))
    assert np.array_equal(rgba[non],lut[baseline][non]) and np.array_equal(rgba[gray],lut[baseline][gray]);assert np.all(rgba[cyan,3]==255) and np.all(rgba[clear]==0)
    assert np.all(m.cyan_donors(rgba[:,:,:3],caps)[cyan])
    x,y,w,h=recipe['frames'][i]['crop'];reg=raw[y:y+h,x:x+w];eligible=(reg[:,:,3]>=128)&m.cyan_donors(reg[:,:,:3],caps);donors=set(map(tuple,reg[:,:,:3][eligible]));assert all(tuple(z) in donors for z in rgba[:,:,:3][cyan])
    assert H(S/'derived2'/(a+'.png'))==execution['execution']['output_sha256'][a]
    assert hashlib.sha256(rgba.tobytes()).hexdigest()==execution['reports'][i]['RGBA_sha256']
    assert np.array_equal(np.asarray(bank[i]['source']['indices']).reshape(40,72),np.asarray(old[i]['source']['indices']).reshape(40,72))
    scale_facts=[]
    for k,row in enumerate(bank[i]['scales'],1):
        idx=np.asarray(row['indices'],np.uint16).reshape(k*40,k*72);ppm=np.asarray(Image.open(S/'actual-currentG2-intrinsic2'/f'{a}-hd-{k}.ppm'))
        expected=lut[idx][:,:,:3].copy()
        bg=ppm[0,0];expected[idx==256]=bg
        assert np.array_equal(ppm,expected),(a,k)
        if k==4:
            # Cyan raw RGB is newly quantized by real G2; only structural
            # palette RGBA and complete alpha are claimed byte-identical.
            assert np.array_equal(lut[idx][non],rgba[non])
            assert np.array_equal(lut[idx][:,:,3],rgba[:,:,3])
            assert np.all(np.max(lut[idx][:,:,:3][cyan],axis=1)<240)
        assert not ((idx>=240)&(idx<256)).any()
        scale_facts.append(dict(scale=k,canvas=[k*72,k*40],PPM_exact_to_saved_bank=True,sha256=H(S/'actual-currentG2-intrinsic2'/f'{a}-hd-{k}.ppm')))
    native=np.asarray(bank[i]['scales'][0]['indices']).reshape(40,72);iou=np.count_nonzero((native<256)&(s<256))/np.count_nonzero((native<256)|(s<256))
    assert abs(iou-[.9932279909706546,.993202416918429][i])<1e-14
    r=execution['reports'][i];assert r['maximum_donor_logical_distance']<=5.5 and r['missing_fraction']<=.90
    facts.append(dict(asset=a,noncyan_RGBA_exact_samples=int(non.sum()),gray_RGBA_exact_samples=int(gray.sum()),cyan_genuine_eligible_same_phase_tuple_samples=int(cyan.sum()),transparent_clear_samples=int(clear.sum()),native1_mask_iou=iou,maximum_donor_logical_distance=r['maximum_donor_logical_distance'],missing_fraction=r['missing_fraction'],scales=scale_facts))
assert sum(r['repaired'] for r in execution['reports'])/sum(r['samples'] for r in execution['reports'])<=.85
output=dict(verified_producer_files=len(frozen['files']),frames=facts,source_and_canvas_alignment='72x40 both phases; bank Source arrays identical to approved initial bank; origin0 ordered candidate frames.',actual_new_cleanup_or_QA=0)
(O/'SAVED-ARRAYS-PINS-PARTITION-DONORS-PROOF.json').write_text(json.dumps(output,indent=2)+'\n')
print(json.dumps(output,indent=2))
