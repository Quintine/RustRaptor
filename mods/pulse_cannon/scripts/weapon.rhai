// Built-in straight projectiles handle the normal volley and collision rules.
// Firing callbacks add audio and counters; impact callbacks add hit visuals.
fn on_fire(event, state, random) {
    let bursts = if state.contains("bursts") { state.bursts % 100000 + 1 } else { 1 };
    let hits = if state.contains("hits") { state.hits } else { 0 };
    let commands = [
        #{ op: "play_sound", sound: "pulse_cannon:fire" }
    ];

    // Every third burst adds a deterministic pair of shallow angled pulses.
    if bursts % 3 == 0 {
        let spread = 1 + random[0] % 2;
        commands.push(#{ op: "projectile", weapon: "pulse_cannon:projectile", x: event.x - 8, y: event.y - 3, vx: -spread, vy: -8 });
        commands.push(#{ op: "projectile", weapon: "pulse_cannon:projectile", x: event.x + 8, y: event.y - 3, vx: spread, vy: -8 });
    }
    #{ commands: commands, state: #{ bursts: bursts, hits: hits } }
}

fn on_hit(event, state, random) {
    let bursts = if state.contains("bursts") { state.bursts } else { 0 };
    let hits = if state.contains("hits") { state.hits % 100000 + 1 } else { 1 };
    let commands = [
        #{ op: "play_sound", sound: "pulse_cannon:impact" },
        #{ op: "effect", x: event.x, y: event.y }
    ];
    #{ commands: commands, state: #{ bursts: bursts, hits: hits } }
}
