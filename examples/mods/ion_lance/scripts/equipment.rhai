// Recovery is recorded separately from the weapon firing state.
fn on_pickup(event, state, random) {
    let recovered = if state.contains("recovered") { state.recovered % 100000 + 1 } else { 1 };
    #{ commands: [#{ op: "objective", key: "ion_lance:recovered", value: recovered }],
       state: #{ recovered: recovered } }
}
