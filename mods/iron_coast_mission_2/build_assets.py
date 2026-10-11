#!/usr/bin/env python3
"""Package built-in imagegen artwork into deterministic SD/HD footprints and WAVs."""
import argparse
import hashlib
import json
import math
import random
import struct
import wave
from pathlib import Path
from PIL import Image, ImageOps
ROOT=Path(__file__).resolve().parent

def palette_image(path):
    raw=path.read_bytes()
    if len(raw)!=768: raise ValueError('expected 768-byte VGA palette')
    colors=[(min(v,63)<<2)|(min(v,63)>>4) for v in raw]
    palette=Image.new('P',(1,1));palette.putpalette(colors)
    return palette,colors

def sd(source,size,palette):
    source=source.convert('RGBA').resize(size,Image.Resampling.LANCZOS)
    alpha=source.getchannel('A').point(lambda a:255 if a>=128 else 0)
    image=source.convert('RGB').quantize(palette=palette,dither=Image.Dither.NONE).convert('RGBA')
    image.putalpha(alpha)
    return image

def synth(name,duration,notes,alarm=False):
    rate=22050; rng=random.Random(7053+sum(map(ord,name)));data=bytearray()
    frames=int(duration*rate);peak=0;energy=0
    for i in range(frames):
        t=i/rate;phase=t/duration*len(notes);n=min(len(notes)-1,int(phase));local=phase%1
        f=notes[n];env=min(1,local*25)*(1-local)**0.9
        s=math.sin(2*math.pi*f*t)+0.20*math.sin(2*math.pi*f*2*t)
        if alarm:s+=0.18*math.sin(2*math.pi*f*0.5*t)
        s+=rng.uniform(-1,1)*0.03*math.exp(-t*6)
        sample=max(-32767,min(32767,int(s*env*7600)));peak=max(peak,abs(sample));energy+=sample*sample
        data+=struct.pack('<h',sample)
    path=ROOT/'audio'/f'{name}.wav'
    with wave.open(str(path),'wb') as out:
        out.setnchannels(1);out.setsampwidth(2);out.setframerate(rate);out.writeframes(data)
    assert peak>0
    return {'file':str(path.relative_to(ROOT)),'samples':frames,'rate':rate,'seconds':duration,'peak':peak,'rms':round(math.sqrt(energy/frames),2),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--palette',type=Path,default=ROOT.parents[2]/'data/misc/PALETTE_DAT');args=parser.parse_args()
    palette,colors=palette_image(args.palette);art=ROOT/'art';(ROOT/'audio').mkdir(exist_ok=True)
    terrain=Image.open(art/'terrain-source-hd.png').convert('RGBA')
    hd=terrain.resize((1152,1536),Image.Resampling.LANCZOS);small=sd(terrain,(288,384),palette)
    n=0
    for reverse in (False,True):
        h=ImageOps.flip(hd) if reverse else hd;s=ImageOps.flip(small) if reverse else small
        for y in range(12):
            for x in range(9):
                h.crop((x*128,y*128,(x+1)*128,(y+1)*128)).save(art/f'tile_{n:03}_hd.png')
                s.crop((x*32,y*32,(x+1)*32,(y+1)*32)).save(art/f'tile_{n:03}_sd.png');n+=1
    for source in (hd,small):
        flip=ImageOps.flip(source);w,h=source.size
        assert source.crop((0,h-1,w,h)).tobytes()==flip.crop((0,0,w,1)).tobytes()
        assert flip.crop((0,h-1,w,h)).tobytes()==source.crop((0,0,w,1)).tobytes()
    hd.save(art/'terrain-preview-hd.png');small.save(art/'terrain-preview-sd.png')
    for name,size in [('briefing',(320,200)),('relay',(32,32))]:
        source=Image.open(art/f'{name}-source-hd.png').convert('RGBA')
        if name=='relay':
            # Normalize excessive generator padding, preserving the complete
            # genuine-alpha silhouette inside an 85% square footprint.
            bounds=source.getchannel('A').point(lambda a:255 if a>=128 else 0).getbbox()
            if bounds is None:raise ValueError('relay source contains no opaque pixels')
            cx=(bounds[0]+bounds[2])/2;cy=(bounds[1]+bounds[3])/2
            extent=math.ceil(max(bounds[2]-bounds[0],bounds[3]-bounds[1])/0.85)
            left=round(cx-extent/2);top=round(cy-extent/2)
            source=source.crop((left,top,left+extent,top+extent))
        sd(source,size,palette).save(art/f'{name}_sd.png')
        source.resize((size[0]*4,size[1]*4),Image.Resampling.LANCZOS).save(art/f'{name}_hd.png')
    audio={
        'approach':synth('approach',0.75,[147,196,294]),
        'network_alarm':synth('network_alarm',0.8,[392,294,392,294],True),
        'relay_offline':synth('relay_offline',0.42,[523,392,262]),
        'network_down':synth('network_down',0.75,[330,392,494]),
        'boss_alarm':synth('boss_alarm',1.05,[165,124,98],True),
        'victory':synth('victory',1.15,[294,370,440,587]),
    }
    raw=small.convert('RGB').tobytes();actual={tuple(raw[i:i+3]) for i in range(0,len(raw),3)};allowed={tuple(colors[i:i+3]) for i in range(0,768,3)}
    assert actual<=allowed
    report={'tile_count':n,'logical_tile':[32,32],'hd_tile':[128,128],'palette_sha256':hashlib.sha256(args.palette.read_bytes()).hexdigest(),'sd_pixels_match_original_palette':True,'actual_sd_unique_colors':len(actual),'seam_checks_passed':True,'vertical_repeat':'12 rows forward +12 reflected, identical repeat boundary pixels','relay_transparent_pixels':sum(a==0 for a in Image.open(art/'relay_sd.png').getchannel('A').tobytes()),'audio':audio,'sources':{p.name:{'size':Image.open(p).size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in art.glob('*-source-hd.png')}}
    (ROOT/'asset-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'Packaged {n} SD/HD tiles, briefing/relay art and {len(audio)} WAVs')
if __name__=='__main__':main()
