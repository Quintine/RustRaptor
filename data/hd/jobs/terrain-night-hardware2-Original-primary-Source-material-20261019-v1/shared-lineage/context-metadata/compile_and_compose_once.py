from pathlib import Path
import subprocess,json,hashlib,shutil,time,os,resource
R=Path('/home/quintine/Projects/RaptorReplica/RustRaptor');P=Path(__file__).resolve().parent;src=P/'compose_night5_SourceG2_H5654.rs';binary=P/'compose-night5-currentG2';recipe=P/'SEALED-NIGHT5-GENUINE10-CURRENTG2-H5654-RECIPE.json';out=P/'actual-once-night5-genuine10-G2-H5654';FLOOR=1800000000
assert shutil.disk_usage(P).free>FLOOR+65000000
prior=json.loads((R/'.reference/hd-newTerrain5-SourceG2-H5596-genuine-seven-context-author-20261019-v1/ACTUAL-ONE-PRIVATE-CURRENT-G2-COMPILE-TERMINAL.json').read_text());argv=prior['argv'].copy();old=argv.index('-O')+1;argv[old]=str(src);argv[-1]=str(binary)
def pin(p):
 p=Path(p);s=p.stat();return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),size=s.st_size,mtime_ns=s.st_mtime_ns,mode=s.st_mode)
def save(n,v):
 p=P/n
 with p.open('x')as f:json.dump(v,f,indent=2);f.write('\n')
 return pin(p)
lib=Path(next(a.split('=',1)[1]for a in argv if a.startswith('raptor_replica=')));assert pin(lib)['sha256']=='5b6bbd03874da298dae953dc1c0f472d24f27031df4f46616368faefb0801676'
save('ACTUAL-ONE-ADAPTER-COMPILE-AND-ONE-CONSTRUCTOR-CLAIM.json',dict(Root_GO=True,source=pin(src),recipe=pin(recipe),actual_G2_library=pin(lib),compile_argv=argv,constructor_argv=[str(binary),str(recipe),str(out)],no_World_QA_enginebuild_image_cleanup_canonical=True,floor_bytes=FLOOR))
def bounds():resource.setrlimit(resource.RLIMIT_AS,(2500000000,2500000000))
for name,args in [('ADAPTER-COMPILE',argv),('GENUINE10-CONSTRUCTOR',[str(binary),str(recipe),str(out)])]:
 assert shutil.disk_usage(P).free>FLOOR+35000000
 save('ACTUAL-'+name+'-STARTED.json',dict(argv=args,start_unix=time.time()))
 stdout=P/('ACTUAL-'+name+'.stdout');stderr=P/('ACTUAL-'+name+'.stderr');start=time.monotonic()
 with stdout.open('xb')as fo,stderr.open('xb')as fe:
  env=os.environ.copy();env['LD_LIBRARY_PATH']='/home/quintine/.local/lib'+(':'+env['LD_LIBRARY_PATH']if env.get('LD_LIBRARY_PATH')else'');run=subprocess.run(args,cwd=R,stdout=fo,stderr=fe,env=env,preexec_fn=bounds,timeout=120)
 result=save('ACTUAL-'+name+'-TERMINAL.json',dict(argv=args,exit_code=run.returncode,elapsed_seconds=time.monotonic()-start,stdout=pin(stdout),stderr=pin(stderr),free_bytes=shutil.disk_usage(P).free))
 print(json.dumps(result),flush=True)
 if run.returncode:print(stderr.read_text()[-5000:],flush=True);raise SystemExit(run.returncode)
assert shutil.disk_usage(P).free>FLOOR
print(json.dumps(dict(status='ACTUAL_ONE_COMPILE_ONE_CONSTRUCTOR_COMPLETED',output=str(out),free=shutil.disk_usage(P).free)))
