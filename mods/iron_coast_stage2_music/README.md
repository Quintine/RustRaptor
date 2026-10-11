# Iron Coast II: Black Tide — Original Soundtrack

Three original FM action themes for Iron Coast II, played by RustRaptor's
checked MUS decoder and classic GENMIDI/OPL3 music bus. This independent API 1
package has no dependencies and does not override original music. Missions
that require it select the appropriate stable ID through `music_track`.

| Track ID | Theme | Tempo | Score length |
| --- | --- | --- | --- |
| `iron_coast_stage2_music:assault` | **Rivetline Assault**: syncopated harbor machinery, distorted power chords and a driving D-minor guitar lead | 144 BPM | 56 bars / 93.329 s |
| `iron_coast_stage2_music:pursuit` | **Undertow Pursuit**: fast F-sharp-minor chase, angular square-wave calls, muted guitar and a quieter FM-bell fog passage | 168 BPM | 64 bars / 91.429 s |
| `iron_coast_stage2_music:finale` | **Black Tide Rising**: C-minor brass beacon motif, chromatic danger variation, open-water bridge and intensified final assault | 126 BPM | 56 bars / 106.671 s |

Each has its own motifs, harmony, instruments, percussion and six-section
arrangement. Closing four-bar phrases return from the dominant to the opening
tonic. Explicit note releases and a final all-notes-off prevent carried notes.
The native 70 Hz service clock starts the first downbeat one quantum after
playback begins; following loop periods use the score's clock length.
Oscillator phases and release envelopes remain native. These are musical
loops, not sample-identical PCM splices. See [provenance](provenance.json) for
bar boundaries, channels, instrument declarations and exact score hashes.

Enable the package in **Mods**, or let an Iron Coast II mission enable its
dependency automatically. It adds no shop item, consumable, control or artwork.
The game's **Music** setting controls these tracks; **Effects** retains its
separate bus. Original menus and cinematics continue to select their own music.
The full local preview WAVs are QA outputs outside the package; they are not
registered digital effects and therefore do not use the 30-second WAV-effect
limit.

## Reproduction and verification

All note sequences and arrangements were authored for this project by Codex.
No proprietary melody, source-game score, MIDI or recording was copied. The
Stage 1 composer was consulted for the existing MUS serialization convention.
FM playback uses the game's separately installed original instrument bank.
No external audio model, SoundFont or sample recording is needed.

From `RustRaptor/`:

```sh
python3 mods/iron_coast_stage2_music/build_music.py
python3 mods/iron_coast_stage2_music/validate_music.py
cargo run --locked --release --no-default-features -- \
  --mods mods --validate-mods iron_coast_stage2_music
cargo test --locked --no-default-features --test music
```

The standard-library-only Python composer regenerates all three MUS files and
provenance byte for byte. The native Rust QA helper validates independent
activation, exact header ranges, actual event counts and percussion preloads,
unmatched notes, original-bank dual-voice requirements, end markers, loop
continuation, Music mute, one-play tail decay, every rendered second and
clipping at both default and maximum Music volume. It creates full previews,
eight-second loop-boundary previews and an exact library/instrument/source
hash report in `../.reference/iron-coast-stage2-music/`. Use `--data PATH` or
`--output PATH` for another local catalog/output folder. It does not write
pilot files, settings or selected mods.

Validation is objective inspection of the native PCM output, not a claim of
human listening or subjective playtest approval. Package verification results
and reproduction hashes are recorded in [validation.json](validation.json).
