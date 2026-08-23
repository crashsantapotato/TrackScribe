"""Pure conservative note cleanup decisions independent of audio libraries."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


class NoteLike(Protocol):
    """Mutable note attributes required from a MIDI backend."""

    pitch: int
    velocity: int
    start: float
    end: float


@dataclass(frozen=True)
class NoteEvidence:
    """Normalized spectral and onset evidence for one existing MIDI note."""

    pitch_support: float
    neighbor_support: float
    onset_support: float


class EvidenceProvider(Protocol):
    """Audio evidence interface consumed by deterministic cleanup logic."""

    def score(self, note: NoteLike) -> NoteEvidence:
        """Return support values for one note."""

    def onset_at(self, time_seconds: float) -> float:
        """Return normalized onset strength around a timestamp."""


@dataclass
class CleanupStats:
    """Cleanup counters and detailed removal diagnostics."""

    input_notes: int
    output_notes: int = 0
    merged_retriggers: int = 0
    removed_notes: list[dict[str, Any]] = field(default_factory=list)


def clean_tracks(
    tracks: list[list[NoteLike]],
    evidence: EvidenceProvider,
    parameters: dict[str, Any],
) -> CleanupStats:
    """Conservatively merge false retriggers and remove unsupported micro-notes."""

    stats = CleanupStats(input_notes=sum(len(track) for track in tracks))
    for track in tracks:
        merged, count = _merge_retriggers(track, evidence, parameters)
        track[:] = merged
        stats.merged_retriggers += count
    chord_notes = _chord_note_ids(tracks, parameters["chord_window_ms"])
    for track in tracks:
        kept = []
        for note in track:
            score = evidence.score(note)
            if _should_remove(note, score, id(note) in chord_notes, parameters):
                stats.removed_notes.append(_removed_record(note, score))
            else:
                kept.append(note)
        track[:] = kept
    stats.output_notes = sum(len(track) for track in tracks)
    return stats


def _merge_retriggers(
    notes: list[NoteLike], evidence: EvidenceProvider, parameters: dict[str, Any]
) -> tuple[list[NoteLike], int]:
    """Merge adjacent same-pitch notes unless audio shows a new attack."""

    threshold = parameters["merge_same_pitch_gap_ms"] / 1000.0
    onset_threshold = parameters["onset_support_threshold"]
    merged_count = 0
    output: list[NoteLike] = []
    for pitch in sorted({note.pitch for note in notes}):
        pitch_notes = sorted(
            (note for note in notes if note.pitch == pitch), key=lambda note: note.start
        )
        for note in pitch_notes:
            previous = output[-1] if output and output[-1].pitch == pitch else None
            gap = note.start - previous.end if previous else threshold + 1.0
            has_new_onset = evidence.onset_at(note.start) >= onset_threshold
            if previous and gap <= threshold and not has_new_onset:
                previous.end = max(previous.end, note.end)
                merged_count += 1
            else:
                output.append(note)
    return sorted(output, key=lambda note: (note.start, note.pitch)), merged_count


def _chord_note_ids(tracks: list[list[NoteLike]], window_ms: float) -> set[int]:
    """Return identities of notes belonging to near-simultaneous attacks."""

    notes = sorted((note for track in tracks for note in track), key=lambda note: note.start)
    chord_ids: set[int] = set()
    window = window_ms / 1000.0
    cursor = 0
    while cursor < len(notes):
        group = [notes[cursor]]
        cursor += 1
        while cursor < len(notes) and notes[cursor].start - group[0].start <= window:
            group.append(notes[cursor])
            cursor += 1
        if len(group) > 1:
            chord_ids.update(id(note) for note in group)
    return chord_ids


def _should_remove(
    note: NoteLike,
    score: NoteEvidence,
    in_chord: bool,
    parameters: dict[str, Any],
) -> bool:
    """Require every conservative rejection signal before deleting a note."""

    duration_ms = (note.end - note.start) * 1000.0
    pitch_key = (
        "chord_pitch_support_threshold" if in_chord else "pitch_support_threshold"
    )
    neighbor_key = (
        "chord_neighbor_support_threshold" if in_chord else "neighbor_support_threshold"
    )
    return (
        duration_ms < parameters["min_note_duration_ms"]
        and score.pitch_support < parameters[pitch_key]
        and score.neighbor_support < parameters[neighbor_key]
        and score.onset_support < parameters["onset_support_threshold"]
    )


def _removed_record(note: NoteLike, score: NoteEvidence) -> dict[str, Any]:
    """Serialize one rejected note and the evidence behind the decision."""

    return {
        "pitch": note.pitch,
        "start": round(note.start, 6),
        "end": round(note.end, 6),
        "duration_ms": round((note.end - note.start) * 1000.0, 3),
        "pitch_support": round(score.pitch_support, 4),
        "neighbor_support": round(score.neighbor_support, 4),
        "onset_support": round(score.onset_support, 4),
        "reason": "short_and_unsupported",
    }
