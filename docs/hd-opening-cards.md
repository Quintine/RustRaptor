# Opening-credit HD rendering

The existing HD setting can display supplied replacements for the standalone
opening-credit pictures. Each keeps its original 320×200 canvas and top-left
origin, with original-picture fallback when a replacement is absent or rejected.

| Picture | Original ID | Unfaded source palette |
| --- | --- | --- |
| `APOGEE_PIC` | `1002b` | `POGPAL_DAT` |
| `CYGNUS_PIC` | `1002d` | `CYGPAL_DAT` |

`Cinematic::still_picture` exposes the current card and its unfaded palette.
`HdAssets::sprite_static_palette` quantizes supplied artwork using all 256 colors
of that palette. Gameplay water/fire/flash index classes do not apply to these
static palettes. The indexed cache distinguishes this policy from ordinary
gameplay sprites while sharing source validation, RGBA residency and derived
disk assets. Existing cinematic presentation applies the fade afterward, so
black or partially faded colors never become quantization inputs.

Opening timing, music and PCM patch generation are unchanged. AGX delta films
and bitmap fonts retain their classic artwork and playback. This rendering
support adds no artwork coverage; actual opening-card remasters still require
source-palette, composition and artistic review before registration.

Synthetic tests cover both cards at 1× and 4×, colors above index 239, complete
fade phases, missing/rejected replacement fallback, separate cache policies,
and unchanged world/pilot/RNG plus cinematic audio/music event streams. The
complete synthetic opening remains 569 ticks. Local original-data checks also
pass: the opening retains 966 ticks and the AGX intro retains 925 ticks, with
their original cue times and palettes. The focused run passed 28 portable checks
and both original-data cinematic checks on 2026-10-10.

Run the desktop route fixtures from `RustRaptor/` with
`cargo test --locked --lib opening_card`. The cinematic and palette/cache suites
are `cargo test --locked --lib cinematics::tests::` and
`cargo test --locked --lib hd::tests::`. Original-data checks require
`RAPTOR_TEST_DATA=../data cargo test --locked --lib cinematics::tests:: -- --ignored`.
