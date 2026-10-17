// Pacing1.0.1: warning precedes the unchanged real boss spawn by180ticks.
// All state resets on a new sortie. No temporary gear is granted or consumed.
fn on_mission_start(event,state,random) {
 #{commands:[#{op:"objective",key:"iron_coast_stage2_mission_7:phase",value:1},
 #{op:"objective",key:"iron_coast_stage2_mission_7:required_siege",value:4},#{op:"objective",key:"iron_coast_stage2_mission_7:required_skimmers",value:3},
 #{op:"objective",key:"iron_coast_stage2_mission_7:debrief",value:0},#{op:"objective",key:"iron_coast_stage2_mission_7:complete",value:0},
 #{op:"objective",key:"iron_coast_stage2_siege:defeated",value:0},#{op:"objective",key:"iron_coast_stage2_skimmer:defeated",value:0},
 #{op:"objective",key:"iron_coast_stage2_boss_7:defeated",value:0},#{op:"objective",key:"iron_coast_stage2_boss_7:phase",value:1},
 #{op:"play_sound",sound:"iron_coast_stage2_mission_7:approach"},#{op:"shield",amount:15}],
 state:#{second:false,third:false,boss:false,complete:false}}
}
fn on_tick(event,state,random) {
 let commands=[];
 // Required naval targets continue their authored lateral movement, but cannot
 // scroll away before the player destroys them. Native classic waves are not
 // moved, cloned or overridden by this mission script.
 for unit in event.entities {
  if unit.definition=="iron_coast_stage2_siege:unit" || unit.definition=="iron_coast_stage2_skimmer:unit" {
   let y=if unit.definition=="iron_coast_stage2_siege:unit" {48} else {80};
   if unit.y>=y {
    let x=if unit.x<16 {16} else if unit.x>240 {240} else {unit.x};
    commands.push(#{op:"move",entity:unit.entity,x:x,y:y});
   }
  }
 }
 if !state.second && event.tick>=900 {
  state.second=true;
  commands.push(#{op:"objective",key:"iron_coast_stage2_mission_7:phase",value:2});commands.push(#{op:"play_sound",sound:"iron_coast_stage2_mission_7:escalation"});
  commands.push(#{op:"shield",amount:15});
 }
 if !state.third && event.tick>=1800 {
  state.third=true;
  commands.push(#{op:"objective",key:"iron_coast_stage2_mission_7:phase",value:3});commands.push(#{op:"play_sound",sound:"iron_coast_stage2_mission_7:escalation"});
  commands.push(#{op:"shield",amount:15});
 }
 if !state.boss && event.tick>=2320 {
  state.boss=true;
  commands.push(#{op:"objective",key:"iron_coast_stage2_mission_7:phase",value:4});commands.push(#{op:"play_sound",sound:"iron_coast_stage2_mission_7:boss_alarm"});
  commands.push(#{op:"shield",amount:20});
 }
 let siege=if event.objectives.contains("iron_coast_stage2_siege:defeated") {event.objectives["iron_coast_stage2_siege:defeated"]} else {0};
 let skimmers=if event.objectives.contains("iron_coast_stage2_skimmer:defeated") {event.objectives["iron_coast_stage2_skimmer:defeated"]} else {0};
 let bosses=if event.objectives.contains("iron_coast_stage2_boss_7:defeated") {event.objectives["iron_coast_stage2_boss_7:defeated"]} else {0};
 if !state.complete && state.boss && siege>=4 && skimmers>=3 && bosses>=1 {
  state.complete=true;
  commands.push(#{op:"objective",key:"iron_coast_stage2_mission_7:phase",value:5});commands.push(#{op:"objective",key:"iron_coast_stage2_mission_7:debrief",value:1});commands.push(#{op:"objective",key:"iron_coast_stage2_mission_7:complete",value:1});
  commands.push(#{op:"credits",amount:32000});commands.push(#{op:"play_sound",sound:"iron_coast_stage2_mission_7:victory"});commands.push(#{op:"complete"});
 }
 #{commands:commands,state:state}
}
fn on_mission_end(event,state,random) { #{commands:[],state:state} }
