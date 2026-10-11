# Mod mission music

Package music uses namespaced `MusicDef` entries and a mission's optional
`music_track`. It plays through the existing Rust MUS/GENMIDI FM synthesizer,
with the ordinary Music volume and fade controls. Sound effects keep their
separate digital bus. Original numeric mission tracks, menus and classic
cinematics keep their existing music paths.

Tracks use package-relative `.mus` files. The registry checks references,
duplicate IDs, namespaces and explicit overrides. Activation decodes the
winning owner's file and rejects missing, escaping, malformed or oversized
scores. The package's existing SHA-256 hash includes the score file, so pilot
mod compatibility covers music changes. Applying mods clears the bounded
decoded-score cache and returns an active mod track to main-menu music.

Limits apply to mod music without changing the legacy decoder: 128 KiB per
file, 16,384 events, at most 256 events at any service tick, positive duration,
and at most 126,000 score ticks (30 minutes at 70 Hz). Header ranges, supported
event types, primary channel count, velocities, controllers and the final end
event are checked by `MusScore::decode`. Cache allocation is bounded separately
from digital effects. Only MUS is supported; external MIDI and SoundFonts
remain deferred.

The host retains a namespaced desired-track ID and its loop flag. A mission
preview can select its music before SDL audio is initialized; attaching the
device applies that pending score. Re-selecting the same active ID/loop
preserves playback position. Selecting original menu or cinematic music clears
the mod identity. A failed score load leaves the pilot and menu state intact.

Synthetic checks cover registration and missing references, conflicting
legacy/custom choices, explicit overrides and owner resolution, hash changes,
cache invalidation, path and symlink containment, unsupported formats, file
size, event density, duration and channel limits. FM output checks exercise the
definition's actual loop flag and show that Music volume mutes the mod score
while digital effects remain audible. A one-play score's ending tail has less
than one twentieth the energy of the looping score in the tested fixture.

```sh
cargo test --locked --no-default-features \
  --manifest-path RustRaptor/Cargo.toml --test music
```

Portable host checks verify pending identity, original-menu transitions and
rollback when music cannot load. The paused SDL test attaches a real device
object and compares consecutive FM PCM blocks against uninterrupted reference
playback, proving that selecting the same track does not restart it:

```sh
LD_LIBRARY_PATH="$HOME/.local/lib" cargo test --locked \
  --manifest-path RustRaptor/Cargo.toml --lib mission_mod_music
LD_LIBRARY_PATH="$HOME/.local/lib" cargo test --locked \
  --manifest-path RustRaptor/Cargo.toml --lib failed_mission_music_load
LD_LIBRARY_PATH="$HOME/.local/lib" SDL_AUDIODRIVER=dummy cargo test --locked \
  --manifest-path RustRaptor/Cargo.toml --lib pending_mod_music_resumes -- --ignored
```

These checks validate the engine path using synthetic scores. Composition,
listening review and original-data in-game soundtrack captures are separate
release checks for each music package.
