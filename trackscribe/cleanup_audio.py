"""Harmonic-aware CQT and onset evidence for conservative MIDI cleanup."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import librosa
import numpy as np

from trackscribe.cleanup_logic import NoteEvidence, NoteLike


class AudioEvidence:
    """Precompute normalized spectral evidence from the original other stem."""

    def __init__(self, audio_path: Path, parameters: dict[str, Any]) -> None:
        """Load audio and build a chromatic CQT plus onset envelope."""

        audio, self.sample_rate = librosa.load(audio_path, sr=None, mono=True)
        self.hop_length = int(parameters.get("hop_length", 512))
        self.minimum_midi = int(parameters.get("minimum_midi", 21))
        maximum_midi = int(parameters.get("maximum_midi", 108))
        cqt = np.abs(
            librosa.cqt(
                audio,
                sr=self.sample_rate,
                hop_length=self.hop_length,
                fmin=librosa.midi_to_hz(self.minimum_midi),
                n_bins=maximum_midi - self.minimum_midi + 1,
                bins_per_octave=12,
            )
        )
        frame_reference = np.percentile(cqt, 95, axis=0, keepdims=True) + 1e-9
        self.relative_cqt = np.clip(cqt / frame_reference, 0.0, 1.0)
        onset = librosa.onset.onset_strength(
            y=audio, sr=self.sample_rate, hop_length=self.hop_length
        )
        onset_reference = max(float(np.percentile(onset, 95)), 1e-9)
        self.onset = np.clip(onset / onset_reference, 0.0, 1.0)
        self.onset_window_ms = float(parameters.get("onset_window_ms", 30.0))

    def score(self, note: NoteLike) -> NoteEvidence:
        """Measure fundamental, second/third harmonic, neighboring, and onset support."""

        frames = self._note_frames(note.start, note.end)
        harmonic_bins = self._harmonic_bins(note.pitch)
        if not harmonic_bins or frames.stop <= frames.start:
            return NoteEvidence(1.0, 1.0, self.onset_at(note.start))
        weights = (1.0, 0.8, 0.65)
        central = [self.relative_cqt[index, frames] * weights[position]
                   for position, index in enumerate(harmonic_bins)]
        neighbors = [
            self.relative_cqt[index + offset, frames] * weights[position]
            for position, index in enumerate(harmonic_bins)
            for offset in (-1, 1)
            if 0 <= index + offset < self.relative_cqt.shape[0]
        ]
        pitch_support = self._aggregate(central)
        neighbor_support = self._aggregate(neighbors)
        return NoteEvidence(pitch_support, neighbor_support, self.onset_at(note.start))

    def onset_at(self, time_seconds: float) -> float:
        """Return peak onset evidence within the configured window."""

        center = int(librosa.time_to_frames(
            time_seconds, sr=self.sample_rate, hop_length=self.hop_length
        ))
        radius = max(
            1,
            int(
                self.onset_window_ms
                * self.sample_rate
                / (1000.0 * self.hop_length)
            ),
        )
        start = max(0, center - radius)
        end = min(len(self.onset), center + radius + 1)
        return float(np.max(self.onset[start:end])) if end > start else 0.0

    def _note_frames(self, start: float, end: float) -> slice:
        """Convert note time bounds to a non-empty, clipped CQT frame slice."""

        frame_start, frame_end = librosa.time_to_frames(
            [start, end], sr=self.sample_rate, hop_length=self.hop_length
        )
        start_index = max(0, min(int(frame_start), self.relative_cqt.shape[1] - 1))
        end_index = max(start_index + 1, min(int(frame_end) + 1, self.relative_cqt.shape[1]))
        return slice(start_index, end_index)

    def _harmonic_bins(self, pitch: int) -> list[int]:
        """Map a pitch and its first two harmonics into available CQT bins."""

        indices = [pitch - self.minimum_midi + offset for offset in (0, 12, 19)]
        return [index for index in indices if 0 <= index < self.relative_cqt.shape[0]]

    @staticmethod
    def _aggregate(curves: list[np.ndarray]) -> float:
        """Combine harmonic curves and return robust temporal support."""

        if not curves:
            return 0.0
        combined = np.max(np.stack(curves), axis=0)
        return float(np.percentile(combined, 75))


class NullEvidence:
    """Conservative evidence used when audio validation is disabled."""

    def score(self, note: NoteLike) -> NoteEvidence:
        """Protect every note when no audio evidence is available."""

        return NoteEvidence(1.0, 1.0, 1.0)

    def onset_at(self, time_seconds: float) -> float:
        """Protect every possible retrigger when onset evidence is unavailable."""

        return 1.0
