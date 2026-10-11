#!/usr/bin/env python3
"""Reproduce packaged artwork footprints and seeded local PCM audio.

Builtin imagegen masters are preserved byte-for-byte. This recipe only crops
empty/runtime-subthreshold transparent padding, fits/resamples canvases, splits joined terrain and
quantizes SD to ordinary game palette colors; it never paints generated pixels.
"""
from pathlib import Path
import argparse,hashlib,json,math,random,struct,wave
from PIL import Image,ImageOps
ROOT=Path(__file__).resolve().parent
hashfile=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def palette(path):
 raw=path.read_bytes();assert len(raw)==768
 colors=[(min(v,63)<<2)|(min(v,63)>>4) for v in raw]
 colors[720:]=colors[:48];im=Image.new('P',(1,1));im.putpalette(colors);return im

def sd(im,size,pal):
 im=im.convert('RGBA').resize(size,Image.Resampling.BOX);alpha=im.getchannel('A').point(lambda v:255 if v>=128 else 0)
 out=im.convert('RGB').quantize(palette=pal,dither=Image.Dither.NONE).convert('RGBA');out.putalpha(alpha);return out

def footprint(stem,logical,pal):
 p=ROOT/'art'/f'{stem}-source-v1.png'
 if stem=='shell' and (ROOT/'art/shell-v2-source-v1.png').exists():p=ROOT/'art/shell-v2-source-v1.png'
 raw=Image.open(p).convert('RGBA');assert raw.getchannel('A').getextrema()[0]==0,'genuine transparent master required'
 # Keep every visible alpha>=128 sample. Imagegen adds isolated alpha1 noise
 # across the canvas; threshold16 bounds remove only runtime-invisible padding,
 # while the raw master and its original alpha remain untouched.
 box=raw.getchannel('A').point(lambda v:255 if v>=16 else 0).getbbox();assert box;assert raw.getchannel('A').point(lambda v:255 if v>=128 else 0).getbbox();crop=raw.crop(box);size=tuple(v*8 for v in logical);margin=8 if stem=='shell' else 24
 hd=Image.new('RGBA',size);fitted=ImageOps.contain(crop,(size[0]-margin*2,size[1]-margin*2),Image.Resampling.LANCZOS);hd.alpha_composite(fitted,((size[0]-fitted.width)//2,(size[1]-fitted.height)//2));low=sd(hd,logical,pal)
 for suffix,im in [('hd',hd),('sd',low)]:
  bounds=im.getchannel('A').point(lambda v:255 if v>=128 else 0).getbbox();assert bounds and bounds[0]>0 and bounds[1]>0 and bounds[2]<im.width and bounds[3]<im.height,(stem,suffix,bounds);im.save(ROOT/'art'/f'{stem}-{suffix}.png')
 return {'master':str(p.relative_to(ROOT)),'master_sha256':hashfile(p),'master_size':list(raw.size),'crop_runtime_invisible_padding':list(box),'crop_threshold':16,'runtime_alpha_threshold':128,'logical_canvas':list(logical),'hd_canvas':list(size),'sd_bounds':list(low.getchannel('A').getbbox()),'hd_bounds':list(hd.getchannel('A').point(lambda v:255 if v>=128 else 0).getbbox()),'frame_count':1,'origin':[0,0],'generated_art_repainted':False}

def synth(name,duration,seed,mode):
 rate=22050;rng=random.Random(seed);count=round(rate*duration);phase=0;slow=0;v=[]
 for i in range(count):
  u=i/(count-1);t=i/rate;noise=rng.uniform(-1,1);slow=slow*.90+noise*.10
  if mode=='warning':freq=440+220*int(u*2);signal=math.sin(phase)*.60+math.sin(phase*2)*.15;env=math.sin(math.pi*u)**1.4
  elif mode=='shot':freq=440*(1-u)**2+65;signal=math.sin(phase)*.5+noise*.20+math.sin(phase*2.13)*.13;env=math.exp(-5*u)
  elif mode=='death':freq=75-50*u;signal=slow*.6+noise*.18+math.sin(phase)*.25;env=math.exp(-4.5*u)
  else:
   notes=[294,370,440,587] if mode=='victory' else [220,294,440];freq=notes[min(len(notes)-1,int(u*len(notes)))];signal=math.sin(phase)*.65+math.sin(phase*2)*.12;env=min(1,(u*len(notes)%1)*20)*(1-u)**.6
  phase+=2*math.pi*freq/rate;env*=min(1,t/.004)*min(1,(count-1-i)/(rate*.005));v.append(signal*max(0,env))
 peak=max(abs(x) for x in v);target=.48 if mode=='warning' else .62;pcm=[round(x/peak*32767*target) for x in v];p=ROOT/'audio'/f'{name}.wav'
 with wave.open(str(p),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(rate);w.writeframes(struct.pack('<'+'h'*count,*pcm))
 return {'path':str(p.relative_to(ROOT)),'sha256':hashfile(p),'sample_rate':rate,'bits':16,'channels':1,'samples':count,'seconds':count/rate,'seed':seed,'peak':max(abs(x) for x in pcm),'recipe':'deterministic seeded chirp/noise, original synthesis, no recordings'}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--palette',type=Path,default=ROOT.parents[1]/'data/misc/PALETTE_DAT');ap.add_argument('--audio-only',action='store_true');a=ap.parse_args();is_boss='boss' in ROOT.name;stage=int(ROOT.name[-1]);sounds={}
 sound_specs=[('warning',.36,'warning'),('shot',.20,'shot'),('death',.95,'death')] if is_boss else [('approach',.78,'tone'),('target_alarm',.42,'warning'),('boss_alarm',.65,'warning'),('salvage',.32,'tone'),('victory',1.10,'victory')]
 for i,(n,d,m) in enumerate(sound_specs):sounds[n]=synth(n,d,stage*733+i,m)
 (ROOT/'audio-recipe.json').write_text(json.dumps(sounds,indent=2)+'\n')
 if a.audio_only:return
 pal=palette(a.palette);report={'palette_sha256':hashfile(a.palette),'ordinary_palette_entries_only':True,'audio':sounds}
 if is_boss:
  report['unit']=footprint('unit',(104,72 if stage==3 else 64),pal);report['shell']=footprint('shell',(8,8),pal)
 else:
  report['target']=footprint('target',(32,32),pal);p=ROOT/'art/terrain-source-v1.png';source=Image.open(p).convert('RGBA');assert source.getchannel('A').getextrema()[0]>=128,'terrain must be fully opaque'
  hd=ImageOps.fit(source,(1152,2048),Image.Resampling.LANCZOS);low=sd(hd,(288,512),pal);tiles=0
  for reverse in [False,True]:
   hi=ImageOps.flip(hd) if reverse else hd;lo=ImageOps.flip(low) if reverse else low
   for row in range(16):
    for col in range(9):
     hi.crop((col*128,row*128,(col+1)*128,(row+1)*128)).save(ROOT/'art'/f'tile-{tiles:03}-hd.png');lo.crop((col*32,row*32,(col+1)*32,(row+1)*32)).save(ROOT/'art'/f'tile-{tiles:03}-sd.png');tiles+=1
  for im in [hd,low]:assert im.crop((0,im.height-1,im.width,im.height)).tobytes()==ImageOps.flip(im).crop((0,0,im.width,1)).tobytes()
  # Briefing is a truthful wide crop of the generated terrain, not new artwork.
  briefing=ImageOps.fit(source,(1280,800),Image.Resampling.LANCZOS);briefing.save(ROOT/'art/briefing-hd.png');sd(briefing,(320,200),pal).save(ROOT/'art/briefing-sd.png');low.save(ROOT/'art/terrain-preview-sd.png');hd.save(ROOT/'art/terrain-preview-hd.png')
  report['terrain']={'master_sha256':hashfile(p),'master_size':list(source.size),'logical_joined_size':[288,512],'hd_joined_size':[1152,2048],'tiles':tiles,'period_rows':32,'repeat':'forward16 rows then reflected16 rows, both periodboundaries identical','joined_before_quantizing_and_splitting':True,'seam_checks':True,'briefing':'320x200 /1280x800 central wide crop from same genuine terrain master'}
 (ROOT/'asset-report.json').write_text(json.dumps(report,indent=2)+'\n');print(ROOT.name,'assets/sounds ready')
if __name__=='__main__':main()
