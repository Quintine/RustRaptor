# Desktop display measurements

Local release measurements on 2026-10-10 used SDL's OpenGL renderer at
1920×1080 fullscreen output, aspect correction, Scale4, no scanlines, and all seven Iron Coast
packages. They include normal terrain, sprites, indexed shadows, effects and
mod scripting. They exclude Cargo compilation.

| Mode | Startup | Render work median | Render work 95th percentile | Frame median | Frame 95th percentile |
| --- | ---: | ---: | ---: | ---: | ---: |
| SD artwork | 2,345.82 ms | 7.40 ms | 8.76 ms | 7.52 ms | 8.88 ms |
| HD artwork | 2,375.56 ms | 8.67 ms | 14.66 ms | 8.79 ms | 14.78 ms |

Each run sampled 174 frames from a 180-frame flight, excluding five warmup
frames and the screenshot frame. Work time excludes the presentation call;
frame time includes it. Startup covers desktop-host construction and SDL setup;
the preceding CLI catalog registration is excluded. The explicit one-millisecond smoke-loop sleep is
outside both measurements. These short runs establish local performance for
this scene and machine, not worst-case performance across every boss or device.
The fixed 70/3 Hz simulation advances independently of display timing.

From `RustRaptor/`, prepare two isolated profile configurations with
`width = 1920`, `height = 1080`, `fullscreen = true`, `scale = 4`, `scanlines = false`, and
`hd_mode = false` or `true`. Enable the mission's six dependencies and mission
package in `enabled_mods`; see [Iron Coast](iron-coast.md). Run:

```sh
./run.sh --profile-root ../.reference/enemy-sd-profile \
  --preview-mission iron_coast_mission_1:mission_01 \
  --smoke-frames 180 --benchmark \
  --screenshot ../.reference/rustraptor-sd-1080-final.png
./run.sh --profile-root ../.reference/enemy-hd-profile \
  --preview-mission iron_coast_mission_1:mission_01 \
  --smoke-frames 180 --benchmark \
  --screenshot ../.reference/rustraptor-hd-1080-final.png
```

Both captures were checked to be exactly 1920×1080. The benchmark reports the
actual SDL output size, since a window manager can constrain a requested window.
Use a real SDL display. Dummy-video screenshots verify raster composition but
cannot measure GPU presentation. Frame-limited runs do not save pilots or
settings. Profiles, caches and screenshots remain ignored local files.
