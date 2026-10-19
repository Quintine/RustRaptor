from pathlib import Path
import json,hashlib,subprocess,os,time,shutil,ast
O=Path(__file__).resolve().parent;R=O.parent.parent;guards={}
def pin(p):
 p=Path(p).absolute();s=p.stat();return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),size=s.st_size,mtime_ns=s.st_mtime_ns,mode=s.st_mode)
def read(p):return json.loads(Path(p).read_text())
def add(p,expected=None):
 q=pin(p)
 if expected:assert q['sha256']==expected
 guards[q['path']]=q;return q
def save(n,v):
 p=O/n;assert not p.exists();p.write_text(json.dumps(v,indent=2)+'\n');return pin(p)
def usage():return sum(p.stat().st_size for p in O.rglob('*')if p.is_file()and 'immutable-H5613-data'not in p.parts)
def budget():assert usage()<120000000;assert shutil.disk_usage(O).free>=2_200_000_000
assert not any(O.glob('ACTUAL-*-STARTED.json'));budget()
cp=add(O/'FROZEN-GRATING2-G2-H5613-GENUINE14-SOURCE-CONTRACT.json');c=read(cp['path'])
for q in read(O/'BEFORE-BOUNDED-SOURCE-NATIVE-BANK-EPOCH-GUARDS.json'):
 # Canonical headers may legitimately advance after an immutable snapshot; only that historical SHA fact is claimed.
 if q['path']in [str(R/'data/hd/hd.json'),str(R/'data/hd/provenance.json')]:continue
 assert pin(q['path'])==q;guards[q['path']]=q
for q in [c['baseline']['HD'],c['baseline']['provenance']]:add(q['path'],q['sha256'])
epoch=c['epoch'];flat=add(R/'target/desktop-runtime/release/deps/libflate2-808a135ff259ee28.rlib');source=add(O/'compose_Grating2_genuine14_SourceG2_H5613.rs');add(Path(__file__))
go=save('ROOT-DIRECT-GRATING2-H5613-GO-RECORD.json',dict(Root_GO=True,authority=c['Root_authority'],scope=c['scope'],baseline=c['baseline']['HD'],scope_no_old_context_carry=True))
inp=dict(status=c['status'],Root_GO=True,Root_authorized_selected_assets=c['selected'],Root_actual_H5613_GO=go,source_contract=cp,baseline_pack_root=c['baseline']['packroot'],baseline_hd=c['baseline']['HD'],baseline_provenance=c['baseline']['provenance'],baseline_hardlink_identity=c['baseline']['hardlink_identity'],actual_baseline_frame_count=5613,baseline_finite_native=c['baseline']['finite_bindings'],actual_library=epoch['library'],serde=epoch['serde_json'],SourceG2_epoch=epoch['receipt'],actual_selected_plain_index_banks=[dict(asset=q['asset'],actual_bank=q['actual_plain_bank'],actual_QA=q['actual_QA'],measured_scope=q['measured_scope'])for q in c['own_routes']],original_data_root=str(R/'data'),own_pack_root=c['own_pack_root'],actual_output_root=str(O/'actual-context14'),resource_cap_bytes=120000000,free_floor_bytes=2_200_000_000)
ip=save('ROOT-GO-ACTUAL-G2-H5613-GRATING2-INPUT.json',inp);add(ip['path']);compileargv=['/usr/bin/rustc','--edition=2024','-O',source['path'],'--extern','raptor_replica='+epoch['library']['path'],'--extern','serde_json='+epoch['serde_json']['path'],'--extern','flate2='+flat['path'],'-L','dependency='+epoch['dependency_dir'],'-L','native=/home/quintine/.local/lib','-o',str(O/'compose-grating2-genuine14-actual-SourceG2')];argv=[str(O/'compose-grating2-genuine14-actual-SourceG2'),str(R/'data'),c['baseline']['packroot'],c['own_pack_root'],ip['path'],inp['actual_output_root']];env=dict(os.environ,LD_LIBRARY_PATH=str(R/'lib')+':/home/quintine/.local/lib',RUST_BACKTRACE='0')
save('ACTUAL-ONE-COMPILE-ONE-CONSTRUCTOR-ARGV.json',dict(compile_argv=compileargv,constructor_argv=argv,source=source,contract=cp));save('BEFORE-ACTUAL-COMPILE-CONSTRUCTOR-EXACT-INPUT-GUARDS.json',list(guards.values()));failure=None
try:
 for name,args in [('ACTUAL-ONE-COMPILE',compileargv),('ACTUAL-ONE-CONSTRUCTOR',argv)]:
  budget();save(name+'-STARTED.json',dict(argv=args,started_ns=time.time_ns(),status='ACTUAL_STARTED_ONCE'));rc=None
  try:
   with(O/(name+'.stdout')).open('xb')as out,(O/(name+'.stderr')).open('xb')as err:
    proc=subprocess.Popen(args,stdout=out,stderr=err,cwd=R,env=env)
    while proc.poll()is None:
     time.sleep(.5)
     try:budget()
     except BaseException:proc.terminate();proc.wait();raise
    rc=proc.returncode
  finally:save(name+'-TERMINAL.json',dict(exit_code=rc,status='ACTUAL_EXIT0'if rc==0 else'ACTUAL_FAILED',terminal_ns=time.time_ns(),stdout=pin(O/(name+'.stdout')),stderr=pin(O/(name+'.stderr')),owned_bytes=usage(),free_bytes=shutil.disk_usage(O).free))
  assert rc==0,(name,rc,(O/(name+'.stderr')).read_text()[-3500:])
except BaseException as e:failure=repr(e);save('PRESERVED-ACTUAL-FAILURE-NO-AUTOMATIC-RETRY.json',dict(error=failure,owned_bytes=usage(),free_bytes=shutil.disk_usage(O).free))
finally:
 mm=[dict(expected=q,actual=pin(q['path']))for q in guards.values()if pin(q['path'])!=q];same=[]
 identities=read(c['baseline']['hardlink_identity']['path'])
 for q in identities['raws'].values():
  st=Path(q['snapshot']).stat();assert(st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns)==(q['dev'],q['inode'],q['size'],q['mtime_ns']);same.append(q['snapshot'])
 save('IMMEDIATE-EXACT-CLOSING-GUARDS-AND-BOUNDARY-RELEASED.json',dict(status='EXACT_INPUTS_BOUNDARY_RELEASED'if not mm else'INPUT_CHANGED',mismatches=mm,checked_inputs=len(guards),all_raw_dependency_identities_exact=len(same),actual_failure=failure,no_pending_owned_writer_call_lease=True,World=0,QA=0,image=0));assert not mm
print(json.dumps(dict(actual_failure=failure,owned_bytes=usage(),free_bytes=shutil.disk_usage(O).free)))
