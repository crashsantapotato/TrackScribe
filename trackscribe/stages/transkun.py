"""Keys and synth transcription through the isolated Transkun environment."""

from __future__ import annotations

from pathlib import Path

from trackscribe.errors import StageError
from trackscribe.stages.base import StageServices
from trackscribe.types import StageOutcome


def transcribe(
    services: StageServices,
    *,
    stage: str,
    audio: Path,
    output: Path,
    output_key: str,
    parameter_section: str = "transkun",
    cache_context: dict | None = None,
) -> StageOutcome:
    """Run Transkun while preserving velocities predicted by the model."""

    model = services.config.model("transkun")
    parameters = services.config.section(parameter_section)
    if not parameters.get("enabled", True):
        raise StageError(f"Stage '{stage}' is disabled in configuration")
    if parameters.get("backend", "transkun") != "transkun":
        raise StageError(f"Unsupported harmony backend: {parameters['backend']}")
    entrypoint = services.entrypoint("piano", "transkun.transcribe")

    def action() -> StageOutcome:
        command = [
            *entrypoint,
            str(audio),
            str(output),
            "--weight",
            model["weights"],
            "--conf",
            model["config"],
            "--device",
            parameters["device"],
        ]
        if parameters.get("segment_size") is not None:
            command.extend(["--segmentSize", str(parameters["segment_size"])])
        if parameters.get("segment_hop_size") is not None:
            command.extend(["--segmentHopSize", str(parameters["segment_hop_size"])])
        services.run_command(stage, command, python_utf8=True)
        return StageOutcome(outputs={output_key: output}, command=command)

    return services.executor.execute(
        stage,
        inputs=[audio],
        model=model,
        parameters=parameters,
        cache_context=cache_context,
        action=action,
    )
