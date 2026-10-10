// The normal centre projectile is emitted by the engine. Add two angled pulses.
fn on_fire(event, state, random) {
    let shots = if state.contains("shots") { state.shots + 1 } else { 1 };
    let spread = 1 + random[0] % 2;
    #{ commands: [
        #{ op: "projectile", weapon: "aurora:pulse_projectile", x: event.x - 6, y: event.y, vx: -spread, vy: -8 },
        #{ op: "projectile", weapon: "aurora:pulse_projectile", x: event.x + 6, y: event.y, vx: spread, vy: -8 }
    ], state: #{ shots: shots } }
}

fn on_hit(event, state, random) {
    #{ commands: [#{ op: "effect", x: event.x, y: event.y }], state: state }
}
