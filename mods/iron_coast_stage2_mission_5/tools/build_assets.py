#!/usr/bin/env python3
"""Prepare game assets from unchanged generated masters and synthesize PCM cues.

Requires Pillow. Original Raptor reference images stay external. The original
palette is read only for ordinary-color SD quantization; final assets are local.
No generated RGB is retouched: whole-canvas proportional fit, resampling,
cropping into tiles and reflected terrain repetition are explicit derivatives.
"""
from pathlib import Path
import json,hashlib,math,random,struct,wave
from PIL import Image,ImageOps,ImageDraw
ROOT=Path(__file__).resolve().parent.parent
NUMBER=int(ROOT.name.rsplit('_',1)[1]);IS_BOSS='_boss_'in ROOT.name
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
write=lambda p,j:p.write_text(json.dumps(j,indent=2,sort_keys=True)+'\n')

def palette():
    path=ROOT.parents[1]/'data/misc/PALETTE_DAT'
    b=path.read_bytes();assert len(b)==768
    rgb=[(min(v,63)<<2)|(min(v,63)>>4)for v in b[:720]]
    image=Image.new('P',(1,1));image.putpalette(rgb+[0]*48)
    return image,{'source':'PALETTE_DAT','sha256':sha(path),'ordinary_indices':[0,239]}

def sd_quantize(image,pal):
    a=image.getchannel('A')if image.mode=='RGBA'else None
    # Duplicate palette0 in unused slots so quantization cannot create a reserved class.
    pal=pal.copy();p=pal.getpalette();p[720:768]=p[:3]*16;pal.putpalette(p)
    q=image.convert('RGB').quantize(palette=pal,dither=Image.Dither.NONE).convert('RGBA')
    if a is not None:q.putalpha(a)
    return q

def artwork():
    raw=ROOT/'sources/raw-v1.png';source=Image.open(raw).convert('RGBA');pal,binding=palette();files={}
    def save(name,img):
        p=ROOT/'art'/name;img.save(p);alpha=img.getchannel('A');mask=alpha.point(lambda a:255 if a>=128 else 0)
        files[name]={'size':list(img.size),'sha256':sha(p),'opaque_bounds':list(mask.getbbox())if mask.getbbox()else None,'transparent_pixels':sum(a<128 for a in alpha.get_flattened_data())}
    if IS_BOSS:
        logical=(112,56 if NUMBER==5 else 72);target=tuple(v*4 for v in logical)
        assert source.getchannel('A').getextrema()[0]==0 and source.getchannel('A').getextrema()[1]>=128,'Real generated alpha required'
        fit=ImageOps.contain(source,(target[0]-32,target[1]-32),Image.Resampling.LANCZOS)
        hd=Image.new('RGBA',target,(0,0,0,0));hd.alpha_composite(fit,((target[0]-fit.width)//2,(target[1]-fit.height)//2))
        sd=sd_quantize(hd.resize(logical,Image.Resampling.LANCZOS),pal)
        save('unit-hd.png',hd);save('unit-sd.png',sd)
        for name in ['unit-hd.png','unit-sd.png']:
            bounds=files[name]['opaque_bounds'];size=files[name]['size'];assert bounds and min(bounds[:2])>=2 and bounds[2]<size[0] and bounds[3]<size[1],name
        preview=Image.new('RGBA',(928,336),(24,32,42,255));preview.alpha_composite(hd,(8,32));preview.alpha_composite(sd.resize(target,Image.Resampling.NEAREST),(472,32));ImageDraw.Draw(preview).text((8,8),'HD4 and SD nearest4 — stable padded112px logical width',fill='white');preview.convert('RGB').save(ROOT/'art-preview.png')
        recipe={'logical_canvas':list(logical),'hd_scale':4,'origin':[0,0],'frames':1,'method':'Fit complete untouched RGBA master proportionally into fixed padded canvas; no silhouette crop, alpha removal or painted changes.'}
    else:
        assert source.getchannel('A').getextrema()==(255,255),'Terrain must be fully opaque'
        hd=source.resize((1152,1152),Image.Resampling.LANCZOS)
        # One joined conversion at each mode preserves every internal32px tile edge.
        sd=sd_quantize(hd.resize((288,288),Image.Resampling.LANCZOS),pal)
        for mode,base,step in [('hd',hd,128),('sd',sd,32)]:
            reflected=ImageOps.flip(base)
            joined=Image.new('RGBA',(base.width,base.height*2));joined.alpha_composite(base,(0,0));joined.alpha_composite(reflected,(0,base.height))
            for row in range(18):
                for col in range(9):
                    i=row*9+col;save(f'tile-{i:03}-{mode}.png',joined.crop((col*step,row*step,(col+1)*step,(row+1)*step)))
        briefing=ImageOps.fit(source,(1280,800),Image.Resampling.LANCZOS,centering=(0.5,0.5));save('briefing-hd.png',briefing);save('briefing-sd.png',sd_quantize(briefing.resize((320,200),Image.Resampling.LANCZOS),pal))
        preview=Image.new('RGBA',(1184,744),(24,32,42,255));preview.alpha_composite(hd.resize((576,576),Image.Resampling.LANCZOS),(8,32));preview.alpha_composite(sd.resize((576,576),Image.Resampling.NEAREST),(600,32));ImageDraw.Draw(preview).text((8,8),'HD terrain and SD nearest2 — joined atlas plus reflected repeat',fill='white');preview.convert('RGB').save(ROOT/'art-preview.png')
        assert ImageOps.flip(hd).crop((0,0,hd.width,1)).tobytes()==hd.crop((0,hd.height-1,hd.width,hd.height)).tobytes()
        recipe={'logical_tile':[32,32],'hd_scale':4,'columns':9,'unique_tiles':162,'master_tiles':81,'method':'Whole square master resized into one joined288px SD/1152px HD canvas; SD ordinary-palette quantization once; whole master vertical reflection creates exact adjacent edge rows, then32/128px tiles are cropped. Repeats have identical joining pixel rows, not an inferred zero luma seam.'}
    write(ROOT/'art-qa.json',{'raw_sha256':sha(raw),'raw_size':list(source.size),'ordinary_palette':binding,'recipe':recipe,'files':files,'visual_status':'Await actual indexed renderer inspection; file checks alone are not art approval.'})

def audio():
    rate=22050
    cues={'warning':(.28,620),'shot':(.19,310),'death':(.9,58)}if IS_BOSS else{'approach':(.45,410),'alarm':(.28,680),'hazard':(.22,820),'target_down':(.36,120),'victory':(.75,440)}
    result={}
    for at,(name,(duration,freq))in enumerate(cues.items()):
        seed=NUMBER*1000+(100 if IS_BOSS else 200)+at;rng=random.Random(seed);n=round(duration*rate);phase=0;low=0;samples=[]
        for i in range(n):
            t=i/rate;p=i/(n-1);noise=rng.uniform(-1,1);low=.88*low+.12*noise
            pitch=freq*(.7+.3*(1-p))if name in ['shot','death','target_down']else freq*(1+.2*p)
            phase+=2*math.pi*pitch/rate
            if name=='victory':v=(math.sin(2*math.pi*440*t)+.7*math.sin(2*math.pi*554.37*t)+.5*math.sin(2*math.pi*659.25*t))/2.2;envelope=math.sin(math.pi*p)**.6
            elif name=='death':v=.7*low+.2*noise+.35*math.sin(phase);envelope=math.exp(-4*p)
            elif name in ['shot','target_down']:v=.7*math.sin(phase)+.25*low+.08*noise;envelope=math.exp(-6*p)
            else:v=math.sin(phase)+.16*math.sin(2*phase);envelope=math.sin(math.pi*p)**2*(1 if int(t/.075)%2==0 else.35)
            envelope*=min(1,t/.004)*min(1,(n-1-i)/(rate*.008));samples.append(v*envelope)
        peak=max(abs(s)for s in samples);pcm=[round(s/peak*.68*32767)for s in samples]
        path=ROOT/'audio'/f'{name}.wav'
        with wave.open(str(path),'wb')as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(rate);w.writeframes(struct.pack('<'+'h'*n,*pcm))
        assert pcm[0]==pcm[-1]==0
        result[name]={'file':str(path.relative_to(ROOT)),'sha256':sha(path),'seed':seed,'sample_rate':rate,'channels':1,'bits':16,'duration_seconds':duration,'peak':max(map(abs,pcm)),'rms':(sum(x*x for x in pcm)/len(pcm))**.5,'first_last_samples':[pcm[0],pcm[-1]]}
    write(ROOT/'audio-recipe.json',{'generator':'tools/build_assets.py deterministic sinusoidal chirps, seeded noise and faded envelopes; no recorded audio or third-party samples','files':result})

if __name__=='__main__':
    artwork();audio();print(ROOT.name,'assets and faded non-silent PCM cues prepared')
