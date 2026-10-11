# Depth Charge 1.0.0

Enable **Depth Charge** in Mods, apply at the main menu, then buy it in the shop
for **525,000 credits**. It is an independent API 1 mod without dependencies or
overrides. Maximum one; resale returns 262,500 credits. It occupies a normal
inventory slot and preserves other equipment.

This is a **selectable, reusable ground/naval special weapon**. Choose it in
Inventory or with Alt/Shift, then hold Ctrl to launch. Space remains the owned
mega-bomb control. It does not consume charges or auto-attack merely because it
is equipped. Always-equipped forward guns remain available alongside it.

The native straight projectile travels six logical pixels per simulation tick.
A real ground-enemy collision deals 72 primary damage and starts one local
ground-blast effect. At most three other living ground enemies can receive
collateral damage: 36 damage within 16 pixels of the primary enemy's center,
or 20 damage between 16 and 36 pixels inclusive. The closest neighbors are
selected first, with stable entity order breaking ties. Aircraft, offscreen
enemies, repeated targets and centers outside that radius are excluded. If the
primary target dies, its contact still triggers the local blast correctly.

The deliberate 48-tick cooldown is about 2.06 seconds at 70/3 Hz. The charge does
not home or detonate automatically in empty space. Slow travel makes moving
ground targets an aiming challenge; there is no screen-wide damage command.
Destructible terrain receives native primary damage, but cannot trigger scripted
collateral because the public snapshot contains enemies rather than terrain
cells. Enemy contacts emit impact audio; a miss produces only the launch sound
and projectile. The normal native terrain destruction effects remain available.

SD equipment/projectile canvases are 16×16 and 8×12; detailed HD variants are
64×64 and 32×48. Options selects SD or HD artwork without changing logical
placement or damage. Both are single aligned frames with transparent margins.
[Artwork provenance](art-provenance.json) records unchanged generated masters,
prompts, final PNG hashes and the Rust preparation recipe. All new images, WAVs,
source masters and recipes are included; decoded original style references are
kept outside the mod.

`python3 generate_audio.py` reproduces the mechanical launch and low naval impact
from deterministic synthesis without external recordings. `prepare_art.rs`
rebuilds SD/HD fitting from the included source masters. The companion Railburst
package's [review helper](../iron_coast_railburst/validation/review.py) is a developer
tool for both packages and is not a gameplay dependency.

From the RustRaptor directory:

```sh
cargo test --locked --no-default-features --test iron_coast_stage2_weapons
cargo run --locked --no-default-features -- --data data --mods mods \
  --validate-mods iron_coast_depth_charge
IRON_COAST_STAGE2_BALANCE_REPORT=/tmp/stage2-balance.json \
  cargo test --locked --no-default-features --test iron_coast_stage2_weapons \
  real_catalog_700_tick_balance_and_coexistence_report -- --ignored --nocapture
```

[validation/balance.json](validation/balance.json) records the actual controlled
700-tick damage observations supporting this price and role. Portable checks
cover ground filtering, inner/outer falloff, the finite neighbor cap, misses,
kills, cooldown, independent activation, coexistence, half-price resale, full
inventory preservation, deterministic state/RNG continuation and whole-tick
rollback. [validation/review.json](validation/review.json) distinguishes public
decoder/blitter/mixer captures from live desktop review. Read the [API](../../docs/modding-api.md)
for save pins and script execution limits.
