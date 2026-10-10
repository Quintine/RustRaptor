fn on_mission_start(event,state,random) {
    let commands=[
        #{op:"objective",key:"iron_coast_mission_2:phase",value:1},
        #{op:"objective",key:"iron_coast_mission_2:relays_disabled",value:0},
        #{op:"objective",key:"iron_coast_mission_2:complete",value:0},
        #{op:"objective",key:"iron_coast_boss_2:defeated",value:0},
        #{op:"play_sound",sound:"iron_coast_mission_2:approach"}
    ];
    let trial_loaned=false;
    let slots=event.player.inventory.len()+event.player.super_shield_reserves.len();
    if !event.player.inventory.contains("pulse_cannon:equipment") && slots<20 {
        commands.push(#{op:"give_item",item:"pulse_cannon:equipment",count:1});
        trial_loaned=true;
    }
    #{commands:commands,state:#{network_alarm:false,boss_alarm:false,network_down:false,complete:false,trial_loaned:trial_loaned}}
}
fn on_tick(event,state,random) {
    let commands=[];
    if event.tick>=170 && !state.network_alarm {
        state.network_alarm=true;
        commands.push(#{op:"objective",key:"iron_coast_mission_2:phase",value:2});
        commands.push(#{op:"play_sound",sound:"iron_coast_mission_2:network_alarm"});
    }
    let relays=if event.objectives.contains("iron_coast_mission_2:relays_disabled") {
        event.objectives["iron_coast_mission_2:relays_disabled"]
    } else {0};
    if relays>=3 && !state.network_down {
        state.network_down=true;
        commands.push(#{op:"objective",key:"iron_coast_mission_2:network_down",value:1});
        commands.push(#{op:"play_sound",sound:"iron_coast_mission_2:network_down"});
    }
    if event.tick>=860 && !state.boss_alarm {
        state.boss_alarm=true;
        commands.push(#{op:"objective",key:"iron_coast_mission_2:phase",value:3});
        commands.push(#{op:"play_sound",sound:"iron_coast_mission_2:boss_alarm"});
    }
    let boss=if event.objectives.contains("iron_coast_boss_2:defeated") {
        event.objectives["iron_coast_boss_2:defeated"]
    } else {0};
    if relays>=3 && boss>=1 && !state.complete {
        state.complete=true;
        commands.push(#{op:"objective",key:"iron_coast_mission_2:phase",value:4});
        commands.push(#{op:"objective",key:"iron_coast_mission_2:complete",value:1});
        commands.push(#{op:"credits",amount:7500});
        commands.push(#{op:"play_sound",sound:"iron_coast_mission_2:victory"});
        commands.push(#{op:"complete"});
    }
    #{commands:commands,state:state}
}
fn on_mission_end(event,state,random) {
    let commands=[#{op:"objective",key:"iron_coast_mission_2:debrief",value:if event.success {1} else {0}}];
    if state.contains("trial_loaned") && state.trial_loaned
        && event.player.inventory.contains("pulse_cannon:equipment")
        && event.player.inventory["pulse_cannon:equipment"]>0 {
        commands.push(#{op:"consume_item",item:"pulse_cannon:equipment",count:1});
    }
    state.trial_loaned=false;
    #{commands:commands,state:state}
}
