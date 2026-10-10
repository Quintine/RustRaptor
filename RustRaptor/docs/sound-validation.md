# Sound playback validation

The Rust engine plays original digital effects, MUS music through its Rust FM
synthesizer, and package-local WAV cues. SDL2 provides the output device.

Original sound-event IDs identify an empty catalog marker. The actual digital
patch is four catalog entries later, matching the original setup routine.
The sound bank resolves and checks that patch, preloads the 26 original
digital assets, and reports missing or invalid cues. Mod WAVs are decoded and
cached before acquiring the audio-device lock. Successful mod activation
invalidates that cache.

Music/effect gains and channel limits are applied before the device starts.
Changing effect volume updates playing voices; muting clears held samples.
Music volume zero gates FM output while the score and synthesizer continue
advancing, so restoring volume resumes the current music position.

Portable audio and sound-bank tests cover checked decoding, mixing, pitch,
priority, channel limits, gains, mute behavior and missing/invalid assets.
Optional original-data checks compare FM and digital samples with a small
retained-source harness. Another integration check dispatches all 36 original
cue variants through the production Rust SDL callback and checks their output.

Local real-device checks on 2026-10-10 used SDL's PulseAudio backend through
PipeWire to the default analog stereo sink. A first-mission run with music
muted produced digital-effect output with peak 16,390 and RMS 6,657.51. A
concurrent sink-monitor recording correlated with the callback output at
0.99929. A seven-package Iron Coast run also produced audible-level output
(peak 16,406; RMS 4,909.62). System volume and mute were unchanged. These
measurements confirm output routing and signal; they do not assess acoustic
balance on every speaker or every cue during ordinary play.

The final combined build was checked through the same real device after the
mute fix: 172,544 captured stereo frames of first-mission effects had peak
16,384 and RMS 6,506.91. A separate run with both gains at zero captured
54,784 stereo frames with zero nonzero samples, peak zero and RMS zero.

For a bounded diagnostic capture of the actual production callback, run from
`RustRaptor/` with an isolated profile:

```sh
RAPTOR_AUDIO_CAPTURE="$PWD/../.reference/audio.wav" \
RAPTOR_AUDIO_CAPTURE_SECONDS=10 \
SDL_AUDIODRIVER=pulseaudio ./run.sh \
  --profile-root ../.reference/audio-profile \
  --preview-mission base:sector_1_wave_1 --smoke-frames 540
```

The capture is PCM16 stereo and accepts 1–120 seconds. Configure music and
effects in that profile before capture. Original assets, captures and reports
remain ignored under `../data/` and `../.reference/`. Authored mod WAVs and
their synthesis recipes are tracked in Git.
