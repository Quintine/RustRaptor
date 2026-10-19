"""Saved-data authentication and unresampled presentation only. No engine/helper/QA."""
from pathlib import Path
import json,hashlib,gzip,struct,ast
import numpy as np
from PIL import Image,ImageDraw,ImageFont
W=Path('/home/quintine/Projects/RaptorReplica');R=W/'RustRaptor';F=Path(__file__).resolve().parent;O=F/'actual-context14';PROOF=O/'ACTUAL-SOURCEG2-GRATING2-GENUINE14-56-SCALES-168-PLANES-2VIEWS-2EVENTS.json'
def pin(p):
 p=Path(p).resolve();s=p.stat();return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),size=s.st_size,mtime_ns=s.st_mtime_ns,mode=s.st_mode)
def save(p,v):
 with p.open('x')as f:json.dump(v,f,indent=2);f.write('\n')
 return pin(p)
alg=R/'.reference/hd-terrain1-20273-20275-currentC-5384-bounded-context-production-20261017/authenticate_and_make_lossless_pages.py';tree=ast.parse(alg.read_text());defs=[v for v in tree.body if isinstance(v,ast.FunctionDef)and v.name in ['cls','upscale']];assert len(defs)==2;exec(compile(ast.Module(body=defs,type_ignores=[]),str(alg),'exec'),globals())
oldauth=R/'.reference/hd-terrain1-40425-40434-SourceE-H5426-context13-corrected-actual-execution-20261017-v2/authenticate_saved_planes_and_present.py';tree=ast.parse(oldauth.read_text());defs=[v for v in tree.body if isinstance(v,ast.FunctionDef)and v.name=='logical_support'];assert len(defs)==1;exec(compile(ast.Module(body=defs,type_ignores=[]),str(oldauth),'exec'),globals())
x=json.loads(PROOF.read_text());c=x['source_contract'];assert len(x['records'])==56 and len(x['components'])==220 and len(x['ordered_pairs'])==2 and x['diagnostics']==[]
pr=np.frombuffer((R/'data/misc/PALETTE_DAT').read_bytes(),dtype='u1').astype('u2');pal=((np.minimum(pr,63)<<2)|(np.minimum(pr,63)>>4)).astype('u1').reshape(256,3);assert (O/'actual-palette-rgb.bin').read_bytes()==pal.tobytes()
sources={}
for row in c['source_pins']:
 assert pin(row['source']['path'])==row['source'];raw=Path(row['source']['path']).read_bytes();assert list(struct.unpack('<5i',raw[:20]))==row['header'];sources[row['asset']]=np.frombuffer(raw[20:],dtype='u1').reshape(32,32).astype('<u2')
assert len(sources)==55
def load(rec,root):
 a=np.frombuffer(gzip.decompress((root/rec['indexed']).read_bytes()),dtype='<u2').reshape(rec['height'],rec['width']);assert a.max()<256
 z=np.frombuffer(gzip.decompress((root/rec['classes']).read_bytes()),dtype='u1').reshape(a.shape);assert np.array_equal(z,cls(a));head=f'P6\n{a.shape[1]} {a.shape[0]}\n255\n'.encode();ppm=gzip.decompress((root/rec['PPM']).read_bytes());assert ppm.startswith(head)and ppm[len(head):]==pal[a].tobytes();return a
bank={}
for q in x['activation']['actual_selected_plain_index_banks']:
 for r in json.loads(Path(q['actual_bank']['path']).read_text()):
  if r['asset']==q['asset']:
   for v in r['scales']:bank[r['asset'],v['scale']]=np.array(v['indices'],dtype='<u2').reshape(v['height'],v['width'])
assert len(bank)==8
base=json.loads(Path(x['activation']['baseline_hd']['path']).read_text());native={f'{s["base_asset"]+f["frame"]:05x}':f for s in base['sequences']for f in s['frames']};ownnative={r['asset']:r['private_full_sequence']['frames'][0]for r in c['own_routes']};own=set(c['selected']);foreign={r['asset']for r in x['activation']['baseline_finite_native']};allhd=own|foreign;components={};compauth=[]
for r in x['components']:
 a=load(r,O/'components');aid=r['asset'];s=r['scale'];frame=ownnative[aid]if aid in own else native[aid];assert frame==r['full_native_frame'];details=r['retained_cells']or[];domain=r['palette_domain'];assert details==frame.get('original_detail_cells',[]);assert bool(domain)==bool(frame.get('palette_constraint'));assert np.array_equal(cls(a),cls(np.repeat(np.repeat(sources[aid],s,0),s,1)))
 if aid in own:assert details==ownnative[aid].get('original_detail_cells',[])and domain is None and np.array_equal(a,bank[aid,s])

 if domain:assert set(domain)==set(int(v)for v in sources[aid].flat);assert set(int(v)for v in a.flat)<=set(domain)
 components[aid,s]=(a,details,domain);compauth.append(dict(asset=aid,scale=s,exact_full_native_metadata_and_palette_domain=True,prejoin_matches_literal_actual_derived_G2_selected_row=aid in own,actual_derived_grating2_row=aid in own))
roles=['Original_joined_SourceNx','actual_H5613_baseline','selected_derived_grating2_proposal'];rows={};audit=[];totals={k:0 for k in ['Original_control_samples','all3_plane_samples','baseline_Original_selected_owner_samples','retained_baseline_samples','retained_proposal_samples','domain_samples','outside_support_samples','foreign_broad_interior_samples','fallback_samples','padding_samples','delta_samples','foreign_noncorner_edge_delta_samples','foreign_corner_delta_samples']}
for rec in x['records']:
 ei=rec['endpoint_index'];s=rec['scale'];e=c['endpoints'][ei];ids=e['ordered_source_ids'];assert sum(v in own for v in ids)>=1;assert (len(e["settled_actors"])==0 if e["role"]=="authentic_static_intact"else len(e["settled_actors"])==1);source=np.zeros((96,96),dtype='<u2')
 for t,v in enumerate(ids):
  if v is not None:source[t//3*32:(t//3+1)*32,t%3*32:(t%3+1)*32]=sources[v]
 original=upscale(source,s);a={r:load(rec['planes'][r],O/'planes')for r in roles};assert np.array_equal(original,a[roles[0]])
 for role in roles:assert np.array_equal(cls(a[role]),cls(original));assert np.array_equal(a[role][original>=250],original[original>=250])
 mask=np.repeat(np.repeat(logical_support(ids),s,0),s,1);rr=np.zeros(original.shape,dtype=bool)
 for x0,y0,x1,y1 in rec['support_rectangles']:rr[y0*s:y1*s,x0*s:x1*s]=True
 assert np.array_equal(mask,rr);b=a[roles[1]];p=a[roles[2]];assert np.array_equal(b[~mask],p[~mask]);outs=int((~mask).sum());fallback=padding=interior=baseowner=0
 for t,v in enumerate(ids):
  yy=t//3*32*s;xx=t%3*32*s;sl=np.s_[yy:yy+32*s,xx:xx+32*s]
  if v in own:assert np.array_equal(b[sl],original[sl]);baseowner+=1024*s*s
  if v not in allhd:assert np.array_equal(b[sl],original[sl])and np.array_equal(p[sl],original[sl]);fallback+=1024*s*s
  if v is None:assert np.all(original[sl]==0);padding+=1024*s*s
  if v not in own:inter=np.s_[yy+2*s:yy+30*s,xx+2*s:xx+30*s];assert np.array_equal(b[inter],p[inter]);interior+=784*s*s
 for info,role in [('baseline_inputs',roles[1]),('proposal_inputs',roles[2])]:
  retained=domaincount=0;active=foreign if info=='baseline_inputs'else allhd;expected=[t for t,v in enumerate(ids)if v in active];assert [r['slot']for r in rec[info]['pre_blit']]==expected
  for r in rec[info]['pre_blit']:
   slot=r['slot'];aid=ids[slot];_,details,domain=components[aid,s];assert r['asset']==aid and r['position']==[slot%3*32,slot//3*32]and r['retained_cells']==(details or None)and r['palette_domain']==domain;yy=slot//3*32*s;xx=slot%3*32*s
   for cx,cy in details:
    sl=np.s_[yy+cy*s:yy+(cy+1)*s,xx+cx*s:xx+(cx+1)*s];assert np.array_equal(a[role][sl],original[sl]);retained+=s*s
   if domain:
    sl=np.s_[yy:yy+32*s,xx:xx+32*s];assert set(int(v)for v in a[role][sl].flat)<=set(domain);domaincount+=1024*s*s
  assert retained==rec[info]['retained_OriginalNx_samples']and domaincount==rec[info]['palette_domain_samples'];totals['retained_baseline_samples'if info=='baseline_inputs'else'retained_proposal_samples']+=retained;totals['domain_samples']+=domaincount
 delta=int(np.count_nonzero(b!=p));assert delta==rec['delta_samples'];assert fallback==rec['fallback_samples_exact']and padding==rec['padding_samples_exact']and outs==rec['outside_support_samples_exact']and interior==rec['broad_foreign_interior_samples_exact']and baseowner==rec['baseline_original_owner_samples_exact']
 for k,v in dict(Original_control_samples=original.size,all3_plane_samples=original.size*3,baseline_Original_selected_owner_samples=baseowner,outside_support_samples=outs,foreign_broad_interior_samples=interior,fallback_samples=fallback,padding_samples=padding,delta_samples=delta).items():totals[k]+=v
 # Independently reconstruct active four-HD stencils and foreign edge/corner changes.
 corners=[];cornerdelta=0
 for vy in [1,2]:
  for vx in [1,2]:
   slots=[(vy-1)*3+vx-1,(vy-1)*3+vx,vy*3+vx-1,vy*3+vx]
   if not any(ids[t]in own for t in slots):continue
   activebefore=all(ids[t]in foreign for t in slots);activeafter=all(ids[t]in allhd for t in slots);changes=0
   for t in slots:
    if ids[t]in own:continue
    xx=t%3*32+(0 if t%3==vx else 30);yy=t//3*32+(0 if t//3==vy else 30);sl=np.s_[yy*s:(yy+2)*s,xx*s:(xx+2)*s];count=int(np.count_nonzero(b[sl]!=p[sl]));assert not count or activeafter;changes+=count
   corners.append(dict(vertex=[vx,vy],slots=slots,active_baseline=activebefore,active_proposal=activeafter,foreign_corner_delta_samples=changes));cornerdelta+=changes
 assert corners==rec['four_HD_corner_stencils']and cornerdelta==rec['foreign_corner_delta_samples']
 edge=0
 for t,v in enumerate(ids):
  if v in own:continue
  yy=t//3*32*s;xx=t%3*32*s;dd=b[yy:yy+32*s,xx:xx+32*s]!=p[yy:yy+32*s,xx:xx+32*s];edge_mask=np.zeros(dd.shape,dtype=bool);edge_mask[2*s:30*s,:]=True;edge_mask[:,2*s:30*s]=True;edge+=int(np.count_nonzero(dd&edge_mask))
 assert edge==rec['foreign_noncorner_edge_delta_samples'];totals['foreign_noncorner_edge_delta_samples']+=edge;totals['foreign_corner_delta_samples']+=cornerdelta
 audit.append(dict(endpoint=ei,scale=s,all_SourceNx_class_palette_domain_PPMS_reserved_outside_foreign_fallback_padding_role_checks_exact=True,delta_samples=delta));rows.setdefault(ei,[]).append((s,a,rec))
pairauth=[]
for k,q in enumerate(x['ordered_pairs']):
 bef=c['endpoints'][q['before_endpoint']];aft=c['endpoints'][q['settled_endpoint']];diff=[i for i,(a,b)in enumerate(zip(bef['ordered_source_ids'],aft['ordered_source_ids']))if a!=b];assert diff==[q['changed_slot']];assert bef['ordered_source_ids'][q['changed_slot']]==q['Original_actor']['intact']and aft['ordered_source_ids'][q['changed_slot']]==q['Original_actor']['settled'];assert any(v['Original_tile']==q['Original_actor']and[v['row'],v['column']]==q['actor_position']for v in aft['settled_actors']);pairauth.append(dict(q,all_scales=[1,2,3,4]))
assert totals['baseline_Original_selected_owner_samples']==sum(sum(v in own for v in e['ordered_source_ids'])*1024*30 for e in c['endpoints'])
assert len(rows)==14 and len(pairauth)==2 and len({p['event_id']for p in pairauth})==2
pages=F/'lossless-whole-native-endpoint-pages';pairs=F/'lossless-ordered-one-cell-pair-pages';pages.mkdir();pairs.mkdir();font=ImageFont.truetype('/usr/share/fonts/Adwaita/AdwaitaSans-Regular.ttf',14);small=ImageFont.truetype('/usr/share/fonts/Adwaita/AdwaitaSans-Regular.ttf',12);pageindex=[]
for ei,parts in rows.items():
 ep=c['endpoints'][ei];im=Image.new('RGB',(1264,1190),(22,24,28));d=ImageDraw.Draw(im);d.text((20,9),f"endpoint{ei:02} / {ep['mission']} r{ep['row']} c{ep['column']} / {ep['role']}",font=font,fill='white');d.text((20,32),f"SourceG2 5b6 / actualH5613 | whole3x3 native1-4 | all12 callers +2 foreign-neighbor states | {ep['Source_key'][:16]}",font=small,fill=(215,215,220))
 for j,label in enumerate(['Whole Original SourceNx','Actual5613 baseline','Derived grating2 proposal']):d.text((28+j*412,59),label,font=font,fill=(235,220,175))
 y=87;panes=[]
 for s,arr,rec in sorted(parts,key=lambda z:z[0]):
  w=96*s;d.text((6,y),str(s)+'x',font=small,fill='white')
  for j,role in enumerate(roles):
   xx=28+j*412+(384-w)//2;rgb=pal[arr[role]];im.paste(Image.fromarray(rgb),(xx,y));panes.append(dict(endpoint_index=ei,scale=s,role=role,box=[xx,y,w,w],actual_plane=rec['planes'][role],RGB_body_sha256=hashlib.sha256(rgb.tobytes()).hexdigest()))
  y+=w+24
 path=pages/f'endpoint-{ei:02}-whole-Original-baseline-proposal-native1to4.png';im.save(path,optimize=True);dec=np.asarray(Image.open(path).convert('RGB'))
 for pane in panes:
  xx,yy,w,h=pane['box'];assert hashlib.sha256(dec[yy:yy+h,xx:xx+w].tobytes()).hexdigest()==pane['RGB_body_sha256']
 pageindex.append(dict(endpoint_index=ei,page=pin(path),dimensions=[1264,1190],endpoint=ep,panes=panes))
pairindex=[]
for p in pairauth:
 bef=pageindex[p['before_endpoint']];aft=pageindex[p['settled_endpoint']];im=Image.new('RGB',(2528,1226),(22,24,28));d=ImageDraw.Draw(im);d.text((16,8),f"PAIR{p['pair_index']}: real Source actor {p['Original_actor']['intact']} LEFT -> {p['Original_actor']['settled']} RIGHT; ONLY slot{p['changed_slot']} / one actor only / separate one-cell state",font=font,fill='white');im.paste(Image.open(bef['page']['path']),(0,36));im.paste(Image.open(aft['page']['path']),(1264,36));path=pairs/f"pair-{p['pair_index']:02}-whole-ordered-before-to-one-cell-settled.png";im.save(path,optimize=True);dec=np.asarray(Image.open(path).convert('RGB'));pp=[]
 for off,side in [(0,bef),(1264,aft)]:
  for pane in side['panes']:
   item=dict(pane);item['box']=[pane['box'][0]+off,pane['box'][1]+36,pane['box'][2],pane['box'][3]];item['ordered_role']='before'if off==0 else'settled';xx,yy,w,h=item['box'];assert hashlib.sha256(dec[yy:yy+h,xx:xx+w].tobytes()).hexdigest()==item['RGB_body_sha256'];pp.append(item)
 pairindex.append(dict(**p,page=pin(path),dimensions=[2528,1226],panes=pp,before_endpoint_page=bef['page'],settled_endpoint_page=aft['page'],panes_duplicate_actual_endpoint_views=True))
auth=save(F/'FILE-ONLY-GRATING2-14-ENDPOINTS-168-PLANES-220-COMPONENTS-AUTHENTICATION.json',dict(status='PASS_FILE_ONLY_NO_ENGINE_HELPER_QA',proof=pin(PROOF),OriginalScaleNx_algorithm=pin(alg),totals=totals,component_checks=compauth,per_scale_checks=audit,pair_checks=pairauth,actual_own_pre_components=8,own_prejoin_matches_exact_literal_actual_derived_G2_bank=True,own_Originaldetails_absent=True,final_joined_retained_whole_SourceNx_exact=True,actual_joined_palette_owners=sorted({r['asset']for r in x['components']if r['palette_domain']}),new7_baseline_Original_fallback_and_offmap_padding_typed=True,unique_whole_endpoint_pane_bodies=168,ordered_pair_duplicate_panes=48,all_PPM_u16_classes_and_palette_body_exact=True,page_readbacks=216,new_engine_calls=0))
interface=save(F/'COMPLETE14-GENUINE-168-NATIVE-PANES-TWO-ORDERED-VIEWS-PAGE-ARRAY-INTERFACE.json',dict(status='FROZEN_TECHNICAL_BODY_INTERFACE_DIFFERENT_PHYSICAL_REVIEW_PENDING',roles=roles,pages=pageindex,ordered_pair_pages=pairindex,unique_Original_Source_endpoints=14,private_or_World_probes=0,unique_scale_records=56,unique_native_whole_planes=168,endpoint_whole_pages=14,ordered_pair_whole_pages=2,ordered_pair_panes_duplicate_endpoints=48,whole_native_page_count=16,source_contract=x['activation']['source_contract'],actual_proof=pin(PROOF),file_only_authentication=auth,components=x['components'],original_palette=pin(O/'actual-palette-rgb.bin'),absolute_plane_root=str(O/'planes'),absolute_component_root=str(O/'components'),actual_H5613=x['activation']['baseline_hd'],SourceG2_epoch=x['activation']['SourceG2_epoch'],actual_library=x['activation']['actual_library'],new7_baseline_Original_fallback_and_offmap_padding_preserved=True,all_bodies_unresampled=True,static_ordered_pair_semantics='All12 actual static callers plus2 controlled legal foreign-neighbor states, exactly2 distinct one-cell events. Own grating health0/reward0 has no settled state. Full genuine Registry/FLATS matches, no World/natural timing claim. Exact public prejoin own pixels equal literalG2QA62d093c4 bank, selected no retention. Foreign complete frame metadata and Original details/domains preserved. Immutable5613 baseline b13a4f7c, actualG2 library5b6; no historical capture or newintrinsic claim.'))
print(json.dumps(dict(authentication=auth,interface=interface,totals=totals,pagebytes=sum(p.stat().st_size for root in [pages,pairs]for p in root.iterdir())),indent=2))
