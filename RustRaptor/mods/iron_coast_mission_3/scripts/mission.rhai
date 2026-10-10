fn on_mission_start(event, state, random) {
    // Reset mission state even when the script was restored from a prior flight.
    #{commands:[
        #{op:"objective",key:"iron_coast_mission_3:phase",value:1},
        #{op:"objective",key:"iron_coast_mission_3:convoys_required",value:3},
        #{op:"objective",key:"iron_coast_mission_3:convoys_intercepted",value:0},
        #{op:"objective",key:"iron_coast_mission_3:escorts_required",value:2},
        #{op:"objective",key:"iron_coast_mission_3:complete",value:0},
        #{op:"objective",key:"iron_coast_turret:defeated",value:0},
        #{op:"objective",key:"iron_coast_boss_3:defeated",value:0},
        #{op:"play_sound",sound:"iron_coast_mission_3:approach"}
    ],state:#{convoy_alarm:false,boss_alarm:false,complete:false}}
}

fn on_tick(event, state, random) {
    let commands=[];
    // Essential escort targets cannot scroll away and leave the objectives
    // impossible. Hold them below the command cruiser in the firing corridor.
    for unit in event.entities {
        if unit.definition=="iron_coast_turret:unit" && unit.health>0 && unit.y>=74 {
            commands.push(#{op:"move",entity:unit.entity,x:unit.x,y:74});
        }
    }
    if event.tick>=180 && !state.convoy_alarm {
        state.convoy_alarm=true;
        commands.push(#{op:"objective",key:"iron_coast_mission_3:phase",value:2});
        commands.push(#{op:"play_sound",sound:"iron_coast_mission_3:convoy_alarm"});
    }
    if event.tick>=1100 && !state.boss_alarm {
        state.boss_alarm=true;
        commands.push(#{op:"objective",key:"iron_coast_mission_3:phase",value:3});
        commands.push(#{op:"play_sound",sound:"iron_coast_mission_3:boss_alarm"});
    }
    let convoys=event.objectives["iron_coast_mission_3:convoys_intercepted"];
    let escorts=event.objectives["iron_coast_turret:defeated"];
    let boss=event.objectives["iron_coast_boss_3:defeated"];
    if convoys>=3 && escorts>=2 && boss>=1 && !state.complete {
        state.complete=true;
        commands.push(#{op:"objective",key:"iron_coast_mission_3:phase",value:4});
        commands.push(#{op:"objective",key:"iron_coast_mission_3:complete",value:1});
        commands.push(#{op:"credits",amount:7500});
        commands.push(#{op:"play_sound",sound:"iron_coast_mission_3:victory"});
        commands.push(#{op:"complete"});
    }
    #{commands:commands,state:state}
}

fn on_mission_end(event,state,random) {
    let debrief=if event.success {1} else {0};
    #{commands:[#{op:"objective",key:"iron_coast_mission_3:debrief",value:debrief}],state:state}
}
