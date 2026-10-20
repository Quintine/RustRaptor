from pathlib import Path
import json,hashlib,struct,os,shutil
R=Path('/home/quintine/Projects/RaptorReplica/RustRaptor');P=Path(__file__).resolve().parent;A=R/'.reference/hd-followon10370-302e1-30380-30465-40372-Original-primary-author-20261019-v1';selected=['10370','302e1','30465','40372'];used=set(selected)
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
assert len(census)==58
censuspin=save('FRESH-ALL27MAP-4FLATS-58POSITIONS-58ROLES.json',dict(status='SOURCE_ONLY_ALL27MAPS_NO_WORLD',maps27=27,layout_cells=36450,spawn_records=spawn_count,selected=selected,callers=census,inputs=inputs,scope='58 actual static MAP positions:55 for10370 plus3 unique singleton callers. Finite6 representative windows, not all58positions rendered.'))
cases=[];ordered=[]
def case(m,y0,x0,h,w,label,changes=[]):
 defs=[];ids=[]
 for yy in range(h):
  for xx in range(w):v=maps[m][(y0+yy)*9+x0+xx];defs.append(v);ids.append(v['intact'])
 assert changes==[], 'static selected tiles forbid fabricated destruction'
 value=dict(case_index=len(cases),mission=m,label=label,window_row0=y0,window_column0=x0,height_tiles=h,width_tiles=w,ordered_source_ids=ids,authentic_original_definitions=defs,settled_changes=changes);cases.append(value);return value['case_index']
centers=[('base:sector_1_wave_1',36,8,'10370-edge-tree'),('base:sector_1_wave_2',28,6,'10370-interior-tree'),('base:sector_2_wave_6',77,8,'10370-cross-sector-edge'),('base:sector_3_wave_3',6,4,'302e1-static-colored-floor'),('base:sector_3_wave_2',64,2,'30465-static-remains-greens'),('base:sector_3_wave_6',97,4,'40372-static-violet-path')]
for m,y,x,label in centers:case(m,y-1,min(max(x-1,0),6),3,3,f'{m}-r{y}c{x}-{label}')
assert all(v['health']==0 and v['settled']is None for c in cases for v in c['authentic_original_definitions']if v['intact']in used)
sourceids=sorted(set(a for c in cases for a in c['ordered_source_ids']));assert len(cases)==6
base=R/'data/hd';captured_manifest=(R/'data/hd/hd.json').read_bytes();hd=json.loads(captured_manifest);H=sum(len(s['frames'])for s in hd['sequences']);(P/'SNAPSHOT-ACTUAL-H-MANIFEST.json').write_bytes(captured_manifest);native={f'{s["base_asset"]+f["frame"]:05x}':dict(frame=f,sequence_header={k:v for k,v in s.items()if k!='frames'})for s in hd['sequences']for f in s['frames']};assert len(native)==H and not used&set(native)
carrier=P/'finite-actual-H-baseline';carrier.mkdir();(carrier/'hd.json').write_bytes((P/'SNAPSHOT-ACTUAL-H-MANIFEST.json').read_bytes());manifestpin=pin(carrier/'hd.json');foreign=sorted(set(sourceids)&set(native));fallback=sorted(set(sourceids)-set(native)-used)
# All raw routes are eligibility hardlinks only. Actual composition and hashing binds finite consumed sources only; no 8GB byte copy.
seen=set();eligible_logical_bytes=0
for aid,n in native.items():
 rel=n['frame']['file'];src=base/rel;dst=carrier/rel
 if rel in seen:continue
 seen.add(rel);dst.parent.mkdir(parents=True,exist_ok=True);os.link(src,dst);eligible_logical_bytes+=src.stat().st_size
proposal=P/'proposal-selected4';proposal.mkdir();sequences=[];banks={};aliases={}
for aid in selected:
 folder=A/aid/('focused-62-Source-outline-successor'if aid=='30380'else'');pack=folder/('final-reviewed-panel-outline-pack'if aid=='30380'else'final-reviewed-landmark-fine-pack');cp=pack/'candidate.json';candidate=json.loads(cp.read_text());qa=folder/'actual-once-final-current-SourceG2/runtime-qa.json';bank=qa.parent/'actual-indexed-source-and-scales.json'
 assert json.loads(qa.read_text())['diagnostics']==[]
 for seq in candidate['sequences']:
  seq=json.loads(json.dumps(seq));aid=f'{seq["base_asset"]:05x}';frame=seq['frames'][0];raw=pack/frame['file'];alias=frame['file'];assert alias not in aliases;aliases[alias]=link(raw,proposal/alias);sequences.append(seq);banks[aid]=pin(bank)
(proposal/'hd.json').write_text(json.dumps(dict(format_version=1,name='Private followon4 genuine Original-primary materials',sequences=sequences),indent=2)+'\n');newnative={f'{s["base_asset"]:05x}':dict(frame=s['frames'][0],sequence_header={k:v for k,v in s.items()if k!='frames'})for s in sequences};bindings={}
for aid in sourceids:
 b=dict(source=pin(cat[int(aid,16)]),native=None);assert struct.unpack('<5i',cat[int(aid,16)].read_bytes()[:20])==(1,1,0,32,32)
 if aid in used:b['native']=dict(**newnative[aid],raw=pin(proposal/newnative[aid]['frame']['file']))
 elif aid in native:b['native']=dict(**native[aid],raw=pin(carrier/native[aid]['frame']['file']))
 bindings[aid]=b
bindingpin=save('FINITE-ACTUAL-H-CONSUMED-SOURCE-NATIVE-RAW-BINDINGS.json',dict(bindings=bindings,registered_foreign=foreign,used_selected=sorted(used),catalogue_unused=[],Original_fallbacks=fallback,actual_baseline_at_capture=pin(P/'SNAPSHOT-ACTUAL-H-MANIFEST.json'),immutable_carrier_manifest=manifestpin,all4_proposed_manifest=pin(proposal/'hd.json'),actual_accepted_banks=banks,eligibility_hardlinks=dict(unique_raw_paths=len(seen),logical_bytes=eligible_logical_bytes,copied_raw_bytes=0),no_full_raw_copy=True))
expected=dict(windows=len(cases),records=len(cases)*4,roles=len(cases)*12,Source=len(sourceids),foreign=len(foreign),own=4,fallback=len(fallback),components=(len(foreign)+len(used))*4,stages=16,baseline_count=H,proposed_count=4,callers=58,maps=27,ordered_events=len(ordered))
recipe=dict(status='SEALED_CURRENT_G2_FOLLOWON4_GENUINE6',Root_GO=True,data_root=str(R/'data'),baseline_root=str(carrier),own_root=str(proposal),selected_proposals=selected,selected=selected,catalogue_unused=[],Original_fallbacks=fallback,cases=cases,ordered_views=ordered,accepted_own_banks=banks,finite_bindings=bindingpin,Source_census=censuspin,expected=expected,limits=['Literal actual H manifest recorded in expected.baseline_count; later additions do not relabel these pixels.','Six finite real3x3 windows, all4staticselectedroles, no World or fabricated destruction.','58actualMAPpositions58selectedroles censused; only6representativewindows rendered.','Zero fullrawtreecopy: all baseline raw paths are eligibilityhardlinks; only finiteconsumed artwork is decoded/pinned.','Predeclared selectedordinarycue and reserved Sourceowner cells remain OriginalNx afterjoins withzeroHDcredit.','Sourcepanel outlines/blackvoid, floorstrip,greens,violetpath preserved; foreignmixedmaterial seams requirephysicalreview.'])
recipepin=save('SEALED-FOLLOWON4-GENUINE6-CURRENTG2-RECIPE.json',recipe);save('CLOSED-FINITE-PREFLIGHT-ONE-COMPILE-ONE-CONSTRUCTOR-AUTHORITY.json',dict(status='SEALED_FINITE_SOURCEG2_CONTEXT_PREFLIGHT',Root_authority='Parent Root explicitly assigned private followon4 authentic contexts after authorQUAL, using existing reviewed static compositor, one compile/composition, no World/fullbuild/art/cleanup/newQA/canonical.',recipe=recipepin,expected=expected,eligibility_only_hardlinks_no_byte_copy=True,free_bytes=shutil.disk_usage(P).free))
print(json.dumps(expected,indent=2));print('fallback',fallback,'foreign',foreign)
