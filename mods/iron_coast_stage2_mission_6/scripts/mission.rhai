// Pacing1.0.1: warning precedes the unchanged real boss spawn by180ticks.
// All encounter flags reset on entry. No inventory grants, consumption or equipment loans.
fn on_mission_start(event, state, random) {
    #{commands:[#{op:"objective",key:"iron_coast_stage2_mission_6:targets_destroyed",value:0},#{op:"objective",key:"iron_coast_stage2_mission_6:targets_required",value:3},#{op:"objective",key:"iron_coast_stage2_mission_6:complete",value:0},#{op:"objective",key:"iron_coast_stage2_mission_6:phase",value:1},#{op:"objective",key:"iron_coast_stage2_mission_6:hazard_lane",value:0},#{op:"objective",key:"iron_coast_stage2_boss_6:defeated",value:0},#{op:"objective",key:"iron_coast_stage2_mission_6:field_repair",value:0},#{op:"objective",key:"iron_coast_stage2_mission_6:debrief",value:0},#{op:"play_sound",sound:"iron_coast_stage2_mission_6:approach"}],state:#{complete:false,repair:false,boss_warning:false}}
}
fn on_tick(event, state, random) {
    let commands = [];
    if event.tick == 440 || event.tick == 1080 {
        commands.push(#{op:"objective",key:"iron_coast_stage2_mission_6:phase",value:2});
        commands.push(#{op:"play_sound",sound:"iron_coast_stage2_mission_6:alarm"});
    }
    if event.tick >= 1400 && !state.repair {
        state.repair = true;
        commands.push(#{op:"shield",amount:15});
        commands.push(#{op:"objective",key:"iron_coast_stage2_mission_6:field_repair",value:1});
    }
    // Warning precedes three outer-lane shots by24 ticks. The center remains safe.
    if event.tick >= 700 && event.tick < 2200 {
        if event.tick % 240 == 0 {
            let lane = if (event.tick / 240) % 2 == 0 { -1 } else { 1 };
            commands.push(#{op:"objective",key:"iron_coast_stage2_mission_6:hazard_lane",value:lane});
            commands.push(#{op:"play_sound",sound:"iron_coast_stage2_mission_6:hazard"});
        }
        if event.tick % 240 == 24 {
            let x = if (event.tick / 240) % 2 == 0 { 48 } else { 248 };
            for dx in [-12,0,12] { commands.push(#{op:"projectile",weapon:"iron_coast_stage2_mission_6:hazard_shell",x:x+dx,y:12,vx:0,vy:4,hostile:true}); }
            commands.push(#{op:"objective",key:"iron_coast_stage2_mission_6:hazard_lane",value:0});
        }
    }
    if event.tick >= 2200 && !state.boss_warning {
        state.boss_warning = true;
        commands.push(#{op:"objective",key:"iron_coast_stage2_mission_6:phase",value:3});
        commands.push(#{op:"shield",amount:15});
        commands.push(#{op:"play_sound",sound:"iron_coast_stage2_mission_6:alarm"});
    }
    let targets = if event.objectives.contains("iron_coast_stage2_mission_6:targets_destroyed") { event.objectives["iron_coast_stage2_mission_6:targets_destroyed"] } else { 0 };
    let boss = if event.objectives.contains("iron_coast_stage2_boss_6:defeated") { event.objectives["iron_coast_stage2_boss_6:defeated"] } else { 0 };
    if targets >= 3 && boss >= 1 && !state.complete {
        state.complete = true;
        commands.push(#{op:"objective",key:"iron_coast_stage2_mission_6:complete",value:1});
        commands.push(#{op:"objective",key:"iron_coast_stage2_mission_6:phase",value:4});
        commands.push(#{op:"credits",amount:32000});
        commands.push(#{op:"play_sound",sound:"iron_coast_stage2_mission_6:victory"});
        commands.push(#{op:"complete"});
    }
    #{commands:commands,state:state}
}
fn on_mission_end(event, state, random) {
    #{commands:[#{op:"objective",key:"iron_coast_stage2_mission_6:debrief",value:if event.success { 1 } else { 0 }}],state:state}
}
