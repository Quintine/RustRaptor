fn on_mission_start(event, state, random) {
    #{ commands: [
        #{ op: "give_item", item: "aurora:pulse_cannon", count: 1 },
        #{ op: "objective", key: "aurora:destroyed", value: 0 }
    ], state: state }
}

fn on_mission_end(event, state, random) {
    #{ commands: [#{ op: "objective", key: "aurora:trial_finished", value: 1 }], state: state }
}
