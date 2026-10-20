from pathlib import Path
import gzip,json,hashlib,struct,collections,io
import numpy as np
from PIL import Image,ImageDraw
O=Path(__file__).resolve().parent;R=O.parents[1];D=O/'actual-context18';V=O/'whole-native-endpoint-pages';W=O/'ordered-before-settled-native4-pages';V.mkdir(exist_ok=True);W.mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def js(p):return json.loads(Path(p).read_text())
proof=js(D/'ACTUAL-SHORELINE4-G2-H5636-GENUINE18-ALL4-216-ROLE-BODIES.json');contract=proof['source_contract'];own=set(contract['selected']);pal=np.frombuffer((D/'actual-palette-rgb.bin').read_bytes(),np.uint8).reshape(256,3);records={};checks=[];total=0;retained=0;changed=0
classes=lambda a:np.where((a>=240)&(a<=244),np.full_like(a,1),np.where((a>=245)&(a<=249),np.full_like(a,2),np.where(a>=250,a,np.zeros_like(a)))).astype(np.uint8)
def rgb(a):assert(a<256).all();return pal[a]
def arr(folder,x):
 a=np.frombuffer(gzip.decompress((D/folder/x['indexed']).read_bytes()),'<u2').reshape(x['height'],x['width']);assert(a<256).all();assert gzip.decompress((D/folder/x['classes']).read_bytes())==classes(a).tobytes();assert np.array_equal(np.array(Image.open(io.BytesIO(gzip.decompress((D/folder/x['PPM']).read_bytes())))),rgb(a));return a
components={}
for c in proof['components']:components[c['asset'],c['scale']]=arr('components',c)
assert len(components)==216
for row in proof['records']:
 si,s=row['endpoint_index'],row['scale'];planes={k:arr('planes',x)for k,x in row['planes'].items()};ori=planes['Original_joined_SourceNx'];cur=planes['immutable_H5636_current'];pro=planes['shoreline4_proposed'];assert np.array_equal(classes(ori),classes(cur))and np.array_equal(classes(ori),classes(pro));assert np.array_equal(ori[ori>=250],cur[ori>=250])and np.array_equal(ori[ori>=250],pro[ori>=250]);diff=cur!=pro;support=np.zeros(ori.shape,bool)
 for l,t,r,b in row['support_rectangles']:support[t*s:b*s,l*s:r*s]=True
 assert not (diff&~support).any();assert int(diff.sum())==row['changed_samples'];changed+=int(diff.sum());total+=sum(a.size for a in planes.values());rims=[]
 for role,info in [('immutable_H5636_current',row['baseline_inputs']),('shoreline4_proposed',row['proposal_inputs'])]:
  for layer in info['pre_blit']:
   asset=layer['asset'];im=components[asset,s];assert im.shape==(32*s,32*s);x,y=layer['position'];target=planes[role][y*s:(y+32)*s,x*s:(x+32)*s];control=ori[y*s:(y+32)*s,x*s:(x+32)*s]
   for cx,cy in layer['retained_cells']or[]:
    aa=target[cy*s:(cy+1)*s,cx*s:(cx+1)*s];bb=control[cy*s:(cy+1)*s,cx*s:(cx+1)*s];assert np.array_equal(aa,bb);retained+=s*s
   if layer['palette_domain']:assert set(map(int,target.ravel()))<=set(layer['palette_domain'])
 for slot,asset in enumerate(row['endpoint']['ordered_source_ids']):
  x=slot%3*32*s;y=slot//3*32*s
  if asset in own:assert np.array_equal(cur[y:y+32*s,x:x+32*s],ori[y:y+32*s,x:x+32*s])
  if asset is None or asset in proof['finite_original_fallback_assets']:assert np.array_equal(cur[y:y+32*s,x:x+32*s],pro[y:y+32*s,x:x+32*s])and np.array_equal(ori[y:y+32*s,x:x+32*s],pro[y:y+32*s,x:x+32*s])
 records[si,s]=(row,planes)
pages=[];roles=['Original_joined_SourceNx','immutable_H5636_current','shoreline4_proposed']
for endpoint in contract['endpoints']:
 si=endpoint['endpoint_index'];page=Image.new('RGB',(1192,1150),(20,22,27));d=ImageDraw.Draw(page);d.text((8,6),f'Endpoint{si:02d} {endpoint["mission"]} r{endpoint["row"]}c{endpoint["column"]} {endpoint["role"]}',fill='white');d.text((8,24),'Whole 3x3 actual MAP window; Original / H5636 current / shoreline4 proposed; no pixel resizing',fill='white');yy=48
 for s in range(1,5):
  row,planes=records[si,s];size=96*s;d.text((8,yy),f'native{s}; {size}x{size}; ids '+','.join(a or'padding'for a in endpoint['ordered_source_ids']),fill='white');yy+=16
  for role,k in enumerate(roles):page.paste(Image.fromarray(rgb(planes[k])),(8+role*396,yy))
  yy+=size+12
 assert yy<=1150;p=V/f'endpoint{si:02d}-whole-Original-current-proposed-all-native.png';page.save(p);pages.append(dict(endpoint=si,path=str(p.relative_to(O)),sha256=sha(p),all_native=[1,2,3,4],roles=roles,pixel_resizing=False))
ordered=[]
for pair in contract['ordered_pairs']:
 page=Image.new('RGB',(1192,864),(20,22,27));d=ImageDraw.Draw(page);d.text((8,6),f'Ordered legal foreign event{pair["pair_index"]}: {pair["event_id"]}',fill='white');d.text((8,24),'Original / H5636 current / proposed ; actual native4 whole96logical window. No World/timing claim.',fill='white')
 for half,key in enumerate(['before_endpoint','settled_endpoint']):
  si=pair[key];row,planes=records[si,4];yy=48+half*408;d.text((8,yy),f'{key}={si}; changedslot{pair["changed_slot"]}',fill='white');yy+=16
  for ri,k in enumerate(roles):page.paste(Image.fromarray(rgb(planes[k])),(8+ri*396,yy))
 p=W/f'pair{pair["pair_index"]}-ordered-before-settled-native4.png';page.save(p);ordered.append(dict(pair=pair['pair_index'],path=str(p.relative_to(O)),sha256=sha(p),before_endpoint=pair['before_endpoint'],settled_endpoint=pair['settled_endpoint'],all_scale_arrays_authenticated=[1,2,3,4],physical_native4_pair_page=True,pixel_resizing=False))
out=dict(status='FILE_ONLY_ALL72_SCALES_216_PLANES_216_COMPONENTS_AUTHENTICATED_PHYSICAL_REVIEW_PENDING',Source_contract_sha256=sha(O/'FROZEN-SHORELINE4-GENUINE18-CURRENTG2-H5636-CONTRACT.json'),actual_context_proof_sha256=sha(D/'ACTUAL-SHORELINE4-G2-H5636-GENUINE18-ALL4-216-ROLE-BODIES.json'),sample_counts=dict(role_body_indices=total,changed_current_to_proposed=changed,retained_original_globalNx_samples_verified=retained),fallback_assets=proof['finite_original_fallback_assets'],components=216,scale_records=72,role_bodies=216,whole_endpoint_pages=pages,ordered_native4_pages=ordered,all_Source_reserved_classes_exact=True,all_retained_whole_OriginalNx_exact=True,all_current_selected_owner_fallback_exact=True,no_outside_local_join_support_changes=True,pages_native_pixels_unresized=True,new_constructor_World_intrinsicQA_generation_cleanup_calls=0,script_sha256=sha(__file__))
(O/'FILE-ONLY-ALL-SAVED-ARRAYS-CLASSES-RGB-RETENTION-AUDIT-AND-PAGE-INDEX.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items()if k not in ['whole_endpoint_pages','ordered_native4_pages']},indent=2))
