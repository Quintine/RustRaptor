fn alive(event) {
    for e in event.entities { if e.entity == event.entity && e.health > 0 { return true; } }
    false
}
fn on_spawn(event, state, random) {
    #{commands:if alive(event) { [#{op:"velocity",entity:event.entity,vx:0,vy:2}] } else { [] },state:state}
}
fn on_tick(event, state, random) {
    if event.health <= 0 || !alive(event) { return #{commands:[],state:state}; }
    if event.y < 28 { return #{commands:[#{op:"velocity",entity:event.entity,vx:0,vy:2}],state:state}; }
    // Required objectives stay in the player's visible firing corridor until killed.
    #{commands:[#{op:"move",entity:event.entity,x:event.x,y:28},#{op:"velocity",entity:event.entity,vx:0,vy:0}],state:state}
}
fn on_fire(event, state, random) {
    #{commands:[#{op:"play_sound",sound:"iron_coast_stage2_mission_6:alarm"}],state:state}
}
fn on_death(event, state, random) {
    let n = if event.objectives.contains("iron_coast_stage2_mission_6:targets_destroyed") { event.objectives["iron_coast_stage2_mission_6:targets_destroyed"]+1 } else { 1 };
    #{commands:[#{op:"objective",key:"iron_coast_stage2_mission_6:targets_destroyed",value:n},#{op:"shield",amount:8},#{op:"play_sound",sound:"iron_coast_stage2_mission_6:target_down"}],state:state}
}
