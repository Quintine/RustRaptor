# Original opening cinematics

The normal startup sequence retains the original Apogee and Cygnus logo cards,
their individual palettes, the Apogee fanfare and the original city chase,
ship, cockpit, firing and explosion animations. **Watch intro** replays that
sequence. The new menu background is used after the cinematics; it does not
replace any of their artwork.

The cinematic player uses a separate 70 Hz clock. Original movie rates are
converted using the native `GFX_WaitUpdate` rule, integer `70 / frame_rate`
ticks per frame. This matters especially for the ship scenes: their native
18 fps setting holds each frame for three service ticks. It previously held
them for eighteen ticks in the Rust implementation. Frame sound effects now
occur after each frame's timed display, as in `MOVIE_Play`.

| Sequence | Service ticks | Seconds |
| --- | ---: | ---: |
| Apogee and Cygnus cards, with local original fanfare | 966 | 13.80 |
| Complete original introduction | 925 | 13.21 |
| Complete startup sequence | 1,891 | 27.01 |
| Landing | 288 | 4.11 |
| Air and ground death | 1,384 | 19.77 |
| Campaign 1 ending, base approach and landing | 1,426 | 20.37 |
| Campaign 2 ending, base approach and landing | 1,171 | 16.73 |
| Campaign 3 ending, base approach and landing | 1,058 | 15.11 |

The Apogee hold is derived from the decoded MUS end event, with the original
120-tick minimum. The local original score ends at music tick 516, requiring
517 music service ticks after it starts. Cygnus plays its two boss sound cues
at hold ticks 3 and 120, and starts the looping introduction music at tick 135.
The logo fades are 64 ticks in and 63 ticks out. The final landing record is
decoded and checked, but its delta is not displayed: that native record fades
the preceding frame rather than drawing another frame.

Jet background patches resolve through the original sound bank's digital
variants. The zero-byte catalog FX markers are not decoded as audio. Their
repeat intervals use the same quantized pitch table and DSP stepping as the
real mixer. The duration helper is checked against actual voice expiry across
72 combinations of sample rate, pitch and service clock.
Clip transitions stop the outgoing background patch before starting the next
one, so a long jet sample cannot spill into the cockpit or firing scene.
Chronological play/stop events preserve that order even when an update crosses
several scene boundaries. Tagged mixer stops remove the patch's held output
immediately while preserving other sounds and their playback positions.

Run the portable decoder, timing and cue checks from the repository root:

```sh
LD_LIBRARY_PATH="$HOME/.local/lib" cargo test --locked \
  --lib cinematics::tests
```

Run the original catalog integration checks locally:

```sh
LD_LIBRARY_PATH="$HOME/.local/lib" RAPTOR_TEST_DATA="$PWD/data" \
  cargo test --locked \
  --lib cinematics::tests -- --ignored
```

The checks cover both card palettes, complete logo and introduction durations,
music and sound cue times, all original cinematic delta decoding, all sequence
rates and rendering-rate independence. Original cinematic assets are included in tracked `data/`; local screenshot
captures remain outside the repository. The retained native source supplies the frame
rates and cue placement; these checks are not a frame-by-frame native video or
whole-sequence PCM comparison.
