fn alive(event) {
    for unit in event.entities {
        if unit.entity == event.entity && unit.health > 0 { return true; }
    }
    false
}

fn on_spawn(event, state, random) {
    if !alive(event) { return #{commands:[], state:state}; }
    #{commands:[#{op:"velocity", entity:event.entity, vx:0, vy:2}], state:state}
}

fn on_tick(event, state, random) {
    if event.health <= 0 || !alive(event) { return #{commands:[], state:state}; }
    if event.y < 24 {
        return #{commands:[#{op:"velocity", entity:event.entity, vx:0, vy:2}], state:state};
    }
    // Ground objects normally scroll away. These mandatory armored stations
    // remain at reachable y=24 until destroyed, even after the cruiser dies.
    #{commands:[
        #{op:"move", entity:event.entity, x:event.x, y:24},
        #{op:"velocity", entity:event.entity, vx:0, vy:0}
    ], state:state}
}

fn on_fire(event, state, random) {
    #{commands:[#{op:"play_sound", sound:"iron_coast_mission_5:foundry_shot"}], state:state}
}

fn on_death(event, state, random) {
    let destroyed = if event.objectives.contains("iron_coast_mission_5:foundries_destroyed") {
        event.objectives["iron_coast_mission_5:foundries_destroyed"] + 1
    } else { 1 };
    #{commands:[
        #{op:"objective", key:"iron_coast_mission_5:foundries_destroyed", value:destroyed},
        #{op:"play_sound", sound:"iron_coast_mission_5:foundry_shutdown"}
    ], state:state}
}
