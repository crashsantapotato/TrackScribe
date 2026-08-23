"""Four-stem core separation through audio-separator and htdemucs_ft."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from trackscribe.errors import StageError
from trackscribe.stages.base import StageServices
from trackscribe.types import StageOutcome


STAGE = "core_separation"
CORE_STEMS = ("drums", "bass", "vocals", "other")


def _find_output(folder: Path, stem: str) -> Path:
    candidates = [path for path in folder.glob("*.wav") if stem in path.stem.lower()]
    if len(candidates) != 1:
        raise StageError(
            f"Expected one {stem} WAV from audio-separator, found {len(candidates)}"
        )
    return candidates[0]


def run(services: StageServices, master: Path) -> StageOutcome:
    """Separate master.wav and normalize external filenames to stable project paths."""

    model = services.config.model("core")
    parameters = services.config.section("core_separation")
    entrypoint = services.entrypoint("main", "audio_separator.utils.cli")

    def action() -> StageOutcome:
        with tempfile.TemporaryDirectory(
            prefix="core-", dir=services.layout.work
        ) as temporary:
            raw_dir = Path(temporary)
            output_names = {stem.title(): stem for stem in CORE_STEMS}
            command = [
                *entrypoint,
                str(master),
                "--model_filename",
                model["name"],
                "--model_file_dir",
                model["model_dir"],
                "--output_dir",
                str(raw_dir),
                "--output_format",
                parameters["output_format"],
                "--sample_rate",
                str(parameters["sample_rate"]),
                "--demucs_shifts",
                str(parameters["shifts"]),
                "--demucs_overlap",
                str(parameters["overlap"]),
                "--custom_output_names",
                json.dumps(output_names),
            ]
            if parameters.get("use_autocast"):
                command.append("--use_autocast")
            services.run_command(STAGE, command)
            outputs: dict[str, Path] = {}
            for stem in CORE_STEMS:
                source = _find_output(raw_dir, stem)
                target = services.layout.stems / f"{stem}.wav"
                os.replace(source, target)
                outputs[f"stems.{stem}"] = target
            return StageOutcome(outputs=outputs, command=command)

    return services.executor.execute(
        STAGE,
        inputs=[master],
        model=model,
        parameters=parameters,
        action=action,
    )
