// Native straight projectile supplies the first collision and its 42 damage.
// Penetration is contact-triggered, finite and locked to that projectile's x lane.
fn on_fire(event, state, random) {
    if event.hostile { return #{commands: [], state: state}; }
    let shots = if state.contains("shots") { state.shots % 100000 + 1 } else { 1 };
    let hits = if state.contains("hits") { state.hits } else { 0 };
    #{commands: [#{op: "play_sound", sound: "iron_coast_railburst:fire"}],
      state: #{shots: shots, hits: hits}}
}

fn on_hit(event, state, random) {
    let shots = if state.contains("shots") { state.shots } else { 0 };
    let hits = if state.contains("hits") { state.hits % 100000 + 1 } else { 1 };
    let origin_y = event.y;
    let ground = false;
    for enemy in event.entities {
        if enemy.entity == event.entity {
            origin_y = enemy.y + enemy.height / 2;
            ground = enemy.ground;
        }
    }
    let kind = if ground { "small_ground" } else { "small_air" };
    let commands = [#{op: "play_sound", sound: "iron_coast_railburst:impact"},
                    #{op: "effect", kind: kind, x: event.x, y: event.y}];
    let struck = [event.entity];
    let previous_y = origin_y;
    let damages = [32, 22];
    for hop in 0..2 {
        let chosen = #{};
        let nearest = 1000000;
        for enemy in event.entities {
            let cx = enemy.x + enemy.width / 2;
            let cy = enemy.y + enemy.height / 2;
            if enemy.health <= 0 || struck.contains(enemy.entity)
                || cx < 0 || cx >= 320 || cy < 0 || cy >= 200 { continue; }
            let distance = previous_y - cy;
            if abs(cx - event.x) <= 12 && distance > 0
                && origin_y - cy <= 160 && distance < nearest {
                chosen = #{entity: enemy.entity, x: cx, y: cy, ground: enemy.ground};
                nearest = distance;
            }
        }
        if !chosen.contains("entity") { break; }
        commands.push(#{op: "damage", entity: chosen.entity, amount: damages[hop]});
        let impact = if chosen.ground { "small_ground" } else { "small_air" };
        commands.push(#{op: "effect", kind: impact, x: chosen.x, y: chosen.y});
        struck.push(chosen.entity);
        previous_y = chosen.y;
        hits = hits % 100000 + 1;
    }
    #{commands: commands, state: #{shots: shots, hits: hits}}
}
