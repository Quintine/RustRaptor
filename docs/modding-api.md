# Rust modding API, version 1

This is an experimental API for the Rust engine. It provides local content packages, deterministic Rhai callbacks, checked commands, an in-game manager and save compatibility checks. The rewrite is still undergoing gameplay parity work; this document describes the implemented API, not a claim that the full remaster has passed its acceptance checks. API compatibility is currently exact: `api_version = 1`.

## Try the example

`examples/mods/aurora/` adds two projectiles, a pulse cannon, a repair cell, two enemies, a mission and a campaign. The weapon adds angled shots in Rhai; enemy movement, item rewards and mission objectives also use scripts. Its artwork references asset IDs in the locally extracted original catalog. The example contains no original or generated game artwork.

Validate the package against your original game data:

```sh
cargo run --no-default-features -- --data data --mods examples/mods --validate-mods aurora
```

Run its mission without a window:

```sh
cargo run --no-default-features -- --data data --mods examples/mods \
  --enabled aurora --headless aurora:field_trials --ticks 700
```

For the in-game manager, copy `examples/mods/aurora` into the `mods/` directory under `$XDG_DATA_HOME/RaptorReplica` (default `~/.local/share/RaptorReplica/mods/`), or start the Rust engine with `--mods examples/mods`. Open **Mods**, toggle Aurora, then select **Apply selections**. Select its mission from the mission menu. Existing pilots can add mods while preserving required versions, hashes and relative load order; the next save records the expanded active set. Disabling, changing or reordering required mods blocks loading with details. Use another pilot for an incompatible set.

In the Mods screen, Enter toggles a package or activates the selected action. Rescan after editing a package on disk. Load dependencies before dependents; independent packages retain your chosen priority. Later explicit overrides win. Changes made through the pause menu remain pending until the main menu. Candidate registries and scripts are validated before the active set changes.

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

IDs use lowercase ASCII letters, digits, `_` and `-`, with a maximum of 64 bytes. `base` is reserved. Package versions and dependency requirements use semantic version syntax. Dependencies must be explicitly enabled; the loader will not quietly enable or install them. Cycles, missing packages, unsupported API versions, incompatible dependency versions and declared conflicts reject activation. Two installed folders claiming the same ID make that ID unusable; rename or remove one folder, then rescan.

All package paths are relative. Absolute paths, parent traversal, symlinks and special files are rejected. Packages are limited to 10,000 files, 16 directory levels, 64 MiB per file and 256 MiB in total. Manifests are limited to 64 KiB; display names to 128 bytes; descriptions to 4 KiB; script declarations to 64, with a 1 MiB limit per source file. Every file, including artwork and documentation, contributes to the package SHA-256 hash. A package changed after discovery requires rescanning before it can be applied.

## Content definitions and overrides

`content.json` has optional `weapons`, `items`, `enemies`, `missions`, `campaigns`, `sounds` and `overrides` arrays. Unknown fields are rejected. IDs have the form `namespace:name`, for example `aurora:pulse_cannon`. IDs are stable save references and unique across content types. Keep item and projectile IDs distinct: the item `aurora:pulse_cannon` refers to the weapon/projectile `aurora:pulse_projectile` through its `weapon` property.

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
| Weapon/projectile | Damage, integer speed, cooldown in simulation ticks, targeting (`air`, `ground`, `all`), behavior (`straight`, `homing`, `beam`, `spread`, `bomb`, `energy_grab`), firing offsets, optional animation and script. Scripts can emit additional projectiles with explicit velocity. |
| Item | Price, maximum and initial count, optional weapon, shield/credit effects, consumable/special flags, artwork and script. `initial_count` controls how many units a purchase or pickup adds. |
| Enemy | Health, speed, rewards, air/ground and boss flags, firing cooldown, path points and repeat flag, weapon, dropped item, animation and script. Scripts can query entities and change enemy movement. |
| Mission | Duration, `auto_complete` (default true), optional briefing artwork, ordered tick-based spawns, terrain tile definitions and row-major layout, column count, next mission, optional music asset and script. Scripts can manage objectives, spawn waves and decide success/failure. |
| Campaign | Name, optional menu artwork and ordered mission IDs. Missions and campaigns appear through the same registries as original content. |

Simulation uses integer coordinates in the original 320×200 logical canvas and runs at 70/3 Hz: one tick is 3/70 seconds. Artwork detail does not enlarge collision boxes. Script movement and projectile speed are bounded to 128 logical pixels per tick; spawn and movement coordinates must stay within ±32,768.

JSON Schemas are checked into `schemas/`: `mod-v1.json`, `content-v1.json`, `hook-v1.json`, `weapon-projectile-v1.json`, `item-v1.json`, `enemy-v1.json`, `mission-v1.json` and `campaign-v1.json` and `sound-v1.json`. Schemas describe serialization shape; the validation CLI also checks references, numeric limits, package paths, dependencies, artwork and script compilation. Generate them from the Rust types with:

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

PNG animations are horizontal strips of equally sized frames. For example, four 64×64 frames use a 256×64 PNG and may declare logical dimensions of 16×16. The strip width must divide evenly by `frames`; supply consistent canvases and alignment across frames. Alpha below 128 is transparent. Opaque colors are mapped to the selected game palette so palette effects remain compatible. Artwork already detailed enough for the selected rendering scale bypasses automatic sprite enlargement. Original asset animations use consecutive catalog IDs. Terrain artwork and destroyed terrain replacements follow the same format.

Artwork dimensions and decoding allocation are bounded. PNGs may be up to 4096 pixels in either direction, with at most 4,194,304 pixels and a 64 MiB decoding allocation limit. Logical dimensions are separately validated and stay independent of physical PNG resolution. The extracted original catalog and local base-game remaster proofs stay outside version control; authored mod artwork and sounds are included in Git.

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
| `on_fire` | Weapon or firing enemy: `entity`, `x`, `y`, `hostile`, `tick`; enemy callbacks also include `weapon`. Player entity is zero. The normal shot has already been emitted. Enemy callbacks run for each emitted gun shot. |
| `on_hit` | Weapon/projectile and damaged enemy: `entity`, `projectile`, `damage`, `x`, `y`; enemy events also include `weapon` and remaining `health`. Scripted enemy damage uses `scripted = true` and omits projectile-specific fields. |
| `on_death` | Enemy: `entity`, `x`, `y`. The entity is retired; use queries to act on surviving entities. |
| `on_pickup` | Item: pickup `entity`. The item and its standard effects have already been awarded. |
| `on_use` | Selected special item without a weapon: player `entity = 0`, `x`, `y`, `tick`. Triggered on the rising edge of special input; standard effects and consumption happen first. |
| `on_mission_start` | Mission: `tick = 0`. Runs when the first simulation step dispatches events. |
| `on_mission_end` | Mission: `success`, `tick`. |

Every dispatched event also includes `tick`, `player`, `entities`, `projectiles`, `pickups` and `objectives`. `player` is a snapshot including position, velocity, shields, credits, inventory and selected equipment. `entities` is the current enemy array; each entry includes `entity`, `definition`, position, health, animation and movement state. Projectiles and pickups likewise carry stable entity IDs. These are read-only snapshots: return commands to change the simulation. Later callbacks in a tick can observe commands committed by earlier callbacks. Events raised by commands, such as a spawned enemy, are dispatched on the following tick.

`state` is JSON-serializable and shared by all callbacks in the same script file. It starts as an empty map, is keyed by `mod_id/script_path`, and is saved with the pilot. Avoid values dependent on wall time, filesystem access or rendering rate. `random` contains 32 deterministic nonnegative integers in the range 0–32,767. Each successful callback advances that script's saved RNG by exactly 32 values, whether or not the script reads them. Missing callbacks do not advance state or RNG.

Commands apply only after a callback returns and passes validation. If a callback or any command fails, the complete simulation tick restores its previous world, script state and script RNG. Runtime errors identify the mod, source file, callback and Rhai source location when available. In the desktop engine a script failure returns to the pause screen with the error; fix the package, rescan and reload at the main menu.

## Commands

Use the `op` field shown below. All fields listed are required unless stated otherwise. Entity zero identifies the player for damage; movement commands currently address enemies.

| `op` | Fields | Effect |
| --- | --- | --- |
| `spawn` | `enemy`, `x`, `y` | Spawn a registered enemy. |
| `projectile` | `weapon`, `x`, `y`, `vx`, `vy`, optional `hostile` (false) | Spawn a projectile using a registered weapon. |
| `damage` | `entity`, `amount` | Deal 0–100,000 damage to the player or an existing enemy. |
| `despawn` | `entity` | Remove an existing enemy or projectile. |
| `move` | `entity`, `x`, `y` | Move an enemy and rebase its movement path. |
| `velocity` | `entity`, `vx`, `vy` | Set enemy velocity. |
| `give_item` | `item`, `count` | Add registered inventory, clamped to item capacity; adding a new entry beyond the 20-item limit fails. |
| `consume_item` | `item`, `count` | Remove owned inventory; insufficient quantity fails. |
| `credits` | signed `amount` | Adjust credits with saturation at valid limits. |
| `shield` | signed `amount` | Adjust ordinary shield, clamped to 0–100. |
| `effect` | `x`, `y` | Add an explosion effect. |
| `sound` | numeric `asset` | Queue an original digital sound asset for playback. |
| `play_sound` | namespaced `sound` ID | Queue a validated package-local sound. |
| `objective` | `key`, integer `value` | Set an objective counter. Use a namespaced key. |
| `complete` | none | Complete the mission. |
| `fail` | none | Fail the mission. |

Rhai uses an explicit package allowlist for arithmetic, strings, collections, iteration and function helpers. The default language/time packages are excluded, so wall-clock timestamps and native `sleep` cannot be reached, including through function pointers. There are no exposed filesystem, network or OS interfaces. Dynamic `eval` and imports are disabled. Limits are 100,000 operations per callback and a shared 500,000-operation budget per simulation tick; 32 call levels; expression depths of 64/32; arrays of 4,096 entries; maps of 1,024 entries; strings of 16 KiB; 256 commands per callback; and 64 KiB of serialized state per script. See the [Rhai execution-limit API](https://docs.rs/rhai/latest/rhai/struct.Engine.html) for the underlying engine controls. Scripts cannot increase these limits.

## Saves and compatibility

Rust pilots use separate, versioned JSON files under `$XDG_DATA_HOME/RaptorReplica`, and settings use TOML under `$XDG_CONFIG_HOME/RaptorReplica`. Atomic writes replace completed saves after file and directory synchronization. Legacy saves are read and imported; their original bytes are not modified.

Each pilot records the ordered mod IDs, package versions, full content hashes, script states and script RNG positions. Loading requires the same active pins and all referenced equipment, missions and progression. Changing a package without changing its version still changes its hash and blocks that save. Disabling a mod preserves its saved inventory and progression; it never silently discards them. Restore the matching package/version and load order, or use another pilot. This API does not yet provide mod save migrations.

## Validation tests

`cargo test --no-default-features --test modding` uses synthetic definitions and temporary packages. It checks dependency ordering, version/API failures, conflicts, cycles, duplicate namespaces, changed hashes, traversal/symlinks, file/depth limits, explicit override priority, registry rollback, script budgets, command failure rollback, RNG resumption, incompatible saves and example callbacks. These tests do not require the original game assets. The validation CLI above provides local integration coverage against the separately installed asset catalog.

## SD/HD artwork and local sound effects

An artwork definition may add `hd_png`, a separate package-relative PNG with the same logical canvas, frame count and aspect ratio as the SD `png` or original `asset`. HD inputs require at least twice the logical resolution. The Options HD toggle selects it; missing variants retain SD artwork. Detailed mod terrain is drawn on the higher-resolution canvas over the joined SD fallback. Authored mod art/audio is included in Git; original catalog references remain excluded.

`sounds` definitions have `id`, `name`, `file` (relative path) and optional `volume` (0–127, default127), `pan` (0–255, default127), `pitch` (0–255, default128) and `priority` (0–100000, default1). Lower numeric priority wins, matching the original DSP. Play one with `#{op:"play_sound",sound:"your_mod:shot"}`. WAV inputs must be uncompressed PCM8/16, mono/stereo, 8–48kHz, at most30seconds/8MiB. Stereo is mixed to mono and converted to the original unsigned8-bit digital format; channel/pan/pitch/volume use the original mixer. Original DMX patches are also accepted. Invalid/missing audio rejects activation.

For objective-driven missions set `auto_complete=false` and explicitly return `complete` or `fail`. Scripted endings dispatch `on_mission_end` in the same transaction. Commands can create further hook events, bounded by the shared execution budget and an8192-event tick limit.
