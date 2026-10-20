from pathlib import Path
import json,gzip,hashlib,io
import numpy as np
from PIL import Image
R=Path('/home/quintine/Projects/RaptorReplica/RustRaptor');P=R/'.reference/hd-shoreline4-H5647-affected-endpoint3-context-successor-author-20261019-v1';Old=R/'.reference/hd-shoreline4-currentG2-H5636-genuine-context-author-20261019-v1/actual-context18';D=P/'actual-affected-endpoint3-context';O=Path(__file__).parent
h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();A=P/'CLOSED-AUTHOR-H5647-REAL-103D6-ENDPOINT3-SUCCESSOR-QUALIFIED-WITH-LIMITS.json';assert h(A)=='087e8281c15e20edf3aa6129363f5ba6207e11a1558d0c45b3bf8fcb0336b797';a=json.loads(A.read_bytes());proof=D/'ACTUAL-SHORELINE4-G2-H5647-CHANGED-ENDPOINT3-ALL4-12-ROLE-BODIES.json';assert h(proof)==a['new_actual_proof_sha256'];q=json.loads(proof.read_bytes());old=json.loads((Old/'ACTUAL-SHORELINE4-G2-H5636-GENUINE18-ALL4-216-ROLE-BODIES.json').read_bytes());orirows={(v['endpoint_index'],v['scale']):v for v in old['records']};pal=np.frombuffer((D/'actual-palette-rgb.bin').read_bytes(),dtype='u1').reshape(256,3);assert pal.tobytes()==(Old/'actual-palette-rgb.bin').read_bytes()
cls=lambda z:np.where((z>=240)&(z<=244),1,np.where((z>=245)&(z<=249),2,np.where(z>=250,z,0))).astype('u1')
def load(root,kind,v):
 z=np.frombuffer(gzip.decompress((root/kind/v['indexed']).read_bytes()),dtype='<u2').reshape(v['height'],v['width']);assert z.max()<256;assert gzip.decompress((root/kind/v['classes']).read_bytes())==cls(z).tobytes();assert np.array_equal(np.asarray(Image.open(io.BytesIO(gzip.decompress((root/kind/v['PPM']).read_bytes())))),pal[z]);return z
for v in q['components']:load(D,'components',v)
page=np.asarray(Image.open(P/a['physical_review']['changed_pages'][0]['path']).convert('RGB'));pair=np.asarray(Image.open(P/a['physical_review']['changed_pages'][1]['path']).convert('RGB'));ret=0;y=64;count=0
for r in q['records']:
 s=r['scale'];oldr=orirows[3,s];rows=[load(D,'planes',r['planes'][k])for k in ['Original_joined_SourceNx','immutable_H5647_current','shoreline4_proposed']];original,cur,prop=rows;assert np.array_equal(original,load(Old,'planes',oldr['planes']['Original_joined_SourceNx']));assert np.array_equal(cls(cur),cls(original))and np.array_equal(cls(prop),cls(original));support=np.zeros(original.shape,dtype=bool)
 for x0,y0,x1,y1 in r['support_rectangles']:support[y0*s:y1*s,x0*s:x1*s]=True
 assert np.array_equal(cur[~support],prop[~support])
 for z,field in [(cur,'baseline_inputs'),(prop,'proposal_inputs')]:
  for v in r[field]['pre_blit']:
   xx,yy=v['position']
   for cx,cy in v['retained_cells']or[]:
    sl=np.s_[(yy+cy)*s:(yy+cy+1)*s,(xx+cx)*s:(xx+cx+1)*s];assert np.array_equal(z[sl],original[sl]);ret+=s*s
 for j,z in enumerate(rows):assert np.array_equal(page[y:y+96*s,8+j*396:8+j*396+96*s],pal[z]);count+=1
 if s==4:
  for j,z in enumerate(rows):assert np.array_equal(pair[64:448,8+j*396:392+j*396],pal[z]);count+=1
 y+=96*s+28
for j,k in enumerate(['Original_joined_SourceNx','immutable_H5636_current','shoreline4_proposed']):
 z=load(Old,'planes',orirows[15,4]['planes'][k]);assert np.array_equal(pair[472:856,8+j*396:392+j*396],pal[z]);count+=1
for v in a['physical_review']['changed_pages']:assert h(P/v['path'])==v['sha256']
assert ret==2670 and count==18 and len(q['records'])==4
report={'status':'DIFFERENT_QUALIFIED_H5647_CHANGED_ENDPOINT3_WITH_LIMITS','author':{'path':str(A),'sha256':h(A)},'new_proof_sha256':h(proof),'whole_pages_physically_viewed':a['physical_review']['changed_pages'],'saved_arrays_independently_checked':{'actual_planes':12,'components':36,'displayed_bodies':18,'Source4_byteexact_previous':True,'palette_cycling_classes_exact':True,'outside_support_exact':True,'retained_whole_control_samples_exact':ret},'findings':['Newly active103d6 bridge slats/edge and shoreline10515 remain correctly aligned; no new missing geometry or semantic object in changed four native contexts.','Ordered one-actor before/settled comparison preserves the genuine103d6→1050b event. Settled1050b remains coarse Original fallback with no HD credit.'],'limits':['Only affected endpoint3 newly rendered at literalH5647. Other17 endpoints retain earlier different qualification and finite input carry, not new render claims.','Ground/water texture is stronger than Original; neutral Source rim stepping and inherited water bands/contrasts remain visible as before. No seamless all-neighbor or timing/combat claim.'],'new_engine_QA_World_generation_cleanup_calls':0,'canonical_Git_mutation':False}
f=O/'DIFFERENT-QUALIFIED-SHORELINE4-H5647-ENDPOINT3-ALL4-AND-ORDERED-DELTA.json';f.write_text(json.dumps(report,indent=2)+'\n');print(f);print(h(f))
