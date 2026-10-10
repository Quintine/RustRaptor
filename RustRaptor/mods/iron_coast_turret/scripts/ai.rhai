// Ground emplacements inherit deterministic terrain scrolling (one pixel/tick).
fn on_spawn(event, state, random) {
    #{ commands: [], state: state }
}

fn on_tick(event, state, random) {
    #{ commands: [], state: state }
}

fn on_fire(event, state, random) {
    state.shots = if state.contains("shots") { state.shots + 1 } else { 1 };
    #{ commands: [#{ op: "play_sound", sound: "iron_coast_turret:shot" }], state: state }
}

fn on_hit(event, state, random) {
    state.hits = if state.contains("hits") { state.hits + 1 } else { 1 };
    #{ commands: [], state: state }
}

fn on_death(event, state, random) {
    state.destroyed = if state.contains("destroyed") { state.destroyed + 1 } else { 1 };
    let defeated = if event.objectives.contains("iron_coast_turret:defeated") { event.objectives["iron_coast_turret:defeated"] + 1 } else { 1 };
    #{ commands: [
        #{ op: "objective", key: "iron_coast_turret:defeated", value: defeated },
        #{ op: "play_sound", sound: "iron_coast_turret:death" }
    ], state: state }
}
