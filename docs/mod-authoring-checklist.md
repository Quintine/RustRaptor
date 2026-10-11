# AI agent checklist for building a new mod

Use this checklist for new weapon, equipment, enemy, mission, campaign and music
packages. The user's current request takes precedence. Treat the checked-in
[mod API](modding-api.md), content types and shipped examples as the contract;
do not invent unsupported fields or callbacks.

## 1. Define the behavior

- [ ] Record the requested content, controls, target types and intended role.
- [ ] For equipment, decide whether it is always equipped and fires with Fire,
  a selected special, a consumable, or a passive item. Always equipped does not
  imply firing without input. State the controls clearly in the shop description.
- [ ] Specify range, cooldown, damage, target limits and interactions with other
  equipment. Account for the 320×200 logical canvas and 70/3 simulation ticks
  per second; HD artwork must not change gameplay geometry.
- [ ] Check existing API support. Use callbacks and checked commands for mod
  behavior. If something is missing, describe a minimal reusable API extension
  and coordinate its implementation with the engine agent when authorized.

## 2. Build an independent package

- [ ] Create `mods/<id>/mod.toml`, `content.json`, `scripts/`, `art/` and any
  `audio/` or `music/` directories needed by the content.
- [ ] Use a unique lowercase package ID, version, `api_version = 1`, clear
  name and description. Declare all script files in `manifest.scripts`.
- [ ] Namespace new definitions with the package ID. Keep inventory item and
  weapon IDs distinct; keep IDs stable so saved inventory survives updates.
- [ ] Declare only real dependencies. Verify standalone packages can be enabled
  alone. Make complete, explicit overrides only when intentionally required.
- [ ] Omit `legacy` on new content. Use relative paths without traversal or
  symlinks, and stay inside the documented package and content limits.
- [ ] Keep equipment capacities and consumable flags consistent with its role.
  Define pickup and shop behavior consistently; reusable gear must remain owned.

## 3. Implement scripts safely

- [ ] Use only documented event snapshots, callbacks and commands. Filter dead,
  invisible or wrong-type targets and enforce the intended range and target cap.
- [ ] Use deterministic target selection and tie breaks. Avoid duplicate hits,
  accidental repeated chaining, screen-wide damage and unnecessary commands.
- [ ] Keep callback work and state bounded. Use the supplied deterministic RNG
  for gameplay randomness; do not depend on render rate, wall time or OS state.
- [ ] Handle initially empty state and older saved state. Verify scripts compile,
  callbacks have three arguments and command failures roll back cleanly.
- [ ] Choose visual commands appropriate to the effect. Do not use explosion
  effects for ordinary muzzle flashes or electrical arcs.

## 4. Ship SD, HD and audio assets

- [ ] Supply a real SD `png` and HD `hd_png` for every authored artwork reference.
  Use the same logical dimensions, aspect ratio, frame count and alignment.
- [ ] Preserve actual alpha transparency and padding. Keep sprites legible at
  their small SD size, with clear silhouettes and stable frame positions.
- [ ] Inspect both modes after palette conversion in the game renderer. Check
  animation strips, shop icons, firing/hit feedback and moving scenes as needed.
- [ ] Ship valid local WAV or DMX effects and MUS scores where applicable.
  Keep volumes and repetition comfortable and avoid playing hit sounds on misses.
- [ ] Track final assets, required source masters, prompts, provenance and
  reproducible preparation/synthesis recipes with the package. Never commit
  decoded style-reference images or local review captures into a mod. The
  approved original/HD runtime catalog is tracked separately in `data/`.

## 5. Price and balance equipment

- [ ] Compare original and shipped gear in [weapon balance](weapon-balance.md).
  Account for aiming difficulty, effective range, air/ground coverage, splash
  or chain caps, recharge, consumption and damage per second.
- [ ] Measure damage through `World::step` with the real scripts over a fixed
  duration. Use surviving stationary fixtures to avoid overkill skewing results.
- [ ] Include aligned, off-axis, ground and cluster cases where relevant.
  Add a close-range scene for proximity gear, and test a combined loadout for
  always-equipped weapons. Keep pilot health and fixture movement controlled.
- [ ] Choose a progression tier and justify the final price. Check purchase,
  capacity, duplicate rejection and resale; purchases must not create money.
- [ ] Distinguish controlled measurements from campaign balance. Document
  relevant tradeoffs and unresolved playtesting questions without claiming that
  every loadout or mission is equally difficult.

## 6. Verify and document

- [ ] Add meaningful portable tests with synthetic images/audio when practical.
  Test actual damage, target exclusions, range boundaries, cooldown, finite
  target caps, inventory preservation and coexistence with shipped packages.
- [ ] Check deterministic continuation of script state/RNG. Exercise kills and
  empty-target situations, not only the happy path with surviving targets.
- [ ] Run the package validation CLI against the original local catalog:
  `cargo run --no-default-features -- --mods mods --validate-mods <id>`.
  Also validate relevant combined packages. Do not alter the user's active mods.
- [ ] Run focused tests, then required regression checks. Regenerate schemas if
  an API type changed, and build the desktop engine if rendering or controls changed.
- [ ] Add a package README with enabling instructions, price, controls, target
  behavior, limits, validation commands and a link to artwork provenance.
- [ ] Update repository documentation and balance observations where relevant.
  Inspect the final diff and preserve unrelated work.
- [ ] Report what was delivered, how to enable/use it, final prices and validation
  results. State any material limitation or unperformed check accurately.

## Local commands

From `RustRaptor/`, replace IDs and test names for the package being authored:

```sh
cargo test --locked --no-default-features --test weapons_mods
cargo run --locked --no-default-features -- --mods mods \
  --validate-mods lightning_cannon,lightning_shield
RAPTOR_BALANCE_REPORT="$PWD/.reference/weapon-balance.json" \
  cargo test --locked --no-default-features --test weapon_balance \
  -- --ignored --nocapture
cargo fmt --all -- --check
```

Use the appropriate test for enemies, missions or music. An unavailable original
catalog is a reason to report the local validation limit, not to bypass portable
tests or deliver broken package references.
