// Required relay targets settle into the firing corridor and never scroll away.
fn alive(event) {
    for unit in event.entities {
        if unit.entity == event.entity && unit.health > 0 {return true;}
    }
    false
}
fn on_spawn(event,state,random) {
    if !state.contains("live") {state.live=#{};}
    // Register even a lethal-on-spawn life so its queued death counts once.
    state.live[event.entity.to_string()]=true;
    if !alive(event) {return #{commands:[],state:state};}
    #{commands:[#{op:"velocity",entity:event.entity,vx:0,vy:1}],state:state}
}
fn on_tick(event,state,random) {
    if event.health<=0 || !alive(event) {return #{commands:[],state:state};}
    // Vary the station depth by its original horizontal lane.
    let anchor=if event.x<120 {28} else if event.x>160 {48} else {68};
    if event.y>=anchor {
        return #{commands:[
            #{op:"move",entity:event.entity,x:event.x,y:anchor},
            #{op:"velocity",entity:event.entity,vx:0,vy:0}
        ],state:state};
    }
    #{commands:[],state:state}
}
fn on_fire(event,state,random) {
    #{commands:[#{op:"play_sound",sound:"iron_coast_turret:shot"}],state:state}
}
fn on_death(event,state,random) {
    let key=event.entity.to_string();
    if alive(event) || !state.contains("live") || !state.live.contains(key) {
        return #{commands:[],state:state};
    }
    state.live.remove(key);
    let count=if event.objectives.contains("iron_coast_mission_2:relays_disabled") {
        event.objectives["iron_coast_mission_2:relays_disabled"]+1
    } else {1};
    #{commands:[
        #{op:"objective",key:"iron_coast_mission_2:relays_disabled",value:count},
        #{op:"shield",amount:12},
        #{op:"play_sound",sound:"iron_coast_mission_2:relay_offline"}
    ],state:state}
}
