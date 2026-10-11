fn is_alive(event) {
    for unit in event.entities {
        if unit.entity == event.entity && unit.health > 0 { return true; }
    }
    false
}

// State is shared by a script, so each staged or simultaneous boss has its own
// patrol direction, charge timer and alternating attack cursor.
fn on_spawn(event, state, random) {
    if state.contains("last_death") && state.last_death == event.entity { state.remove("last_death"); }
    if !is_alive(event) { return #{ commands: [], state: state }; }
    if !state.contains("units") { state.units = #{}; }
    state.units[event.entity.to_string()] = #{direction: 1, age: 0, volley: 0};
    #{ commands: [#{ op: "velocity", entity: event.entity, vx: 0, vy: 2 }], state: state }
}

fn on_tick(event, state, random) {
    if event.health <= 0 || !is_alive(event) { return #{ commands: [], state: state }; }
    let key = event.entity.to_string();
    if !state.contains("units") { state.units = #{}; }
    let cursor = if state.units.contains(key) {
        state.units[key]
    } else { #{direction: 1, age: 0, volley: 0} };
    if event.y < 24 {
        state.units[key] = cursor;
        return #{ commands: [#{ op: "velocity", entity: event.entity, vx: 0, vy: 2 }], state: state };
    }
    if event.x >= 144 { cursor.direction = -1; }
    if event.x <= 80 { cursor.direction = 1; }
    cursor.age += 1;
    let commands = [
        #{ op: "move", entity: event.entity, x: event.x, y: 24 },
        #{ op: "velocity", entity: event.entity, vx: cursor.direction, vy: 0 }
    ];
    // Nine simulation ticks (0.386 seconds) of audible warning precede each
    // volley. Charging does not create an explosion in front of the aircraft.
    if cursor.age % 54 == 45 {
        commands.push(#{ op: "play_sound", sound: "iron_coast_boss_6:warning" });
    }
    if cursor.age % 54 == 0 {
        if cursor.volley % 2 == 0 {
            commands.push(#{ op: "projectile", weapon: "iron_coast_boss_6:projectile", x: event.x + 28, y: event.y + 60, vx: -2, vy: 4, hostile: true });
            commands.push(#{ op: "projectile", weapon: "iron_coast_boss_6:projectile", x: event.x + 48, y: event.y + 60, vx: 0, vy: 4, hostile: true });
            commands.push(#{ op: "projectile", weapon: "iron_coast_boss_6:projectile", x: event.x + 68, y: event.y + 60, vx: 2, vy: 4, hostile: true });
        } else {
            commands.push(#{ op: "projectile", weapon: "iron_coast_boss_6:projectile", x: event.x + 28, y: event.y + 60, vx: 0, vy: 4, hostile: true });
            commands.push(#{ op: "projectile", weapon: "iron_coast_boss_6:projectile", x: event.x + 68, y: event.y + 60, vx: 0, vy: 4, hostile: true });
        }
        commands.push(#{ op: "play_sound", sound: "iron_coast_boss_6:shot" });
        cursor.volley += 1;
    }
    state.units[key] = cursor;
    #{ commands: commands, state: state }
}

fn on_hit(event, state, random) {
    state.hits = if state.contains("hits") { state.hits + 1 } else { 1 };
    #{ commands: [], state: state }
}

fn on_death(event, state, random) {
    let key = event.entity.to_string();
    // Retired entities cannot fire. Preserve other live bosses' cursors, and
    // still count an aircraft destroyed before its queued spawn hook runs.
    if state.contains("last_death") && state.last_death == event.entity {
        return #{ commands: [], state: state };
    }
    state.last_death = event.entity;
    if state.contains("units") { state.units.remove(key); }
    state.destroyed = if state.contains("destroyed") { state.destroyed + 1 } else { 1 };
    let defeated = if event.objectives.contains("iron_coast_boss_6:defeated") {
        event.objectives["iron_coast_boss_6:defeated"] + 1
    } else { 1 };
    #{ commands: [
        #{ op: "objective", key: "iron_coast_boss_6:defeated", value: defeated },
        #{ op: "effect", x: event.x + 28, y: event.y + 44 },
        #{ op: "effect", x: event.x + 68, y: event.y + 44 },
        #{ op: "play_sound", sound: "iron_coast_boss_6:death" }
    ], state: state }
}
