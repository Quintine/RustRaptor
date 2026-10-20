from pathlib import Path
import struct,json,hashlib,collections
O=Path(__file__).resolve().parent;R=O.parents[1];own={'10514','10515','1051b','1051c'};pins={}
def read(p):
 b=p.read_bytes();pins[str(p.relative_to(R))]=hashlib.sha256(b).hexdigest();return b
cat={};names={}
for l in read(R/'data/INDEX').decode().splitlines():
 a,n,p=l.split();cat[int(a,16)]=(int(n),R/'data'/p);names[Path(p).name]=int(a,16)
flats={};definitions=[]
for g in range(4):
 a=names[f'FLATSG{g+1}_ITM'];b=read(cat[a][1]);start=names[f'STARTG{g+1}TILES']+1;rr=[]
 for k in range(len(b)//8):
  d,h,re=struct.unpack_from('<ihh',b,k*8);t=dict(intact=f'{start+k:05x}',settled=None if d==k else f'{start+d:05x}',health=0 if d==k else h,reward=max(0,re),game=g,FLATS_record=k,FLATS_asset=f'{a:05x}',FLATS_byte_offset=8*k,raw_hex=b[k*8:k*8+8].hex());rr.append(t)
  if t['intact'] in own or t['settled']in own:definitions.append(t)
 flats[g]=rr
maps={};callers=[];joins=[]
for sec in range(1,4):
 for w in range(1,10):
  a=names[f'MAP{w}G{sec}_MAP'];b=read(cat[a][1]);rows=[];m=f'base:sector_{sec}_wave_{w}'
  for k in range(1350):f,g=struct.unpack_from('<hh',b,12+k*4);rows.append(flats[g][f])
  maps[m]=rows
  for k,t in enumerate(rows):
   if t['intact']not in own and t['settled']not in own:continue
   y,x=divmod(k,9);neighbors=[]
   for dy,dx in [(-1,0),(0,-1),(0,1),(1,0)]:
    yy,xx=y+dy,x+dx
    if 0<=yy<150 and 0<=xx<9:
     nt=rows[yy*9+xx];neighbors.append(dict(direction=[dy,dx],row=yy,column=xx,Original_tile=nt))
     if t['intact']in own and nt['intact']in own and (dy,dx) in [(0,1),(1,0)]:joins.append(dict(mission=m,position=[y,x],neighbor_position=[yy,xx],assets=[t['intact'],nt['intact']],direction=[dy,dx]))
   callers.append(dict(mission=m,row=y,column=x,MAP_asset=f'{a:05x}',MAP_byte_offset=12+k*4,raw_hex=b[12+k*4:16+k*4].hex(),Original_tile=t,cardinal_neighbors=neighbors))
summary=dict(status='AUTHENTIC_ALL27_MAP_ALL4_FLATS_LITERAL_CENSUS_NO_CONTEXT_EXECUTION',selected=sorted(own),definitions=definitions,all_callers=callers,own_own_cardinal_joins=joins,all27_MAP_and4_FLATS_pins=pins,caller_counts=dict(collections.Counter(t['Original_tile']['intact'] for t in callers)),mission_counts=dict(collections.Counter(t['mission']for t in callers)),map_layouts=maps)
(O/'SOURCE-ALL27-MAPS-ALL4-FLATS-SHORELINE4-CALLER-CENSUS.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps({k:v for k,v in summary.items()if k not in ['map_layouts','all_callers','all27_MAP_and4_FLATS_pins']},indent=2));print('callers',len(callers),'joins',len(joins))
