// All cursors are per entity. Arrival and attack timers use simulation callbacks.
fn is_alive(event) {
    for unit in event.entities {
        if unit.entity == event.entity && unit.health > 0 { return true; }
    }
    false
}

fn on_spawn(event, state, random) {
    // Register the life before checking current liveness: the engine can kill a
    // queued spawn during advance, before it dispatches this callback. Its later
    // actual death still needs one objective update, without movement or audio.
    if !state.contains("directions") { state.directions = #{}; }
    if !state.contains("ages") { state.ages = #{}; }
    let key = event.entity.to_string();
    state.directions[key] = 1;
    state.ages[key] = 0;
    if !is_alive(event) { return #{ commands: [], state: state }; }
    #{ commands: [#{ op: "velocity", entity: event.entity, vx: 0, vy: 2 }], state: state }
}

fn on_tick(event, state, random) {
    if event.health <= 0 || !is_alive(event) { return #{ commands: [], state: state }; }
    if event.y < 24 {
        return #{ commands: [#{ op: "velocity", entity: event.entity, vx: 0, vy: 2 }], state: state };
    }
    let key = event.entity.to_string();
    // An untracked unit cannot acquire another entity's attack timer.
    if !state.contains("ages") || !state.ages.contains(key) {
        return #{ commands: [], state: state };
    }
    let direction = state.directions[key];
    if event.x >= 144 { direction = -1; }
    if event.x <= 80 { direction = 1; }
    state.directions[key] = direction;
    let age = state.ages[key] + 1;
    state.ages[key] = age;
    let commands = [
        #{ op: "move", entity: event.entity, x: event.x, y: 24 },
        #{ op: "velocity", entity: event.entity, vx: direction, vy: 0 }
    ];
    // Twelve ticks of warning precede the shot: about half a second at 70/3 Hz.
    if age % 54 == 42 {
        commands.push(#{ op: "play_sound", sound: "iron_coast_boss_2:warning" });
    }
    if age % 54 == 0 {
        // Alternate parallel outer lanes with a diverging inner fork.
        // Both leave a readable opening directly under the central radar dish.
        if (age / 54) % 2 == 1 {
            commands.push(#{ op: "projectile", weapon: "iron_coast_boss_2:projectile", x: event.x + 24, y: 75, vx: 0, vy: 4, hostile: true });
            commands.push(#{ op: "projectile", weapon: "iron_coast_boss_2:projectile", x: event.x + 72, y: 75, vx: 0, vy: 4, hostile: true });
        } else {
            commands.push(#{ op: "projectile", weapon: "iron_coast_boss_2:projectile", x: event.x + 36, y: 75, vx: -1, vy: 4, hostile: true });
            commands.push(#{ op: "projectile", weapon: "iron_coast_boss_2:projectile", x: event.x + 60, y: 75, vx: 1, vy: 4, hostile: true });
        }
        commands.push(#{ op: "play_sound", sound: "iron_coast_boss_2:shot" });
        state.shots = if state.contains("shots") { state.shots + 1 } else { 1 };
    }
    #{ commands: commands, state: state }
}

fn on_hit(event, state, random) {
    state.hits = if state.contains("hits") { state.hits + 1 } else { 1 };
    #{ commands: [], state: state }
}

fn on_death(event, state, random) {
    let key = event.entity.to_string();
    // A death callback must refer to a spawned unit that is absent from live queries.
    // Removing its cursor also makes repeated death notifications harmless.
    if is_alive(event) || !state.contains("ages") || !state.ages.contains(key) {
        return #{ commands: [], state: state };
    }
    state.ages.remove(key);
    state.directions.remove(key);
    state.destroyed = if state.contains("destroyed") { state.destroyed + 1 } else { 1 };
    let defeated = if event.objectives.contains("iron_coast_boss_2:defeated") { event.objectives["iron_coast_boss_2:defeated"] + 1 } else { 1 };
    #{ commands: [
        #{ op: "objective", key: "iron_coast_boss_2:defeated", value: defeated },
        #{ op: "effect", x: event.x + 32, y: event.y + 38 },
        #{ op: "effect", x: event.x + 64, y: event.y + 38 },
        #{ op: "play_sound", sound: "iron_coast_boss_2:death" }
    ], state: state }
}
