// Authored attack clocks, not a legacy selector. Art, sound and kill rewards are unchanged.
// The central actor snapshot gives O(1) current-entity access. A legacy-only scan
// remains for dispatchers lacking BOTH actor and difficulty; no full event helper.
// Current dispatch supplies BOTH actor and difficulty. Read compact properties
// directly: native map methods recursively validate the entire event payload.
// Only an older dispatch with neither field enters the legacy array fallback.
fn legacy_actor(entities, id) {
    for unit in entities { if unit.entity == id { return unit; } }
    ()
}
fn difficulty(value) {
    if type_of(value) == "i64" && value >= 0 && value <= 3 { return value; }
    1
}
fn ready(state) {
    if !state.contains("units") { state.units = #{}; }
    if !state.contains("order") { state.order = []; }
    if !state.contains("dead") { state.dead = #{}; }
    if !state.contains("dead_order") { state.dead_order = []; }
    state
}
fn bump(state, name) {
    if !state.contains(name) { return 1; }
    if state[name] < 1000000000 { state[name] + 1 } else { state[name] }
}
fn visible(a, player) {
    a.x >= 0 && a.x + a.width <= 320 && a.y >= 4 && a.y + a.height <= 174 && a.y + a.height < player.y - 8
}
fn aimed(a, player, speed) {
    let dx = player.x + 16 - (a.x + a.width / 2);
    let dy = player.y + 16 - (a.y + a.height);
    let ax = if dx < 0 {-dx} else {dx};
    let norm = if ax > dy {ax} else {dy};
    if norm <= 0 { return [0,speed]; }
    let vx = dx * speed / norm;
    let vy = dy * speed / norm;
    [vx, if vy < 1 {1} else {vy}]
}
fn on_spawn(event, state, random) {
    state = ready(state);
    let key = event.entity.to_string();
    // IDs restart with missions. Replace this lifecycle even if the callback is stale.
    state.units.remove(key); state.dead.remove(key);
    let order = []; for old in state.order { if old != key { order.push(old); } }
    state.order = order;
    let dead_order = []; for old in state.dead_order { if old != key { dead_order.push(old); } }
    state.dead_order = dead_order;
    let a = event.actor;
    if a == () && event.difficulty == () { a = legacy_actor(event.entities,event.entity); }
    if a == () || a.health <= 0 { return #{commands:[],state:state}; }
    // Constant bound; pruning is at birth/death, never an all-entity tick sweep.
    if state.order.len() >= 64 { let old = state.order.remove(0); state.units.remove(old); }
    state.order.push(key);
    state.units[key] = #{age:0, sign:if a.x < 148 {1} else {-1}, cooldown:18 + event.entity % 19, remaining:0, wait:0, aim_x:0, aim_y:3};
    #{commands:[#{op:"velocity",entity:event.entity,vx:0,vy:3}],state:state}
}
fn on_tick(event, state, random) {
    state = ready(state);
    let key = event.entity.to_string();
    let a = event.actor;
    if a == () && event.difficulty == () { a = legacy_actor(event.entities,event.entity); }
    if a == () || a.health <= 0 { state.units.remove(key); return #{commands:[],state:state}; }
    if !state.units.contains(key) { return #{commands:[],state:state}; }
    let unit = state.units[key];
    unit.age = if unit.age < 1000000000 {unit.age + 1} else {unit.age};
    let commands = [];
    if a.y > 224 || a.x < -32 || a.x > 328 {
        state.units.remove(key);
        return #{commands:[#{op:"despawn",entity:event.entity}],state:state};
    }
    // Straight entry, diagonal firing pass, brief level break, then a committed exit.
    let vx = if unit.age < 16 {0} else if unit.age < 56 {unit.sign * 2} else if unit.age < 76 {0} else {unit.sign};
    let vy = if unit.age < 16 {3} else if unit.age < 56 {1} else if unit.age < 76 {2} else {3};
    if unit.age < 76 && a.x < 8 {vx = 2;}
    if unit.age < 76 && a.x > 288 {vx = -2;}
    commands.push(#{op:"velocity",entity:event.entity,vx:vx,vy:vy});
    let d = difficulty(event.difficulty);
    let period = [64, 54, 46, 40][d];
    let burst = [1, 1, 2, 2][d];
    let windup = [9, 8, 7, 7][d];
    let speed = [3, 4, 4, 5][d];
    if unit.cooldown > 0 { unit.cooldown -= 1; }
    let can_fire = visible(a,event.player) && unit.age >= 12;
    if !can_fire { unit.remaining = 0; unit.wait = 0; }
    if can_fire && unit.remaining == 0 && unit.cooldown == 0 {
        let aim = aimed(a,event.player,speed);
        unit.aim_x = aim[0]; unit.aim_y = aim[1];
        // This tick consumes one counter step; retain the full documented warning interval.
        unit.remaining = burst; unit.wait = windup + 1; unit.cooldown = period;
        // No oversized flare: the visible approach/hold is the light-unit telegraph.
    }
    if unit.wait > 0 { unit.wait -= 1; }
    if can_fire && unit.remaining > 0 && unit.wait == 0 {
        // Aim is frozen at the start of this short salvo: no homing correction.
        commands.push(#{op:"projectile",weapon:"iron_coast_scout:projectile",x:a.x + a.width / 2 - 6 / 2,y:a.y + a.height - 6 / 2,vx:unit.aim_x,vy:unit.aim_y,hostile:true});
        commands.push(#{op:"play_sound",sound:"iron_coast_scout:shot"});
        unit.remaining -= 1; unit.wait = 5;
        state.shots = bump(state,"shots");
    }
    state.units[key] = unit;
    #{commands:commands,state:state}
}
fn on_hit(event, state, random) {
    state.hits = bump(state,"hits");
    #{commands:[],state:state}
}
fn on_death(event, state, random) {
    state = ready(state);
    let key = event.entity.to_string();
    // Only the engine's actual death hook advances required-target counters.
    // Natural air exits never enter this path and never grant rewards/objectives.
    let a = event.actor;
    if a == () && event.difficulty == () { a = legacy_actor(event.entities,event.entity); }
    if (a != () && a.health > 0) || state.dead.contains(key) { return #{commands:[],state:state}; }
    if state.dead_order.len() >= 64 { let old = state.dead_order.remove(0); state.dead.remove(old); }
    state.dead[key] = true; state.dead_order.push(key); state.units.remove(key);
    state.destroyed = bump(state,"destroyed");
    let defeated = if event.objectives.contains("iron_coast_scout:defeated") {event.objectives["iron_coast_scout:defeated"] + 1} else {1};
    #{commands:[#{op:"objective",key:"iron_coast_scout:defeated",value:defeated},#{op:"play_sound",sound:"iron_coast_scout:death"}],state:state}
}
