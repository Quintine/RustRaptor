// Per-life cursors are serializable and deterministic. No engine-specific boss behavior.
fn alive(event,id) {
    for unit in event.entities { if unit.entity==id && unit.health>0 { return true; } }
    false
}
fn on_spawn(event,state,random) {
    if !state.contains("ages") { state.ages=#{}; state.phases=#{}; state.directions=#{}; }
    if !state.contains("maximums") {state.maximums=#{};}
    // Remove cursors from a prior replay or an explicitly despawned life.
    for key in state.ages.keys() {
        let present=false;for unit in event.entities {if unit.entity.to_string()==key && unit.health>0 {present=true;}}
        if !present { state.ages.remove(key);state.phases.remove(key);state.directions.remove(key);state.maximums.remove(key); }
    }
    let key=event.entity.to_string();state.ages[key]=0;state.phases[key]=1;state.directions[key]=1;state.maximums[key]=1;
    for unit in event.entities {if unit.entity==event.entity && unit.health>0 {state.maximums[key]=unit.health;}}
    if !alive(event,event.entity) { return #{commands:[],state:state}; }
    #{commands:[#{op:"velocity",entity:event.entity,vx:0,vy:2}],state:state}
}
fn on_tick(event,state,random) {
    if event.health<=0 || !alive(event,event.entity) { return #{commands:[],state:state}; }
    let key=event.entity.to_string();
    if !state.contains("ages") || !state.ages.contains(key) { return #{commands:[],state:state}; }
    if event.y<20 { return #{commands:[#{op:"velocity",entity:event.entity,vx:0,vy:2}],state:state}; }
    // Older saved cursors lack maximums; initialize at their current living health.
    if !state.contains("maximums") {state.maximums=#{};}
    if !state.maximums.contains(key) {state.maximums[key]=event.health;}
    let phase=if event.health*2<=state.maximums[key] {2} else {1};
    if state.phases[key]!=phase {state.phases[key]=phase;state.ages[key]=0;}
    let age=state.ages[key]+1;state.ages[key]=age;
    let commands=[];
    commands.push(#{op:"move",entity:event.entity,x:96,y:20});commands.push(#{op:"velocity",entity:event.entity,vx:0,vy:0});
    let cycle=if phase==1 {84} else {66};
    if age%cycle==cycle-12 {commands.push(#{op:"play_sound",sound:"iron_coast_stage2_boss_1:warning"});}
    if age%cycle==0 {
        if phase==1 {
            commands.push(#{op:"projectile",weapon:"iron_coast_stage2_boss_1:projectile",x:120,y:72,vx:0,vy:4,hostile:true});
            commands.push(#{op:"projectile",weapon:"iron_coast_stage2_boss_1:projectile",x:200,y:72,vx:0,vy:4,hostile:true});
        } else {
            for lane in [-2,-1,1,2] {
                commands.push(#{op:"projectile",weapon:"iron_coast_stage2_boss_1:projectile",x:160+lane*18,y:72,vx:lane,vy:4,hostile:true});
            }
        }
        commands.push(#{op:"play_sound",sound:"iron_coast_stage2_boss_1:shot"});
    }
    #{commands:commands,state:state}
}
fn on_death(event,state,random) {
    let key=event.entity.to_string();
    if alive(event,event.entity) || !state.contains("ages") || !state.ages.contains(key) {return #{commands:[],state:state};}
    state.ages.remove(key);state.phases.remove(key);state.directions.remove(key);state.maximums.remove(key);
    let value=if event.objectives.contains("iron_coast_stage2_boss_1:defeated") {event.objectives["iron_coast_stage2_boss_1:defeated"]+1} else {1};
    #{commands:[#{op:"objective",key:"iron_coast_stage2_boss_1:defeated",value:value},#{op:"effect",x:event.x+64,y:event.y+32},#{op:"play_sound",sound:"iron_coast_stage2_boss_1:death"}],state:state}
}
