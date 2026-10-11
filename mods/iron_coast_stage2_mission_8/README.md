# Iron Coast II 8: Black Tide

Standalone API 1/version 1.0.0 mission mod; the optional eight-sortie campaign links progression. No `next` override or embedded copy of another package is used.

Mission ID: `iron_coast_stage2_mission_8:mission_08`. Dependencies: the interceptor, siege, skimmer, boss 8 and Stage2 soundtrack mods, each ^1.0. Enabling this mission in Mods selects its dependencies through the normal manager. Optional Railburst/Depth Charge shop upgrades require no loan or mission dependency.

Destroy **5 Bastion Crawlers, 4 Wakeknife Skimmers and the Leviathan**. All naval spawns are required and are held at y 48/80 once they enter, preserving lateral AI; the final carrier arrives at tick 2850 and remains reachable. Elapsed duration 3800 never completes the mission. Victory is gated by actual shared death counters plus the boss death counter and pays 55000 credits once, in addition to enemy rewards.

Three assault acts at start/900/1800 lead into the carrier encounter. Authored support repairs +15 shield at each act and +20 at boss arrival, capped by the standard shield system. No item is granted/removed, so full inventories, owned equipment and physical shield reserves retain their identities and capacity. Failed sorties grant no victory reward; the next sortie resets phase/debrief/death objectives.

Starter strategy: hold Ctrl, use ordinary lateral movement to line up paired forward guns, clear the lowest required naval target first, then the carrier. Native classic loop/sweep entries are retained as `base:enemy_0_73/74/23/24/95/96`; this package never clones, changes or anchors their native paths. Sidestep approaching shots while continuing fire; the reference controller uses at most 4 pixels per tick and reacts only to nearby hostile rounds at y136–188. Boss warning sounds/charge arcs identify firing pods; open deck lanes offer counterplay. Alt/Shift changes selectable weapons, Space remains the normal bomb control.

Genuine newly generated joined harbor/citadel art is the SD/HD source. Tiles are split only after whole-canvas resampling and palette reduction; reflected half-period rows have exact boundary pixels, with complete reassembly assertions. Briefing artwork is a proportional overview of this map. Tiles are 32×32 logical/128×128 HD, nine columns; sixteen complete mirrored periods cover 12,288 logical scroll pixels, including delayed finale objectives. SD uses ordinary palette 0..239; no original palette classes are invented. Original reference pixels are not shipped.

The reproducible sibling helper `../iron_coast_stage2_mission_8/build_finale_assets.py` builds all four finale packages using self-contained `RustRaptor/data/misc/PALETTE_DAT` and preserves all raw art/prompts/provenance. Mission 8 v1's painted-aircraft terrain is retained as rejected history; v2 genuinely replaces it with static service decks. WAV cues are deterministic local 22.05 kHz mono 16-bit synthesis, not recordings. Music: `iron_coast_stage2_music:finale`.

Validation lives in mission 8 `validation/`: real original Catalog/Rhai/World, all difficulties from 75 shield/10,000 credits, 100 shield/0 credits, full 20 slots, all visible boss phases, native movement, no-fire reachability after duration, every-step deterministic replay, preserved mid-boss state and restart/failure checks. Review captures stay outside all mod folders to keep save hashes stable.

Measured starter runs: 3026 ticks at difficulties 0/1 and 3206 at 2/3, ending with 86/32 shield from 75. The full 20-slot hard-mode run ends with 32 shield. Enemy geometry, wave density and repairs were preserved during controller tuning.
