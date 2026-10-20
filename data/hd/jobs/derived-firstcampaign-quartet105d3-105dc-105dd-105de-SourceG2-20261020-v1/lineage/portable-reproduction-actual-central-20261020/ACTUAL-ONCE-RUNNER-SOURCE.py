from pathlib import Path
import subprocess,json,hashlib,sys,time,shutil,os
R=Path('/home/quintine/Projects/RaptorReplica/RustRaptor');C=R/'.reference/hd-final50-private-normalized-append-after5693-SourceG2-20261020-v1/project';F=R/'.reference/hd-stag-firstcampaign5-two-portable-jobs-SourceG2-H5654-20261020-v1/project';O=R/'.reference/hd-stag-firstcampaign5-actual-central-portability3replays-20261020-v2';assert not O.exists();assert shutil.disk_usage(R).free>1_800_000_000;O.mkdir();python=Path('/home/quintine/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3');shutil.copyfile(__file__,O/'ACTUAL-ONCE-RUNNER-SOURCE.py')
def pin(p):p=Path(p);return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),size=p.stat().st_size)
def save(n,v):p=O/n;assert not p.exists();p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2)+'\n');return pin(p)
fm=json.loads((F.parent/'FINAL-PRIVATE-PAYLOAD-ONLY-FILEMAP.json').read_text());props=[x for x in fm['entries']if x['path'].startswith('tools/firstcampaign5_')];assert len(props)==53
for x in props:assert pin(C/x['path'])['sha256']==x['sha256']
deps=[]
for n in ['hd_terrain_cleanup.py','hd_frame_policy.py']:
 p=C/'tools'/n;assert pin(p)['sha256']==pin(F/'tools'/n)['sha256'];deps.append(pin(p))
JQ=Path('data/hd/jobs/derived-firstcampaign-quartet105d3-105dc-105dd-105de-SourceG2-20261020-v1');JG=Path('data/hd/jobs/derived-firstcampaign105a4-complete-green-SourceG2-20261020-v1');jobs=[('quartet','firstcampaign5_quartet',JQ/'reproducer/recipe.json'),('green-parent','firstcampaign5_green_parent',JG/'reproducer/parent-reproducer/recipe.json'),('green-final','firstcampaign5_green',JG/'reproducer/recipe.json')]
for _,_,rel in jobs:assert pin(C/rel)['sha256']==pin(F/rel)['sha256']
save('PREFLIGHT-53-PROPOSED-FILES-EXACT-AND-THREE-RECIPES.json',dict(status='PASS',central_project=str(C),frozen_project=str(F),proposal_files=props,dependencies=deps,recipes=[pin(C/r)for _,_,r in jobs],runner=pin(O/'ACTUAL-ONCE-RUNNER-SOURCE.py'),new_engine_or_art_calls=0))
records=[]
def execute(name,argv,cwd):
 folder=O/name;assert not folder.exists();folder.mkdir();record=dict(name=name,argv=[str(x)for x in argv],cwd=str(cwd),start_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()))
 (folder/'ACTUAL-ARGV.json').write_text(json.dumps(record,indent=2)+'\n')
 with(folder/'stdout.txt').open('wb')as out,(folder/'stderr.txt').open('wb')as err:
  p=subprocess.run(record['argv'],cwd=cwd,stdout=out,stderr=err,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),timeout=180)
 record.update(exit_code=p.returncode,end_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),stdout=pin(folder/'stdout.txt'),stderr=pin(folder/'stderr.txt'))
 (folder/'ACTUAL-EXIT.json').write_text(json.dumps(record,indent=2)+'\n');records.append(record)
 assert p.returncode==0,(name,p.returncode)
 return folder
for name in ['firstcampaign5_quartet','firstcampaign5_green']:
 folder=execute('tests-'+name,[python,'-B','-m','unittest','discover','-s',C/'tools'/name,'-p','test_*.py'],C)
 logs=(folder/'stdout.txt').read_text()+(folder/'stderr.txt').read_text();assert 'Ran 64 tests' in logs and '\nOK' in logs
outputs={}
for name,tool,rel in jobs:
 output=O/('output-'+name);assert not output.exists()
 folder=execute('replay-'+name,[python,'-B',C/'tools'/tool/'terrain_component_cleanup.py','--recipe',C/rel,'--output',output],C)
 receipt=output/'ACTUAL-DERIVATION-RECEIPT.json';assert receipt.is_file();outputs[name]=dict(output=str(output),actual_receipt=pin(receipt),tool=pin(C/'tools'/tool/'terrain_component_cleanup.py'),recipe=pin(C/rel))
compare=[]
for aid in ['105d3','105dc','105dd','105de']:
 actual=O/'output-quartet'/f'{aid}-derived.png';frozen=F/JQ/'derived'/actual.name;assert pin(actual)['sha256']==pin(frozen)['sha256'];compare.append(dict(asset=aid,actual=pin(actual),approved=pin(frozen),byte_exact=True))
actual=O/'output-green-parent/105a4-derived.png';frozen=C/JG/'reproducer/inputs/held-parent105a4-derived.png';assert pin(actual)['sha256']==pin(frozen)['sha256']=='0a5b170f1453238ac34861c92da6bcbd0018eba6903cd6ac4a2f60fdea6cc003';parent=dict(actual=pin(actual),frozen_parent=pin(frozen),byte_exact=True,stage='Actual parent replay uses full contained 105a4/105a7recipe. Final unchanged successor recipe reads its frozen held-parent copy with this identical sha; no recipe/path rewrite or extra replay.')
actual=O/'output-green-final/105a4-derived.png';frozen=F/JG/'derived/105a4-derived.png';assert pin(actual)['sha256']==pin(frozen)['sha256'];compare.append(dict(asset='105a4',actual=pin(actual),approved=pin(frozen),byte_exact=True))
for x in props:assert pin(C/x['path'])['sha256']==x['sha256']
summary=dict(status='PASS_ACTUAL_TWO64_SYNTHETIC_SUITES_AND_EXACT3_RELOCATED_REPRODUCTIONS',tests=128,actual_recipe_replay_calls=3,records=records,reproductions=outputs,approved_final_pngs_byteexact=compare,actual_parent105a4_byteexact=parent,scope='Portability reproduction only: approved artwork/candidate/QA/lineage bytes unchanged. Exactlyone call per3recipe. Real absoluteargv/tools/recipes/inputpins and receipts preserved; historical SourceG2 runtime candidate_at_start/epoch not rewritten.',frozen975_map=pin(F.parent/'FINAL-PRIVATE-PAYLOAD-ONLY-FILEMAP.json'),source_53_unchanged=True,engine_compile_context_World_runtimeQA_imagegen_calls=0,canonical_Git_writes=0)
proof=save('PASS-ACTUAL-3-RELOCATED-REPRODUCTIONS-AND128-ISOLATED-SYNTHETICS.json',summary)
# Copy only proof files into the already-admitted quartet namespace, as an additive map; no writes to either project.
destbase=JQ/'lineage/portable-reproduction-actual-central-20261020';maps=[]
for p in sorted(O.rglob('*')):
 if p.is_file() and not p.name.endswith('.png'):
  maps.append(dict(source=pin(p),destination=(destbase/p.relative_to(O)).as_posix()))
copy=save('ADDITIVE-REPRODUCTION-PROOF-COPY-MAP-NO-PROJECT-WRITES.json',dict(status='ADDITIVE_MAP_ONLY',entries=maps,files=len(maps),bytes=sum(x['source']['size']for x in maps),proof=proof,exclude='Duplicate reproducedPNGfiles are not releasepayload; exact hashes prove unchanged approvedimages. Frozen975map/tree and centralproject preserved.'))
print(json.dumps(dict(proof=proof,copy_map=copy,free_bytes=shutil.disk_usage(R).free),indent=2))
