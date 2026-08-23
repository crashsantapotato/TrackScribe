"""Worker CLI producing conservative harmony MIDI and cleanup diagnostics."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import time
from collections import Counter
from pathlib import Path


def _parser() -> argparse.ArgumentParser:
    """Build worker arguments passed by the stage adapter."""

    parser = argparse.ArgumentParser()
    parser.add_argument("audio", type=Path)
    parser.add_argument("raw_midi", type=Path)
    parser.add_argument("output_midi", type=Path)
    parser.add_argument("diagnostics", type=Path)
    parser.add_argument("--settings-json", required=True)
    return parser


def run(
    audio: Path,
    raw_midi: Path,
    output_midi: Path,
    diagnostics: Path,
    parameters: dict,
) -> dict:
    """Run cleanup or make an exact raw copy when the stage is disabled."""

    import pretty_midi

    started = time.perf_counter()
    midi = pretty_midi.PrettyMIDI(str(raw_midi))
    input_notes = sum(len(instrument.notes) for instrument in midi.instruments)
    if not parameters["enabled"]:
        copy_raw_midi(raw_midi, output_midi)
        report = _report(input_notes, input_notes, 0, [], parameters, started)
    else:
        from trackscribe.cleanup_audio import AudioEvidence, NullEvidence
        from trackscribe.cleanup_logic import clean_tracks

        evidence = (
            AudioEvidence(audio, parameters)
            if parameters["audio_validation"]
            else NullEvidence()
        )
        tracks = [instrument.notes for instrument in midi.instruments]
        stats = clean_tracks(tracks, evidence, parameters)
        midi.write(str(output_midi))
        report = _report(
            stats.input_notes,
            stats.output_notes,
            stats.merged_retriggers,
            stats.removed_notes,
            parameters,
            started,
        )
    _write_json_atomic(diagnostics, report)
    return report


def copy_raw_midi(raw_midi: Path, output_midi: Path) -> None:
    """Copy raw MIDI byte-for-byte when cleanup is explicitly disabled."""

    shutil.copy2(raw_midi, output_midi)


def _report(
    input_notes: int,
    output_notes: int,
    merged: int,
    removed_notes: list[dict],
    parameters: dict,
    started: float,
) -> dict:
    """Build the diagnostic summary written beside the final MIDI."""

    reasons = Counter(note["reason"] for note in removed_notes)
    return {
        "input_notes": input_notes,
        "output_notes": output_notes,
        "removed": dict(sorted(reasons.items())),
        "removed_total": len(removed_notes),
        "merged_retriggers": merged,
        "parameters": parameters,
        "removed_notes": removed_notes,
        "duration_seconds": round(time.perf_counter() - started, 3),
    }


def _write_json_atomic(path: Path, report: dict) -> None:
    """Commit diagnostics atomically to avoid partially written cache outputs."""

    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    os.replace(temporary, path)


def main() -> int:
    """Parse arguments and execute the cleanup worker."""

    args = _parser().parse_args()
    parameters = json.loads(args.settings_json)
    report = run(
        args.audio,
        args.raw_midi,
        args.output_midi,
        args.diagnostics,
        parameters,
    )
    summary_keys = (
        "input_notes",
        "output_notes",
        "removed_total",
        "merged_retriggers",
    )
    print(json.dumps({key: report[key] for key in summary_keys}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
