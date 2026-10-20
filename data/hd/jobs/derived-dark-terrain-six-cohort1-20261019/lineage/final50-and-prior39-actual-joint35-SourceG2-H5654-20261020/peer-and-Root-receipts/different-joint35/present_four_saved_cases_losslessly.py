from pathlib import Path
import json,hashlib
from PIL import Image,ImageDraw
import numpy as np
O=Path(__file__).resolve().parent;R=O.parents[1];P=R/'.reference/hd-all89-joint35-SourceG2-H5654-context-author-20261020-v1';I=json.loads((P/'FROZEN-ALL89-GENUINE35-ALLNATIVE-CONTEXT-PEER-INTERFACE.json').read_text());D=O/'exact-saved-case17to20-role-columns';D.mkdir();out=[]
for case in range(17,21):
 page=next(x for x in I['whole_endpoint_pages']if x['case_index']==case);im=Image.open(page['page']['path']).convert('RGB')
 for pair in range(2):
  roles=I['roles'][pair*2:pair*2+2];canvas=Image.new('RGB',(1040,1184),(20,28,38));draw=ImageDraw.Draw(canvas);positions=[]
  for j,role in enumerate(roles):
   y=0
   for scale in range(1,5):
    pane=next(x for x in page['panes']if x['scale']==scale and x['role']==role);x0,y0,w,h=pane['xywh'];crop=im.crop((x0,y0,x0+w,y0+h));assert crop.size==(w,h);x=8+j*520;draw.text((x,y),f'case{case} native{scale} {role}',fill='white');canvas.paste(crop,(x,y+20));positions.append(dict(scale=scale,role=role,source_xywh=pane['xywh'],output_xywh=[x,y+20,w,h]));y+=h+24
   assert y<=1184
  p=D/f'case{case}-rolepair{pair}-all4-exact-whole-saved-bodies.png';canvas.save(p);dec=np.asarray(Image.open(p));src=np.asarray(im)
  for z in positions:
   sx,sy,w,h=z['source_xywh'];x,y,ww,hh=z['output_xywh'];assert np.array_equal(dec[y:y+h,x:x+w],src[sy:sy+h,sx:sx+w])
  out.append(dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),source_page=page['page'],positions=positions))
(O/'EXACT-64-SAVED-BODY-DISPLAY-CROPS-NO-RESAMPLE-OR-NEW-RENDERER.json').write_text(json.dumps(dict(status='PASS_8_LOSSLESS_DISPLAY_PANELS_64_COMPLETE_SAVED_BODIES',images=out,new_generated_pixels=0,new_renderer_QA_calls=0),indent=2)+'\n');print('8 exact panels, 64 complete unchanged bodies')
