// Damage is collision-triggered. Empty space, aircraft and inactive equipment
// never start a blast. Native targeting handles the primary ground collision.
fn on_fire(event, state, random) {
    if event.hostile { return #{commands: [], state: state}; }
    let shots = if state.contains("shots") { state.shots % 100000 + 1 } else { 1 };
    let hits = if state.contains("hits") { state.hits } else { 0 };
    #{commands: [#{op: "play_sound", sound: "iron_coast_depth_charge:fire"}],
      state: #{shots: shots, hits: hits}}
}

fn on_hit(event, state, random) {
    let shots = if state.contains("shots") { state.shots } else { 0 };
    let hits = if state.contains("hits") { state.hits % 100000 + 1 } else { 1 };
    let center_x = event.x;
    let center_y = event.y;
    for enemy in event.entities {
        if enemy.entity == event.entity {
            center_x = enemy.x + enemy.width / 2;
            center_y = enemy.y + enemy.height / 2;
        }
    }
    let commands = [#{op: "play_sound", sound: "iron_coast_depth_charge:impact"},
                    #{op: "effect", kind: "small_air", x: center_x, y: center_y}];
    let struck = [event.entity];
    for neighbor in 0..3 {
        let chosen = #{};
        let nearest = 1000000;
        for enemy in event.entities {
            let cx = enemy.x + enemy.width / 2;
            let cy = enemy.y + enemy.height / 2;
            if !enemy.ground || enemy.health <= 0 || struck.contains(enemy.entity)
                || cx < 0 || cx >= 320 || cy < 0 || cy >= 200 { continue; }
            let dx = cx - center_x;
            let dy = cy - center_y;
            let distance = dx * dx + dy * dy;
            if distance <= 36 * 36 && distance < nearest {
                chosen = #{entity: enemy.entity};
                nearest = distance;
            }
        }
        if !chosen.contains("entity") { break; }
        let damage = if nearest <= 16 * 16 { 36 } else { 20 };
        commands.push(#{op: "damage", entity: chosen.entity, amount: damage});
        struck.push(chosen.entity);
        hits = hits % 100000 + 1;
    }
    #{commands: commands, state: #{shots: shots, hits: hits}}
}
