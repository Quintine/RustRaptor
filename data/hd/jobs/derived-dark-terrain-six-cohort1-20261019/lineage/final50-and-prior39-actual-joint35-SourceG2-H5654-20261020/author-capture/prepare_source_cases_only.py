"""Read Original MAP/FLATS and bind exactly33 affected +two legal optional states."""
from pathlib import Path
import hashlib, json, struct
R=Path('/home/quintine/Projects/RaptorReplica/RustRaptor'); P=Path(__file__).resolve().parent
A=R/'.reference/hd-final50-independent-cross-cohort-consumed-input-audit-20261020-v1/FUTURE50-AND-FROZEN39-CROSS-COHORT-CONSUMED-INPUT-INTERSECTIONS-MINIMAL-ENDPOINTS.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def pin(p):return {'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size}
assert sha(A)=='5946f18e9cfe4415b43bbfd61e22e8eb4e9d6fe74596d7c62eb18c4d570f4efe'
d=json.loads(A.read_text()); idx={}; names={}
for line in (R/'data/INDEX').read_text().splitlines():
 if line.strip(): a,n,p=line.split();idx[int(a,16)]=R/'data'/p;names[Path(p).name]=int(a,16)
inputs=[pin(R/'data/INDEX'),pin(R/'data/misc/PALETTE_DAT')]; flats={}
for g in range(4):
 fa=names[f'FLATSG{g+1}_ITM'];raw=idx[fa].read_bytes();inputs.append(pin(idx[fa]));start=names[f'STARTG{g+1}TILES']+1
 flats[g]=[(start+k,start+dest,h,re,fa,k)for k,(dest,h,re)in enumerate(struct.iter_unpack('<ihh',raw))]
maps={}
for sector in range(1,4):
 for wave in range(1,10):
  ma=names[f'MAP{wave}G{sector}_MAP']; raw=idx[ma].read_bytes();assert len(raw)>=5412;inputs.append(pin(idx[ma])); rows=[]
  for k in range(1350):
   f,g=struct.unpack_from('<hh',raw,12+4*k);a,z,h,re,fa,j=flats[g][f]
   rows.append(dict(intact=f'{a:05x}',settled=None if a==z else f'{z:05x}',row=k//9,column=k%9,
    MAP_asset=f'{ma:05x}',MAP_byte_offset=12+4*k,flat=f,game=g,FLATS_asset=f'{fa:05x}',FLATS_byte_offset=j*8,
    health=0 if a==z else h,raw_health=h,reward=max(0,re),raw_reward=re))
  maps[f'base:sector_{sector}_wave_{wave}']=rows
endpoints=d['minimal_exact_endpoint_set_after_source_location_state_identity_dedup'];assert len(endpoints)==33
cases=[];sourceids=set();sourcechecks=padding=0
def make(e,optional=None):
 global sourcechecks,padding
 m=e['mission'];r0=e['window_row0'];c0=e['window_column0'];w=e['width_tiles'];h=e['height_tiles'];ids=list(e['ordered_source_ids']);definitions=[];changes=[]
 if optional:
  ch=optional['single_genuine_settled_change'];slot=ch['slot'];assert ids[slot]==ch['intact'];ids[slot]=ch['settled']
 for slot,a in enumerate(ids):
  y=r0+slot//w;x=c0+slot%w
  if not(0<=y<150 and 0<=x<9):assert a is None;definitions.append(None);padding+=1;continue
  q=maps[m][y*9+x];definitions.append(q);sourceids.add(a);sourcechecks+=1
  if a!=q['intact']:assert q['health']>0 and a==q['settled'];changes.append(q)
 if optional:
  assert len(changes)==1
  for k in ['row','column','intact','settled','raw_health','reward','game','flat','FLATS_asset','FLATS_byte_offset']:assert changes[0][k]==ch[k],k
  direction,a,b=optional['cardinal_pair'];pairs=[]
  for t,v in enumerate(ids):
   if direction=='right' and t%w+1<w:pairs.append((v,ids[t+1]))
   if direction=='down' and t//w+1<h:pairs.append((v,ids[t+w]))
  assert (a,b) in pairs
 cs={q['cohort']for q in e['required_by']};assert len(cs)==1;consumer=next(iter(cs))
 cases.append(dict(case_index=len(cases),label=f'all89-{consumer}-{m}-r{r0}c{c0}'+('-optional-oneactor'if optional else''),consumer_cohort=consumer,
  mission=m,window_row0=r0,window_column0=c0,width_tiles=w,height_tiles=h,ordered_source_ids=ids,
  authentic_original_definitions=definitions,settled_changes=changes,old_context_routes=e['required_by'],
  optional_true_legal_oneactor_pair=optional))
for e in endpoints:make(e)
optionals=d['only_unrepresented_new_new_cardinal_legal_variants_NOT_rendered'];assert len(optionals)==2
for optional in optionals:
 rep=optional['representative_existing_endpoint'];matches=[e for e in endpoints if all(e[k]==rep[k]for k in ['mission','window_row0','window_column0','width_tiles','height_tiles']) and not e['genuine_settled_changes']]
 assert len(matches)==1;make(matches[0],optional)
assert len(cases)==35
identities={(c['mission'],c['window_row0'],c['window_column0'],c['width_tiles'],c['height_tiles'],tuple(c['ordered_source_ids']))for c in cases};assert len(identities)==35
sourcepins={a:pin(idx[int(a,16)])for a in sorted(sourceids)}
for p in sourcepins.values():assert struct.unpack('<5i',Path(p['path']).read_bytes()[:20])==(1,1,0,32,32)
out={'status':'SOURCE_ONLY_EXACT35_LEGAL_ENDPOINTS_NO_RENDER','Root_authorized_actual_joint35':True,'source_audit':pin(A),
 'cases':cases,'actual_MAP_FLATS_real_slot_checks':sourcechecks,'literal_outside_MAP_None_slots':padding,
 'Original_INDEX_palette_all27MAP_all4FLATS':inputs,'finite_Source_sprite_pins':sourcepins,
 'expected':{'windows':35,'records':140,'roles':560,'source_assets':len(sourceids),'baseline_frames':5654,'overlay_frames':89},
 'optional_true_legal_oneactor_pairs_verified':[o['cardinal_pair']for o in optionals],
 'future50_targets':d['all50_targets'],'prior39_frozen_frame_binding':d['frozen39_frame_bindings_sha256'],
 'provider_refused_excluded':d['explicitly_excluded_provider_refused10'],
 'literal_epoch_policy':'Capture immutable original5654bank control. Proposedall89 header is overlay89, not installed5743 projection. Consumer cohort role uses final selected material freshly on5654; original cohort saved epoch/old10521 art remain historical, never relabeled.',
 'runtime_compile_QA_World_generation_cleanup_calls':0}
p=P/'SOURCE-ONLY-EXACT35-ORIGINAL-ENDPOINTS-AND-OPTIONAL-LEGAL-STATE-VERIFICATION.json'
with p.open('x')as f:json.dump(out,f,indent=2);f.write('\n')
print(json.dumps({'output':str(p),'sha256':sha(p),'source_assets':len(sourceids),'actual_Source_slot_checks':sourcechecks,'outside_MAP_None':padding,'windows':len(cases)},indent=2))
