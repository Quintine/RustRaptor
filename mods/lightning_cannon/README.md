# Lightning Cannon

An independent, reusable heavy lightning special for **825,000 credits**.
Enable **Lightning Cannon** in the Mods menu, apply selections at the main menu,
then buy it in the supply room. Select it in Inventory or cycle specials;
**Fire or Special** discharges the cannon while selected. It consumes no ammo,
and you can own one.

The bolt instantly hits the nearest visible air or ground target ahead of the
muzzle, within 180 logical pixels and a 36-pixel horizontal aiming allowance.
It deals **32 damage**, then jumps from the struck ship to the nearest unhit
enemy within **48 pixels**, for **20, 12 and 8 damage**. A discharge hits at most
four different enemies. Chaining can change direction and continues from a
destroyed target's last position. An isolated target takes only the initial hit;
off-axis targets require an adjacent chain target. Cooldown is **18 ticks**,
about 0.77 seconds. A missed shot shows a bolt and firing sound without damage.

The 30-second controlled simulation measured **41.60 damage/s** on an isolated
aligned target and **93.60 combined damage/s** across a four-target chain. The
price places it above the original Pulse Cannon and below the Death Ray. See
the package [balance report](balance-report.json) for the recorded observations.

This package uses the public mod API's `scripted` weapon behavior, read-only
entity snapshots, `damage`, `arc` and `play_sound` commands. All acquisition,
chaining and damage rules live in `scripts/weapon.rhai`. It has no dependencies
or overrides. It coexists with the other independent weapons and Iron Coast.

The equipment icon ships in **16×16 SD** and **64×64 HD**, alongside the
transparent source master and deterministic synthesized audio. Connecting bolts
use the game's arc renderer at both scales. See [provenance](ART_PROVENANCE.md)
for the exact built-in imagegen prompt, asset hashes and reproduction recipes.

From `RustRaptor/`:

```sh
cargo run --locked --no-default-features -- --mods mods --validate-mods lightning_cannon
cargo test --locked --no-default-features --test weapons_mods lightning_cannon
```

See [weapon pricing and measurements](../../docs/weapon-balance.md),
[the API](../../docs/modding-api.md) and
[the AI mod checklist](../../docs/mod-authoring-checklist.md).
