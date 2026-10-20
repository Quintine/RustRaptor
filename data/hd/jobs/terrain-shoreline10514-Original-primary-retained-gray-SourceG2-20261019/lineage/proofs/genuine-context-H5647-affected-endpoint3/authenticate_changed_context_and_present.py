from pathlib import Path
import json,gzip,hashlib,io
import numpy as np
from PIL import Image,ImageDraw
O=Path(__file__).resolve().parent;R=O.parents[1];Old=R/'.reference/hd-shoreline4-currentG2-H5636-genuine-context-author-20261019-v1';D=O/'actual-affected-endpoint3-context';OD=Old/'actual-context18';V=O/'changed-review-pages';V.mkdir()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def js(p):return json.loads(Path(p).read_text())
P=js(D/'ACTUAL-SHORELINE4-G2-H5647-CHANGED-ENDPOINT3-ALL4-12-ROLE-BODIES.json');prev=js(OD/'ACTUAL-SHORELINE4-G2-H5636-GENUINE18-ALL4-216-ROLE-BODIES.json');pal=np.frombuffer((D/'actual-palette-rgb.bin').read_bytes(),np.uint8).reshape(256,3);assert (D/'actual-palette-rgb.bin').read_bytes()==(OD/'actual-palette-rgb.bin').read_bytes();oldrows={(r['endpoint_index'],r['scale']):r for r in prev['records']};classes=lambda a:np.where((a>=240)&(a<=244),1,np.where((a>=245)&(a<=249),2,np.where(a>=250,a,0))).astype(np.uint8)
def arr(root,folder,x):
 a=np.frombuffer(gzip.decompress((root/folder/x['indexed']).read_bytes()),'<u2').reshape(x['height'],x['width']);assert(a<256).all();assert gzip.decompress((root/folder/x['classes']).read_bytes())==classes(a).tobytes();assert np.array_equal(np.array(Image.open(io.BytesIO(gzip.decompress((root/folder/x['PPM']).read_bytes())))),pal[a]);return a
components={}
for c in P['components']:components[c['asset'],c['scale']]=arr(D,'components',c)
assert len(components)==36;rows={};deltas=[];retained=0
for r in P['records']:
 s=r['scale'];assert r['endpoint_index']==3;planes={k:arr(D,'planes',v)for k,v in r['planes'].items()};ori=planes['Original_joined_SourceNx'];current=planes['immutable_H5647_current'];prop=planes['shoreline4_proposed'];old=oldrows[3,s];oldori=arr(OD,'planes',old['planes']['Original_joined_SourceNx']);assert np.array_equal(ori,oldori);assert np.array_equal(classes(ori),classes(current))and np.array_equal(classes(ori),classes(prop));support=np.zeros(ori.shape,bool)
 for l,t,rr,b in r['support_rectangles']:support[t*s:b*s,l*s:rr*s]=True
 assert not((current!=prop)&~support).any()
 for role,info in [('immutable_H5647_current',r['baseline_inputs']),('shoreline4_proposed',r['proposal_inputs'])]:
  for layer in info['pre_blit']:
   x,y=layer['position'];a=planes[role][y*s:(y+32)*s,x*s:(x+32)*s];control=ori[y*s:(y+32)*s,x*s:(x+32)*s]
   for cx,cy in layer['retained_cells']or[]:assert np.array_equal(a[cy*s:(cy+1)*s,cx*s:(cx+1)*s],control[cy*s:(cy+1)*s,cx*s:(cx+1)*s]);retained+=s*s
   if layer['palette_domain']:assert set(map(int,a.ravel()))<=set(layer['palette_domain'])
 deltas.append(dict(scale=s,Original_exact_previous=True,new_current_changed_samples=int(np.count_nonzero(current!=arr(OD,'planes',old['planes']['immutable_H5636_current']))),new_proposed_changed_samples=int(np.count_nonzero(prop!=arr(OD,'planes',old['planes']['shoreline4_proposed'])))));rows[s]=planes
roles=['Original_joined_SourceNx','immutable_H5647_current','shoreline4_proposed'];page=Image.new('RGB',(1192,1150),(20,22,27));d=ImageDraw.Draw(page);d.text((8,6),'Endpoint03 S1W5 r24c2, actual H5647 rerender with newly active103d6 slot3',fill='white');d.text((8,24),'Original / H5647 current / shoreline4 proposed; all4 native, no resizing',fill='white');y=48
for s in range(1,5):
 d.text((8,y),f'native{s}; whole{96*s}x{96*s}',fill='white');y+=16
 for i,k in enumerate(roles):page.paste(Image.fromarray(pal[rows[s][k]]),(8+i*396,y))
 y+=96*s+12
out=V/'endpoint03-H5647-whole-Original-current-proposed-all-native.png';page.save(out)
# Pair1 BEFORE is newly rendered; settled endpoint15 consumes no103d6 and is input-carried exactly.
pair=Image.new('RGB',(1192,864),(20,22,27));d=ImageDraw.Draw(pair);d.text((8,6),'Ordered event1 S1W5 r24c1:103d6→1050b ; H5647 Source/current/proposed',fill='white');d.text((8,24),'Before endpoint3 newly rendered; settled endpoint15 exact-input carried unchanged from H5636.',fill='white')
for half,ep in enumerate([3,15]):
 y=48+half*408;d.text((8,y),'new BEFORE endpoint3'if ep==3 else'carried legal SETTLED endpoint15',fill='white');y+=16
 if ep==3:aa=[rows[4][k]for k in roles]
 else:aa=[arr(OD,'planes',oldrows[15,4]['planes'][k])for k in ['Original_joined_SourceNx','immutable_H5636_current','shoreline4_proposed']]
 for i,a in enumerate(aa):pair.paste(Image.fromarray(pal[a]),(8+i*396,y))
pout=V/'pair1-H5647-ordered-new-before-carried-settled-native4.png';pair.save(pout)
report=dict(status='FILE_ONLY_CHANGED_ENDPOINT3_ALL4_12_ROLES_AND_PAIR1_AUTHENTICATED_PHYSICAL_REVIEW_PENDING',new_proof_sha256=sha(D/'ACTUAL-SHORELINE4-G2-H5647-CHANGED-ENDPOINT3-ALL4-12-ROLE-BODIES.json'),Source4_exact_historical=True,actual_new_103d6_dependency_deltas=deltas,all_palette_cycling_classes_exact=True,retained_Original_whole_control_samples_verified=retained,components36_authenticated=True,unaffected17_not_rerendered=True,endpoint15_settled1050b_true_Original_fallback=True,changed_pages=[dict(path=str(p.relative_to(O)),sha256=sha(p))for p in [out,pout]],new_World_QA_or_compositor_calls=0,script_sha256=sha(__file__))
(O/'FILE-ONLY-H5647-CHANGED-ENDPOINT3-ARRAY-AND-PAGE-AUDIT.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
