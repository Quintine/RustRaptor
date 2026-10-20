from pathlib import Path
import json,hashlib,gzip,struct,ast,shutil
import numpy as np
from PIL import Image,ImageDraw
R=Path('/home/quintine/Projects/RaptorReplica/RustRaptor');P=Path(__file__).resolve().parent;Q=P/'actual-once-focused30380-genuine1-G2';FLOOR=1800000000
assert shutil.disk_usage(P).free>FLOOR+20000000
proof=Q/'ACTUAL-FOCUSED30380-GENUINE1-SOURCEG2-CONTEXTS.json';x=json.loads(proof.read_text());r=x['recipe'];bind=json.loads(Path(r['finite_bindings']['path']).read_text());own=set(r['selected']);foreign=set(bind['registered_foreign']);fallback=set(r['Original_fallbacks'])
def pin(p):
 p=Path(p).resolve();s=p.stat();return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),size=s.st_size,mtime_ns=s.st_mtime_ns,mode=s.st_mode)
def save(n,v):
 p=P/n
 with p.open('x')as f:json.dump(v,f,indent=2);f.write('\n')
 return pin(p)
refs={}
def walk(v):
 if isinstance(v,dict):
  if 'path'in v and 'sha256'in v:
   p=Path(v['path'])
   # Canonical baseline identity is a capture witness, not an immutable consumed input.
   if p==R/'data/hd/hd.json':return
   z=pin(p);assert z['sha256']==v['sha256'],p
   for k in ['size','mtime_ns','mode']:
    if k in v:assert z[k]==v[k],(p,k)
   if 'bytes'in v:assert z['size']==v['bytes']
   refs[str(p)]=z
  for a in v.values():walk(a)
 elif isinstance(v,list):
  for a in v:walk(a)
walk(bind);walk(r);assert len(x['records'])==r['expected']['records']and len(x['components'])==r['expected']['components']and len(x['own_stage_checks'])==4 and x['diagnostics']==[]and x['World_calls']==0
k=R/'.reference/hd-independent-green7-H5567-genuine31-context-review-20261018-v1/authenticate_readonly.py';fn=next(a for a in ast.parse(k.read_text()).body if isinstance(a,ast.FunctionDef)and a.name=='upscale');ns={'np':np};exec(compile(ast.Module(body=[fn],type_ignores=[]),str(k),'exec'),ns);upscale=ns['upscale']
pal=np.frombuffer((Q/'actual-palette-rgb.bin').read_bytes(),dtype='u1').reshape(256,3);rawpal=np.frombuffer((R/'data/misc/PALETTE_DAT').read_bytes(),dtype='u1').astype('u2');assert np.array_equal(pal,((np.minimum(rawpal,63)<<2)|(np.minimum(rawpal,63)>>4)).astype('u1').reshape(256,3))
def classes(a):return np.where(a<240,0,np.where(a<245,1,np.where(a<250,2,a))).astype('u1')
sources={}
for aid,b in bind['bindings'].items():
 raw=Path(b['source']['path']).read_bytes();assert struct.unpack('<5i',raw[:20])==(1,1,0,32,32);sources[aid]=np.frombuffer(raw[20:],dtype='u1').reshape(32,32).astype('u2')
rawpins=[];samples=0
def body(row,folder):
 global samples
 a=np.frombuffer(gzip.decompress((folder/row['indexed']).read_bytes()),dtype='<u2').reshape(row['height'],row['width']);assert a.max()<256;cl=np.frombuffer(gzip.decompress((folder/row['classes']).read_bytes()),dtype='u1').reshape(a.shape);assert np.array_equal(cl,classes(a));ppm=gzip.decompress((folder/row['PPM']).read_bytes());assert ppm==f'P6\n{a.shape[1]} {a.shape[0]}\n255\n'.encode()+pal[a].tobytes();samples+=a.size
 for n in ['indexed','classes','PPM']:rawpins.append(pin(folder/row[n]))
 return a
components={}
for rec in x['components']:
 aid=rec['asset'];s=rec['scale'];a=body(rec,Q/'components');assert rec['full_native_frame']==bind['bindings'][aid]['native']['frame'];assert a.shape==(32*s,32*s);assert (rec['retained_cells']or[])==(rec['full_native_frame'].get('original_detail_cells')or[]);domain=rec['palette_domain'];assert (domain is None)==(rec['full_native_frame'].get('palette_constraint')is None);assert domain is None or(set(domain)==set(sources[aid].flat)and set(a.flat)<=set(domain));components[aid,s]=a
banks={aid:next(v for v in json.loads(Path(b['path']).read_text())if v['asset']==aid)for aid,b in r['accepted_own_banks'].items()};stagechecks=[]
for st in x['own_stage_checks']:
 aid=st['asset'];s=st['scale'];details=bind['bindings'][aid]['native']['frame'].get('original_detail_cells',[]);raw=components[aid,s];standalone=raw.copy();srcNx=upscale(sources[aid],s);owners=np.zeros(raw.shape,dtype=bool)
 for xx,yy in details:owners[yy*s:(yy+1)*s,xx*s:(xx+1)*s]=True
 standalone[owners]=srcNx[owners];accepted=np.array(banks[aid]['scales'][s-1]['indices'],dtype='u2').reshape(raw.shape);assert np.array_equal(standalone,accepted);n=int(np.count_nonzero((srcNx==244)&(accepted!=244)&(~owners)));assert n==st['accepted_global_SourceNx_244_fringe_mismatches_outside_retained_owners'];stagechecks.append(dict(asset=aid,scale=s,restored_SourceNx_matches_accepted_final_G2=True,protected_logical_cells=len(details),unretained_global244_fringe=n))
roles=['Original_joined_SourceNx','immutable_actual_H_baseline','selected_focused30380_proposal'];arrays={};totals=dict(retained_baseline=0,retained_proposal=0,outside=0,fallback=0,own_original=0,foreign_interior=0,delta=0,final_global244_index_differences=0)
checks=[]
for rec in x['records']:
 ci=rec['case_index'];s=rec['scale'];case=r['cases'][ci];cols=case['width_tiles'];rows=case['height_tiles'];ids=case['ordered_source_ids'];logical=np.empty((rows*32,cols*32),dtype='u2')
 for t,aid in enumerate(ids):logical[t//cols*32:(t//cols+1)*32,t%cols*32:(t%cols+1)*32]=sources[aid]
 arr={role:body(v,Q/'planes')for role,v in rec['planes'].items()};o=upscale(logical,s);assert np.array_equal(o,arr[roles[0]])
 for role,a in arr.items():assert np.array_equal(classes(a),classes(o));assert np.array_equal(a[o>=250],o[o>=250]);arrays[ci,s,role]=a
 b=arr[roles[1]];p=arr[roles[2]];mask=np.zeros(o.shape,dtype=bool)
 for x0,y0,x1,y1 in rec['support_rectangles']:mask[y0*s:y1*s,x0*s:x1*s]=True
 assert np.array_equal(b[~mask],p[~mask]);outside=int((~mask).sum());owncount=fc=fi=0
 for t,aid in enumerate(ids):
  yy=t//cols*32*s;xx=t%cols*32*s;sl=np.s_[yy:yy+32*s,xx:xx+32*s]
  if aid in own:assert np.array_equal(b[sl],o[sl]);owncount+=1024*s*s
  if aid in fallback:assert np.array_equal(b[sl],o[sl])and np.array_equal(p[sl],o[sl]);fc+=1024*s*s
  if aid in foreign:
   inter=np.s_[yy+2*s:yy+30*s,xx+2*s:xx+30*s];assert np.array_equal(b[inter],p[inter]);fi+=784*s*s
 for inp,role in [('baseline_inputs',roles[1]),('proposal_inputs',roles[2])]:
  retained=0
  for pre in rec[inp]['pre_blit']:
   t=pre['slot'];aid=ids[t];assert aid==pre['asset']and pre['position']==[t%cols*32,t//cols*32]
   for cx,cy in pre['retained_cells']or[]:
    yy=(t//cols*32+cy)*s;xx=(t%cols*32+cx)*s;sl=np.s_[yy:yy+s,xx:xx+s];assert np.array_equal(arr[role][sl],o[sl]);retained+=s*s
  assert retained==rec[inp]['retained_OriginalNx_samples'];totals['retained_baseline'if inp=='baseline_inputs'else'retained_proposal']+=retained
 delta=int(np.count_nonzero(b!=p));assert outside==rec['outside_support_samples_exact']and owncount==rec['baseline_own_Original_samples_exact']and fc==rec['foreign_Original_fallback_samples_exact']and fi==rec['broad_foreign_interior_samples_exact']and delta==rec['changed_samples']
 for k,v in dict(outside=outside,fallback=fc,own_original=owncount,foreign_interior=fi,delta=delta,final_global244_index_differences=int(np.count_nonzero((o==244)&(p!=244)))).items():totals[k]+=v
 checks.append(dict(case_index=ci,scale=s,all_SourceNx_class_reserved_outside_fallback_foreign_exact=True,retained_joined_SourceNx_exact=True,changed=delta))
assert samples==1024*30*(r['expected']['foreign']+r['expected']['own']+sum(c['width_tiles']*c['height_tiles']for c in r['cases'])*3)
for view in r['ordered_views']:
 if 'before'in view:
  a=r['cases'][view['before']]['ordered_source_ids'];b=r['cases'][view['settled']]['ordered_source_ids'];slot=view['changed_slot'];assert [j for j in range(len(a))if a[j]!=b[j]]==[slot] and a[slot]==view['Original_actor']['intact'] and b[slot]==view['Original_actor']['settled']
 else:
  ids=r['cases'][view['case_index']]['ordered_source_ids'];assert ids[view['left_slot']]=='103d5'and ids[view['right_slot']]=='103d6'and view['right_slot']==view['left_slot']+1
V=P/'whole-saved-native-context-pages';V.mkdir();pages=[]
for case in r['cases']:
 ci=case['case_index'];w=case['width_tiles']*32;h=case['height_tiles']*32;maxw=w*4;gap=16;factors={1:2,2:1,3:1,4:1};totalheight=32+sum(h*s*factors[s]+36 for s in range(1,5));im=Image.new('RGB',(3*(maxw+gap)+8,totalheight),(20,28,38));draw=ImageDraw.Draw(im);draw.text((8,5),case['label']+' | Original / immutable capturedH / proposed1 | fixed G2',fill='white');panes=[];y=32
 for s in range(1,5):
  factor=factors[s];draw.text((8,y),f'native{s}: full genuine {case["width_tiles"]}x{case["height_tiles"]}; retained Original cells are not HD credit',fill='white')
  for j,role in enumerate(roles):
   rgb=pal[arrays[ci,s,role]];rgb=np.repeat(np.repeat(rgb,factor,0),factor,1);xx=8+j*(maxw+gap);yy=y+20;im.paste(Image.fromarray(rgb),(xx,yy));panes.append(dict(case_index=ci,scale=s,role=role,xywh=[xx,yy,rgb.shape[1],rgb.shape[0]],nearest_display_factor=factor))
  y+=h*s*factor+36
 path=V/f'case{ci:02}-WHOLE-Original-capturedH-proposed1-native1to4.png';im.save(path);dec=np.asarray(Image.open(path))
 for q in panes:
  xx,yy,ww,hh=q['xywh'];rgb=np.repeat(np.repeat(pal[arrays[ci,q['scale'],q['role']]],q['nearest_display_factor'],0),q['nearest_display_factor'],1);assert np.array_equal(dec[yy:yy+hh,xx:xx+ww],rgb)
 pages.append(dict(case_index=ci,page=pin(path),dimensions=list(im.size),panes=panes))
orderedpages=[]
for event_index,view in enumerate([v for v in r['ordered_views']if 'before'in v]):
 for s in range(1,5):
  case=r['cases'][view['before']];w=case['width_tiles']*32*s;h=case['height_tiles']*32*s;im=Image.new('RGB',(3*(w+16)+8,2*(h+36)+36),(20,28,38));draw=ImageDraw.Draw(im);draw.text((8,5),f'Legal {view["Original_actor"]["intact"]}->{view["Original_actor"]["settled"]} event{event_index} native{s}; static, no natural timing',fill='white');panes=[]
  for row,(side,ci)in enumerate([('intact',view['before']),('settled',view['settled'])]):
   y=36+row*(h+36);draw.text((8,y),side,fill='white')
   for j,role in enumerate(roles):
    xx=8+j*(w+16);yy=y+20;rgb=pal[arrays[ci,s,role]];im.paste(Image.fromarray(rgb),(xx,yy));panes.append(dict(case_index=ci,scale=s,role=role,ordered_role=side,xywh=[xx,yy,w,h],nearest_display_factor=1))
  path=V/f'ordered-event{event_index:02}-native{s}-WHOLE-before-settled.png';im.save(path);dec=np.asarray(Image.open(path))
  for q in panes:
   xx,yy,ww,hh=q['xywh'];assert np.array_equal(dec[yy:yy+hh,xx:xx+ww],pal[arrays[q['case_index'],s,q['role']]])
  orderedpages.append(dict(Original_event=view,page=pin(path),native_scale=s,dimensions=list(im.size),panes=panes))
assert len(pages)==1 and len(orderedpages)==0 and sum(len(v['panes'])for v in pages+orderedpages)==12
for p,z in refs.items():assert pin(p)==z
save('AUTHENTICATED-CONSUMED-IMMUTABLE-INPUTS.json',list(refs.values()))
auth=save('PASS-SAVED-FOCUSED30380-GENUINE1-ALL4SCALES-12ROLEBODIES.json',dict(status='TECHNICAL_SAVED_ONLY_PASS_NOT_PHYSICAL_ART_APPROVAL',actual_proof=pin(proof),components=len(x["components"]),unique_role_bodies=12,page_bodies=12,SourceNx_controls=4,total_index_class_RGB_samples=samples,totals=totals,stage_checks=stagechecks,record_checks=checks,actual_raw_planes=rawpins,pages=pages,ordered_pages=orderedpages,retained_Original_selected_owner_counts={a:len(bind["bindings"][a]["native"]["frame"].get("original_detail_cells",[]))for a in own},actual_constructor_exit_code=json.loads((P/'ACTUAL-GENUINE1-CONSTRUCTOR-TERMINAL.json').read_text())['exit_code'],file_only_metadata_recovery=False,retained_Original_cells_no_HDcredit=True,global_intrinsic244_fringe_distinction_preserved=True,World=0,new_raster_or_generation=0))
interface=save('FROZEN-FOCUSED30380-GENUINE1-ALLNATIVE-SOURCEG2-CONTEXT-PEER-INTERFACE.json',dict(status='FROZEN_TECHNICAL_BODY_INTERFACE_AUTHOR_PHYSICAL_AND_DIFFERENT_PEER_PENDING',selected1=sorted(own),catalogue_unused=[],actual_pixel_epoch=f'SourceG2 compiled5b6/H{r["expected"]["baseline_count"]} finite consumed bank',recipe=pin(P/'SEALED-FOCUSED30380-GENUINE1-CURRENTG2-RECIPE.json'),actual_proof=pin(proof),bindings=r['finite_bindings'],census=r['Source_census'],authentication=auth,whole_endpoint_pages=pages,ordered_event_pages=orderedpages,spatial_pair_order_views=[v for v in r['ordered_views']if 'before'not in v],limits=r['limits'],technical_totals=totals,unique_whole_role_bodies=12,duplicated_ordered_role_bodies=0,whole_page_bodies=12,source_grid_from_actual_MAP=True))
print(json.dumps(dict(authentication=auth,interface=interface,totals=totals,free=shutil.disk_usage(P).free),indent=2))
