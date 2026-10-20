"""One already-built, Root-authorized fixed context adapter invocation; no compile."""
from pathlib import Path
import hashlib,json,os,resource,shutil,subprocess,time
P=Path(__file__).resolve().parent;R=P.parents[1]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
source=P/'compose_windows6_SourceG2_H5654.rs';binary=P/'compose-windows6-currentG2';recipe=P/'SEALED-WINDOWS6-GENUINE10-CURRENTG2-H5654-RECIPE.json';output=P/'actual-once-windows6-genuine10-G2-H5654'
assert sha(source)=='e76f7f7b1d477567cecfbef6189b7d44d87a0fa91487619fd449263a004c866b'
assert sha(binary)=='957b45f9f123eb68ecf84beeeffbf11822c29a47b2e0a39b1b1d608b12831d90'
assert sha(recipe)=='64dfd9539b7693159e913f924a2b427a23b85cd78c649da4e5eeaa825574f536'
compile_receipt=json.loads((P/'ACTUAL-ADAPTER-COMPILE-TERMINAL.json').read_text());assert compile_receipt['exit_code']==0 and compile_receipt['actual_compile_processes']==1
assert not output.exists()and not(P/'ACTUAL-GENUINE10-CONSTRUCTOR-STARTED.json').exists()
assert shutil.disk_usage(P).free>1800000000+100000000
argv=[str(binary),str(recipe),str(output)]
(P/'ACTUAL-GENUINE10-CONSTRUCTOR-STARTED.json').open('x').write(json.dumps(dict(argv=argv,source_sha256=sha(source),recipe_sha256=sha(recipe),binary_sha256=sha(binary),Root_authority='Standing one adapter process after different intrinsic QUAL40055113 and different source/input PASSd77a8fe5; no new build, World, QA or art.',bounded_address_space_bytes=2500000000),indent=2)+'\n')
def bounds():resource.setrlimit(resource.RLIMIT_AS,(2500000000,2500000000))
start=time.monotonic();stdout=P/'ACTUAL-GENUINE10-CONSTRUCTOR.stdout';stderr=P/'ACTUAL-GENUINE10-CONSTRUCTOR.stderr';env=os.environ.copy();env['LD_LIBRARY_PATH']='/home/quintine/.local/lib'+(':'+env['LD_LIBRARY_PATH']if env.get('LD_LIBRARY_PATH')else'')
with stdout.open('xb')as fo,stderr.open('xb')as fe:run=subprocess.run(argv,cwd=R,stdout=fo,stderr=fe,env=env,preexec_fn=bounds,timeout=120)
terminal=dict(argv=argv,exit_code=run.returncode,elapsed_seconds=time.monotonic()-start,stdout_sha256=sha(stdout),stderr_sha256=sha(stderr),source_sha256=sha(source),recipe_sha256=sha(recipe),binary_sha256=sha(binary),actual_adapter_processes=1,actual_extra_compiles=0,World_calls=0,free_bytes=shutil.disk_usage(P).free)
(P/'ACTUAL-GENUINE10-CONSTRUCTOR-TERMINAL.json').open('x').write(json.dumps(terminal,indent=2)+'\n');print(json.dumps(terminal));raise SystemExit(run.returncode)
