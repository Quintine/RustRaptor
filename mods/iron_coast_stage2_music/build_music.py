#!/usr/bin/env python3
"""Compose three original Iron Coast II scores directly into checked MUS.

All motifs and arrangements below are authored for this package. No original
game score, MIDI file, audio recording, external library or randomness is read.
The native Rust MUS service clock is 70 Hz; exact rational timing keeps rounded
boundaries consistent across long phrases. Run with Python 3 from any folder.
"""

from collections import defaultdict
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import struct


ROOT = Path(__file__).resolve().parent
CLOCK = 70


class Score:
    def __init__(self, key, title, bpm, bars, programs, tonality, sections):
        self.key, self.title, self.bpm, self.bars = key, title, bpm, bars
        self.programs, self.tonality, self.sections = programs, tonality, sections
        self.events = defaultdict(list)
        self.end = self.tick(Fraction(bars * 4))
        self.drums = set()
        self.note_count = 0
        # Rhythm/bass have space for the melodic line; all five FM roles are
        # original-bank programs, not an external SoundFont or recorded sample.
        self.volumes = {0: 84, 1: 68, 2: 83, 3: 54, 4: 40, 15: 83}
        # The original OPL driver uses three pan positions; values >=96 are
        # the opposite side from <=48. Keep melodic counterlines apart from
        # the rhythm guitar, with bass/lead/pads/drums centered.
        self.pans = {0: 64, 1: 38, 2: 64, 3: 102, 4: 64, 15: 64}
        for channel, program in programs.items():
            self.emit(0, 0, 0x40 | channel, [0, program])
        for channel, volume in self.volumes.items():
            self.emit(0, 0, 0x40 | channel, [3, volume])
            self.emit(0, 0, 0x40 | channel, [4, self.pans[channel]])

    def tick(self, beat):
        value = Fraction(beat) * CLOCK * 60 / self.bpm
        return (2 * value.numerator + value.denominator) // (2 * value.denominator)

    def emit(self, tick, priority, descriptor, payload):
        assert 0 <= tick <= self.end
        self.events[tick].append((priority, bytes([descriptor]) + bytes(payload)))

    def note(self, channel, pitch, bar, step, length, velocity):
        if pitch is None:
            return
        assert 0 <= pitch <= 127 and 0 < velocity <= 127 and length > 0
        beat = Fraction(bar * 4) + Fraction(step) / 4
        start = self.tick(beat)
        stop = min(self.tick(beat + Fraction(length) / 4), self.end - 2)
        assert stop > start
        self.emit(start, 2, 0x10 | channel, [pitch | 0x80, velocity])
        self.emit(stop, 1, channel, [pitch])
        self.note_count += 1
        if channel == 15:
            self.drums.add(pitch)

    def phrase(self, channel, notes, bar, velocity=91):
        for slot, pitch in enumerate(notes):
            if pitch is not None:
                length = Fraction(3, 2) if slot < 7 and notes[slot + 1] is not None else 3
                self.note(channel, pitch, bar, slot * 2, min(length, 15 - slot * 2),
                          velocity if slot in [0, 4] else velocity - 11)

    def power(self, root, bar, slots, length=1, velocity=80):
        for step in slots:
            self.note(1, root + 12, bar, step, length, velocity)
            self.note(1, root + 19, bar, step, length, velocity - 13)

    def pad(self, root, bar, length=15, velocity=48):
        self.note(4, root + 24, bar, 0, length, velocity)
        self.note(4, root + 31, bar, 0, length, velocity - 10)

    def kit(self, bar, style, crash=False, fill=False):
        hat_steps = range(0, 16, 2) if style == "open" else range(16)
        for step in hat_steps:
            key = 46 if style == "ride" and step == 14 else 42
            self.note(15, key, bar, step, Fraction(2, 3),
                      58 if step % 4 == 0 else 37 if step % 2 else 47)
        kicks = [0, 8] if style == "open" else [0, 3, 8, 11] if style == "chase" else [0, 6, 8, 14]
        for step in kicks:
            self.note(15, 36, bar, step, 1, 108 if step in [0, 8] else 84)
        for step in [4, 12]:
            self.note(15, 38, bar, step, 1, 101 if style != "open" else 87)
        if crash:
            self.note(15, 49, bar, 0, 3, 84)
        if fill:
            for step, pitch in [(12, 47), (13, 45), (14, 43), (15, 41)]:
                self.note(15, pitch, bar, step, Fraction(3, 4), 76 + (step % 2) * 7)

    @staticmethod
    def delay(value):
        chunks = [value & 127]
        value >>= 7
        while value:
            chunks.append(value & 127)
            value >>= 7
        return bytes(piece | (128 if i < len(chunks) - 1 else 0)
                     for i, piece in enumerate(reversed(chunks)))

    def write(self):
        # Every scored voice is released before the next downbeat. The cadence
        # resolves to the starting tonic; this is a musical loop, not a pasted
        # PCM splice. The game's FM release envelopes remain in the native bus.
        for channel in self.volumes:
            self.emit(self.end - 1, 3, 0x30 | channel, [11])
        self.emit(self.end, 4, 0x60, [])
        times = sorted(self.events)
        stream = bytearray()
        pressed = set()
        maximum = 0
        for index, tick in enumerate(times):
            group = sorted(self.events[tick], key=lambda item: item[0])
            for position, (_, raw) in enumerate(group):
                kind, channel = raw[0] >> 4, raw[0] & 15
                if kind == 1:
                    voice = (channel, raw[1] & 127)
                    assert voice not in pressed, f"Overlapping same pitch: {voice}, tick {tick}"
                    pressed.add(voice)
                elif kind == 0:
                    pressed.remove((channel, raw[1]))
                maximum = max(maximum, len(pressed))
                descriptor = raw[0] | (128 if position == len(group) - 1 and tick < self.end else 0)
                stream.extend(bytes([descriptor]) + raw[1:])
            if tick < self.end:
                stream.extend(self.delay(times[index + 1] - tick))
        assert not pressed
        # MUS instrument declarations use 100 + GM percussion key. The Rust
        # synthesizer's internal GENMIDI percussion index is a separate value.
        instruments = sorted(set(self.programs.values()) | {100 + key for key in self.drums})
        start = 16 + 2 * len(instruments)
        assert len(stream) <= 65535
        score = b"MUS\x1a" + struct.pack("<6H", len(stream), start, len(self.programs), 0,
                                        len(instruments), 0)
        score += struct.pack("<" + "H" * len(instruments), *instruments) + stream
        path = ROOT / "music" / f"{self.key}.mus"
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(score)
        return {
            "id": f"iron_coast_stage2_music:{self.key}", "title": self.title,
            "file": f"music/{self.key}.mus", "tempo_bpm": self.bpm, "meter": "4/4",
            "bars": self.bars, "duration_ticks": self.end,
            "duration_seconds": self.end / CLOCK, "tonality": self.tonality,
            "sections": self.sections, "programs": self.programs,
            "percussion_keys": sorted(self.drums), "instrument_preload_table": instruments,
            "events": sum(len(group) for group in self.events.values()),
            "notes": self.note_count, "max_events_per_tick": max(map(len, self.events.values())),
            "max_simultaneous_notes": maximum, "bytes": len(score),
            "sha256": hashlib.sha256(score).hexdigest(), "dangling_notes": 0,
        }


def section(name, first, bars):
    return {"name": name, "first_bar": first, "bars": bars}


def assault():
    s = Score("assault", "Rivetline Assault", 144, 56,
              {0: 34, 1: 30, 2: 29, 3: 81, 4: 48},
              "D minor, B-flat/F contrast, A-major dominant and D tonic return",
              [section("Ignition", 0, 4), section("Rivetline", 4, 16),
               section("Container crosswind", 20, 12), section("Drydock bridge", 32, 8),
               section("Harbor assault", 40, 12), section("Home bearing", 52, 4)])
    a = [[74, None, 79, 77, 74, 81, 77, 72],
         [74, 77, None, 81, 84, 81, 79, 77],
         [72, None, 75, 77, 79, None, 77, 75],
         [73, 76, 81, 79, 76, None, 73, None]]
    b = [[77, 81, 84, 81, 79, 77, None, 74],
         [79, None, 84, 86, 84, 81, 79, 77],
         [76, 79, 84, None, 82, 79, 76, None],
         [73, 76, 79, 81, 79, 76, 73, None]]
    closing = [[79, 82, 81, 79, 77, None, 74, 77],
               [76, 79, 84, 82, 79, 76, 74, None],
               [73, 76, 81, 79, 76, 73, None, None],
               [74, None, 77, 74, None, None, 74, None]]
    for bar in range(s.bars):
        intro, bridge, ending = bar < 4, 32 <= bar < 40, bar >= 52
        root = ([43, 36, 33, 38][bar - 52] if ending else
                [43, 34, 36, 33][bar % 4] if bridge else
                [34, 41, 36, 33][bar % 4] if 20 <= bar < 32 else [38, 38, 34, 33][bar % 4])
        for step, interval in [(0, 0), (2, 0), (5, 7), (8, 0), (10, 12), (13, 7)]:
            if not bridge or step in [0, 8]:
                s.note(0, root + interval, bar, step, 2 if bridge else Fraction(3, 2),
                       100 if step in [0, 8] else 83)
        s.power(root, bar, [0, 8] if intro or bridge else [0, 3, 4, 6, 8, 11, 12, 14],
                3 if bridge else 1, 80 if not intro else 69)
        if bridge or bar % 4 == 0:
            s.pad(root, bar, velocity=60 if bridge else 44)
        if ending:
            s.phrase(2, closing[bar - 52], bar, 94)
        elif not intro and not bridge:
            s.phrase(2, b[bar % 4] if 20 <= bar < 32 else a[bar % 4], bar, 95)
        if bridge:
            for step, interval in [(0, 24), (4, 31), (8, 36), (12, 31)]:
                s.note(3, root + interval, bar, step, 3, 75)
        elif 40 <= bar < 52 and bar % 4 == 3:
            for step, pitch in [(10, 81), (12, 79), (14, 77)]:
                s.note(3, pitch, bar, step, 1, 66)
        s.kit(bar, "open" if intro or bridge else "drive",
              crash=bar in [4, 20, 32, 40, 52], fill=bar % 8 == 7)
    return s


def pursuit():
    s = Score("pursuit", "Undertow Pursuit", 168, 64,
              {0: 33, 1: 28, 2: 80, 3: 10, 4: 50},
              "F-sharp minor, D/E rising chase and C-sharp-major return",
              [section("Wake signal", 0, 4), section("Undertow", 4, 16),
               section("Crosscurrent", 20, 16), section("Fog channel", 36, 8),
               section("Raider wake", 44, 16), section("Bearing reset", 60, 4)])
    a = [[78, 85, 81, 83, 80, 78, 76, 81],
         [83, None, 85, 88, 86, 85, 81, 80],
         [81, 86, 85, 81, 80, 83, None, 80],
         [77, 80, 85, None, 83, 80, 77, None]]
    b = [[81, 85, 88, 86, 85, None, 81, 78],
         [80, 83, 88, 90, 88, 83, 80, None],
         [78, 81, 85, 88, 86, 85, 83, 81],
         [77, None, 80, 85, 83, 80, 77, None]]
    closing = [[81, 85, 86, 85, 81, 78, 76, None],
               [80, 83, 88, 86, 83, 80, 78, None],
               [77, 80, 85, 83, 80, 77, None, None],
               [78, None, 85, 81, 78, None, 78, None]]
    for bar in range(s.bars):
        intro, fog, ending = bar < 4, 36 <= bar < 44, bar >= 60
        root = ([38, 40, 37, 42][bar - 60] if ending else
                [42, 42, 38, 37][bar % 4] if fog else
                [38, 40, 42, 37][bar % 4] if 20 <= bar < 36 else [42, 38, 40, 37][bar % 4])
        for step, interval in [(0, 0), (3, 7), (4, 0), (6, 12), (8, 0), (11, 7), (12, 0), (14, 7)]:
            if not fog or step in [0, 4, 8, 12]:
                s.note(0, root + interval, bar, step, 1 if not fog else 2, 94 if step % 4 == 0 else 79)
        s.power(root, bar, [0, 6, 8, 14] if not fog else [0, 8], 1, 71)
        if bar % 4 == 0:
            s.pad(root, bar, 11, 44)
        if ending:
            s.phrase(2, closing[bar - 60], bar, 88)
        elif not intro and not fog:
            s.phrase(2, b[bar % 4] if 20 <= bar < 36 else a[bar % 4], bar, 90)
        if fog or bar % 4 == 2:
            # A short FM bell calls across the muted chase rhythm. This part is
            # pitched music, not a repeating digital nautical sound effect.
            for step, interval in [(1, 24), (5, 31), (9, 36), (13, 31)]:
                s.note(3, root + interval, bar, step, 2, 63 if fog else 49)
        s.kit(bar, "open" if fog else "chase", crash=bar in [4, 20, 36, 44, 60],
              fill=bar in [3, 19, 35, 43, 51, 59])
    return s


def finale():
    s = Score("finale", "Black Tide Rising", 126, 56,
              {0: 38, 1: 30, 2: 61, 3: 81, 4: 48},
              "C minor heroic/danger motif, A-flat/E-flat contrast and G-major dominant",
              [section("Black horizon", 0, 4), section("Beacon motif", 4, 12),
               section("Danger current", 16, 12), section("Eye of the tide", 28, 8),
               section("The last breakwater", 36, 16), section("Beacon return", 52, 4)])
    hero = [[72, None, 79, 75, 74, None, 77, 75],
            [80, 79, None, 75, 77, 80, 79, None],
            [75, 79, 82, 79, 77, 75, 74, None],
            [71, 74, 79, 77, 74, 71, 72, None]]
    danger = [[72, 75, 74, 71, 72, 79, 78, 77],
              [77, 80, 79, 75, 74, None, 77, 75],
              [74, 77, 80, 77, 75, 74, 71, None],
              [71, 74, 79, 82, 80, 79, 74, None]]
    closing = [[80, 79, 75, None, 77, 75, 72, None],
               [75, 79, 82, 79, 77, 75, 74, None],
               [71, 74, 79, 77, 74, 71, None, None],
               [72, None, 79, 75, 72, None, 72, None]]
    for bar in range(s.bars):
        intro, eye, rise, ending = bar < 4, 28 <= bar < 36, 36 <= bar < 52, bar >= 52
        root = ([32, 39, 31, 36][bar - 52] if ending else
                [36, 41, 38, 31][bar % 4] if eye or 16 <= bar < 28 else [36, 32, 39, 31][bar % 4])
        bass_slots = [0, 8] if intro or eye else [0, 4, 6, 8, 12, 14]
        for step in bass_slots:
            s.note(0, root + (7 if step in [6, 14] else 0), bar, step,
                   5 if eye else 2, 104 if step in [0, 8] else 86)
        s.power(root, bar, [0, 8] if intro or eye else [0, 2, 6, 8, 10, 14],
                5 if eye else 1, 81)
        if intro or eye or bar % 4 == 0:
            s.pad(root, bar, 15, 61 if eye else 51)
        if ending:
            s.phrase(2, closing[bar - 52], bar, 91)
        elif intro:
            for step, pitch in [(0, 60), (8, 67 if bar % 2 == 0 else 63)]:
                s.note(2, pitch, bar, step, 6, 78)
        elif not eye:
            s.phrase(2, danger[bar % 4] if 16 <= bar < 28 else hero[bar % 4], bar,
                     98 if rise else 87)
        if eye:
            for step, interval in [(0, 24), (4, 27), (8, 31), (12, 36)]:
                s.note(3, root + interval, bar, step, 3, 71)
        elif rise and bar % 4 == 3:
            for step, pitch in [(8, 79), (10, 77), (12, 74), (14, 71)]:
                s.note(3, pitch, bar, step, 1, 65)
        s.kit(bar, "open" if intro or eye else "ride" if rise else "drive",
              crash=bar in [0, 4, 16, 28, 36, 44, 52], fill=bar % 8 == 7)
    return s


def main():
    tracks = [score.write() for score in [assault(), pursuit(), finale()]]
    report = {
        "title": "Iron Coast II: Black Tide — Original Soundtrack",
        "authorship": "Original note sequences, harmony, arrangement and deterministic composer authored by Codex for this project.",
        "service_clock_hz": CLOCK, "recipe": "build_music.py",
        "recipe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "percussion_preload_encoding": "100 + GM percussion key (MUS convention)",
        "source_policy": "No proprietary/original-game melody, MIDI, recording or generated audio model is used. Stage1 recipe read only for MUS serialization contract.",
        "rendering": "Native Rust MusScore decoder and Mixer, using separately installed original GENMIDI FM instruments.",
        "loop_design": "Four-bar dominant-to-tonic returns, explicit per-note releases and all-notes-off at final service tick; next score downbeat starts on the same tonic. FM waveform phases are native, not a sample-exact PCM splice.",
        "tracks": tracks,
    }
    (ROOT / "provenance.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
