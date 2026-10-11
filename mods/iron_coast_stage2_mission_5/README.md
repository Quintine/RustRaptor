# Iron Coast II: Black Tide — Skybreaker Arsenal

Standalone mission `iron_coast_stage2_mission_5:mission_05` and single-sortie campaign
`iron_coast_stage2_mission_5:campaign`. The optional `iron_coast_stage2_campaign` assembly
places it in the complete Black Tide route; no cross-mission override is needed.
Enable this package in **Mods**. Dependency selection adds its own boss,
`iron_coast_stage2_music`, `iron_coast_stage2_siege` and
`iron_coast_stage2_interceptor`, all at version 1.x. The package never changes
pilot equipment or grants a premium weapon.

Use normal controls: **Ctrl** fires, **Space** drops a carried bomb,
**Alt/Shift** cycles selectable weapons. The forward guns hit both required
stations and the boss. Optional Railburst/Depth Charge equipment follows its
own shop price and inventory rules; neither is required by this mission.

Destroy all 2 persistent ground targets, then destroy Skybreaker. Target
deaths award 900 credits and restore 8 shield each.
The boss awards 6,000; confirmed objectives pay a once-per-sortie
26,000-credit completion bonus. Mid-sortie field support restores 15 shield
at tick 1400 and another 15 on boss arrival. Shields remain capped by the engine.
A target killed after the boss still completes the objective. Escaped ordinary
wave enemies do not block progression. The 3,500-tick duration is descriptive;
there is no automatic success, timer failure or despawn of required targets.
The reflected 18-row terrain period repeats 16 times: 288 rows / 9,216 logical scroll
pixels, covering prolonged objective fights beyond the nominal duration.

The boss enters at tick 2340. Three outer-lane industrial
hazard shells have an audible warning 24 ticks beforehand; the center stays
clear of those fixed hazards. Difficulty 2 is the intended challenge. Boss
health follows original easier-difficulty scaling, while its second attack
phase uses half of its actual per-instance starting health.

Native classic definitions are referenced directly, retaining their original
movement: `base:enemy_0_12`, `base:enemy_0_13`, `base:enemy_0_21`, `base:enemy_0_22`, `base:enemy_1_25`, `base:enemy_1_26`. New shared enemies are normal nonlegacy mods. Decorative
runway/docks, cranes, rocks and molten metal are scenery; required targets are
separate destroyable units and are always reachable near the top of the screen.

Artwork includes 162 joined terrain tiles in both 32px SD and 128px HD, plus a
320×200 /1280×800 briefing. A complete generated square master is resized as one
canvas before cropping. Whole-canvas vertical reflection makes the repeating
scroll join meet exactly on its boundary row. Texture orientation repeats and
HD is more detailed than SD; no claim of unique terrain over the entire mission
or exact zero luminance difference is made. Required station/projectile art
references the original catalog. Runtime palette conversion preserves alpha
and uses ordinary colors rather than reserved cycling colors.

[`provenance.json`](provenance.json), `prompts/`, unchanged `sources/raw-v1.png`,
[`art-qa.json`](art-qa.json) and [`audio-recipe.json`](audio-recipe.json) track
masters and recipes. Run `python3 mods/iron_coast_stage2_mission_5/tools/build_assets.py`
from RustRaptor; Pillow and bundled `data/misc/PALETTE_DAT` are required. No
external game-data fallback is used. WAVs are original deterministic 22050Hz
PCM16 mono synthesized chirps/noise with faded zero endpoints.

Validation from RustRaptor:

```sh
CARGO_TARGET_DIR=target cargo test --locked --manifest-path mods/iron_coast_stage2_boss_5/validation/Cargo.toml --lib
CARGO_TARGET_DIR=target cargo run --release --locked --manifest-path mods/iron_coast_stage2_boss_5/validation/Cargo.toml
cargo run --release --locked --no-default-features -- --data data --mods mods --validate-mods iron_coast_stage2_mission_5,iron_coast_stage2_boss_5,iron_coast_stage2_music,iron_coast_stage2_siege,iron_coast_stage2_interceptor
```

The portable callback/boss simulation tests require no original catalog. The
real acceptance runner uses bundled original data and writes only isolated
`.reference/iron-coast-stage2-56-acceptance/` evidence. It checks all difficulties,
registered 75-shield / 10,000-credit and default 100-shield / zero-credit pilots,
full 20 inventory slots and four stacked shield reserves, failure/restart reset,
actual classic enemy movement, complete/debrief flags, single rewards,
identical per-step replay digests and unshot targets still present at tick 5700.
The controlled registered difficulty 2 run completes at tick 2638
(113.06s), shield 100, credits 48,610,
using forward guns only and at most 4 horizontal pixels per tick. This is an
aim/hold-bottom controller, not a guarantee for all play styles. Both indexed
modes and all eight package/boss cues were decoded through the actual Rust
asset loader/mixer. Live 1080p capture belongs to the aggregate release check.
