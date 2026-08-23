"""Apply audio-derived velocities to an ADTOF drum MIDI transcription."""

from __future__ import annotations

import argparse
from pathlib import Path

import librosa
import numpy as np
import pretty_midi


def hit_strength(y: np.ndarray, sr: int, time_sec: float) -> float:
    """Estimate transient strength around one detected drum hit."""

    start = max(0, int((time_sec - 0.010) * sr))
    end = min(len(y), int((time_sec + 0.070) * sr))
    chunk = y[start:end]
    if not len(chunk):
        return 0.0
    rms = float(np.sqrt(np.mean(chunk**2)))
    peak = float(np.max(np.abs(chunk)))
    return 0.65 * rms + 0.35 * peak


def normalize(
    values: list[float], min_velocity: int, max_velocity: int, gamma: float
) -> list[int]:
    """Robustly map strengths to MIDI velocity while preserving quiet hits."""

    array = np.asarray(values, dtype=np.float32)
    if len(array) == 0:
        return []
    if len(array) == 1:
        return [min(max(100, min_velocity), max_velocity)]
    low, high = np.percentile(array, (10, 95))
    if high <= low + 1e-8:
        return [min(max(100, min_velocity), max_velocity)] * len(array)
    scaled = np.clip((array - low) / (high - low), 0.0, 1.0) ** gamma
    velocity = min_velocity + scaled * (max_velocity - min_velocity)
    return np.clip(np.rint(velocity), 1, 127).astype(int).tolist()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--midi", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--min-velocity", type=int, default=35)
    parser.add_argument("--max-velocity", type=int, default=127)
    parser.add_argument("--gamma", type=float, default=0.75)
    return parser


def main() -> None:
    """Group hits by drum pitch and write a velocity-adjusted MIDI file."""

    args = _parser().parse_args()
    y, sr = librosa.load(args.audio, sr=None, mono=True)
    midi = pretty_midi.PrettyMIDI(str(args.midi))
    groups: dict[int, list] = {}
    for instrument in midi.instruments:
        for note in instrument.notes:
            groups.setdefault(note.pitch, []).append(note)
    for pitch, notes in groups.items():
        velocities = normalize(
            [hit_strength(y, sr, note.start) for note in notes],
            args.min_velocity,
            args.max_velocity,
            args.gamma,
        )
        for note, velocity in zip(notes, velocities):
            note.velocity = velocity
        print(f"Pitch {pitch}: {len(notes)} hits | velocity {min(velocities)}-{max(velocities)}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    midi.write(str(args.out))
    print(f"Saved: {args.out}")


if __name__ == "__main__":
    main()
