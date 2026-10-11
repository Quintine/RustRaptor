# Iron Coast content packages

Iron Coast contains six independently toggleable mission mods, five shared
weapon and enemy mods, a shared soundtrack, six stage boss mods, and an optional
campaign assembly mod. Enable **Iron
Coast — Complete Campaign** (`iron_coast_campaign`) to select the full campaign
and its eighteen dependencies automatically. Each individual mission can also be
enabled separately; it selects the five shared content mods, soundtrack and its
own boss. Disabling a package also deselects unused dependencies. When this
affects other packages, a confirmation lists all affected mods; a single-mod
toggle with no dependency changes applies immediately. Dependencies still
needed by another enabled mod remain selected. The Mods manager validates versions
and dependency order and applies the change at the main menu. The new weapons can also be used in the original campaigns;
the enemy packages can be referenced from other missions.

| Package | Content |
| --- | --- |
| `iron_coast_campaign` | Links all six missions into one campaign without replacing mission scripts or artwork |
| `iron_coast_mission_1` | Breakwater mission, campaign, supply depots, field repairs, terrain, briefing art and mission audio |
| `iron_coast_mission_2` | Tidal Relay mission and its local communications targets, terrain, briefing art and audio |
| `iron_coast_mission_3` | Saltworks Convoy mission and its local cargo transports, terrain, briefing art and audio |
| `iron_coast_mission_4` | Stormwall mission, cliff batteries, terrain, briefing art and audio |
| `iron_coast_mission_5` | Cinder Docks mission and its armored foundries, coolant repairs, terrain, briefing art and audio |
| `iron_coast_mission_6` | Iron Crown finale, fortified batteries, dreadnoughts, terrain, briefing art and audio |
| `iron_coast_scout` | Airborne scout, weaving AI, projectiles, art and audio |
| `iron_coast_turret` | Ground turret, aimed firing, projectiles, art and audio |
| `iron_coast_boss` | Harbor command ship, persistent patrol and fan volleys, art and audio |
| `iron_coast_boss_2` | Relay Warden, authored movement and firing pattern, SD/HD art and audio |
| `iron_coast_boss_3` | Saltbreaker VTOL, authored movement and firing pattern, SD/HD art and audio |
| `iron_coast_boss_4` | Stormwall Arsenal, authored movement and firing pattern, SD/HD art and audio |
| `iron_coast_boss_5` | Cinder Hammer, authored movement and firing pattern, SD/HD art and audio |
| `iron_coast_boss_6` | Iron Crown Dreadnought, authored movement and firing pattern, SD/HD art and audio |
| `iron_coast_music` | Coastal Steel, original 96-second MUS loop played through the game's Rust FM synthesizer |
| `pulse_cannon` | Primary paired pulses and scripted burst rounds |
| `seeker_swarm` | Selectable homing missile volleys |
| `ion_lance` | Selectable penetrating beam |

All packages are version 1.0.0 and use mod API 1. Every mission requires
compatible 1.x versions of its five shared content mods, soundtrack and stage
boss. The campaign assembly requires all six mission packages; shared dependencies are selected transitively.
Save compatibility records each enabled package's exact version and content
hash. A changed or missing mod prompts before loading. Unavailable saved
equipment and progression are retained, and the first subsequent write backs
up the original pilot.

The assembly explicitly overrides `iron_coast_mission_1:campaign`, changing its
mission list from Breakwater alone to missions 1–6. The Mods manager reports
this winning override. Campaign order supplies the next mission when a mission
has no explicit `next` ID, so each mission keeps its own asset root and saved
script identity. Finishing the sixth mission marks it completed and leaves it
available for replay. Disabling the assembly leaves each mission independently
playable. Disabling it while another enabled package needs one of its dependencies
retains that dependency; the confirmation lists the actual affected packages.

## Mission 1: Breakwater

The player raids a coastal industrial harbor. Ten scouts cover the approach,
four ground turrets protect the docks, two destructible supply depots release
repair kits, and the command ship arrives at step 720. Destroy at least two
turrets and the command ship to finish. Surviving turrets stop at y=72 and the boss stays in the playfield until
killed; waiting out the mission duration cannot produce victory. Missing an
early battery does not leave an unreachable required target.

When inventory space allows, the mission grants a trial Pulse Cannon, which
fires alongside forward guns, and three field repairs. The cannon is a mission-only loan and is returned before a successful flight
is saved; a cannon already owned by the pilot remains untouched. A full inventory can still start; new grants are
skipped while existing equipment is preserved. Cycle equipment to **Iron Coast Field Repair** and
press the special button to restore 25 shield per repair. Depots drop extra
repairs. Victory pays 5,000 credits plus ordinary enemy rewards. The central
turrets and boss patrol overlap the starter-gun firing corridor; the mission
is intended to remain playable without the trial weapon.

Script objectives are namespaced and tracked for the current flight. Script
state and completed mission IDs are saved with the pilot:

| Objective | Meaning |
| --- | --- |
| `iron_coast_mission_1:phase` | 1 approach, 2 docks, 3 command ship, 4 complete |
| `iron_coast_mission_1:turrets_required` | Required count of two |
| `iron_coast_turret:defeated` | Turrets destroyed |
| `iron_coast_boss:defeated` | Command ships destroyed |
| `iron_coast_mission_1:depots_opened` | Supply depots destroyed |
| `iron_coast_mission_1:complete` | All required targets destroyed |
| `iron_coast_mission_1:trial_issued` | A loan or an already owned cannon is available |

## Six-mission route

The linked route progresses from the outer harbor to the fleet headquarters.
Every mission requires explicit objectives; reaching its duration never awards
victory. Every mission holds essential structures in the firing area so
missed targets cannot make the rest of a flight impossible. Bosses patrol until
destroyed. Optional scouts and additional enemies pay their normal rewards.

| Mission | Required targets | Completion bonus | Support |
| --- | --- | ---: | --- |
| 1 — Breakwater | Two turrets and one command cruiser | 5,000 | Pulse Cannon loan and three 25-shield field repairs when inventory fits; depot repairs |
| 2 — Tidal Relay | Three radar relays and Relay Warden | 7,500 | Pulse Cannon loan when inventory fits; each destroyed relay restores 12 shield |
| 3 — Saltworks Convoy | Three cargo transports, two escort turrets and Saltbreaker VTOL | 7,500 | Each intercepted transport restores 15 shield; no equipment grant |
| 4 — Stormwall | Four cliff batteries and Stormwall Arsenal | 12,000 | Pulse Cannon loan when inventory fits |
| 5 — Cinder Docks | Two armored foundries and Cinder Hammer | 15,000 | Three selectable 30-shield coolant injectors when inventory fits; outer-lane slag volleys have audible warnings |
| 6 — Iron Crown | Six citadel batteries and two Iron Crown Dreadnoughts, including the final arrival | 30,000 | Ion Lance loan when inventory fits; 25 shield on entry and 20 at each dreadnought phase |

Loaned weapons are returned at mission end; owned weapons remain equipped.
Inventory grants check the twenty-slot limit, including reserve super-shield
modules, and never remove existing equipment to make room. Mission repair
items use normal equipment selection and the **Special** control. Keep **Ctrl**
held to fire, use **Alt** or **Shift** to cycle, **Z** for Special, and **Space**
for a carried bomb with the default bindings.

Missions 2–6 reference original `base:enemy_*` definitions directly. Those foes
retain the original sprite library's flight paths, firing types, animation and
rewards; no mod override substitutes generic downward movement.

Progression records each completed mission and carries shield charge, credits,
equipment and script state into the hangar. The player can buy an original
Energy refill for 10,000 credits to recover 25 shield between sorties. Selecting
a mission directly remains available for replay and independent level mods.

## Art and audio

Original terrain asset `0x10360` and military sprite `0x102f6` were decoded and
inspected before generating the new art with the built-in imagegen skill.
Mission, enemy and weapon packages include generated masters, packaged
SD/HD art, WAV files and prompt/provenance metadata in Git. The assembly owns
its SD/HD campaign portrait; the soundtrack package owns its MUS composition. Original style-reference images remain external; the packaged original
game data is tracked in Git. Mission sources are a generated shoreline texture,
harbor briefing backdrop and transparent supply depot. The source images
remain unchanged; the build step normalizes logical footprints and derives
palette SD versions and HD counterparts.

Mission tiles have 32×32 logical canvases, 32×32 palette SD images and 128×128
HD images. The 288×384 logical shoreline map is converted globally before
cropping into 108 tiles. A reflected copy produces 216 definitions; twelve
forward rows followed by twelve reflected rows give exact matching pixels
at each vertical repetition boundary. This keeps the map continuous but
repeats and reflects port structures. The 72-row mission map uses three such
periods. This is a deliberate first-mission content choice, not unique terrain
for the whole original game.

Briefing/menu art uses a 320×200 logical canvas, with 320×200 SD and 1280×800
HD files. Supply depots preserve a 32×32 collision canvas and transparent
sprite margins; repair icons use 16×16 logical canvases. The asset report
records hashes, palette membership, footprints and repeat-boundary checks.
HD remains constrained by the renderer's indexed palette, so generated color
detail is reduced to the selected palette during play.

Mission audio is original procedural synthesis: approach signal, dock alarm,
boss warning, victory arpeggio, depot impact and repair cue. These are bounded
mono PCM16 WAVs at 22,050 Hz, 0.35–1.2 seconds, made from deterministic
oscillators and seeded noise. No original sound recording, SoundFont or online
audio service is used. The generators and output hashes are tracked. The soundtrack is an original
MUS score played through the same FM synthesizer as the original game music;
its source composition, generated score and provenance are included.

The generated mod assets are included in Git, so a fresh checkout includes
the complete content packages. The original base-game asset catalog is still
required locally to play the game and remains excluded from version control.
To rebuild the mission assets from their included generated masters, run:

```sh
python3 mods/iron_coast_mission_1/build_assets.py --palette ../data/misc/PALETTE_DAT
cargo run --no-default-features -- --mods mods --validate-mods iron_coast_scout,iron_coast_turret,iron_coast_boss,iron_coast_music,pulse_cannon,seeker_swarm,ion_lance,iron_coast_mission_1
```

From `RustRaptor/`, validating the full assembly uses all dependencies explicitly
at the CLI (the in-game Mods manager selects them automatically):

```sh
cargo run --no-default-features -- --mods mods --validate-mods iron_coast_scout,iron_coast_turret,iron_coast_boss,iron_coast_boss_2,iron_coast_boss_3,iron_coast_boss_4,iron_coast_boss_5,iron_coast_boss_6,iron_coast_music,pulse_cannon,seeker_swarm,ion_lance,iron_coast_mission_1,iron_coast_mission_2,iron_coast_mission_3,iron_coast_mission_4,iron_coast_mission_5,iron_coast_mission_6,iron_coast_campaign
```

## Acceptance checks

`tests/iron_coast.rs` loads the standalone Breakwater manifests, definitions
and scripts with synthetic PNG/WAV fixtures and the mod-authored MUS score. It checks dependency activation, artwork
footprints, explicit boss/turret completion gating, one-time victory rewards,
and actual headless runs through the scout waves and boss using starter guns
and the trial Pulse Cannon. These tests use no original images and replace the
generated assets with synthetic fixtures. Local package validation additionally checks
the actual generated SD/HD images and WAV files.

The standalone suite also checks mission-only loan cleanup, preservation of
owned equipment, full-inventory starts, and required turrets remaining reachable
after their scheduled entrance. The full campaign run below exercises the
current Mission 1 package together with the later missions and shared soundtrack.

Release measurements exclude compilation.

`tests/iron_coast_campaign.rs` adds six portable structural checks and one
original-data integration check for the complete route. The portable tests
load the real nineteen manifests, content definitions and Rhai scripts with
synthetic PNG/WAV resources. Referenced native IDs receive labeled registry
placeholders only for these structural checks; their movement is tested using
the original catalog in the separate integration run. Generated artwork and
sound files are checked separately by local package validation. The six portable checks passed in **0.54 seconds** in release mode, excluding
compilation. The suite checks automatic dependency selection, shared dependency retention, independent
mission activation, one explicit campaign override, unchanged mission owners,
full twenty-slot inventory starts, explicit-next priority, deterministic
campaign ordering, terminal replay behavior and versioned pilot save/load.

The original-data headless campaign starts with the registered pilot's 75
shield and 10,000 credits at difficulty 2. It holds fire, moves at most four horizontal
pixels per step toward mission structures, turrets, cruisers and scouts, and
uses actual consumable callbacks when shield is at most 70. It carries damage,
equipment, credits and script state between all six flights and round-trips an
atomic save after each victory. It then replays the finale with the recovered
mission and boss state, verifies both boss deaths and keeps exactly six
completed mission records after another save/load. The harness uses no direct shield refills, enemy-damage commands, invulnerability or
objective mutations. Any Energy refills use the actual shop purchase and are
recorded in the report.

The final nineteen-package release run passed in **19.44 seconds**, excluding
compilation, after every package was frozen and ignored bytecode was removed.
It needed no Energy refills or purchased weapons. All original enemy types
authored into missions 2–6 appeared and moved through their native paths.

| Mission | Completion step | Starting shield | Final shield | Total credits | Native types seen moving |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 — Breakwater | 785 | 75 | 92 | 18,480 | 0 |
| 2 — Tidal Relay | 926 | 92 | 86 | 30,685 | 3 |
| 3 — Saltworks Convoy | 1,290 | 86 | 82 | 43,425 | 4 |
| 4 — Stormwall | 1,217 | 82 | 91 | 61,280 | 6 |
| 5 — Cinder Docks | 1,818 | 91 | 89 | 84,510 | 6 |
| 6 — Iron Crown | 2,428 | 89 | 100 | 122,705 | 6 |

The recovered finale replay also completed in **2,428 steps** with **100 shield**,
bringing credits to **160,900**. Both dreadnought deaths were required again,
and the completed mission list stayed at six entries. Pilot saves and loads
preserved the exact active package versions, hashes, inventory, script state
and script RNG after every flight and the replay. The local JSON report records
these package pins, objectives, native movement metadata and state digests.

The machine-readable report can be captured locally with:

```sh
RAPTOR_TEST_DATA=../data RAPTOR_IRON_COAST_REPORT=../.reference/iron-coast-six-level.json cargo test --locked --release --no-default-features --test iron_coast_campaign -- --ignored --nocapture
```

A passing original-data run establishes a viable continuous route using
ordinary controls and campaign-provided support. It does not establish balance
for every loadout, difficulty or normal-player route. Each individual mission also includes its
own acceptance runner and generated asset provenance.

Visual approval remains provisional: sprite and terrain previews were
inspected for readability, canvas alignment and transparency, with numeric
palette and repeat-seam checks. Wider player testing should assess difficulty,
audio balance and HD details during normal play before treating the new art
as final. These packages extend the Rust engine; they do not establish full
parity across the original campaigns.
