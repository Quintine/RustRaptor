// This is an ordinary non-special weapon: it runs only while Fire is held.
// Measure range to the nearest point of an enemy hull, not its center, so large
// ships can be zapped at the edge too. The reach is only 12px past our 32px hull.
fn on_fire(event, state, random) {
    if event.hostile {
        return #{ commands: [], state: state };
    }
    let bursts = if state.contains("bursts") { state.bursts % 100000 + 1 } else { 1 };
    let hits = if state.contains("hits") { state.hits } else { 0 };
    let commands = [];
    let struck = [];
    let from_x = event.player.x + 16;
    let from_y = event.player.y + 16;

    // An electric halo just outside the hull follows the ship throughout the
    // recharge. Both endpoints use the public arc anchoring API; it is visual
    // only, so even an empty pulse still lights the ring without playing audio.
    let ring = [[19, 0], [18, 7], [13, 13], [7, 18], [0, 19], [-7, 18],
                [-13, 13], [-18, 7], [-19, 0], [-18, -7], [-13, -13],
                [-7, -18], [0, -19], [7, -18], [13, -13], [18, -7]];
    for i in 0..ring.len() {
        let a = ring[i];
        let b = ring[(i + 1) % ring.len()];
        commands.push(#{ op: "arc", x: from_x + a[0], y: from_y + a[1],
                         to_x: from_x + b[0], to_y: from_y + b[1],
                         anchor: 0, to_anchor: 0, ticks: 8 });
    }

    // Bound each pulse's work and sound: at most four close airborne ships.
    for target in 0..4 {
        let selected = #{};
        let nearest = 1000000;
        for enemy in event.entities {
            if enemy.health <= 0 || enemy.ground || struck.contains(enemy.entity) {
                continue;
            }
            let x = max(enemy.x, min(from_x, enemy.x + enemy.width - 1));
            let y = max(enemy.y, min(from_y, enemy.y + enemy.height - 1));
            if x < 0 || x >= 320 || y < 0 || y >= 200 { continue; }
            let dx = x - from_x;
            let dy = y - from_y;
            let distance = dx * dx + dy * dy;
            if distance <= 28 * 28 && distance < nearest {
                selected = #{ entity: enemy.entity, x: x, y: y };
                nearest = distance;
            }
        }
        if !selected.contains("entity") { break; }
        // Start at the halo point facing this hull, not at the player's center.
        let dx = selected.x - from_x;
        let dy = selected.y - from_y;
        let origin = ring[0];
        let best = -1000000;
        for point in ring {
            let facing = point[0] * dx + point[1] * dy;
            if facing > best { best = facing; origin = point; }
        }
        commands.push(#{ op: "arc", x: from_x + origin[0], y: from_y + origin[1],
                         to_x: selected.x, to_y: selected.y,
                         anchor: 0, to_anchor: selected.entity, ticks: 3 });
        commands.push(#{ op: "damage", entity: selected.entity, amount: 2 });
        struck.push(selected.entity);
        hits = hits % 100000 + 1;
    }
    if struck.len() > 0 {
        commands.push(#{ op: "play_sound", sound: "lightning_shield:fire" });
        commands.push(#{ op: "play_sound", sound: "lightning_shield:impact" });
    }
    #{ commands: commands, state: #{ bursts: bursts, hits: hits } }
}
