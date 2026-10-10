fn on_pickup(event, state, random) {
    let recovered = if state.contains("recovered") { state.recovered + 1 } else { 1 };
    #{ commands: [#{ op: "credits", amount: 25 }], state: #{ recovered: recovered } }
}

// A selected repair cell can also be consumed with the special-action button.
fn on_use(event, state, random) {
    let used = if state.contains("used") { state.used + 1 } else { 1 };
    state.used = used;
    #{ commands: [#{ op: "objective", key: "aurora:repairs_used", value: used }], state: state }
}
