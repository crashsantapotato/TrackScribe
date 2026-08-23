"""External instrument-agnostic AMT transcription stage adapter."""

from __future__ import annotations

from pathlib import Path

from trackscribe.errors import StageError
from trackscribe.provenance import file_signature
from trackscribe.stages.base import StageServices
from trackscribe.types import StageOutcome


STAGE = "harmony_amt_transcription"


def transcribe(services: StageServices, audio: Path) -> StageOutcome:
    """Run upstream AMT with its isolated CUDA environment and default thresholds."""

    parameters = services.config.section(STAGE)
    if not parameters.get("enabled", True):
        raise StageError("Instrument-agnostic AMT backend is disabled in configuration")
    repo_dir = services.config.resolve_path(parameters["repo_dir"])
    infer_script = repo_dir / "infer.py"
    output = services.layout.midi / "harmony_amt_raw.mid"
    checkpoint = _checkpoint_path(repo_dir, parameters)
    normalized = dict(parameters)
    normalized["repo_dir"] = str(repo_dir)
    model = {
        "name": "anime-song/instrument-agnostic-amt",
        "repository": str(repo_dir),
        "revision": parameters.get("repo_revision"),
        "model_type": parameters["model_type"],
        "checkpoint": str(checkpoint),
        "checkpoint_source": "configured" if parameters.get("checkpoint") else "upstream-auto",
    }

    def action() -> StageOutcome:
        if not infer_script.is_file():
            raise StageError(f"Instrument-agnostic AMT infer.py not found: {infer_script}")
        python = services.config.python("amt")
        command = [
            str(python),
            str(infer_script),
            "--audio",
            str(audio),
            "--output-midi",
            str(output),
            "--type",
            parameters["model_type"],
            "--device",
            parameters["device"],
            "--window-batch-size",
            str(parameters["window_batch_size"]),
            "--max-midi-melodic-instruments",
            str(parameters["max_midi_melodic_instruments"]),
        ]
        if parameters.get("amp"):
            command.append("--amp")
        if parameters.get("checkpoint"):
            command.extend(["--checkpoint", str(checkpoint)])
        services.run_command(STAGE, command, cwd=repo_dir)
        metadata = {"checkpoint": str(checkpoint)}
        if checkpoint.is_file():
            metadata["checkpoint_signature"] = file_signature(checkpoint)
        return StageOutcome(
            outputs={"midi.harmony_amt_raw": output},
            command=command,
            metadata=metadata,
        )

    return services.executor.execute(
        STAGE,
        inputs=[audio],
        model=model,
        parameters=normalized,
        cache_context={"output_contract": "harmony-amt-raw-v1"},
        action=action,
    )


def _checkpoint_path(repo_dir: Path, parameters: dict) -> Path:
    """Resolve an explicit checkpoint or upstream's deterministic auto-download path."""

    configured = parameters.get("checkpoint")
    if configured:
        path = Path(configured)
        return path if path.is_absolute() else (repo_dir / path).resolve()
    filename = parameters.get(
        "checkpoint_filename", f"best_model_{parameters['model_type']}.pth"
    )
    return repo_dir / "checkpoints" / filename
