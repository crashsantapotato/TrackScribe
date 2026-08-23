"""Bass and guitar transcription through hf-midi-transcription workers."""

from __future__ import annotations

from pathlib import Path

from trackscribe.stages.base import StageServices
from trackscribe.types import StageOutcome


def transcribe(
    services: StageServices,
    *,
    stage: str,
    audio: Path,
    instrument: str,
    output: Path,
    output_key: str,
    parameter_section: str,
    cache_context: dict | None = None,
) -> StageOutcome:
    """Run the HF model with optional threshold overrides in its dedicated venv."""

    model = services.config.model("hf")
    parameters = services.config.section(parameter_section)
    checkpoint = model[f"{instrument}_checkpoint"]
    python = services.config.python("bass")

    def action() -> StageOutcome:
        command = [
            str(python),
            str(services.worker("hf_transcribe.py")),
            str(audio),
            str(output),
            "--instrument",
            instrument,
            "--checkpoint",
            checkpoint,
            "--device",
            parameters["device"],
            "--batch-size",
            str(parameters["batch_size"]),
        ]
        for key in ("onset_threshold", "offset_threshold", "frame_threshold"):
            if key in parameters:
                command.extend([f"--{key.replace('_', '-')}", str(parameters[key])])
        services.run_command(stage, command, python_utf8=True)
        return StageOutcome(outputs={output_key: output}, command=command)

    stage_model = {
        "name": model["name"],
        "instrument": instrument,
        "checkpoint": checkpoint,
    }
    return services.executor.execute(
        stage,
        inputs=[audio],
        model=stage_model,
        parameters=parameters,
        cache_context=cache_context,
        action=action,
    )


def add_guitar_velocity(
    services: StageServices,
    *,
    stage: str,
    audio: Path,
    raw_midi: Path,
    output: Path,
    output_key: str,
    cache_context: dict | None = None,
) -> StageOutcome:
    """Apply the tested chord-aware, audio-derived guitar velocity pass."""

    parameters = services.config.section("guitar_velocity")
    python = services.config.python("main")

    def action() -> StageOutcome:
        command = [
            str(python),
            str(services.worker("guitar_velocity.py")),
            "--audio",
            str(audio),
            "--midi",
            str(raw_midi),
            "--out",
            str(output),
            "--min-velocity",
            str(parameters["min_velocity"]),
            "--max-velocity",
            str(parameters["max_velocity"]),
            "--gamma",
            str(parameters["gamma"]),
            "--chord-window-ms",
            str(parameters["chord_window_ms"]),
        ]
        services.run_command(stage, command, python_utf8=True)
        return StageOutcome(outputs={output_key: output}, command=command)

    return services.executor.execute(
        stage,
        inputs=[audio, raw_midi],
        model={"name": "audio-derived guitar velocity"},
        parameters=parameters,
        cache_context=cache_context,
        action=action,
    )
