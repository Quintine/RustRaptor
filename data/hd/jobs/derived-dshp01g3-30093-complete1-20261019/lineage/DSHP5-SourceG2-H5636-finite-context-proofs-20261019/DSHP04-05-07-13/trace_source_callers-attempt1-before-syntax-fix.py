from pathlib import Path
import json,struct,hashlib
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;D=R/'data'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
ids={};names={}
for line in (D/'INDEX').read_text().splitlines():
 if line.strip():
  i,size,path=line.split();v=int(i,16);ids[v]=path;names.setdefault(Path(path).name.upper(),v)
targets={'30096':'DSHP04G3_PIC','30097':'DSHP05G3_PIC','30099':'DSHP07G3_PIC','3009e':'DSHP13G3_PIC'}
libs=[];matches={a:[]for a in targets}
for game in range(4):
 p=D/'misc'/f'SPRITE{game+1}_ITM';b=p.read_bytes();assert len(b)%528==0;hits=[]
 for n in range(len(b)//528):
  rec=b[n*528:(n+1)*528];name=rec[:16].split(b'\0')[0].decode();fields=list(struct.unpack_from('<26i',rec,16));assert 0<=fields[19]<=30 and 0<=fields[22]<=24
  if name.upper()not in names:continue
  base=names[name.upper()];frames=max(1,fields[7])
  for asset in targets:
   if base<=int(asset,16)<base+frames:
    v={'game':game,'library':n,'name':name,'base_asset':f'{base:05x}','frames':frames,'fields':fields,'record_sha256':hashlib.sha256(rec).hexdigest(),'definition':f'base:enemy_{game}_{n}','health':max(1,fields[13]),'ground':fields[21]>=3,'Source_shadow':fields[11]!=0,'flight_x':list(struct.unpack_from('<30h',rec,408)),'flight_y':list(struct.unpack_from('<30h',rec,468))};hits.append(v);matches[asset].append(v)
 libs.append({'path':str(p),'sha256':sha(p),'records':len(b)//528,'hits':hits})
callers={a:[]for a in targets};maps=[]
for sector in range(1,4):
 for wave in range(1,10):
  p=D/'maps'/f'MAP{wave}G{sector}_MAP';b=p.read_bytes();size,off,count=struct.unpack_from('<iii',b);assert size==len(b)and off==5412 and 5412+count*24<=len(b);group=None
  for n in range(count):
   link,library,x,row,game,diff=struct.unpack_from('<6i',b,5412+n*24)
   if group is None:group=row
   for asset,defs in matches.items():
    for d in defs:
     if(game,library)==(d['game'],d['library']):callers[asset].append({'mission':f'base:sector_{sector}_wave_{wave}','Source_map':str(p.relative_to(D)),'spawn_ordinal':n,'Source_row':row,'Source_x_cell':x,'group_row':group,'link':link,'game':game,'library':library,'definition':d['definition'],'raw_difficulty':diff,'difficulty_code':max(0,diff),'tick':0 if group>=139 else56+(138-group)*32,'spawn_x':16+x*32,'spawn_y':(-136 if group>=139 else-112)-(group-row)*32,'legal_normal_pilot2_enabled':diff in[3,4],'legal_pilot3_enabled':diff in[3,4,5]})
   if link in[1,-1]:group=None
  maps.append({'path':str(p),'sha256':sha(p),'spawns':count,'layout_cells':1350})
report={'status':'AUTHENTIC-SOURCE-ALL4-SPRITE-ALL27MAP-FOUR-DISTINCT-FAMILY-LOOKUP','INDEX':{'path':str(D/'INDEX'),'sha256':sha(D/'INDEX')},'libraries':libs,'maps':maps,'targets':{a:{'source':ids[int(a,16)],'source_sha256':sha(D/ids[int(a,16)]),'definitions':matches[a],'callers':callers[a]}for a in targets},'actual_World_calls':0,'no_canonical_mutation':True}
(O/'AUTHENTIC-ALL4-SPRITE-ALL27MAP-DSHP04-05-07-13-CALLER-TRACE.json').write_text(json.dumps(report,indent=2)+'\n')
for a,t in report['targets'].items():print(a,'defs',[(d['definition'],d['health'],d['ground'],d['Source_shadow'])for d in t['definitions']],'callers',len(t['callers']),'normal',sum(c['legal_normal_pilot2_enabled']for c in t['callers']));print(t['callers'][:5])
