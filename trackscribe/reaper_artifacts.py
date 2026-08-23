"""Resolve selected TrackScribe outputs before handing them to REAPER."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import mido


@dataclass(frozen=True)
class ReaperSelection:
    """User-selectable project outputs sent to one REAPER import."""

    drums: bool = True
    bass: bool = True
    harmony: bool = True
    vocals: bool = True


@dataclass(frozen=True)
class ReaperArtifact:
    """One verified, non-empty source media file and its target track name."""

    key: str
    track_name: str
    path: Path
    media_type: str
    note_count: int | None = None


@dataclass(frozen=True)
class SkippedArtifact:
    """One deliberately omitted selection with a user-facing reason."""

    key: str
    reason: str


_SPECS = (
    ("drums", "TrackScribe - Drums", "midi/drums.mid", "midi"),
    ("bass", "TrackScribe - Bass", "midi/bass.mid", "midi"),
    ("harmony", "TrackScribe - Harmony", "midi/harmony.mid", "midi"),
    ("vocals", "TrackScribe - Vocals", "stems/vocals.wav", "audio"),
)


def midi_note_count(path: Path) -> int:
    """Count sounding note-on events without modifying the MIDI file."""

    midi = mido.MidiFile(str(path), clip=True)
    return sum(
        1
        for track in midi.tracks
        for message in track
        if message.type == "note_on" and message.velocity > 0
    )


def collect_reaper_artifacts(
    project_dir: str | Path,
    selection: ReaperSelection,
) -> tuple[tuple[ReaperArtifact, ...], tuple[SkippedArtifact, ...]]:
    """Return selected existing artifacts while skipping missing or empty files."""

    project = Path(project_dir).expanduser().resolve()
    artifacts: list[ReaperArtifact] = []
    skipped: list[SkippedArtifact] = []
    for key, track_name, relative, media_type in _SPECS:
        if not getattr(selection, key):
            skipped.append(SkippedArtifact(key, "not selected"))
            continue
        path = project / relative
        if not path.is_file():
            skipped.append(SkippedArtifact(key, "file not found"))
            continue
        note_count = midi_note_count(path) if media_type == "midi" else None
        if note_count == 0:
            skipped.append(SkippedArtifact(key, "MIDI contains 0 notes"))
            continue
        artifacts.append(
            ReaperArtifact(key, track_name, path, media_type, note_count)
        )
    return tuple(artifacts), tuple(skipped)
