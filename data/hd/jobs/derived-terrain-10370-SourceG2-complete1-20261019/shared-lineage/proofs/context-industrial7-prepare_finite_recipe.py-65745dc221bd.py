from pathlib import Path
import json,hashlib,struct,os,shutil
R=Path('/home/quintine/Projects/RaptorReplica/RustRaptor');P=Path(__file__).resolve().parent;A=R/'.reference/hd-industrial20593-205ff-Original-primary-author-20261019-v1';selected=['20593','20594','2059a','2059b','2059c','205fe','205ff'];used=set(selected)
assert shutil.disk_usage(P).free>1800000000+150000000
pin=lambda p:dict(path=str(Path(p).resolve()),sha256=hashlib.sha256(Path(p).read_bytes()).hexdigest(),size=Path(p).stat().st_size,mtime_ns=Path(p).stat().st_mtime_ns,mode=Path(p).stat().st_mode)
def save(n,v):p=P/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2)+'\n');return pin(p)
def link(src,dst):
 dst.parent.mkdir(parents=True,exist_ok=True)
 if not dst.exists():os.link(src,dst)
 assert pin(src)['sha256']==pin(dst)['sha256'];return pin(dst)
cat={};names={}
for line in (R/'data/INDEX').read_text().splitlines():a,n,f=line.split();cat[int(a,16)]=R/'data'/f;names[Path(f).name]=int(a,16)
flats={};inputs=[pin(R/'data/INDEX'),pin(R/'data/misc/PALETTE_DAT')]
for g in range(4):
 aid=names[f'FLATSG{g+1}_ITM'];raw=cat[aid].read_bytes();inputs.append(pin(cat[aid]));start=names[f'STARTG{g+1}TILES']+1;flats[g]=[(start+k,start+d,h,re,aid,k)for k,(d,h,re)in enumerate(struct.iter_unpack('<ihh',raw))]
maps={};census=[];spawn_count=0
for sec in range(1,4):
 for wave in range(1,10):
  mission=f'base:sector_{sec}_wave_{wave}';aid=names[f'MAP{wave}G{sec}_MAP'];raw=cat[aid].read_bytes();inputs.append(pin(cat[aid]));spawn_count+=struct.unpack_from('<i',raw,8)[0];rows=[]
  for j in range(1350):
   fi,g=struct.unpack_from('<hh',raw,12+j*4);a,d,h,re,fa,k=flats[g][fi];v=dict(intact=f'{a:05x}',settled=None if a==d else f'{d:05x}',row=j//9,column=j%9,MAP_asset=f'{aid:05x}',MAP_byte_offset=12+4*j,flat=fi,game=g,FLATS_asset=f'{fa:05x}',FLATS_byte_offset=k*8,health=0 if a==d else max(h,0),raw_health=h,reward=max(re,0),raw_reward=re);rows.append(v)
   if v['intact']in selected or v['settled']in selected:census.append(dict(mission=mission,Source_role='intact'if v['intact']in selected else'legal_settled',**v))
  maps[mission]=rows
assert len(census)==43
censuspin=save('FRESH-ALL27MAP-4FLATS-43POSITIONS-45ROLES.json',dict(status='SOURCE_ONLY_ALL27MAPS_NO_WORLD',maps27=27,layout_cells=36450,spawn_records=spawn_count,selected=selected,callers=census,inputs=inputs,scope='43 actual MAP positions,45 selected roles:41 farm direct+2earth direct+2legal2059a-to2059c. Finite10 representative windows below, not all43positions or45roles rendered.'))
cases=[];ordered=[]
def case(m,y0,x0,h,w,label,changes=[]):
 defs=[];ids=[]
 for yy in range(h):
  for xx in range(w):v=maps[m][(y0+yy)*9+x0+xx];defs.append(v);ids.append(v['intact'])
 for v in changes:
  slot=(v['row']-y0)*w+v['column']-x0;assert ids[slot]==v['intact']and v['intact']=='2059a'and v['settled']=='2059c';ids[slot]=v['settled']
 value=dict(case_index=len(cases),mission=m,label=label,window_row0=y0,window_column0=x0,height_tiles=h,width_tiles=w,ordered_source_ids=ids,authentic_original_definitions=defs,settled_changes=changes);cases.append(value);return value['case_index']
soil5=next(v for v in census if v['mission']=='base:sector_2_wave_5'and v['intact']=='20593'and 0<v['column']<8)
centers=[('base:sector_2_wave_2',37,1,'field-pair'),('base:sector_2_wave_5',soil5['row'],soil5['column'],'field-second-MAP'),('base:sector_2_wave_2',108,2,'gray-machinery'),('base:sector_2_wave_2',109,2,'red-machinery'),('base:sector_2_wave_5',110,6,'gray-machinery-second-MAP'),('base:sector_2_wave_5',111,6,'red-machinery-second-MAP'),('base:sector_2_wave_9',17,3,'earth-left'),('base:sector_2_wave_9',17,4,'earth-right')]
befores={}
for m,y,x,label in centers:befores[m,y,x]=case(m,y-1,x-1,3,3,f'{m}-r{y}c{x}-{label}')
for m,y,x in [('base:sector_2_wave_2',109,2),('base:sector_2_wave_5',111,6)]:
 actor=maps[m][y*9+x];assert actor['health']==15 and actor['reward']==50 and actor['intact']=='2059a'and actor['settled']=='2059c';end=case(m,y-1,x-1,3,3,f'{m}-r{y}c{x}-genuine-2059a-to2059c-settled',[actor]);ordered.append(dict(kind='legal_Original_one_actor_intact_to_settled_not_natural_timing',before=befores[m,y,x],settled=end,changed_slot=4,Original_actor=actor))
sourceids=sorted(set(a for c in cases for a in c['ordered_source_ids']));assert len(cases)==10
base=R/'data/hd';hd=json.loads((R/'data/hd/hd.json').read_text());(P/'SNAPSHOT-H5647-MANIFEST.json').write_bytes((R/'data/hd/hd.json').read_bytes());native={f'{s["base_asset"]+f["frame"]:05x}':dict(frame=f,sequence_header={k:v for k,v in s.items()if k!='frames'})for s in hd['sequences']for f in s['frames']};assert len(native)==5647 and not used&set(native)
carrier=P/'finite-H5647-baseline';carrier.mkdir();(carrier/'hd.json').write_bytes((P/'SNAPSHOT-H5647-MANIFEST.json').read_bytes());manifestpin=pin(carrier/'hd.json');foreign=sorted(set(sourceids)&set(native));fallback=sorted(set(sourceids)-set(native)-used)
# All raw routes are eligibility hardlinks only. Actual composition and hashing binds finite consumed sources only; no 8GB byte copy.
seen=set();eligible_logical_bytes=0
for aid,n in native.items():
 rel=n['frame']['file'];src=base/rel;dst=carrier/rel
 if rel in seen:continue
 seen.add(rel);dst.parent.mkdir(parents=True,exist_ok=True);os.link(src,dst);eligible_logical_bytes+=src.stat().st_size
proposal=P/'proposal-selected7';proposal.mkdir();sequences=[];banks={};aliases={}
for cohort in ['farm5','earth2']:
 pack=A/cohort/'final-reviewed-fine-pack';cp=pack/'candidate.json';candidate=json.loads(cp.read_text());qa=A/cohort/'actual-once-final-current-SourceG2/runtime-qa.json';bank=qa.parent/'actual-indexed-source-and-scales.json'
 assert json.loads(qa.read_text())['diagnostics']==[]
 for seq in candidate['sequences']:
  seq=json.loads(json.dumps(seq));aid=f'{seq["base_asset"]:05x}';frame=seq['frames'][0];raw=pack/frame['file'];alias=frame['file'];assert alias not in aliases;aliases[alias]=link(raw,proposal/alias);sequences.append(seq);banks[aid]=pin(bank)
(proposal/'hd.json').write_text(json.dumps(dict(format_version=1,name='Private industrial7 genuine Original-primary materials',sequences=sequences),indent=2)+'\n');newnative={f'{s["base_asset"]:05x}':dict(frame=s['frames'][0],sequence_header={k:v for k,v in s.items()if k!='frames'})for s in sequences};bindings={}
for aid in sourceids:
 b=dict(source=pin(cat[int(aid,16)]),native=None);assert struct.unpack('<5i',cat[int(aid,16)].read_bytes()[:20])==(1,1,0,32,32)
 if aid in used:b['native']=dict(**newnative[aid],raw=pin(proposal/newnative[aid]['frame']['file']))
 elif aid in native:b['native']=dict(**native[aid],raw=pin(carrier/native[aid]['frame']['file']))
 bindings[aid]=b
bindingpin=save('FINITE-H5647-CONSUMED-SOURCE-NATIVE-RAW-BINDINGS.json',dict(bindings=bindings,registered_foreign=foreign,used_selected=sorted(used),catalogue_unused=[],Original_fallbacks=fallback,actual_baseline_at_capture=pin(P/'SNAPSHOT-H5647-MANIFEST.json'),immutable_carrier_manifest=manifestpin,all7_proposed_manifest=pin(proposal/'hd.json'),actual_accepted_banks=banks,eligibility_hardlinks=dict(unique_raw_paths=len(seen),logical_bytes=eligible_logical_bytes,copied_raw_bytes=0),no_full_raw_copy=True))
expected=dict(windows=len(cases),records=len(cases)*4,roles=len(cases)*12,Source=len(sourceids),foreign=len(foreign),own=7,fallback=len(fallback),components=(len(foreign)+3)*4,stages=28,baseline_count=5647,proposed_count=7,callers=43,maps=27,ordered_events=len(ordered))
recipe=dict(status='SEALED_CURRENT_G2_H5647_INDUSTRIAL7_GENUINE10',Root_GO=True,data_root=str(R/'data'),baseline_root=str(carrier),own_root=str(proposal),selected_proposals=selected,selected=selected,catalogue_unused=[],Original_fallbacks=fallback,cases=cases,ordered_views=ordered,accepted_own_banks=banks,finite_bindings=bindingpin,Source_census=censuspin,expected=expected,limits=['Literal captured H5647 manifest; later published additions do not relabel these pixels.','Ten finite representative real3x3 windows, all7selectedroles, two legal one-actor2059a-to2059c static settlements, no World or natural destruction timing claim.','43actualMAPpositions45selectedroles censused; only bounded10windows rendered, not all positions/signatures.','Zero fullrawtreecopy: all baseline raw paths are eligibilityhardlinks; only finiteconsumed artwork is decoded/pinned.','All11retainedSourceowners2059c remain OriginalNx after joins and receive zeroHDcredit.','Earth/furrow/metal Source geometry and green blockiness remain; mixed neighbor texture/brightness seams require physical review.'])
recipepin=save('SEALED-INDUSTRIAL7-GENUINE10-CURRENTG2-H5647-RECIPE.json',recipe);save('CLOSED-FINITE-PREFLIGHT-ONE-COMPILE-ONE-CONSTRUCTOR-AUTHORITY.json',dict(status='SEALED_FINITE_SOURCEG2_CONTEXT_PREFLIGHT',Root_authority='Parent Root explicitly assigned private industrial7 authentic contexts after authorQUAL, using existing reviewed static compositor, one compile/composition, no World/fullbuild/art/cleanup/newQA/canonical.',recipe=recipepin,expected=expected,eligibility_only_hardlinks_no_byte_copy=True,free_bytes=shutil.disk_usage(P).free))
print(json.dumps(expected,indent=2));print('fallback',fallback,'foreign',foreign)
