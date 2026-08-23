"""Deterministic tests for conservative harmony note decisions."""

from __future__ import annotations

import unittest
from dataclasses import dataclass

from trackscribe.cleanup_logic import NoteEvidence, clean_tracks


PARAMETERS = {
    "min_note_duration_ms": 35,
    "merge_same_pitch_gap_ms": 30,
    "chord_window_ms": 40,
    "pitch_support_threshold": 0.08,
    "neighbor_support_threshold": 0.08,
    "chord_pitch_support_threshold": 0.03,
    "chord_neighbor_support_threshold": 0.04,
    "onset_support_threshold": 0.18,
}


@dataclass
class Note:
    """Tiny pretty_midi-compatible note used by pure logic tests."""

    pitch: int
    start: float
    end: float
    velocity: int = 90


class FakeEvidence:
    """Provide deterministic scores and onset values without loading audio."""

    def __init__(
        self,
        scores: dict[int, NoteEvidence] | None = None,
        onsets: dict[float, float] | None = None,
    ) -> None:
        self.scores = scores or {}
        self.onsets = onsets or {}

    def score(self, note: Note) -> NoteEvidence:
        """Return a pitch-specific score or complete lack of support."""

        return self.scores.get(note.pitch, NoteEvidence(0.0, 0.0, 0.0))

    def onset_at(self, time_seconds: float) -> float:
        """Return an exact timestamp-specific onset strength."""

        return self.onsets.get(time_seconds, 0.0)


class CleanupLogicTests(unittest.TestCase):
    """Exercise every deletion and retrigger safety gate."""

    def test_very_short_unsupported_note_is_removed(self) -> None:
        tracks = [[Note(60, 1.0, 1.02)]]
        stats = clean_tracks(tracks, FakeEvidence(), PARAMETERS)
        self.assertEqual(tracks, [[]])
        self.assertEqual(stats.removed_notes[0]["reason"], "short_and_unsupported")

    def test_short_note_with_strong_audio_onset_is_kept(self) -> None:
        tracks = [[Note(60, 1.0, 1.02)]]
        evidence = FakeEvidence(scores={60: NoteEvidence(0.0, 0.0, 0.9)})
        stats = clean_tracks(tracks, evidence, PARAMETERS)
        self.assertEqual(stats.output_notes, 1)

    def test_tiny_gap_same_pitch_retrigger_is_merged(self) -> None:
        tracks = [[Note(60, 1.0, 1.24, 77), Note(60, 1.255, 1.52, 99)]]
        stats = clean_tracks(tracks, FakeEvidence(), PARAMETERS)
        self.assertEqual(stats.merged_retriggers, 1)
        self.assertEqual(len(tracks[0]), 1)
        self.assertEqual((tracks[0][0].end, tracks[0][0].velocity), (1.52, 77))

    def test_strong_new_onset_prevents_retrigger_merge(self) -> None:
        tracks = [[Note(60, 1.0, 1.24), Note(60, 1.255, 1.52)]]
        evidence = FakeEvidence(onsets={1.255: 0.9})
        stats = clean_tracks(tracks, evidence, PARAMETERS)
        self.assertEqual(stats.merged_retriggers, 0)
        self.assertEqual(len(tracks[0]), 2)

    def test_chord_group_uses_stricter_removal_threshold(self) -> None:
        tracks = [[Note(60, 1.0, 1.02), Note(64, 1.02, 1.04)]]
        weak = NoteEvidence(0.05, 0.05, 0.0)
        stats = clean_tracks(
            tracks, FakeEvidence(scores={60: weak, 64: weak}), PARAMETERS
        )
        self.assertEqual(stats.output_notes, 2)
        self.assertEqual(stats.removed_notes, [])


if __name__ == "__main__":
    unittest.main()
