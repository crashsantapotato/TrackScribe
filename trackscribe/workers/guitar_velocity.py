"""Apply chord-aware audio-derived velocities to a guitar MIDI transcription."""

from __future__ import annotations

import argparse
from pathlib import Path

import librosa
import numpy as np
import pretty_midi


def robust_normalize(values: np.ndarray) -> np.ndarray:
    """Scale a feature using its 10th and 95th percentiles."""

    low, high = np.percentile(values, (10, 95))
    if high <= low + 1e-12:
        return np.full_like(values, 0.5)
    return np.clip((values - low) / (high - low), 0.0, 1.0)


def group_attacks(notes: list, chord_window: float) -> list[list]:
    """Group near-simultaneous notes so every chord receives one velocity."""

    groups: list[list] = []
    current: list = []
    anchor: float | None = None
    for note in notes:
        if anchor is None or note.start - anchor <= chord_window:
            current.append(note)
            anchor = note.start if anchor is None else anchor
        else:
            groups.append(current)
            current = [note]
            anchor = note.start
    if current:
        groups.append(current)
    return groups


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--midi", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--min-velocity", type=int, default=42)
    parser.add_argument("--max-velocity", type=int, default=122)
    parser.add_argument("--gamma", type=float, default=0.80)
    parser.add_argument("--chord-window-ms", type=float, default=30.0)
    return parser


def main() -> None:
    """Measure attack features and write a guitar MIDI with expressive velocities."""

    args = _parser().parse_args()
    y, sr = librosa.load(args.audio, sr=None, mono=True)
    midi = pretty_midi.PrettyMIDI(str(args.midi))
    notes = sorted(
        [note for instrument in midi.instruments for note in instrument.notes],
        key=lambda note: note.start,
    )
    groups = group_attacks(notes, args.chord_window_ms / 1000.0)
    if not groups:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        midi.write(str(args.out))
        print(f"Saved {args.out} | 0 notes")
        return
    hop = 256
    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
    onset_times = librosa.frames_to_time(np.arange(len(onset_env)), sr=sr, hop_length=hop)

    def segment(time_sec: float, start: float, end: float) -> np.ndarray:
        return y[max(0, int((time_sec + start) * sr)) : min(len(y), int((time_sec + end) * sr))]

    def features(time_sec: float) -> tuple[float, float, float, float]:
        pre = segment(time_sec, -0.080, -0.010)
        post = segment(time_sec, 0.000, 0.120)
        attack = segment(time_sec, 0.000, 0.050)
        rms_post = float(np.sqrt(np.mean(post**2))) if len(post) else 0.0
        rms_pre = float(np.sqrt(np.mean(pre**2))) if len(pre) else 0.0
        peak = float(np.max(np.abs(attack))) if len(attack) else 0.0
        mask = (onset_times >= time_sec - 0.030) & (onset_times <= time_sec + 0.060)
        onset = float(np.max(onset_env[mask])) if np.any(mask) else 0.0
        return rms_post, peak, onset, max(rms_post - rms_pre, 0.0)

    values = np.asarray([features(group[0].start) for group in groups])
    score = (
        0.40 * robust_normalize(np.log1p(values[:, 0] * 100.0))
        + 0.20 * robust_normalize(np.log1p(values[:, 1] * 50.0))
        + 0.30 * robust_normalize(np.log1p(values[:, 2]))
        + 0.10 * robust_normalize(np.log1p(values[:, 3] * 100.0))
    )
    velocities = np.rint(
        args.min_velocity
        + np.clip(score, 0.0, 1.0) ** args.gamma
        * (args.max_velocity - args.min_velocity)
    ).astype(int)
    for group, velocity in zip(groups, velocities):
        for note in group:
            note.velocity = int(np.clip(velocity, 1, 127))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    midi.write(str(args.out))
    print(f"Saved {args.out} | {len(notes)} notes | {len(groups)} attacks")


if __name__ == "__main__":
    main()
