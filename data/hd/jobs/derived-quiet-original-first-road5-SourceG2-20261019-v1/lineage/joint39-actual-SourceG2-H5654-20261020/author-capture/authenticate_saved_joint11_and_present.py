from pathlib import Path
import json,hashlib,gzip,struct,ast,shutil
import numpy as np
from PIL import Image,ImageDraw
R=Path('/home/quintine/Projects/RaptorReplica/RustRaptor');P=Path(__file__).resolve().parent;Q=P/'actual-once-joint39-genuine11-STRICT-MANIFEST-V2-G2';proof=Q/'ACTUAL-JOINT39-GENUINE11-SOURCEG2-H5654-CONTEXTS.json';X=json.load(open(proof));r=X['recipe'];B=json.load(open(r['finite_bindings']['path']));own=set(r['selected']);foreign=set(B['old5654_foreign']);roles=['Original_global_SourceNx','H5654_only','H5654_plus_consumer_cohort','H5654_plus_all39_joint'];assert shutil.disk_usage(P).free>1932735284+60000000
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def pin(p):p=Path(p).resolve();s=p.stat();return {'path':str(p),'sha256':sha(p),'size':s.st_size,'mtime_ns':s.st_mtime_ns,'mode':s.st_mode}
def save(name,d):p=P/name;p.write_text(json.dumps(d,indent=2)+'\n');return pin(p)
refs={}
def walk(v):
 if isinstance(v,dict):
  if'path'in v and'sha256'in v:
   p=Path(v['path']);z=pin(p);assert z['sha256']==v['sha256'],p
   for k in ['size','mtime_ns','mode']:
    if k in v:assert z[k]==v[k],(p,k)
   refs[str(p)]=z
  for x in v.values():walk(x)
 elif isinstance(v,list):
  for x in v:walk(x)
walk(B);walk(r);source18=json.load(open(r['Source18_verification']['path']));walk(source18)
for path,h in source18['Source18'].items():assert sha(R/path)==h
assert X['diagnostics']==[]and X['World_calls']==X['new_intrinsic_QA_calls']==0;assert len(X['records'])==44 and len(X['components'])==160 and len(X['new_contributor_stages'])==28
k=R/'.reference/hd-independent-green7-H5567-genuine31-context-review-20261018-v1/authenticate_readonly.py';fn=next(x for x in ast.parse(k.read_text()).body if isinstance(x,ast.FunctionDef)and x.name=='upscale');ns={'np':np};exec(compile(ast.Module(body=[fn],type_ignores=[]),str(k),'exec'),ns);upscale=ns['upscale']
pal=np.frombuffer((Q/'actual-palette-rgb.bin').read_bytes(),dtype='u1').reshape(256,3);rawpal=np.frombuffer((R/'data/misc/PALETTE_DAT').read_bytes(),dtype='u1').astype('u2');assert np.array_equal(pal,((np.minimum(rawpal,63)<<2)|(np.minimum(rawpal,63)>>4)).astype('u1').reshape(256,3))
def classes(a):return np.where(a<240,0,np.where(a<245,1,np.where(a<250,2,a))).astype('u1')
sources={}
for aid,b in B['bindings'].items():
 raw=Path(b['source']['path']).read_bytes();assert struct.unpack('<5i',raw[:20])==(1,1,0,32,32);sources[aid]=np.frombuffer(raw[20:],dtype='u1').reshape(32,32).astype('u2')
rawpins=[];samples=0

def body(row,folder):
 global samples
 a=np.frombuffer(gzip.decompress((folder/row['indexed']).read_bytes()),dtype='<u2').reshape(row['height'],row['width']);assert a.max()<256;cl=np.frombuffer(gzip.decompress((folder/row['classes']).read_bytes()),dtype='u1').reshape(a.shape);assert np.array_equal(cl,classes(a));ppm=gzip.decompress((folder/row['PPM']).read_bytes());assert ppm==f'P6\n{a.shape[1]} {a.shape[0]}\n255\n'.encode()+pal[a].tobytes();samples+=a.size
 for n in ['indexed','classes','PPM']:rawpins.append(pin(folder/row[n]))
 return a
components={}
for rec in X['components']:
 a=rec['asset'];s=rec['scale'];v=body(rec,Q/'components');assert rec['full_native_frame']==B['bindings'][a]['native']['frame'];assert v.shape==(32*s,32*s);assert(rec['retained_cells']or[])==(rec['full_native_frame'].get('original_detail_cells')or[]);domain=rec['palette_domain'];assert(domain is None)==(rec['full_native_frame'].get('palette_constraint')is None);assert domain is None or(set(domain)==set(sources[a].flat)and set(v.flat)<=set(domain));components[a,s]=v
for st in X['new_contributor_stages']:
 aid=st['asset'];s=st['scale'];a=components[aid,s];control=upscale(sources[aid],s);frame=B['bindings'][aid]['native']['frame'];mask=np.zeros(a.shape,dtype=bool)
 for xx,yy in frame.get('original_detail_cells',[]):mask[yy*s:(yy+1)*s,xx*s:(xx+1)*s]=True
 changed=int(np.count_nonzero((a!=control)&~mask));assert changed==st['nonretained_prejoin_samples_different_from_OriginalNx'];assert changed>0 or s<3
arrays={};totals={'outside_support_exact':0,'stable_old_contributor_interiors_exact':0,'reserved250plus_exact':0,'padding_exact':0,'delta':0,'Source_retention_H5654':0,'Source_retention_old_cohort':0,'Source_retention_joint39':0,'palette_domain_H5654':0,'palette_domain_old_cohort':0,'palette_domain_joint39':0};checks=[];contributor_checks=[]
for rec in X['records']:
 ci=rec['case_index'];s=rec['scale'];case=r['cases'][ci];w=case['width_tiles'];h=case['height_tiles'];ids=case['ordered_source_ids'];logical=np.zeros((h*32,w*32),dtype='u2')
 for t,aid in enumerate(ids):
  if aid is not None:logical[t//w*32:(t//w+1)*32,t%w*32:(t%w+1)*32]=sources[aid]
 arr={role:body(v,Q/'planes')for role,v in rec['planes'].items()};assert set(arr)==set(roles);o=upscale(logical,s);assert np.array_equal(arr[roles[0]],o)
 for role,a in arr.items():assert np.array_equal(classes(a),classes(o));assert np.array_equal(a[o>=250],o[o>=250]);arrays[ci,s,role]=a
 base=arr[roles[1]];old=arr[roles[2]];joint=arr[roles[3]];cohort=set(case['cohort_selected']);oldallowed=foreign|cohort;added=own-cohort;mask=np.zeros(o.shape,dtype=bool)
 for x0,y0,x1,y1 in rec['added_new_foreign_support_rectangles']:mask[y0*s:y1*s,x0*s:x1*s]=True
 assert np.array_equal(old[~mask],joint[~mask]);outside=int((~mask).sum());stable=padding=0
 for slot,aid in enumerate(ids):
  yy=slot//w*32*s;xx=slot%w*32*s;sl=np.s_[yy:yy+32*s,xx:xx+32*s]
  if aid is None:
   assert np.array_equal(base[sl],o[sl])and np.array_equal(old[sl],o[sl])and np.array_equal(joint[sl],o[sl]);padding+=1024*s*s;continue
  if aid in own:assert np.array_equal(base[sl],o[sl])
  if aid in added:assert np.array_equal(old[sl],o[sl])
  if aid in oldallowed:
   inner=np.s_[yy+2*s:yy+30*s,xx+2*s:xx+30*s];assert np.array_equal(old[inner],joint[inner]);stable+=784*s*s
 for key,role,tag in [('H5654_inputs',roles[1],'H5654'),('old_cohort_inputs',roles[2],'old_cohort'),('joint39_inputs',roles[3],'joint39')]:
  retained=domainsamples=0;actualslots=set()
  for pre in rec[key]['pre_blit']:
   slot=pre['slot'];aid=ids[slot];assert aid==pre['asset'];assert pre['position']==[slot%w*32,slot//w*32];assert aid not in actualslots or True;actualslots.add(slot);assert pre['component']['full_native_frame']==B['bindings'][aid]['native']['frame']
   for cx,cy in pre['retained_cells']or[]:
    yy=(slot//w*32+cy)*s;xx=(slot%w*32+cx)*s;sl=np.s_[yy:yy+s,xx:xx+s];assert np.array_equal(arr[role][sl],o[sl]);retained+=s*s
   if pre['palette_domain']is not None:
    yy=slot//w*32*s;xx=slot%w*32*s;tile=arr[role][yy:yy+32*s,xx:xx+32*s];assert set(tile.flat)<=set(pre['palette_domain']);domainsamples+=1024*s*s
  expectedslots={i for i,a in enumerate(ids)if a in(foreign if tag=='H5654'else oldallowed if tag=='old_cohort'else foreign|own)};assert actualslots==expectedslots
  assert retained==rec[key]['retained_OriginalNx_samples'];assert domainsamples==rec[key]['palette_domain_samples'];totals['Source_retention_'+tag]+=retained;totals['palette_domain_'+tag]+=domainsamples
 for st in rec['new_contributor_slot_checks']:
  slot=st['slot'];aid=ids[slot];assert aid==st['asset']and aid in own;yy=slot//w*32*s;xx=slot%w*32*s;sl=np.s_[yy:yy+32*s,xx:xx+32*s];inner=np.s_[yy+2*s:yy+30*s,xx+2*s:xx+30*s];v0=int(np.count_nonzero(joint[sl]!=o[sl]));v1=int(np.count_nonzero(joint[sl]!=old[sl]));vi=int(np.count_nonzero(joint[inner]!=o[inner]));assert(v0,v1,vi)==(st['final_samples_different_from_globalOriginalNx'],st['final_samples_different_from_old_cohort_only'],st['new_material_in_interior_samples']);assert st['new_other_cohort_contributor']==(aid in added)
  if s>=3:assert vi>0 and(aid not in added or v1>0)
  contributor_checks.append({'case_index':ci,'scale':s,**st})
 delta=int(np.count_nonzero(old!=joint));reserved=int((o>=250).sum());assert outside==rec['outside_added_support_samples_exact']and stable==rec['stable_old_contributor_broad_interiors_exact']and padding==rec['outside_MAP_OriginalNx_padding_samples_exact']and reserved==rec['reserved250plus_exact']and delta==rec['changed_old_cohort_to_joint_samples']
 for k,n in [('outside_support_exact',outside),('stable_old_contributor_interiors_exact',stable),('reserved250plus_exact',reserved),('padding_exact',padding),('delta',delta)]:totals[k]+=n
 checks.append({'case_index':ci,'scale':s,'SourceNx_class_reserved_control_support_retention_domain_and_actual_contributors_PASS':True,'changed_old_cohort_to_joint':delta})
assert samples==1024*30*(40+11*9*4),samples
V=P/'whole-saved-native-joint11-pages';V.mkdir(exist_ok=False);pages=[]
for case in r['cases']:
 ci=case['case_index'];w=case['width_tiles']*32;h=case['height_tiles']*32;maxw=w*4;gap=16;fac={1:2,2:1,3:1,4:1};height=32+sum(h*s*fac[s]+36 for s in range(1,5));im=Image.new('RGB',(4*(maxw+gap)+8,height),(20,28,38));draw=ImageDraw.Draw(im);draw.text((8,5),f'case{ci:02} {case["consumer_cohort"]} {case["mission"]} r{case["window_row0"]}c{case["window_column0"]} | ORIGINAL / H5654 / COHORT / JOINT39',fill='white');panes=[];y=32
 for s in range(1,5):
  f=fac[s];draw.text((8,y),f'native{s}; all four complete genuine3x3roles; Source-retained pixels earn no HD credit',fill='white')
  for j,role in enumerate(roles):
   rgb=pal[arrays[ci,s,role]];rgb=np.repeat(np.repeat(rgb,f,0),f,1);xx=8+j*(maxw+gap);yy=y+20;im.paste(Image.fromarray(rgb),(xx,yy));panes.append({'case_index':ci,'scale':s,'role':role,'xywh':[xx,yy,rgb.shape[1],rgb.shape[0]],'nearest_display_factor':f})
  y+=h*s*f+36
 path=V/f'case{ci:02}-WHOLE-Source-H5654-cohort-JOINT39-all4-native.png';im.save(path);decoded=np.asarray(Image.open(path))
 for z in panes:
  x0,y0,ww,hh=z['xywh'];rgb=np.repeat(np.repeat(pal[arrays[ci,z['scale'],z['role']]],z['nearest_display_factor'],0),z['nearest_display_factor'],1);assert np.array_equal(decoded[y0:y0+hh,x0:x0+ww],rgb)
 pages.append({'case_index':ci,'label':case['label'],'page':pin(path),'dimensions':list(im.size),'panes':panes})
assert len(pages)==11 and sum(len(p['panes'])for p in pages)==176
for p,x in refs.items():assert pin(p)==x
inputs=save('AUTHENTICATED-CONSUMED-IMMUTABLE-INPUTS-JOINT11.json',list(refs.values()));auth=save('PASS-SAVED-JOINT11-ALL44SCALES-160COMPONENTS-176WHOLE-ROLEBODIES.json',{'status':'TECHNICAL_SAVED_ONLY_PASS_AUTHOR_AND_DIFFERENT_PHYSICAL_REVIEW_PENDING','actual_proof':pin(proof),'unique_components':160,'unique_records':44,'unique_roles':176,'index_class_RGB_samples':samples,'actual_new_contributor_stages':28,'retained_and_control_totals':totals,'record_checks':checks,'all_new_contributor_slot_checks':contributor_checks,'all_saved_component_and_role_body_files':rawpins,'all_saved_pages':pages,'actual_call_truth':{'adapter_compiles':1,'compile_exit':0,'constructor_calls':2,'first_exit101_before_any_component_or_role_output':True,'focused_samebinary_strictmanifestV2_exit':0,'engine_builds':0,'World':0,'new_intrinsicQA':0,'file_only_renderer_calls':0},'source_static_math_reuse':pin(P/'STATIC-MATH-REUSE-EXACT-BEFORE-MAIN.json'),'all_immutable_consumed_pins':inputs,'coarse_Source_retention_zero_HD_credit':True})
interface=save('FROZEN-JOINT39-GENUINE11-ALLNATIVE-CONTEXT-PEER-INTERFACE.json',{'status':'FROZEN_SAVED_OUTPUT_INTERFACE_AUTHOR_AND_DIFFERENT_PHYSICAL_REVIEW_PENDING','actual_epoch':'SourceG2 5b6/H5654 +exact39 renderer bindings e3c9b36b','actual_proof':pin(proof),'actual_recipe':pin(P/'SEALED-JOINT39-GENUINE11-STRICT-MANIFEST-V2-RECIPE.json'),'finite_bindings':r['finite_bindings'],'publisher_renderer_freeze':r['publisher39freeze'],'authentication':auth,'whole_endpoint_pages':pages,'unique_whole_body_count':176,'native_scales':[1,2,3,4],'roles':roles,'limits':r['limits'],'actual_call_truth':{'adapter_compile0':1,'constructor101_preserved':1,'samebinary_constructor0':1,'new_intrinsicQA_World_enginebuild':0},'Source_retention_totals':totals})
print(json.dumps({'authentication':auth,'interface':interface,'samples':samples,'totals':totals,'pages':len(pages),'free':shutil.disk_usage(P).free},indent=2))
