// Built-in beam projectiles handle the normal volley and collision rules.
// Firing callbacks add audio and counters; impact callbacks add hit visuals.
fn on_fire(event, state, random) {
    let bursts = if state.contains("bursts") { state.bursts % 100000 + 1 } else { 1 };
    let hits = if state.contains("hits") { state.hits } else { 0 };
    let commands = [
        #{ op: "play_sound", sound: "ion_lance:fire" }
    ];
    #{ commands: commands, state: #{ bursts: bursts, hits: hits } }
}

fn on_hit(event, state, random) {
    let bursts = if state.contains("bursts") { state.bursts } else { 0 };
    let hits = if state.contains("hits") { state.hits % 100000 + 1 } else { 1 };
    let commands = [
        #{ op: "play_sound", sound: "ion_lance:impact" },
        #{ op: "effect", x: event.x, y: event.y }
    ];
    #{ commands: commands, state: #{ bursts: bursts, hits: hits } }
}
