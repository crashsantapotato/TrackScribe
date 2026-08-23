"""Worker that replaces AMT note-on velocities using pitch-aware audio evidence."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import time
from pathlib import Path
from typing import Any

from trackscribe.harmony_velocity_logic import (
    assign_velocities,
    velocity_statistics,
)
from trackscribe.harmony_velocity_midi import (
    apply_velocities,
    collect_notes,
    structure_signature,
)


def _parser() -> argparse.ArgumentParser:
    """Build arguments supplied by the harmony velocity stage adapter."""

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
    parameters: dict[str, Any],
) -> dict[str, Any]:
    """Recover velocities while preserving all other MIDI events and timings."""

    import mido

    started = time.perf_counter()
    midi = mido.MidiFile(str(raw_midi))
    original_structure = structure_signature(midi)
    notes = collect_notes(midi)
    before = [note.velocity for note in notes]
    warnings: list[str] = []
    if not parameters.get("enabled", True):
        velocities = before
        fallback = True
        fallback_reason = "disabled"
        shutil.copy2(raw_midi, output_midi)
    else:
        from trackscribe.harmony_velocity_audio import AudioVelocityEvidence

        evidence = AudioVelocityEvidence(audio, parameters)
        features = [evidence.measure(note) for note in notes]
        assignment = assign_velocities(
            [note.start for note in notes],
            features,
            parameters,
            audio_silent=evidence.silent,
        )
        velocities = assignment.velocities
        fallback = assignment.fallback
        fallback_reason = assignment.fallback_reason
        if fallback_reason:
            warnings.append(f"Velocity fallback used: {fallback_reason}")
        apply_velocities(midi, notes, velocities)
        if structure_signature(midi) != original_structure:
            raise RuntimeError("Harmony velocity pass changed non-velocity MIDI data")
        output_midi.parent.mkdir(parents=True, exist_ok=True)
        midi.save(str(output_midi))
        reloaded = mido.MidiFile(str(output_midi))
        if structure_signature(reloaded) != original_structure:
            raise RuntimeError("Serialized harmony MIDI changed its event structure")
    report = {
        "algorithm_version": parameters["algorithm_version"],
        "input_notes": len(notes),
        "output_notes": len(velocities),
        "changed_velocities": sum(a != b for a, b in zip(before, velocities)),
        "unchanged_velocities": sum(a == b for a, b in zip(before, velocities)),
        "structure_preserved": True,
        "fallback": fallback,
        "fallback_reason": fallback_reason,
        "warnings": warnings,
        "velocity_before": velocity_statistics(before),
        "velocity_after": velocity_statistics(velocities),
        "parameters": parameters,
        "duration_seconds": round(time.perf_counter() - started, 3),
    }
    _write_json_atomic(diagnostics, report)
    return report


def _write_json_atomic(path: Path, report: dict[str, Any]) -> None:
    """Write diagnostics atomically beside the processed MIDI."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    os.replace(temporary, path)


def main() -> int:
    """Execute the configured velocity pass from the isolated main environment."""

    args = _parser().parse_args()
    report = run(
        args.audio,
        args.raw_midi,
        args.output_midi,
        args.diagnostics,
        json.loads(args.settings_json),
    )
    print(
        json.dumps(
            {
                key: report[key]
                for key in ("input_notes", "changed_velocities", "fallback")
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
