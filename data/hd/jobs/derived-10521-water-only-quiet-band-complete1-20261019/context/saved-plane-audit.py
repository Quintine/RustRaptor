from pathlib import Path
import json,gzip,hashlib
import numpy as np
from PIL import Image,ImageDraw
O=Path(__file__).resolve().parent;C=O/'actual-once-focused3-water-context';OLD=O.parent/'hd-second7-SourceG2-H5647-genuine-context-author-20261019-v1/actual-once-second7-genuine11-G2-H5647';P=O/'focused-context-pages';P.mkdir();new=json.loads((C/'ACTUAL-10521-FOCUSED-WATER-SUCCESSOR-THREE-CONTEXTS.json').read_text());old=json.loads((OLD/'ACTUAL-SECOND7-GENUINE11-SOURCEG2-H5647-CONTEXTS.json').read_text());pal=np.frombuffer((C/'actual-palette-rgb.bin').read_bytes(),np.uint8).reshape(256,3);assert (C/'actual-palette-rgb.bin').read_bytes()==(OLD/'actual-palette-rgb.bin').read_bytes()
def cls(a):return np.where(a<240,0,np.where(a<245,1,np.where(a<250,2,a))).astype(np.uint8)
def arr(r,where):
 a=np.frombuffer(gzip.decompress((where/r['indexed']).read_bytes()),'<u2').reshape(r['height'],r['width']);assert np.max(a)<256;assert gzip.decompress((where/r['classes']).read_bytes())==cls(a).tobytes();prefix=f'P6\n{r["width"]} {r["height"]}\n255\n'.encode();assert gzip.decompress((where/r['PPM']).read_bytes())==prefix+pal[a].tobytes();return a
for c in new['components']:arr(c,C/'components')
pages=[];checks=[];samples=0;delta=0;retained=0
for r in new['records']:
 case,s=r['case_index'],r['scale'];prior=next(x for x in old['records']if x['case_index']==case and x['scale']==s);a=[arr(r['planes'][n],C/'planes')for n in ['Original_joined_SourceNx','immutable_H5647_baseline','10521_water_only_successor']];held=arr(prior['planes']['selected_second7_used3_proposal'],OLD/'planes');assert np.array_equal(a[0],arr(prior['planes']['Original_joined_SourceNx'],OLD/'planes'));assert np.array_equal(a[1],arr(prior['planes']['immutable_H5647_baseline'],OLD/'planes'));orig,base,prop=a;assert np.array_equal(cls(orig),cls(base))and np.array_equal(cls(orig),cls(prop));support=np.zeros(orig.shape,bool)
 for x0,y0,x1,y1 in r['support_rectangles']:support[y0*s:y1*s,x0*s:x1*s]=True
 diff=base!=prop;assert not(diff&~support).any();assert int(diff.sum())==r['changed_samples'];delta+=int(diff.sum());samples+=sum(z.size for z in[a[0],a[1],held,a[2]])
 for z in r['proposal_inputs']['pre_blit']:
  px,py=z['position']
  for x,y in z.get('retained_cells')or[]:
   yy=(py+y)*s;xx=(px+x)*s;assert np.array_equal(prop[yy:yy+s,xx:xx+s],orig[yy:yy+s,xx:xx+s]);retained+=s*s
 w,h=orig.shape[1],orig.shape[0];page=Image.new('RGB',(w*2,(h+28)*2+24),(21,24,29));d=ImageDraw.Draw(page);d.text((3,3),f'Exact genuine oldcase{case}, native{s}; savedOriginal/current/oldHOLD/newwater',fill='white')
 for k,(label,z)in enumerate([('Original SourceNx',orig),('immutableH5647 current baseline',base),('oldHOLD10521',held),('10521water-onlysuccessor',prop)]):x=(k%2)*w;y=24+(k//2)*(h+28);d.text((x+2,y+2),label,fill='white');page.paste(Image.fromarray(pal[z]),(x,y+26))
 p=P/f'case{case:02d}-native{s}-Original-current-HOLD-successor.png';page.save(p);pages.append(dict(case=case,scale=s,path=str(p),roles=['Original','H5647current','oldHOLD','waterSuccessor'],individual_native_size=[w,h],resizing=False));checks.append(dict(case=case,scale=s,Original_and_current_planes_exact_old_saved_context=True,current_to_new_changed_samples=int(diff.sum()),oldHOLD_to_new_changed_samples=int((held!=prop).sum()),outside_support_changes=0))
other=json.loads((O/'FROZEN-OTHER6-UNCHANGED-CONTROL-INPUTS.json').read_text())
for a,v in other['other6'].items():assert hashlib.sha256(Path(v['raw_path']).read_bytes()).hexdigest()==v['raw_sha256']
r=dict(status='FOCUSED3_ALL12SCALES36NEWROLEPLANES12OLDHOLDPLANES_AUTHENTICATED_NO_OUTSIDE_SUPPORT_CHANGE',four_role_samples=samples,current_to_new_changed_samples=delta,outside_support_changes=0,retained_Original_postjoin_samples_checked=retained,Original_and_current_controls_exact_original_HOLD_context=True,other6_raws_headers_unchanged_and_not_reprocessed=True,newcompositor_invocations=0,SourceClasses_exact=True,pages=pages,checks=checks,diagnostics=new['diagnostics'],physical_review_pending=True)
(O/'STRICT-FOCUSED-WATER-CONTEXT-AUDIT-AND-PHYSICAL-INDEX.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:v for k,v in r.items()if k not in('pages','checks')},indent=2))
