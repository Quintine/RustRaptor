// Each boss has its own direction, cannon clock and alternating barrel.
// No wall-clock time or global tick modulo affects restored behavior.
fn is_alive(event) {
    for unit in event.entities {
        if unit.entity == event.entity && unit.health > 0 { return true; }
    }
    false
}

fn on_spawn(event, state, random) {
    if !state.contains("units") { state.units = #{}; }
    if !state.contains("dead") { state.dead = #{}; }
    let key = event.entity.to_string();
    state.units[key] = #{direction: 1, clock: 0, side: 0};
    state.dead.remove(key);
    // IDs restart on replay. Even a spawn killed during advance must clear
    // its previous life's death guard before the queued death callback runs.
    if !is_alive(event) { return #{commands: [], state: state}; }
    #{commands: [#{op: "velocity", entity: event.entity, vx: 0, vy: 2}], state: state}
}

fn on_tick(event, state, random) {
    if event.health <= 0 || !is_alive(event) { return #{commands: [], state: state}; }
    if event.y < 24 {
        return #{commands: [#{op: "velocity", entity: event.entity, vx: 0, vy: 2}], state: state};
    }
    let key = event.entity.to_string();
    if !state.contains("units") { state.units = #{}; }
    let unit = if state.units.contains(key) { state.units[key] } else {#{direction: 1, clock: 0, side: 0}};
    if event.x >= 144 { unit.direction = -1; }
    if event.x <= 80 { unit.direction = 1; }
    unit.clock = (unit.clock + 1) % 54;
    let commands = [
        #{op: "move", entity: event.entity, x: event.x, y: 24},
        #{op: "velocity", entity: event.entity, vx: unit.direction, vy: 0}
    ];
    // Audible warning lasts nine simulation steps before each side fires.
    if unit.clock == 45 {
        commands.push(#{op: "play_sound", sound: "iron_coast_boss_3:warning"});
    }
    if unit.clock == 0 {
        let muzzle = if unit.side == 0 {35} else {61};
        let inward = if unit.side == 0 {1} else {-1};
        commands.push(#{op: "projectile", weapon: "iron_coast_boss_3:projectile", x: event.x + muzzle, y: event.y + 54, vx: 0, vy: 4, hostile: true});
        commands.push(#{op: "projectile", weapon: "iron_coast_boss_3:projectile", x: event.x + muzzle, y: event.y + 54, vx: inward, vy: 4, hostile: true});
        commands.push(#{op: "play_sound", sound: "iron_coast_boss_3:shot"});
        unit.side = 1 - unit.side;
        state.shots = if state.contains("shots") {state.shots + 1} else {1};
    }
    state.units[key] = unit;
    #{commands: commands, state: state}
}

fn on_hit(event, state, random) {
    state.hits = if state.contains("hits") {state.hits + 1} else {1};
    #{commands: [], state: state}
}

fn on_death(event, state, random) {
    let key = event.entity.to_string();
    if !state.contains("dead") { state.dead = #{}; }
    if state.dead.contains(key) { return #{commands: [], state: state}; }
    state.dead[key] = true;
    if state.contains("units") { state.units.remove(key); }
    state.destroyed = if state.contains("destroyed") {state.destroyed + 1} else {1};
    let defeated = if event.objectives.contains("iron_coast_boss_3:defeated") {event.objectives["iron_coast_boss_3:defeated"] + 1} else {1};
    #{commands: [
        #{op: "objective", key: "iron_coast_boss_3:defeated", value: defeated},
        #{op: "effect", x: event.x + 35, y: event.y + 48},
        #{op: "effect", x: event.x + 61, y: event.y + 48},
        #{op: "play_sound", sound: "iron_coast_boss_3:death"}
    ], state: state}
}
