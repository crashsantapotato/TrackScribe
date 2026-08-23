"""MIDI event helpers that preserve every non-velocity field exactly."""

from __future__ import annotations

import bisect
from dataclasses import dataclass
from typing import Any


@dataclass
class MidiNote:
    """Location, pitch, and exact tick/second timing of one MIDI note-on event."""

    track_index: int
    event_index: int
    channel: int
    pitch: int
    start_tick: int
    end_tick: int
    start: float
    end: float
    velocity: int


def collect_notes(midi: Any) -> list[MidiNote]:
    """Collect positive note-ons and match their offsets without changing event order."""

    tempo_map = _TempoMap(midi)
    notes: list[MidiNote] = []
    for track_index, track in enumerate(midi.tracks):
        tick = 0
        active: dict[tuple[int, int], list[int]] = {}
        for event_index, message in enumerate(track):
            tick += int(message.time)
            channel = int(getattr(message, "channel", 0))
            pitch = int(getattr(message, "note", -1))
            key = (channel, pitch)
            is_on = message.type == "note_on" and int(message.velocity) > 0
            is_off = message.type == "note_off" or (
                message.type == "note_on" and int(message.velocity) == 0
            )
            if is_on:
                active.setdefault(key, []).append(len(notes))
                seconds = tempo_map.seconds(tick)
                notes.append(
                    MidiNote(
                        track_index,
                        event_index,
                        channel,
                        pitch,
                        tick,
                        tick,
                        seconds,
                        seconds,
                        int(message.velocity),
                    )
                )
            elif is_off and active.get(key):
                note = notes[active[key].pop(0)]
                note.end_tick = tick
                note.end = tempo_map.seconds(tick)
    return notes


def apply_velocities(midi: Any, notes: list[MidiNote], velocities: list[int]) -> None:
    """Replace only velocities at the collected positive note-on event locations."""

    if len(notes) != len(velocities):
        raise ValueError("MIDI note and velocity counts differ")
    for note, velocity in zip(notes, velocities):
        midi.tracks[note.track_index][note.event_index].velocity = int(velocity)


def structure_signature(midi: Any) -> tuple:
    """Freeze every MIDI event field while masking positive note-on velocity values."""

    tracks = []
    for track in midi.tracks:
        events = []
        for message in track:
            fields = message.dict()
            if message.type == "note_on" and int(message.velocity) > 0:
                fields = dict(fields)
                fields["velocity"] = "<note-velocity>"
            events.append(tuple(sorted((key, _freeze(value)) for key, value in fields.items())))
        tracks.append(tuple(events))
    return tuple(tracks)


class _TempoMap:
    """Convert absolute MIDI ticks to seconds across global tempo changes."""

    def __init__(self, midi: Any) -> None:
        """Build ordered tempo segments from all MIDI tracks."""

        events = [(0, -1, -1, 500000)]
        for track_index, track in enumerate(midi.tracks):
            tick = 0
            for event_index, message in enumerate(track):
                tick += int(message.time)
                if message.type == "set_tempo":
                    events.append((tick, track_index, event_index, int(message.tempo)))
        events.sort()
        self.ticks_per_beat = int(midi.ticks_per_beat)
        self.ticks: list[int] = []
        self.seconds_at_tick: list[float] = []
        self.tempos: list[int] = []
        elapsed = 0.0
        previous_tick = 0
        previous_tempo = 500000
        for tick, _track, _event, tempo in events:
            if tick == self.ticks[-1] if self.ticks else False:
                self.tempos[-1] = tempo
                previous_tempo = tempo
                continue
            elapsed += _ticks_to_seconds(
                tick - previous_tick, previous_tempo, self.ticks_per_beat
            )
            self.ticks.append(tick)
            self.seconds_at_tick.append(elapsed)
            self.tempos.append(tempo)
            previous_tick = tick
            previous_tempo = tempo

    def seconds(self, tick: int) -> float:
        """Convert one absolute tick position to elapsed seconds."""

        index = max(0, bisect.bisect_right(self.ticks, tick) - 1)
        return self.seconds_at_tick[index] + _ticks_to_seconds(
            tick - self.ticks[index], self.tempos[index], self.ticks_per_beat
        )


def _ticks_to_seconds(ticks: int, tempo: int, ticks_per_beat: int) -> float:
    """Convert a tick delta using one constant microseconds-per-beat tempo."""

    return ticks * tempo / 1_000_000.0 / ticks_per_beat


def _freeze(value: Any) -> Any:
    """Convert mutable MIDI field containers into comparable tuples."""

    if isinstance(value, (list, tuple, bytes, bytearray)):
        return tuple(value)
    return value
