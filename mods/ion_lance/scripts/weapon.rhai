// Built-in beam projectiles handle the normal volley and collision rules.
// Firing callbacks add audio and counters; compact two-tick contact arcs are cosmetic.
fn on_fire(event, state, random) {
    // Runtime script state can survive a mission change while tick/entity IDs restart.
    // Reset only cosmetic gates; the existing burst/hit counters keep their semantics.
    let last_fire = if state.contains("last_fire_tick") { state.last_fire_tick } else { -1 };
    let restarted = event.tick <= last_fire
        || (state.contains("feedback_tick") && event.tick <= state.feedback_tick)
        || (state.contains("sound_tick") && event.tick <= state.sound_tick);
    let bursts = if state.contains("bursts") { state.bursts % 100000 + 1 } else { 1 };
    let hits = if state.contains("hits") { state.hits } else { 0 };
    let commands = [
        #{ op: "play_sound", sound: "ion_lance:fire" }
    ];
    #{ commands: commands, state: #{ bursts: bursts, hits: hits,
        // A new volley cannot be the preceding beam's second hit tick. Forget its
        // entity ID, which may be reused in another mission even after a late first shot.
        feedback_projectile: -1,
        feedback_tick: if !restarted && state.contains("feedback_tick") { state.feedback_tick } else { -10 },
        sound_tick: if !restarted && state.contains("sound_tick") { state.sound_tick } else { -10 },
        last_fire_tick: event.tick } }
}

fn on_hit(event, state, random) {
    let bursts = if state.contains("bursts") { state.bursts } else { 0 };
    let hits = if state.contains("hits") { state.hits % 100000 + 1 } else { 1 };
    // One compact contact flash per projectile, not one explosion per beam target.
    // A separate six-tick audio gate also bounds coincident paired/swarm hits.
    let previous_projectile = if state.contains("feedback_projectile") { state.feedback_projectile } else { -1 };
    let previous_tick = if state.contains("feedback_tick") { state.feedback_tick } else { -10 };
    let sound_tick = if state.contains("sound_tick") { state.sound_tick } else { -10 };
    let commands = [];
    let feedback = event.projectile != previous_projectile && event.tick - previous_tick >= 3;
    if feedback {
        commands.push(#{op: "arc", x: event.x - 2, y: event.y + 2,
                        to_x: event.x + 2, to_y: event.y - 2, ticks: 2});
    }
    let audible = event.tick - sound_tick >= 6;
    if audible { commands.push(#{op: "play_sound", sound: "ion_lance:impact"}); }
    #{ commands: commands, state: #{ bursts: bursts, hits: hits,
        feedback_projectile: if feedback { event.projectile } else { previous_projectile },
        feedback_tick: if feedback { event.tick } else { previous_tick },
        sound_tick: if audible { event.tick } else { sound_tick },
        last_fire_tick: if state.contains("last_fire_tick") { state.last_fire_tick } else { -1 } } }
}
