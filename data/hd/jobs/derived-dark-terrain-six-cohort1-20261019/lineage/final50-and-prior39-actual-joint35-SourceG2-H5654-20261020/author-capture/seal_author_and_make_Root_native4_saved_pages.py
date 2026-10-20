"""Seal actual physical author review and re-present saved native4 planes losslessly."""
from pathlib import Path
import json,hashlib,gzip
import numpy as np
from PIL import Image,ImageDraw
P=Path(__file__).resolve().parent;Q=P/'actual-once-all89-genuine35-G2'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def pin(p):return {'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size}
def save(n,v):
 p=P/n
 with p.open('x')as f:json.dump(v,f,indent=2);f.write('\n')
 return pin(p)
I=P/'FROZEN-ALL89-GENUINE35-ALLNATIVE-CONTEXT-PEER-INTERFACE.json';assert sha(I)=='e28210fc3d91d960ca1ba7e8b12d1fe8e8b171fc912ef8aeb76e1dbe6ce1380e';i=json.loads(I.read_text())
X=json.loads(Path(i['actual_proof']['path']).read_text());auth=Path(i['authentication']['path']);assert sha(auth)==i['authentication']['sha256']
findings={}
for case in X['recipe']['cases']:
 ci=case['case_index']
 if ci==0:f='Whole9x8 dark industrial placement preserves wall ribs, triangular vents, roads and remnant. Quiet302e1 floor fits; dark6 fine material visible without changing broad topology.'
 elif ci in [1,4,33]:f='Dome/rim and small intact/settled fixture retain their Original positions. Mixed pre-existing refined rim versus coarse Original lower-left panels remains an inherited limit.'
 elif ci in [2,3,5]:f='Water-side white/red assembly and intact/damaged corner remain readable. New canopy/wreck fixture fits adjoining hull; stronger bright fine water grain is visible.'
 elif 6<=ci<=16 or ci==34:f='Canal, yellow perimeter, grille and intact/damaged breach align with Source. Final10521 quiet water avoids the previous high-contrast error; bright fine-grid shadow water adjoining coarser turquoise water is an explicit material-density limit.'
 elif 17<=ci<=20:f='Roads, crate grid, conduit and damaged single/both machinery placements remain aligned. New shoreline refinement changes material, preserving openings and shadows; inherited coarse lower-right fixtures remain visible.'
 elif ci==21:f='White remnant/diagonal stem, color stripe and neighboring dark triangular vents retain Source positions. Quiet floor joins dark material with localized inherited grain transitions.'
 elif 22<=ci<=29:f='All literal eight intact/destroyed combinations retain the three green fixture silhouettes, rubble placement and surrounding foliage. New cliff/ramp follows Original geometry; mixed coarse fixture geometry and fine terrain remain explicit.'
 else:f='Fine6 helipad/industrial perimeter and settled roof preserve Source placement. New second7 fixtures and yellow edges are readable; mixed low/high material density and coarse functional support remain visible.'
 findings[ci]=f
author=save('AUTHOR-QUALIFIED-ALL89-GENUINE35-ALL560-COMPLETE-ROLES-WITH-LIMITS.json',{
 'status':'AUTHOR_QUALIFIED_ALL35_WITH_LIMITS_HOLD0','author':'/root/industrial_remaining','interface':pin(I),'authentication':pin(auth),
 'physically_viewed':{'complete_saved_pages_original_detail':52,'complete_role_bodies':560,'native_scales':[1,2,3,4],
  'all_actual_whole_pages':i['whole_endpoint_pages'],'no_partial_or_contact_only_review':True},
 'per_endpoint':[{'case_index':c['case_index'],'label':c['label'],'verdict':'QUALIFIED_WITH_LIMITS','finding':findings[c['case_index']]}for c in X['recipe']['cases']],
 'finite_scope':X['recipe']['limits'],'additional_limits':['No complete-mission, natural timing, every-map placement or live palette-cycle claim. Source-retained pixels have zero generatedHD credit.',
 'Case8 trigger is same-family final10521 repair, so freshconsumer-final andall89 agree there; historical original10521HOLD is preserved rather than relabeled.',
 'Two optional down105dc/105e6 andright1052f/1050a are independently Source-verified oneactor legal states. Other recorded multi-actor infantry combinations are literal already-reviewed Source states.',
 'All89 private rows/raws were projected by file path only; full proposal normalization may add empty OriginalDetailCells on two unused2043f/20458 metadata rows, not a pixel change.'],
 'actual_calls':{'small_adapter_compile':1,'compile_exit':0,'constructor':1,'constructor_exit':0,'engine_build':0,'intrinsic_QA':0,'World':0,'generation_cleanup':0},
 'preserved_Source_prep_failure':pin(P/'PRESERVED-SOURCE-PREP-CASE8-VERSION-ONLY-ASSERTION-AND-FOCUSED-SUCCESSOR.json'),
 'different_and_Root_reviews_pending':True,'canonical_or_Git_changes':0})
pal=np.frombuffer((Q/'actual-palette-rgb.bin').read_bytes(),dtype='u1').reshape(256,3)
roles=['H5654_plus_consumer_cohort','H5654_plus_all89_joint'];records={x['case_index']:x for x in X['records']if x['scale']==4}
groups=[];group=[];x=8;y=40;shelf=0;maxw=1944;maxh=1640
for ci in range(35):
 rec=records[ci];w=rec['planes'][roles[0]]['width'];h=rec['planes'][roles[0]]['height'];ww=2*w+24;hh=h+32
 if ww+16>maxw:
  if group:groups.append(group);group=[];x=8;y=40;shelf=0
  groups.append([{'case_index':ci,'xy':[8,40],'width':ww,'height':hh}]);continue
 if x+ww+8>maxw:x=8;y+=shelf+16;shelf=0
 if y+hh+8>maxh:
  assert group;groups.append(group);group=[];x=8;y=40;shelf=0
 group.append({'case_index':ci,'xy':[x,y],'width':ww,'height':hh});x+=ww+16;shelf=max(shelf,hh)
if group:groups.append(group)
V=P/'Root-native4-lossless-review-pages';V.mkdir();pages=[]
for j,group in enumerate(groups):
 w=max(v['xy'][0]+v['width']+8 for v in group);h=max(v['xy'][1]+v['height']+8 for v in group)
 im=Image.new('RGB',(w,h),(20,28,38));draw=ImageDraw.Draw(im);draw.text((8,5),'CAPTURED5654 + CONSUMER FINAL (left) / ALL89 JOINT (right); exact whole native4 saved planes',fill='white');panes=[]
 for g in group:
  ci=g['case_index'];rec=records[ci];xx,yy=g['xy'];draw.text((xx,yy),f'case{ci:02} {X["recipe"]["cases"][ci]["consumer_cohort"]} | complete native4: CONSUMER FINAL / ALL89',fill='white')
  for k,role in enumerate(roles):
   row=rec['planes'][role];a=np.frombuffer(gzip.decompress((Q/'planes'/row['indexed']).read_bytes()),dtype='<u2').reshape(row['height'],row['width']);rgb=pal[a];px=xx+k*(row['width']+24);py=yy+24
   im.paste(Image.fromarray(rgb),(px,py));panes.append({'case_index':ci,'role':role,'xywh':[px,py,row['width'],row['height']],'actual_indexed':row['indexed']})
 path=V/f'ROOT-all89-native4-page{j:02}-complete-oldconsumer-vs-joint.png';im.save(path);decoded=np.asarray(Image.open(path))
 for pane in panes:
  px,py,ww,hh=pane['xywh'];row=records[pane['case_index']]['planes'][pane['role']];a=np.frombuffer(gzip.decompress((Q/'planes'/row['indexed']).read_bytes()),dtype='<u2').reshape(hh,ww);assert np.array_equal(decoded[py:py+hh,px:px+ww],pal[a])
 pages.append({'page':pin(path),'dimensions':list(im.size),'complete_panes':panes})
assert len([v for p in pages for v in p['complete_panes']])==70
root=save('ROOT-ALL35-NATIVE4-LOSSLESS-REVIEW-PAGE-INDEX.json',{'status':'FILE_ONLY_NATIVE4_PRESENTATION_ALL70_COMPLETE_BODIES_EXACT','actual_epoch':i['actual_epoch'],
 'author_qualification':author,'all35_cases':list(range(35)),'pages':pages,'new_renderer_QA_compile_World_calls':0})
files=[pin(p)for p in sorted(P.rglob('*'))if p.is_file()and p.name!='compose-all89-genuine35-currentG2']
guard=save('FROZEN-JOINT35-AUTHOR-ACTUAL-SAVED-PIXEL-AND-REVIEW-FILE-GUARD.json',{'status':'FROZEN_FINITE_JOINT35_SAVED_PACKET_EXCLUDING_COMPILED_BINARY','files':files,
 'different_Root_receipts_are_additive_only':True,'all_raw_files_are_hardlinks_no_full_data_copy':True})
print(json.dumps({'author':author,'Root_native4_pages':root,'Root_page_count':len(pages),'guard':guard,'guard_files':len(files)},indent=2))
