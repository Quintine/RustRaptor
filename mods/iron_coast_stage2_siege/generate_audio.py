#!/usr/bin/env python3
"""Reproduce authored mono PCM effects using seeded chirps and filtered noise."""
from pathlib import Path
import random,math,struct,wave,json,hashlib
root=Path(__file__).resolve().parent
role=root.name.split('_')[-1];index=['interceptor','siege','skimmer'].index(role)
rate=22050;files=[]
for name,duration in [('shot',[.095,.19,.14][index]),('warning',[.12,.26,.19][index]),('death',[.46,.72,.56][index])]:
 seed=8100+index*100+['shot','warning','death'].index(name);rng=random.Random(seed);count=round(rate*duration);values=[];phase=0.0;low=0.0
 for i in range(count):
  t=i/rate;u=i/max(count-1,1);noise=rng.uniform(-1,1);low=.9*low+.1*noise
  if name=='shot':
   start=[1600,440,1000][index];end=[460,90,280][index];phase+=2*math.pi*(end+(start-end)*(1-u)**2)/rate
   value=[.64,.45,.57][index]*math.sin(phase)+[.10,.34,.18][index]*noise+.14*math.sin(1.93*phase);env=math.exp(-[5.8,6.5,5.3][index]*u)
  elif name=='warning':
   phase+=2*math.pi*([670,310,540][index]+[390,240,420][index]*u)/rate;value=.7*math.sin(phase)+.1*math.sin(2*phase);env=math.sin(math.pi*u)**1.4*(.65+.35*math.sin(2*math.pi*[13,9,16][index]*t))
  else:
   phase+=2*math.pi*([130,85,110][index]*(1-u)+24)/rate;value=.55*low+.27*noise+.24*math.sin(phase);env=math.exp(-[5.5,4.7,5.1][index]*u)
  env*=min(1,t/.003)*min(1,(count-1-i)/(rate*.006));values.append(value*max(env,0))
 peak=max(abs(v)for v in values);amp=.4 if name=='warning'else(.62 if name=='shot'else.74);samples=[round(v/peak*amp*32767)for v in values];path=root/'audio'/f'{name}.wav'
 with wave.open(str(path),'wb')as out:out.setnchannels(1);out.setsampwidth(2);out.setframerate(rate);out.writeframes(struct.pack('<'+'h'*count,*samples))
 files.append({'file':str(path.relative_to(root)),'seed':seed,'duration_seconds':count/rate,'samples':count,'format':'mono PCM16 little endian','sample_rate':rate,'peak':max(abs(v)for v in samples),'rms':math.sqrt(sum(v*v for v in samples)/count)/32767,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
(root/'audio-recipe.json').write_text(json.dumps({'generator':'generate_audio.py standard Python seeded chirp/filtered noise; no original recordings','files':files},indent=2)+'\n')
print(root.name,'3 valid PCM WAV cues reproduced')
