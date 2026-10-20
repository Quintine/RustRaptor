"""Project frozen39 plus auditor-bound50 exact renderer rows into strict private89 overlay."""
from pathlib import Path
import copy,hashlib,json,os,shutil
R=Path('/home/quintine/Projects/RaptorReplica/RustRaptor');P=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def pin(p):
 p=Path(p);s=p.stat();return {'path':str(p),'sha256':sha(p),'size':s.st_size,'mtime_ns':s.st_mtime_ns,'mode':s.st_mode}
def save(n,d):
 p=P/n
 body=json.dumps(d,indent=2)+'\n'
 if p.exists():assert p.read_text()==body,str(p)
 else:p.write_text(body)
 return pin(p)
assert shutil.disk_usage(P).free>1932735284+260000000
source=P/'SOURCE-ONLY-EXACT35-ORIGINAL-ENDPOINTS-AND-OPTIONAL-LEGAL-STATE-VERIFICATION.json'
assert sha(source)=='9e928d46f48c5fed0041104e20d2605e07dacb80db9c847f81de768c845ffad9'
S=json.loads(source.read_text());Apath=Path(S['source_audit']['path']);assert sha(Apath)==S['source_audit']['sha256'];A=json.loads(Apath.read_text())
Fpath=Path(A['frozen39_renderer_map']['path']);assert sha(Fpath)==A['frozen39_renderer_map']['sha256'];F=json.loads(Fpath.read_text())
assert sha(F['candidate']['path'])==F['candidate']['sha256'];C39=json.loads(Path(F['candidate']['path']).read_text())
audit39=R/'.reference/hd-next39-independent-cross-cohort-consumed-input-audit-20261020-v1/ALL39-CROSS-COHORT-CONSUMED-INPUT-INTERSECTIONS-AND-MINIMAL-JOINT-ENDPOINTS.json'
assert sha(audit39)=='d074a0b6e264567d7846316abc42facba1cca066ad34e2ccca32b06963c7b956';A39=json.loads(audit39.read_text())
root=P/'frozen89-strict-runtime-overlay';root.mkdir(exist_ok=True);seqs=[];mapping={};targetcohorts={};fullunprojected={}
def add(a,seq,raw,original,cohort,authority):
 assert a not in mapping and len(seq['frames'])==1 and seq['frame_count']==1 and seq['base_asset']==int(a,16)
 fr=seq['frames'][0];assert fr['frame']==0 and fr['source_sha256']==original['sha256'];assert sha(original['path'])==original['sha256'];assert sha(raw['path'])==raw['sha256']
 projected=copy.deepcopy(seq);rel='raw/'+raw['sha256']+'.png';projected['frames'][0]['file']=rel
 q=root/rel;q.parent.mkdir(exist_ok=True)
 if q.exists():assert sha(q)==raw['sha256']
 else:os.link(raw['path'],q)
 fullunprojected[a]=copy.deepcopy(seq);seqs.append(projected);targetcohorts[a]=cohort
 mapping[a]={'cohort':cohort,'unprojected_sequence':seq,'strict_private_runtime_sequence':projected,'raw':pin(q),
  'original_provider_bound_raw':raw,'Original_source':original,'material_authority':authority,
  'only_renderer_frame_change':'file path projected to private content-addressed hardlink; all other frame/sequence fields unchanged'}
for seq in C39['sequences']:
 a=f'{seq["base_asset"]:05x}';fr=seq['frames'][0];raw=F['raw_files'][fr['file']]
 # Exact Source path is independently found through INDEX below; hash is in frozen frame.
 src=next(line.split()[2]for line in (R/'data/INDEX').read_text().splitlines()if line.split()and int(line.split()[0],16)==int(a,16))
 add(a,seq,{'path':raw['source'],'sha256':raw['sha256']},{'path':str(R/'data'/src),'sha256':fr['source_sha256']},'next39:'+A39['all39_targets'][a],pin(Fpath))
assert len(mapping)==39
for a,b in sorted(A['future50_actual_frame_bindings'].items()):
 mp=Path(b['manifest']['path']);assert sha(mp)==b['manifest']['sha256'],str(mp)
 manifest=json.loads(mp.read_text());matched=[s for s in manifest['sequences']if s['base_asset']==int(a,16)];assert len(matched)==1
 seq=matched[0];assert seq['frames']==[b['frame']],a
 add(a,seq,b['raw'],b['Original_source'],b['cohort'],{'audit':pin(Apath),'literal_manifest':b['manifest']})
assert len(mapping)==89 and set(mapping)==set(A39['all39_targets'])|set(A['all50_targets'])
strict={'format_version':1,'name':'Private SourceG2 capturedH5654 plus exact89 proposed renderer overlay','sequences':sorted(seqs,key=lambda s:s['base_asset'])}
strictbody=json.dumps(strict,indent=2)+'\n'
if (root/'hd.json').exists():assert (root/'hd.json').read_text()==strictbody
else:(root/'hd.json').write_text(strictbody)
M=save('FROZEN-ALL89-EXACT-MATERIAL-ROWS-RAW-PINS-AND-PRIVATE-FILE-PROJECTION.json',{
 'status':'FROZEN89_RENDERER_FIELDS_AND_EXACT_RAW_BYTES_NOT_REGISTERED', 'projection':'Only file paths changed to private SHA-named hardlinks; rawbytes/allotherfullsequencefields exact.',
 'strict_runtime_overlay':pin(root/'hd.json'),'frames':mapping,'renderer_rows_sha256':hashlib.sha256(json.dumps(strict['sequences'],sort_keys=True,separators=(',',':')).encode()).hexdigest(),
 'literal_frozen39':pin(Fpath),'literal_future50_Source_audit':pin(Apath),'full89_registered_only_for_eligibility':True,
 'original_central_future50_normalization_pending':'Later canonical job-route normalization may differ; this actual check is bound to these renderer fields and raw bytes, never mutable coordinator headers.'})
base=R/'.reference/hd-next39-joint11-SourceG2-H5654-context-author-20261020-v1/immutable-H5654-baseline'
assert sha(base/'hd.json')=='104dc8f0d154f6a3e8edf6c72283205cb1f323daf8c225a8ca3a56680ac87f5b'
baseHD=json.loads((base/'hd.json').read_text());native={f'{s["base_asset"]+f["frame"]:05x}':{'frame':f,'sequence_header':{k:v for k,v in s.items()if k!='frames'}}for s in baseHD['sequences']for f in s['frames']}
assert len(native)==5654 and not(set(mapping)&set(native))
allsource=set(S['finite_Source_sprite_pins']);own=sorted(allsource&set(mapping));foreign=sorted(allsource&set(native));fallback=sorted(allsource-set(mapping)-set(native));assert len(own)==30 and len(foreign)==81 and not fallback
bindings={}
for a,src in S['finite_Source_sprite_pins'].items():
 assert sha(src['path'])==src['sha256']
 if a in mapping:
  seq=mapping[a]['strict_private_runtime_sequence'];n={'frame':seq['frames'][0],'sequence_header':{k:v for k,v in seq.items()if k!='frames'},'raw':mapping[a]['raw']}
 else:n={**native[a],'raw':pin(base/native[a]['frame']['file'])}
 bindings[a]={'source':pin(src['path']),'native':n}
B=save('FINITE-JOINT35-CONSUMED-SOURCE-NATIVE-RAW-BINDINGS.json',{'bindings':bindings,'old5654_foreign':foreign,'new89_consumed':own,'Original_fallbacks':fallback,
 'captured5654_manifest':pin(base/'hd.json'),'strict89_manifest':pin(root/'hd.json'),'all89_projection':M,
 'baseline_eligibility':'Reuse existing hardlinked complete5654 carrier read-only; finite consumed closure individually hashed; no full raw copy.'})
cases=copy.deepcopy(S['cases'])
for c in cases:
 consumer=c['consumer_cohort'];c['cohort_selected']=sorted(a for a,g in targetcohorts.items()if g==consumer);assert c['cohort_selected'],consumer
 ids={a for a in c['ordered_source_ids']if a is not None};added=ids & (set(own)-set(c['cohort_selected']))
 c['same_family_final_version_only']=not bool(added)
 if not added:assert c['case_index']==8 and any('10521'in old['same_family_changed_art_version']for old in c['old_context_routes']),c['case_index']
sourceqa=R/'.reference/hd-followon10370-302e1-30380-30465-40372-Original-primary-author-20261019-v1/10370/actual-once-final-current-SourceG2/runtime-qa.json';src18=json.loads(sourceqa.read_text())['actual_sourceG2_source18_sha256'];assert len(src18)==18
for rel,h in src18.items():assert sha(R/rel)==h,(rel,h,sha(R/rel))
SP=save('PRECOMPILE-EXACT-SOURCE18-AND-FROZEN89-INPUT-VERIFICATION.json',{'Source18':src18,'sourceqa':pin(sourceqa),
 'Original_MAP_FLATS_INDEX_pins':S['Original_INDEX_palette_all27MAP_all4FLATS'],'palette':pin(R/'data/misc/PALETTE_DAT'),
 'source_only35':pin(source),'actual89_map':M,'literal5654':pin(base/'hd.json')})
expected={'windows':35,'records':140,'roles':560,'Source':111,'foreign':81,'own_used':30,'fallback':0,'components':444,'stages':120,'baseline_count':5654,'proposed_count':89,'maps':27,
 'logical_tile_slots':sum(c['width_tiles']*c['height_tiles']for c in cases)}
recipe={'status':'SEALED_ALL89_GENUINE35_CURRENT_SOURCEG2_H5654','Root_GO':True,'data_root':str(R/'data'),'baseline_root':str(base),'own_root':str(root),
 'selected_proposals':sorted(mapping),'selected':own,'cases':cases,'finite_bindings':B,'Source18_verification':SP,'publisher89freeze':M,'expected':expected,
 'limits':['Actual captured5654 accepted baseline plus strict89 overlay, not a full5743 or5693 manifest; later canonical normalization does not relabel this saved epoch.',
 'Fresh controls: globalOriginalNx / captured5654 / captured5654+consumer selected FINAL artwork / all89joint. Literal older cohort saved scenes/old10521 HOLD are preserved historically, not relabeled or pasted into actual composition.',
 '35 bounded true Original endpoints including2 independently verified legal oneactor optional cardinal pairs; no World/natural timing/full mission claim.',
 'Protected ordinary/functional Source geometry remains globalOriginalNx after joins and earns zero generatedHD credit.',
 'All89definitions registered for eligibility; only111 finite consumed sources/81old+30new are decoded at native1..4. No extra intrinsic QA or game-engine build.']}
rp=save('SEALED-ALL89-GENUINE35-SOURCEG2-H5654-RECIPE.json',recipe)
save('ROOT-BOUNDED-JOINT35-AUTHORITY-AND-COUNTS.json',{'Root_explicit_authority':'Proceed33affected plus2truelegal oneactor optional endpoints; freeze auditor5946actual50+frozen39 rows now, do not wait central filemap; unchanged SourceG2staticTerrainHd; no World/enginebuild/intrinsicQA. No oldunrepaired10521 extra control required.',
 'recipe':rp,'expected':expected,'actual_compile_constructor_calls_so_far':0,'free_bytes':shutil.disk_usage(P).free})
print(json.dumps({'expected':expected,'recipe':rp,'overlay_map':M,'free_bytes':shutil.disk_usage(P).free},indent=2))
