from pathlib import Path
import json,hashlib,subprocess,time,os,shutil
O=Path(__file__).resolve().parent;R=O.parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def js(p):return json.loads(Path(p).read_text())
def save(n,d):p=O/n;assert not p.exists();p.write_text(json.dumps(d,indent=2)+'\n')
def usage():return sum(p.stat().st_size for p in O.rglob('*')if p.is_file()and'immutable-H5647-data'not in p.parts)
def budget():assert shutil.disk_usage(O).free>=1_800_000_000;assert usage()<220_000_000
assert not any(O.glob('ACTUAL-*-STARTED.json'));budget();c=js(O/'FROZEN-H5647-REAL-CHANGED-ENDPOINT3-CONTRACT.json');guards=js(O/'BEFORE-H5647-CHANGED-ENDPOINT-GUARDS.json');ignored={str(R/'data/hd/hd.json'),str(R/'data/hd/provenance.json')}
for p in guards:
 if p['path']not in ignored:assert sha(p['path'])==p['sha256']
epoch=c['epoch'];src=O/'compose_affected_endpoint3.rs';binary=O/'compose-shoreline4-changed-endpoint3-currentG2';comp=['/usr/bin/rustc','--edition=2024','-O',str(src),'--extern','raptor_replica='+epoch['library']['path'],'--extern','serde_json='+epoch['serde_json']['path'],'--extern','flate2='+str(R/'target/desktop-runtime/release/deps/libflate2-808a135ff259ee28.rlib'),'-L','dependency='+epoch['dependency_dir'],'-L','native=/home/quintine/.local/lib','-o',str(binary)];run=[str(binary),str(O/'FROZEN-H5647-REAL-CHANGED-ENDPOINT3-CONTRACT.json'),c['output_root']];env=dict(os.environ,LD_LIBRARY_PATH=str(R/'lib')+':/home/quintine/.local/lib',RUST_BACKTRACE='0');save('ACTUAL-COMPILE-AND-COMPOSITION-ARGS.json',dict(compile_argv=comp,composition_argv=run,source_sha256=sha(src),contract_sha256=sha(O/'FROZEN-H5647-REAL-CHANGED-ENDPOINT3-CONTRACT.json'),Root_authority=c['Root_authority']));failure=None
try:
 for name,argv in [('ACTUAL-ONE-ADAPTER-COMPILE',comp),('ACTUAL-ONE-FINITE-COMPOSITION',run)]:
  budget();save(name+'-STARTED.json',dict(argv=argv,status='ACTUAL_STARTED',ns=time.time_ns()));start=time.time();rc=None
  with(O/(name+'.stdout')).open('xb')as out,(O/(name+'.stderr')).open('xb')as err:
   proc=subprocess.Popen(argv,cwd=R,env=env,stdout=out,stderr=err)
   while proc.poll()is None:
    time.sleep(.3)
    try:budget()
    except BaseException:proc.terminate();proc.wait();raise
   rc=proc.returncode
  save(name+'-TERMINAL.json',dict(status='ACTUAL_EXIT0'if rc==0 else'ACTUAL_FAILED',exit_code=rc,elapsed_seconds=time.time()-start,stdout_sha256=sha(O/(name+'.stdout')),stderr_sha256=sha(O/(name+'.stderr')),free_bytes=shutil.disk_usage(O).free));assert rc==0,(name,rc,(O/(name+'.stderr')).read_text()[-4000:])
except BaseException as e:
 failure=repr(e);save('PRESERVED-ACTUAL-FAILURE-NO-AUTOMATIC-RETRY.json',dict(error=failure,free_bytes=shutil.disk_usage(O).free));raise
finally:
 changed=[p for p in guards if p['path']not in ignored and sha(p['path'])!=p['sha256']];identity=js(c['baseline']['all_raw_identities']['path']);bad=[]
 for n,d in identity['raws'].items():
  s=Path(d['snapshot']).stat()
  if(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns)!=(d['dev'],d['inode'],d['bytes'],d['mtime_ns']):bad.append(n)
 save('IMMEDIATE-CLOSING-GUARDS-NO-PENDING-EXECUTION.json',dict(status='EXACT_INPUTS'if not changed and not bad else'INPUT_CHANGED',changed=changed,raw_identity_mismatches=bad,all_full_header_raw_path_identities_checked=len(identity['raws']),actual_failure=failure,no_pending_owned_execution=True,World=0,new_intrinsic_QA=0,canonical_changes=0,owned_logical_bytes_excluding_baseline_hardlinks=usage()));assert not changed and not bad
print(json.dumps(dict(status='ACTUAL_COMPILE1_COMPOSITION1_SUCCESS',free_bytes=shutil.disk_usage(O).free,owned_bytes=usage())))
