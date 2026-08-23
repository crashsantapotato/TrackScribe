"""Audio-backed conservative cleanup stage for raw Transkun harmony MIDI."""

from __future__ import annotations

import json
from pathlib import Path

from trackscribe.stages.base import StageServices
from trackscribe.types import StageOutcome


STAGE = "harmony_cleanup"


def cleanup(
    services: StageServices,
    *,
    audio: Path,
    raw_midi: Path,
    enabled_override: bool | None = None,
    cache_context: dict | None = None,
) -> StageOutcome:
    """Create cleaned harmony MIDI and a diagnostic report from immutable raw MIDI."""

    parameters = services.config.section(STAGE)
    if enabled_override is not None:
        parameters["enabled"] = enabled_override
    output = services.layout.midi / "harmony.mid"
    diagnostics = services.layout.midi / "harmony_cleanup.json"
    python = services.config.python("main")

    def action() -> StageOutcome:
        command = [
            str(python),
            "-m",
            "trackscribe.workers.harmony_cleanup",
            str(audio),
            str(raw_midi),
            str(output),
            str(diagnostics),
            "--settings-json",
            json.dumps(parameters),
        ]
        services.run_command(STAGE, command, python_utf8=True)
        report = json.loads(diagnostics.read_text(encoding="utf-8"))
        statistics = {
            key: report[key]
            for key in (
                "input_notes",
                "output_notes",
                "removed",
                "removed_total",
                "merged_retriggers",
                "duration_seconds",
            )
        }
        return StageOutcome(
            outputs={
                "midi.harmony": output,
                "diagnostics.harmony_cleanup": diagnostics,
            },
            command=command,
            metadata={"statistics": statistics, "parameters": parameters},
        )

    return services.executor.execute(
        STAGE,
        inputs=[audio, raw_midi],
        model={"name": "conservative harmonic-aware MIDI cleanup", "backend": "librosa-cqt"},
        parameters=parameters,
        cache_context=cache_context,
        action=action,
    )
