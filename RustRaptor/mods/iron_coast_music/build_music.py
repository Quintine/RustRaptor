#!/usr/bin/env python3
"""Author Coastal Steel as a deterministic checked MUS score, without MIDI tools.

The Rust game's MUS service clock is 70 Hz. A quarter lasts 30 ticks: 140 BPM.
56 four-beat bars give a 96-second loop. All musical phrases below are original
authored note sequences; no original-game music is read by this recipe.
"""

from collections import defaultdict
import hashlib
import json
from pathlib import Path
import struct


ROOT = Path(__file__).resolve().parent
BAR = 120
END = 56 * BAR
EVENTS = defaultdict(list)
PROGRAMS = {0: 33, 1: 30, 2: 29, 3: 81, 4: 48}
VOLUMES = {0: 86, 1: 72, 2: 85, 3: 58, 4: 42, 15: 83}
PAN = {0: 64, 1: 32, 2: 64, 3: 100, 4: 64, 15: 64}
SECTIONS = [
    {"name": "Approach", "first_bar": 0, "bars": 4},
    {"name": "Breakwater riff", "first_bar": 4, "bars": 12},
    {"name": "Offshore pursuit", "first_bar": 16, "bars": 12},
    {"name": "Stormwall bridge", "first_bar": 28, "bars": 8},
    {"name": "Citadel assault", "first_bar": 36, "bars": 16},
    {"name": "Return to coast", "first_bar": 52, "bars": 4},
]


def event(tick, priority, descriptor, payload):
    assert 0 <= tick <= END
    EVENTS[tick].append((priority, bytes([descriptor]) + bytes(payload)))


def control(channel, number, value):
    event(0, 0, 0x40 | channel, [number, value])


def note(channel, key, tick, duration, velocity):
    assert 0 <= key <= 127 and 0 < velocity <= 127 and duration > 0
    end = min(tick + duration, END - 1)
    event(tick, 2, 0x10 | channel, [key | 0x80, velocity])
    event(end, 1, channel, [key])


def variable_length(value):
    pieces = [value & 127]
    value >>= 7
    while value:
        pieces.append(value & 127)
        value >>= 7
    return bytes(v | (0x80 if i else 0) for i, v in reversed(list(enumerate(pieces))))


for channel, program in PROGRAMS.items():
    control(channel, 0, program)
for channel in VOLUMES:
    control(channel, 3, VOLUMES[channel])
    control(channel, 4, PAN[channel])

# E minor riff and its G-major/Am contrast. Each cell describes one eighth
# note per slot; None leaves a melodic breath. The refrain has a clear call
# (E-G-B-A) and downward answer (G-F#-E-D), with a four-bar tonic resolution.
MELODY_A = [
    [76, None, 79, 83, 81, 79, 78, 76],
    [74, 76, None, 79, 78, None, 76, None],
    [72, None, 76, 79, 83, 81, 79, 76],
    [74, 78, 81, None, 79, 78, 76, None],
]
MELODY_B = [
    [79, 83, 86, None, 83, 81, 79, None],
    [78, None, 81, 85, 83, 81, 78, 74],
    [76, 81, None, 84, 83, 81, 79, 76],
    [76, 79, 84, None, 83, 79, 76, None],
]
CADENCE = [
    [81, None, 78, 74, 78, 79, 81, None],
    [79, 76, 72, None, 76, None, 79, None],
    [78, 75, 71, None, 75, 78, 83, None],
    [83, 81, 79, 78, 76, None, None, None],
]


def harmony(bar):
    if bar < 4:
        return [40, 40, 36, 38][bar]
    if bar < 16:
        return [40, 40, 36, 38][(bar - 4) % 4]
    if bar < 28:
        return [43, 38, 45, 36][(bar - 16) % 4]
    if bar < 36:
        return [40, 35, 36, 38][(bar - 28) % 4]
    if bar < 52:
        return [40, 40, 36, 38][(bar - 36) % 4]
    return [38, 36, 35, 40][bar - 52]


for bar in range(56):
    tick = bar * BAR
    root = harmony(bar)
    intro = bar < 4
    bridge = 28 <= bar < 36
    climax = 36 <= bar < 52
    turnaround = bar >= 52

    # Fingered bass alternates the root and fifth, leaving space for the drums.
    for slot, interval in enumerate([0, 0, 7, 0, 12, 7, 0, 7]):
        if bridge and slot % 2:
            continue
        note(0, root + interval, tick + slot * 15,
             24 if bridge else 11, 97 if slot % 2 == 0 else 78)

    # Palm-muted FM power-chord pulses. Intro/bridge leave an open half-bar;
    # the assault adds an upper octave accent without dense voice stealing.
    slots = [0, 4, 6] if intro else [0, 2, 4, 6] if bridge else list(range(8))
    for slot in slots:
        start = tick + slot * 15
        length = 24 if bridge else 10
        velocity = 82 if slot % 2 == 0 else 63
        note(1, root + 12, start, length, velocity)
        note(1, root + 19, start, length, velocity - 9)
        if climax and slot in [0, 4]:
            note(1, root + 24, start, 9, 54)

    # A quiet sustained interval opens up the bridge and supports phrase starts.
    if bridge or bar % 4 == 0:
        note(4, root + 24, tick, BAR - 6, 64 if bridge else 47)
        note(4, root + 31, tick, BAR - 6, 49 if bridge else 37)

    melody = None
    if 4 <= bar < 16:
        melody = MELODY_A[(bar - 4) % 4]
    elif 16 <= bar < 28:
        melody = MELODY_B[(bar - 16) % 4]
    elif climax:
        melody = MELODY_A[(bar - 36) % 4]
    elif turnaround:
        melody = CADENCE[bar - 52]
    if melody:
        for slot, key in enumerate(melody):
            if key is not None:
                next_rest = slot == 7 or melody[slot + 1] is None
                length = min(25 if next_rest else 12, BAR - slot * 15 - 2)
                note(2, key, tick + slot * 15, length,
                     95 if slot in [0, 4] else 83)
        if climax and bar % 4 == 3:
            # A short response joins the refrain at the end of the phrase.
            for slot, key in [(4, 83), (5, 81), (6, 79), (7, 78)]:
                note(3, key, tick + slot * 15 + 3, 10, 71)
    elif bridge:
        for slot, key in enumerate([root + 24, root + 31, root + 36, root + 31]):
            note(3, key, tick + slot * 30, 23, 78)

    # Standard percussion on MUS channel 15. Repeating closed hats are softer
    # than snare/kick; phrase ends use a restrained tom fill, never a sample loop.
    hats = range(0, 16, 2) if intro or bridge else range(16)
    for slot in hats:
        start = tick + (slot * 15) // 2
        key = 46 if climax and slot == 14 else 42
        note(15, key, start, 5, 64 if slot % 4 == 0 else 40 if slot % 2 else 49)
    kick_slots = [0, 60] if intro or bridge else [0, 45, 60, 105]
    for offset in kick_slots:
        note(15, 36, tick + offset, 8, 111 if offset in [0, 60] else 83)
    for offset in [30, 90]:
        note(15, 38, tick + offset, 8, 104 if not bridge else 85)
    if bar in [4, 16, 28, 36, 52]:
        note(15, 49, tick, 18, 87)
    if bar in [3, 15, 27, 35, 43, 51, 54]:
        for offset, key in [(90, 47), (97, 47), (105, 45), (112, 43)]:
            note(15, key, tick + offset, 6, 85)

# Release every voice at the loop boundary. The final melody resolves to E;
# the next approach begins on E without a hanging voice or an abrupt chord flip.
for channel in VOLUMES:
    event(END - 1, 3, 0x30 | channel, [11])
event(END, 4, 0x60, [])

ticks = sorted(EVENTS)
stream = bytearray()
for index, tick in enumerate(ticks):
    group = sorted(EVENTS[tick], key=lambda e: e[0])
    for position, (_, raw) in enumerate(group):
        last = position == len(group) - 1
        descriptor = raw[0] | (0x80 if last and tick < END else 0)
        stream.extend(bytes([descriptor]) + raw[1:])
    if tick < END:
        stream.extend(variable_length(ticks[index + 1] - tick))

# MUS preload tables use 100 + percussion key, distinct from the synthesizer's
# internal GENMIDI bank indexing. Verified against all eleven local original
# scores containing percussion; the recipe never reads their melody data.
instruments = sorted(set(PROGRAMS.values()) | {100 + n for n in [36, 38, 42, 43, 45, 46, 47, 49]})
start = 16 + len(instruments) * 2
assert len(stream) <= 65535
header = b"MUS\x1a" + struct.pack("<6H", len(stream), start, len(PROGRAMS), 0,
                                      len(instruments), 0)
score = header + struct.pack("<" + "H" * len(instruments), *instruments) + stream
path = ROOT / "music/iron-coast.mus"
path.parent.mkdir(exist_ok=True)
path.write_bytes(score)

notes = sum(1 for group in EVENTS.values() for _, raw in group if raw[0] >> 4 == 1)
report = {
    "title": "Coastal Steel",
    "composer": "Original authored composition for RustRaptor Iron Coast",
    "format": "MUS with explicit note velocities and standard GM programs",
    "service_clock_hz": 70,
    "tempo_bpm": 140,
    "meter": "4/4",
    "bars": 56,
    "duration_ticks": END,
    "duration_seconds": END / 70,
    "tonality": "E minor with G-major contrast and B-major turnaround",
    "sections": SECTIONS,
    "channels": {str(k): v for k, v in PROGRAMS.items()} | {"15": "standard percussion"},
    "instrument_preload_table": instruments,
    "percussion_preload_encoding": "100 + MIDI percussion key (MUS convention)",
    "events": sum(len(g) for g in EVENTS.values()),
    "notes": notes,
    "groups": len(EVENTS),
    "max_events_per_tick": max(len(g) for g in EVENTS.values()),
    "file": "music/iron-coast.mus",
    "bytes": len(score),
    "sha256": hashlib.sha256(score).hexdigest(),
    "recipe": "build_music.py",
    "sources": "Authored note sequences and deterministic arrangement; no original-game score or recording used",
    "rendering": "Existing Rust MUS decoder and GENMIDI/OPL3 synthesizer; original instrument bank remains external",
}
(ROOT / "provenance.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
