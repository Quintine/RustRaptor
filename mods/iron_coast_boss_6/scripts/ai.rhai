// Private 1.0.1 retune: per-entity telegraph, locked lanes and recovery.
// No legacy selectors. Old persisted counters and cursor fields are retained.
fn live_actor(event) {
    // Current API refreshes actor after earlier committed callbacks. An explicit
    // absent/dead actor must not fall back to a stale queued event payload.
    if event.contains("actor") {
        if type_of(event.actor) == "map" { return event.actor; }
        return #{health:0,x:0,y:0};
    }
    // Historical API fallback only: its entities snapshot is also current.
    for enemy in event.entities { if enemy.entity == event.entity { return enemy; } }
    #{health:0,x:0,y:0}
}
fn settings(event) {
    // API v1 fallback is Training until the centrally supplied field is present.
    if event.contains("difficulty") { return event.difficulty; }
    0
}
fn cursor(event, state, key) {
    let unit = if state.contains("units") && state.units.contains(key) {state.units[key]} else {#{}};
    if !unit.contains("direction") { unit.direction = if state.contains("directions") && state.directions.contains(key) {state.directions[key]} else {1}; }
    if !unit.contains("age") { unit.age = if state.contains("ages") && state.ages.contains(key) {state.ages[key]} else {0}; }
    if !unit.contains("clock") { unit.clock = 0; }
    if !unit.contains("volley") { unit.volley = if unit.contains("shots") {unit.shots} else {0}; }
    if !unit.contains("phase") { unit.phase = 0; }
    if !unit.contains("max_health") { unit.max_health = live_actor(event).health; }
    if unit.max_health < 1 { unit.max_health = 1; }
    if !unit.contains("lock_x") { unit.lock_x = event.player.x + 16; }
    if !unit.contains("pattern") { unit.pattern = unit.volley % 3; }
    unit
}
fn on_spawn(event, state, random) {
    let key = event.entity.to_string();
    if !state.contains("units") { state.units = #{}; }
    if !state.contains("dead") { state.dead = #{}; }
    state.dead.remove(key);
    if state.contains("dead_order") {let keep=[];for old in state.dead_order {if old!=key {keep.push(old);}}state.dead_order=keep;}
    // Register even a queued spawn killed before this callback: its death counts.
    state.units[key] = #{direction:1,age:0,clock:0,volley:0,phase:0,max_health:live_actor(event).health,lock_x:event.player.x+16,pattern:0};
    if live_actor(event).health <= 0 { return #{commands:[],state:state}; }
    #{commands:[#{op:"velocity",entity:event.entity,vx:0,vy:2}],state:state}
}
fn on_tick(event, state, random) {
    let actor=live_actor(event);
    if actor.health <= 0 { return #{commands:[],state:state}; }
    let key = event.entity.to_string();
    if !state.contains("units") { state.units = #{}; }
    let unit = cursor(event,state,key);
    if actor.y < 12 {
        state.units[key] = unit;
        return #{commands:[#{op:"velocity",entity:event.entity,vx:0,vy:2}],state:state};
    }
    let difficulty = settings(event);
    unit.difficulty=difficulty;
    let phase = if actor.health*3 <= unit.max_health {2} else if actor.health*3 <= unit.max_health*2 {1} else {0};
    // A health transition always restarts the full warning; it cannot skip ahead
    // to an untelegraphed salvo when the period changes.
    if phase != unit.phase { unit.phase=phase; unit.clock=0; }
    let period = 90 - difficulty*6 - phase*6;
    let lead = 18-difficulty*2;
    let speed = 3 + if difficulty >= 2 {1} else {0};
    if unit.clock >= period { unit.clock=0; }
    let width=108;
    let left=actor.x+37;
    let center=actor.x+width/2;
    let right=actor.x+71;
    let muzzle_y=actor.y+61;
    let center_y=actor.y+67;
    let commands=[];
    if unit.clock == 0 {
        unit.lock_x=event.player.x+16;
        unit.pattern=(unit.volley+phase)%3;
        commands.push(#{op:"play_sound",sound:"iron_coast_boss_6:warning"});
        if unit.pattern == 2 {commands.push(#{op:"arc",x:center-4,y:center_y,to_x:center+4,to_y:center_y,ticks:8,anchor:event.entity,to_anchor:event.entity});}
        else {
            commands.push(#{op:"arc",x:left-4,y:muzzle_y,to_x:left+4,to_y:muzzle_y,ticks:8,anchor:event.entity,to_anchor:event.entity});
            commands.push(#{op:"arc",x:right-4,y:muzzle_y,to_x:right+4,to_y:muzzle_y,ticks:8,anchor:event.entity,to_anchor:event.entity});
        }
        state.warnings=if state.contains("warnings") {state.warnings+1} else {1};
    }
    let aim=if unit.lock_x<center-24 {-1} else if unit.lock_x>center+24 {1} else {0};
    if unit.clock == lead {
        if unit.pattern == 0 { commands.push(#{op:"projectile",weapon:"iron_coast_boss_6:projectile",x:left,y:muzzle_y,vx:-1,vy:speed,hostile:true}); commands.push(#{op:"projectile",weapon:"iron_coast_boss_6:projectile",x:center,y:center_y,vx:0,vy:speed,hostile:true}); commands.push(#{op:"projectile",weapon:"iron_coast_boss_6:projectile",x:right,y:muzzle_y,vx:1,vy:speed,hostile:true}); }
        else if unit.pattern == 1 { commands.push(#{op:"projectile",weapon:"iron_coast_boss_6:projectile",x:left,y:muzzle_y,vx:0,vy:speed,hostile:true}); commands.push(#{op:"projectile",weapon:"iron_coast_boss_6:projectile",x:right,y:muzzle_y,vx:0,vy:speed,hostile:true}); }
        else { commands.push(#{op:"projectile",weapon:"iron_coast_boss_6:projectile",x:center,y:center_y,vx:aim,vy:speed,hostile:true}); }
    }
    if unit.clock == lead+8 && unit.pattern == 2 && difficulty >= 1 {
        let active = if unit.volley % 2 == 0 {left} else {right};
        commands.push(#{op:"projectile",weapon:"iron_coast_boss_6:projectile",x:active,y:muzzle_y,vx:0,vy:speed,hostile:true});
    }
    if unit.clock == lead {
        commands.push(#{op:"play_sound",sound:"iron_coast_boss_6:shot"});
        state.shots=if state.contains("shots") {state.shots+1} else {1};
    }
    // Warning and short burst are stationary hit windows; reposition only in
    // recovery. The ship never leaves the forward-gun reach or dives into player.
    let resting=unit.clock <= lead+8;
    if actor.x >= 320-width-32 {unit.direction=-1;}
    if actor.x <= 32 {unit.direction=1;}
    let vx=if resting {0} else {unit.direction*(1+if difficulty>=2 {1} else {0})};
    let triangle=if (unit.age/12)%8<4 {(unit.age/12)%8} else {8-(unit.age/12)%8};
    let y=if resting {actor.y} else {12+if phase>0 {triangle*10/4} else {0}};
    commands.push(#{op:"move",entity:event.entity,x:actor.x,y:y});
    commands.push(#{op:"velocity",entity:event.entity,vx:vx,vy:0});

    if unit.clock == lead+8 {unit.volley+=1;}
    unit.age+=1;
    unit.clock=(unit.clock+1)%period;
    state.units[key]=unit;
    #{commands:commands,state:state}
}
fn on_hit(event,state,random) {
    state.hits=if state.contains("hits") {state.hits+1} else {1};
    #{commands:[],state:state}
}
fn on_death(event,state,random) {
    let key=event.entity.to_string();
    if !state.contains("dead") {state.dead=#{};}
    if state.dead.contains(key) {return #{commands:[],state:state};}
    state.dead[key]=true;
    if !state.contains("dead_order") {state.dead_order=[];}
    state.dead_order.push(key);
    if state.dead_order.len()>32 {let old=state.dead_order.remove(0);state.dead.remove(old);}
    if state.contains("units") {state.units.remove(key);}
    if state.contains("directions") {state.directions.remove(key);}
    if state.contains("ages") {state.ages.remove(key);}
    state.destroyed=if state.contains("destroyed") {state.destroyed+1} else {1};
    let defeated=if event.objectives.contains("iron_coast_boss_6:defeated") {event.objectives["iron_coast_boss_6:defeated"]+1} else {1};
    #{commands:[#{op:"objective",key:"iron_coast_boss_6:defeated",value:defeated},
        #{op:"effect",x:event.x+108/3,y:event.y+72/2},
        #{op:"effect",x:event.x+108*2/3,y:event.y+72/2},
        #{op:"play_sound",sound:"iron_coast_boss_6:death"}],state:state}
}
