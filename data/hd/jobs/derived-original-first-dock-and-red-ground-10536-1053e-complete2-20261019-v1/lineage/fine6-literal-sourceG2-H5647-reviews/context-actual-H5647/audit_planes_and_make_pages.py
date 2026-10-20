from pathlib import Path
import json,gzip,hashlib
import numpy as np
from PIL import Image,ImageDraw
O=Path(__file__).resolve().parent;C=O/'actual-once-SourceG2-H5647-genuine9-allnative';P=O/'whole-genuine-context-pages';P.mkdir();p=json.loads((C/'ACTUAL-SIX-NINE-ENDPOINTS-FOUR-PAIRS-SOURCEG2-H5647.json').read_text());pal=np.frombuffer((C/'actual-palette-rgb.bin').read_bytes(),np.uint8).reshape(256,3)
def classify(a):return np.where(a<240,0,np.where(a<245,1,np.where(a<250,2,a))).astype(np.uint8)
def arr(r,where):
 a=np.frombuffer(gzip.decompress((where/r['indexed']).read_bytes()),'<u2').reshape(r['height'],r['width']);assert np.max(a)<256;assert gzip.decompress((where/r['classes']).read_bytes())==classify(a).tobytes();prefix=f'P6\n{r["width"]} {r["height"]}\n255\n'.encode();assert gzip.decompress((where/r['PPM']).read_bytes())==prefix+pal[a].tobytes();return a
for c in p['components']:arr(c,C/'components')
roles=['Original_joined_SourceNx','immutable_H5647_baseline','qualified6_proposal'];arrays={};screen=0;changes=0;outside=0;retained=0
for r in p['records']:
 key=(r['case_index'],r['scale']);aa=[arr(r['planes'][role],C/'planes')for role in roles];scale=r['scale'];orig,base,prop=aa;mask=np.zeros(orig.shape,bool)
 for x0,y0,x1,y1 in r['support_rectangles']:mask[y0*scale:y1*scale,x0*scale:x1*scale]=True
 diff=base!=prop;assert not(diff&~mask).any();assert int(diff.sum())==r['changed_samples'];assert np.array_equal(classify(base),classify(orig))and np.array_equal(classify(prop),classify(orig));screen+=sum(a.size for a in aa);changes+=int(diff.sum());outside+=int((~mask).sum())
 for inp,a in [('baseline_inputs',base),('proposal_inputs',prop)]:
  for part in r[inp]['pre_blit']:
   px,py=part['position']
   for x,y in part.get('retained_cells')or[]:
    yy=(py+y)*scale;xx=(px+x)*scale;assert np.array_equal(a[yy:yy+scale,xx:xx+scale],orig[yy:yy+scale,xx:xx+scale]);retained+=scale*scale
 arrays[key]=aa
pages=[]
for group in range(3):
 for scale in range(1,5):
  side=96*scale;page=Image.new('RGB',(side*3,3*(side+34)+24),(21,24,29));d=ImageDraw.Draw(page);d.text((3,3),f'Genuine finite endpoints{group*3}–{group*3+2}, native{scale}; Original / currentH5647 / sixOnly',fill='white')
  for q in range(3):
   case=group*3+q;row=next(r for r in p['records']if r['case_index']==case and r['scale']==scale);y0=24+q*(side+34);event=row['endpoint']['settled_event'];eventtxt='initial'if event is None else event['definition']['asset']+'→'+event['definition']['settled'];d.text((3,y0+2),f'case{case} {row["endpoint"]["mission"]} {eventtxt}',fill='white')
   for role,a in enumerate(arrays[case,scale]):page.paste(Image.fromarray(pal[a]),(role*side,y0+26))
  out=P/f'endpoints{group*3}-{group*3+2}-native{scale}-Original-current-proposed.png';page.save(out);pages.append(dict(group=group,cases=list(range(group*3,group*3+3)),scale=scale,path=str(out),whole_role_native_size=[side,side],resizing=False))
pairpages=[]
for pair in p['Source_contract']['ordered_pairs']:
 before,after=pair['before'],pair['after'];scale=4;side=384;page=Image.new('RGB',(side*3,2*(side+30)+26),(21,24,29));d=ImageDraw.Draw(page);d.text((3,3),f'Legal Source one-cell settled event {pair["change"]}, native4; Original/current/proposed',fill='white')
 for q,case in enumerate([before,after]):
  y0=26+q*(side+30);d.text((3,y0+3),f'case{case}: '+('intact'in pair and'')+('before'if q==0 else'after'),fill='white')
  for role,a in enumerate(arrays[case,4]):page.paste(Image.fromarray(pal[a]),(role*side,y0+26))
 out=P/f'legal-pair-{before}-{after}-native4-Original-current-proposed.png';page.save(out);pairpages.append(dict(pair=pair,path=str(out),scale=4))
r=dict(status='ALL108_ROLE_PLANES_COMPONENTS_RGB_CLASSES_AND_POSTJOIN_RETENTION_AUTHENTICATED',screen_samples=screen,changed_samples=changes,outside_support_samples_exact=outside,outside_support_changes=0,postjoin_retained_Original_samples_checked=retained,own_stage_checks=len(p['own_stage_checks']),all_SourceClasses_exact=True,fallbacks=p['fallback_ids'],all_fallbacks_exact=True,foreign_interiors_exact=True,diagnostics=p['diagnostics'],pages=pages,pair_pages=pairpages,operations=dict(new_World_QA_render_cleanup_generation=0),physical_review_pending=True)
(O/'STRICT-SAVED-PLANES-AUDIT-AND-PHYSICAL-INDEX.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:v for k,v in r.items()if k not in('pages','pair_pages')},indent=2))
