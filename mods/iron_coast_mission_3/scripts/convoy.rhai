fn on_tick(event,state,random) {
    // Stop at the interdiction line: an unarmed objective must never escape.
    let commands=[];
    if event.health>0 && event.y>=44 {
        commands.push(#{op:"move",entity:event.entity,x:event.x,y:44});
    }
    #{commands:commands,state:state}
}

fn on_death(event,state,random) {
    let intercepted=if event.objectives.contains("iron_coast_mission_3:convoys_intercepted") {
        event.objectives["iron_coast_mission_3:convoys_intercepted"]+1
    } else {1};
    // Recovered maintenance supplies restore shield directly. No extra item
    // slot or trial equipment is needed, even with a full veteran inventory.
    #{commands:[
        #{op:"objective",key:"iron_coast_mission_3:convoys_intercepted",value:intercepted},
        #{op:"shield",amount:15},
        #{op:"play_sound",sound:"iron_coast_mission_3:cargo_salvage"}
    ],state:state}
}
