# Iron Coast II: Needlewing

An independent enemy package for API version 1. Enable **Iron Coast II: Needlewing** in the game's Mods menu. Enabling a mission that requires it also enables this package through the dependency manager. Enabling this enemy alone registers its content; a mission or another mod must spawn it. There are no dependencies or overrides.

## Behavior

- Enemy ID: `iron_coast_stage2_interceptor:unit`; air target, logical canvas 24×24, health 18, reward 100 credits.
- Fast flanker. Its integer route curves through eight lateral phases, with short straight pauses and a downward speed of one or two logical pixels per tick.
- Three aimed 2-damage projectiles at speed 3, four ticks apart. The next burst starts after 70 engine ticks (about 3 seconds). There is no warning chirp for this quick, low-damage enemy.
- `:gun` is a scripted firing controller; `:projectile` is the distinct hostile projectile definition. These weapons are enemy content, unavailable in the shop; no player equipment or credits are granted.
- `:shot`, `:warning` and `:death` are synthesized local WAV cues. Needlewing's warning is supplied for authors but is not played by its ordinary AI.

The original forward guns can hit these enemies. Air-only weapons cannot hit ground enemies, and ground-only weapons cannot hit the Needlewing. Collision dimensions are identical in SD and HD; artwork has transparent padding and one aligned frame per sprite. Normal units leave the playfield if not killed. A mission may hold a required target inside the screen while retaining its lateral movement.

## Mission integration

Spawn `iron_coast_stage2_interceptor:unit` through normal mission definitions or the documented `spawn` command. Actual deaths increment the objective `iron_coast_stage2_interceptor:defeated` once. Escapes and despawns do not increment it. The engine awards the configured reward and creates normal death feedback; this script adds its local death cue. Objective keys and content IDs are namespaced so all three shared enemy packages coexist.

Firing is rejected for dead or invisible units and after they pass the player. Bursts are finite; scripts never spawn enemies, grant equipment, deal direct damage, or complete a mission. Per-entity movement clocks and burst state are serializable and use only supplied deterministic RNG. Up to 128 live units receive custom AI, with periodic pruning and a bounded 128-entry death guard. Excess units retain basic engine movement and do not gain extra attacks. The diagnostics counters saturate at one billion. Missions should use much smaller readable waves.

No new controls are introduced. Fire and weapon selection remain the normal game controls. All prices are inapplicable because the package adds enemies, not purchasable items.

## Assets and validation

Both artwork modes, unchanged generated masters, prompts, derivation recipe and all sound recipes are included. See [artwork provenance](ART_PROVENANCE.md), [art checks](art-qa.json), [audio recipe](audio-recipe.json) and [validation record](validation/acceptance.json). Decoded original style references and local review screenshots are deliberately kept outside this package.

From the RustRaptor folder:

```sh
cargo test --locked --no-default-features --test stage2_enemies
cargo run --locked --no-default-features -- --data data --mods mods --validate-mods iron_coast_stage2_interceptor
```

Tests exercise actual World callbacks, finite volleys and telegraphs, ground/air filtering, damage behavior, escapes, real death rewards and counters, reused entity IDs, bounded state, full save/RNG continuation and independent/combined activation. Shipped PNG geometry and all nine effects are also checked through the real SoundBank/Mixer. Local catalog validation and indexed SD/HD scale 1–4 galleries are recorded separately. These controlled checks do not establish full campaign balance or a live SDL scene; the mission packages have their own route tests.
