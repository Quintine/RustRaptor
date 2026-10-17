// Pacing1.0.1: warning precedes the unchanged real boss spawn by180ticks.
fn on_mission_start(event,state,random) {
 #{commands:[#{op:"objective",key:"iron_coast_stage2_mission_3:phase",value:1},#{op:"objective",key:"iron_coast_stage2_mission_3:targets_required",value:4},#{op:"objective",key:"iron_coast_stage2_mission_3:targets_destroyed",value:0},#{op:"objective",key:"iron_coast_stage2_mission_3:complete",value:0},#{op:"objective",key:"iron_coast_stage2_boss_3:defeated",value:0},#{op:"play_sound",sound:"iron_coast_stage2_mission_3:approach"}],state:#{boss_alarm:false,complete:false}}
}
fn on_tick(event,state,random) {
 let commands=[];
 if event.tick==1920 && !state.boss_alarm {
  state.boss_alarm=true;commands.push(#{op:"objective",key:"iron_coast_stage2_mission_3:phase",value:3});commands.push(#{op:"play_sound",sound:"iron_coast_stage2_mission_3:boss_alarm"});
 }
 if event.tick==1100 {commands.push(#{op:"objective",key:"iron_coast_stage2_mission_3:phase",value:2});commands.push(#{op:"play_sound",sound:"iron_coast_stage2_mission_3:target_alarm"});}
 if event.tick%420==210 {
  let left=random[0]%2==0;let x=if left {20} else {300};
  commands.push(#{op:"arc",x:x,y:4,to_x:x-4,to_y:112,ticks:6});
 }
 let kills=if event.objectives.contains("iron_coast_stage2_mission_3:targets_destroyed") {event.objectives["iron_coast_stage2_mission_3:targets_destroyed"]} else {0};
 let boss=if event.objectives.contains("iron_coast_stage2_boss_3:defeated") {event.objectives["iron_coast_stage2_boss_3:defeated"]} else {0};
 if event.tick>=2100 && kills>=4 && boss>=1 && !state.complete {
  state.complete=true;commands.push(#{op:"objective",key:"iron_coast_stage2_mission_3:complete",value:1});commands.push(#{op:"objective",key:"iron_coast_stage2_mission_3:phase",value:4});commands.push(#{op:"credits",amount:14500});commands.push(#{op:"play_sound",sound:"iron_coast_stage2_mission_3:victory"});commands.push(#{op:"complete"});
 }
 #{commands:commands,state:state}
}
fn on_mission_end(event,state,random) {#{commands:[#{op:"objective",key:"iron_coast_stage2_mission_3:debrief",value:if event.success {1} else {0}}],state:state}}
