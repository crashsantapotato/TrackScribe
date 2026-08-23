"""Pitch-aware CQT and onset measurements for harmony velocity recovery."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Protocol

from trackscribe.harmony_velocity_logic import VelocityFeature


class TimedNote(Protocol):
    """Note timing and pitch attributes required by the audio analyser."""

    pitch: int
    start: float
    end: float


class AudioVelocityEvidence:
    """Precompute spectral data and measure local evidence for MIDI notes."""

    def __init__(self, audio_path: Path, parameters: dict[str, Any]) -> None:
        """Load mono audio and prepare CQT/onset matrices when signal is present."""

        import librosa
        import numpy as np

        self.librosa = librosa
        self.np = np
        self.parameters = parameters
        self.audio, self.sample_rate = librosa.load(audio_path, sr=None, mono=True)
        rms = float(np.sqrt(np.mean(self.audio**2))) if len(self.audio) else 0.0
        self.silent = rms <= float(parameters["silence_rms_threshold"])
        self.hop_length = int(parameters["hop_length"])
        self.minimum_midi = int(parameters["minimum_midi"])
        self.bins_per_octave = int(parameters["bins_per_octave"])
        self.cqt = np.empty((0, 0))
        self.onset = np.empty(0)
        if not self.silent:
            maximum_midi = int(parameters["maximum_midi"])
            semitone_bins = self.bins_per_octave / 12.0
            n_bins = round((maximum_midi - self.minimum_midi) * semitone_bins) + 1
            self.cqt = np.abs(
                librosa.cqt(
                    self.audio,
                    sr=self.sample_rate,
                    hop_length=self.hop_length,
                    fmin=librosa.midi_to_hz(self.minimum_midi),
                    n_bins=n_bins,
                    bins_per_octave=self.bins_per_octave,
                )
            )
            self.onset = librosa.onset.onset_strength(
                y=self.audio, sr=self.sample_rate, hop_length=self.hop_length
            )

    def measure(self, note: TimedNote) -> VelocityFeature:
        """Return pitch-band attack/body energy and onset strength for one note."""

        if self.silent:
            return VelocityFeature(0.0, 0.0, 0.0)
        attack = self._frames(
            note.start - float(self.parameters["onset_pre_ms"]) / 1000.0,
            note.start + float(self.parameters["onset_window_ms"]) / 1000.0,
        )
        sustain_end = min(
            note.end,
            note.start + float(self.parameters["sustain_window_ms"]) / 1000.0,
        )
        sustain = self._frames(note.start, max(sustain_end, note.start))
        curve = self._pitch_curve(note.pitch)
        return VelocityFeature(
            attack=self._aggregate(curve[attack], 85.0),
            sustain=self._aggregate(curve[sustain], 70.0),
            onset=self._onset_at(note.start),
        )

    def _pitch_curve(self, pitch: int):
        """Combine fundamental and harmonic CQT bins with tuning tolerance."""

        semitone_bins = self.bins_per_octave / 12.0
        fundamental = round((pitch - self.minimum_midi) * semitone_bins)
        neighbors = int(self.parameters["neighbor_bins"])
        weights = [float(value) for value in self.parameters["harmonic_weights"]]
        curves = []
        used_weights = []
        for harmonic, weight in enumerate(weights, start=1):
            offset = round(self.bins_per_octave * math.log2(harmonic))
            center = fundamental + offset
            indices = [
                center + delta
                for delta in range(-neighbors, neighbors + 1)
                if 0 <= center + delta < self.cqt.shape[0]
            ]
            if indices:
                curves.append(self.np.max(self.cqt[indices], axis=0) * weight)
                used_weights.append(weight)
        if not curves:
            return self.np.zeros(self.cqt.shape[1])
        return self.np.sum(self.np.stack(curves), axis=0) / max(sum(used_weights), 1e-12)

    def _frames(self, start: float, end: float) -> slice:
        """Convert a time interval to a clipped, non-empty frame slice."""

        indices = self.librosa.time_to_frames(
            [max(start, 0.0), max(end, 0.0)],
            sr=self.sample_rate,
            hop_length=self.hop_length,
        )
        first = max(0, min(int(indices[0]), self.cqt.shape[1] - 1))
        last = max(first + 1, min(int(indices[1]) + 1, self.cqt.shape[1]))
        return slice(first, last)

    def _onset_at(self, start: float) -> float:
        """Measure broadband onset evidence around a note attack."""

        window = float(self.parameters["onset_window_ms"]) / 1000.0
        frames = self._frames(start - window / 2.0, start + window)
        last = min(frames.stop, len(self.onset))
        return float(self.np.max(self.onset[frames.start:last])) if last > frames.start else 0.0

    def _aggregate(self, values, percentile: float) -> float:
        """Return a robust amplitude for a local pitch-band curve."""

        return float(self.np.percentile(values, percentile)) if len(values) else 0.0
