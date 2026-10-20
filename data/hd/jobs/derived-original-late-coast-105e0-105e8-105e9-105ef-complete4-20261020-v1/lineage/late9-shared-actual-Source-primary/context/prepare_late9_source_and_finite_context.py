from pathlib import Path
import json,hashlib,struct,os,shutil
O=Path(__file__).resolve().parent; R=O.parent.parent
A=R/'.reference/hd-firstcampaign105e0-105ef-and105f3-Original-primary-author-20261019-v1'
S=R/'.reference/hd-stag-firstcampaign5-SourceG2-H5654-genuine-context-20261019-v1'
own=set('105e0 105e6 105e7 105e8 105e9 105eb 105ed 105ef 105f3'.split()); guards={}
def pin(p):
 p=Path(p).absolute();st=p.stat();return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),size=st.st_size,mtime_ns=st.st_mtime_ns)
def take(p):
 p=Path(p);b=p.read_bytes();q=pin(p);assert hashlib.sha256(b).hexdigest()==q['sha256'];guards[str(p.absolute())]=q;return b
def save(n,v):
 p=O/n;assert not p.exists();p.write_text(json.dumps(v,indent=2)+'\n');return pin(p)
assert shutil.disk_usage(O).free>1_800_000_000
catalog={};names={}
for line in take(R/'data/INDEX').decode().splitlines():
 a,n,p=line.split();catalog[int(a,16)]=R/'data'/p;names[Path(p).name]=int(a,16)
flats={};definitions={}
for g in range(4):
 fa=names[f'FLATSG{g+1}_ITM'];b=take(catalog[fa]);start=names[f'STARTG{g+1}TILES']+1;rows=[]
 for k in range(len(b)//8):
  destroyed,h,re=struct.unpack_from('<ihh',b,k*8)
  d=dict(asset=f'{start+k:05x}',settled=None if destroyed==k else f'{start+destroyed:05x}',raw_health=0 if destroyed==k else h,reward=max(0,re),FLATS_record=k,FLATS_asset=f'{fa:05x}',FLATS_byte_offset=k*8,game=g)
  # Keep true on-disk health/reward for the adapter's independent binary check.
  d['raw_health']=h;d['reward']=re
  rows.append(d)
  if d['asset'] in own or d['settled'] in own:definitions[d['asset']]=d
 flats[g]=rows
maps={};callers=[]
for sec in range(1,4):
 for w in range(1,10):
  b=take(catalog[names[f'MAP{w}G{sec}_MAP']]);m=f'base:sector_{sec}_wave_{w}';rows=[]
  for k in range(1350):
   f,g=struct.unpack_from('<hh',b,12+k*4);d=flats[g][f];rows.append(d)
   if d['asset'] in own or d['settled'] in own:callers.append(dict(mission=m,row=k//9,column=k%9,definition=d))
  maps[m]=rows
roles={a:{role:sum(t[key]==a for rows in maps.values() for t in rows) for role,key in [('direct','asset'),('settled','settled')]} for a in sorted(own)}
need={(a,role)for a,counts in roles.items()for role,n in counts.items()if n}
assert all(any(roles[a].values())for a in own),'unused pictures must receive honest catalog-only treatment, never manufactured context'
def window(p):
 y0=max(0,min(147,p['row']-1));x0=max(0,min(6,p['column']-1));ds=[maps[p['mission']][(y0+i//3)*9+x0+i%3]for i in range(9)];return y0,x0,ds
possible=[]
for p in callers:
 y,x,ds=window(p);cover={(d['asset'],'direct')for d in ds if d['asset']in own}
 if p['definition']['settled']in own:
  assert p['definition']['raw_health']>0;cover.add((p['definition']['settled'],'settled'))
 possible.append((p,cover))
chosen=[];left=set(need)
while left:
 p,cov=max(possible,key=lambda z:(len(z[1]&left),len(z[1]),-z[0]['row'],-z[0]['column'],z[0]['mission']))
 assert cov&left;chosen.append(p);left-=cov
cases=[];pairs=[];seen={}
def endpoint(p,settled=False):
 y0,x0,ds=window(p);ids=[d['asset']for d in ds];event=None
 if settled:
  d=p['definition'];assert d['raw_health']>0 and d['settled'];slot=(p['row']-y0)*3+p['column']-x0;assert ids[slot]==d['asset'];ids[slot]=d['settled'];event=dict(row=p['row'],column=p['column'],slot=slot,definition=d)
 key=(p['mission'],y0,x0,tuple(ids))
 if key in seen:return seen[key]
 i=len(cases);seen[key]=i;cases.append(dict(case_index=i,mission=p['mission'],window_row0=y0,window_column0=x0,ordered_source_ids=ids,authentic_original_definitions=ds,settled_event=event));return i
def pair(p):
 b=endpoint(p);a=endpoint(p,True)
 if any(x['before']==b and x['after']==a for x in pairs):return
 changed=[i for i in range(9)if cases[b]['ordered_source_ids'][i]!=cases[a]['ordered_source_ids'][i]];assert len(changed)==1
 pairs.append(dict(before=b,after=a,change={'slot':changed[0],'definition':p['definition']},World=0))
for p in chosen:
 endpoint(p)
 if p['definition']['settled']in own:pair(p)
covered_direct_events={p['change']['definition']['asset']for p in pairs}
for aid in sorted(own):
 ps=[p for p in callers if p['definition']['asset']==aid and p['definition']['raw_health']>0 and p['definition']['settled']]
 if ps and aid not in covered_direct_events:pair(ps[0])
covered=set()
for c in cases:
 for i,aid in enumerate(c['ordered_source_ids']):
  if aid in own:covered.add((aid,'settled'if c['settled_event']and c['settled_event']['slot']==i else'direct'))
assert need<=covered
census=save('ALL27MAP-4FLATS-COMPLETE-REAL-LATE9-CALLER-CENSUS.json',dict(selected=sorted(own),definitions=definitions,callers=callers,roles=roles,total_map_cells=36450,all27_maps=True,all4_FLATS=True,input_pins=list(guards.values())))
hist=json.loads(take(S/'FROZEN-FIRSTCAMPAIGN5-G2-LITERAL-BASELINE-GENUINE-SOURCE-CONTRACT.json'));baseline=hist['baseline'];B=Path(baseline['packroot']);assert pin(B/'hd.json')['sha256']=='104dc8f0d154f6a3e8edf6c72283205cb1f323daf8c225a8ca3a56680ac87f5b'
hd=json.loads(take(B/'hd.json'));native={};raws=json.loads(take(Path(baseline['hardlink_identity']['path'])))
assert sum(len(s['frames'])for s in hd['sequences'])==5654 and raws['unique_raw_dependencies']==3088
for q in raws['raws'].values():
 st=Path(q['snapshot']).stat();assert(st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns)==(q['dev'],q['inode'],q['size'],q['mtime_ns'])
for s in hd['sequences']:
 for f in s['frames']:native[f'{s["base_asset"]+f["frame"]:05x}']={'frame':f,'full_sequence':s}
assert own.isdisjoint(native)
all_ids=sorted({i for c in cases for i in c['ordered_source_ids']});sourcepins=[];finite=[]
for aid in all_ids:
 p=catalog[int(aid,16)];b=take(p);assert len(b)==1044 and struct.unpack('<5i',b[:20])==(1,1,0,32,32);sourcepins.append(dict(asset=aid,source=pin(p)))
 if aid in native:
  p=B/native[aid]['frame']['file'];take(p);finite.append(dict(asset=aid,**native[aid],raw=pin(p)))
P=O/'combined-private-own9-pack';P.mkdir();sequences=[];banks=[];routes=[]
for group in ['coast4','ground4','ramp105f3']:
 d=A/group;pack=d/'final-isotropic-gray-successor-pack';q=d/'actual-once-isotropic-gray-successor-current-SourceG2';candidate=json.loads(take(pack/'candidate.json'));bank=json.loads(take(q/'actual-indexed-source-and-scales.json'));banks.extend(bank)
 for s in candidate['sequences']:
  aid=f'{s["base_asset"]:05x}';assert aid in own
  for f in s['frames']:take(pack/f['file']);os.link(pack/f['file'],P/f['file'])
  sequences.append(s);routes.append(dict(asset=aid,candidate=pin(pack/'candidate.json'),bank=pin(q/'actual-indexed-source-and-scales.json'),QA=pin(q/'runtime-qa.json')))
(P/'hd.json').write_text(json.dumps(dict(format_version=1,name='Literal late9 final successor frames, no metadata change',sequences=sequences),indent=2)+'\n')
bankpin=save('LITERAL-MERGED-ACTUAL-FINAL-SOURCEG2-NINE-BANK.json',banks)
epochp=R/'.reference/hd-SourceG2-current-intrinsic-helper-and-epoch-carry-private-20261019-v1/CURRENT-SOURCEG2-HELPER-COMPILE-RECEIPT.json';epoch=json.loads(take(epochp))
for rel,h in epoch['source18'].items():assert hashlib.sha256(take(R/rel)).hexdigest()==h
for k in ['library','serde_json']:assert pin(Path(epoch[k]['path']))['sha256']==epoch[k]['sha256'];take(Path(epoch[k]['path']))
contract=dict(status='PRIVATE_ROOT_AUTHORIZED_LATE9_SOURCEG2_H5654_FINITE_GENUINE_CONTEXT',own=sorted(own),cases=cases,ordered_pairs=pairs,required_roles=sorted(need),covered_roles=sorted(covered),real_caller_count=len(callers),all_callers_rendered=False,not_all_neighbor_state_combinations=True,World=0,new_intrinsic_QA=0,census=census,Source_pins=sourcepins,baseline={'packroot':str(B),'HD':pin(B/'hd.json'),'provenance':pin(B/'provenance.json'),'registered':5654,'hardlink_identity':baseline['hardlink_identity'],'finite_bindings':finite},own_pack=str(P),own_routes=routes,merged_actual_bank=bankpin,epoch=epoch,epoch_receipt=pin(epochp),Root_authority='Root resume NEW_TASK2026-10-20: one finite genuine Source context via reviewed staticTerrainHd/currentSource18G2/fullH5654/3088hardlinks after independent intrinsic. No new perasset gate, no World, no public/canonical/Git.')
save('FROZEN-LATE9-GENUINE-FINITE-SOURCE-H5654-CONTRACT.json',contract);save('BEFORE-CONTEXT-EXACT-INPUT-GUARDS.json',list(guards.values()))
print(json.dumps({'roles':roles,'cases':len(cases),'pairs':len(pairs),'Source_contributors':len(all_ids),'foreign':len(finite),'fallback':sorted(set(all_ids)-own-set(native)),'baseline':5654,'hardlinks':3088,'freeGB':shutil.disk_usage(O).free/1e9}))
