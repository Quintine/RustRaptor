// Built-in homing projectiles handle the normal volley and collision rules.
// Callbacks add deterministic visuals, audio and serializable weapon counters.
fn on_fire(event, state, random) {
    let bursts = if state.contains("bursts") { state.bursts % 100000 + 1 } else { 1 };
    let hits = if state.contains("hits") { state.hits } else { 0 };
    let commands = [
        #{ op: "play_sound", sound: "seeker_swarm:fire" },
#{ op: "effect", x: event.x, y: event.y - 3 }
    ];
    #{ commands: commands, state: #{ bursts: bursts, hits: hits } }
}

fn on_hit(event, state, random) {
    let bursts = if state.contains("bursts") { state.bursts } else { 0 };
    let hits = if state.contains("hits") { state.hits % 100000 + 1 } else { 1 };
    let commands = [
        #{ op: "play_sound", sound: "seeker_swarm:impact" },
        #{ op: "effect", x: event.x, y: event.y }
    ];

    // A small fragmentation charge affects at most two nearby surviving enemies.
    let fragments = 0;
    for enemy in event.entities {
        if fragments < 2 && enemy.entity != event.entity && enemy.health > 0
            && abs(enemy.x + enemy.width / 2 - event.x) <= 18
            && abs(enemy.y + enemy.height / 2 - event.y) <= 18 {
            commands.push(#{ op: "damage", entity: enemy.entity, amount: 2 });
            fragments += 1;
        }
    }
    #{ commands: commands, state: #{ bursts: bursts, hits: hits } }
}
