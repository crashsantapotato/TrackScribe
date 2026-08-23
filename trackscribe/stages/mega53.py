"""Mega53 separation and activity classification for the core 'other' stem."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path

from trackscribe.errors import StageError
from trackscribe.stages.base import StageServices
from trackscribe.types import StageOutcome


SEPARATION_STAGE = "mega53_separation"
ANALYSIS_STAGE = "mega53_analysis"


def separate(
    services: StageServices, other_wav: Path, cache_context: dict | None = None
) -> StageOutcome:
    """Run MVSep Mega 53 in its venv and normalize every stem filename."""

    model = services.config.model("mega53")
    parameters = services.config.section("mega53_separation")
    entrypoint = services.entrypoint("mega", "bs_roformer.inference")

    def action() -> StageOutcome:
        services.layout.mega53.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix="mega53-", dir=services.layout.work
        ) as temporary:
            temporary_root = Path(temporary)
            input_dir = temporary_root / "input"
            raw_dir = temporary_root / "output"
            input_dir.mkdir()
            raw_dir.mkdir()
            staged_input = input_dir / "other.wav"
            shutil.copy2(other_wav, staged_input)
            command = [
                *entrypoint,
                "--model_type",
                parameters["model_type"],
                "--config_path",
                model["config"],
                "--model_path",
                model["checkpoint"],
                "--input_folder",
                str(input_dir),
                "--store_dir",
                str(raw_dir),
                "--device",
                parameters["device"],
                "--backend",
                parameters["backend"],
                "--output_format",
                parameters["output_format"],
            ]
            services.run_command(SEPARATION_STAGE, command, python_utf8=True)
            raw_outputs = sorted(raw_dir.glob("other_*.wav"))
            expected = int(parameters["expected_stems"])
            if len(raw_outputs) != expected:
                raise StageError(
                    f"Mega53 produced {len(raw_outputs)} WAVs, expected {expected}"
                )
            outputs: dict[str, Path] = {}
            for source in raw_outputs:
                instrument = source.stem.removeprefix("other_")
                if not instrument or any(char in instrument for char in "\\/:"):
                    raise StageError(f"Unsafe Mega53 output id: {instrument!r}")
                target = services.layout.mega53 / f"{instrument}.wav"
                os.replace(source, target)
                outputs[f"stems.mega53.{instrument}"] = target
            return StageOutcome(outputs=outputs, command=command)

    return services.executor.execute(
        SEPARATION_STAGE,
        inputs=[other_wav],
        model=model,
        parameters=parameters,
        cache_context=cache_context,
        action=action,
    )


def analyze(
    services: StageServices, stems: list[Path], cache_context: dict | None = None
) -> StageOutcome:
    """Measure activity and classify all Mega53 WAVs as KEEP, REVIEW, or IGNORE."""

    parameters = services.config.section("mega53_analysis")
    output_json = services.layout.mega53 / "analysis.json"
    output_csv = services.layout.mega53 / "analysis.csv"
    python = services.config.python("main")

    def action() -> StageOutcome:
        command = [
            str(python),
            str(services.worker("activity_analysis.py")),
            str(services.layout.mega53),
            "--json",
            str(output_json),
            "--csv",
            str(output_csv),
            "--settings-json",
            json.dumps(parameters),
        ]
        services.run_command(ANALYSIS_STAGE, command, python_utf8=True)
        report = json.loads(output_json.read_text(encoding="utf-8"))
        return StageOutcome(
            outputs={
                "analysis.mega53_json": output_json,
                "analysis.mega53_csv": output_csv,
            },
            command=command,
            metadata={"summary": report["summary"], "stems": report["stems"]},
        )

    return services.executor.execute(
        ANALYSIS_STAGE,
        inputs=stems,
        model={"name": "audio activity classifier"},
        parameters=parameters,
        cache_context=cache_context,
        action=action,
    )


def statuses(outcome: StageOutcome) -> dict[str, str]:
    """Extract a stem-to-status mapping from a fresh or cached analysis outcome."""

    return {
        row["name"]: row["status"]
        for row in outcome.metadata.get("stems", [])
        if "name" in row and "status" in row
    }
