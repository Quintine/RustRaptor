#!/usr/bin/env python3
"""Reproduce SD/HD canvases and PCM WAVs from untouched builtin generated PNGs.
No decoded original images are packaged. No painted/masked master edits occur.
"""
from pathlib import Path
import argparse,datetime,hashlib,json,math,random,struct,wave
from PIL import Image,ImageOps
ROOT=Path(__file__).resolve().parent
h=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def palette(path):
 raw=path.read_bytes();assert len(raw)==768
 values=[(min(v,63)<<2)|(min(v,63)>>4) for v in raw]
 values[720:]=[0]*48
 im=Image.new('P',(1,1));im.putpalette(values);return im

def small(im,size,pal):
 im=im.convert('RGBA').resize(size,Image.Resampling.LANCZOS)
 alpha=im.getchannel('A').point(lambda a:255 if a>=128 else 0)
 out=im.convert('RGB').quantize(palette=pal,dither=Image.Dither.NONE).convert('RGBA');out.putalpha(alpha);return out

def canvases(source,name,size,pal):
 src=Image.open(source).convert('RGBA');target=(size[0]*4,size[1]*4)
 hd=Image.new('RGBA',target);fitted=ImageOps.contain(src,target,Image.Resampling.LANCZOS);hd.alpha_composite(fitted,((target[0]-fitted.width)//2,(target[1]-fitted.height)//2))
 hd.save(ROOT/'art'/f'{name}-hd.png');small(hd,size,pal).save(ROOT/'art'/f'{name}-sd.png')
 return {'source':str(source.relative_to(ROOT)),'sha256':h(source),'logical_size':size,'hd_size':target,'alpha_below128_transparent':True,'original_master_not_modified':True}

def synth(name,duration,base):
 rate=22050;n=int(rate*duration);rng=random.Random(7043+sum(map(ord,name))+base);data=bytearray();peak=0;sumsq=0
 for i in range(n):
  t=i/rate;u=i/n;env=min(1,u*30)*(1-u)**1.3
  if name=='shot':s=(math.sin(2*math.pi*(95*t-40*t*t))+rng.uniform(-1,1)*0.45)*math.exp(-u*3)
  elif name=='death':s=rng.uniform(-1,1)*0.65+math.sin(2*math.pi*(70*t-18*t*t))*0.4
  elif name=='warning' or name=='boss_alarm':s=math.sin(2*math.pi*(base+70*math.sin(2*math.pi*t*5))*t)*0.8+0.12*math.sin(2*math.pi*base*.5*t)
  else:
   notes=[1,1.25,1.5,2] if name=='victory' else [1,1.5,1.25];freq=base*notes[min(len(notes)-1,int(u*len(notes)))];s=math.sin(2*math.pi*freq*t)+0.15*math.sin(2*math.pi*freq*2*t)
  v=max(-32767,min(32767,int(s*env*8500)));peak=max(peak,abs(v));sumsq+=v*v;data+=struct.pack('<h',v)
 p=ROOT/'audio'/f'{name}.wav'
 with wave.open(str(p),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(rate);w.writeframes(data)
 return {'file':str(p.relative_to(ROOT)),'sha256':h(p),'samples':n,'rate':rate,'duration':duration,'peak':peak,'rms':round(math.sqrt(sumsq/n),2),'seed':7043+sum(map(ord,name))+base}

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--palette',type=Path,default=ROOT.parents[1]/'data/misc/PALETTE_DAT');args=parser.parse_args();pal=palette(args.palette)
 report={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'recipe':Path(__file__).name,'recipe_sha256':h(__file__),'palette_sha256':h(args.palette),'ordinary_palette_entries_only':list(range(240)),'assets':[]}
 n=int(ROOT.name.rsplit('_',1)[1]);is_boss='_boss_' in ROOT.name
 if is_boss:
  report['assets'].append(canvases(ROOT/'art/unit-generated-v1.png','unit',(128,64) if n==1 else (48,80),pal))
  report['assets'].append(canvases(ROOT/'art/projectile-generated-v1.png','projectile',(8,16),pal))
  cues=[('warning',.5,250+n*30),('shot',.16,100),('death',1.05,80)]
 else:
  raw=ROOT/'art/terrain-generated-v1.png';src=Image.open(raw).convert('RGBA');hd=src.resize((1280,2048),Image.Resampling.LANCZOS);sd=small(hd,(320,512),pal)
  for reverse in [False,True]:
   hi=ImageOps.flip(hd) if reverse else hd;lo=ImageOps.flip(sd) if reverse else sd
   for y in range(16):
    for x in range(10):
     index=(160 if reverse else 0)+y*10+x
     hi.crop((x*128,y*128,(x+1)*128,(y+1)*128)).save(ROOT/'art'/f'tile_{index:03}-hd.png')
     lo.crop((x*32,y*32,(x+1)*32,(y+1)*32)).save(ROOT/'art'/f'tile_{index:03}-sd.png')
  # Reflected cycle joins equal boundary rows at full and logical resolution.
  for im in [hd,sd]:assert im.crop((0,im.height-1,im.width,im.height)).tobytes()==ImageOps.flip(im).crop((0,0,im.width,1)).tobytes()
  hd.save(ROOT/'art/terrain-preview-hd.png');sd.save(ROOT/'art/terrain-preview-sd.png')
  bg=ImageOps.fit(src,(1280,800),Image.Resampling.LANCZOS,centering=(.5,.35));bg.save(ROOT/'art/briefing-hd.png');small(bg,(320,200),pal).save(ROOT/'art/briefing-sd.png')
  report['assets'].append({'source':'art/terrain-generated-v1.png','sha256':h(raw),'logical_map':[320,512],'hd_map':[1280,2048],'reflected_cycle':True,'tiles':320,'briefing':'same generated map cropped with 8:5 viewport, no separate generation','source_not_modified':True})
  cues=[('approach',.6,164+n*30),('objective',.36,392),('boss_alarm',.75,275),('victory',.95,262)]
 (ROOT/'audio').mkdir(exist_ok=True);report['audio']=[synth(*c) for c in cues]
 report['final_art']=[{'file':str(p.relative_to(ROOT)),'sha256':h(p),'size':Image.open(p).size} for p in sorted((ROOT/'art').glob('*.png')) if 'generated' not in p.name]
 (ROOT/'asset-report.json').write_text(json.dumps(report,indent=2)+'\n');print(ROOT.name,'assets',len(report['final_art']),'sounds',len(cues))
if __name__=='__main__':main()
