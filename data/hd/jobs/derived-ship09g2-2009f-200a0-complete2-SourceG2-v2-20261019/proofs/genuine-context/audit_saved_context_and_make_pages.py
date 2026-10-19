from pathlib import Path
import json,gzip,hashlib
import numpy as np
from PIL import Image,ImageDraw
R=Path('/home/quintine/Projects/RaptorReplica/RustRaptor');O=R/'.reference/hd-SHIP09G2-currentG2-genuine-S2W9-H5636-context-20261019-v1';C=O/'actual-once-currentG2-H5636-allnative-composition';P=O/'review-pages';P.mkdir(exist_ok=False);proof=json.loads((C/'actual-controlled-one-phase-composition-proof.json').read_text());pal=np.frombuffer((C/'actual-palette-rgb.bin').read_bytes(),np.uint8).reshape(256,3)
def ar(r):
 a=np.frombuffer(gzip.decompress((C/r['indices']).read_bytes()),'<u2').reshape(r['height'],r['width']);assert np.max(a)<=256;cl=np.where((a>=240)&(a<=255),a,0).astype(np.uint8);assert gzip.decompress((C/r['classes']).read_bytes())==cl.tobytes();return a
def rgb(a):
 b=np.zeros((*a.shape,3),np.uint8);v=a<256;b[v]=pal[a[v]];return Image.fromarray(b)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
components={(c['frame'],c['scale']):(ar(c['actual_Original_ScaleNx']),ar(c['measured_selected']))for c in proof['actual_target_components']};rows=[];samples=0;changed=0;gray=[]
rawbank=json.loads((R/'.reference/hd-SHIP09G2-complete2-Original-primary-author-20261019-v1/actual-currentG2-intrinsic2/actual-indexed-source-and-scales.json').read_text())
for r in proof['rows']:
 f=r['frame'];asset=f'{0x2009f+f:05x}';s=r['scale'];a=[ar(z['files'])for z in r['roles']];assert np.array_equal(a[0],a[1]);assert all(z['Original_shadow_entities']==[]for z in r['roles']);x,y=r['target_native_top_left'];w,h=r['target_canvas'];diff=a[1]!=a[2];support=np.zeros(diff.shape,bool);original,proposal=components[f,s];support[y:y+h,x:x+w]=(original<256)|(proposal<256);assert not(diff&~support).any();assert int(diff.sum())==r['current_to_proposed_changes'];samples+=sum(z.size for z in a);changed+=int(diff.sum());full=[]
 for role,z in enumerate(a):
  wp=P/f'{asset}-native{s}-whole-'+['Original','current','proposed'][role]+'.png' if False else P/f"{asset}-native{s}-whole-{['Original','current','proposed'][role]}.png"
  rgb(z).save(wp);full.append(dict(role=['Original','current','proposed'][role],path=str(wp),sha256=sha(wp),dimensions=[320*s,200*s],physical_review_pending=True))
 side=96*s;cx=x+w//2;cy=y+h//2;left=max(0,min(a[0].shape[1]-side,cx-side//2));top=max(0,min(a[0].shape[0]-side,cy-side//2));page=Image.new('RGB',(side*3+20,side+28),(20,23,27));d=ImageDraw.Draw(page)
 for role,z in enumerate(a):page.paste(rgb(z[top:top+side,left:left+side]),(role*(side+10),28));d.text((role*(side+10)+2,5),['Original no SourceShadow','current5636','proposed no SourceShadow'][role],fill='white')
 rp=P/f'{asset}-native{s}-ROI-Original-current-proposed.png';page.save(rp)
 if s==4:
  parent=np.array(rawbank[f]['scales'][3]['indices'],dtype=np.uint16).reshape(160,288);mask=(original<=31)&(parent<256);local=a[2][y:y+h,x:x+w];assert np.array_equal(pal[local[mask]],pal[parent[mask]]);assert not np.any(proposal[mask]>=256);gray.append(dict(asset=asset,actual_Source_gray_samples=int(mask.sum()),after_blend_proposed_matches_literal_parent_G2_gray_RGB=True,changed_gray_RGB_samples=0))
 rows.append(dict(frame=f,asset=asset,scale=s,whole_frames=full,ROI_page=str(rp),native_whole_size=[320*s,200*s],no_presentation_resizing=True,Source_shadow_field11=0,shadow_entities=[],tick=r['tick'],top_left=[x,y],target_canvas=[w,h]))
report=dict(status='ALL24_SAVED_SCREENS_AND16_COMPONENT_ARRAYS_AUTHENTICATED_OWN_ALPHA_ONLY_DELTA',screen_samples=samples,changed_samples=changed,outside_canvas_changes=0,outside_own_Source_or_proposal_alpha_changes=0,Original_controls_equal_current=True,Source_shadow_field11=0,Source_shadow_enabled=False,Source_shadow_not_invented=True,all4_own_preblits_equal_actual_G2_22686_bank=True,after_blend_gray_checks=gray,diagnostics=proof['diagnostics'],rows=rows,World_calls_in_audit=0,physical_review_pending=True)
(O/'STRICT-SAVED-CONTEXT-AUDIT-AND-PHYSICAL-INDEX.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items()if k!='rows'},indent=2))
