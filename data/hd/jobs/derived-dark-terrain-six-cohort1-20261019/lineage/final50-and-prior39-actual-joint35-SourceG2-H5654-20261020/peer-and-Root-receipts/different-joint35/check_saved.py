from pathlib import Path
import hashlib,json,gzip,struct,ast
import numpy as np
from PIL import Image
O=Path(__file__).resolve().parent;R=O.parents[1];P=R/'.reference/hd-all89-joint35-SourceG2-H5654-context-author-20261020-v1';ip=P/'FROZEN-ALL89-GENUINE35-ALLNATIVE-CONTEXT-PEER-INTERFACE.json'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def js(p):return json.loads(Path(p).read_text())
def pin(p):p=Path(p);return dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size)
I=js(ip);X=js(I['actual_proof']['path']);r=js(I['actual_recipe']['path']);B=js(I['finite_bindings']['path']);assert r==X['recipe'] and not X['diagnostics'] and X['World_calls']==X['new_intrinsic_QA_calls']==0;Q=Path(I['actual_proof']['path']).parent
refs={}
def walk(v):
 if isinstance(v,dict):
  if 'path'in v and 'sha256'in v:
   p=Path(v['path']);assert sha(p)==v['sha256'];refs[str(p)]=pin(p)
  for x in v.values():walk(x)
 elif isinstance(v,list):
  for x in v:walk(x)
walk(I);walk(r);walk(B)
k=R/'.reference/hd-shoreline4-independent-intrinsic-ART-review-20261019-v1/check_saved_shoreline.py';f=next(x for x in ast.parse(k.read_text()).body if isinstance(x,ast.FunctionDef)and x.name=='nx');ns={'np':np};exec(compile(ast.Module(body=[f],type_ignores=[]),str(k),'exec'),ns);nx=ns['nx']
cat={};names={}
for l in (R/'data/INDEX').read_text().splitlines():a,n,f=l.split();cat[f'{int(a,16):05x}']=R/'data'/f;names[Path(f).name]=int(a,16)
source={}
for aid,b in B['bindings'].items():
 raw=Path(b['source']['path']).read_bytes();assert raw==cat[aid].read_bytes() and struct.unpack_from('<5i',raw)==(1,1,0,32,32);source[aid]=np.frombuffer(raw[20:],np.uint8).reshape(32,32).astype('u2')
for c in r['cases']:
 for d in c['authentic_original_definitions']:
  if d is None:continue
  fi,g=struct.unpack_from('<hh',cat[d['MAP_asset']].read_bytes(),d['MAP_byte_offset']);delta,h,re=struct.unpack_from('<ihh',cat[d['FLATS_asset']].read_bytes(),d['FLATS_byte_offset']);start=names[f'STARTG{g+1}TILES']+1;a=start+fi;dead=start+delta
  assert fi==d['flat'] and g==d['game'] and d['MAP_byte_offset']==12+4*(d['row']*9+d['column']) and d['FLATS_byte_offset']==fi*8 and f'{a:05x}'==d['intact'] and d['settled']==(None if a==dead else f'{dead:05x}') and h==d['raw_health'] and re==d['raw_reward']
 ids=[v['intact']if v else None for v in c['authentic_original_definitions']]
 for d in c['settled_changes']:
  slot=(d['row']-c['window_row0'])*c['width_tiles']+d['column']-c['window_column0'];assert c['authentic_original_definitions'][slot]==d and d['health']>0;ids[slot]=d['settled']
 assert ids==c['ordered_source_ids']
pal=np.frombuffer((Q/'actual-palette-rgb.bin').read_bytes(),np.uint8).reshape(256,3);vga=np.frombuffer((R/'data/misc/PALETTE_DAT').read_bytes(),np.uint8).astype('u2');assert np.array_equal(pal,((np.minimum(vga,63)<<2)|(np.minimum(vga,63)>>4)).astype('u1').reshape(256,3))
classes=lambda a:np.where(a<240,0,np.where(a<245,1,np.where(a<250,2,a))).astype('u1');samples=0;filepins={}
def body(d,folder):
 global samples
 a=np.frombuffer(gzip.decompress((folder/d['indexed']).read_bytes()),'<u2').reshape(d['height'],d['width']);assert a.max()<256 and gzip.decompress((folder/d['classes']).read_bytes())==classes(a).tobytes();assert gzip.decompress((folder/d['PPM']).read_bytes())==f'P6\n{a.shape[1]} {a.shape[0]}\n255\n'.encode()+pal[a].tobytes();samples+=a.size
 for key in ['indexed','classes','PPM']:filepins[str(folder/d[key])]=pin(folder/d[key])
 return a
for z in X['components']:
 a=body(z,Q/'components');assert a.shape==(32*z['scale'],32*z['scale']) and z['full_native_frame']==B['bindings'][z['asset']]['native']['frame']
arrays={};ret=outside=stable=delta=0;changes=[]
for rec in X['records']:
 ci=rec['case_index'];s=rec['scale'];c=r['cases'][ci];w=c['width_tiles'];ids=c['ordered_source_ids'];logical=np.block([[source[ids[y*w+x]] if ids[y*w+x] else np.zeros((32,32),np.uint16)for x in range(w)]for y in range(c['height_tiles'])]);original=nx(logical,s);arr={role:body(d,Q/'planes')for role,d in rec['planes'].items()};roles=I['roles'];assert np.array_equal(arr[roles[0]],original)
 for role,a in arr.items():assert np.array_equal(classes(a),classes(original)) and np.array_equal(a[original>=250],original[original>=250]);arrays[ci,s,role]=a
 old=arr[roles[2]];joint=arr[roles[3]];mask=np.zeros(original.shape,bool)
 for x0,y0,x1,y1 in rec['added_new_foreign_support_rectangles']:mask[y0*s:y1*s,x0*s:x1*s]=True
 assert np.array_equal(old[~mask],joint[~mask]);outside+=int((~mask).sum());dc=int(np.count_nonzero(old!=joint));assert dc==rec['changed_old_cohort_to_joint_samples'];delta+=dc;st=0
 for t,aid in enumerate(ids):
  y=t//w*32*s;x=t%w*32*s
  if aid in set(B['old5654_foreign'])|set(c['cohort_selected']):assert np.array_equal(old[y+2*s:y+30*s,x+2*s:x+30*s],joint[y+2*s:y+30*s,x+2*s:x+30*s]);st+=784*s*s
  if aid is None:assert all(np.array_equal(a[y:y+32*s,x:x+32*s],original[y:y+32*s,x:x+32*s])for a in arr.values())
 stable+=st;assert st==rec['stable_old_contributor_broad_interiors_exact']
 for pre in rec['joint89_inputs']['pre_blit']:
  t=pre['slot'];assert pre['asset']==ids[t]
  for cx,cy in pre['retained_cells']or[]:
   y=(t//w*32+cy)*s;x=(t%w*32+cx)*s;assert np.array_equal(joint[y:y+s,x:x+s],original[y:y+s,x:x+s]);ret+=s*s
 for st in rec['new_contributor_slot_checks']:
  t=st['slot'];y=t//w*32*s;x=t%w*32*s;v=int(np.count_nonzero(joint[y:y+32*s,x:x+32*s]!=old[y:y+32*s,x:x+32*s]));assert v==st['final_samples_different_from_old_cohort_only']
 changes.append(dict(case=ci,scale=s,changed=dc))
for page in I['whole_endpoint_pages']:
 im=np.asarray(Image.open(page['page']['path']).convert('RGB'));assert [im.shape[1],im.shape[0]]==page['dimensions']
 for z in page['panes']:
  x,y,w,h=z['xywh'];f=z['nearest_display_factor'];rgb=np.repeat(np.repeat(pal[arrays[z['case_index'],z['scale'],z['role']]],f,0),f,1);assert rgb.shape==(h,w,3) and x+w<=im.shape[1] and y+h<=im.shape[0] and np.array_equal(im[y:y+h,x:x+w],rgb)
assert (samples,ret,outside,stable,delta)==(60057600,13890,12300960,9455040,920297)
for p,v in refs.items():assert sha(p)==v['sha256']
out=dict(status='PASS_DIFFERENT_SAVED_JOINT35_PLANES_SOURCE_MAP_FLATS_RETENTION_SUPPORT_AND_ALL560_BODIES',interface=pin(ip),actual_epoch=I['actual_epoch'],actual_proof=I['actual_proof'],author_technical_authentication=I['authentication'],independently_checked=dict(component_bodies=444,context_bodies=560,index_class_RGB_samples=samples,joined_SourceNx_controls=140,postjoin_retained_samples=ret,outside_added_support_samples_exact=outside,stable_old_interiors_exact=stable,old_to_joint_changes=delta,all35_literal_MAP_FLATS_windows_and_settled_states_exact=True,all52_saved_pages_all560_body_rectangles_complete=True),record_changes=changes,producer_reference_files_unchanged=len(refs),raw_plane_files=list(filepins.values()),new_runtime_calls=0,checker=pin(__file__))
p=O/'PASS-DIFFERENT-JOINT35-SAVED-NATIVE-SOURCE-AND-SUPPORT-CHECKS.json';p.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(pin(p)))
