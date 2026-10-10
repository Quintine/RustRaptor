# Iron Coast campaign music

**Coastal Steel** is an original 96-second, 140 BPM FM action score with six
sections: approach, breakwater riff, offshore pursuit, stormwall bridge,
citadel assault and the return to the coast. Fingered bass, muted power chords,
an overdriven guitar melody, a contrasting lead and restrained strings sit
over kick, snare, hats and occasional tom fills. The closing phrase resolves
to the opening E-minor harmony for continuous mission playback.

The package is independently toggleable, uses mod API 1 and has no mod
dependencies. Iron Coast missions depend on it and reference
`iron_coast_music:iron_coast` through `music_track`. It uses the existing Rust
MUS/GENMIDI FM music bus, so the game's music volume and mute controls apply.
The original game instrument bank is required locally; it is not copied here.

The score, deterministic composition recipe and provenance are included in
Git. No original-game melody, recording or instrument data is bundled.
Regenerate the exact score with:

```sh
python3 mods/iron_coast_music/build_music.py
```

The engine services MUS events at 70 Hz. This score uses five melodic channels
and standard percussion on channel 15, releases notes explicitly, and ends
after 6,720 ticks. It stays within the checked package music limits. The
looping flag is declared in `content.json`; neither a Rhai script nor an
ordinary sound-effect command is needed for playback.

Validation uses the actual Rust decoder and locally installed original FM
instrument bank. A 100-second stereo render is non-silent through the first
loop, has no clipped samples, and mutes to exact digital silence. The recipe
also checks paired note events and the 6,720-tick duration. Numeric results are
in `validation.json`; human listening and normal-play sound balance remain
part of wider campaign testing. The locally rendered preview remains outside
Git because it uses the original instrument bank.
