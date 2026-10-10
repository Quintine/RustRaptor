fn is_alive(event) {
    for unit in event.entities {
        if unit.entity == event.entity && unit.health > 0 { return true; }
    }
    false
}

// Per-entity directions permit multiple cruisers without sharing a patrol cursor.
fn on_spawn(event, state, random) {
    if !is_alive(event) { return #{ commands: [], state: state }; }
    if !state.contains("directions") { state.directions = #{}; }
    state.directions[event.entity.to_string()] = 1;
    #{ commands: [#{ op: "velocity", entity: event.entity, vx: 0, vy: 2 }], state: state }
}

fn on_tick(event, state, random) {
    if event.health <= 0 || !is_alive(event) { return #{ commands: [], state: state }; }
    if event.y < 24 {
        return #{ commands: [#{ op: "velocity", entity: event.entity, vx: 0, vy: 2 }], state: state };
    }
    let key = event.entity.to_string();
    if !state.contains("directions") { state.directions = #{}; }
    let direction = if state.directions.contains(key) { state.directions[key] } else { 1 };
    if event.x >= 144 { direction = -1; }
    if event.x <= 80 { direction = 1; }
    state.directions[key] = direction;
    let commands = [
        #{ op: "move", entity: event.entity, x: event.x, y: 24 },
        #{ op: "velocity", entity: event.entity, vx: direction, vy: 0 }
    ];
    if event.tick % 54 == 0 {
        commands.push(#{ op: "projectile", weapon: "iron_coast_boss:projectile", x: event.x + 35, y: 64, vx: -2, vy: 4, hostile: true });
        commands.push(#{ op: "projectile", weapon: "iron_coast_boss:projectile", x: event.x + 48, y: 64, vx: 0, vy: 4, hostile: true });
        commands.push(#{ op: "projectile", weapon: "iron_coast_boss:projectile", x: event.x + 61, y: 64, vx: 2, vy: 4, hostile: true });
        commands.push(#{ op: "play_sound", sound: "iron_coast_boss:shot" });
        state.shots = if state.contains("shots") { state.shots + 1 } else { 1 };
    }
    #{ commands: commands, state: state }
}

fn on_hit(event, state, random) {
    state.hits = if state.contains("hits") { state.hits + 1 } else { 1 };
    #{ commands: [], state: state }
}

fn on_death(event, state, random) {
    if state.contains("directions") { state.directions.remove(event.entity.to_string()); }
    state.destroyed = if state.contains("destroyed") { state.destroyed + 1 } else { 1 };
    let defeated = if event.objectives.contains("iron_coast_boss:defeated") { event.objectives["iron_coast_boss:defeated"] + 1 } else { 1 };
    #{ commands: [
        #{ op: "objective", key: "iron_coast_boss:defeated", value: defeated },
        #{ op: "effect", x: event.x + 35, y: event.y + 36 },
        #{ op: "effect", x: event.x + 61, y: event.y + 36 },
        #{ op: "play_sound", sound: "iron_coast_boss:death" }
    ], state: state }
}
