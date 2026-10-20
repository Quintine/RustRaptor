"""Read saved outputs only; no cleanup, helper, engine, QA or generation invocation."""
from pathlib import Path
import json,hashlib,struct,ast
import numpy as np
from PIL import Image
O=Path(__file__).resolve().parent;R=O.parent.parent;guards={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def take(p):
 p=Path(p).absolute();s=p.stat();b=p.read_bytes();q={'path':str(p),'sha256':hashlib.sha256(b).hexdigest(),'size':s.st_size,'mtime_ns':s.st_mtime_ns,'mode':s.st_mode};assert len(b)==s.st_size
 if str(p)in guards:assert guards[str(p)]==q
 guards[str(p)]=q;return b
# A file-only independent SourceNx reference algorithm already used for preserved context controls.
alg=R/'.reference/hd-terrain1-20273-20275-currentC-5384-bounded-context-production-20261017/authenticate_and_make_lossless_pages.py';tree=ast.parse(take(alg).decode());defs=[n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='upscale'];assert len(defs)==1;exec(compile(ast.Module(body=defs,type_ignores=[]),str(alg),'exec'),globals())
palraw=take(R/'data/misc/PALETTE_DAT');assert len(palraw)==768 and max(palraw)<=63;p=np.frombuffer(palraw,'u1').astype('u2');pal=((p<<2)|(p>>4)).astype('u1').reshape(256,3)
cat={}
for line in take(R/'data/INDEX').decode().splitlines():
 a,n,p=line.split();cat[a]=(int(n),R/'data'/p)
first=R/'.reference/hd-firstcampaign10536-1053e-Original-primary-pair-author-20261019-v1';single=R/'.reference/hd-firstcampaign1054f-and10561-Original-primary-singletons-author-20261019-v1';last=R/'.reference/hd-firstcampaign1059e-and105a4-105a7-Original-primary-author-20261019-v1'
cohorts=[(first,['10536','1053e']),(single/'1054f',['1054f']),(single/'10561',['10561']),(last/'singleton1059e',['1059e']),(last/'pair105a4-105a7',['105a4','105a7'])]
allmasterpaths=[f for folder,_ in cohorts for f in folder.glob('*RETURNED-UNTOUCHED.png')]
allmasters={hashlib.sha256(take(f)).hexdigest():f for f in allmasterpaths}
for a in [first/'AUTHOR-QUALIFIED2-WITH-LIMITS-ALL8-NATIVE-PORTABLE-READY.json',single/'AUTHOR-QUALIFIED-TWO-SINGLETONS-WITH-LIMITS-ALL8-NATIVE-PORTABLE-READY.json',last/'AUTHOR-QUALIFIED3-WITH-LIMITS-ALL12-NATIVE-PORTABLE-READY.json']:take(a)
rows=[];allpane=0;all_source_pixels=0
for folder,ids in cohorts:
 pack=folder/'final-reviewed-fine-selector-pack';candidate=json.loads(take(pack/'candidate.json'));frames={f'{s["base_asset"]+f["frame"]:05x}':f for s in candidate['sequences']for f in s['frames']};assert set(frames)==set(ids)
 Q=folder/'actual-once-final-current-SourceG2';qa=json.loads(take(Q/'runtime-qa.json'));assert qa['diagnostics']==[]and qa['validated_frames']==len(ids);assert qa['candidate_sha256']==sha(pack/'candidate.json');bank=json.loads(take(Q/'actual-indexed-source-and-scales.json'));bank={r['asset']:r for r in bank};assert set(bank)==set(ids)
 recipe=json.loads(take(pack/'reproducer/recipe.json'));derive_receipt=json.loads(take(folder/'actual-once-reviewed-fine-selector-derived/ACTUAL-DERIVATION-RECEIPT.json'))
 master=folder/('ACTUAL-ORIGINAL-PRIMARY-PAIR-RETURNED-UNTOUCHED.png'if folder==first else'ACTUAL-ORIGINAL-PRIMARY-RETURNED-UNTOUCHED.png');take(master);take(folder/'ACTUAL-BUILTIN-PRIMITIVE-RECEIPT.json')
 donor_pins={d['sha256']for d in recipe['donors'].values()};assert donor_pins<=set(allmasters) # Shared per-cohort recipes disclose both genuine masters, including unused donor slots.
 for d in recipe['donors'].values():assert hashlib.sha256(take(pack/'reproducer'/d['path'])).hexdigest()==d['sha256']
 for asset in ids:
  f=frames[asset];n,sourcepath=cat[asset];raw=take(sourcepath);assert len(raw)==n==1044 and list(struct.unpack('<5i',raw[:20]))==[1,1,0,32,32]and hashlib.sha256(raw).hexdigest()==f['source_sha256'];src=np.frombuffer(raw[20:],'u1').reshape(32,32).astype('u2');assert np.array_equal(src,np.array(bank[asset]['source']['indices'],dtype='u2').reshape(32,32));assert f['origin']==[0,0]and f['logical_width']==f['logical_height']==32
  artpath=pack/f['file'];take(artpath);assert sha(artpath)==qa['artwork_sha256'][f['file']];with_image=Image.open(artpath);art=np.asarray(with_image.convert('RGB'));assert art.shape==(512,512,3)
  src4=upscale(src,4);source512=np.repeat(np.repeat(pal[src4],4,0),4,1);protected512=np.repeat(np.repeat(src4>=240,4,0),4,1);assert np.array_equal(art[protected512],source512[protected512]);details=f.get('original_detail_cells',[]);srcppm=Q/f'{asset}-original.ppm';take(srcppm);assert np.array_equal(np.asarray(Image.open(srcppm).convert('RGB')),pal[src])
  pagepath=folder/'whole-final-Source-and-actual-native1to4'/f'{asset}-WHOLE-SourceNx-and-ACTUAL-G2-native1to4-NN3.png';take(pagepath);page=np.asarray(Image.open(pagepath).convert('RGB'));assert page.shape==(1680,840,3);scales=[]
  for v in bank[asset]['scales']:
   scale=v['scale'];assert scale in [1,2,3,4];a=np.array(v['indices'],dtype='u2').reshape(32*scale,32*scale);assert a.max()<256;source=upscale(src,scale);rgb=pal[a];ppm=Q/f'{asset}-hd-{scale}.ppm';take(ppm);assert np.array_equal(np.asarray(Image.open(ppm).convert('RGB')),rgb)
   # Reserved labels and explicit original detail ownership are exact; never HD credit.
   protected=source>=240;assert np.array_equal(a[protected],source[protected]);owner=np.zeros(src.shape,bool)
   for x,y in details:owner[y,x]=True
   owned=np.repeat(np.repeat(owner,scale,0),scale,1);assert np.array_equal(a[owned],source[owned])
   panes=[]
   for side,x,body in [('SourceNx',12,pal[source]),('actualG2',440,rgb)]:
    tile=np.repeat(np.repeat(body,3,0),3,1);hh,ww=tile.shape[:2];candidates=np.flatnonzero(np.all(page[:,x:x+ww]==tile[0],axis=(1,2)));found=[int(y)for y in candidates if y+hh<=page.shape[0]and np.array_equal(page[y:y+hh,x:x+ww],tile)];assert len(found)==1,(asset,scale,side,found);panes.append({'side':side,'xy':[x,found[0]],'size':[ww,hh],'NN_factor_exact':3,'full_saved_body_matches_exact_native_RGB':True});allpane+=1
   # Ancillary quantized variation evidence, not generated-detail/visual approval by count.
   s=np.pad(source,1,mode='edge');constant=np.ones(source.shape,bool)
   lo=a.copy();hi=a.copy()
   aa=np.pad(a,1,mode='edge')
   for dy in range(3):
    for dx in range(3):constant&=s[dy:dy+source.shape[0],dx:dx+source.shape[1]]==source;lo=np.minimum(lo,aa[dy:dy+a.shape[0],dx:dx+a.shape[1]]);hi=np.maximum(hi,aa[dy:dy+a.shape[0],dx:dx+a.shape[1]])
   allowed=constant&~owned&~protected;green_Source=(pal[source][:,:,1]>pal[source][:,:,0])&(pal[source][:,:,1]>pal[source][:,:,2]);green_actual=(rgb[:,:,1]>rgb[:,:,0])&(rgb[:,:,1]>rgb[:,:,2]);all_source_pixels+=a.size
   scales.append({'scale':scale,'dimensions':[v['width'],v['height']],'PPM_palette_indexed_body_exact':True,'SourceNx_protected_labels_exact_samples':int(protected.sum()),'Original_detail_owner_exact_samples_no_HD_credit':int(owned.sum()),'actual_nonfunctional_changed_from_SourceNx':int(np.count_nonzero((a!=source)&~owned&~protected)),'SourceNx_constant3x3_nonfunctional_positions':int(allowed.sum()),'actual_palette_variation_among_those_positions':int(np.count_nonzero(allowed&(lo!=hi))),'green_Source_support':int(green_Source.sum()),'actual_green_inside_Source_green_support':int(np.count_nonzero(green_Source&green_actual)),'actual_green_outside_Source_green_support':int(np.count_nonzero(~green_Source&green_actual)),'saved_page_panes':panes,'PPM_sha256':sha(ppm)})
  rows.append({'asset':asset,'Source':guards[str(sourcepath.absolute())],'candidate':guards[str((pack/'candidate.json').absolute())],'QA':guards[str((Q/'runtime-qa.json').absolute())],'derived_PNG':guards[str(artpath.absolute())],'untouched_parent_master':guards[str(master.absolute())],'original_detail_cells':details,'derived512_protected_SourceNx_RGB_exact_samples':int(protected512.sum()),'whole_page':guards[str(pagepath.absolute())],'scales':scales,'generated_detail_credit_for_Source_geometry_color_and_retained_labels':0})
# Input preservation by SHA/size/time/mode; no producer file is written.
for expected in guards.values():
 p=Path(expected['path']);s=p.stat();actual={'path':str(p),'sha256':sha(p),'size':s.st_size,'mtime_ns':s.st_mtime_ns,'mode':s.st_mode};assert actual==expected,p
report={'status':'PASS_INDEPENDENT_READONLY_SAVED7_NATIVE28_AND_SOURCE28_BODY_AUDIT_NOT_MATERIAL_APPROVAL','reviewer':'/root/grating_pair','rows':rows,'saved_body_readbacks':allpane,'actual_native_scales':28,'all_native_indexed_samples':all_source_pixels,'all_input_pins_unchanged':len(guards),'input_pins':list(guards.values()),'new_engine_QA_cleanup_image_context_calls':0,'physical_quality_judgment_separate':True,'limits':'Quantized nonfunctional differences/constantSource-neighborhood variation include low-frequency Source-guided interpolation as well as genuine band detail; these counts alone are not an attribution proof or approval. Actual whole raw/derived/native material judged physically, retained Original and Source geometry/color receive no HD credit.'}
p=O/'READONLY-SOURCE-RAW-DERIVED-INDEXED-PALETTE-ALL56-PAGE-BODIES-AND-RETENTION-AUDIT.json';assert not p.exists();p.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'audit_sha256':sha(p),'rows':len(rows),'native_panes':allpane//2,'total_Source_plus_native_panes':allpane,'pixels':all_source_pixels,'guards':len(guards),'summary':[{'asset':r['asset'],'retained_cells':len(r['original_detail_cells']),'scales':[{k:v for k,v in s.items()if k in ['scale','actual_palette_variation_among_those_positions','actual_nonfunctional_changed_from_SourceNx','green_Source_support','actual_green_inside_Source_green_support']}for s in r['scales']]}for r in rows]}))
