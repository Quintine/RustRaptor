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
            if e.definition == "iron_coast_stage2_boss_5:unit" && state.units.contains(key) { retained[key] = state.units[key]; }
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
    if event.x >= 136 { u.direction = -1; }
    if event.x <= 80 { u.direction = 1; }
    let commands = [#{op:"move",entity:event.entity,x:event.x,y:24},#{op:"velocity",entity:event.entity,vx:u.direction,vy:0}];
    let phase = u.age % 84;
    if phase == 36 { commands.push(#{op:"play_sound",sound:"iron_coast_stage2_boss_5:warning"}); }
    if phase == 50 {
        commands.push(#{op:"projectile",weapon:"iron_coast_stage2_boss_5:shell",x:event.x+28,y:event.y+48,vx:-1,vy:4,hostile:true});
        commands.push(#{op:"play_sound",sound:"iron_coast_stage2_boss_5:shot"});
    }
    if phase == 58 {
        commands.push(#{op:"projectile",weapon:"iron_coast_stage2_boss_5:shell",x:event.x+80,y:event.y+48,vx:1,vy:4,hostile:true});
        commands.push(#{op:"play_sound",sound:"iron_coast_stage2_boss_5:shot"});
    }
    if phase == 66 && event.health <= u.max_health / 2 {
        let aim = (event.player_x - event.x - 40) / 48;
        let vx = if aim < -2 { -2 } else if aim > 2 { 2 } else { aim };
        commands.push(#{op:"projectile",weapon:"iron_coast_stage2_boss_5:core",x:event.x+52,y:event.y+48,vx:vx,vy:3,hostile:true});
        commands.push(#{op:"play_sound",sound:"iron_coast_stage2_boss_5:shot"});
    }
    state.units[key] = u;
    #{commands:commands,state:state}
}
fn on_death(event, state, random) {
    if state.contains("units") { state.units.remove(event.entity.to_string()); }
    let n = if event.objectives.contains("iron_coast_stage2_boss_5:defeated") { event.objectives["iron_coast_stage2_boss_5:defeated"] + 1 } else { 1 };
    #{commands:[#{op:"objective",key:"iron_coast_stage2_boss_5:defeated",value:n},#{op:"effect",x:event.x+28,y:event.y+40},#{op:"effect",x:event.x+80,y:event.y+40},#{op:"play_sound",sound:"iron_coast_stage2_boss_5:death"}],state:state}
}
