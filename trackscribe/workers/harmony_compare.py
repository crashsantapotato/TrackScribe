"""Copy raw backend hypotheses and write neutral MIDI summary metrics."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import statistics
from pathlib import Path

from trackscribe.harmony_velocity_logic import velocity_statistics

def _parser() -> argparse.ArgumentParser:
    """Build the worker CLI used by the compare stage adapter."""

    parser = argparse.ArgumentParser()
    parser.add_argument("transkun_raw", type=Path)
    parser.add_argument("amt_raw", type=Path)
    parser.add_argument("amt_velocity", type=Path)
    parser.add_argument("transkun_ab", type=Path)
    parser.add_argument("amt_ab", type=Path)
    parser.add_argument("amt_velocity_ab", type=Path)
    parser.add_argument("diagnostics", type=Path)
    parser.add_argument("--transkun-seconds", type=float, required=True)
    parser.add_argument("--amt-seconds", type=float, required=True)
    return parser


def midi_metrics(path: Path, backend: str, processing_seconds: float) -> dict:
    """Calculate descriptive pitch, duration, velocity, and polyphony metrics."""

    import pretty_midi

    midi = pretty_midi.PrettyMIDI(str(path))
    notes = [note for instrument in midi.instruments for note in instrument.notes]
    durations = [note.end - note.start for note in notes]
    pitches = [note.pitch for note in notes]
    velocities = [note.velocity for note in notes]
    span = max((note.end for note in notes), default=0.0)
    return {
        "backend": backend,
        "note_count": len(notes),
        "pitch_min": min(pitches) if pitches else None,
        "pitch_max": max(pitches) if pitches else None,
        "unique_pitches": sorted(set(pitches)),
        "mean_note_duration": _mean(durations),
        "median_note_duration": _median(durations),
        "polyphony_max": _maximum_polyphony(notes),
        "notes_per_second": round(len(notes) / span, 4) if span else 0.0,
        "mean_velocity": _mean(velocities),
        "median_velocity": _median(velocities),
        "processing_seconds": round(processing_seconds, 3),
    }


def export_comparison(
    transkun_raw: Path,
    amt_raw: Path,
    amt_velocity: Path,
    transkun_ab: Path,
    amt_ab: Path,
    amt_velocity_ab: Path,
    diagnostics: Path,
    transkun_seconds: float,
    amt_seconds: float,
) -> dict:
    """Preserve raw files byte-for-byte and write non-ranking diagnostics."""

    transkun_ab.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(transkun_raw, transkun_ab)
    shutil.copy2(amt_raw, amt_ab)
    shutil.copy2(amt_velocity, amt_velocity_ab)
    report = {
        "purpose": "descriptive raw transcription metrics; no automatic ranking",
        "backends": {
            "transkun": midi_metrics(transkun_ab, "transkun", transkun_seconds),
            "agnostic-amt": midi_metrics(amt_ab, "agnostic-amt", amt_seconds),
        },
        "velocity_pass": {
            "purpose": "descriptive AMT velocity statistics; no automatic ranking",
            "raw": velocity_metrics(amt_ab),
            "processed": velocity_metrics(amt_velocity_ab),
        },
    }
    temporary = diagnostics.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, indent=2), encoding="utf-8")
    os.replace(temporary, diagnostics)
    return report


def velocity_metrics(path: Path) -> dict:
    """Calculate descriptive velocity-only metrics for one MIDI file."""

    import pretty_midi

    midi = pretty_midi.PrettyMIDI(str(path))
    velocities = [
        note.velocity for instrument in midi.instruments for note in instrument.notes
    ]
    return {"note_count": len(velocities), **velocity_statistics(velocities)}


def _maximum_polyphony(notes: list) -> int:
    """Return maximum simultaneous note count with offsets applied before onsets."""

    events = [(note.start, 1) for note in notes] + [(note.end, -1) for note in notes]
    active = maximum = 0
    for _time, delta in sorted(events, key=lambda event: (event[0], event[1])):
        active += delta
        maximum = max(maximum, active)
    return maximum


def _mean(values: list[float | int]) -> float:
    """Return a rounded arithmetic mean or zero for an empty list."""

    return round(statistics.fmean(values), 4) if values else 0.0


def _median(values: list[float | int]) -> float:
    """Return a rounded median or zero for an empty list."""

    return round(float(statistics.median(values)), 4) if values else 0.0


def main() -> int:
    """Run the compare worker from stage-provided paths and timings."""

    args = _parser().parse_args()
    report = export_comparison(
        args.transkun_raw,
        args.amt_raw,
        args.amt_velocity,
        args.transkun_ab,
        args.amt_ab,
        args.amt_velocity_ab,
        args.diagnostics,
        args.transkun_seconds,
        args.amt_seconds,
    )
    print(json.dumps({key: value["note_count"] for key, value in report["backends"].items()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
