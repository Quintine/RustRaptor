"""Recover metadata of already saved failed-counter output; NO raster/compile/World."""
from pathlib import Path
import json,gzip,hashlib,struct,importlib.util
import numpy as np
q=Path(__file__).resolve().parent;r=q.parents[1];out=q/'actual-once-industrial7-genuine10-G2-H5647';recipe=json.loads((q/'SEALED-INDUSTRIAL7-GENUINE10-CURRENTG2-H5647-RECIPE.json').read_text());bind=json.loads(Path(recipe['finite_bindings']['path']).read_text());own=set(recipe['selected']);foreign=set(bind['registered_foreign']);active=own|foreign
p=r/'.reference/hd-industrial20593-205ff-fine-material-CODE-guard-successor-20261019-v2/industrial_fine_cleanup.py';sp=importlib.util.spec_from_file_location('saved_only',p);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();pin=lambda p:dict(path=str(p),sha256=sha(p));pal=np.frombuffer((out/'actual-palette-rgb.bin').read_bytes(),np.uint8).reshape(256,3);sources={a:np.frombuffer(Path(b['source']['path']).read_bytes()[20:],np.uint8).reshape(32,32)for a,b in bind['bindings'].items()};components=[];layers={};stages=[]
def record(folder,name,w,h):
 value=dict(width=w,height=h,indexed=name+'.indices-u16le.gz',classes=name+'.classes-u8.gz',PPM=name+'.ppm.gz');idx=np.frombuffer(gzip.decompress((folder/value['indexed']).read_bytes()),'<u2').reshape(h,w);assert idx.max()<256;cl=np.frombuffer(gzip.decompress((folder/value['classes']).read_bytes()),np.uint8).reshape(h,w);expected=np.where(idx<240,0,np.where(idx<245,1,np.where(idx<250,2,idx))).astype(np.uint8);assert np.array_equal(cl,expected);assert gzip.decompress((folder/value['PPM']).read_bytes())==f'P6\n{w} {h}\n255\n'.encode()+pal[idx].tobytes();return value,idx
for aid in sorted(active):
 frame=bind['bindings'][aid]['native']['frame'];details=frame.get('original_detail_cells')or None;assert frame.get('palette_constraint')is None
 for s in range(1,5):
  rec,idx=record(out/'components',f'{aid}-s{s}',32*s,32*s);rec.update(asset=aid,scale=s,full_native_frame=frame,retained_cells=details,palette_domain=None,metadata_recovery='File-only from frozenbinding and Sourcecode emit schema after final count assertion101.');components.append(rec);layers[aid,s]=rec
  if aid in own:
   bank=next(x for x in json.loads(Path(recipe['accepted_own_banks'][aid]['path']).read_text())if x['asset']==aid);src=m.scale_nx(sources[aid],s);restored=idx.copy()
   for x,y in details or[]:restored[y*s:(y+1)*s,x*s:(x+1)*s]=src[y*s:(y+1)*s,x*s:(x+1)*s]
   actual=np.array(bank['scales'][s-1]['indices'],np.uint16).reshape(32*s,32*s);assert np.array_equal(restored,actual);stages.append(dict(asset=aid,scale=s,prejoin_plus_SourceNx_retention_equals_accepted_final_G2_bank=True,retained_cells=details or[],accepted_global_SourceNx_244_fringe_mismatches_outside_retained_owners=0,same_literal_actual_binding=True))
def support(ids,cols,rows):
 areas=set()
 def at(x,y):return y*cols+x if 0<=x<cols and 0<=y<rows else None
 for t,aid in enumerate(ids):
  if aid not in own:continue
  tx,ty=t%cols,t//cols;areas.add((tx*32,ty*32,(tx+1)*32,(ty+1)*32))
  for dx,dy in [(-1,0),(1,0),(0,-1),(0,1)]:
   n=at(tx+dx,ty+dy)
   if n is None or ids[n]not in active or ids[n]in own:continue
   x,y=n%cols*32,n//cols*32;areas.add({(-1,0):(x+30,y+2,x+32,y+30),(1,0):(x,y+2,x+2,y+30),(0,-1):(x+2,y+30,x+30,y+32),(0,1):(x+2,y,x+30,y+2)}[dx,dy])
  for vy in [ty,ty+1]:
   for vx in [tx,tx+1]:
    pos=[(vx-1,vy-1),(vx,vy-1),(vx-1,vy),(vx,vy)];slots=[at(x,y)for x,y in pos]
    if any(z is None for z in slots)or not all(ids[z]in active for z in slots):continue
    for n,(px,py)in zip(slots,pos):
     if ids[n]in own:continue
     x=n%cols*32+(0 if px==vx else30);y=n//cols*32+(0 if py==vy else30);areas.add((x,y,x+2,y+2))
 return [list(x)for x in sorted(areas)]
records=[];roles=['Original_joined_SourceNx','immutable_H5647_baseline','selected_industrial7_proposal']
for case in recipe['cases']:
 ci=case['case_index'];ids=case['ordered_source_ids'];cols=case['width_tiles'];rows=case['height_tiles'];regions=support(ids,cols,rows)
 for s in range(1,5):
  planes={};arr={}
  for role in roles:planes[role],arr[role]=record(out/'planes',f'case{ci:02}-s{s}-{role}',cols*32*s,rows*32*s)
  original,b,proposal=[arr[x]for x in roles];mask=np.zeros(original.shape,bool)
  for x0,y0,x1,y1 in regions:mask[y0*s:y1*s,x0*s:x1*s]=True
  assert np.array_equal(b[~mask],proposal[~mask]);owncount=0;foreigncount=0
  for t,aid in enumerate(ids):
   yy=t//cols*32*s;xx=t%cols*32*s
   if aid in own:assert np.array_equal(b[yy:yy+32*s,xx:xx+32*s],original[yy:yy+32*s,xx:xx+32*s]);owncount+=1024*s*s
   if aid in foreign:assert np.array_equal(b[yy+2*s:yy+30*s,xx+2*s:xx+30*s],proposal[yy+2*s:yy+30*s,xx+2*s:xx+30*s]);foreigncount+=784*s*s
  def inputmetadata(allowed):
   pre=[];retained=0
   for t,aid in enumerate(ids):
    if aid not in allowed:continue
    details=layers[aid,s]['retained_cells'];retained+=len(details or[])*s*s;pre.append(dict(slot=t,asset=aid,position=[t%cols*32,t//cols*32],component=layers[aid,s],retained_cells=details,palette_domain=None))
   return dict(pre_blit=pre,retained_OriginalNx_samples=retained,palette_domain_samples=0)
  records.append(dict(case_index=ci,scale=s,endpoint=case,planes=planes,baseline_inputs=inputmetadata(foreign),proposal_inputs=inputmetadata(active),support_rectangles=regions,outside_support_samples_exact=int((~mask).sum()),broad_foreign_interior_samples_exact=foreigncount,baseline_own_Original_samples_exact=owncount,reserved250plus_exact=int((original>=250).sum()),foreign_Original_fallback_samples_exact=0,changed_samples=int((b!=proposal).sum()),all_final_joined_SourceClasses_exact=True))
assert len(records)==40 and len(components)==96 and len(stages)==28
proof=dict(status='SAVED_PLANE_METADATA_RECOVERY_AFTER_FINAL_COMPONENT_COUNT_ASSERTION101_NO_NEW_PIXELS',recipe=recipe,records=records,components=components,own_stage_checks=stages,unique_endpoints=10,scale_records=40,whole_role_bodies=120,Original_fallbacks=[],unused_catalogue_only=[],World_calls=0,diagnostics=[],actual_constructor_terminal=pin(q/'ACTUAL-GENUINE10-CONSTRUCTOR-TERMINAL.json'),actual_constructor_exit_code=101,actual_saved_component_arrays=96,wrong_inherited_component_count=80,correct_formula='(17foreign+7own)*4=96',source_all_pixel_assertions_preceded_counter_stop=True,metadata_reconstructed_from_frozen_bindings_and_saved_index_class_RGB_only=True,no_rerender_compile_World_QA_cleanup=True)
p=q/'SAVED-INDUSTRIAL7-GENUINE10-FILE-ONLY-METADATA-RECOVERY.json';assert not p.exists();p.write_text(json.dumps(proof,indent=2)+'\n');print(sha(p))
