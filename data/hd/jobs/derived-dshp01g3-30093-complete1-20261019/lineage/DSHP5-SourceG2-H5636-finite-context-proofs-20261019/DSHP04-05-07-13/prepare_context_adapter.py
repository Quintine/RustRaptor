from pathlib import Path
import json,hashlib,shutil
R=Path(__file__).resolve().parents[2]
O=Path(__file__).resolve().parent
T=R/'.reference/hd-DSHP01G3-30093-currentG2-genuine-S3W3-H5636-context-20261019-v1'
trace=json.loads((O/'AUTHENTIC-ALL4-SPRITE-ALL27MAP-DSHP04-05-07-13-CALLER-TRACE.json').read_text())
chosen={}
for asset,target in trace['targets'].items():
 c=next(x for x in target['callers'] if x['legal_normal_pilot2_enabled'])
 d=next(x for x in target['definitions'] if x['definition']==c['definition'])
 cfg={'asset':asset,'definition':d['definition'],'mission':c['mission'],'frame_count':d['frames'],'width':32 if asset=='30096' else 40,'height':32,'health':d['health'],'ground':d['ground'],'shadow':d['Source_shadow'],'original_name':d['name'],'pilot_difficulty':2,'starting_seed':2048,'Source_caller':c,'chosen_spawn':{'tick':c['tick'],'enemy':d['definition'],'x':c['spawn_x'],'y':c['spawn_y'],'difficulty':c['difficulty_code']}}
 (O/f'SOURCE-CONFIG-{asset}.json').write_text(json.dumps(cfg,indent=2)+'\n')
 chosen[asset]=cfg
s=(T/'dshp01_capture_and_composition.rs').read_text()
start=s.index(' let(target,def,mission_name,frame_count,width,height,health,original_name)=')
end=s.index('\n let cat=',start)
s=s[:start]+''' let cfg=read(Path::new(&a[4]));let target=id(&cfg["asset"]);let def=cfg["definition"].as_str().unwrap();let mission_name=cfg["mission"].as_str().unwrap();let frame_count=cfg["frame_count"].as_u64().unwrap()as usize;let width=cfg["width"].as_i64().unwrap()as i32;let height=cfg["height"].as_i64().unwrap()as i32;let health=cfg["health"].as_i64().unwrap()as i32;let original_name=cfg["original_name"].as_str().unwrap();let ground=cfg["ground"].as_bool().unwrap();let shadow=cfg["shadow"].as_bool().unwrap();assert_eq!(frame_count,1);
'''+s[end:]
s=s.replace('assert!(d.ground);','assert_eq!(d.ground,ground);').replace('assert_eq!(d.legacy.as_ref().unwrap().fields[11],1);','assert_eq!(d.legacy.as_ref().unwrap().fields[11]!=0,shadow);')
s=s.replace('let chosen=original.spawns.iter().find(|sp|sp.enemy.0==def && sp.difficulty==4).unwrap().clone();','let chosen=original.spawns.iter().find(|sp|serde_json::to_value(sp).unwrap()==cfg["chosen_spawn"]).expect("literal authentic Source declaration absent").clone();')
s=s.replace('pilot.difficulty=2;','pilot.difficulty=u32::try_from(cfg["pilot_difficulty"].as_u64().unwrap()).unwrap();').replace('let expected_seed=2048;','let expected_seed=i32::try_from(cfg["starting_seed"].as_i64().unwrap()).unwrap();')
s=s.replace('ACTUAL_CONTROLLED_ORIGINAL_DSHP01_COMPLETE1_CAPTURED','ACTUAL_CONTROLLED_ORIGINAL_DISTINCT_DSHP_COMPLETE1_CAPTURED').replace('"family":a[4],','"family":cfg["asset"],"source_config":cfg,')
s=s.replace('let cat=Catalog::open(&a[2]).unwrap();let pal=cat.palette().unwrap();','let base=cap["target_base"].as_u64().unwrap()as u32;let cfg=&cap["source_config"];let width=cfg["width"].as_u64().unwrap()as usize;let height=cfg["height"].as_u64().unwrap()as usize;let health=cfg["health"].as_i64().unwrap();let ground=cfg["ground"].as_bool().unwrap();let shadow=cfg["shadow"].as_bool().unwrap();let cat=Catalog::open(&a[2]).unwrap();let pal=cat.palette().unwrap();')
s=s.replace('0x30093+f as u32','base+f as u32').replace('assert_eq!((src.width,src.height),(32,32));','assert_eq!((src.width,src.height),(width,height));').replace('0x30093+si as u32','base+si as u32')
s=s.replace('assert_eq!(actor["ground"],true);assert_eq!(actor["shadow_enabled"],true);assert_eq!(actor["health"],55);let width=32;let height=32;','assert_eq!(actor["ground"],ground);assert_eq!(actor["shadow_enabled"],shadow);assert_eq!(actor["health"],health);let width=width as i32;let height=height as i32;')
s=s.replace('(0x30093u32..=0x30093)','(base..=base)').replace('ACTUAL_CONTROLLED_DSHP01_ONE_PHASE_ALL4_THREE_ROLES_SUCCESS','ACTUAL_CONTROLLED_DISTINCT_DSHP_ONE_PHASE_ALL4_THREE_ROLES_SUCCESS').replace('target_preblit_equals_frozen_G2_30093_bank','target_preblit_equals_own_frozen_G2_intrinsic_bank')
s=s.replace('Controlled OriginalS3W3 DSHP01 complete1, one World retains exact raw4 declaration141 and normalpilot2.','Controlled authentic distinct DSHP complete1, one World retains exact chosen declared spawn and normalpilot2. Ground or air shadow follows unchanged Source definition.').replace('Original mission clone retains first exact declared family spawn','Original mission clone retains literal configured declared family spawn')
(O/'four_dshp_capture_and_composition.rs').write_text(s)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
orig={}
for line in(R/'data/INDEX').read_text().splitlines():
 if line.strip():
  aid,size,path=line.split();f=R/'data'/path;assert f.stat().st_size==int(size);orig[path]=sha(f)
contract=json.loads((R/'.reference/hd-SourceG2-current-intrinsic-helper-and-epoch-carry-private-20261019-v1/CURRENT-SOURCEG2-HELPER-COMPILE-RECEIPT.json').read_text())
assert all(sha(R/f)==h for f,h in contract['source18'].items())
manifest=json.loads((R/'data/hd/hd.json').read_text());count=sum(seq['frame_count']for seq in manifest['sequences']);assert count==5636,count
shutil.copyfile(R/'data/hd/hd.json',O/'historic-actual-fullH5636-manifest.json')
(O/'PRE-WORLD-SOURCE-AND-EPOCH-INPUT-GUARDS.json').write_text(json.dumps({'source18':contract['source18'],'INDEX_sha256':sha(R/'data/INDEX'),'all_INDEX_original_input_sha256':orig,'full_H5636_header_sha256':sha(O/'historic-actual-fullH5636-manifest.json'),'library':contract['library'],'helper_source_template_sha256':sha(T/'dshp01_capture_and_composition.rs'),'new_adapter_source_sha256':sha(O/'four_dshp_capture_and_composition.rs'),'actual_World_calls_so_far':0},indent=2)+'\n')
print('configs',[(x,v['chosen_spawn'])for x,v in chosen.items()]);print('Original_input_pins',len(orig),'H',count)
