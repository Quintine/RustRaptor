from pathlib import Path
import json,hashlib,gzip
import numpy as np
from PIL import Image,ImageDraw
P=Path(__file__).resolve().parent;Q=P/'actual-once-joint39-genuine11-STRICT-MANIFEST-V2-G2';x=json.load(open(Q/'ACTUAL-JOINT39-GENUINE11-SOURCEG2-H5654-CONTEXTS.json'));roles=['H5654_plus_consumer_cohort','H5654_plus_all39_joint'];rec={r['case_index']:r for r in x['records']if r['scale']==4};V=P/'Root-native4-lossless-review-pages';V.mkdir();pages=[]
def pin(p):return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
for start in range(0,11,3):
 batch=list(range(start,min(start+3,11)));im=Image.new('RGB',(808,len(batch)*420+24),(20,28,38));draw=ImageDraw.Draw(im);draw.text((8,4),'Root exactnative4 | LEFT consumercohort +H5654 | RIGHT joint39 +H5654',fill='white');bodies=[]
 for row,ci in enumerate(batch):
  r=rec[ci];c=r['endpoint'];y=24+row*420;draw.text((8,y),f'case{ci:02} {c["consumer_cohort"]} {c["mission"]} r{c["window_row0"]}c{c["window_column0"]}',fill='white')
  for col,role in enumerate(roles):
   src=Q/'planes'/r['planes'][role]['PPM'];ppm=gzip.decompress(src.read_bytes());header=b'P6\n384 384\n255\n';assert ppm.startswith(header);rgb=np.frombuffer(ppm[len(header):],dtype='u1').reshape(384,384,3);xx=8+400*col;yy=y+20;im.paste(Image.fromarray(rgb),(xx,yy));bodies.append({'case_index':ci,'role':role,'exact_actual_native4_PPM_gz':pin(src),'xywh':[xx,yy,384,384]})
 path=V/f'ROOT-joint39-cases{batch[0]:02}to{batch[-1]:02}-EXACT-native4-old-vs-joint.png';im.save(path);z=np.array(Image.open(path))
 for b in bodies:
  raw=gzip.decompress(Path(b['exact_actual_native4_PPM_gz']['path']).read_bytes());rgb=np.frombuffer(raw[len(b'P6\n384 384\n255\n'):],dtype='u1').reshape(384,384,3);xx,yy,w,h=b['xywh'];assert np.array_equal(z[yy:yy+h,xx:xx+w],rgb)
 pages.append({'page':pin(path),'dimensions':list(im.size),'complete_cases':batch,'complete_native4_bodies':bodies})
d={'status':'LOSSLESS_SAVED_ONLY_ROOT_CONTACT_REVIEW_ALL11_NATIVE4_22WHOLE_BODIES','new_raster_TerrainHd_QA_compile_calls':0,'no_resampling':True,'initial_wrong_python_import_stop_before_any_output':True,'pages':pages};p=P/'ROOT-ALL11-NATIVE4-LOSSLESS-REVIEW-PAGE-INDEX.json';p.write_text(json.dumps(d,indent=2)+'\n');print(pin(p));print('\n'.join(x['page']['path']for x in pages))
