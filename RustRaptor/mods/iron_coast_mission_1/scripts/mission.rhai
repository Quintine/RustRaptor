fn on_mission_start(event, state, random) {
    let commands=[
        #{op:"objective", key:"iron_coast_mission_1:phase", value:1},
        #{op:"objective", key:"iron_coast_mission_1:turrets_required", value:2},
        #{op:"objective", key:"iron_coast_mission_1:complete", value:0},
        #{op:"play_sound", sound:"iron_coast_mission_1:approach"}
    ];
    // A full veteran inventory must not prevent a mission from starting.
    // Existing equipment may receive its normal refill without adding a slot.
    let slots=event.player.inventory.len()+event.player.super_shield_reserves.len();
    if event.player.inventory.contains("iron_coast_mission_1:repair") || slots<20 {
        commands.push(#{op:"give_item",item:"iron_coast_mission_1:repair",count:3});
        if !event.player.inventory.contains("iron_coast_mission_1:repair") {slots+=1;}
    }
    let trial=0;
    // Borrow a cannon for this mission only. Never replace or remove an owned copy.
    let trial_loaned=false;
    if event.player.inventory.contains("pulse_cannon:equipment")
        && event.player.inventory["pulse_cannon:equipment"]>0 {
        trial=1;
    } else if slots<20 {
        commands.push(#{op:"give_item",item:"pulse_cannon:equipment",count:1});
        trial=1;
        trial_loaned=true;
    }
    commands.push(#{op:"objective",key:"iron_coast_mission_1:trial_issued",value:trial});
    #{commands:commands,state:#{dock_alarm:false,boss_alarm:false,complete:false,trial_loaned:trial_loaned}}
}

fn on_tick(event, state, random) {
    let commands=[];
    if event.tick>=280 && !state.dock_alarm {
        state.dock_alarm=true;
        commands.push(#{op:"objective",key:"iron_coast_mission_1:phase",value:2});
        commands.push(#{op:"play_sound",sound:"iron_coast_mission_1:dock_alarm"});
    }
    if event.tick>=720 && !state.boss_alarm {
        state.boss_alarm=true;
        commands.push(#{op:"objective",key:"iron_coast_mission_1:phase",value:3});
        commands.push(#{op:"play_sound",sound:"iron_coast_mission_1:boss_alarm"});
    }
    let turrets=0;
    if event.objectives.contains("iron_coast_turret:defeated") {
        turrets=event.objectives["iron_coast_turret:defeated"];
    }
    let boss=0;
    if event.objectives.contains("iron_coast_boss:defeated") {
        boss=event.objectives["iron_coast_boss:defeated"];
    }
    // Surviving turrets must be disabled even if the command ship died first.
    if turrets>=2 && boss>=1 && !state.complete {
        state.complete=true;
        commands.push(#{op:"objective",key:"iron_coast_mission_1:phase",value:4});
        commands.push(#{op:"objective",key:"iron_coast_mission_1:complete",value:1});
        commands.push(#{op:"credits",amount:5000});
        commands.push(#{op:"play_sound",sound:"iron_coast_mission_1:victory"});
        commands.push(#{op:"complete"});
    }
    #{commands:commands,state:state}
}

fn on_mission_end(event,state,random) {
    let value=0;
    if event.success {value=1;}
    let commands=[#{op:"objective",key:"iron_coast_mission_1:debrief",value:value}];
    if state.contains("trial_loaned") && state.trial_loaned
        && event.player.inventory.contains("pulse_cannon:equipment")
        && event.player.inventory["pulse_cannon:equipment"]>0 {
        commands.push(#{op:"consume_item",item:"pulse_cannon:equipment",count:1});
    }
    state.trial_loaned=false;
    #{commands:commands,state:state}
}
