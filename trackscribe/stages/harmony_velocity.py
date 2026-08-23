"""Audio-derived velocity stage for immutable instrument-agnostic AMT output."""

from __future__ import annotations

import json
from pathlib import Path

from trackscribe.stages.base import StageServices
from trackscribe.types import StageOutcome


STAGE = "harmony_amt_velocity"


def add_velocity(
    services: StageServices, *, audio: Path, raw_midi: Path
) -> StageOutcome:
    """Create expressive AMT MIDI and diagnostics without changing the raw source."""

    parameters = services.config.section(STAGE)
    output = services.layout.midi / "harmony_amt_velocity.mid"
    diagnostics = services.layout.midi / "harmony_amt_velocity.json"
    python = services.config.python("main")

    def action() -> StageOutcome:
        command = [
            str(python),
            "-m",
            "trackscribe.workers.harmony_amt_velocity",
            str(audio),
            str(raw_midi),
            str(output),
            str(diagnostics),
            "--settings-json",
            json.dumps(parameters),
        ]
        services.run_command(STAGE, command)
        report = json.loads(diagnostics.read_text(encoding="utf-8"))
        metadata = {
            key: report[key]
            for key in (
                "algorithm_version",
                "input_notes",
                "output_notes",
                "changed_velocities",
                "unchanged_velocities",
                "structure_preserved",
                "fallback",
                "fallback_reason",
                "warnings",
                "velocity_before",
                "velocity_after",
            )
        }
        return StageOutcome(
            outputs={
                "midi.harmony_amt_velocity": output,
                "diagnostics.harmony_amt_velocity": diagnostics,
            },
            command=command,
            metadata=metadata,
        )

    return services.executor.execute(
        STAGE,
        inputs=[audio, raw_midi],
        model={
            "name": "audio-derived AMT harmony velocity",
            "backend": "pitch-aware-cqt-onset",
        },
        parameters=parameters,
        cache_context={"algorithm_version": parameters["algorithm_version"]},
        action=action,
    )
