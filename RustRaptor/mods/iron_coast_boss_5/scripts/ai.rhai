// Persistent furnace gunship. Each instance has its own serializable clock.
fn is_alive(event) {
    for unit in event.entities {
        if unit.entity == event.entity && unit.health > 0 { return true; }
    }
    false
}

fn initialize(state, key) {
    if !state.contains("units") { state.units = #{}; }
    if !state.units.contains(key) {
        state.units[key] = #{ age: 0, direction: 1, shots: 0 };
    }
    state
}

fn on_spawn(event, state, random) {
    if !is_alive(event) { return #{ commands: [], state: state }; }
    let key = event.entity.to_string();
    state = initialize(state, key);
    // A pilot save contains previous script state; this is a fresh enemy instance.
    state.units[key] = #{ age: 0, direction: 1, shots: 0 };
    #{ commands: [#{ op: "velocity", entity: event.entity, vx: 0, vy: 2 }], state: state }
}

fn on_tick(event, state, random) {
    // A lethal hit earlier in this tick must never create a ghost attack.
    if event.health <= 0 || !is_alive(event) { return #{ commands: [], state: state }; }
    if event.y < 24 {
        return #{ commands: [#{ op: "velocity", entity: event.entity, vx: 0, vy: 2 }], state: state };
    }
    let key = event.entity.to_string();
    state = initialize(state, key);
    let unit = state.units[key];
    unit.age += 1;
    if event.x >= 144 { unit.direction = -1; }
    if event.x <= 80 { unit.direction = 1; }
    let commands = [
        #{ op: "move", entity: event.entity, x: event.x, y: 24 },
        #{ op: "velocity", entity: event.entity, vx: unit.direction, vy: 0 }
    ];
    // 12 ticks of warning before the first muzzle fires, then three shells six
    // ticks apart. The right/center/left lanes leave space to dodge the fan.
    let phase = unit.age % 54;
    if phase == 36 {
        commands.push(#{ op: "play_sound", sound: "iron_coast_boss_5:warning" });
    }
    if phase == 48 {
        commands.push(#{ op: "projectile", weapon: "iron_coast_boss_5:plasma", x: event.x + 24, y: event.y + 55, vx: -2, vy: 4, hostile: true });
        commands.push(#{ op: "play_sound", sound: "iron_coast_boss_5:shot" });
        unit.shots += 1;
    }
    if phase == 0 {
        commands.push(#{ op: "projectile", weapon: "iron_coast_boss_5:mortar", x: event.x + 44, y: event.y + 58, vx: 0, vy: 4, hostile: true });
        commands.push(#{ op: "play_sound", sound: "iron_coast_boss_5:shot" });
        unit.shots += 1;
    }
    if phase == 6 && unit.age > 6 {
        commands.push(#{ op: "projectile", weapon: "iron_coast_boss_5:plasma", x: event.x + 64, y: event.y + 55, vx: 2, vy: 4, hostile: true });
        commands.push(#{ op: "play_sound", sound: "iron_coast_boss_5:shot" });
        unit.shots += 1;
    }
    state.units[key] = unit;
    #{ commands: commands, state: state }
}

fn on_hit(event, state, random) {
    state.hits = if state.contains("hits") { state.hits + 1 } else { 1 };
    #{ commands: [], state: state }
}

fn on_death(event, state, random) {
    if state.contains("units") { state.units.remove(event.entity.to_string()); }
    state.destroyed = if state.contains("destroyed") { state.destroyed + 1 } else { 1 };
    let defeated = if event.objectives.contains("iron_coast_boss_5:defeated") { event.objectives["iron_coast_boss_5:defeated"] + 1 } else { 1 };
    #{ commands: [
        #{ op: "objective", key: "iron_coast_boss_5:defeated", value: defeated },
        #{ op: "effect", x: event.x + 24, y: event.y + 40 },
        #{ op: "effect", x: event.x + 64, y: event.y + 40 },
        #{ op: "play_sound", sound: "iron_coast_boss_5:death" }
    ], state: state }
}
