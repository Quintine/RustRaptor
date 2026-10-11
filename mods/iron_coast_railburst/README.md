# Railburst Cannon 1.0.0

Enable **Railburst Cannon** in Mods, apply at the main menu, then buy it in the
shop for **685,000 credits**. It is an independent API 1 mod without dependencies
or overrides. Maximum one; resale returns 342,500 credits. It occupies a normal
inventory slot and never replaces or deletes another upgrade.

This is a **selectable, reusable special weapon**. Select it in Inventory or with
Alt/Shift during a mission, then hold Ctrl to fire. Space still drops an owned
mega bomb. Merely owning or selecting the cannon does not auto-fire it. No
ammunition is consumed; always-equipped forward guns can fire alongside it.

A native straight rail slug travels 16 logical pixels per simulation tick,
dealing 42 damage on its first real air or ground collision. That contact
penetrates at most two further living enemies ahead for 32 and 22 damage. Their
centers must stay within 12 pixels of the original firing x coordinate and within
160 pixels ahead of the first target's center. The nearest forward target wins;
stable entity order breaks ties. The primary projectile retires normally, while
the two additional contacts resolve through bounded `on_hit` damage commands.
This is finite contact-triggered penetration rather than a persistent beam.

The cooldown is 22 ticks, about 0.94 seconds at the original 70/3 Hz simulation
rate. Aim carefully: it does not home, acquire offscreen enemies, turn sideways
or clear the screen. Native point collision can miss exceptionally tiny targets
between its 16-pixel steps. Destructible terrain receives native primary damage;
the API exposes enemy snapshots, so terrain does not trigger scripted penetration.
Small air/ground impacts and impact audio occur only after an enemy contact;
empty-space shots produce fire audio and the projectile, without muzzle blasts.

The SD equipment/projectile canvases are 16×16 and 4×20, with detailed 4× HD
variants at 64×64 and 16×80. Toggle HD artwork in Options. Both modes share logical
placement and gameplay dimensions; the single-frame master has no animation
misalignment. [Artwork provenance](art-provenance.json) binds untouched built-in
generated masters, prompts, output hashes and the preparation recipe. Generated
masters, final sprites, original procedural WAVs and reproduction inputs belong
to this package; decoded original reference art is kept outside it.

`python3 generate_audio.py` reproduces the firing crack and short metal impact.
`prepare_art.rs` reproduces SD/HD fitting from the included source PNGs. The
shared read-only [native review helper](validation/review.py) builds this project,
validates both independent packages and writes indexed art/audio captures to an
explicit evidence directory. It requires the included original catalog for the
engine palette and instruments and never changes pilots or selected mods.

From the RustRaptor directory:

```sh
cargo test --locked --no-default-features --test iron_coast_stage2_weapons
cargo run --locked --no-default-features -- --data data --mods mods \
  --validate-mods iron_coast_railburst
IRON_COAST_STAGE2_BALANCE_REPORT=/tmp/stage2-balance.json \
  cargo test --locked --no-default-features --test iron_coast_stage2_weapons \
  real_catalog_700_tick_balance_and_coexistence_report -- --ignored --nocapture
python3 mods/iron_coast_railburst/validation/review.py --output /tmp/stage2-native
```

See [validation/balance.json](validation/balance.json) for controlled 700-tick
single-target, off-axis, aligned-column, mixed-cluster and forward-gun combination
observations, and [validation/review.json](validation/review.json) for the tested
scope. These stationary fixtures establish the price/role comparison, not a claim
about every campaign encounter. Script counters and RNG checkpoints serialize
normally with pilot state; rejected callback commands roll back the whole tick.
Read the [API](../../docs/modding-api.md) for save compatibility and sandbox limits.
