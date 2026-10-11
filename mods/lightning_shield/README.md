# Lightning Shield

An independent, reusable proximity weapon for **155,000 credits**. Enable
**Lightning Shield** in the Mods menu, apply selections at the main menu, then
buy it in the supply room. It is **always equipped** while owned and fires
alongside the other primary guns when you hold **Fire**. It needs no special
selection, consumes no ammo, and you can own one.

Each pulse deals **2 damage** to up to **four close airborne ships** in any
direction. Range is **28 logical pixels from your ship's center to the nearest
point of the enemy hull**: approximately 12 pixels beyond your 32-pixel hull.
It picks the nearest ships first, with a stable tie break. Ground structures
are excluded. The **8-tick cooldown** gives about 2.92 pulses per second and
5.87 measured damage per second against a stationary close ship.
The price places this short-range supplement below the Micro Missile primary
upgrade. See the [balance report](balance-report.json) for the 30-second
controlled observations, including ground exclusions and combined loadouts.

It runs only while Fire is held, and makes no sound when nothing is in range.
It supplements close combat; it does not absorb collision damage, restore energy
or block bullets. It continues working when you select a different special.

Firing charges a flickering electric ring just outside the hull. The short zaps
start from the edge facing each target, with a blue glow around the ship. The
ring follows your movement and fades within one recharge after releasing Fire;
it remains silent when no aircraft are close. The ring and its forks are cosmetic.

This package uses the public mod API's `scripted` weapon behavior, read-only
entity snapshots with `ground`, and `damage`, `arc` and `play_sound` commands.
All targeting and damage rules live in `scripts/weapon.rhai`. It has no
dependencies or overrides, and coexists with the other weapons and Iron Coast.

The equipment icon ships in **16×16 SD** and **64×64 HD**, alongside the
transparent source master and deterministic synthesized audio. The halo and
connecting bolts use anchored `arc` commands and the game's renderer at both
scales. See [provenance](ART_PROVENANCE.md)
for the exact built-in imagegen prompt, asset hashes and reproduction recipes.

From `RustRaptor/`:

```sh
cargo run --locked --no-default-features -- --mods mods --validate-mods lightning_shield
cargo test --locked --no-default-features --test weapons_mods lightning_shield
```

See [weapon pricing and measurements](../../docs/weapon-balance.md),
[the API](../../docs/modding-api.md) and
[the AI mod checklist](../../docs/mod-authoring-checklist.md).
