# Iron Coast S2: Black Tide

Stage 2 is an eight-sortie expansion built from independent local mods. It
preserves the original 70/3 Hz simulation, native classic enemy movement and
the normal shop, firing controls, shield economy and pilot saves.

Enable **Iron Coast S2: Black Tide** in **Mods**, apply at the main menu, then
select **Iron Coast S2 M01: Nightbreak Inlet** in the Hangar's mission menu. Its dependency selection
includes the eight mission packages, their bosses and shared enemies, music
and the two weapon packages. Enabling a single mission selects only its actual
dependencies and leaves the other missions and optional weapons disabled.
Disabling the campaign offers to remove its unused dependencies in the usual
confirmation popup.

| Sortie | Mission | Encounter | Boss | Music |
| --- | --- | --- | --- | --- |
| 1 | Nightbreak Inlet | Moonlit harbor breach | Gatebreaker shore platform | assault |
| 2 | Undertow Run | Naval convoy pursuit | Undertow missile submarine | pursuit |
| 3 | Stormglass Refinery | Fuelworks under air attack | Stormglass refinery crawler | assault |
| 4 | Floodgate Zero | River crossing and dam defenses | Floodgate defense platform | pursuit |
| 5 | Skybreaker Arsenal | Cliffside airborne weapons facility | Skybreaker flying fortress | assault |
| 6 | Emberwake Shipyards | Volcanic steelworks and repair docks | Emberwake battleship | pursuit |
| 7 | Siege of the Iron Fleet | Layered coastal fleet raid | Dreadnought carrier | finale |
| 8 | Black Tide | Offshore command citadel assault | Leviathan command carrier | finale |

## Package contract

- `iron_coast_stage2_campaign:campaign` links the eight mission IDs in order.
  Its manifest depends on all eight mission packages and the two optional
  weapon packages. This ID sorts before individual mission campaigns so the
  full campaign determines progression when installed together.
- `iron_coast_stage2_mission_N:mission_0N` belongs to mission package N.
  Individual mission packages remain independently playable. Each declares
  only the shared enemies, own boss and soundtrack it actually references.
- `iron_coast_stage2_boss_N:unit` belongs to a separate boss package.
  An actual boss death increments `iron_coast_stage2_boss_N:defeated`.
- Shared enemy packages expose `iron_coast_stage2_interceptor:unit`,
  `iron_coast_stage2_siege:unit` and `iron_coast_stage2_skimmer:unit`.
  Their death counters use their own `:defeated` objective IDs.
- `iron_coast_stage2_music` supplies `:assault`, `:pursuit` and `:finale`.
- `iron_coast_railburst:equipment` and `iron_coast_depth_charge:equipment`
  are separate shop additions. Prices follow actual simulated damage and
  target/range/cadence constraints. Their weapons and projectiles have
  separate IDs from their inventory items.

Every package uses API 1. The manifests record exact current versions;
mission and boss updates retain compatible 1.x dependency requirements. Stage 2 introduces no overrides
of original or Stage 1 content. Mission scripts use `auto_complete=false`:
elapsed duration does not grant victory. Required targets stay reachable;
destroying them and the final boss earns the ending. Every sortie resets its
own objective and phase state. Completion and debrief counters are scoped to
the mission and victory credits are awarded once per sortie.

## Equipment and controls

The **Railburst Cannon** costs 685,000 credits. This selected special fires a
fast 42-damage round and can penetrate two further targets in a narrow forward
lane for 32 and 22 damage. It hits air and ground targets and rewards alignment.
The **Depth Charge** costs 525,000 credits. This selected special delivers
72 damage to a ground target, with bounded splash to three nearby ground
targets; aircraft are excluded. Both are reusable, allow one owned copy and
sell for half their purchase price. Their package READMEs include measured
damage, limits, art provenance and reproducible sound recipes.

Buy either in the supply room after enabling its mod. **Alt or Shift** cycles
selected equipment; **Ctrl** fires it alongside the default guns. **Space**
continues to drop bombs. The campaign grants no equipment loans or automatic
full-shield refill. Later sorties include bounded support repairs; additional
repairs use the normal Energy purchase.

## Content and review requirements

New terrain and boss silhouettes should distinguish each mission while
keeping the top-down industrial military appearance of Raptor. Classic
enemy IDs keep their native paths, weapons and behavior. Boss phases should
change the attack pattern visibly and leave reasonable escape lanes.

New artwork includes SD and HD PNGs with identical logical collision
dimensions and correct transparency. Authored art, generated sound effects,
MUS scores, prompts, provenance and reproducible processing/composition
sources are included in Git. Working original-reference images and review
captures stay in ignored directories.

Acceptance covers dependency selection and disabling, individual activation,
all eight real mission completions, native enemy movement, owned equipment
and full inventories, pilot save/RNG continuation, finale replay and reward
deduplication. SD/HD gameplay and shop images and actual audio output are
reviewed before updating both self-contained Linux and Windows bundles.

## Validated release content

All 23 Stage 2 packages are frozen and add no overrides. The complete installed
set contains 45 packages; its sole override is the existing Stage 1 campaign
progression link. Portable campaign checks cover dependency closure, unused
pruning, individual missions, eight-sortie progression and full inventories.

The original-data route starts with the actual registered pilot baseline of
75 shields and 10,000 credits at Veteran difficulty. Normal default-gun fire
and pointer input complete all eight sorties, saving and loading the pilot,
script state and RNG between each, then replay the finale. Three normal Energy
purchases are paid from carried credits. The route finishes the first eight
with 334,910 credits, and the saved replay with 396,520; equipment stays owned
and rewards are not duplicated. Independent review also completes the eight
sorties and a saved finale replay at all four difficulties from the same
registered-pilot baseline, using paid Energy repairs. Authors check full
inventories, purchased weapons and delayed objective completion. The aggregate
README subsequently corrects the mission-selection instructions; its separate
successor receipt compares all 4,480 package files: only that README changes,
and the other 4,479 files and the other 22 package hashes remain identical.
The final saved route binds the successor package hash. A pilot saved with
the preceding README hash still receives the normal changed-mod confirmation;
this review does not bypass the saved content-hash check.
Control policies vary, so these are achievable fixture outcomes rather than
predictions of player earnings or difficulty.

Independent review clears 40 boss lifecycle/phase cases, 32 emitted-attack
contracts, eight concurrent-boss cases, four 1,100-lifetime state/migration
probes and exact 14-tick phase-transition warnings. Actual weapon collision,
splash/penetration limits and a 24-enemy command-budget fixture pass. The
review inspected 232 decoded SD/HD outputs at scales 1–4 and checked 75 native
sound effects with nonzero output and exact FX mute. The music package records
separate complete-score FM and loop-boundary validation.

Script-pinned boss phase artwork reaches both sprites and shadows; resetting a
pin restores normal animation. A synthetic Host regression covers ground and
air enemies in SD/HD at scales 1 and 4, and the real artwork previews assert
that consecutive boss phases produce distinct displayed pixels.

PNG activation still fully decodes artwork and retains the same size, canvas,
HD-resolution and catalog-palette checks. It now avoids converting validation
images to indexed pixels only to discard them. Paired checks with all 45 mods
reduce active content construction from 26.9 to 7.0 seconds; all 6,682 unique
referenced PNGs produce byte-identical indexed output. Actual package startup
is measured separately during relocation tests.

The ordinary suites pass 315 headless and 380 desktop tests. Final focused
checks pass four portable campaign checks plus the real saved route, nine
weapon tests, nine shared-enemy tests, six animation/effect API tests and the
ignored Host preview check. All 34 Host captures were visually inspected; after the phase fix, the six
changed SD/HD phase pictures were inspected again and the other 28 remained
byte-identical:
SD/HD boss artwork on each mission's terrain, both shop modes, weapon details,
Nightbreak/finale mission cards, dependencies and the disable confirmation.
Bosses in these pictures are deliberate art previews; actual combat phase
and campaign completion evidence is separate. Drawing preserves gameplay
state, Escape cancels diagnostics/disable, and mod rows retain their order.

Reproduce the original-data route from this folder with:

```sh
cargo test --release --locked --no-default-features --test iron_coast_stage2 \
  starter_ship_completes_all_eight_missions_with_paid_repairs_and_finale_replay \
  -- --ignored --nocapture
```

Set `RAPTOR_TEST_DATA` for a deliberate catalog override, and
`RAPTOR_STAGE2_DIFFICULTY` to 0–3 to choose difficulty. The final Linux and
Windows archive checks use extracted copies, 1080p SDL rendering and separate
music/effect PCM captures. These entry smoke checks are distinct from full
headless combat acceptance; automated SDL uses dummy drivers.

The [corrected native Windows run](https://github.com/Quintine/RustRaptor/actions/runs/38129755440)
passes on source commit `0e8a27c`, including the eight-mission saved route,
phase sprites/shadows, actual SD/HD Host previews, all 45 packaged mods and
isolated FM music/sound-effect captures. The same corrected included GNU
executable passes relocated Wine checks. Final archive documentation refreshes
are checked separately against the complete runtime proofs; see
[standalone packages](standalone-package.md).
