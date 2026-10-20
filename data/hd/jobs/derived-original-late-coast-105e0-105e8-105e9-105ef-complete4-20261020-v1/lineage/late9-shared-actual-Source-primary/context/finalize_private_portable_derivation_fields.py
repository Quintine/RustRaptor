"""Read-only normalization of actual byte-equal recipe executions; no new art/QA."""
from pathlib import Path
import json,hashlib,copy,sys,os
O=Path(__file__).resolve().parent;R=O.parent.parent;P=R/'.reference/hd-late9-private-portable-three-jobs-SourceG2-20261020-v1';H=P/'data/hd'
sys.path.insert(0,str(R/'tools'));from hd_candidate_review import proposal_frames,binding_digest
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read=lambda p:json.loads(Path(p).read_bytes())
def ref(p):return dict(path=p.relative_to(H).as_posix(),sha256=sha(p))
def put(p,v):
 p.parent.mkdir(parents=True,exist_ok=True);assert not p.exists();p.write_text(json.dumps(v,indent=2)+'\n')
summary=read(P/'PRIVATE-THREE-JOB-PORTABLE-NAMESPACE-PREPARED-PENDING-REVIEWS.json');reproductions=read(P/'ACTUAL-PORTABLE-THREE-RECIPES-NINE-PNGS-BYTE-EQUAL-REPRODUCTION.json')
first=H/'jobs'/summary['jobs'][0]['job_id'];L=first/'lineage/late9-shared-actual-Source-primary';repro=L/'reproducer'
target='tools/late9_source_components/terrain_component_cleanup.py';tools=[dict(path=target,sha256=sha(repro/'terrain_component_cleanup.py')),dict(path='tools/hd_terrain_cleanup.py',sha256=sha(R/'tools/hd_terrain_cleanup.py'))]
put(P/'PRIVATE-EXACT-PUBLIC-TOOL-TEST-PROMOTION-PROPOSAL-NOT-APPLIED.json',dict(status='PRIVATE_PROPOSAL_ONLY_NO_PUBLIC_WRITES',helper_source=ref(repro/'terrain_component_cleanup.py'),helper_target=target,tools=tools,tests=[dict(source=ref(p),target='tools/late9_source_components/'+p.name)for p in sorted((L/'code-proposal').glob('test_*.py'))],actual_different_CODE72_report='.reference/hd-late9-different-CODE-review-20261019-v1/PASS-LATE9-DIFFERENT-CODE72-INPUTS-AND-EXPLICIT-SOURCE-FIDELITY-METHOD.json',actual_recipe_only_successor_CODE_input_report=ref(L/'different-recipe-CODE-input-verbatim.json'),additional_tests_or_cleanup_QA=0))
parents=[]
for g in ['coast4','ground4','ramp105f3']:
 inputname={'coast4':'new-coast4-master.png','ground4':'new-ground4-master.png','ramp105f3':'new-ramp105f3-master.png'}[g]
 parents.append(dict(raw_png=ref(repro/'inputs'/inputname),imagegen_receipt=ref(L/'generation'/g/'ACTUAL-BUILTIN-PRIMITIVE-RECEIPT.json'),prompt=ref(L/'generation'/g/'prompt.txt')))
for job,z in zip(summary['jobs'],reproductions['executions']):
 J=H/'jobs'/job['job_id'];group=z['group'];candidate=read(J/'candidate.json');rows=proposal_frames(candidate);actual=Path(z['actual_receipt_path']);assert sha(actual)==z['actual_receipt_sha256'];receipt=read(actual);recipe=repro/f'{group}-EXECUTABLE-PORTABLE-RECIPE.json';assert receipt['recipe_sha256']==sha(recipe)
 assert receipt['implementation']['sha256']==tools[0]['sha256']and receipt['executed_dependency']['sha256']==tools[1]['sha256']
 archived=L/'measurement'/group/'actual-relocated-byte-reproduction-receipt-verbatim.json';os.link(actual,archived)
 execution=dict(status='success',method=receipt['method'],recipe_sha256=sha(recipe),tool_sha256=tools[0]['sha256'],source_sha256={aid:f['source_sha256']for aid,f in rows.items()},parent_raw_sha256=sorted(p['raw_png']['sha256']for p in parents),output_sha256=z['selected_byte_equal_pngs'])
 normal=J/'actual-portable-execution-normalized.json';put(normal,dict(execution=execution,literal_actual_execution_receipt=ref(archived),literal_actual_recipe_input_path=receipt['recipe_input']['path'],scope='Exact field projection from actual one-shot relocated recipe execution; selected9 output bytes matched actual G2-reviewed PNGs. No fabricated or relabeled historical execution.'))
 outputs={f['file']:sha(H/f['file'])for f in rows.values()};lineage=J/'artwork-derivation.json';put(lineage,dict(format_version=1,kind='deterministic_cleanup',method=receipt['method'],parents=parents,tools=tools,recipe=ref(recipe),execution_receipt=ref(normal),sources=execution['source_sha256'],outputs=outputs,Source_fidelity_limits='Exact SourceNx geometry/color base with genuine bounded fineRGB bands; Original-owned functional/ordinarygreen detail cells do not receive generatedHD credit. Raw coarse layouts not used as whole-tile geometry.'))
 candidate['artwork_derivation']=ref(lineage);(J/'candidate.json').write_text(json.dumps(candidate,indent=2)+'\n');qa=read(J/'runtime-qa.json');qa['candidate_sha256']=sha(J/'candidate.json');qa['frame_bindings_sha256']=binding_digest(proposal_frames(candidate));(J/'runtime-qa.json').write_text(json.dumps(qa,indent=2)+'\n')
 put(J/'provenance.json',dict(format_version=1,job_id=job['job_id'],status='PRIVATE_QUALIFIED_INTRINSIC_PENDING_CONTEXT_ROOT_AND_PUBLIC_TOOLS',artist='/root/remaining_catalog',genuine_builtin_parents=parents,artwork_derivation=ref(lineage),raw_masters_untouched=True,logical_geometry_and_palette_original=True,generated_fine_material_only=True,Original_retained_detail_cells={aid:f.get('original_detail_cells',[])for aid,f in rows.items()},Original_retained_HD_credit=0,actual_G2_libraries_Source18_and_native_bodies_unchanged=True,actual_authored_successor_trials=1,actual_relocated_byte_reproduction_validation_runs=1,additional_G2_from_namespace_or_recipe_replay=0,Root_art_admission_not_claimed=True))
put(P/'PRIVATE-PORTABLE-DERIVATION-REPLAY-NORMALIZATION-CLOSED-PENDING-CONTEXT-ROOT.json',dict(status='PRIVATE_THREE_PORTABLE_JOBS_NINE_BYTE_EQUAL_OUTPUTS_DERIVATION_READY_PENDING_PUBLIC_TOOL_PROMOTION',jobs=[dict(job_id=j['job_id'],candidate=ref(H/'jobs'/j['job_id']/'candidate.json'),QA=ref(H/'jobs'/j['job_id']/'runtime-qa.json'),derivation=ref(H/'jobs'/j['job_id']/'artwork-derivation.json'))for j in summary['jobs']],new_generation_cleanup_QA_World_calls=0,public_tools_not_applied=True,Root_review_pending=True))
print('Three portable derivations bind actual relocated recipe execution; new art/QA calls0.')
