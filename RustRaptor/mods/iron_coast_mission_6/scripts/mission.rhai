// Mission state resets on every sortie, including replaying a failed attempt.
fn on_mission_start(event, state, random) {
    let commands = [
        #{op:"objective", key:"iron_coast_mission_6:phase", value:1},
        #{op:"objective", key:"iron_coast_mission_6:batteries_required", value:6},
        #{op:"objective", key:"iron_coast_mission_6:cruisers_required", value:2},
        #{op:"objective", key:"iron_coast_mission_6:complete", value:0},
        #{op:"objective", key:"iron_coast_turret:defeated", value:0},
        #{op:"objective", key:"iron_coast_boss_6:defeated", value:0},
        #{op:"play_sound", sound:"iron_coast_mission_6:approach"},
        #{op:"shield", amount:25}
    ];
    let loaned = false;
    let slots = event.player.inventory.len() + event.player.super_shield_reserves.len();
    // Loan a column weapon only when it fits. An owned copy is never removed.
    if !event.player.inventory.contains("ion_lance:equipment") && slots < 20 {
        commands.push(#{op:"give_item", item:"ion_lance:equipment", count:1});
        loaned = true;
    }
    #{commands:commands, state:#{fleet:false, crown:false, complete:false, loaned:loaned}}
}

fn on_tick(event, state, random) {
    let commands = [];
    // These are mandatory fixed citadel batteries. Keep surviving emplacements
    // in firing range even when the terrain scrolls beyond the headquarters.
    for unit in event.entities {
        if unit.definition == "iron_coast_turret:unit" && unit.health > 0 {
            let anchor = if unit.x == 32 || unit.x == 112 || unit.x == 192 {48} else {80};
            if unit.y > anchor {
                commands.push(#{op:"move", entity:unit.entity, x:unit.x, y:anchor});
            }
        }
    }
    if event.tick >= 1450 && !state.fleet {
        state.fleet = true;
        commands.push(#{op:"objective", key:"iron_coast_mission_6:phase", value:2});
        commands.push(#{op:"play_sound", sound:"iron_coast_mission_6:fleet_alarm"});
        commands.push(#{op:"shield", amount:20});
    }
    if event.tick >= 2350 && !state.crown {
        state.crown = true;
        commands.push(#{op:"objective", key:"iron_coast_mission_6:phase", value:3});
        commands.push(#{op:"play_sound", sound:"iron_coast_mission_6:crown_alarm"});
        commands.push(#{op:"shield", amount:20});
    }
    let batteries = if event.objectives.contains("iron_coast_turret:defeated") {
        event.objectives["iron_coast_turret:defeated"]
    } else {0};
    let cruisers = if event.objectives.contains("iron_coast_boss_6:defeated") {
        event.objectives["iron_coast_boss_6:defeated"]
    } else {0};
    if state.crown && batteries >= 6 && cruisers >= 2 && !state.complete {
        state.complete = true;
        commands.push(#{op:"objective", key:"iron_coast_mission_6:phase", value:4});
        commands.push(#{op:"objective", key:"iron_coast_mission_6:complete", value:1});
        commands.push(#{op:"credits", amount:30000});
        commands.push(#{op:"play_sound", sound:"iron_coast_mission_6:victory"});
        commands.push(#{op:"complete"});
    }
    #{commands:commands, state:state}
}

fn on_mission_end(event, state, random) {
    let commands = [#{op:"objective", key:"iron_coast_mission_6:debrief", value:if event.success {1} else {0}}];
    if state.contains("loaned") && state.loaned
        && event.player.inventory.contains("ion_lance:equipment")
        && event.player.inventory["ion_lance:equipment"] > 0 {
        commands.push(#{op:"consume_item", item:"ion_lance:equipment", count:1});
    }
    state.loaned = false;
    #{commands:commands, state:state}
}
