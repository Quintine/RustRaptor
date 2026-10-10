# Original mission ending and death

The Rust simulation now follows the retained engine's `RAP_ThinkStats` ending
sequence for missions with `legacy_map`. Authored mod missions retain their
immediate completion/failure contract. This is a source-based port with portable
synthetic regressions; a C++ recording through a complete ending or death is
still required before claiming transition parity.

## Departure

Removing the final eligible original enemy arms a 60-step countdown before
hostile-shot processing, matching `ENEMY_Remove`. Player damage is suppressed
while the countdown is active, matching `OBJS_SubEnergy`. At the start of each
subsequent step the countdown decrements after input and before world updates.
An entry value of zero still executes that final simulation step before the
outcome changes.

At 40, control pauses and `FX_FLYBY` is emitted. Below 40, the ship moves toward
the horizontal corridor 152–168 in eight-pixel increments and upward four
pixels. The original paused input phase retains the prior forced delta; the
statistics phase then applies the new delta. Consequently most departure steps
contain both moves. Boundary clamping is suspended during the ending. A healthy
ship remains drawable as it leaves the screen; `Outcome::Complete` follows the
final simulation pass, rather than appearing while the ship is stationary.

`World.control_paused`, `departure_delta`, `end_timer` and `draw_player` expose
these states to the SDL-independent renderer/input consumer. The synthetic
stationary-pilot fixture, starting with an already armed countdown, completes
after 61 steps at `(160, -160)`.

Original demo playback assigns recorded coordinates and banking directly and
bypasses both automatic moves, matching `IPT_MovePlayer`'s playback early return.
Coordinates captured at the end of a newly authored step do not necessarily
represent the original recording phase; use deterministic keyboard-input replay
for strict reproduction of an entire newly recorded ending.

## Death

Zero energy starts the same countdown instead of immediately failing the
mission. Each statistics pass requests a medium-air and small-air explosion
with randomized coordinates. Above 24 it also emits a randomly panned air
explosion sound; the original randomized sound pitch consumes the shared RNG.

At 24, `draw_player` becomes false. The sequence requests its centered explosion,
three explosion sounds and 512 alternating large-air/air-blast effects. The
original animation pool holds at most 100 effects. All 1,024 burst-coordinate
RNG calls still occur when that pool fills. The portable fixture verifies the
first randomized positions, sound pan choices, the pool limit and exact RNG
advance at the burst, including the separate palette-update RNG call. A pilot
whose energy is initially zero remains `Playing` through the visible explosion
sequence and reaches `Failed` after 62 steps.

Low-energy equipment loss runs after the death/departure statistics, preserving
the existing shared RNG and automatic weapon-selection behavior.

## Verification

Run the portable regressions without original assets:

```sh
cargo test --no-default-features --test transitions --test gameplay
```

The transition suite has five tests covering successful departure, direct demo
positions, immunity beginning on final-enemy removal, delayed death with the
burst RNG/pool cap, and authored mod outcome compatibility. The gameplay suite
also retains beam ordering, raw demo bounds, equipment loss, kamikaze movement,
Energy Grab, Ground Bomb and Mega Bomb checks.

After this change, the complete available `DEMO1G1_REC` still matched the rebuilt
C++ engine's gameplay snapshots across all 1,889 simulation steps. That recording
ends before its boss, so it proves the transition changes did not disturb the
captured pre-ending behavior; it does not validate the new transition itself.
See [campaign-validation.md](campaign-validation.md) for reference rebuild and
comparison commands, captured fields, original-data checks and limitations.

The relevant retained sources are `raptor/src/rap.cpp` (`RAP_ThinkStats` and
`Do_Game`), `raptor/src/rap.h` (`END_DURATION`, `END_EXPLODE`, `END_FLYOFF`),
`raptor/src/input.cpp` (`IPT_MovePlayer`, `IPT_FMovePlayer`),
`raptor/src/enemy.cpp` (`ENEMY_Remove`) and `raptor/src/objects.cpp`
(`OBJS_SubEnergy`). God-mode/debug behavior, rumble, warning-light presentation,
cinematic sequencing and a native transition reference are outside this scoped
verification.
