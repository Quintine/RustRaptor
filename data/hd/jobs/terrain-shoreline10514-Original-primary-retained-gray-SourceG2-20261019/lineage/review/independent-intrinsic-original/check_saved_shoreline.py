from pathlib import Path
import struct,json,hashlib
import numpy as np
from PIL import Image
O=Path(__file__).resolve().parent;R=O.parents[1];P=R/'.reference/hd-iron-names-terrain10510-1051c-Original-primary-author-20261019-v1/shoreline4';D=P/'actual-SourceG2-intrinsic'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def js(p):return json.loads(Path(p).read_text())
def decode(data):
 kind,_,_,w,h=struct.unpack_from('<5i',data);a=np.full((h,w),256,np.uint16)
 if kind==1:return np.frombuffer(data[20:20+w*h],np.uint8).reshape(h,w).astype(np.uint16)
 assert kind==0;o=20
 while True:
  x,y,d,n=struct.unpack_from('<4i',data,o);o+=16
  if d==-1:break
  assert 0<=y<h and x>=0 and n>0 and x+n<=w;a[y,x:x+n]=np.frombuffer(data[o:o+n],np.uint8);o+=n
 return a
def nx(a,s):
 if s==1:return a.copy()
 if s==4:return nx(nx(a,2),2)
 H,W=a.shape;o=np.empty((H*s,W*s),np.uint16);pad=np.pad(a,1,mode='edge')
 for y in range(H):
  for x in range(W):
   A,B,C,D,E,F,G,Hh,I=pad[y:y+3,x:x+3].ravel();p=[E]*(s*s)
   if B!=Hh and D!=F:
    if s==2:p=[D if D==B else E,F if B==F else E,D if D==Hh else E,F if Hh==F else E]
    else:p=[D if D==B else E,B if (D==B and E!=C)or(B==F and E!=A) else E,F if B==F else E,D if (D==B and E!=G)or(D==Hh and E!=A) else E,E,F if (B==F and E!=I)or(Hh==F and E!=C) else E,D if D==Hh else E,Hh if (D==Hh and E!=I)or(Hh==F and E!=G) else E,F if Hh==F else E]
   o[y*s:(y+1)*s,x*s:(x+1)*s]=np.array(p).reshape(s,s)
 return o
ids=['10514','10515','1051b','1051c'];cand=js(P/'candidate-notes.json');author=js(P/'AUTHOR-QUALIFIED4-CURRENT-SOURCEG2-INTRINSIC-ONLY.json');qa=js(D/'runtime-qa.json');bank=js(D/'actual-indexed-source-and-scales.json');iv=js(D/'ACTUAL-CURRENT-SOURCEG2-INVOCATION.json');assert sha(D/'runtime-qa.json')=='915185ad8677adbe9cf58a56a570a7fbd969f9de81385e6455fbec77b2d4d89d';assert sha(P/'returned-untouched-atlas.png')=='eca43a75313243b03f67731e79b50fcbc9388a3e05ce06f38ac064fb60a3237d';assert qa['diagnostics']==[]and qa['validated_frames']==4;assert qa['candidate_sha256']==qa['candidate_sha256_at_start']==sha(P/'candidate-notes.json')==author['candidate_sha256'];assert iv['exit_code']==0 and iv['runtime_QA_sha256']==sha(D/'runtime-qa.json') and iv['indexed_bank_sha256']==sha(D/'actual-indexed-source-and-scales.json');assert sha(R/qa['library'])==qa['library_sha256'];assert all(sha(R/n)==h for n,h in qa['actual_sourceG2_source18_sha256'].items());assert sha(R/qa['review_helper_source'])==qa['review_helper_source_sha256'];assert qa['actual_new_helper_invocations']==1
entries={int(i,16):(int(n),R/'data'/f)for i,n,f in (l.split()for l in (R/'data/INDEX').read_text().splitlines()if l.strip())};vga=np.frombuffer((R/'data/misc/PALETTE_DAT').read_bytes(),np.uint8).reshape(256,3);palette=(vga<<2)|(vga>>4);raw=np.array(Image.open(P/'returned-untouched-atlas.png').convert('RGBA'));assert raw.shape==(1254,1254,4)and(raw[:,:,3]==255).all();reference=np.array(Image.open(P/'Original-only-input.png').convert('RGB'));assert reference.shape==(1024,1024,3)
frames=[];source_total=0;native_total=0;retained_total=0
for n,(b,target) in enumerate(zip(bank,cand['targets'])):
 asset=ids[n];assert b['asset']==target['asset']==asset;size,path=entries[int(asset,16)];payload=path.read_bytes();assert len(payload)==size and sha(path)==target['source_sha256'];a=decode(payload);assert a.shape==(32,32)and(a<256).all()and b['source']['indices']==a.ravel().tolist();assert target['origin']==[0,0]and target['logical_width']==target['logical_height']==32
 cells=target['original_detail_cells'];gray=set(map(tuple,np.argwhere((a>=17)&(a<=24))[:,::-1].tolist()));assert set(map(tuple,cells))==gray;assert len(cells)==[33,35,49,24][n];assert cells==sorted(cells)and len(cells)==len(set(map(tuple,cells)))
 cell=raw[(n//2)*627:(n//2+1)*627,(n%2)*627:(n%2+1)*627];art=P/'private-hd'/target['file'];assert np.array_equal(np.array(Image.open(art).convert('RGBA')),cell);assert qa['artwork_sha256'][target['file']]==sha(art);orig=palette[a];refcell=reference[(n//2)*512:(n//2+1)*512,(n%2)*512:(n%2+1)*512];assert np.array_equal(refcell,np.repeat(np.repeat(orig,16,0),16,1));assert np.array_equal(np.array(Image.open(D/f'{asset}-original.ppm')),orig)
 rows=[]
 for s,ss in enumerate(b['scales'],1):
  actual=np.array(ss['indices'],np.uint16).reshape(32*s,32*s);assert(actual<256).all();expected=nx(a,s);mask=np.zeros(actual.shape,bool)
  for x,y in cells:mask[y*s:(y+1)*s,x*s:(x+1)*s]=True
  assert np.array_equal(actual[mask],expected[mask]);owner=np.repeat(np.repeat(a,s,0),s,1);classes=lambda ar:np.select([(ar>=240)&(ar<=244),(ar>=245)&(ar<=249),(ar>=250)&(ar<=255)],[1,2,3],0);assert np.array_equal(classes(actual)[~mask],classes(owner)[~mask]);assert np.array_equal(np.array(Image.open(D/f'{asset}-hd-{s}.ppm')),palette[actual]);retained_total+=int(mask.sum());native_total+=actual.size;rows.append(dict(scale=s,opaque_samples=int(actual.size),retained_OriginalNx_samples=int(mask.sum()),retained_ordinary_gray_or_neighbor_samples=int(np.count_nonzero(mask&(expected<240))),retained_reserved_neighbor_samples=int(np.count_nonzero(mask&(expected>=240))),outside_retained_reserved_class_owner_exact=True))
 source_total+=a.size;frames.append(dict(asset=asset,source_sha256=sha(path),source_palette_gray_indices=sorted(set(int(a[y,x])for x,y in cells)),all_Original_gray_cells_declared=True,gray_logical_cells=len(cells),raw_direct_cell_RGBA_exact=True,raw_cell_coordinates=[(n%2)*627,(n//2)*627,627,627],scales=rows))
# Pin all existing producer files; do not write inside their tree.
pins={str(p.relative_to(P)):dict(sha256=sha(p),bytes=p.stat().st_size)for p in sorted(P.rglob('*'))if p.is_file()}
out=dict(status='PASS_LITERAL_ORIGINAL_SOURCE_PALETTE_GRAY_OWNERS_AND_SAVED_NATIVE_RGBA',ids=ids,frames=frames,Source_indices=source_total,actual_native_indices=native_total,retained_OriginalNx_samples=retained_total,retained_samples_generated_HD_credit=0,producer_files_verified=len(pins),producer_files=pins,actual_current_G2_QA_sha256=sha(D/'runtime-qa.json'),raw_master_sha256=sha(P/'returned-untouched-atlas.png'),candidate_sha256=sha(P/'candidate-notes.json'),actual_Source18_current_bytes_exact=True,read_only_check_script_sha256=sha(__file__),new_intrinsic_QA_cleanup_generation_World_build_calls=0)
(O/'INDEPENDENT-EXACT-SOURCE-GRAY-OWNERS-RAW-CROPS-AND-NATIVE-CHECKS.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items()if k not in ['frames','producer_files']},indent=2))
