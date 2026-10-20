"""Independent file-only audit. Does not render, compile, derive or edit producer inputs."""
from pathlib import Path
import json,hashlib,struct,gzip,ast,io
import numpy as np
from PIL import Image
R=Path('/home/quintine/Projects/RaptorReplica/RustRaptor');O=Path(__file__).parent
P=R/'.reference/hd-night5-SourceG2-H5654-genuine-context-author-20261019-v1';A=P/'actual-once-night5-genuine10-G2-H5654'
def js(p):return json.loads(Path(p).read_text())
def pin(p):
 p=Path(p);s=p.stat();return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),size=s.st_size,mtime_ns=s.st_mtime_ns,mode=s.st_mode)
def checkpin(p):assert pin(p['path'])==p,p['path']
def cls(a):return np.where(a<240,0,np.where(a<245,1,np.where(a<250,2,a))).astype('u1')
# Import only the pure published Scale2/3/4 reference function, never its original top-level producer.
f=R/'.reference/hd-terrain1-20273-20275-currentC-5384-bounded-context-production-20261017/authenticate_and_make_lossless_pages.py';tree=ast.parse(f.read_text());node=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='upscale');exec(compile(ast.Module(body=[node],type_ignores=[]),str(f),'exec'))
recipe=js(P/'SEALED-NIGHT5-GENUINE10-CURRENTG2-H5654-RECIPE.json');actual=js(A/'ACTUAL-NIGHT5-GENUINE10-SOURCEG2-H5654-CONTEXTS.json');face=js(P/'FROZEN-NIGHT5-GENUINE10-ALLNATIVE-SOURCEG2-H5654-CONTEXT-PEER-INTERFACE.json');bindings=js(P/'FINITE-H5654-NIGHT5-CONSUMED-SOURCE-NATIVE-RAW-BINDINGS.json')
assert len(actual['records'])==40 and actual['World_calls']==0 and actual['diagnostics']==[]
# Preserve every actual producer file, while excluding our independent output namespace.
before={str(p):pin(p) for p in P.rglob('*') if p.is_file() and 'literal-H5654-full-raw-route-baseline' not in p.parts}
source={};inputpins=[]
for k,v in bindings['bindings'].items():
 checkpin(v['source']);inputpins.append(v['source']);b=Path(v['source']['path']).read_bytes();assert struct.unpack('<5i',b[:20])==(1,1,0,32,32);assert len(b)==1044;source[k]=np.frombuffer(b[20:],dtype='u1').reshape(32,32).astype('<u2')
 if v['native']:checkpin(v['native']['raw']);inputpins.append(v['native']['raw'])
palraw=np.frombuffer((R/'data/misc/PALETTE_DAT').read_bytes(),dtype='u1').astype('u2');assert palraw.size==768 and palraw.max()<=63;palette=((palraw<<2)|(palraw>>4)).astype('u1').reshape(256,3);assert palette.tobytes()==(A/'actual-palette-rgb.bin').read_bytes()
count=0
def load(d,sub):
 global count
 shape=(d['height'],d['width']);a=np.frombuffer(gzip.decompress((A/sub/d['indexed']).read_bytes()),dtype='<u2').reshape(shape);assert a.max()<256;c=np.frombuffer(gzip.decompress((A/sub/d['classes']).read_bytes()),dtype='u1').reshape(shape);assert np.array_equal(c,cls(a));rgb=np.asarray(Image.open(io.BytesIO(gzip.decompress((A/sub/d['PPM']).read_bytes()))).convert('RGB'));assert np.array_equal(rgb,palette[a]);count+=a.size*5;return a
components={};detail={}
for d in actual['components']:
 a=load(d,'components');s=d['scale'];assert np.array_equal(cls(a),cls(np.repeat(np.repeat(source[d['asset']],s,0),s,1)));components[d['asset'],s]=a;detail[d['asset']]=d['retained_cells'] or []
accepted={}
for p in recipe['accepted_own_banks'].values():
 checkpin(p)
 for d in js(p['path']):
  for sc in d['scales']:accepted[d['asset'],sc['scale']]=np.array(sc['indices'],dtype='<u2').reshape(sc['height'],sc['width'])
for (asset,scale),arr in components.items():
 if asset not in recipe['selected5']:continue
 restored=arr.copy();ori=upscale(source[asset],scale)
 for x,y in detail[asset]:restored[y*scale:(y+1)*scale,x*scale:(x+1)*scale]=ori[y*scale:(y+1)*scale,x*scale:(x+1)*scale]
 assert np.array_equal(restored,accepted[asset,scale]),(asset,scale)
# Literal original grids, authentic legal actor replacements, no synthetic caller invention.
original={}
for case in recipe['cases']:
 assert case['mission']=='base:sector_2_wave_8';w=case['width_tiles'];h=case['height_tiles'];grid=np.empty((h*32,w*32),dtype='<u2');changes={(d['row'],d['column']):d for d in case['settled_changes']}
 for t,(k,d) in enumerate(zip(case['ordered_source_ids'],case['authentic_original_definitions'])):
  assert d['row']==case['window_row0']+t//w and d['column']==case['window_column0']+t%w
  expected=d['settled'] if (d['row'],d['column']) in changes else d['intact'];assert k==expected
  grid[t//w*32:(t//w+1)*32,t%w*32:(t%w+1)*32]=source[k]
 original[case['case_index']]=grid
for event in recipe['ordered_views']:
 x=recipe['cases'][event['before']]['ordered_source_ids'];y=recipe['cases'][event['settled']]['ordered_source_ids'];different=[i for i,(a,b) in enumerate(zip(x,y)) if a!=b];assert different==[event['changed_slot']];d=event['Original_actor'];assert x[different[0]]==d['intact'] and y[different[0]]==d['settled'] and d['health']>0
# Independently decode all27 MAP layouts and all4 FLATS libraries, then check literal per-cell semantics.
census=js(P/'FRESH-ALL27MAP-4FLATS-23NIGHT5-CALLERS-SOURCE-ONLY.json')
for q in census['inputs']:checkpin(q)
cat={};names={}
for line in (R/'data/INDEX').read_text().splitlines():
 a,n,p=line.split();cat[int(a,16)]=(int(n),R/'data'/p);names[Path(p).name]=int(a,16)
flats={}
for game in range(4):
 body=cat[names[f'FLATSG{game+1}_ITM']][1].read_bytes();start=names[f'STARTG{game+1}TILES']+1;rows=[]
 for k in range(len(body)//8):
  destroyed,health,reward=struct.unpack_from('<ihh',body,k*8);rows.append(dict(intact=f'{start+k:05x}',settled=None if destroyed==k else f'{start+destroyed:05x}',health=0 if destroyed==k else health,raw_health=health,reward=max(0,reward),raw_reward=reward,flat=k,game=game))
 flats[game]=rows
maps={};caller_tuples=[];spawn_count=0
for sector in range(1,4):
 for wave in range(1,10):
  body=cat[names[f'MAP{wave}G{sector}_MAP']][1].read_bytes();length,off,n=struct.unpack_from('<iii',body);assert length==len(body) and off==5412 and 5412+n*24<=length;spawn_count+=n;rows=[]
  for k in range(1350):
   flat,game=struct.unpack_from('<hh',body,12+k*4);d=flats[game][flat];rows.append(d)
   for role in (['intact'] if d['intact'] in recipe['selected5'] else ['settled']):
    if d[role] in recipe['selected5']:caller_tuples.append((f'base:sector_{sector}_wave_{wave}',k//9,k%9,role,d['intact'],d['settled']))
  maps[f'base:sector_{sector}_wave_{wave}']=rows
expected_callers=[(d['mission'],d['row'],d['column'],d['Source_role'],d['intact'],d['settled']) for d in census['callers']];assert sorted(caller_tuples)==sorted(expected_callers);assert spawn_count==census['spawn_records']
for case in recipe['cases']:
 for d in case['authentic_original_definitions']:
  original_d=maps[case['mission']][d['row']*9+d['column']]
  for key,value in original_d.items():assert d[key]==value,(key,d,original_d)
  assert d['MAP_byte_offset']==12+4*(d['row']*9+d['column']) and d['FLATS_byte_offset']==8*d['flat']
own=set(recipe['selected5']);allhd={k for k,v in bindings['bindings'].items() if v['native']};totals=dict(outside=0,fallback=0,own_original=0,foreign_interior=0,delta=0,retained_proposal=0,final_global244_index_differences=0);saved={};checks=[]
for rec in actual['records']:
 ci=rec['case_index'];s=rec['scale'];case=recipe['cases'][ci];w=case['width_tiles'];h=case['height_tiles'];ids=case['ordered_source_ids'];arr={k:load(v,'planes') for k,v in rec['planes'].items()};ori=upscale(original[ci],s);assert np.array_equal(arr['Original_joined_SourceNx'],ori);base=arr['immutable_H5654_baseline'];new=arr['selected_night5_proposal']
 for a in arr.values():assert np.array_equal(cls(a),cls(ori));assert np.array_equal(a[ori>=250],ori[ori>=250])
 logical=np.zeros((h*32,w*32),dtype=bool)
 for t,k in enumerate(ids):
  if k not in own:continue
  tx=t%w;ty=t//w;logical[ty*32:(ty+1)*32,tx*32:(tx+1)*32]=True
  for dx,dy in [(-1,0),(1,0),(0,-1),(0,1)]:
   x=tx+dx;y=ty+dy
   if not(0<=x<w and 0<=y<h) or ids[y*w+x] not in allhd or ids[y*w+x] in own:continue
   xx=x*32;yy=y*32;x0,y0,x1,y1={(-1,0):(xx+30,yy+2,xx+32,yy+30),(1,0):(xx,yy+2,xx+2,yy+30),(0,-1):(xx+2,yy+30,xx+30,yy+32),(0,1):(xx+2,yy,xx+30,yy+2)}[dx,dy];logical[y0:y1,x0:x1]=True
  for vy in [ty,ty+1]:
   for vx in [tx,tx+1]:
    slots=[(vx-1,vy-1),(vx,vy-1),(vx-1,vy),(vx,vy)]
    if not all(0<=x<w and 0<=y<h and ids[y*w+x] in allhd for x,y in slots):continue
    for x,y in slots:
     if ids[y*w+x] in own:continue
     xx=x*32+(0 if x==vx else 30);yy=y*32+(0 if y==vy else 30);logical[yy:yy+2,xx:xx+2]=True
 allowed=np.repeat(np.repeat(logical,s,0),s,1);reported=np.zeros(ori.shape,dtype=bool)
 for x0,y0,x1,y1 in rec['support_rectangles']:reported[y0*s:y1*s,x0*s:x1*s]=True
 assert np.array_equal(allowed,reported);assert np.array_equal(base[~allowed],new[~allowed]);outside=int((~allowed).sum());fallback=interior=ownorig=retained=0
 for t,k in enumerate(ids):
  y=t//w*32*s;x=t%w*32*s;sl=np.s_[y:y+32*s,x:x+32*s]
  if k not in allhd:assert np.array_equal(base[sl],ori[sl]) and np.array_equal(new[sl],ori[sl]);fallback+=1024*s*s
  if k in own:assert np.array_equal(base[sl],ori[sl]);ownorig+=1024*s*s
  elif k in allhd:
   ins=np.s_[y+2*s:y+30*s,x+2*s:x+30*s];assert np.array_equal(base[ins],new[ins]);interior+=784*s*s
  for xx,yy in detail.get(k,[]):
   dsl=np.s_[y+yy*s:y+(yy+1)*s,x+xx*s:x+(xx+1)*s];assert np.array_equal(new[dsl],ori[dsl]);retained+=s*s
 delta=int(np.count_nonzero(base!=new));g244=int(np.count_nonzero((new==244)!=(ori==244)));assert g244==0
 for key,val in [('outside',outside),('fallback',fallback),('own_original',ownorig),('foreign_interior',interior),('delta',delta),('retained_proposal',retained),('final_global244_index_differences',g244)]:totals[key]+=val
 for key,val in [('outside_support_samples_exact',outside),('foreign_Original_fallback_samples_exact',fallback),('baseline_own_Original_samples_exact',ownorig),('broad_foreign_interior_samples_exact',interior),('changed_samples',delta)]:assert rec[key]==val,(ci,s,key)
 saved[ci,s]=arr;checks.append(dict(case_index=ci,scale=s,SourceNx_control_exact=True,Source_classes_exact=True,outside_support_exact=outside,retained_SourceNx_exact=retained,delta_samples=delta))
# Every original native role PNG and every pane in every public saved triptych must match indexed RGB.
for d in face.get('individual_whole_role_images',[]):
 checkpin(d['file']);rgb=np.asarray(Image.open(d['file']['path']).convert('RGB'));assert np.array_equal(rgb,palette[saved[d['case_index'],d['scale']][d['role']]])
for d in face['whole_endpoint_pages']+face['ordered_event_pages']:
 checkpin(d['page']);rgb=np.asarray(Image.open(d['page']['path']).convert('RGB'))
 for pane in d['panes']:
  x,y,w,h=pane['xywh'];factor=pane['nearest_display_factor'];expected=palette[saved[pane['case_index'],pane['scale']][pane['role']]];expected=np.repeat(np.repeat(expected,factor,0),factor,1);assert np.array_equal(rgb[y:y+h,x:x+w],expected)
for p,old in before.items():assert pin(p)==old,p
report=dict(status='PASS_DIFFERENT_FILE_ONLY_SAVED_NIGHT5_GENUINE10_CONTEXT_AUTHENTICATION',reviewer='/root/grating_pair',producer_epoch=face['actual_pixel_epoch'],no_renderer_QA_compile_art_actions=True,Source_PICs=len(source),independent_MAPs=27,independent_FLATS=4,independent_caller_roles=len(caller_tuples),components=len(components),records=len(checks),whole_native_role_bodies=120,whole_native_page_bodies=168,ordered_legal_events=len(recipe['ordered_views']),index_class_RGB_samples=count,totals=totals,checks=checks,inputpins=inputpins,producer_files_exact_before_after=len(before),proof=pin(A/'ACTUAL-NIGHT5-GENUINE10-SOURCEG2-H5654-CONTEXTS.json'),recipe=pin(P/'SEALED-NIGHT5-GENUINE10-CURRENTG2-H5654-RECIPE.json'),limits=['Static MAP/FLATS legal endpoints, World0; no natural damage timing or gameplay-replay claim','Finite H5654 snapshot only; no fresh current-header/capture claim','Source retention is functional/fidelity ownership, zero generated-HD credit'])
out=O/'PASS-INDEPENDENT-NIGHT5-GENUINE10-ALL40-NATIVE-120ROLE-168BODY-ARRAY-AUDIT.json';out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(report=pin(out),totals=totals,samples=count,producer_pins=len(before)),indent=2))
