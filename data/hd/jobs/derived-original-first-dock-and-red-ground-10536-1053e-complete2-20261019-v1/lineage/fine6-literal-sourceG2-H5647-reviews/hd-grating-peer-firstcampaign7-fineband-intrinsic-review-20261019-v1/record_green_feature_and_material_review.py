from pathlib import Path
import json,hashlib,struct
import numpy as np
from PIL import Image,ImageDraw
O=Path(__file__).resolve().parent;R=O.parent.parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def save(name,v):p=O/name;assert not p.exists();p.write_text(json.dumps(v,indent=2)+'\n');return p
p=R/'.reference/hd-firstcampaign1059e-and105a4-105a7-Original-primary-author-20261019-v1/pair105a4-105a7/actual-once-final-current-SourceG2';b=next(v for v in json.loads((p/'actual-indexed-source-and-scales.json').read_text())if v['asset']=='105a4');src=np.array(b['source']['indices'],dtype='u2').reshape(32,32);act=np.array(b['scales'][0]['indices'],dtype='u2').reshape(32,32);pal=np.frombuffer((R/'data/misc/PALETTE_DAT').read_bytes(),'u1').astype('u2');pal=((pal<<2)|(pal>>4)).astype('u1').reshape(256,3)
green=lambda a:(pal[a][:,:,1]>pal[a][:,:,0])&(pal[a][:,:,1]>pal[a][:,:,2]);mask=green(src);actual=green(act);seen=set();groups=[]
for y,x in zip(*np.nonzero(mask)):
 if(int(y),int(x))in seen:continue
 stack=[(int(y),int(x))];seen.add(stack[0]);cells=[]
 while stack:
  yy,xx=stack.pop();cells.append([xx,yy])
  for dy,dx in [(-1,0),(1,0),(0,-1),(0,1)]:
   loc=(yy+dy,xx+dx)
   if 0<=loc[0]<32 and 0<=loc[1]<32 and mask[loc]and loc not in seen:seen.add(loc);stack.append(loc)
 groups.append({'complete_Source_green_component':sorted(cells),'Source_cell_count':len(cells),'native1_green_survivors':sum(int(actual[yy,xx])for xx,yy in cells),'cells':[{'xy':[xx,yy],'Source_index':int(src[yy,xx]),'Source_RGB':pal[src[yy,xx]].tolist(),'actual_native1_index':int(act[yy,xx]),'actual_native1_RGB':pal[act[yy,xx]].tolist(),'actual_still_green':bool(actual[yy,xx])}for xx,yy in sorted(cells)]})
# Complete bodies, nearest-neighbor16 for exact native1 visual comparison only.
page=Image.new('RGB',(1056,560),(22,24,27));d=ImageDraw.Draw(page);d.text((10,10),'105a4 complete Original32 left / ACTUAL final native1 right; exact NN16 diagnostic',fill='white');page.paste(Image.fromarray(pal[src]).resize((512,512),Image.Resampling.NEAREST),(8,38));page.paste(Image.fromarray(pal[act]).resize((512,512),Image.Resampling.NEAREST),(536,38));im=O/'FILE-ONLY-105a4-WHOLE-ORIGINAL-VS-ACTUAL-NATIVE1-NN16.png';page.save(im);readback=np.asarray(Image.open(im));assert np.array_equal(readback[38:550,8:520],np.repeat(np.repeat(pal[src],16,0),16,1));assert np.array_equal(readback[38:550,536:1048],np.repeat(np.repeat(pal[act],16,0),16,1))
proof=save('READONLY-105a4-COMPLETE-GENUINE-GREEN-FEATURE-GROUPS-NATIVE1-LOSS.json',{'status':'SOURCE_COLOR_ROLE_LOSS_DOCUMENTED_NOT_AN_EXACT_PALETTE_ID_REQUIREMENT','Source_green_cells':int(mask.sum()),'native1_Source_support_still_green':int(np.count_nonzero(mask&actual)),'all_connected_Source_green_feature_groups':groups,'zero_surviving_green_components':sum(g['native1_green_survivors']==0 for g in groups),'whole_exact_NN16_visual_comparison':{'path':str(im),'sha256':sha(im)},'reason':'Several genuine green remnants disappear into gray/brown atnative1, including moderate-bright green, so whole existing plant-remnant color features are lost rather than merely reindexed in another shade ofgreen. Sourcegray/brown colors may vary; this is a visual role judgment, not a globalordinary index identity rule.','new_art_cleanup_QA_engine_calls':0})
print(json.dumps({'proof_sha256':sha(proof),'whole_diagnostic':str(im),'groups':len(groups),'zero_green_groups':sum(g['native1_green_survivors']==0 for g in groups)}))
