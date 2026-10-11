# Iron Coast: Relay Warden

Standalone API 1 boss package used by the Tidal Relay mission. It has no dependencies and never decides when a mission finishes. Enable the mission to select this package automatically through its dependency.

- Enemy: `iron_coast_boss_2:unit`, health 160, reward 1,800 credits, airborne boss.
- Projectile: `iron_coast_boss_2:projectile`, damage 3, speed 4, 8×8 logical canvas.
- Completion observation: `iron_coast_boss_2:defeated` increases once for each actual death. Duplicate notifications are harmless; despawning or time passing does not count.
- Art: one complete static frame on a 96×64 logical canvas. SD and HD preserve the same origin, full silhouette and true alpha. HD is 768×512; gameplay collision dimensions remain 96×64.
- Audio: `shot`, `warning` and `death` namespaced sound IDs, each a generated, non-silent 22,050 Hz, mono, 16-bit PCM WAV.

The Warden enters at two logical pixels per tick, stops at y=24, and patrols x=80…144. Each entity tracks its own arrival timer and direction. An audible radar charge starts 12 ticks before each 54-tick volley. Odd volleys fire two parallel outer lanes; even volleys fire two diverging inner lanes. The opening below its central radar dish remains readable. Each queued spawn registers its life even if a projectile has already killed it before callback dispatch; that early kill still counts when the engine delivers its actual death. Timers and directions are removed when the aircraft dies, and dead units cannot emit movement, warnings or shots. Difficulty scaling comes from the engine, including its existing half-health rule on the two lower difficulties.

## Asset sources

The two masters were generated using the built-in imagegen tool from the saved prompts, with the existing generated Iron Coast cruiser inspected for material and color style. The Warden and cyan radar pulse have new silhouettes; no original game art or recordings are copied into this package. `provenance.json`, `art-qa.json` and `audio-recipe.json` record inputs, processing, alpha bounds and hashes. All PNGs, WAVs and prompts are intended for Git.

Recreate the SD/HD output and audio from the saved masters with:

```sh
python3 RustRaptor/mods/iron_coast_boss_2/build_assets.py
```

## Validation

The package contains a small Rust validation program that uses the game's public modding and deterministic simulation API. It validates package artwork and WAV decoding, both telegraphs and alternating volleys, separate entity timers, actual death rewards/objectives, repeated and dead callbacks, cleanup, a real lethal projectile during the spawn step, and reuse of an entity ID for a new life. It requires no original game assets.

```sh
CARGO_TARGET_DIR=RustRaptor/target cargo run --offline \
  --manifest-path RustRaptor/mods/iron_coast_boss_2/validation/Cargo.toml \
  --bin validate-boss
```

Its saved result is `validation/report.json`. Tidal Relay's validation also exercises this boss in the complete mission with the real original content registry.
