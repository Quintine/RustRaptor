# Iron Coast content packages

Iron Coast is a local campaign assembled from seven independently toggleable
mods. Enable all six dependencies before enabling the campaign package. The
Mods manager validates versions and dependency order and applies the change
at the main menu. The new weapons can also be used in the original campaigns;
the enemy packages can be referenced from other missions.

| Package | Content |
| --- | --- |
| `iron_coast_mission_1` | Breakwater mission, campaign, supply depots, field repairs, terrain, briefing art and mission audio |
| `iron_coast_scout` | Airborne scout, weaving AI, projectiles, art and audio |
| `iron_coast_turret` | Ground turret, aimed firing, projectiles, art and audio |
| `iron_coast_boss` | Harbor command ship, persistent patrol and fan volleys, art and audio |
| `pulse_cannon` | Primary paired pulses and scripted burst rounds |
| `seeker_swarm` | Selectable homing missile volleys |
| `ion_lance` | Selectable penetrating beam |

All packages are version 1.0.0 and use mod API 1. Mission 1 requires compatible
1.x versions of the other six. Save compatibility also records each enabled
package's exact version and content hash.

## Mission 1: Breakwater

The player raids a coastal industrial harbor. Ten scouts cover the approach,
four ground turrets protect the docks, two destructible supply depots release
repair kits, and the command ship arrives at step 720. Destroy at least two
turrets and the command ship to finish. The boss stays in the playfield until
killed; waiting out the mission duration cannot produce victory.

The mission grants a trial Pulse Cannon, which fires alongside forward guns,
and three field repairs. Cycle equipment to **Iron Coast Field Repair** and
press the special button to restore 25 shield per repair. Depots drop extra
repairs. Victory pays 5,000 credits plus ordinary enemy rewards. The central
turrets and boss patrol overlap the starter-gun firing corridor; the mission
is intended to remain playable without the trial weapon.

Script objectives are namespaced and saved with the pilot:

| Objective | Meaning |
| --- | --- |
| `iron_coast_mission_1:phase` | 1 approach, 2 docks, 3 command ship, 4 complete |
| `iron_coast_mission_1:turrets_required` | Required count of two |
| `iron_coast_turret:defeated` | Turrets destroyed |
| `iron_coast_boss:defeated` | Command ships destroyed |
| `iron_coast_mission_1:depots_opened` | Supply depots destroyed |
| `iron_coast_mission_1:complete` | All required targets destroyed |

## Art and audio

Original terrain asset `0x10360` and military sprite `0x102f6` were decoded and
inspected before generating the new art with the built-in imagegen skill.
Every package includes generated masters, packaged SD/HD art, WAV files and
prompt/provenance metadata in Git. Original style-reference images and original
game data remain outside Git. Mission sources are a generated shoreline texture,
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
audio service is used. The generator and output hashes are tracked.

The generated mod assets are included in Git, so a fresh checkout includes
the complete seven packages. The original base-game asset catalog is still
required locally to play the game and remains excluded from version control.
To rebuild the mission assets from their included generated masters, run:

```sh
python3 examples/mods/iron_coast_mission_1/build_assets.py --palette data/misc/PALETTE_DAT
cargo run --no-default-features -- --mods examples/mods --validate-mods iron_coast_scout,iron_coast_turret,iron_coast_boss,pulse_cannon,seeker_swarm,ion_lance,iron_coast_mission_1
```

## Acceptance checks

`tests/iron_coast.rs` loads all seven real manifests, definitions and scripts
with synthetic PNG/WAV fixtures. It checks dependency activation, artwork
footprints, explicit boss/turret completion gating, one-time victory rewards,
and actual headless runs through the scout waves and boss using starter guns
and the trial Pulse Cannon. These tests use no original images and replace the
generated assets with synthetic fixtures. Local package validation additionally checks
the actual generated SD/HD images and WAV files.

Visual approval remains provisional: sprite and terrain previews were
inspected for readability, canvas alignment and transparency, with numeric
palette and repeat-seam checks. Wider player testing should assess difficulty,
audio balance and HD details during normal play before treating the new art
as final. These packages extend the Rust engine; they do not establish full
parity across the original campaigns.
