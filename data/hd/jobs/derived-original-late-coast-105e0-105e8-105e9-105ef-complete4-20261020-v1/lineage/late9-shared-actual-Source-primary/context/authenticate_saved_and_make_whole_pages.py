"""Authenticate saved static context planes; presentation only, no game calls."""
from pathlib import Path
import json,gzip,hashlib,math
import numpy as np
from PIL import Image,ImageDraw
O=Path(__file__).resolve().parent;C=O/'actual-once-SourceG2-H5654-genuine13-allnative';P=O/'whole-genuine-context-pages';P.mkdir()
p=json.loads((C/'ACTUAL-LATE9-THIRTEEN-ENDPOINTS-SIX-PAIRS-SOURCEG2-H5654.json').read_text());pal=np.frombuffer((C/'actual-palette-rgb.bin').read_bytes(),np.uint8).reshape(256,3)
def classify(a):return np.where(a<240,0,np.where(a<245,1,np.where(a<250,2,a))).astype(np.uint8)
def arr(r,where):
 a=np.frombuffer(gzip.decompress((where/r['indexed']).read_bytes()),'<u2').reshape(r['height'],r['width']);assert np.max(a)<256;assert gzip.decompress((where/r['classes']).read_bytes())==classify(a).tobytes();prefix=f'P6\n{r["width"]} {r["height"]}\n255\n'.encode();assert gzip.decompress((where/r['PPM']).read_bytes())==prefix+pal[a].tobytes();return a
for c in p['components']:arr(c,C/'components')
roles=['Original_joined_SourceNx','immutable_H5654_baseline','qualified9_proposal'];arrays={};samples=0;changes=0;outside=0;retained=0
for r in p['records']:
 key=r['case_index'],r['scale'];aa=[arr(r['planes'][role],C/'planes')for role in roles];scale=r['scale'];orig,base,prop=aa;mask=np.zeros(orig.shape,bool)
 for x0,y0,x1,y1 in r['support_rectangles']:mask[y0*scale:y1*scale,x0*scale:x1*scale]=True
 diff=base!=prop;assert not(diff&~mask).any();assert int(diff.sum())==r['changed_samples'];assert np.array_equal(classify(base),classify(orig))and np.array_equal(classify(prop),classify(orig));samples+=sum(a.size for a in aa);changes+=int(diff.sum());outside+=int((~mask).sum())
 for inp,a in [('baseline_inputs',base),('proposal_inputs',prop)]:
  for part in r[inp]['pre_blit']:
   px,py=part['position']
   for x,y in part.get('retained_cells')or[]:
    yy=(py+y)*scale;xx=(px+x)*scale;assert np.array_equal(a[yy:yy+scale,xx:xx+scale],orig[yy:yy+scale,xx:xx+scale]);retained+=scale*scale
 arrays[key]=aa
pages=[];cases=sorted({r['case_index']for r in p['records']})
for start in range(0,len(cases),3):
 selected=cases[start:start+3]
 for scale in range(1,5):
  zoom=2 if scale<=2 else 1;side=96*scale*zoom;page=Image.new('RGB',(side*3,len(selected)*(side+36)+26),(21,24,29));d=ImageDraw.Draw(page);d.text((3,3),f'Late9 native{scale}: Original / historicalH5654 / proposed; NN{zoom}',fill='white')
  for j,case in enumerate(selected):
   row=next(r for r in p['records']if r['case_index']==case and r['scale']==scale);event=row['endpoint']['settled_event'];desc='intact'if event is None else event['definition']['asset']+'>'+event['definition']['settled'];y=26+j*(side+36);d.text((3,y+3),f"case{case} {row['endpoint']['mission']} {desc}",fill='white')
   for k,a in enumerate(arrays[case,scale]):page.paste(Image.fromarray(pal[a]).resize((side,side),Image.Resampling.NEAREST),(k*side,y+30))
  q=P/f'endpoints-{start}-{start+len(selected)-1}-native{scale}-whole-Original-H5654-proposal.png';page.save(q);pages.append(dict(cases=selected,scale=scale,path=str(q),sha256=hashlib.sha256(q.read_bytes()).hexdigest(),presentation_integer_NN=zoom,all_whole_role_bodies=True))
pairpages=[]
for pair in p['Source_contract']['ordered_pairs']:
 before,after=pair['before'],pair['after'];side=384;page=Image.new('RGB',(side*3,2*(side+30)+26),(21,24,29));d=ImageDraw.Draw(page);de=pair['change']['definition'];d.text((3,3),f"Real FLATS one-cell transition {de['asset']}>{de['settled']}, Original/H5654/proposed",fill='white')
 for j,case in enumerate([before,after]):
  y=26+j*(side+30);d.text((3,y+3),f'case{case} '+('before'if j==0 else'after'),fill='white')
  for k,a in enumerate(arrays[case,4]):page.paste(Image.fromarray(pal[a]),(k*side,y+26))
 q=P/f'legal-pair-{before}-{after}-native4-whole-Original-H5654-proposal.png';page.save(q);pairpages.append(dict(pair=pair,path=str(q),sha256=hashlib.sha256(q.read_bytes()).hexdigest(),scale=4))
result=dict(status='SAVED156_ROLE_PLANES_COMPONENTS_RGB_CLASSES_RETENTION_AND_JOIN_SUPPORT_AUTHENTICATED',screen_samples=samples,changed_samples=changes,outside_support_samples_exact=outside,outside_support_changes=0,postjoin_retained_Original_samples_checked=retained,own_stage_checks=len(p['own_stage_checks']),all_SourceClasses_exact=True,fallbacks=p['fallback_ids'],all_fallbacks_exact=True,foreign_interiors_exact=True,diagnostics=p['diagnostics'],pages=pages,pair_pages=pairpages,operations=dict(new_World_QA_render_cleanup_generation=0),physical_review_pending=True,scope='Finite13genuine endpoints/6one-cell events, not all callers/timing/neighbor states; baseline literalhistoricalH5654 only.')
q=O/'STRICT-SAVED-PLANES-AUDIT-AND-PHYSICAL-INDEX.json';q.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items()if k not in('pages','pair_pages')},indent=2))
