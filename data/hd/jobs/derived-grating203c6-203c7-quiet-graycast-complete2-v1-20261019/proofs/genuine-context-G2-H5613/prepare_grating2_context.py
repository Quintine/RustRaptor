from pathlib import Path
import json,hashlib,os,struct,shutil,copy
O=Path(__file__).resolve().parent;R=O.parent.parent;A=R/'.reference/hd-grating2-fixed-graycast-once-currentG2-author-20261019-v1';guards={};own={'203c6','203c7'}
def pin(p):
 p=Path(p).absolute();s=p.stat();return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),size=s.st_size,mtime_ns=s.st_mtime_ns,mode=s.st_mode)
def take(p,expected=None):
 q=pin(p)
 if expected:assert q['sha256']==expected
 guards[q['path']]=q;return Path(p).read_bytes()
def save(n,v):
 p=O/n;assert not p.exists();p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2)+'\n');return pin(p)
assert shutil.disk_usage(O).free>=2_200_000_000
census=json.loads(take(A/'STATIC-CURRENT27MAP-GRATING2-GENUINE-CALLER-CENSUS-AND-ROUTE.json','a05987676876e592baf52177f24894e20851f54063c108fc4cb54db1c6d47cad'))
for p,h in census['all27_MAP_and_FLATS_pins'].items():take(R/p,h)
cat={};names={}
for l in take(R/'data/INDEX').decode().splitlines():
 a,n,p=l.split();cat[int(a,16)]=(int(n),R/'data'/p);names[Path(p).name]=int(a,16)
flats={}
for g in range(4):
 a=names[f'FLATSG{g+1}_ITM'];b=take(cat[a][1]);start=names[f'STARTG{g+1}TILES']+1;rr=[]
 for k in range(len(b)//8):
  d,h,re=struct.unpack_from('<ihh',b,k*8);rr.append(dict(intact=f'{start+k:05x}',settled=None if d==k else f'{start+d:05x}',health=0 if d==k else h,reward=max(0,re),game=g,FLATS_record=k,FLATS_asset=f'{a:05x}',FLATS_byte_offset=8*k))
 flats[g]=rr
maps={}
for sec in range(1,4):
 for w in range(1,10):
  a=names[f'MAP{w}G{sec}_MAP'];b=take(cat[a][1]);rows=[]
  for k in range(1350):f,g=struct.unpack_from('<hh',b,12+k*4);rows.append(flats[g][f])
  maps[f'base:sector_{sec}_wave_{w}']=rows
endpoints=[];pairs=[]
def at(m,y,x):return maps[m][y*9+x]if 0<=y<150 and 0<=x<9 else None
def endpoint(p,actors):
 m,y,x=p['mission'],p['row'],p['column'];v=[at(m,y+dy,x+dx)['intact']if at(m,y+dy,x+dx)else None for dy in [-1,0,1]for dx in [-1,0,1]]
 for ac in actors:
  slot=(ac['row']-y+1)*3+ac['column']-x+1;assert v[slot]==ac['Original_tile']['intact'];v[slot]=ac['Original_tile']['settled']
 row=dict(endpoint_index=len(endpoints),Source_key=hashlib.sha256(json.dumps([m,y,x,v],sort_keys=True,separators=(',',':')).encode()).hexdigest(),mission=m,row=y,column=x,columns=3,ordered_source_ids=v,role='authentic_static_intact'if not actors else'controlled_legal_foreign_neighbor_settled',settled_actors=actors,semantic_scope='Exact static health0 grating remains intact. One genuine foreign actor only may be settled; no timing/World claim.')
 endpoints.append(row);return len(endpoints)-1
before={}
for p in census['all_callers']:
 assert p['Original_tile']['health']==0 and p['Original_tile']['settled']is None and p['Original_tile']['reward']==0
 before[p['mission'],p['row'],p['column']]=endpoint(p,[])
for asset in ['203c6','203c7']:
 p=next(p for p in census['all_callers']if p['Original_tile']['intact']==asset);m,y,x=p['mission'],p['row'],p['column'];ac=None
 for dy,dx in [(0,1),(-1,0),(1,0),(0,-1)]:
  t=at(m,y+dy,x+dx)
  if t and t['health']>0 and t['settled']is not None and t['intact']not in own and t['settled']not in own:ac=dict(row=y+dy,column=x+dx,Original_tile=t);break
 assert ac;bi=before[m,y,x];ai=endpoint(p,[ac]);diff=[i for i,(b,a)in enumerate(zip(endpoints[bi]['ordered_source_ids'],endpoints[ai]['ordered_source_ids']))if b!=a];assert len(diff)==1
 pairs.append(dict(pair_index=len(pairs),before_endpoint=bi,settled_endpoint=ai,changed_slot=diff[0],Original_actor=ac['Original_tile'],actor_position=[ac['row'],ac['column']],event_id=f"{m}:r{ac['row']}c{ac['column']}:{ac['Original_tile']['intact']}-to-{ac['Original_tile']['settled']}",separate_one_cell_state=True,comparison_kind='one_genuine_foreign_neighbor_event_beside_static_grating',all_scales=[1,2,3,4]))
assert len(endpoints)==14 and len(pairs)==2
ids=sorted({v for e in endpoints for v in e['ordered_source_ids']if v});sources=[]
for a in ids:
 b=take(cat[int(a,16)][1]);header=list(struct.unpack('<5i',b[:20]));assert header==[1,1,0,32,32]and len(b)==1044;sources.append(dict(asset=a,source=pin(cat[int(a,16)][1]),header=header))
take(R/'data/misc/PALETTE_DAT')
# Snapshot headers, hardlink all declared immutable raw dependencies without hashing/copying8GB.
canonical=R/'data/hd';hdbytes=take(canonical/'hd.json','b13a4f7c494262527df1137ed6a5442e100fc51ec25680b7046e1c6f7820648a');hd=json.loads(hdbytes);native={};B=O/'immutable-H5613-data/hd';B.mkdir(parents=True);(B/'hd.json').write_bytes(hdbytes)
for n in ['provenance.json']:(B/n).write_bytes(take(canonical/n))
raws={}
for seq in hd['sequences']:
 for f in seq['frames']:
  a=f'{seq["base_asset"]+f["frame"]:05x}';assert a not in native;native[a]=dict(frame=f,full_sequence=seq)
  name=f['file']
  if name in raws:continue
  src=canonical/name;assert src.resolve().is_relative_to(canonical.resolve());dst=B/name;dst.parent.mkdir(parents=True,exist_ok=True);st=src.stat();os.link(src,dst);dt=dst.stat();assert(st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns)==(dt.st_dev,dt.st_ino,dt.st_size,dt.st_mtime_ns);raws[name]=dict(source=str(src),snapshot=str(dst),dev=st.st_dev,inode=st.st_ino,size=st.st_size,mtime_ns=st.st_mtime_ns)
assert len(native)==5613 and own.isdisjoint(native)
rawident=save('IMMUTABLE-H5613-ALL-RAW-HARDLINK-IDENTITIES-NO-COPY-NO-8GB-REHASH.json',dict(HD=pin(B/'hd.json'),registered=5613,unique_raw_dependencies=len(raws),raw_logical_bytes=sum(r['size']for r in raws.values()),new_copied_raw_bytes=0,all_source_and_destination_same_inode=True,raws=raws))
bindings=[]
for a in ids:
 if a in native:
  q=native[a];p=B/q['frame']['file'];take(p);bindings.append(dict(asset=a,**q,raw=pin(p)))
Q=A/'actual-once-current-SourceG2-intrinsic2';ownpack=A/'private-finalbinding-derived-complete2-pack';manifest=json.loads(take(ownpack/'hd.json'));routes=[]
for seq in manifest['sequences']:
 a=f'{seq["base_asset"]:05x}';f=seq['frames'][0];assert a in own and f['origin']==[0,0]and f['logical_width']==f['logical_height']==32;take(ownpack/f['file']);routes.append(dict(asset=a,private_full_sequence=seq,actual_bank=pin(Q/'actual-indexed-source-and-scales.json'),actual_plain_bank=pin(Q/'actual-indexed-source-and-scales.json'),actual_QA=pin(Q/'runtime-qa.json'),measured_scope='Exact actual derived no-retention G2 native bank for both frames. Public terrain prejoin and compositor require no Source functional retention.'))
for q in [Q/'actual-indexed-source-and-scales.json',Q/'runtime-qa.json',A/'CLOSED-AUTHOR-FIXED-GRATING2-ONE-DERIVE-ONE-G2-INTRINSIC-QUAL2-CONTEXT-PENDING.json',Path(str(A)+'-strict-author-qual2-portable-draft-closure.json')]:take(q)
epochp=R/'.reference/hd-SourceG2-current-intrinsic-helper-and-epoch-carry-private-20261019-v1/CURRENT-SOURCEG2-HELPER-COMPILE-RECEIPT.json';epoch=json.loads(take(epochp))
for key in ['library','serde_json']:take(Path(epoch[key]['path']),epoch[key]['sha256'])
for p,h in epoch['source18'].items():take(R/p,h)
contract=dict(status='ROOT_ACTIVATED_SOURCEG2_GRATING2_GENUINE14_H5613',selected=sorted(own),source_assets=ids,source_pins=sources,own_routes=routes,own_pack_root=str(ownpack),endpoints=endpoints,ordered_pairs=pairs,full12_caller_census=census['all_callers'],Original_definitions=census['Original_definitions'],scope=dict(real_MAP_callers=12,representative_windows=12,unique_endpoints=14,scale_records=56,whole_planes=168,ordered_views=2,distinct_damage_events=2,own_center_transitions=0,foreign_neighbor_transitions=2,selected_material_assets=2,used_context_assets=2,World=0,new_intrinsic_QA=0,all12_real_callers=True,not_all_neighbor_state_combinations=True),baseline=dict(packroot=str(B),HD=pin(B/'hd.json'),provenance=pin(B/'provenance.json'),hardlink_identity=rawident,finite_bindings=bindings),epoch=dict(receipt=pin(epochp),library=epoch['library'],serde_json=epoch['serde_json'],dependency_dir=str(R/'target/desktop-runtime/release/deps')),Root_authority='Root authorizes immutableH5613 headers+hardlinked dependencies currentb13a4f7c and current5b6G2 library, one bounded adapter compile/composition, all12 real3x3 windows+2 real legal foreign-neighbor states. Static ownhealth0/reward0 intact-only, World0/newintrinsicQA0/newart0. Preserve actualG2QA62d093c4 literal.')
save('FROZEN-GRATING2-G2-H5613-GENUINE14-SOURCE-CONTRACT.json',contract);save('BEFORE-BOUNDED-SOURCE-NATIVE-BANK-EPOCH-GUARDS.json',list(guards.values()));print(json.dumps(dict(scope=contract['scope'],source_count=len(ids),foreign_count=len(bindings),raw_hardlinks=len(raws),free_bytes=shutil.disk_usage(O).free)))
