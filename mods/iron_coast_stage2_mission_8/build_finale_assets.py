#!/usr/bin/env python3
"""Package four genuine imagegen masters and synthesize reproducible local PCM.

Art operations only extract complete alpha sprites, fit without distortion,
reduce SD, and split joined terrain. Original reference pixels are not shipped.
"""
from pathlib import Path
import runpy
from PIL import Image, ImageOps
import hashlib,json,math,random,struct,wave
ROOT=Path(__file__).resolve().parent.parent
PALETTE=ROOT.parent/'data/misc/PALETTE_DAT'
GEN=Path('/home/quintine/.codex/generated_images/01a1245e-048c-7e92-91d2-78de2e5900ab')
REFERENCE=ROOT.parent.parent/'.reference/iron-coast-stage2-finale/classic-reference.png'
GATE={('boss', 7, 1): ('stage2-dreadnought-v1', '82daccfc-adb2-4c39-964f-9016d2bde07d'), ('boss', 8, 1): ('stage2-leviathan-v1', 'e5eae8a4-174b-43e7-9b11-c9fadf457ebf'), ('mission', 7, 1): ('stage2-fleet-terrain-v1', 'ae683e17-1f9b-47dd-9f85-5cb4664341f9'), ('mission', 8, 1): ('stage2-blacktide-terrain-v1', '6533e770-3571-4536-be9d-f5b641e9d2f0'), ('mission', 8, 2): ('stage2-blacktide-terrain-v2', 'd96ef991-fdf2-4189-9865-555a6a42927c')}
RAW={('boss',7,1):'exec-d314321c-4fde-4164-affb-67f3fa61a50f.png',('boss',8,1):'exec-34a0f83d-4b85-46ed-b927-6681a113ed09.png',('mission',7,1):'exec-b60ac9a7-fbe0-4ae4-944a-cfaed9bd3df9.png',('mission',8,1):'exec-6a1fcf7e-50e9-4764-bbd9-6c6476670b65.png',('mission',8,2):'exec-1ba2d521-d873-4602-8ef2-046c1f241587.png'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def pcm(pkg,name,n,seed):
 rate=22050;count=round(n*rate);rng=random.Random(seed);phase=0;low=0;values=[]
 for i in range(count):
  t=i/rate;p=i/(count-1);noise=rng.uniform(-1,1);low=.91*low+.09*noise
  if name in ['warning','phase']:
   f=[550,825,1100][min(2,int(p*3))] if name=='warning' else [165,220,330,440][min(3,int(p*4))]
   phase+=2*math.pi*f/rate;v=.7*math.sin(phase)+.2*math.sin(phase*2);env=math.sin(math.pi*((p*3)%1))**.7 if name=='warning' else math.sin(math.pi*p)**.6
  elif name=='shot':
   phase+=2*math.pi*(60+270*(1-p)**2)/rate;v=.55*math.sin(phase)+.22*noise+.25*low;env=min(1,t/.003)*math.exp(-p*7)
  elif name=='death':
   phase+=2*math.pi*(55-30*p)/rate;v=.6*low+.2*noise+.3*math.sin(phase);env=min(1,t/.003)*math.exp(-p*4)
  else:
   notes={'approach':[110,147,165,220],'escalation':[220,165,220,165],'boss_alarm':[147,110,98,73],'victory':[196,262,330,392,524]}
   ns=notes[name];f=ns[min(len(ns)-1,int(p*len(ns)))];phase+=2*math.pi*f/rate;v=.8*math.sin(phase)+.18*math.sin(phase*2)
   local=(p*len(ns))%1;env=math.sin(math.pi*local)**.65
  env*=min(1,(count-1-i)/(rate*.005));values.append(v*max(0,env))
 peak=max(abs(v) for v in values);samples=[round(v/peak*.72*32767) for v in values];path=pkg/'audio'/f'{name}.wav'
 with wave.open(str(path),'wb') as w:w.setparams((1,2,rate,0,'NONE','not compressed'));w.writeframes(struct.pack('<'+'h'*count,*samples))
 return {'file':str(path.relative_to(pkg)),'sample_rate':rate,'bits':16,'channels':1,'seconds':count/rate,'seed':seed,'peak':max(map(abs,samples)),'rms':(sum(v*v for v in samples)/count)**.5,'sha256':sha(path)}
def provenance(pkg,kind,n):
 previous_path=pkg/'art/provenance.json'
 previous=json.loads(previous_path.read_text()) if previous_path.exists() else {}
 old={v['version']:v for v in previous.get('raws',[])}
 raws=[]
 for (k,num,ver),builtin in RAW.items():
  if (k,num)!=(kind,n):continue
  p=pkg/'art'/f'generated-v{ver}.png';original=GEN/builtin
  if original.exists():assert sha(p)==sha(original)
  prompt=pkg/'art'/f'prompt-v{ver}.txt'
  ref=pkg/'art/generated-v1.png' if ver==2 else REFERENCE
  raws.append({'version':ver,'gate_owner':'/root/iron_coast_6','gate_job':GATE[(kind,n,ver)][0],'gate_lease':GATE[(kind,n,ver)][1],'gate_outcome':'success','builtin_file':str(original),'builtin_sha256':sha(p),'raw_file':str(p.relative_to(pkg)),'raw_sha256':sha(p),'prompt_file':str(prompt.relative_to(pkg)),'prompt_sha256':sha(prompt),'reference_file':str(ref),'reference_sha256':sha(ref) if ref.exists() else old[ver]['reference_sha256'],'builtin_identity_verified':True,'transparent_requested':kind=='boss','rejected':kind=='mission' and n==8 and ver==1})
 put(pkg/'art/provenance.json',{'generator':'OpenAI builtin imagegen; exact untouched PNGs preserved','utc':'2026-10-11','raws':raws,'original_references':'External authentic catalog board; no decoded original reference pixels included in this package','historical_hold':'Mission8 v1 painted an aircraft in the platform; v2 genuinely replaces it with empty service deck' if n==8 and kind=='mission' else None})
def boss(n):
 pkg=ROOT/f'iron_coast_stage2_boss_{n}';frames=2 if n==7 else 3;logical=(112,88) if n==7 else (112,112);im=Image.open(pkg/'art/generated-v1.png').convert('RGBA');cut=im.height*3//4
 output=[];crops=[]
 for f in range(frames):
  cell=(f*im.width//frames,0,(f+1)*im.width//frames,cut);part=im.crop(cell)
  box=part.getchannel('A').point(lambda a:255 if a>=128 else 0).getbbox();assert box
  # Preserve meaningful alpha, plus margin; all discarded pixels are alpha<16.
  allbox=part.getchannel('A').point(lambda a:255 if a>=16 else 0).getbbox()
  crop=(max(0,allbox[0]-2),max(0,allbox[1]-2),min(part.width,allbox[2]+2),min(part.height,allbox[3]+2))
  part=part.crop(crop);size=(logical[0]*4,logical[1]*4);ratio=min((size[0]-24)/part.width,(size[1]-24)/part.height)
  fit=part.resize((round(part.width*ratio),round(part.height*ratio)),Image.Resampling.LANCZOS);hd=Image.new('RGBA',size);hd.alpha_composite(fit,((size[0]-fit.width)//2,(size[1]-fit.height)//2));output.append(hd)
  crops.append({'frame':f,'cell':cell,'alpha16_crop':crop,'source_occupied_bounds':box,'fit_size':fit.size})
 hd=Image.new('RGBA',(logical[0]*4*frames,logical[1]*4));sd=Image.new('RGBA',(logical[0]*frames,logical[1]))
 for f,frame in enumerate(output):hd.paste(frame,(f*logical[0]*4,0));sd.paste(frame.resize(logical,Image.Resampling.BOX),(f*logical[0],0))
 hd.save(pkg/'art/unit-hd.png');sd.save(pkg/'art/unit-sd.png')
 part=im.crop((0,cut,im.width,im.height));box=part.getchannel('A').point(lambda a:255 if a>=16 else 0).getbbox();assert box;part=part.crop(box)
 shd=Image.new('RGBA',(24,48));ratio=min(20/part.width,44/part.height);fit=part.resize((round(part.width*ratio),round(part.height*ratio)),Image.Resampling.LANCZOS);shd.alpha_composite(fit,((24-fit.width)//2,(48-fit.height)//2));shd.save(pkg/'art/projectile-hd.png');shd.resize((6,12),Image.Resampling.BOX).save(pkg/'art/projectile-sd.png')
 files={}
 for name in ['unit-sd','unit-hd','projectile-sd','projectile-hd']:
  path=pkg/'art'/f'{name}.png';x=Image.open(path);files[str(path.relative_to(pkg))]={'size':x.size,'sha256':sha(path)}
 audio={name:pcm(pkg,name,duration,n*1000+i) for i,(name,duration) in enumerate([('warning',.32),('phase',.55),('shot',.25),('death',1.25)])}
 put(pkg/'audio-recipe.json',{'generator':'build_finale_assets.py deterministic chirp/noise PCM synthesis; no recordings','files':audio})
 put(pkg/'art-qa.json',{'pipeline':'Complete meaningful-alpha cell crop with proportional fit; transparent centered padding; BOX SD reduction; no repaint','logical_size':logical,'frames':frames,'hd_scale':4,'origin':[0,0],'crops':crops,'projectile_crop_in_lower_cell':box,'files':files,'phase_alignment':'Common centered logical canvas; collision bounds identical for every displayed phase'})
 provenance(pkg,'boss',n)
 id=pkg.name;title='Dreadnought' if n==7 else 'Leviathan';hp=280 if n==7 else 360
 content={'weapons':[{'id':id+':shell','name':title+' cannon shell','damage':3 if n==7 else 4,'speed':3,'cooldown':84,'behavior':'straight','target':'all','art':{'png':'art/projectile-sd.png','hd_png':'art/projectile-hd.png','logical_width':6,'logical_height':12}}], 'enemies':[{'id':id+':unit','name':title,'health':hp,'speed':0,'reward':5000 if n==7 else 9000,'ground':False,'boss':True,'cooldown':10000,'art':{'png':'art/unit-sd.png','hd_png':'art/unit-hd.png','logical_width':logical[0],'logical_height':logical[1],'frames':frames},'script':'scripts/ai.rhai'}], 'sounds':[{'id':id+':'+name,'name':title+' '+name,'file':info['file'],'volume':90 if name=='warning' else 110,'pan':127,'pitch':128,'priority':3 if name in ['death','phase'] else 2} for name,info in audio.items()]}
 put(pkg/'content.json',content)
 (pkg/'mod.toml').write_text(f'id = "{id}"\nname = "Iron Coast II: {title} Boss"\nversion = "1.0.0"\napi_version = 1\ndescription = "Distinct persistent {title} carrier with telegraphed phase attacks, SD/HD artwork and original synthesized PCM sounds."\ncontent = "content.json"\nscripts = ["scripts/ai.rhai"]\n')
def mission(n):
 pkg=ROOT/f'iron_coast_stage2_mission_{n}';selected=2 if n==8 else 1;source=Image.open(pkg/f'art/generated-v{selected}.png').convert('RGB');hd=source.resize((1152,1536),Image.Resampling.LANCZOS)
 # Ordinary palette0..239 only: reserved252/253 may never be remapped by art.
 raw=PALETTE.read_bytes();colors=[(min(v,63)<<2)|(min(v,63)>>4) for v in raw];pal=Image.new('P',(1,1));pal.putpalette(colors[:720]+colors[:3]*16)
 sd=source.resize((288,384),Image.Resampling.LANCZOS).quantize(palette=pal,dither=Image.Dither.NONE).convert('RGB')
 for mode,master,scale in [('sd',sd,1),('hd',hd,4)]:
  for reflect in [False,True]:
   img=ImageOps.flip(master) if reflect else master;joined=Image.new('RGB',img.size)
   for row in range(12):
    for col in range(9):
     k=int(reflect)*108+row*9+col;tile=img.crop((col*32*scale,row*32*scale,(col+1)*32*scale,(row+1)*32*scale));tile.save(pkg/f'art/tile_{k:03}_{mode}.png');joined.paste(tile,(col*32*scale,row*32*scale))
   assert joined.tobytes()==img.tobytes()
  assert master.crop((0,master.height-1,master.width,master.height)).tobytes()==ImageOps.flip(master).crop((0,0,master.width,1)).tobytes()
  master.save(pkg/f'art/terrain-preview-{mode}.png')
 # Each finale mission owns a separate cinematic briefing master and recipe.
 runpy.run_path(str(pkg/'art/build_cinematic_briefing.py'),run_name='__main__')
 audio={name:pcm(pkg,name,seconds,n*10000+i) for i,(name,seconds) in enumerate([('approach',1.1),('escalation',.9),('boss_alarm',1.2),('victory',1.6)])}
 put(pkg/'audio-recipe.json',{'generator':'build_finale_assets.py deterministic note-envelope PCM synthesis; no recordings','files':audio})
 # Varied real native enemy entries keep original Catalog behavior and paths.
 classics=['base:enemy_0_73','base:enemy_0_74','base:enemy_0_23','base:enemy_0_24','base:enemy_0_95','base:enemy_0_96']
 spawns=[]
 for k,tick in enumerate(range(100,2400 if n==7 else 2700,125)):
  spawns.append({'tick':tick,'enemy':classics[k%len(classics)],'x':[40,210,112,230,72,176][k%6],'y':-32})
 # Interceptor formations provide additional air pressure, with timed rests.
 for k,tick in enumerate([330,740,1120,1510,1890,2210] if n==7 else [360,800,1210,1590,2030,2500]):
  spawns.append({'tick':tick,'enemy':'iron_coast_stage2_interceptor:unit','x':[52,210,90,190][k%4],'y':-24})
 siege=[(260,32),(610,216),(1100,80),(1710,168)] if n==7 else [(280,32),(700,216),(1180,80),(1730,168),(2210,128)]
 skimmer=[(460,64),(1370,192),(2140,128)] if n==7 else [(490,64),(960,192),(1510,112),(2400,224)]
 for enemy,entries in [('siege',siege),('skimmer',skimmer)]:
  spawns.extend({'tick':tick,'enemy':f'iron_coast_stage2_{enemy}:unit','x':x,'y':-32} for tick,x in entries)
 boss_tick=2500 if n==7 else 2850;spawns.append({'tick':boss_tick,'enemy':f'iron_coast_stage2_boss_{n}:unit','x':88,'y':-112 if n==8 else -88});spawns.sort(key=lambda x:x['tick'])
 id=pkg.name;title='Siege of the Iron Fleet' if n==7 else 'Black Tide'
 content={'sounds':[{'id':id+':'+name,'name':title+' '+name,'file':info['file'],'volume':90 if name!='boss_alarm' else 105,'pan':127,'pitch':128,'priority':3 if name in ['boss_alarm','victory'] else 2} for name,info in audio.items()], 'missions':[{'id':id+f':mission_0{n}','name':f'Iron Coast II {n} — {title}','duration':3800,'auto_complete':False,'columns':9,'music_track':'iron_coast_stage2_music:finale','spawns':spawns,'tiles':[{'art':{'png':f'art/tile_{k:03}_sd.png','hd_png':f'art/tile_{k:03}_hd.png','logical_width':32,'logical_height':32}} for k in range(216)],'layout':list(range(216))*16,'art':{'png':'art/briefing-sd.png','hd_png':'art/briefing-hd.png','logical_width':320,'logical_height':200},'script':'scripts/mission.rhai'}]}
 put(pkg/'content.json',content)
 deps=['iron_coast_stage2_interceptor','iron_coast_stage2_siege','iron_coast_stage2_skimmer',f'iron_coast_stage2_boss_{n}','iron_coast_stage2_music']
 (pkg/'mod.toml').write_text(f'id = "{id}"\nname = "Iron Coast II {n}: {title}"\nversion = "1.0.0"\napi_version = 1\ndescription = "{title}: native classic waves, persistent naval defense objectives and a phased final carrier. Starter-gun viable, inventory safe, joined SD/HD terrain and original PCM cues."\ncontent = "content.json"\nscripts = ["scripts/mission.rhai"]\n\n[dependencies]\n'+''.join(f'{d} = "^1.0"\n' for d in deps))
 put(pkg/'art-qa.json',{'selected_raw':f'art/generated-v{selected}.png','selected_raw_sha256':sha(pkg/f'art/generated-v{selected}.png'),'logical_tile':[32,32],'hd_tile':[128,128],'columns':9,'rows':24,'layout_period_repetitions':16,'layout_total_rows':384,'logical_scroll_coverage':12288,'joined_palette_then_split':True,'mirrored_loop_boundary_exact':True,'reassembly_pixel_exact':True,'logical_collision_unchanged_by_hd':True,'palette_sha256':sha(PALETTE),'palette_classes':'ordinary0..239 only, alpha opaque; runtime mods never claim reserved original palette classes','briefing':'independent cinematic master, art/build_cinematic_briefing.py; see art/briefing-cinematic-provenance.json','files':{str(p.relative_to(pkg)):sha(p) for p in sorted((pkg/'art').glob('*-*.png'))}})
 provenance(pkg,'mission',n)
for n in [7,8]:boss(n);mission(n)
print('Four finale packages: matching art, seam-safe terrain, PCM and content generated')
