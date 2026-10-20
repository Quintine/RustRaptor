from pathlib import Path
import json,hashlib,os,shutil,struct
R=Path('/home/quintine/Projects/RaptorReplica/RustRaptor');P=Path(__file__).resolve().parent;SRC=R/'.reference/hd-next39-private-source-normalization-after5654-20261019-v1';AUD=R/'.reference/hd-next39-independent-cross-cohort-consumed-input-audit-20261020-v1/ALL39-CROSS-COHORT-CONSUMED-INPUT-INTERSECTIONS-AND-MINIMAL-JOINT-ENDPOINTS.json';sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def pin(p):p=Path(p);st=p.stat();return {'path':str(p),'sha256':sha(p),'size':st.st_size,'mtime_ns':st.st_mtime_ns,'mode':st.st_mode}
def save(n,d):p=P/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,indent=2)+'\n');return pin(p)
assert shutil.disk_usage(P).free>1932735284+150000000
freeze=SRC/'JOINT39-FROZEN-RENDERER-FRAME-MAP-AND-RAW-PINS.json';assert sha(freeze)=='a8f2b5dd427360904825bfc89759351c02783668024b4a1db0ee1dddb3f8ff24';F=json.load(open(freeze));assert sha(F['candidate']['path'])==F['candidate']['sha256'];A=json.load(open(AUD));assert sha(AUD)=='d074a0b6e264567d7846316abc42facba1cca066ad34e2ccca32b06963c7b956';allown=set(A['all39_targets']);assert len(allown)==39
base=R/'data/hd';assert sha(base/'hd.json')==F['baseline_HD']['sha256'];hd=json.load(open(base/'hd.json'));H=sum(len(s['frames'])for s in hd['sequences']);assert H==5654
native={f'{s["base_asset"]+f["frame"]:05x}':{'frame':f,'sequence_header':{k:v for k,v in s.items()if k!='frames'}}for s in hd['sequences']for f in s['frames']};assert not allown&set(native)
carrier=P/'immutable-H5654-baseline';carrier.mkdir();(carrier/'hd.json').write_bytes((base/'hd.json').read_bytes());linked={};logicalbytes=0
for n in native.values():
 rel=n['frame']['file']
 if rel in linked:continue
 src=base/rel;dst=carrier/rel;dst.parent.mkdir(parents=True,exist_ok=True);os.link(src,dst);linked[rel]={'dev':dst.stat().st_dev,'ino':dst.stat().st_ino,'size':dst.stat().st_size};logicalbytes+=src.stat().st_size
proposal=P/'frozen39-proposal';proposal.mkdir();pl=json.load(open(F['candidate']['path']));(proposal/'hd.json').write_text(json.dumps(pl,indent=2)+'\n')
for rel,raw in F['raw_files'].items():
 src=Path(raw['source']);assert sha(src)==raw['sha256'];dst=proposal/rel;dst.parent.mkdir(parents=True,exist_ok=True);os.link(src,dst);assert sha(dst)==raw['sha256']
newnative={f'{s["base_asset"]:05x}':{'frame':s['frames'][0],'sequence_header':{k:v for k,v in s.items()if k!='frames'}}for s in pl['sequences']};assert set(newnative)==allown
idx={};names={}
for l in(R/'data/INDEX').read_text().splitlines():
 if l.strip():a,n,p=l.split();idx[int(a,16)]=R/'data'/p;names[Path(p).name]=int(a,16)
flats={};inputs=[pin(R/'data/INDEX'),pin(R/'data/misc/PALETTE_DAT')]
for game in range(4):
 fa=names[f'FLATSG{game+1}_ITM'];raw=idx[fa].read_bytes();inputs.append(pin(idx[fa]));start=names[f'STARTG{game+1}TILES']+1;flats[game]=[(start+k,start+d,h,re,fa,k)for k,(d,h,re)in enumerate(struct.iter_unpack('<ihh',raw))]
maps={}
for sec in range(1,4):
 for wave in range(1,10):
  ma=names[f'MAP{wave}G{sec}_MAP'];raw=idx[ma].read_bytes();inputs.append(pin(idx[ma]));rows=[]
  for k in range(1350):
   flat,g=struct.unpack_from('<hh',raw,12+k*4);a,d,h,re,fa,j=flats[g][flat];rows.append({'intact':f'{a:05x}','settled':None if a==d else f'{d:05x}','row':k//9,'column':k%9,'MAP_asset':f'{ma:05x}','MAP_byte_offset':12+4*k,'flat':flat,'game':g,'FLATS_asset':f'{fa:05x}','FLATS_byte_offset':j*8,'health':0 if a==d else h,'raw_health':h,'reward':max(re,0),'raw_reward':re})
  maps[f'base:sector_{sec}_wave_{wave}']=rows
cases=[];sourceids=set()
for i,e in enumerate(A['minimal_exact_endpoint_set_after_identity_dedup']):
 m=e['mission'];r0=e['window_row0'];c0=e['window_column0'];w=e['width_tiles'];h=e['height_tiles'];defs=[];ids=[];changes=[]
 for slot,display in enumerate(e['ordered_source_ids']):
  y=r0+slot//w;x=c0+slot%w
  if not(0<=y<150 and 0<=x<9):assert display is None;defs.append(None);ids.append(None);continue
  d=maps[m][y*9+x];defs.append(d);ids.append(display);sourceids.add(display)
  if display!=d['intact']:assert display==d['settled']and d['health']>0;changes.append(d)
 consumer={x['cohort']for x in e['required_by']};assert len(consumer)==1;consumer=next(iter(consumer));cohortown=sorted(a for a,c in A['all39_targets'].items()if c==consumer)
 cases.append({'case_index':i,'label':f'joint39-{consumer}-{m}-r{r0}c{c0}','consumer_cohort':consumer,'cohort_selected':cohortown,'mission':m,'window_row0':r0,'window_column0':c0,'height_tiles':h,'width_tiles':w,'ordered_source_ids':ids,'authentic_original_definitions':defs,'settled_changes':changes,'old_context_routes':e['required_by']})
assert len(cases)==11
foreign=sorted(sourceids&set(native));ownused=sorted(sourceids&allown);fallback=sorted(sourceids-set(native)-allown);bindings={}
for aid in sorted(sourceids):
 src=idx[int(aid,16)];assert struct.unpack('<5i',src.read_bytes()[:20])==(1,1,0,32,32);b={'source':pin(src),'native':None}
 if aid in allown:b['native']={**newnative[aid],'raw':pin(proposal/newnative[aid]['frame']['file'])}
 elif aid in native:b['native']={**native[aid],'raw':pin(carrier/native[aid]['frame']['file'])}
 bindings[aid]=b
bp=save('FINITE-JOINT11-CONSUMED-SOURCE-NATIVE-RAW-BINDINGS.json',{'bindings':bindings,'old5654_foreign':foreign,'new39_consumed':ownused,'Original_fallbacks':fallback,'old5654_manifest':pin(carrier/'hd.json'),'frozen39_proposal':pin(proposal/'hd.json'),'all_baseline_eligibility_paths_hardlinked':len(linked),'logical_eligibility_bytes_not_copied':logicalbytes,'copied_raw_bytes':0})
sourceqa=R/'.reference/hd-followon10370-302e1-30380-30465-40372-Original-primary-author-20261019-v1/10370/actual-once-final-current-SourceG2/runtime-qa.json';pins18=json.load(open(sourceqa))['actual_sourceG2_source18_sha256'];assert len(pins18)==18
for rel,digest in pins18.items():assert sha(R/rel)==digest,(rel,sha(R/rel),digest)
sp=save('PRECOMPILE-EXACT-SOURCE18-AND-FROZEN-INPUT-VERIFICATION.json',{'Source18':pins18,'sourceqa':pin(sourceqa),'palette':pin(R/'data/misc/PALETTE_DAT'),'Original_MAP_FLATS_INDEX_pins':inputs,'publisher39freeze':pin(freeze),'source_audit':pin(AUD),'baseline5654':pin(carrier/'hd.json')})
expected={'windows':11,'records':44,'roles':176,'Source':len(sourceids),'foreign':len(foreign),'own_used':len(ownused),'fallback':len(fallback),'components':(len(foreign)+len(ownused))*4,'stages':len(ownused)*4,'baseline_count':5654,'proposed_count':39,'maps':27,'own_source_callers':None}
recipe={'status':'SEALED_JOINT39_GENUINE11_CURRENT_SOURCEG2_H5654','Root_GO':True,'data_root':str(R/'data'),'baseline_root':str(carrier),'own_root':str(proposal),'selected_proposals':sorted(allown),'selected':ownused,'cases':cases,'finite_bindings':bp,'Source18_verification':sp,'publisher39freeze':pin(freeze),'expected':expected,'limits':['Literal currentH5654 base plus exact39 frozen renderer bindings,7consumed new definitions. All39registered privately for correct eligibility, only finite case-consumed artwork decoded.','Four roles per endpoint: globalOriginalNx, H5654only, H5654+originalconsumercohort, H5654+all39. The old consumer role is freshly composed currentH5654 from exactownmaterial, not relabeled oldH5636/H5647 saved pixels.','Eleven real3x3 windows/states; outside-mapNone padding is preserved. Genuine Original settledactors only, no World/natural timing/fullmission claim.','Source-retained ordinary/functional geometry remains globalOriginalNx after all joins and earns zero HD credit.','No pasted prior standalone/component images; all layers read through actual frozenSourceG2 HdAssets/TerrainHd once per consumedasset/scale.']}
rp=save('SEALED-JOINT39-GENUINE11-SOURCEG2-H5654-RECIPE.json',recipe);save('ROOT-BOUNDED-JOINT11-AUTHORITY-AND-COUNTS.json',{'Root_explicit_authority':'Proceed bounded actual joint39 eleven endpointsnative1–4; reuseSourceG2staticTerrainHd,noWorld/enginebuild/newintrinsicQA; hardlinkedoldcontextassets; inspectnewinteractingcontributors andafterjoinretention; ridge_pair differentafterward.','recipe':rp,'expected':expected,'actual_compile_constructor_calls_so_far':0,'free_bytes':shutil.disk_usage(P).free});print(json.dumps(expected,indent=2));print('newconsumed',ownused,'fallback',fallback)
