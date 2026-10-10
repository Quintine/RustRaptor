# Ion Lance 1.0.0

Enable **Ion Lance** in Mods and apply at the main menu. This independent API 1 example has no dependencies. Buy its equipment in the shop (425,000 credits, maximum one) or collect its pickup. Choose it in Inventory or cycle special weapons during a mission. The equipped weapon fires with Fire or Special; it consumes no ammunition.

Projectile: 8 damage, 12 logical pixels per step, 14 step cooldown, `beam`, air and ground targets. The narrow beam pierces every enemy in its column for two steps (16 total damage per enemy per trigger). Rhai stores bounded burst/hit counters and emits local firing/impact sounds and effects.

`art/equipment-sd.png` is a 16×16 logical icon, `art/equipment-hd.png` its detailed 4× variant. Projectile canvases are 4×32 SD and 16×128 HD. Switch HD artwork in Options. The generated master images, SD/HD sprites, WAV files, provenance and reproduction inputs are tracked in Git. Original game assets and decoded reference images remain outside version control. `python3 generate_audio.py` reproduces both sound files.

Validate locally with `cargo run --no-default-features -- --mods mods --validate-mods ion_lance`. Read the shared [API documentation](../../docs/modding-api.md) for save pins, dependencies and sandbox limits.
