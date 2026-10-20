from pathlib import Path
import json,hashlib,struct,os,shutil
R=Path('/home/quintine/Projects/RaptorReplica/RustRaptor');P=Path(__file__).parent;B=R/'.reference/hd-windows-ci-six-remaining-terrain-guided-fine-successor-20261019-v2';selected=['2069f','206a2','206a7','301fc','301fd','30201'];own=set(selected)
assert shutil.disk_usage(P).free>1800000000+150000000
pin=lambda p:dict(path=str(Path(p).absolute()),sha256=hashlib.sha256(Path(p).read_bytes()).hexdigest(),size=Path(p).stat().st_size,mtime_ns=Path(p).stat().st_mtime_ns,mode=Path(p).stat().st_mode)
def save(n,v):p=P/n;p.write_text(json.dumps(v,indent=2)+'\n');return pin(p)
cat={};names={}
for line in (R/'data/INDEX').read_text().splitlines():a,n,f=line.split();cat[int(a,16)]=R/'data'/f;names[Path(f).name]=int(a,16)
flats={};inputs=[pin(R/'data/INDEX'),pin(R/'data/misc/PALETTE_DAT')]
for g in range(4):
 aid=names[f'FLATSG{g+1}_ITM'];raw=cat[aid].read_bytes();assert len(raw)%8==0;inputs.append(pin(cat[aid]));start=names[f'STARTG{g+1}TILES']+1;flats[g]=[(start+k,start+d,h,re,aid,k)for k,(d,h,re)in enumerate(struct.iter_unpack('<ihh',raw))]
maps={};census=[];spawn_count=0
for sec in range(1,4):
 for wave in range(1,10):
  mission=f'base:sector_{sec}_wave_{wave}';aid=names[f'MAP{wave}G{sec}_MAP'];raw=cat[aid].read_bytes();size,off,num=struct.unpack_from('<iii',raw);assert size==len(raw)and off==5412 and 5412+num*24<=len(raw);inputs.append(pin(cat[aid]));spawn_count+=num;rows=[]
  for j in range(1350):
   fi,g=struct.unpack_from('<hh',raw,12+j*4);a,d,h,re,fa,k=flats[g][fi];v=dict(intact=f'{a:05x}',settled=None if a==d else f'{d:05x}',row=j//9,column=j%9,MAP_asset=f'{aid:05x}',MAP_byte_offset=12+4*j,flat=fi,game=g,FLATS_asset=f'{fa:05x}',FLATS_byte_offset=k*8,health=0 if a==d else h,raw_health=h,reward=max(re,0),raw_reward=re);rows.append(v)
   if v['intact']in own or v['settled']in own:census.append(dict(mission=mission,Source_role='intact'if v['intact']in own else'legal_settled',**v))
  maps[mission]=rows
assert len(census)==15 and spawn_count==8778
censuspin=save('FRESH-ALL27MAP-4FLATS-15POSITIONS-SIX-ROLES.json',dict(status='SOURCE_ONLY_NO_WORLD',maps27=27,layout_cells=36450,spawn_records=spawn_count,selected=selected,callers=census,inputs=inputs))
cases=[];ordered=[];centers={}
for a in selected:
 v=next(v for v in census if v['intact']==a);m=v['mission'];y,x=v['row'],v['column'];centers[a]=(m,y,x);y0=min(max(y-1,0),147);x0=min(max(x-1,0),6);defs=[maps[m][yy*9+xx]for yy in range(y0,y0+3)for xx in range(x0,x0+3)];cases.append(dict(case_index=len(cases),mission=m,label=f'{a}-{m}-r{y}c{x}-intact',owner=a,window_row0=y0,window_column0=x0,height_tiles=3,width_tiles=3,ordered_source_ids=[d['intact']for d in defs],authentic_original_definitions=defs,settled_changes=[]))
for a,expectedhp,expectedreward,dest in [('2069f',10,50,'206a0'),('301fc',10,100,'30505'),('301fd',15,100,'30506'),('30201',25,300,'301ac')]:
 before=next(c for c in cases if c['owner']==a);m,y,x=centers[a];actor=maps[m][y*9+x];assert (actor['health'],actor['reward'],actor['settled'])==(expectedhp,expectedreward,dest);after=json.loads(json.dumps(before));after['case_index']=len(cases);after['label']=before['label'].replace('-intact','-legal-settled');slot=(y-before['window_row0'])*3+x-before['window_column0'];assert after['ordered_source_ids'][slot]==a;after['ordered_source_ids'][slot]=dest;after['settled_changes']=[actor];cases.append(after);ordered.append(dict(kind='Source_legal_one_tile_settlement_not_natural_timing',before=before['case_index'],settled=after['case_index'],changed_slot=slot,Original_actor=actor))
sourceids=sorted({a for c in cases for a in c['ordered_source_ids']});hdbytes=(R/'data/hd/hd.json').read_bytes();hd=json.loads(hdbytes);native={f'{s["base_asset"]+f["frame"]:05x}':dict(frame=f,sequence_header={k:v for k,v in s.items()if k!='frames'})for s in hd['sequences']for f in s['frames']};assert len(native)==5654 and not own&set(native);(P/'SNAPSHOT-H5654-MANIFEST.json').write_bytes(hdbytes)
carrier=P/'literal-H5654-full-eligibility-hardlinks';carrier.mkdir();(carrier/'hd.json').write_bytes(hdbytes);routes={n['frame']['file']for n in native.values()};assert len(routes)==3088;hardlinks=[]
for rel in sorted(routes):
 src=R/'data/hd'/rel;dst=carrier/rel;assert not src.is_symlink();dst.parent.mkdir(parents=True,exist_ok=True);os.link(src,dst,follow_symlinks=False);ss=src.stat();ds=dst.stat();assert not dst.is_symlink()and(ss.st_dev,ss.st_ino,ss.st_size)==(ds.st_dev,ds.st_ino,ds.st_size);hardlinks.append(dict(relative=rel,device=ss.st_dev,inode=ss.st_ino,size=ss.st_size))
save('ALL3088-RAW-ELIGIBILITY-HARDLINK-IDENTITIES-ZERO-BYTE-COPY.json',dict(manifest=pin(carrier/'hd.json'),registered_frames=5654,raw_routes=3088,copied_raw_bytes=0,entries=hardlinks))
proposal=P/'proposal-selected6';proposal.mkdir();cp=B/'private-final6-pack-sourcehash-v2/candidate.json';candidate=json.loads(cp.read_text());sequences=candidate['sequences'];banks={};bank=B/'actual-once-SourceG2-final-intrinsic-sourcehash-v2/actual-indexed-source-and-scales.json'
for s in sequences:
 a=f'{s["base_asset"]:05x}';f=s['frames'][0];src=cp.parent/f['file'];os.link(src,proposal/f['file']);banks[a]=pin(bank)
(proposal/'hd.json').write_text(json.dumps(dict(format_version=1,name='Private faithful six Source-guided terrain proposal',sequences=sequences),indent=2)+'\n');newnative={f'{s["base_asset"]:05x}':dict(frame=s['frames'][0],sequence_header={k:v for k,v in s.items()if k!='frames'})for s in sequences};foreign=sorted(set(sourceids)&set(native));fallback=sorted(set(sourceids)-set(native)-own);bindings={}
for a in sourceids:
 p=cat[int(a,16)];assert struct.unpack('<5i',p.read_bytes()[:20])==(1,1,0,32,32);b=dict(source=pin(p),native=None)
 if a in own:b['native']=dict(**newnative[a],raw=pin(proposal/newnative[a]['frame']['file']))
 elif a in native:b['native']=dict(**native[a],raw=pin(carrier/native[a]['frame']['file']))
 bindings[a]=b
bindingpin=save('FINITE-H5654-CONSUMED-SOURCE-NATIVE-RAW-BINDINGS.json',dict(bindings=bindings,registered_foreign=foreign,used_selected=selected,Original_fallbacks=fallback,actual_baseline_at_capture=pin(P/'SNAPSHOT-H5654-MANIFEST.json'),all6_proposed_manifest=pin(proposal/'hd.json'),actual_accepted_banks=banks,no_full_raw_copy=True))
expected=dict(windows=10,records=40,roles=120,Source=len(sourceids),foreign=len(foreign),own=6,fallback=len(fallback),components=4*(len(foreign)+6),stages=24,baseline_count=5654,proposed_count=6,callers=15,maps=27,ordered_events=4)
recipe=dict(status='SEALED_CURRENT_G2_H5654_WINDOWS6_GENUINE10',Root_GO=True,data_root=str(R/'data'),baseline_root=str(carrier),own_root=str(proposal),selected_proposals=selected,selected=selected,Original_fallbacks=fallback,cases=cases,ordered_views=ordered,accepted_own_banks=banks,finite_bindings=bindingpin,Source_census=censuspin,expected=expected,limits=['Literal captured H5654 full manifest; all3088rawroutes are eligibilityhardlinks only. Later publication does not relabel these pixels.','Six real finite3x3 intact windows and four Source-legal one-tile settled endpoints, no World or natural destruction timing claim.','Original owner retention13cells206a2/4cells206a7 afterjoins carries noHDdetailcredit; SourceClasses and foreign domains preserved.','Source15actualMAPpositions censused; only ten finite endpoints rendered, not all reachable scene states.'])
save('SEALED-WINDOWS6-GENUINE10-CURRENTG2-H5654-RECIPE.json',recipe);print(json.dumps(expected));print('fallback',fallback,'foreign',foreign)
