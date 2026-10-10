fn is_alive(event) {
    for unit in event.entities {
        if unit.entity == event.entity && unit.health > 0 { return true; }
    }
    false
}

// Velocity changes are committed after the callback completes.
fn on_spawn(event, state, random) {
    if !is_alive(event) { return #{ commands: [], state: state }; }
    #{ commands: [#{ op: "velocity", entity: event.entity, vx: 1, vy: 1 }], state: state }
}

fn on_tick(event, state, random) {
    if event.health <= 0 || !is_alive(event) { return #{ commands: [], state: state }; }
    let sideways = if ((event.tick + event.entity * 7) / 24) % 2 == 0 { 1 } else { -1 };
    if event.x <= 24 { sideways = 1; }
    if event.x >= 272 { sideways = -1; }
    #{ commands: [#{ op: "velocity", entity: event.entity, vx: sideways, vy: 1 }], state: state }
}

fn on_fire(event, state, random) {
    let shots = if state.contains("shots") { state.shots + 1 } else { 1 };
    state.shots = shots;
    #{ commands: [#{ op: "play_sound", sound: "iron_coast_scout:shot" }], state: state }
}

fn on_hit(event, state, random) {
    state.hits = if state.contains("hits") { state.hits + 1 } else { 1 };
    #{ commands: [], state: state }
}

fn on_death(event, state, random) {
    state.destroyed = if state.contains("destroyed") { state.destroyed + 1 } else { 1 };
    let defeated = if event.objectives.contains("iron_coast_scout:defeated") { event.objectives["iron_coast_scout:defeated"] + 1 } else { 1 };
    #{ commands: [
        #{ op: "objective", key: "iron_coast_scout:defeated", value: defeated },
        #{ op: "play_sound", sound: "iron_coast_scout:death" }
    ], state: state }
}
