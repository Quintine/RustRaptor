fn on_spawn(event, state, random) {
    #{ commands: [], state: state }
}

fn on_tick(event, state, random) {
    // on_tick may be queued on the same step as on_death; do not command a retired entity.
    if event.health <= 0 { return #{ commands: [], state: state }; }
    let sideways = if (event.tick / 24) % 2 == 0 { 1 } else { -1 };
    #{ commands: [#{ op: "velocity", entity: event.entity, vx: sideways, vy: 1 }], state: state }
}

fn on_death(event, state, random) {
    let destroyed = if state.contains("destroyed") { state.destroyed + 1 } else { 1 };
    #{ commands: [#{ op: "objective", key: "aurora:destroyed", value: destroyed }],
       state: #{ destroyed: destroyed } }
}
