from pathlib import Path
import json,hashlib,gzip,io,ast
import numpy as np
from PIL import Image
R=Path('/home/quintine/Projects/RaptorReplica/RustRaptor');P=R/'.reference/hd-six10536-1053e-1054f-10561-1059e-1059e-105a7-currentG2-H5647-genuine9-context-20261019-v1'
P=R/'.reference/hd-six10536-1053e-1054f-10561-1059e-105a7-currentG2-H5647-genuine9-context-20261019-v1';O=Path(__file__).parent;sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();A=P/'CLOSED-AUTHOR-QUAL6-GENUINE9-LEGAL4-ALLNATIVE-H5647-CONTEXT.json';assert sha(A)=='e66205674462bc85da84b343a9f712708e6c5e70bf75ccab5860b88a1f2ebfc0';a=json.loads(A.read_bytes())
for k in ['different_intrinsic','source_census_and_endpoints','actual_compile','actual_compositor_source','actual_compositor','actual_terminal','input_pins','historic_actualH5647_full_header','strict_audit']:assert sha(Path(a[k]['path']))==a[k]['sha256']
pins=json.loads(Path(a['input_pins']['path']).read_bytes())
for path,h in pins['pins'].items():
 if Path(path)==R/'data/hd/hd.json':assert sha(Path(a['historic_actualH5647_full_header']['path']))==h
 elif Path(path)==R/'data/hd/provenance.json':pass # Historical hash witness only; current appended metadata is not a pixel contributor.
 else:assert sha(Path(path))==h,path
x=json.loads(Path(a['actual_compositor']['path']).read_bytes());D=Path(a['actual_compositor']['path']).parent;pal=np.frombuffer((D/'actual-palette-rgb.bin').read_bytes(),dtype='u1').reshape(256,3);roles=['Original_joined_SourceNx','immutable_H5647_baseline','qualified6_proposal'];cl=lambda z:np.where(z<240,0,np.where(z<245,1,np.where(z<250,2,z))).astype('u1')
alg=R/'.reference/hd-terrain1-20273-20275-currentC-5384-bounded-context-production-20261017/authenticate_and_make_lossless_pages.py';nodes=[n for n in ast.parse(alg.read_bytes()).body if isinstance(n,ast.FunctionDef)and n.name in ['cls','upscale']];exec(compile(ast.Module(body=nodes,type_ignores=[]),str(alg),'exec'),globals());idx={int(t[0],16):t[2]for l in(R/'data/INDEX').read_text().splitlines()if(t:=l.split())}
def load(r,folder):
 z=np.frombuffer(gzip.decompress((D/folder/r['indexed']).read_bytes()),dtype='<u2').reshape(r['height'],r['width']);assert z.max()<256 and gzip.decompress((D/folder/r['classes']).read_bytes())==cl(z).tobytes();assert np.array_equal(np.asarray(Image.open(io.BytesIO(gzip.decompress((D/folder/r['PPM']).read_bytes())))),pal[z]);return z
for v in x['components']:load(v,'components')
counts={'samples':0,'outside':0,'changes':0,'retained':0,'bodies':0};rows={}
for r in x['records']:
 s=r['scale'];aa=[load(r['planes'][role],'planes')for role in roles];ori,base,prop=aa;joined=np.zeros((96,96),dtype='<u2')
 for t,v in enumerate(r['endpoint']['ordered_source_ids']):
  if v is not None:joined[t//3*32:(t//3+1)*32,t%3*32:(t%3+1)*32]=np.frombuffer((R/'data'/idx[int(v,16)]).read_bytes()[20:],dtype='u1').reshape(32,32)
 assert np.array_equal(upscale(joined,s),ori)
 for z in aa:assert np.array_equal(cl(z),cl(ori));counts['samples']+=z.size
 support=np.zeros(ori.shape,dtype=bool)
 for x0,y0,x1,y1 in r['support_rectangles']:support[y0*s:y1*s,x0*s:x1*s]=True
 assert np.array_equal(base[~support],prop[~support]);counts['outside']+=int((~support).sum());counts['changes']+=int(np.count_nonzero(base!=prop))
 for role,field in [(base,'baseline_inputs'),(prop,'proposal_inputs')]:
  for part in r[field]['pre_blit']:
   px,py=part['position']
   for cx,cy in part.get('retained_cells')or[]:
    sl=np.s_[(py+cy)*s:(py+cy+1)*s,(px+cx)*s:(px+cx+1)*s];assert np.array_equal(role[sl],ori[sl]);counts['retained']+=s*s
 rows[r['case_index'],s]=aa
for p in a['physical_review']['pages']+a['physical_review']['pair_pages']:assert sha(Path(p['path']))==p['sha256']
audit=json.loads(Path(a['strict_audit']['path']).read_bytes())
for part in audit['pages']:
 s=part['scale'];side=96*s;dec=np.asarray(Image.open(part['path']).convert('RGB'))
 for t,case in enumerate(part['cases']):
  for role,z in enumerate(rows[case,s]):assert np.array_equal(dec[50+t*(side+34):50+t*(side+34)+side,role*side:(role+1)*side],pal[z]);counts['bodies']+=1
for part in audit['pair_pages']:
 dec=np.asarray(Image.open(part['path']).convert('RGB'))
 for t,case in enumerate([part['pair']['before'],part['pair']['after']]):
  for role,z in enumerate(rows[case,4]):assert np.array_equal(dec[52+t*414:436+t*414,role*384:(role+1)*384],pal[z]);counts['bodies']+=1
assert counts=={'samples':7464960,'outside':2193600,'changes':147460,'retained':450,'bodies':132},counts
out={'status':'PASS_DIFFERENT_ALL108_PLANES_132_PAGE_BODIES_AND_SOURCE_CONTROLS','counts':counts,'finite_nonheader_input_pins_exact':len(pins['pins'])-2,'historic_H5647_manifest_exact':True,'historic_provenance_hash_current_append_not_rechecked':pins['pins'].get(str(R/'data/hd/provenance.json')),'actual_components':len(x['components']),'Source_control_canonical_original_wholeScaleNx_exact':True,'all_roles_palette_index_classes_PPM_exact':True,'epoch':'literalSourceG2/H5647','new_QA_World_composition_generation_cleanup':0};f=O/'ACTUAL-DIFFERENT-SAVED-FINE6-GENUINE9-108PLANES-AND132-BODIES.json';f.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
