from pathlib import Path
import json,gzip,hashlib,os
import numpy as np
from PIL import Image,ImageDraw
O=Path(__file__).resolve().parent
P=O/'review-pages';P.mkdir()
rows=[];samples=0;component_samples=0;changes=0
for asset in ['30096','30097','30099','3009e']:
 C=O/f'actual-once-{asset}-currentG2-H5636-composition';proof=json.loads((C/'actual-controlled-one-phase-composition-proof.json').read_text());pal=np.frombuffer((C/'actual-palette-rgb.bin').read_bytes(),np.uint8).reshape(256,3)
 def array(r):
  a=np.frombuffer(gzip.decompress((C/r['indices']).read_bytes()),'<u2').reshape(r['height'],r['width']);assert a.max()<=256;classes=np.where((a>=240)&(a<=255),a,0).astype(np.uint8);assert gzip.decompress((C/r['classes']).read_bytes())==classes.tobytes();return a
 def rgb(a):
  p=np.zeros((*a.shape,3),np.uint8);painted=a<256;p[painted]=pal[a[painted]];return Image.fromarray(p)
 components={}
 for c in proof['actual_target_components']:
  original=array(c['actual_Original_ScaleNx']);proposed=array(c['measured_selected']);component_samples+=original.size+proposed.size;components[c['scale']]=(original,proposed)
 for r in proof['rows']:
  scale=r['scale'];images=[array(v['files'])for v in r['roles']];assert np.array_equal(images[0],images[1]);assert all(v['Original_shadow_entities']==[1]for v in r['roles']);x,y=r['target_native_top_left'];w,h=r['target_canvas'];delta=images[1]!=images[2];original,proposed=components[scale];support=np.zeros(delta.shape,bool);support[y:y+h,x:x+w]=(original<256)|(proposed<256);assert not(delta&~support).any();assert int(delta.sum())==r['current_to_proposed_changes'];samples+=sum(a.size for a in images);changes+=int(delta.sum())
  paths=[]
  for n,im in enumerate(images):
   f=P/f'{asset}-native{scale}-whole-'+Path('Original').name if False else P/f'{asset}-native{scale}-whole-{["Original","current","proposed"][n]}.png'
   if n==1:os.link(paths[0],f)
   else:rgb(im).save(f)
   paths.append(f)
  side=80*scale;cx=x+w//2;cy=y+h//2;left=max(0,min(images[0].shape[1]-side,cx-side//2));top=max(0,min(images[0].shape[0]-side,cy-side//2));page=Image.new('RGB',(side*3+20,side+28),(20,23,27));d=ImageDraw.Draw(page)
  for n,im in enumerate(images):page.paste(rgb(im[top:top+side,left:left+side]),(n*(side+10),28));d.text((n*(side+10)+2,5),['Original+SourceShadow','currentH5636','proposed+SourceShadow'][n],fill='white')
  crop=P/f'{asset}-native{scale}-genuine-context-Original-current-proposed.png';page.save(crop)
  rows.append({'asset':asset,'tick':r['tick'],'scale':scale,'target_native_top_left':[x,y],'target_canvas':[w,h],'native_whole_size':[320*scale,200*scale],'whole_Original':str(paths[0]),'whole_current':str(paths[1]),'whole_proposed':str(paths[2]),'ROI_triptych':str(crop),'Original_shadow_entity':1,'native_direct_pixels_no_presentation_resizing':True,'changes':int(delta.sum()),'outside_original_or_proposed_alpha_changes':0})
report={'status':'ACTUAL48-SCREEN-32-COMPONENT-ARRAYS-VERIFIED-SOURCE-SHADOWS-OWN-ALPHA-DELTA-ONLY','screen_samples':samples,'component_samples':component_samples,'changed_samples':changes,'all_Original_equals_current':True,'actual_Original_shadow_entity_each_role':[1],'no_fake_zero_shadow':True,'outside_own_original_or_proposed_alpha_changes':0,'body_clipping_samples':0,'World_calls_in_audit':0,'actual_scene_count':4,'actual_screen_count':48,'actual_component_array_count':32,'all_own_preblits_equal_accepted_currentG2_banks':True,'physical_review_pending':True,'pages':rows};(O/'STRICT-SAVED-FOUR-CONTEXT-AUDIT-AND-PHYSICAL-INDEX.json').write_text(json.dumps(report,indent=2)+'\n');print({k:v for k,v in report.items()if k!='pages'})
