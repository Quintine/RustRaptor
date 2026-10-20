from pathlib import Path
import json,hashlib,os,shutil,struct,collections
O=Path(__file__).resolve().parent;R=O.parents[1];A=R/'.reference/hd-iron-names-terrain10510-1051c-Original-primary-author-20261019-v1/shoreline4';own={'10514','10515','1051b','1051c'};guards={}
def pin(p):p=Path(p).resolve();s=p.stat();return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=s.st_size,mtime_ns=s.st_mtime_ns)
def take(p,h=None):
 q=pin(p);assert h is None or q['sha256']==h;guards[q['path']]=q;return Path(p).read_bytes()
def save(n,d):p=O/n;assert not p.exists();p.write_text(json.dumps(d,indent=2)+'\n');return pin(p)
assert shutil.disk_usage(O).free>=1_800_000_000
census=json.loads(take(O/'SOURCE-ALL27-MAPS-ALL4-FLATS-SHORELINE4-CALLER-CENSUS.json'))
for n,h in census['all27_MAP_and4_FLATS_pins'].items():take(R/n,h)
callers=census['all_callers'];maps=census['map_layouts'];selected=[];events=[]
def key(c):return(c['mission'],c['row'],c['column'])
def choose(c):
 if key(c)not in [key(x)for x in selected]:selected.append(c)
def at(m,y,x):return maps[m][y*9+x]if 0<=y<150 and 0<=x<9 else None
def legal(c):return[n for n in c['cardinal_neighbors']if n['Original_tile']['health']>0 and n['Original_tile']['settled']and n['Original_tile']['intact']not in own and n['Original_tile']['settled']not in own]
# Preserve BOTH real views of the only selected-selected cardinal join.
for j in census['own_own_cardinal_joins']:
 for y,x in[j['position'],j['neighbor_position']]:choose(next(c for c in callers if key(c)==(j['mission'],y,x)))
# One legal foreign-neighbor event per static selected family; no invented own damage state.
for asset in sorted(own):
 c=next(c for c in callers if c['Original_tile']['intact']==asset and legal(c) and 0<c['column']<8);choose(c);events.append((c,legal(c)[0]))
# Every campaign1 mission represented by a real selected caller.
for m in census['mission_counts']:
 if m not in [c['mission']for c in selected]:
  choices=[c for c in callers if c['mission']==m]
  choose(max(choices,key=lambda c:(sum(at(m,c['row']+dy,c['column']+dx)['intact']in own for dy in[-1,0,1]for dx in[-1,0,1]if at(m,c['row']+dy,c['column']+dx)),0<c['column']<8)))
# Fill14 genuine windows by novel ordered3x3 neighbor signatures, favour own-family variation.
def signature(c):return tuple(at(c['mission'],c['row']+dy,c['column']+dx)['intact']if at(c['mission'],c['row']+dy,c['column']+dx)else None for dy in[-1,0,1]for dx in[-1,0,1])
while len(selected)<14:
 seen={signature(c)for c in selected};remaining=[c for c in callers if key(c)not in [key(x)for x in selected]]
 choose(max(remaining,key=lambda c:(len(set(signature(c))&own),signature(c)not in seen,0<c['column']<8)))
endpoints=[];pairs=[]
def endpoint(c,ac=None):
 m,y,x=key(c);ids=list(signature(c));actors=[]
 if ac:
  slot=(ac['row']-y+1)*3+ac['column']-x+1;assert ids[slot]==ac['Original_tile']['intact'];ids[slot]=ac['Original_tile']['settled'];actors=[ac]
 row=dict(endpoint_index=len(endpoints),Source_key=hashlib.sha256(json.dumps([m,y,x,ids],separators=(',',':')).encode()).hexdigest(),mission=m,row=y,column=x,columns=3,ordered_source_ids=ids,role='authentic_static_intact'if not ac else'controlled_legal_foreign_neighbor_settled',settled_actors=actors,Original_definition=c['Original_tile']);endpoints.append(row);return len(endpoints)-1
before={key(c):endpoint(c)for c in selected}
for c,ac in events:
 bi=before[key(c)];ai=endpoint(c,ac);slot=(ac['row']-c['row']+1)*3+ac['column']-c['column']+1;pairs.append(dict(pair_index=len(pairs),before_endpoint=bi,settled_endpoint=ai,changed_slot=slot,Original_actor=ac['Original_tile'],actor_position=[ac['row'],ac['column']],event_id=f"{c['mission']}:r{ac['row']}c{ac['column']}:{ac['Original_tile']['intact']}-to-{ac['Original_tile']['settled']}",separate_one_cell_state=True))
assert len(endpoints)==18 and len(pairs)==4
cat={};names={}
for l in take(R/'data/INDEX').decode().splitlines():a,n,p=l.split();cat[int(a,16)]=(int(n),R/'data'/p);names[Path(p).name]=int(a,16)
ids=sorted({a for e in endpoints for a in e['ordered_source_ids']if a});sources=[]
for a in ids:
 b=take(cat[int(a,16)][1]);assert list(struct.unpack_from('<5i',b))==[1,1,0,32,32]and len(b)==1044;sources.append(dict(asset=a,source=pin(cat[int(a,16)][1])))
take(R/'data/misc/PALETTE_DAT');H=R/'data/hd';hb=take(H/'hd.json');hd=json.loads(hb);B=O/'immutable-H5636-data/hd';B.mkdir(parents=True);(B/'hd.json').write_bytes(hb);(B/'provenance.json').write_bytes(take(H/'provenance.json'));native={};raws={}
for seq in hd['sequences']:
 for f in seq['frames']:
  a=f'{seq["base_asset"]+f["frame"]:05x}';assert a not in native;native[a]=dict(frame=f,full_sequence=seq);name=f['file']
  if name in raws:continue
  src=H/name;dst=B/name;assert src.resolve().is_relative_to(H.resolve());dst.parent.mkdir(parents=True,exist_ok=True);os.link(src,dst);s=src.stat();t=dst.stat();assert(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns)==(t.st_dev,t.st_ino,t.st_size,t.st_mtime_ns);raws[name]=dict(source=str(src),snapshot=str(dst),dev=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns)
assert len(native)==5636 and own.isdisjoint(native);identity=save('IMMUTABLE-H5636-ALL-RAW-PATH-HARDLINK-IDENTITIES.json',dict(manifest=pin(B/'hd.json'),provenance=pin(B/'provenance.json'),frames=len(native),unique_raw_paths=len(raws),logical_raw_bytes=sum(x['bytes']for x in raws.values()),physical_raw_bytes_copied=0,raws=raws));bindings=[]
for a in ids:
 if a in native:
  n=native[a];take(B/n['frame']['file']);bindings.append(dict(asset=a,**n,raw=pin(B/n['frame']['file'])))
cand=json.loads(take(A/'candidate-notes.json','eaf74b54ec6b67e5f1896e13e8d48c6e594dd63264eaf3619c961731f63b3356'));ownpack=O/'selected4-pack';ownpack.mkdir();manifest=dict(format_version=1,name='Root-authorized private shoreline4 context pack',sequences=cand['sequences']);(ownpack/'hd.json').write_text(json.dumps(manifest,indent=2)+'\n')
for f in cand['targets']:
 src=A/'private-hd'/f['file'];take(src);dst=ownpack/f['file'];dst.parent.mkdir(parents=True,exist_ok=True);os.link(src,dst)
qa=pin(A/'actual-SourceG2-intrinsic/runtime-qa.json');assert qa['sha256']=='915185ad8677adbe9cf58a56a570a7fbd969f9de81385e6455fbec77b2d4d89d';take(qa['path']);bank=pin(A/'actual-SourceG2-intrinsic/actual-indexed-source-and-scales.json');take(bank['path']);take(A/'returned-untouched-atlas.png','eca43a75313243b03f67731e79b50fcbc9388a3e05ce06f38ac064fb60a3237d')
epochp=R/'.reference/hd-SourceG2-current-intrinsic-helper-and-epoch-carry-private-20261019-v1/CURRENT-SOURCEG2-HELPER-COMPILE-RECEIPT.json';epoch=json.loads(take(epochp));
for k in ['library','serde_json']:take(epoch[k]['path'],epoch[k]['sha256'])
for n,h in epoch['source18'].items():take(R/n,h)
contract=dict(status='ROOT_AUTHORIZED_SHORELINE4_CURRENTG2_H5636_GENUINE18',Root_GO=True,Root_authority='Root explicitly authorizes one finite currentG2 compositor compilation/composition, no World/newQA/art/cleanup/canonical/Git; 1.8GB disk floor. All-header raw paths hardlinked; only finite consumed artwork decoded.',selected=sorted(own),source_assets=ids,source_pins=sources,Original_definitions=census['definitions'],all209_callers_census=pin(O/'SOURCE-ALL27-MAPS-ALL4-FLATS-SHORELINE4-CALLER-CENSUS.json'),endpoints=endpoints,ordered_pairs=pairs,selected_selected_actual_join=census['own_own_cardinal_joins'],scope=dict(census_callers=209,cardinal_foreign_event_occurrences=37,representative_intact_windows=14,own_own_cardinal_joins=1,all9_campaign1_missions_represented=True,legal_foreign_neighbor_events=4,total_endpoints=18,scale_records=72,role_bodies=216,not_all197_distinct_cardinal_neighbor_signatures=True,no_World_or_timing_claim=True),baseline=dict(pack_root=str(B),manifest=pin(B/'hd.json'),provenance=pin(B/'provenance.json'),all_raw_identities=identity,finite_native=bindings),own_pack_root=str(ownpack),candidate=pin(A/'candidate-notes.json'),accepted_intrinsic_QA=qa,accepted_intrinsic_bank=bank,epoch=dict(receipt=pin(epochp),library=epoch['library'],serde_json=epoch['serde_json'],dependency_dir=str(R/'target/desktop-runtime/release/deps')),output_root=str(O/'actual-context18'))
save('FROZEN-SHORELINE4-GENUINE18-CURRENTG2-H5636-CONTRACT.json',contract);save('BEFORE-BOUNDED-COMPILATION-CONTEXT-INPUT-GUARDS.json',list(guards.values()));print(json.dumps(dict(scope=contract['scope'],source_assets=len(ids),foreign_registered=len(bindings),all_raw_paths=len(raws),full_baseline_frames=len(native),free_bytes=shutil.disk_usage(O).free),indent=2))
