// Stormwall uses the shared Iron Coast units and pins every objective battery
// on the battlefield until it is destroyed. Nothing completes on a time limit.
fn on_mission_start(event, state, random) {
    let commands = [
        #{op:"objective",key:"iron_coast_mission_4:phase",value:1},
        #{op:"objective",key:"iron_coast_mission_4:turrets_required",value:4},
        #{op:"objective",key:"iron_coast_mission_4:complete",value:0},
        #{op:"objective",key:"iron_coast_turret:defeated",value:0},
        #{op:"objective",key:"iron_coast_boss_4:defeated",value:0},
        #{op:"play_sound",sound:"iron_coast_mission_4:approach"}
    ];
    // A full inventory starts safely. Existing equipment is never replaced.
    let slots = event.player.inventory.len() + event.player.super_shield_reserves.len();
    let loaned = false;
    let available = event.player.inventory.contains("pulse_cannon:equipment")
        && event.player.inventory["pulse_cannon:equipment"] > 0;
    if !available && slots < 20 {
        loaned = true;
        available = true;
        commands.push(#{op:"give_item",item:"pulse_cannon:equipment",count:1});
    }
    let issued = if available {1} else {0};
    commands.push(#{op:"objective",key:"iron_coast_mission_4:trial_issued",value:issued});
    #{commands:commands,state:#{loaned:loaned,second_battery:false,cruiser_alarm:false,complete:false}}
}

fn on_tick(event, state, random) {
    let commands = [];
    // The ground-unit engine scrolls one pixel each step; clamp in the mission
    // callback to keep mandatory survivors reachable after the coast passes.
    for unit in event.entities {
        if unit.definition == "iron_coast_turret:unit" && unit.health > 0 && unit.y >= 72 {
            commands.push(#{op:"move",entity:unit.entity,x:unit.x,y:72});
            commands.push(#{op:"velocity",entity:unit.entity,vx:0,vy:0});
        }
    }
    if event.tick >= 600 && !state.second_battery {
        state.second_battery = true;
        commands.push(#{op:"objective",key:"iron_coast_mission_4:phase",value:2});
        commands.push(#{op:"play_sound",sound:"iron_coast_mission_4:battery_alarm"});
    }
    if event.tick >= 1150 && !state.cruiser_alarm {
        state.cruiser_alarm = true;
        commands.push(#{op:"objective",key:"iron_coast_mission_4:phase",value:3});
        commands.push(#{op:"play_sound",sound:"iron_coast_mission_4:cruiser_alarm"});
    }
    let turrets = if event.objectives.contains("iron_coast_turret:defeated") {
        event.objectives["iron_coast_turret:defeated"]
    } else {0};
    let cruisers = if event.objectives.contains("iron_coast_boss_4:defeated") {
        event.objectives["iron_coast_boss_4:defeated"]
    } else {0};
    if turrets >= 4 && cruisers >= 1 && !state.complete {
        state.complete = true;
        commands.push(#{op:"objective",key:"iron_coast_mission_4:phase",value:4});
        commands.push(#{op:"objective",key:"iron_coast_mission_4:complete",value:1});
        commands.push(#{op:"credits",amount:12000});
        commands.push(#{op:"play_sound",sound:"iron_coast_mission_4:victory"});
        commands.push(#{op:"complete"});
    }
    #{commands:commands,state:state}
}

fn on_mission_end(event, state, random) {
    let success = if event.success {1} else {0};
    let commands = [#{op:"objective",key:"iron_coast_mission_4:debrief",value:success}];
    if state.contains("loaned") && state.loaned
        && event.player.inventory.contains("pulse_cannon:equipment")
        && event.player.inventory["pulse_cannon:equipment"] > 0 {
        commands.push(#{op:"consume_item",item:"pulse_cannon:equipment",count:1});
    }
    state.loaned = false;
    #{commands:commands,state:state}
}
