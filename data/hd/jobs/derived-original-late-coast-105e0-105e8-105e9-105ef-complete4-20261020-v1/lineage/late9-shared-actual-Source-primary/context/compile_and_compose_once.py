from pathlib import Path
import json,hashlib,subprocess,os,shutil,time
O=Path(__file__).resolve().parent;R=O.parent.parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def pin(p):
 p=Path(p);s=p.stat();return dict(path=str(p.absolute()),sha256=sha(p),size=s.st_size,mtime_ns=s.st_mtime_ns)
def save(n,v):
 p=O/n;assert not p.exists();p.write_text(json.dumps(v,indent=2)+'\n')
def check():
 assert shutil.disk_usage(O).free>1_800_000_000
 for q in guards:assert pin(q['path'])==q,q['path']
 for q in identities['raws'].values():
  st=Path(q['snapshot']).stat();assert(st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns)==(q['dev'],q['inode'],q['size'],q['mtime_ns'])
c=json.loads((O/'FROZEN-LATE9-GENUINE-FINITE-SOURCE-H5654-CONTRACT.json').read_text());ep=c['epoch'];guards=json.loads((O/'BEFORE-CONTEXT-EXACT-INPUT-GUARDS.json').read_text());identities=json.loads(Path(c['baseline']['hardlink_identity']['path']).read_text())
# Root standing actual operation is conditional on a saved different intrinsic ART QUAL9.
peer=json.loads((O/'ACTUAL-RECEIVED-DIFFERENT-ART-QUAL9-COLLABORATION-DECISION.json').read_text());assert peer['decision']=='QUAL9'and peer['reviewer']=='/root/mission_preview_design'and peer['origin']=='trusted_collaboration_message_recorded_by_author'
source=O/'compose_late9_genuine13_SourceG2_H5654.rs';assert sha(source)=='8af3749168abc465fb1ecc24c66688433c6e714696567b818edc3f61cd2c6b2e'
flat=R/'target/desktop-runtime/release/deps/libflate2-808a135ff259ee28.rlib';guards.extend([pin(source),pin(flat),pin(Path(__file__)),pin(O/'FROZEN-LATE9-GENUINE-FINITE-SOURCE-H5654-CONTRACT.json'),pin(O/'ACTUAL-RECEIVED-DIFFERENT-ART-QUAL9-COLLABORATION-DECISION.json')]);save('EXACT-PRECOMPILE-COMPOSE-INPUT-GUARDS.json',guards)
binary=O/'compose-late9-genuine13-actual-SourceG2';out=O/'actual-once-SourceG2-H5654-genuine13-allnative';assert not binary.exists()and not out.exists()
compileargv=['/usr/bin/rustc','--edition=2024','-O',str(source),'--extern','raptor_replica='+ep['library']['path'],'--extern','serde_json='+ep['serde_json']['path'],'--extern','flate2='+str(flat),'-L','dependency='+str(R/'target/desktop-runtime/release/deps'),'-L','native=/home/quintine/.local/lib','-o',str(binary)]
argv=[str(binary),str(R/'data'),c['baseline']['packroot'],c['own_pack'],c['merged_actual_bank']['path'],str(O/'FROZEN-LATE9-GENUINE-FINITE-SOURCE-H5654-CONTRACT.json'),str(out)]
env=dict(os.environ,LD_LIBRARY_PATH=str(R/'lib')+':/home/quintine/.local/lib',RUST_BACKTRACE='0')
save('ACTUAL-ONE-COMPILE-ONE-STATIC-CONSTRUCTOR-ARGV.json',dict(compile=compileargv,constructor=argv,World=0,intrinsic_QA=0,art_cleanup=0))
for name,args in [('ACTUAL-ONE-COMPILE',compileargv),('ACTUAL-ONE-STATIC-CONSTRUCTOR',argv)]:
 check();save(name+'-STARTED.json',dict(argv=args,started_ns=time.time_ns()));z=subprocess.run(args,cwd=R,env=env,capture_output=True,timeout=60);(O/(name+'.stdout')).write_bytes(z.stdout);(O/(name+'.stderr')).write_bytes(z.stderr);save(name+'-TERMINAL.json',dict(exit_code=z.returncode,stdout=pin(O/(name+'.stdout')),stderr=pin(O/(name+'.stderr')),terminal_ns=time.time_ns()));assert z.returncode==0,z.stderr.decode()[-3000:]
check();save('IMMEDIATE-CLOSING-ALL-INPUTS-AND-3088-IDENTITIES-EXACT.json',dict(guard_count=len(guards),raw_identities=3088,mismatches=[],compile_calls=1,static_constructor_calls=1,World=0,new_QA=0,new_cleanup=0,no_pending_process=True));print('One compile / one static constructor EXIT0; exact closing guards; no pending process.')
