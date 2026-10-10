fn is_alive(event) {
    for unit in event.entities {
        if unit.entity == event.entity && unit.health > 0 { return true; }
    }
    false
}

// Every live boss owns its own clock/direction. A fresh spawn clears reused IDs
// from previous sorties; no wall clock or rendering state enters the simulation.
fn on_spawn(event, state, random) {
    if !state.contains("units") { state.units = #{}; }
    if !state.contains("dead") { state.dead = #{}; }
    let key = event.entity.to_string();
    // A queued spawn still starts a new lifecycle if advance already killed it.
    // Clear saved guards first so its following death is counted for this sortie.
    state.dead.remove(key);
    state.units.remove(key);
    if !is_alive(event) { return #{ commands: [], state: state }; }
    state.units[key] = #{ direction: 1, age: 0 };
    #{ commands: [#{ op: "velocity", entity: event.entity, vx: 0, vy: 2 }], state: state }
}

fn on_tick(event, state, random) {
    if event.health <= 0 || !is_alive(event) { return #{ commands: [], state: state }; }
    let key = event.entity.to_string();
    if !state.contains("units") { state.units = #{}; }
    if !state.units.contains(key) { state.units[key] = #{ direction: 1, age: 0 }; }
    if event.y < 24 {
        return #{ commands: [#{ op: "velocity", entity: event.entity, vx: 0, vy: 2 }], state: state };
    }
    let unit = state.units[key];
    if event.x >= 144 { unit.direction = -1; }
    if event.x <= 80 { unit.direction = 1; }
    let phase = unit.age % 54;
    let commands = [#{ op: "move", entity: event.entity, x: event.x, y: 24 }];
    // Twelve ticks of a visible pause plus a two-note alarm telegraph each salvo.
    commands.push(#{ op: "velocity", entity: event.entity, vx: if phase < 12 { 0 } else { unit.direction }, vy: 0 });
    if phase == 0 { commands.push(#{ op: "play_sound", sound: "iron_coast_boss_4:warning" }); }
    if phase == 12 {
        let left_active = (unit.age / 54) % 2 == 0;
        // The outer shells come from both batteries; the third shell alternates.
        commands.push(#{ op: "projectile", weapon: "iron_coast_boss_4:projectile", x: event.x + 24, y: 80, vx: -1, vy: 4, hostile: true });
        commands.push(#{ op: "projectile", weapon: "iron_coast_boss_4:projectile", x: event.x + 72, y: 80, vx: 1, vy: 4, hostile: true });
        commands.push(#{ op: "projectile", weapon: "iron_coast_boss_4:projectile", x: event.x + if left_active { 28 } else { 68 }, y: 80, vx: 0, vy: 4, hostile: true });
        commands.push(#{ op: "play_sound", sound: "iron_coast_boss_4:shot" });
        state.salvos = if state.contains("salvos") { state.salvos + 1 } else { 1 };
    }
    unit.age += 1;
    state.units[key] = unit;
    #{ commands: commands, state: state }
}

fn on_death(event, state, random) {
    let key = event.entity.to_string();
    if !state.contains("dead") { state.dead = #{}; }
    if state.dead.contains(key) { return #{ commands: [], state: state }; }
    state.dead[key] = true;
    if state.contains("units") { state.units.remove(key); }
    let defeated = if event.objectives.contains("iron_coast_boss_4:defeated") { event.objectives["iron_coast_boss_4:defeated"] + 1 } else { 1 };
    #{ commands: [
        #{ op: "objective", key: "iron_coast_boss_4:defeated", value: defeated },
        #{ op: "effect", x: event.x + 24, y: event.y + 40 },
        #{ op: "effect", x: event.x + 72, y: event.y + 40 },
        #{ op: "play_sound", sound: "iron_coast_boss_4:death" }
    ], state: state }
}
