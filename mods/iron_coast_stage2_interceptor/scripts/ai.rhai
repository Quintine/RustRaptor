// Integer-only per-entity clocks. No spawns, equipment grants or direct damage.
// The engine owns collision, one kill reward, projectile retirement and explosions.
fn alive(event) {
    for unit in event.entities {
        if unit.entity == event.entity && unit.health > 0 { return true; }
    }
    false
}
// Firing events use muzzle coordinates; visibility must use the real canvas.
fn ready_to_fire(event) {
    for unit in event.entities {
        if unit.entity == event.entity {
            return unit.health > 0 && unit.x >= 0 && unit.x + unit.width <= 320 && unit.y >= 0 && unit.y + unit.height <= 180 && unit.y + unit.height < event.player.y - 8;
        }
    }
    false
}
fn fresh(random) { #{clock:0, sign: if random[0] % 2 == 0 {1} else {-1}, remaining:0, wait:0, aim_x:0, aim_y:3} }
fn ready(state) {
    if !state.contains("units") { state.units = #{}; }
    if !state.contains("dead") { state.dead = #{}; }
    if !state.contains("dead_order") { state.dead_order = []; }
    state
}
fn tidy(event, state) {
    state = ready(state);
    let retained = #{};
    for unit in event.entities {
        let key = unit.entity.to_string();
        if unit.definition == "iron_coast_stage2_interceptor:unit" && unit.health > 0 && state.units.contains(key) && retained.len() < 128 {
            retained[key] = state.units[key];
        }
    }
    state.units = retained;
    state
}
fn counter(state, key) {
    if !state.contains(key) {return 1;}
    if state[key] >= 1000000000 {return 1000000000;}
    state[key] + 1
}
fn clamp_speed(value) { if value < -3 {-3} else if value > 3 {3} else {value} }
fn aimed(event) {
    let dx = event.player.x + 16 - event.x;
    let dy = event.player.y + 16 - event.y;
    let ax = if dx < 0 {-dx} else {dx};
    let ay = if dy < 0 {-dy} else {dy};
    let norm = if ax > ay {ax} else {ay};
    if norm == 0 {return [0,3];}
    let vy = dy * 3 / norm;
    [clamp_speed(dx * 3 / norm), if vy < 1 {1} else {vy}]
}
fn on_spawn(event, state, random) {
    state = tidy(event,state);
    let key = event.entity.to_string();
    // Entity IDs restart with each mission. Clear the old lifecycle guard even
    // when a spawn was already killed before queued callbacks are dispatched.
    state.dead.remove(key);
    let keep = [];
    for old in state.dead_order { if old != key {keep.push(old);} }
    state.dead_order = keep;
    if !alive(event) {return #{commands:[],state:state};}
    if state.units.len() >= 128 {return #{commands:[],state:state};}
    let unit = fresh(random);
    state.units[key] = unit;
    #{commands:[#{op:"velocity",entity:event.entity,vx:unit.sign,vy:1}],state:state}
}
fn on_fire(event, state, random) {
    state = ready(state);
    if !ready_to_fire(event) || event.x < 0 || event.x >= 320 || event.y < 24 || event.y > 180 || event.y >= event.player.y - 8 {
        return #{commands:[],state:state};
    }
    let key = event.entity.to_string();
    if !state.units.contains(key) {return #{commands:[],state:state};}
    let unit = state.units[key];
    let aim = aimed(event);
    unit.remaining = 3; unit.wait = 0;
    unit.aim_x = aim[0]; unit.aim_y = aim[1];
    state.units[key] = unit;
    #{commands:[],state:state}
}
fn on_tick(event, state, random) {
    state = ready(state);
    // Stagger periodic pruning to keep dense waves within the shared script budget.
    if (event.tick + event.entity) % 32 == 0 { state = tidy(event,state); }
    if event.health <= 0 || !alive(event) {return #{commands:[],state:state};}
    let key = event.entity.to_string();
    if !state.units.contains(key) {return #{commands:[],state:state};}
    let unit = state.units[key];
    unit.clock = (unit.clock + 1) % 96;
    let phase = unit.clock / 12;
    let route = [2,1,0,-1,-2,-1,0,1];
    let sideways = route[phase] * unit.sign;
    let down = if unit.clock % 48 < 12 {2} else {1};
    if event.x <= 8 {sideways = 1;}
    if event.x >= 320 - 24 - 8 {sideways = -1;}
    let commands = [#{op:"velocity",entity:event.entity,vx:sideways,vy:down}];
    // Never fire from an invisible/dead unit, or backwards at a player it passed.
    if event.x < 0 || event.x + 24 > 320 || event.y < 0 || event.y + 24 > 180 || event.y + 24 >= event.player.y - 8 {
        unit.remaining = 0;
    }
    if unit.wait > 0 {unit.wait -= 1;}
    if unit.remaining > 0 && unit.wait == 0 {
        commands.push(#{op:"projectile",weapon:"iron_coast_stage2_interceptor:projectile",x:event.x+8,y:event.y+22,vx:unit.aim_x,vy:unit.aim_y,hostile:true});
        unit.remaining -= 1;unit.wait=4;
        commands.push(#{op:"play_sound",sound:"iron_coast_stage2_interceptor:shot"});
        state.shots = counter(state,"shots");
    }
    state.units[key] = unit;
    #{commands:commands,state:state}
}
fn on_hit(event, state, random) {
    state.hits = counter(state,"hits");
    #{commands:[],state:state}
}
fn on_death(event, state, random) {
    state = tidy(event,state);
    let key = event.entity.to_string();
    if alive(event) || state.dead.contains(key) {return #{commands:[],state:state};}
    if state.dead_order.len() >= 128 {let oldest=state.dead_order.remove(0);state.dead.remove(oldest);}
    state.dead[key] = true; state.dead_order.push(key); state.units.remove(key);
    state.destroyed = counter(state,"destroyed");
    let defeated = if event.objectives.contains("iron_coast_stage2_interceptor:defeated") {event.objectives["iron_coast_stage2_interceptor:defeated"] + 1} else {1};
    #{commands:[#{op:"objective",key:"iron_coast_stage2_interceptor:defeated",value:defeated},#{op:"play_sound",sound:"iron_coast_stage2_interceptor:death"}],state:state}
}
