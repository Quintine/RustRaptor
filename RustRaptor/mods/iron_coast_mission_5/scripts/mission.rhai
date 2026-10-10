// All encounter state resets on entry, even when prior script statistics were saved.
fn on_mission_start(event, state, random) {
    let commands = [
        #{op:"objective", key:"iron_coast_mission_5:phase", value:1},
        #{op:"objective", key:"iron_coast_mission_5:foundries_destroyed", value:0},
        #{op:"objective", key:"iron_coast_mission_5:foundries_required", value:2},
        #{op:"objective", key:"iron_coast_mission_5:heat_lane", value:0},
        #{op:"objective", key:"iron_coast_mission_5:complete", value:0},
        #{op:"objective", key:"iron_coast_boss_5:defeated", value:0},
        #{op:"play_sound", sound:"iron_coast_mission_5:approach"}
    ];
    let slots = event.player.inventory.len() + event.player.super_shield_reserves.len();
    if event.player.inventory.contains("iron_coast_mission_5:coolant") || slots < 20 {
        commands.push(#{op:"give_item", item:"iron_coast_mission_5:coolant", count:3});
    }
    #{commands:commands, state:#{complete:false, second_alarm:false, boss_alarm:false}}
}

fn on_tick(event, state, random) {
    let commands = [];
    if event.tick == 240 {
        commands.push(#{op:"objective", key:"iron_coast_mission_5:phase", value:2});
        commands.push(#{op:"play_sound", sound:"iron_coast_mission_5:foundry_alarm"});
    }
    if event.tick >= 920 && !state.second_alarm {
        state.second_alarm = true;
        commands.push(#{op:"objective", key:"iron_coast_mission_5:phase", value:3});
        commands.push(#{op:"play_sound", sound:"iron_coast_mission_5:foundry_alarm"});
    }
    // Slag falls only in the outer lanes. A warning precedes each bounded volley
    // by 35 simulation ticks (1.5 seconds); the central firing corridor is safe.
    if event.tick >= 360 && event.tick < 1560 {
        let cycle = event.tick / 180;
        let left = cycle % 2 == 0;
        if event.tick % 180 == 0 {
            let lane = if left { -1 } else { 1 };
            commands.push(#{op:"objective", key:"iron_coast_mission_5:heat_lane", value:lane});
            commands.push(#{op:"play_sound", sound:"iron_coast_mission_5:heat_warning"});
        }
        if event.tick % 180 == 35 {
            let origin = if left { 32 } else { 232 };
            for offset in [0, 16, 32] {
                commands.push(#{op:"projectile", weapon:"iron_coast_mission_5:slag", x:origin + offset, y:24, vx:0, vy:5, hostile:true});
            }
            commands.push(#{op:"play_sound", sound:"iron_coast_mission_5:slag_release"});
            commands.push(#{op:"objective", key:"iron_coast_mission_5:heat_lane", value:0});
        }
    }
    if event.tick >= 1660 && !state.boss_alarm {
        state.boss_alarm = true;
        commands.push(#{op:"objective", key:"iron_coast_mission_5:phase", value:4});
        commands.push(#{op:"play_sound", sound:"iron_coast_mission_5:launch_alarm"});
    }
    let foundries = if event.objectives.contains("iron_coast_mission_5:foundries_destroyed") {
        event.objectives["iron_coast_mission_5:foundries_destroyed"]
    } else { 0 };
    let boss = if event.objectives.contains("iron_coast_boss_5:defeated") {
        event.objectives["iron_coast_boss_5:defeated"]
    } else { 0 };
    if foundries >= 2 && boss >= 1 && !state.complete {
        state.complete = true;
        commands.push(#{op:"objective", key:"iron_coast_mission_5:phase", value:5});
        commands.push(#{op:"objective", key:"iron_coast_mission_5:complete", value:1});
        commands.push(#{op:"credits", amount:15000});
        commands.push(#{op:"play_sound", sound:"iron_coast_mission_5:victory"});
        commands.push(#{op:"complete"});
    }
    #{commands:commands, state:state}
}

fn on_mission_end(event, state, random) {
    let value = if event.success { 1 } else { 0 };
    #{commands:[#{op:"objective", key:"iron_coast_mission_5:debrief", value:value}], state:state}
}
