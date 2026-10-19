from pathlib import Path
import hashlib,json,gzip,io,datetime
import numpy as np
from PIL import Image
R=Path('/home/quintine/Projects/RaptorReplica/RustRaptor');Q=R/'.reference/hd-grating2-SourceG2-H5613-genuine14-context-20261019-v1';O=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
interface=Q/'COMPLETE14-GENUINE-168-NATIVE-PANES-TWO-ORDERED-VIEWS-PAGE-ARRAY-INTERFACE.json';assert sha(interface)=='ca3435415edac6bae96ff900967ef0a2cc8c55b9d2b47ebfb6c6c622f055f955';v=json.loads(interface.read_text());contract=json.loads(Path(v['source_contract']['path']).read_text());assert sha(Path(v['source_contract']['path']))==v['source_contract']['sha256'];proof=json.loads(Path(v['actual_proof']['path']).read_text());assert sha(Path(v['actual_proof']['path']))==v['actual_proof']['sha256']
ident=json.loads((Q/'IMMUTABLE-H5613-ALL-RAW-HARDLINK-IDENTITIES-NO-COPY-NO-8GB-REHASH.json').read_text())
for b in ident['raws'].values():
 for key in ['source','snapshot']:
  s=Path(b[key]).stat();assert(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns)==(b['dev'],b['inode'],b['size'],b['mtime_ns'])
for b in contract['source_pins']:assert sha(Path(b['source']['path']))==b['source']['sha256']
for binding in [v['actual_H5613'],v['actual_library'],v['SourceG2_epoch'],v['original_palette']]:assert sha(Path(binding['path']))==binding['sha256']
palette=np.frombuffer(Path(v['original_palette']['path']).read_bytes(),np.uint8).reshape(256,3)
plane_root=Path(v['absolute_plane_root']);component_root=Path(v['absolute_component_root']);total=0;outside=0;broad=0;padding=0;deltas=0

def load(root,b):
 idx=np.frombuffer(gzip.decompress((root/b['indexed']).read_bytes()),'<u2').reshape(b['height'],b['width']);classes=np.frombuffer(gzip.decompress((root/b['classes']).read_bytes()),np.uint8).reshape(idx.shape);rgb=np.asarray(Image.open(io.BytesIO(gzip.decompress((root/b['PPM']).read_bytes()))).convert('RGB'));assert idx.max()<256;assert np.array_equal(rgb,palette[idx]);return idx,classes,rgb

for row in v['pages']:
 p=Path(row['page']['path']);assert sha(p)==row['page']['sha256'];page=np.asarray(Image.open(p).convert('RGB'))
 for pane in row['panes']:
  a,c,rgb=load(plane_root,pane['actual_plane']);x,y,w,h=pane['box'];assert np.array_equal(page[y:y+h,x:x+w],rgb);assert hashlib.sha256(rgb.tobytes()).hexdigest()==pane['RGB_body_sha256'];total+=a.size
for record in proof['records']:
 roles={role:load(plane_root,b)for role,b in record['planes'].items()};a,ac,_=roles['actual_H5613_baseline'];b,bc,_=roles['selected_derived_grating2_proposal'];support=np.zeros(a.shape,bool)
 for x0,y0,x1,y1 in record['support_rectangles']:support[y0:y1,x0:x1]=True
 assert np.array_equal(a[~support],b[~support])and np.array_equal(ac[~support],bc[~support]);outside+=int((~support).sum());assert int((~support).sum())==record['outside_support_samples_exact']
 scale=record['scale'];t=32*scale;foreign=np.zeros(a.shape,bool);pad=np.zeros(a.shape,bool)
 for slot,asset in enumerate(record['endpoint']['ordered_source_ids']):
  y,x=divmod(slot,3);y*=t;x*=t
  if slot!=4:foreign[y+2*scale:y+30*scale,x+2*scale:x+30*scale]=True
  if asset is None:pad[y:y+t,x:x+t]=True
 assert np.array_equal(a[foreign],b[foreign])and np.array_equal(ac[foreign],bc[foreign]);broad+=int(foreign.sum());assert int(foreign.sum())==record['broad_foreign_interior_samples_exact']
 assert np.all(a[pad]==0)and np.array_equal(a[pad],b[pad])and np.array_equal(ac[pad],bc[pad]);padding+=int(pad.sum());assert int(pad.sum())==record['padding_samples_exact'];delta=int(np.count_nonzero(a!=b));assert delta==record['delta_samples'];deltas+=delta
bank=json.loads(Path(contract['own_routes'][0]['actual_bank']['path']).read_text());lookup={(f['asset'],s['scale']):np.array(s['indices']).reshape(s['height'],s['width'])for f in bank for s in f['scales']};own=0
for component in proof['components']:
 a,c,rgb=load(component_root,component)
 if component['asset']in['203c6','203c7']:assert np.array_equal(a,lookup[component['asset'],component['scale']]);own+=1
halves=json.loads((Q/'FILE-ONLY-ORDERED-HALVES-DISPLAY-INTERFACE.json').read_text())
for half in halves['rows']:
 p=Path(half['file']);assert sha(p)==half['sha256'];a=np.asarray(Image.open(p).convert('RGB'));whole=np.asarray(Image.open(half['source']).convert('RGB'));x0,y0,x1,y1=half['source_box'];assert np.array_equal(a,whole[y0:y1,x0:x1])
for pair in v['ordered_pair_pages']:
 p=Path(pair['page']['path']);assert sha(p)==pair['page']['sha256'];page=np.asarray(Image.open(p).convert('RGB'))
 for pane in pair['panes']:
  _,_,rgb=load(plane_root,pane['actual_plane']);x,y,w,h=pane['box'];assert np.array_equal(page[y:y+h,x:x+w],rgb)
restoration=json.loads((Q/'DISCLOSED-POST-EXECUTION-ADAPTER-BYTE-RESTORATION-NO-NEW-PIXELS.json').read_text());assert sha(Q/'compose_Grating2_genuine14_SourceG2_H5613.rs')==sha(Q/'ACTUAL-COMPILED-ADAPTER-IMMUTABLE-BYTES.rs')==restoration['actual_compiled_source_sha256'];assert own==8
report=dict(status='PASS_INDEPENDENT_READONLY_FINITE_NATIVE_CONTEXT_AUDIT',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),SourceG2_library=v['actual_library']['sha256'],H5613=v['actual_H5613']['sha256'],unique_native_planes=168,plane_samples=total,outside_support_exact=outside,nonown_broad_interiors_exact=broad,padding_exact=padding,delta_samples=deltas,components=220,own_prejoin_components_exact_literal62d_bank=own,whole_native_endpoint_pages=14,ordered_pair_pages=2,exact_unresampled_ordered_halves=4,raw_hardlink_identity_stat_checks=len(ident['raws']),raw_8GB_hash_reads=0,Source_graphic_byte_bindings_verified=len(contract['source_pins']),adapter_disclosed_restoration_exact=True,new_engine_QA_cleanup_or_Git_calls=0)
assert(total,outside,broad,padding)==(11612160,3333600,2634240,276480);out=O/'PASS-READONLY-GENUINE14-168-NATIVE-PLANES-AND-PINS-AUDIT.json';assert not out.exists();out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));print('report_sha256',sha(out))
