"""Tests for exact non-velocity preservation in MIDI event helpers."""

from __future__ import annotations

import unittest

from trackscribe.harmony_velocity_midi import (
    apply_velocities,
    collect_notes,
    structure_signature,
)


class FakeMessage:
    """Minimal mutable mido-like message used by dependency-free tests."""

    def __init__(self, message_type: str, time: int = 0, **fields) -> None:
        self.type = message_type
        self.time = time
        self._fields = fields
        for key, value in fields.items():
            setattr(self, key, value)

    def dict(self) -> dict:
        """Return the event fields in mido-compatible dictionary form."""

        return {"type": self.type, "time": self.time, **self._fields_from_attributes()}

    def _fields_from_attributes(self) -> dict:
        """Read mutable attributes so velocity edits appear in signatures."""

        return {key: getattr(self, key) for key in self._fields}


class FakeMidi:
    """Minimal multi-track MIDI container."""

    ticks_per_beat = 480

    def __init__(self) -> None:
        """Create a tempo track and a melodic track with two ordered notes."""

        self.tracks = [
            [FakeMessage("set_tempo", tempo=500000)],
            [
                FakeMessage("program_change", channel=0, program=23),
                FakeMessage("note_on", time=480, channel=0, note=60, velocity=100),
                FakeMessage("note_off", time=240, channel=0, note=60, velocity=0),
                FakeMessage("note_on", time=120, channel=0, note=64, velocity=100),
                FakeMessage("note_on", time=240, channel=0, note=64, velocity=0),
            ],
        ]


class HarmonyVelocityMidiTests(unittest.TestCase):
    """Verify exact track/event timing and order while velocities change."""

    def test_collect_notes_preserves_event_order_and_converts_tempo(self) -> None:
        notes = collect_notes(FakeMidi())
        self.assertEqual([note.pitch for note in notes], [60, 64])
        self.assertEqual([note.start_tick for note in notes], [480, 840])
        self.assertEqual([note.end_tick for note in notes], [720, 1080])
        self.assertAlmostEqual(notes[0].start, 0.5)
        self.assertAlmostEqual(notes[1].end, 1.125)

    def test_apply_changes_only_positive_note_on_velocities(self) -> None:
        midi = FakeMidi()
        notes = collect_notes(midi)
        before = structure_signature(midi)
        apply_velocities(midi, notes, [55, 110])
        self.assertEqual(structure_signature(midi), before)
        self.assertEqual(midi.tracks[1][1].velocity, 55)
        self.assertEqual(midi.tracks[1][3].velocity, 110)
        self.assertEqual(midi.tracks[1][2].velocity, 0)
        self.assertEqual(midi.tracks[1][0].program, 23)

    def test_velocity_count_mismatch_is_rejected(self) -> None:
        midi = FakeMidi()
        with self.assertRaises(ValueError):
            apply_velocities(midi, collect_notes(midi), [70])


if __name__ == "__main__":
    unittest.main()
