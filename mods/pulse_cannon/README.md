# Pulse Cannon 1.0.0

Enable **Pulse Cannon** in Mods and apply at the main menu. This independent API 1 example has no dependencies. Buy its equipment in the shop (185,000 credits, maximum one) or collect its pickup. It is a primary upgrade and fires alongside the starter guns.

Projectile: 4 damage, 8 logical pixels per step, 9 step cooldown, `straight`, air and ground targets. Every third paired burst adds two angled shots using deterministic random values. Rhai stores bounded burst/hit counters and emits local firing/impact sounds and effects.

`art/equipment-sd.png` is a 16×16 logical icon, `art/equipment-hd.png` its detailed 4× variant. Projectile canvases are 8×12 SD and 32×48 HD. Switch HD artwork in Options. The generated master images, SD/HD sprites, WAV files, provenance and reproduction inputs are tracked in Git. Original game assets and decoded reference images remain outside version control. `python3 generate_audio.py` reproduces both sound files.

Validate locally with `cargo run --no-default-features -- --mods mods --validate-mods pulse_cannon`. Read the shared [API documentation](../../docs/modding-api.md) for save pins, dependencies and sandbox limits.
