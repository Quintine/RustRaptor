// The scripted discharge uses only public snapshots and checked API commands.
// A narrow forward acquisition lane preserves aiming; later hops may go sideways.
fn on_fire(event, state, random) {
    if event.hostile {
        return #{ commands: [], state: state };
    }
    let bursts = if state.contains("bursts") { state.bursts % 100000 + 1 } else { 1 };
    let hits = if state.contains("hits") { state.hits } else { 0 };
    let commands = [#{ op: "play_sound", sound: "lightning_cannon:fire" }];
    let struck = [];
    let from_x = event.x;
    let from_y = event.y;
    let damages = [32, 20, 12, 8];

    for hop in 0..4 {
        let selected = #{};
        let nearest = 1000000;
        for enemy in event.entities {
            let cx = enemy.x + enemy.width / 2;
            let cy = enemy.y + enemy.height / 2;
            if enemy.health <= 0 || struck.contains(enemy.entity)
                || cx < 0 || cx >= 320 || cy < 0 || cy >= 200 {
                continue;
            }
            let dx = cx - from_x;
            let dy = cy - from_y;
            let distance = dx * dx + dy * dy;
            let reachable = if hop == 0 {
                abs(dx) <= 36 && dy < 0 && distance <= 180 * 180
            } else {
                distance <= 48 * 48
            };
            // Entity order provides a stable tie break for equally near targets.
            if reachable && distance < nearest {
                selected = #{ entity: enemy.entity, x: cx, y: cy };
                nearest = distance;
            }
        }
        if !selected.contains("entity") { break; }
        commands.push(#{ op: "arc", x: from_x, y: from_y,
                         to_x: selected.x, to_y: selected.y, ticks: 4 });
        commands.push(#{ op: "damage", entity: selected.entity, amount: damages[hop] });
        struck.push(selected.entity);
        from_x = selected.x;
        from_y = selected.y;
        hits = hits % 100000 + 1;
    }
    if struck.len() > 0 {
        commands.push(#{ op: "play_sound", sound: "lightning_cannon:impact" });
    } else {
        // A missed shot remains visible without spawning a damaging carrier.
        commands.push(#{ op: "arc", x: event.x, y: event.y,
                         to_x: event.x, to_y: event.y - 180, ticks: 3 });
    }
    #{ commands: commands, state: #{ bursts: bursts, hits: hits } }
}
