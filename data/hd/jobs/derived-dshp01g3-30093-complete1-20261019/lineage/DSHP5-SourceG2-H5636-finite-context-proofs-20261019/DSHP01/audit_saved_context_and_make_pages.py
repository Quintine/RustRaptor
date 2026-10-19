from pathlib import Path
import json,gzip,hashlib
import numpy as np
from PIL import Image,ImageDraw
O=Path(__file__).resolve().parent;C=O/'actual-once-currentG2-H5636-allnative-composition';P=O/'review-pages';P.mkdir();proof=json.loads((C/'actual-controlled-one-phase-composition-proof.json').read_text());pal=np.frombuffer((C/'actual-palette-rgb.bin').read_bytes(),np.uint8).reshape(256,3)
def array(r):
 a=np.frombuffer(gzip.decompress((C/r['indices']).read_bytes()),'<u2').reshape(r['height'],r['width']);assert np.max(a)<=256;c=np.where((a>=240)&(a<=255),a,0).astype(np.uint8);assert gzip.decompress((C/r['classes']).read_bytes())==c.tobytes();return a

def rgb(a):
 b=np.zeros((*a.shape,3),np.uint8);v=a<256;b[v]=pal[a[v]];return Image.fromarray(b)
components={}
for c in proof['actual_target_components']:components[c['scale']]=(array(c['actual_Original_ScaleNx']),array(c['measured_selected']))
rows=[];samples=0;changed=0
for r in proof['rows']:
 s=r['scale'];a=[array(z['files'])for z in r['roles']];assert np.array_equal(a[0],a[1]);assert all(z['Original_shadow_entities']==[1]for z in r['roles']);x,y=r['target_native_top_left'];w,h=r['target_canvas'];diff=a[1]!=a[2];support=np.zeros(diff.shape,bool);original,proposal=components[s];support[y:y+h,x:x+w]=(original<256)|(proposal<256);assert not(diff&~support).any();assert int(diff.sum())==r['current_to_proposed_changes'];samples+=sum(z.size for z in a);changed+=int(diff.sum());side=80*s;cx=x+w//2;cy=y+h//2;left=max(0,min(a[0].shape[1]-side,cx-side//2));top=max(0,min(a[0].shape[0]-side,cy-side//2));page=Image.new('RGB',(side*3+20,side+28),(20,23,27));d=ImageDraw.Draw(page)
 for role,z in enumerate(a):page.paste(rgb(z[top:top+side,left:left+side]),(role*(side+10),28));d.text((role*(side+10)+2,5),['Original+SourceShadow','current5636','proposed+SourceShadow'][role],fill='white')
 rp=P/f'30093-native{s}-genuine-ground-context-Original-current-proposed.png';page.save(rp);wp=P/f'30093-native{s}-whole-proposed.png';rgb(a[2]).save(wp)
 if s==4:
  rgb(a[0]).save(P/'30093-native4-whole-Original.png');rgb(a[1]).save(P/'30093-native4-whole-current.png')
 rows.append(dict(scale=s,ROI_page=str(rp),whole_proposed=str(wp),native_whole_size=[320*s,200*s],no_presentation_resizing=True,Source_ground_shadow_entity=1))
r=dict(status='ALL12_SCREEN_AND8_COMPONENT_ARRAYS_AUTHENTICATED_OWN_ALPHA_ONLY_DELTA',screen_samples=samples,changed_samples=changed,outside_canvas_changes=0,outside_own_Source_or_proposal_alpha_changes=0,Original_controls_equal_current=True,Source_ground_shadow_entity=1,Source_shadow_mask_not_regenerated=True,all4own_preblits_equal_actualG2_author_bank=True,diagnostics=proof['diagnostics'],pages=rows,World_calls_in_audit=0,physical_review_pending=True)
(O/'STRICT-SAVED-CONTEXT-AUDIT-AND-PHYSICAL-INDEX.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:v for k,v in r.items()if k!='pages'},indent=2))
