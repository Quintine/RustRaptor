# Original first mission: ordinary-input victory

The opt-in `tests/first_mission.rs` check completes `base:sector_1_wave_1`
through its original boss with a fresh pilot on difficulties 1 and 2. It uses
the locally installed original catalog and the production `World::step` path.
Both runs start with the default forward guns, shield 100, no super shield,
no special weapon, and zero credits. No extra equipment is required.

Run it with:

```sh
RAPTOR_TEST_DATA=/absolute/path/to/data cargo test --release --no-default-features --test first_mission -- --ignored --nocapture
```

Without `RAPTOR_TEST_DATA`, it reads this checkout's `data/` directory. The
test is ignored in the default suite because original game data is not shipped
in Git. It writes local results to `.reference/`, which is also ignored.

## Recorded results

Local validation on 2026-10-10 produced:

| Difficulty | Boss spawned | First visible alive | Boss killed / reward paid | Complete | Shield remaining | Final credits | Confirmed kills | Positive-health retirements |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 4,441 | 4,487 | 4,583 | 4,644 | 80 | 42,775 | 118 | 12 |
| 2 | 4,441 | 4,487 | 4,703 | 4,764 | 65 | 59,025 | 161 | 37 |

Step counts use the original 70/3 Hz simulation. Both runs visit all 299
cataloged spawn entries; the original difficulty flags decide which entries
actually spawn. The boss is `base:enemy_0_28`, with an original reward of 3,000
credits. Its last observed health before removal was 0 on difficulty 1 and
−3 on difficulty 2. The test asserts that its death pays the reward, that every
eligible boss enters the playfield alive and is killed, and that the surviving
player reaches `Outcome::Complete`.

The healthy departure cue plays at timer 40 (steps 4,603 and 4,723), pauses
ordinary controls, and starts the forced flight offscreen. At timer 24
(steps 4,619 and 4,739), the surviving ship remains drawable. It ends the
departure at logical y = −160 before completing. The test checks these
milestones and records every countdown step; it does not substitute a direct
victory command or terminate immediately after the boss kill.

A confirmed kill requires an entity to be observed with health at or below zero
before removal. An entity removed after a positive-health observation is kept
separately and never counted as a confirmed kill. That count is conservative
around a possible same-step collision death; it is not an all-enemies kill
claim. Mission completion alone cannot satisfy the boss-kill assertion.

The local catalog's `INDEX` SHA-256 was
`4ce78e5e638b6603114dd233ceaa41f386c0963ba4aa02ecf88ce0215b096681`.

## Controller and assistance limits

The controller supplies only normal keyboard direction values (`dx`, `dy`
each −1, 0 or 1) and a held fire button. Production acceleration, speed limits,
banking, shot cooldowns, collisions, incoming damage, rewards and RNG all run
normally. The actual playthrough never uses absolute positioning, scripted
commands, bombs, shield refills, inventory grants or direct gameplay-state
edits after `World::new`.

For target selection, it leads visible enemies using their current observed
motion and gives the boss priority. To choose movement, it evaluates nine
direction pairs in disposable cloned worlds over 12 normal simulation steps:
three steps holding that direction and nine steps releasing movement. It
penalizes predicted damage, then balances aiming, lower-screen positioning and
distance from hostile shots. Cloned predictions are discarded; they cannot
change the live world's state or RNG.

This is an automated viability proof with full simulation-state knowledge and
precise timing. It demonstrates that the implemented first mission is winnable
with ordinary movement and starter equipment. It does not measure human
difficulty, input-device usability, graphics quality, or audio accuracy.

## Replay artifacts and reproducibility

For each difficulty, the test generates:

- `.reference/first-mission-fresh-difficulty-N.dem`: the original 12-byte demo
  record layout, with a sector/wave header, button bytes, observed player
  position and bank. It includes the complete boss encounter and ends at the
  flyby cue, before stats-stage forced departure movement: 4,603 and 4,723
  frames respectively. The first record is the first completed simulation step.
- `...-controls.json`: the actual keyboard direction and fire inputs per step.
- `...-report.json`: starting pilot, boss observations and deaths, rewards,
  conservative retirement classification, shield changes and periodic states.
- `....jsonl`: every production reference snapshot, including tick, shared RNG,
  player state, ordered enemies and ordered projectiles.

The test independently decodes and replays both recordings from an identical
fresh pilot. The full keyboard log must reproduce every reference snapshot
through `Outcome::Complete`: all 4,644 and 4,764 steps. Legacy demo playback
uses recorded absolute positions and banking, and must reproduce every
snapshot through the defeated boss and flyby cue: 4,603 and 4,723 steps.
The winning controller run itself uses keyboard movement.

The retained C++ engine records demos before its stats-stage automatic
departure movement and skips that movement during playback. End-of-step
coordinates therefore stop being equivalent after the flyby cue. A full
end-of-step demo showed its first divergence at step 4,605 in player projectiles
and RNG. Keeping the legacy-format recording to the verified prefix preserves
that record-phase distinction; the full keyboard replay verifies departure.

The recorded demo SHA-256 values are:

| Difficulty | SHA-256 |
| --- | --- |
| 1 | `c5385b30c600f91dab9c0f5009a24204f114626b7f655d18687799e834da34ef` |
| 2 | `8d245a537812535ebf0e8e66594a73afef6ff01a14581b80332b095d971cda63` |

These boss-encounter recordings exceed the retained C++ engine's 2,800-frame
static demo buffer. A checked reference-input loader with a larger buffer is
needed before loading them there. It must also preserve the fresh pilot and
difficulty, rather than substituting `DEMO_MakePlayer`'s showcase loadout.
The new recordings have **not** yet been compared against a C++ first-mission
boss victory. The existing 1,889-step `DEMO1G1_REC` parity test covers
a different original demo and remains a separate acceptance check.
