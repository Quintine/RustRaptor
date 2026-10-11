# Rust modding API, version 1

This is an experimental API for the Rust engine. It provides local content packages, deterministic Rhai callbacks, checked commands, an in-game manager and save compatibility checks. The rewrite is still undergoing gameplay parity work; this document describes the implemented API, not a claim that the full remaster has passed its acceptance checks. API compatibility is currently exact: `api_version = 1`.

## Try the example

`mods/aurora/` adds two projectiles, a pulse cannon, a repair cell, two enemies, a mission and a campaign. The weapon adds angled shots in Rhai; enemy movement, item rewards and mission objectives also use scripts. Its artwork references asset IDs in the locally extracted original catalog. The example contains no original or generated game artwork.

Validate the package against your original game data:

```sh
cargo run --no-default-features -- --data data --mods mods --validate-mods aurora
```

Run its mission without a window:

```sh
cargo run --no-default-features -- --data data --mods mods \
  --enabled aurora --headless aurora:field_trials --ticks 700
```

The manager discovers the bundled `mods/` folder by default when no user mods folder exists. You can also copy `mods/aurora` into the `mods/` directory under `$XDG_DATA_HOME/RaptorReplica` (default `~/.local/share/RaptorReplica/mods/`), or start the Rust engine with `--mods mods`. Open **Mods**, toggle Aurora, then select **Apply selections**. Select its mission from the mission menu. Existing pilots can add mods while preserving required versions, hashes and relative load order; the next save records the expanded active set. Disabling, changing or reordering required mods shows compatibility details and asks whether to load anyway. Missing equipment and progression remain saved until their packages are restored.

In the Mods screen, Enter toggles a package or activates the selected action. Enabling a package immediately checks versions, API compatibility, cycles and conflicts, then selects its installed dependencies recursively. A failed check leaves the selection unchanged. Disabling includes dependent mods and dependencies that become unused, preserving dependencies required by other remaining packages. A single-package disable toggles immediately; changes affecting multiple packages show an **Are you sure?** popup listing every affected mod, with Cancel selected initially. Cancel or Back preserves the pending selection. Rescan after editing a package on disk. Dependencies load before dependents; independent packages retain your chosen priority. Later explicit overrides win. Changes made through the pause menu remain pending until the main menu. Candidate registries and scripts are validated before the active set changes.

## Package layout and manifest

```text
mods/
  aurora/
    mod.toml
    content.json
    scripts/
      weapon.rhai
    art/
      cannon.png
```

```toml
id = "aurora"
name = "Aurora Field Trials"
version = "1.0.0"
api_version = 1
content = "content.json"
scripts = ["scripts/weapon.rhai"]
description = "A new weapon and mission."
conflicts = ["alternate_aurora"]

[dependencies]
common_tools = "^1.2"
```

IDs use lowercase ASCII letters, digits, `_` and `-`, with a maximum of 64 bytes. `base` is reserved. Package versions and dependency requirements use semantic version syntax. The in-game manager selects compatible installed dependencies when enabling a package. It never downloads or installs missing packages. The CLI still requires a complete explicit `--enabled` set. Cycles, missing packages, unsupported API versions, incompatible dependency versions and declared conflicts reject activation. Two installed folders claiming the same ID make that ID unusable; rename or remove one folder, then rescan.

All package paths are relative. Absolute paths, parent traversal, symlinks and special files are rejected. Filenames must be UTF-8 and cannot contain literal backslashes or colons. Hashes use forward-slash paths and UTF-8 component ordering on both Linux and Windows, preserving existing Linux save pins. Keep the original file bytes when copying packages between systems; the repository disables line-ending conversion for mods. Packages are limited to 10,000 files, 16 directory levels, 64 MiB per file and 256 MiB in total. Manifests are limited to 64 KiB; display names to 128 bytes; descriptions to 4 KiB; script declarations to 64, with a 1 MiB limit per source file. Every file, including artwork and documentation, contributes to the package SHA-256 hash. A package changed after discovery requires rescanning before it can be applied.

## Content definitions and overrides

`content.json` has optional `weapons`, `items`, `enemies`, `missions`, `campaigns`, `sounds`, `music` and `overrides` arrays. Unknown fields are rejected. IDs have the form `namespace:name`, for example `aurora:pulse_cannon`. IDs are stable save references and unique across content types. Keep item and projectile IDs distinct: the item `aurora:pulse_cannon` refers to the weapon/projectile `aurora:pulse_projectile` through its `weapon` property.

Items may include an optional `description` of up to 4096 UTF-8 bytes for shop information. The shop displays the description, artwork, effective target types, firing mode, price, ownership and inventory limits.

The item price buys `initial_count` units, up to its capacity. Selling an
ordinary item removes one unit and returns half its unit purchase price,
rounded down. Original energy refills and super-shield modules retain their
half-price sale per refill/module. This prevents multi-unit mod packs from
creating credits through repeated buying and selling.

New definitions must belong to the package namespace. An existing definition may be replaced only when its ID appears in `overrides` and the replacement retains the same content type. Overrides are complete replacements, not field merges. An override targeting a missing ID, a replacement without explicit permission, an override without its replacement, or duplicate IDs within a pack rejects the whole pack. The manager exposes the override history and its winning owner.

```json
{
  "overrides": ["base:projectile_forward_guns"],
  "weapons": [{
    "id": "base:projectile_forward_guns",
    "name": "Modified Forward Guns",
    "damage": 2,
    "speed": 8,
    "cooldown": 2,
    "behavior": "straight",
    "target": "air",
    "offsets": [[-8, 0], [8, 0]]
  }]
}
```

`legacy` fields exist to map original numeric definitions into the base registries. New mods should omit them: they select legacy engine behavior and are not a general scripting extension mechanism.

| Definition | Properties and behavior |
| --- | --- |
| Weapon/projectile | Damage, integer speed, cooldown in simulation ticks, targeting (`air`, `ground`, `all`), behavior (`straight`, `homing`, `beam`, `spread`, `bomb`, `energy_grab`, `scripted`), firing offsets, optional animation and script. Scripts can emit additional projectiles with explicit velocity. `scripted` requires a script and emits no automatic projectile. |
| Item | Price, maximum and initial count, optional weapon, shield/credit effects, consumable/special flags, artwork and script. `initial_count` controls how many units a purchase or pickup adds. |
| Enemy | Health, speed, rewards, air/ground and boss flags, firing cooldown, path points and repeat flag, weapon, dropped item, animation and script. Scripts can query entities and change enemy movement. |
| Mission | Duration, `auto_complete` (default true), optional briefing artwork, ordered tick-based spawns, terrain tile definitions and row-major layout, column count, next mission, optional legacy music asset or namespaced `music_track`, and script. Scripts can manage objectives, spawn waves and decide success/failure. |
| Campaign | Name, optional menu artwork and ordered mission IDs. Missions and campaigns appear through the same registries as original content. |
| Music | Namespaced ID, display name, package-relative MUS file and `looping` (default true). Mission `music_track` references this ID; playback uses original GENMIDI FM and the Music volume control. |

For non-legacy missions, an explicit `next` takes priority. Otherwise progression
uses the following entry in the first containing campaign, ordered by stable
campaign ID. The last stage stays selected for replay, and completing it again
does not duplicate its completion record. This lets an optional assembly mod
join independently owned missions without overriding their scripts or artwork.

Simulation uses integer coordinates in the original 320×200 logical canvas and runs at 70/3 Hz: one tick is 3/70 seconds. Artwork detail does not enlarge collision boxes. Script movement and projectile speed are bounded to 128 logical pixels per tick; spawn and movement coordinates must stay within ±32,768.

JSON Schemas are checked into `schemas/`: `mod-v1.json`, `content-v1.json`, `hook-v1.json`, `weapon-projectile-v1.json`, `item-v1.json`, `enemy-v1.json`, `mission-v1.json`, `campaign-v1.json`, `sound-v1.json` and `music-v1.json`. Schemas describe serialization shape; the validation CLI also checks references, numeric limits, package paths, dependencies, artwork and script compilation. Generate them from the Rust types with:

```sh
cargo run --no-default-features -- --schemas schemas
```

## Artwork

An `art` object requires exactly one of `asset` (an original numeric catalog ID) or `png` (a package-relative PNG path), plus `logical_width` and `logical_height`. `frames` defaults to 1. `nearest = true` opts that artwork out of Scale2x/3x/4x filtering.

```json
{
  "png": "art/cannon.png",
  "logical_width": 16,
  "logical_height": 16,
  "frames": 4
}
```

PNG animations are horizontal strips of equally sized frames. For example, four 64×64 frames use a 256×64 PNG and may declare logical dimensions of 16×16. The strip width must divide evenly by `frames`; supply consistent canvases and alignment across frames. Alpha below 128 is transparent. Opaque colors are mapped to ordinary entries 0–239 of the selected game palette. Plain PNGs carry no palette-animation labels, so their highlights cannot acquire reserved water, fire or blinking indices 240–255. Artwork already detailed enough for the selected rendering scale bypasses automatic sprite enlargement. Original asset animations use consecutive catalog IDs and retain their native palette labels. Terrain artwork and destroyed terrain replacements follow the same format.

Artwork dimensions and decoding allocation are bounded. PNGs may be up to 4096 pixels in either direction, with at most 4,194,304 pixels and a 64 MiB decoding allocation limit. Logical dimensions are separately validated and stay independent of physical PNG resolution. The packaged original catalog, approved runtime remasters and authored mod artwork/sounds are included in Git; working remaster proofs and source references remain external.

## Rhai callbacks

Every callback takes `(event, state, random)` and returns a map containing `commands` and `state`. All scripts referenced by definitions must appear in `manifest.scripts`. A missing optional callback does nothing; a declared callback with the wrong parameter count is rejected during compilation.

```javascript
fn on_fire(event, state, random) {
    let shots = if state.contains("shots") { state.shots + 1 } else { 1 };
    #{
        commands: [#{
            op: "projectile",
            weapon: "aurora:pulse_projectile",
            x: event.x,
            y: event.y,
            vx: (random[0] % 3) - 1,
            vy: -8
        }],
        state: #{ shots: shots }
    }
}
```

| Callback | Definition and event fields |
| --- | --- |
| `on_spawn` | Enemy: `entity`, `x`, `y`. |
| `on_tick` | Enemy: `entity`, `x`, `y`, `health`, `tick`, `player_x`, `player_y`. Mission: `tick`, `player_x`, `player_y`. |
| `on_fire` | Weapon or firing enemy: `entity`, `x`, `y`, `hostile`, `tick`; enemy callbacks also include `weapon`. Player entity is zero. The normal shot has already been emitted, except for `scripted` weapons, whose script supplies all attacks. Enemy callbacks run for each gun discharge. |
| `on_hit` | Weapon/projectile and damaged enemy: `entity`, `projectile`, `damage`, `x`, `y`; enemy events also include `weapon` and remaining `health`. Scripted enemy damage uses `scripted = true` and omits projectile-specific fields. |
| `on_death` | Enemy: `entity`, `x`, `y`. The entity is retired; use queries to act on surviving entities. |
| `on_pickup` | Item: pickup `entity`. The item and its standard effects have already been awarded. |
| `on_use` | Selected special item without a weapon: player `entity = 0`, `x`, `y`, `tick`. Triggered on the rising edge of special input; standard effects and consumption happen first. |
| `on_mission_start` | Mission: `tick = 0`. Runs when the first simulation step dispatches events. |
| `on_mission_end` | Mission: `success`, `tick`. |

Every dispatched event also includes `tick`, `player`, `entities`, `projectiles`, `pickups` and `objectives`. `player` is a snapshot including position, velocity, shields, credits, inventory and selected equipment. `entities` is the current enemy array; each entry includes `entity`, `definition`, position, `width`, `height`, health, animation, movement state and the definition's `ground` boolean. Filter on `ground` when an attack affects only airborne or ground targets. Projectiles and pickups likewise carry stable entity IDs. These are read-only snapshots: return commands to change the simulation. Later callbacks in a tick can observe commands committed by earlier callbacks. Events raised by commands, such as a spawned enemy, are dispatched in subsequent batches of the same tick, within the 8,192-event limit. Rejected command batches report the mod, script path and callback, and roll back that simulation step and script state.

Use `behavior: "scripted"` for hitscan, chain lightning, proximity zaps or other attacks implemented entirely with commands. Player selection, firing input and weapon cooldowns still apply. An owned item with `special: false` fires its weapon alongside other ordinary equipment when Fire is held; `special: true` makes it selectable. Neither player nor enemy scripted weapons receive a default engine projectile. A script may explicitly emit `projectile`, or pair `damage` with `arc` for an immediate visible discharge. `target` describes the weapon's capability for the shop and governs explicit projectiles; scripts must enforce the intended targets and range for their own `damage` commands.

`state` is JSON-serializable and shared by all callbacks in the same script file. It starts as an empty map, is keyed by `mod_id/script_path`, and is saved with the pilot. Avoid values dependent on wall time, filesystem access or rendering rate. `random` contains 32 deterministic nonnegative integers in the range 0–32,767. Each successful callback advances that script's saved RNG by exactly 32 values, whether or not the script reads them. Missing callbacks do not advance state or RNG.

Commands apply only after a callback returns and passes validation. If a callback or any command fails, the complete simulation tick restores its previous world, script state and script RNG. Runtime errors identify the mod, source file, callback and Rhai source location when available. In the desktop engine a script failure returns to the pause screen with the error; fix the package, rescan and reload at the main menu.

## Commands

The 20-slot inventory limit counts physical super-shield modules separately.
`player.super_shield_reserves` lists the stored charge of reserve modules;
`player.inventory["base:super_shield"]` is the equipped module's charge.
For the built-in `base:energy` and `base:super_shield`, `give_item` and
`consume_item` change charge units, not the number of modules. Zero-charge
shield entries remain valid. Other items are removed when their quantity
reaches zero, releasing their slot and selecting another available special
item when needed.

Use the `op` field shown below. All fields listed are required unless stated otherwise. Entity zero identifies the player for damage; movement commands currently address enemies.

| `op` | Fields | Effect |
| --- | --- | --- |
| `spawn` | `enemy`, `x`, `y` | Spawn a registered enemy. |
| `projectile` | `weapon`, `x`, `y`, `vx`, `vy`, optional `hostile` (false) | Spawn a projectile using a registered weapon. |
| `damage` | `entity`, `amount` | Deal 0–100,000 damage to the player or an existing enemy. |
| `despawn` | `entity` | Remove an existing enemy or projectile. |
| `move` | `entity`, `x`, `y` | Move an enemy and rebase its movement path. |
| `velocity` | `entity`, `vx`, `vy` | Set enemy velocity. |
| `animation` | `entity`, `frame` (integer or null) | Pin the displayed frame of an existing nonlegacy enemy. The zero-based frame must be below its artwork's declared `frames`; null resumes automatic animation. |
| `give_item` | `item`, `count` | Add registered inventory, clamped to item capacity; adding a new entry beyond the 20-item limit fails. |
| `consume_item` | `item`, `count` | Remove owned inventory; insufficient quantity fails. |
| `credits` | signed `amount` | Adjust credits with saturation at valid limits. |
| `shield` | signed `amount` | Adjust ordinary shield, clamped to 0–100. |
| `effect` | `x`, `y`, optional `kind` (`air_blast`) | Add a native effect at a bounded position. Kinds: `ground_blast`, `small_ground`, `large_air`, `medium_air`, `small_air`, `air_blast`, `energy`, `person`, `platoon`, `flare`, `sparkle`. |
| `arc` | `x`, `y`, `to_x`, `to_y`, optional `ticks` (3), `anchor`, `to_anchor` | Draw cosmetic branching lightning with a hot white core, blue glow and flicker between two positions. Optional anchors are player (`0`) or existing enemy entity IDs. Endpoints must be within ±32,768; lifetime must be 1–12 simulation ticks; at most 256 arcs may be active. Pair with `damage` to attack. |
| `sound` | numeric `asset` | Queue an original digital sound asset for playback. |
| `play_sound` | namespaced `sound` ID | Queue a validated package-local sound. |
| `objective` | `key`, integer `value` | Set an objective counter. Use a namespaced key. |
| `complete` | none | Complete the mission. |
| `fail` | none | Fail the mission. |

`animation` supports visible boss phases without changing their collision
canvas, movement, firing cadence or gameplay RNG. It requires an enemy with
declared artwork and rejects original legacy enemies. A selected frame stays
visible across simulation ticks until another command changes it or supplies
null. Enemy snapshots include `pinned_art_frame` while a frame is selected.
The override survives serialization of a world; pilots save the script state
that determines the phase, and mission scripts should reset/reapply it at the
appropriate spawn or mission-start callback. No live mission snapshot is
implied by pilot saving. Invalid entities or frames roll back the whole command
batch and callback tick like other command failures.

Lightning arcs render in both SD and HD using irregular fractal channels, thin tapered forks and glow that brightens the scene. Geometry and brightness change with simulation age; each discharge receives a cosmetic seed derived from its creation tick and queue position so repeated shots vary. Drawing the same simulation state again gives the same image, and pausing freezes the effect. Arcs persist until their simulation lifetime expires. Forks are visual only and do not hit additional targets. Arcs use a separate cosmetic pool and consume no gameplay RNG, entity IDs or projectile capacity. The pool is excluded from saves and the gameplay digest. Invalid endpoints, lifetime or capacity reject the complete command batch and roll back the tick like other command failures.

`anchor` attaches the starting endpoint, and `to_anchor` independently attaches the destination. Supply absolute world coordinates at creation; each endpoint preserves its offset from the anchor's top-left `x/y` origin as the ship moves. Omitting an anchor keeps that endpoint fixed. Both anchors may be `0` to make a ring segment follow the player, or use `anchor: 0` and `to_anchor: enemy.entity` for a ship-to-ship bolt. Anchor IDs must exist when the command runs; a missing anchor rejects the batch. Endpoints update after simulation movement and API movement commands, and freeze at their last position when the anchored enemy disappears. Cosmetic coordinates clamp to ±32,768 when an attached ship moves beyond those bounds.

Rhai uses an explicit package allowlist for arithmetic, strings, collections, iteration and function helpers. The default language/time packages are excluded, so wall-clock timestamps and native `sleep` cannot be reached, including through function pointers. There are no exposed filesystem, network or OS interfaces. Dynamic `eval` and imports are disabled. Limits are 100,000 operations per callback and a shared 500,000-operation budget per simulation tick; 32 call levels; expression depths of 64/32; arrays of 4,096 entries; maps of 1,024 entries; strings of 16 KiB; 256 commands per callback; and 64 KiB of serialized state per script. See the [Rhai execution-limit API](https://docs.rs/rhai/latest/rhai/struct.Engine.html) for the underlying engine controls. Scripts cannot increase these limits.

## Saves and compatibility

Rust pilots use separate, versioned JSON files under `$XDG_DATA_HOME/RaptorReplica`, and settings use TOML under `$XDG_CONFIG_HOME/RaptorReplica`. Atomic writes replace completed saves after file and directory synchronization. Legacy saves are read and imported; their original bytes are not modified.

Each pilot records the ordered mod IDs, package versions, full content hashes, script states and script RNG positions. The load screen reports missing packages, changed versions or hashes, changed required load order, and unavailable equipment or missions. Changing a package without changing its version still changes its hash and therefore requires confirmation. Cancel leaves the current pilot and original save untouched; choosing to load accepts the differences for that pilot session.

Unavailable equipment stays in the pilot's inventory with its saved quantity and occupies its original inventory slots, but cannot be fired, selected or traded until its definition is available. Unavailable completed missions remain recorded. If the saved current mission is missing, choose an available mission in the hangar before flying. Runtime saves retain inactive package pins, script state and script RNG alongside the active packages, so restoring a disabled package can recover its data. Current active versions and hashes are recorded after an accepted load is successfully saved; the original save is backed up before its first replacement. Structural corruption, unsupported save versions and invalid IDs still cannot be loaded. This API does not yet provide scripted mod save migrations, so a changed script must handle its earlier serializable state.

For Rust tooling, `Pilot::inspect_load` returns the unmodified pilot and a structured `SaveCompatibility` report. `Pilot::load` remains strict for callers that require a fully matching environment. Only consume `PilotLoad::confirm_load` after explicit acceptance. Use `validate_tolerant` and `complete_mission_tolerant` for that accepted session, and `merge_runtime_snapshot` to retain saved state and pins belonging to inactive packages.

## Validation tests

`cargo test --no-default-features --test modding` uses synthetic definitions and temporary packages. It checks dependency ordering, version/API failures, conflicts, cycles, duplicate namespaces, changed hashes, traversal/symlinks, file/depth limits, explicit override priority, registry rollback, script budgets, command failure rollback, RNG resumption, incompatible saves and example callbacks. These tests do not require the original game assets. The validation CLI above provides local integration coverage against the separately installed asset catalog.

## SD/HD artwork and local sound effects

An artwork definition may add `hd_png`, a separate package-relative PNG with the same logical canvas, frame count and aspect ratio as the SD `png` or original `asset`. HD inputs require at least twice the logical resolution. The Options HD toggle selects it; missing variants retain SD artwork. Detailed mod terrain is drawn on the higher-resolution canvas over the joined SD fallback. Authored mod art/audio is included in Git; original catalog references remain excluded.

`sounds` definitions have `id`, `name`, `file` (relative path) and optional `volume` (0–127, default127), `pan` (0–255, default127), `pitch` (0–255, default128) and `priority` (0–100000, default1). Lower numeric priority wins, matching the original DSP. Play one with `#{op:"play_sound",sound:"your_mod:shot"}`. WAV inputs must be uncompressed PCM8/16, mono/stereo, 8–48kHz, at most30seconds/8MiB. Stereo is mixed to mono and converted to the original unsigned8-bit digital format; channel/pan/pitch/volume use the original mixer. Original DMX patches are also accepted. Invalid/missing audio rejects activation.

For objective-driven missions set `auto_complete=false` and explicitly return `complete` or `fail`. Scripted endings dispatch `on_mission_end` in the same transaction. Commands can create further hook events, bounded by the shared execution budget and an8192-event tick limit.


## Package mission music

Register a track in the optional `music` array. A music definition contains `id`, `name`, a package-relative `.mus` `file` and optional `looping` (default `true`). A mission selects it with `music_track`; setting both `music_track` and legacy numeric `music` rejects activation. Declare a dependency on a separate music package so enabling the mission also selects its installed soundtrack. Music IDs use the same namespace, duplicate and explicit-override rules as other content. Winning overrides resolve their score from the winning package.

```json
{
  "music": [{"id":"your_mod:theme", "name":"Mission theme", "file":"music/theme.mus", "looping":true}],
  "missions": [{"id":"your_mod:mission", "name":"New mission", "duration":2000, "music_track":"your_mod:theme"}]
}
```

Only checked MUS scores are accepted, played through the original GENMIDI FM synthesizer and the **Music volume** control. Digital effects keep their separate volume. External MIDI and SoundFont playback remain deferred. Scores are limited to 128 KiB, 16,384 events, 256 events per service tick and 30 minutes of score time. The MUS header, event types, controller values, primary-channel count and end marker are checked by the existing decoder. Zero-duration scores, missing files, escaping paths, invalid scores and unsupported formats reject activation with the package/file identified. Score bytes participate in the normal mod hash and pilot compatibility checks. A bounded score cache is cleared when mods are applied.

The selected track starts with the mission, honors its loop flag, and can be scheduled before the SDL device is ready. Selecting the same active track preserves playback position; ordinary menus and classic cinematics select their original tracks. See [music validation](music-validation.md) for the registry, file, volume, loop and device-attachment checks.
