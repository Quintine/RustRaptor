from pathlib import Path
from PIL import Image
import json,hashlib,re,shutil,sys
P=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
wave=int(sys.argv[1]);stem=f'sector_3_wave_{wave}';receipt=json.loads((P/'provenance'/f'{stem}-provider-primitive.json').read_text());assert receipt['outcome']=='success';m=re.search(r' as (/[^\n]+\.png) by default',receipt['output_hint']);assert m;source=Path(m[1]);master=P/'masters'/f'{stem}-untouched-master.png';assert not master.exists();shutil.copy2(source,master)
im=Image.open(master);rgb=im.convert('RGB');w,h=rgb.size;desired=1280/800
if w/h>desired:
 cw=h*desired;box=((w-cw)/2,0,(w+cw)/2,h)
else:
 ch=w/desired;box=(0,(h-ch)/2,w,(h+ch)/2)
hd=rgb.resize((1280,800),Image.Resampling.LANCZOS,box=box);sd=hd.resize((320,200),Image.Resampling.LANCZOS)
hdp=P/'data/briefings'/f'{stem}_hd.png';sdp=P/'data/briefings'/f'{stem}_sd.png';assert not hdp.exists() and not sdp.exists();hd.save(hdp);sd.save(sdp)
preview=P/'provenance'/f'{stem}-132x70-centered-preview.png';ch=1280/(132/70);hd.resize((132,70),Image.Resampling.LANCZOS,box=(0,(800-ch)/2,1280,(800+ch)/2)).save(preview)
record={'wave':wave,'method':'untouched builtin generated master -> explicit centered aspect crop/resize LANCZOS1280x800 -> same-composition LANCZOS320x200','master':{'path':str(master.relative_to(P)),'sha256':sha(master),'size':list(im.size),'mode':im.mode},'provider_source_path':str(source),'source_master_bytes_exact':source.read_bytes()==master.read_bytes(),'HD_float_source_crop_box':list(box),'HD':{'path':str(hdp.relative_to(P)),'sha256':sha(hdp),'size':[1280,800]},'SD':{'path':str(sdp.relative_to(P)),'sha256':sha(sdp),'size':[320,200]},'small_center_crop_preview':{'path':str(preview.relative_to(P)),'sha256':sha(preview),'size':[132,70]},'prompt_sha256':sha(P/'provenance'/f'{stem}-prompt.txt'),'provider_receipt_sha256':sha(P/'provenance'/f'{stem}-provider-primitive.json'),'original_sprite_coverage_credit':False}
(P/'provenance'/f'{stem}-derivation.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2))
