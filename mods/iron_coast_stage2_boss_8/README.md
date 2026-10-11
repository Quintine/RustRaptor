# Iron Coast II: Leviathan

Separate API 1/version 1.0.0 boss mod, with no dependencies or overrides.

- Enemy: `iron_coast_stage2_boss_8:unit`, health 360, reward 9000 credits (difficulty applies the normal engine health rules).
- Actual death objective: `iron_coast_stage2_boss_8:defeated`. Escape/despawn grants nothing.
- Persistent patrol is confined to x 60–116, y 4, so the complete carrier stays reachable.
- Three phases: closed reactor, open amber reactor below two-thirds health, red warning strips and blue ion coils below one-third. The first fan leaves the center open; later attacks rotate a full 32-pixel safe lane and add outward flanks in the final act.
- Every volley has an audible warning 18 simulation ticks ahead and cosmetic arcs at attacking pods. Shots travel 3 pixels/tick; no aiming at the player's instantaneous position, no contact explosion at the muzzle.
- Logical art 112×112, 3 phase frames; HD 4×; shell 6×12. Collision dimensions stay identical in SD/HD.

Per-entity cursors isolate simultaneous bosses. Spawn callbacks reset reused IDs; actual deaths retire only that cursor and increment the public death counter once. `animation` pins a declared frame; phase state remains serializable.

`art/generated-v1.png` is the untouched builtin output. Prompt and provenance bind the exact generator/reference hashes. The companion mission 8 `build_finale_assets.py` performs complete meaningful-alpha crops and proportional fits, then SD reduction; it also reproduces the seeded 22.05 kHz mono 16-bit warning/phase/shot/death WAVs. It does not repaint or stretch sprites. Reference/catalog images and gameplay screenshots remain outside the package.

Acceptance source: `../iron_coast_stage2_mission_8/validation/`; standalone boss runs and both full sorties use the actual Catalog/World/Rhai and starter guns. Durable simulation/SD-HD captures are external review evidence; final metrics are copied into `validation-summary.json` after balance is frozen.

Actual starter boss-only runs from 75 shield: 186 ticks at difficulties 0/1 and 366 at 2/3; 75/67 shield remains. Retained-state spawn-step lethal replays use the actual World and verify the counter and reward once on each new lifecycle.
