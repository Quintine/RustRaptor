// Each real instance has a bounded serializable clock. No native/legacy behavior.
fn alive(event) {
    for e in event.entities { if e.entity == event.entity && e.health > 0 { return true; } }
    false
}
fn on_spawn(event, state, random) {
    if !alive(event) { return #{commands:[],state:state}; }
    let retained = #{};
    // Discard entries from earlier failed/replayed missions; preserve simultaneous instances.
    if state.contains("units") {
        for e in event.entities {
            let key = e.entity.to_string();
            if e.definition == "iron_coast_stage2_boss_6:unit" && state.units.contains(key) { retained[key] = state.units[key]; }
        }
    }
    state.units = retained;
    let max_health = 1;
    for e in event.entities { if e.entity == event.entity { max_health = e.health; } }
    state.units[event.entity.to_string()] = #{age:0,direction:1,max_health:max_health};
    #{commands:[#{op:"velocity",entity:event.entity,vx:0,vy:2}],state:state}
}
fn on_tick(event, state, random) {
    if event.health <= 0 || !alive(event) { return #{commands:[],state:state}; }
    let key = event.entity.to_string();
    if !state.contains("units") { state.units = #{}; }
    if !state.units.contains(key) { state.units[key] = #{age:0,direction:1,max_health:event.health}; }
    let u = state.units[key];
    if !u.contains("max_health") { u.max_health = event.health; }
    if event.y < 24 { return #{commands:[#{op:"velocity",entity:event.entity,vx:0,vy:2}],state:state}; }
    u.age += 1;
    if event.x >= 112 { u.direction = -1; }
    if event.x <= 88 { u.direction = 1; }
    let commands = [#{op:"move",entity:event.entity,x:event.x,y:24},#{op:"velocity",entity:event.entity,vx:u.direction,vy:0}];
    let phase = u.age % 96;
    if phase == 44 { commands.push(#{op:"play_sound",sound:"iron_coast_stage2_boss_6:warning"}); }
    if phase == 60 {
        commands.push(#{op:"projectile",weapon:"iron_coast_stage2_boss_6:shell",x:event.x+28,y:event.y+64,vx:-1,vy:4,hostile:true});
        commands.push(#{op:"play_sound",sound:"iron_coast_stage2_boss_6:shot"});
    }
    if phase == 72 {
        commands.push(#{op:"projectile",weapon:"iron_coast_stage2_boss_6:shell",x:event.x+80,y:event.y+64,vx:1,vy:4,hostile:true});
        commands.push(#{op:"play_sound",sound:"iron_coast_stage2_boss_6:shot"});
    }
    if phase == 84 && event.health <= u.max_health / 2 {
        let aim = (event.player_x - event.x - 40) / 48;
        let vx = if aim < -2 { -2 } else if aim > 2 { 2 } else { aim };
        commands.push(#{op:"projectile",weapon:"iron_coast_stage2_boss_6:core",x:event.x+52,y:event.y+64,vx:vx,vy:3,hostile:true});
        commands.push(#{op:"play_sound",sound:"iron_coast_stage2_boss_6:shot"});
    }
    state.units[key] = u;
    #{commands:commands,state:state}
}
fn on_death(event, state, random) {
    if state.contains("units") { state.units.remove(event.entity.to_string()); }
    let n = if event.objectives.contains("iron_coast_stage2_boss_6:defeated") { event.objectives["iron_coast_stage2_boss_6:defeated"] + 1 } else { 1 };
    #{commands:[#{op:"objective",key:"iron_coast_stage2_boss_6:defeated",value:n},#{op:"effect",x:event.x+28,y:event.y+40},#{op:"effect",x:event.x+80,y:event.y+40},#{op:"play_sound",sound:"iron_coast_stage2_boss_6:death"}],state:state}
}
