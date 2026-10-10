fn on_death(event,state,random) {
    let opened=0;
    if event.objectives.contains("iron_coast_mission_1:depots_opened") {
        opened=event.objectives["iron_coast_mission_1:depots_opened"];
    }
    #{commands:[
        #{op:"objective",key:"iron_coast_mission_1:depots_opened",value:opened+1},
        #{op:"play_sound",sound:"iron_coast_mission_1:depot_open"}
    ],state:state}
}
