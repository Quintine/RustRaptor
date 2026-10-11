// Pickups use the same reusable equipment as the shop.
fn on_pickup(event, state, random) {
    let recovered = if state.contains("recovered") { state.recovered % 100000 + 1 } else { 1 };
    #{ commands: [#{ op: "objective", key: "lightning_shield:recovered", value: recovered }],
       state: #{ recovered: recovered } }
}
