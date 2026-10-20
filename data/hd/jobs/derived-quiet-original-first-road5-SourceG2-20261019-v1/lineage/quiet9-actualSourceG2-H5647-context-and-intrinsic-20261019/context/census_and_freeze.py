from pathlib import Path
import json,hashlib,struct,os,shutil
O=Path(__file__).resolve().parent;R=O.parent.parent;Q=R/'.reference/hd-stag-nine1050-quiet-materialplate-remediation-20261019-v1';own=set('10502 10504 10506 10508 10509 1050a 1050b 1050c 1050e'.split());guards={}
def pin(p):
 p=Path(p).absolute();s=p.stat();return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),size=s.st_size,mtime_ns=s.st_mtime_ns,mode=s.st_mode)
def take(p):
 q=pin(p);guards[q['path']]=q;return Path(p).read_bytes()
def save(n,v):
 p=O/n;assert not p.exists();p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2)+'\n');return pin(p)
cat={};names={}
for l in take(R/'data/INDEX').decode().splitlines():
 a,n,p=l.split();cat[int(a,16)]=(int(n),R/'data'/p);names[Path(p).name]=int(a,16)
flats={};definitions={}
for g in range(4):
 a=names[f'FLATSG{g+1}_ITM'];b=take(cat[a][1]);start=names[f'STARTG{g+1}TILES']+1;rr=[]
 for k in range(len(b)//8):
  d,h,re=struct.unpack_from('<ihh',b,k*8);v=dict(intact=f'{start+k:05x}',settled=None if d==k else f'{start+d:05x}',health=0 if d==k else h,reward=max(0,re),game=g,FLATS_record=k,FLATS_asset=f'{a:05x}',FLATS_byte_offset=8*k);rr.append(v)
  if v['intact']in own or v['settled']in own:definitions[v['intact']]=v
 flats[g]=rr
maps={};callers=[]
for sec in range(1,4):
 for w in range(1,10):
  a=names[f'MAP{w}G{sec}_MAP'];b=take(cat[a][1]);rows=[];m=f'base:sector_{sec}_wave_{w}'
  for k in range(1350):
   f,g=struct.unpack_from('<hh',b,12+k*4);v=flats[g][f];rows.append(v)
   if v['intact']in own or v['settled']in own:callers.append(dict(mission=m,row=k//9,column=k%9,Original_tile=v,roles=[r for r,key in [('direct','intact'),('settled','settled')]if v[key]in own]))
  maps[m]=rows
save('ALL27MAP-4FLATS-QUIET9-COMPLETE-REAL-CALLER-CENSUS.json',dict(selected=sorted(own),definitions=definitions,callers=callers,input_pins=list(guards.values()),total_map_cells=36450,roles={a:{role:sum(v['Original_tile'][key]==a for v in callers)for role,key in [('direct','intact'),('settled','settled')]}for a in sorted(own)}))
# Minimal deterministic set cover of actual targeted direct/settled roles; every selected target needs its real role represented.
def at(m,y,x):return maps[m][y*9+x]if 0<=y<150 and 0<=x<9 else None
candidates=[]
for p in callers:
 m,y,x=p['mission'],p['row'],p['column'];neigh=[at(m,y+dy,x+dx)for dy in [-1,0,1]for dx in [-1,0,1]];cov={(t['intact'],'direct')for t in neigh if t and t['intact']in own};actor=p['Original_tile'];settled=(actor['settled'],'settled')if actor['settled']in own else None
 if settled:cov.add(settled)
 candidates.append((p,cov))
need={(a,r)for a in own for r,key in [('direct','intact'),('settled','settled')]if any(t[key]==a for t in maps.values()for t in t)};selected=[];remaining=set(need)
while remaining:
 p,cov=max(candidates,key=lambda q:(len(q[1]&remaining),len(q[1]),-int(q[0]['mission'].split('_')[-1]),-q[0]['row'],-q[0]['column']))
 assert cov&remaining;selected.append(p);remaining-=cov
endpoints=[];pairs=[];seen={}
def endpoint(p,actors):
 m,y,x=p['mission'],p['row'],p['column'];ids=[at(m,y+dy,x+dx)['intact']if at(m,y+dy,x+dx)else None for dy in [-1,0,1]for dx in [-1,0,1]]
 for ac in actors:
  slot=(ac['row']-y+1)*3+ac['column']-x+1;assert ids[slot]==ac['Original_tile']['intact'];ids[slot]=ac['Original_tile']['settled']
 key=hashlib.sha256(json.dumps([m,y,x,ids],sort_keys=True,separators=(',',':')).encode()).hexdigest()
 if key in seen:return seen[key]
 i=len(endpoints);seen[key]=i;endpoints.append(dict(endpoint_index=i,Source_key=key,mission=m,row=y,column=x,columns=3,ordered_source_ids=ids,role='authentic_intact'if not actors else'controlled_one_genuine_actor_settled',settled_actors=actors,semantic_scope='Literal MAP/FLATS positions; one genuine settled actor at a time, no timing/World claim.'));return i
def pair(p,ac):
 b=endpoint(p,[]);a=endpoint(p,[ac]);diff=[i for i,(x,y)in enumerate(zip(endpoints[b]['ordered_source_ids'],endpoints[a]['ordered_source_ids']))if x!=y];assert len(diff)==1
 pairs.append(dict(pair_index=len(pairs),before_endpoint=b,settled_endpoint=a,changed_slot=diff[0],Original_actor=ac['Original_tile'],actor_position=[ac['row'],ac['column']],event_id=f"{p['mission']}:r{ac['row']}c{ac['column']}:{ac['Original_tile']['intact']}-to-{ac['Original_tile']['settled']}",separate_one_cell_state=True,comparison_kind='genuine_original_actor_transition',all_scales=[1,2,3,4]))
for p in selected:
 endpoint(p,[])
 if p['Original_tile']['settled']in own:assert p['Original_tile']['health']>0;pair(p,dict(row=p['row'],column=p['column'],Original_tile=p['Original_tile']))
# Ensure actual own destructible direct roles also get one state; no duplicates or invented damage.
covered_events={p['Original_actor']['intact']for p in pairs}
for a in sorted(own):
 ps=[p for p in callers if p['Original_tile']['intact']==a and p['Original_tile']['health']>0 and p['Original_tile']['settled']]
 if ps and a not in covered_events:
  p=ps[0];pair(p,dict(row=p['row'],column=p['column'],Original_tile=p['Original_tile']));covered_events.add(a)
actual_roles={(v,'settled'if any(ac['Original_tile']['settled']==v for ac in e['settled_actors'])else'direct')for e in endpoints for v in e['ordered_source_ids']if v in own};assert need<=actual_roles,(need-actual_roles)
plan=save('FINITE-GENUINE-QUIET9-WINDOW-AND-ORDERED-STATE-PLAN.json',dict(required_roles=sorted(need),covered_roles=sorted(actual_roles),selected_caller_centers=selected,endpoints=endpoints,ordered_pairs=pairs,all9_covered=True,all_callers_captured=False,World=0,new_intrinsic_QA=0,author_art_unchanged=True))
# Capture literal baseline now; full headers + zero-copy raw inode snapshot only.
assert shutil.disk_usage(O).free>1_800_000_000
canonical=R/'data/hd';hdbytes=take(canonical/'hd.json');hd=json.loads(hdbytes);native={};raws={};count=sum(len(s['frames'])for s in hd['sequences']);B=O/f'immutable-H{count}-data/hd';B.mkdir(parents=True);(B/'hd.json').write_bytes(hdbytes);(B/'provenance.json').write_bytes(take(canonical/'provenance.json'))
for seq in hd['sequences']:
 for f in seq['frames']:
  a=f'{seq["base_asset"]+f["frame"]:05x}';assert a not in native;native[a]=dict(frame=f,full_sequence=seq);name=f['file']
  if name in raws:continue
  src=canonical/name;assert src.resolve().is_relative_to(canonical.resolve());dst=B/name;dst.parent.mkdir(parents=True,exist_ok=True);st=src.stat();os.link(src,dst);dt=dst.stat();assert(st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns)==(dt.st_dev,dt.st_ino,dt.st_size,dt.st_mtime_ns);raws[name]=dict(source=str(src),snapshot=str(dst),dev=st.st_dev,inode=st.st_ino,size=st.st_size,mtime_ns=st.st_mtime_ns)
assert own.isdisjoint(native)
rawident=save('IMMUTABLE-LITERAL-BASELINE-RAW-HARDLINK-IDENTITIES-NO-8GB-COPY-OR-REHASH.json',dict(HD=pin(B/'hd.json'),registered=count,unique_raw_dependencies=len(raws),raw_logical_bytes=sum(r['size']for r in raws.values()),new_copied_raw_bytes=0,raws=raws))
ids=sorted({a for e in endpoints for a in e['ordered_source_ids']if a});sources=[];bindings=[]
for a in ids:
 b=take(cat[int(a,16)][1]);header=list(struct.unpack('<5i',b[:20]));assert header==[1,1,0,32,32]and len(b)==1044;sources.append(dict(asset=a,source=pin(cat[int(a,16)][1]),header=header))
 if a in native:
  q=native[a];take(B/q['frame']['file']);bindings.append(dict(asset=a,**q,raw=pin(B/q['frame']['file'])))
take(R/'data/misc/PALETTE_DAT');P=O/'combined-private-own9-pack';P.mkdir();sequences=[];routes=[]
for cohort,qa in [('road-damage5','actual-final-G2-schema-successor'),('collapsed-bridge4','actual-once-final-current-SourceG2')]:
 p=Q/cohort/'schema-correct-final-quiet-selector-pack';mf=json.loads(take(p/'hd.json'));bank=pin(Q/cohort/qa/'actual-indexed-source-and-scales.json');take(bank['path']);quality=pin(Q/cohort/qa/'runtime-qa.json');take(quality['path'])
 for seq in mf['sequences']:
  a=f'{seq["base_asset"]:05x}';assert a in own;f=seq['frames'][0];take(p/f['file']);os.link(p/f['file'],P/f['file']);sequences.append(seq);routes.append(dict(asset=a,private_full_sequence=seq,actual_bank=bank,actual_QA=quality,measured_scope='Actual POST-retention G2 native bank. Prejoin compares only outside retained-cell mask; after source restoration all samples equal literal bank before terrain joins. Final terrain restore uses whole joined SourceNx.'))
(P/'hd.json').write_text(json.dumps(dict(format_version=1,name='Private quiet9 exact approved frames combined without metadata change',sequences=sequences),indent=2)+'\n');take(P/'hd.json')
epochp=R/'.reference/hd-SourceG2-current-intrinsic-helper-and-epoch-carry-private-20261019-v1/CURRENT-SOURCEG2-HELPER-COMPILE-RECEIPT.json';ep=json.loads(take(epochp))
for k in ['library','serde_json']:assert pin(ep[k]['path'])['sha256']==ep[k]['sha256'];take(ep[k]['path'])
for p,h in ep['source18'].items():assert hashlib.sha256(take(R/p)).hexdigest()==h
assert take(canonical/'hd.json')==hdbytes
contract=dict(status='ROOT_ACTIVATED_SOURCEG2_QUIET9_GENUINE_CONTEXT',selected=sorted(own),source_assets=ids,source_pins=sources,own_routes=routes,own_pack_root=str(P),endpoints=endpoints,ordered_pairs=pairs,complete_census=pin(O/'ALL27MAP-4FLATS-QUIET9-COMPLETE-REAL-CALLER-CENSUS.json'),finite_plan=plan,scope=dict(real_relevant_callers=len(callers),unique_endpoints=len(endpoints),scale_records=len(endpoints)*4,whole_planes=len(endpoints)*12,ordered_views=len(pairs),selected_material_assets=9,World=0,new_intrinsic_QA=0,all_callers_captured=False,not_all_neighbor_state_combinations=True),baseline=dict(packroot=str(B),HD=pin(B/'hd.json'),provenance=pin(B/'provenance.json'),registered=count,hardlink_identity=rawident,finite_bindings=bindings),epoch=dict(receipt=pin(epochp),library=ep['library'],serde_json=ep['serde_json'],dependency_dir=str(R/'target/desktop-runtime/release/deps')),Root_authority='Root NEW_TASK 2026-10-19: Continue true Source caller census + finite genuine neighboring-context capture all9/currentG2 H5636. One bounded actual context run per coherent group; protect controls/real settled states, no artificial World events. Capture literal epoch before publication11, no canonical/tools promotion.')
save('FROZEN-QUIET9-G2-LITERAL-BASELINE-GENUINE-SOURCE-CONTRACT.json',contract);save('BEFORE-BOUNDED-SOURCE-NATIVE-BANK-EPOCH-GUARDS.json',list(guards.values()));print(json.dumps(dict(scope=contract['scope'],roles=sorted(need),baseline=count,HD=contract['baseline']['HD']['sha256'],source_count=len(ids),foreign_count=len(bindings),free_bytes=shutil.disk_usage(O).free)))
