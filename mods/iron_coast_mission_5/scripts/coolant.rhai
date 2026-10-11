fn on_use(event, state, random) {
    state.uses = if state.contains("uses") { state.uses + 1 } else { 1 };
    #{commands:[
        #{op:"shield", amount:30},
        #{op:"play_sound", sound:"iron_coast_mission_5:coolant_use"}
    ], state:state}
}
