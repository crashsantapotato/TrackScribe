"""ADTOF drum transcription followed by audio-derived velocity processing."""

from __future__ import annotations

from pathlib import Path

from trackscribe.stages.base import StageServices
from trackscribe.types import StageOutcome


TRANSCRIBE_STAGE = "drums_transcription"
VELOCITY_STAGE = "drums_velocity"


def transcribe(services: StageServices, drums_wav: Path) -> StageOutcome:
    """Run ADTOF in the main audio-tools environment."""

    model = services.config.model("adtof")
    parameters = services.config.section("drums_transcription")
    raw_midi = services.layout.work / "drums.raw.mid"
    entrypoint = services.entrypoint("main", "adtof_pytorch.cli")

    def action() -> StageOutcome:
        command = [
            *entrypoint,
            "--audio",
            str(drums_wav),
            "--out",
            str(raw_midi),
            "--device",
            parameters["device"],
            "--weights",
            model["weights"],
        ]
        if parameters.get("thresholds"):
            command.extend(["--thresholds", parameters["thresholds"]])
        services.run_command(TRANSCRIBE_STAGE, command, python_utf8=True)
        return StageOutcome(outputs={"intermediate.drums_midi": raw_midi}, command=command)

    return services.executor.execute(
        TRANSCRIBE_STAGE,
        inputs=[drums_wav],
        model=model,
        parameters=parameters,
        action=action,
    )


def add_velocity(
    services: StageServices, drums_wav: Path, raw_midi: Path
) -> StageOutcome:
    """Replace ADTOF velocities with values derived from drum stem transients."""

    parameters = services.config.section("drums_velocity")
    output = services.layout.midi / "drums.mid"
    python = services.config.python("main")

    def action() -> StageOutcome:
        command = [
            str(python),
            str(services.worker("drum_velocity.py")),
            "--audio",
            str(drums_wav),
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
        ]
        services.run_command(VELOCITY_STAGE, command, python_utf8=True)
        return StageOutcome(outputs={"midi.drums": output}, command=command)

    return services.executor.execute(
        VELOCITY_STAGE,
        inputs=[drums_wav, raw_midi],
        model={"name": "audio-derived drum velocity"},
        parameters=parameters,
        action=action,
    )
