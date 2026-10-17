// Pacing1.0.1: warning precedes the unchanged real boss spawn by180ticks.
// Only actual shared-enemy and boss death callbacks advance kill goals.
fn on_mission_start(event,state,random) {
    #{commands:[#{op:"objective",key:"iron_coast_stage2_mission_2:phase",value:1},#{op:"objective",key:"iron_coast_stage2_mission_2:complete",value:0},#{op:"objective",key:"iron_coast_stage2_mission_2:debrief",value:0},#{op:"objective",key:"iron_coast_stage2_skimmer:defeated",value:0},#{op:"objective",key:"iron_coast_stage2_boss_2:defeated",value:0},#{op:"play_sound",sound:"iron_coast_stage2_mission_2:approach"}],state:#{complete:false,boss_alarm:false,reported:0}}
}
fn on_tick(event,state,random) {
    let commands=[];
    // Required convoys may enter normally, but stay reachable once on screen.
    // Their own scripts retain all firing/timing/health; no escape counts as death.
    for unit in event.entities {
        if unit.definition=="iron_coast_stage2_skimmer:unit" && unit.health>0 && unit.y>=85 {
            let x=unit.x;if x<24 {x=24;}if x>264 {x=264;}
            commands.push(#{op:"move",entity:unit.entity,x:x,y:85});
            commands.push(#{op:"velocity",entity:unit.entity,vx:0,vy:0});
        }
    }
    let kills=if event.objectives.contains("iron_coast_stage2_skimmer:defeated") {event.objectives["iron_coast_stage2_skimmer:defeated"]} else {0};
    if kills>state.reported {state.reported=kills;commands.push(#{op:"play_sound",sound:"iron_coast_stage2_mission_2:objective"});}
    if event.tick>=2100 && !state.boss_alarm {state.boss_alarm=true;commands.push(#{op:"objective",key:"iron_coast_stage2_mission_2:phase",value:2});commands.push(#{op:"play_sound",sound:"iron_coast_stage2_mission_2:boss_alarm"});}
    let defeated=if event.objectives.contains("iron_coast_stage2_boss_2:defeated") {event.objectives["iron_coast_stage2_boss_2:defeated"]} else {0};
    if kills>=4 && defeated>=1 && !state.complete {
        state.complete=true;
        commands.push(#{op:"objective",key:"iron_coast_stage2_mission_2:phase",value:3});commands.push(#{op:"objective",key:"iron_coast_stage2_mission_2:complete",value:1});commands.push(#{op:"credits",amount:32000});commands.push(#{op:"play_sound",sound:"iron_coast_stage2_mission_2:victory"});commands.push(#{op:"complete"});
    }
    #{commands:commands,state:state}
}
fn on_mission_end(event,state,random) {
    #{commands:[#{op:"objective",key:"iron_coast_stage2_mission_2:debrief",value:if event.success {1} else {0}}],state:state}
}
