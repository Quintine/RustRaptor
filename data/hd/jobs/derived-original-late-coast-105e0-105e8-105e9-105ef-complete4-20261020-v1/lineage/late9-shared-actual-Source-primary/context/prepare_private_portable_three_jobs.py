"""Source-only namespace packaging; measured data never rewritten in place."""
from pathlib import Path
import json,hashlib,copy,sys,os
O=Path(__file__).resolve().parent;R=O.parent.parent
A=R/'.reference/hd-firstcampaign105e0-105ef-and105f3-Original-primary-author-20261019-v1'
C=R/'.reference/hd-late9-isotropic-gray-material-successor-CODE-proposal-20261019-v2'
P=R/'.reference/hd-late9-private-portable-three-jobs-SourceG2-20261020-v1';H=P/'data/hd'
sys.path.insert(0,str(R/'tools'))
from hd_candidate_review import proposal_frames,binding_digest
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read=lambda p:json.loads(Path(p).read_bytes())
def put(p,v):
 p.parent.mkdir(parents=True,exist_ok=True);assert not p.exists();p.write_text(json.dumps(v,indent=2)+'\n')
def link(s,t):
 assert s.is_file()and not s.is_symlink();t.parent.mkdir(parents=True,exist_ok=True);assert not t.exists();os.link(s,t)
def linktree(s,t):
 for p in sorted(s.rglob('*')):
  if p.is_file():link(p,t/p.relative_to(s))
def ref(p):return dict(path=p.relative_to(H).as_posix(),sha256=sha(p))
groups={'coast4':'derived-original-late-coast-105e0-105e8-105e9-105ef-complete4-20261020-v1','ground4':'derived-original-late-ground-105e6-105e7-105eb-105ed-complete4-20261020-v1','ramp105f3':'derived-original-late-ramp-105f3-complete1-20261020-v1'}
assert not P.exists();first=H/'jobs'/groups['coast4'];L=first/'lineage/late9-shared-actual-Source-primary'
repro=L/'reproducer';link(C/'terrain_component_cleanup.py',repro/'terrain_component_cleanup.py');linktree(C/'inputs',repro/'inputs')
for p in C.glob('test_*.py'):link(p,L/'code-proposal'/p.name)
link(C/'FROZEN-ONLY-GRAY-SQUARE-DONOR-RECIPE-SUCCESSOR-READY.json',L/'code-proposal/FROZEN-RECIPE-SUCCESSOR-PROPOSAL.json')
link(A/'AUTHOR-SQUARE-GRAY-SUCCESSOR-QUALIFIED9-ALL36-NATIVE-FROZEN-HANDOFF.json',L/'author-intrinsic-verbatim.json')
link(A/'ACTUAL-SQUARE-GRAY-SUCCESSOR-SAVED-ALL-NATIVE-RETENTION-READBACK-AUDIT.json',L/'saved-native-exact-retention-audit-verbatim.json')
peer=r'.reference/hd-late9-square-gray-successor-different-review-20261019-v1/PASS-LATE9-SQUARE-GRAY-RECIPE-ONLY-SUCCESSOR-WITH-CONFIRMED-FIRST-TRIAL-MATERIAL-HOLD.json';link(R/peer,L/'different-recipe-CODE-input-verbatim.json')
link(A/'AUTHOR-FIRST-TRIAL-ALL9-MATERIAL-HOLD-ANISOTROPIC-GRAY-STRIP.json',L/'history/first-trial-author-material-HOLD-verbatim.json')
catalog={int(s.split()[0],16):s.split()[2]for s in(R/'data/INDEX').read_text().splitlines()}
result=[]
for g,jid in groups.items():
 d=A/g;J=H/'jobs'/jid;pack=d/'final-isotropic-gray-successor-pack';q=d/'actual-once-isotropic-gray-successor-current-SourceG2';old=read(pack/'candidate.json');new=copy.deepcopy(old);new.update(job_id=jid,complete_family=True)
 ids=[format(s['base_asset'],'05x')for s in new['sequences']]
 for seq in new['sequences']:
  for f in seq['frames']:
   name=f['file'];link(pack/name,J/name);f['file']=f'jobs/{jid}/{name}'
 new['publisher_namespace_scope']='Complete independent singleton Original Terrain pictures, selected4/4/1 only; not a complete numbered catalog family or new animation. Raw bytes/Source geometry/masks/native measured bodies unchanged; file routes only.'
 put(J/'candidate.json',new);put(J/'job.json',dict(format_version=1,category='Terrain',job_id=jid,kind='complete_native_family',owner='/root/remaining_catalog',targets=[dict(asset=format(s['base_asset'],'05x'),logical_canvas=[32,32],origin=[0,0],source_palette='PALETTE_DAT',source_palette_sha256='1cf6adb926d1dee1888b3e3d33b51a7049b3e5eb5f90a3067ef71c8970547204',source_path=catalog[s['base_asset']],source_sha256=s['frames'][0]['source_sha256'])for s in old['sequences']]))
 measured=L/'measurement'/g;link(pack/'candidate.json',measured/'actual-measured-candidate-verbatim.json');linktree(q,measured/'actual-current-SourceG2');link(d/'actual-once-isotropic-gray-successor-derived/ACTUAL-DERIVATION-RECEIPT.json',measured/'actual-derivation-receipt-verbatim.json')
 recipe=C/f'{g}-UNEXECUTED-RECIPE.json';link(recipe,repro/f'{g}-EXECUTABLE-PORTABLE-RECIPE.json')
 qa=copy.deepcopy(read(q/'runtime-qa.json'));rows=proposal_frames(new);qa['candidate_sha256']=sha(J/'candidate.json');qa['frame_bindings_sha256']=binding_digest(rows);qa['artwork_sha256']={f['file']:sha(H/f['file'])for f in rows.values()};qa['namespace_only_publisher_rebind_not_new_QA']=True;qa['namespace_rebind_scope']='Only file routes and candidate/hash bindings projected. Every original measured frame, exact native body, library/Source18 epoch and diagnostic remains literal; no new invocation.'
 put(J/'runtime-qa.json',qa)
 for aid,f in rows.items():
  x=copy.deepcopy(proposal_frames(old)[aid]);y=copy.deepcopy(f);x.pop('file');y.pop('file');assert x==y
 gen=L/'generation'/g
 for n in ['prepared-imagegen-arguments.json','prompt.txt','ACTUAL-REFERENCE-PINS.json','ACTUAL-BUILTIN-PRIMITIVE-RECEIPT.json']:link(d/n,gen/n)
 # The actual new master bytes are already present ONCE in the shared recipe inputs.
 raw=list(d.glob('ACTUAL-ORIGINAL-PRIMARY-*-RETURNED-UNTOUCHED.png'));assert len(raw)==1
 refmap=[]
 for j,x in enumerate(read(d/'ACTUAL-REFERENCE-PINS.json')):
  s=Path(x['path']);assert sha(s)==x['sha256']
  if s.is_relative_to(R/'data/hd'):
   refmap.append(dict(historical_path=x['path'],external_existing_HD_dependency=s.relative_to(R/'data/hd').as_posix(),sha256=x['sha256'],already_bundled_existing_HD_not_new_payload=True))
  else:
   t=gen/'references'/f'{j}-{s.name}';link(s,t);refmap.append(dict(historical_path=x['path'],portable=ref(t)))
 put(gen/'ACTUAL-REFERENCES-PORTABLE-ALIASES-NO-HISTORY-REWRITE.json',refmap)
 hist=L/'history'/g;link(d/'actual-once-final-current-SourceG2/runtime-qa.json',hist/'first-trial-QA-verbatim.json');link(d/'final-reviewed-fine-selector-pack/candidate.json',hist/'first-trial-candidate-verbatim.json')
 put(J/'PRIVATE-NAMESPACE-AND-LINEAGE-BRIDGE.json',dict(status='PRIVATE_NOT_ROOT_APPROVED_OR_REGISTERED',selected=ids,shared_lineage=ref(L/'author-intrinsic-verbatim.json'),literal_actual_candidate=ref(measured/'actual-measured-candidate-verbatim.json'),literal_actual_QA=ref(measured/'actual-current-SourceG2/runtime-qa.json'),literal_actual_bank=ref(measured/'actual-current-SourceG2/actual-indexed-source-and-scales.json'),actual_derivation=ref(measured/'actual-derivation-receipt-verbatim.json'),portable_recipe=ref(repro/f'{g}-EXECUTABLE-PORTABLE-RECIPE.json'),portable_replay_pending=True,original_QA_unmodified=True,new_QA_calls=0,Root_art_approval_pending=True))
 result.append(dict(job_id=jid,path=str(J),candidate=ref(J/'candidate.json'),QA=ref(J/'runtime-qa.json'),ids=ids,sequences=len(ids),new_output_bytes=sum((J/f'{aid}-derived.png').stat().st_size for aid in ids),portable_recipe=ref(repro/f'{g}-EXECUTABLE-PORTABLE-RECIPE.json')))
put(P/'PRIVATE-THREE-JOB-PORTABLE-NAMESPACE-PREPARED-PENDING-REVIEWS.json',dict(status='PRIVATE_SOURCE_ONLY_PORTABLE_PREPARATION_NOT_ADMISSION',jobs=result,selected9=sorted(aid for x in result for aid in x['ids']),genuine_masters3_once_in_shared_inputs=True,portable_replay_pending=True,different_intrinsic_pending=True,genuine_context_pending=True,Root_art_approval_pending=True,new_generation_cleanup_QA_World_calls=0,public_tools_untouched=True))
print(json.dumps(dict(jobs=len(result),selected=9,output_bytes=sum(x['new_output_bytes']for x in result),summary_sha256=sha(P/'PRIVATE-THREE-JOB-PORTABLE-NAMESPACE-PREPARED-PENDING-REVIEWS.json'))))
