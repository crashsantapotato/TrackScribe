"""Raw A/B export and neutral diagnostics stage for harmony backends."""

from __future__ import annotations

import json
from pathlib import Path

from trackscribe.stages.base import StageServices
from trackscribe.types import StageOutcome


STAGE = "harmony_compare"


def export(
    services: StageServices,
    *,
    transkun_raw: Path,
    amt_raw: Path,
    amt_velocity: Path,
    processing_seconds: dict[str, float],
) -> StageOutcome:
    """Copy untouched hypotheses plus separate processed AMT MIDI and measure them."""

    ab_dir = services.layout.midi / "ab"
    transkun_ab = ab_dir / "harmony_transkun_raw.mid"
    amt_ab = ab_dir / "harmony_amt_raw.mid"
    amt_velocity_ab = ab_dir / "harmony_amt_velocity.mid"
    diagnostics = ab_dir / "compare.json"
    parameters = {
        "metrics_schema": 2,
        "raw_hypotheses_untouched": True,
        "includes_amt_velocity_copy": True,
    }
    python = services.config.python("main")

    def action() -> StageOutcome:
        ab_dir.mkdir(parents=True, exist_ok=True)
        command = [
            str(python),
            "-m",
            "trackscribe.workers.harmony_compare",
            str(transkun_raw),
            str(amt_raw),
            str(amt_velocity),
            str(transkun_ab),
            str(amt_ab),
            str(amt_velocity_ab),
            str(diagnostics),
            "--transkun-seconds",
            str(processing_seconds["transkun"]),
            "--amt-seconds",
            str(processing_seconds["agnostic-amt"]),
        ]
        services.run_command(STAGE, command, python_utf8=True)
        report = json.loads(diagnostics.read_text(encoding="utf-8"))
        return StageOutcome(
            outputs={
                "midi.ab.transkun_raw": transkun_ab,
                "midi.ab.amt_raw": amt_ab,
                "midi.ab.amt_velocity": amt_velocity_ab,
                "diagnostics.harmony_compare": diagnostics,
            },
            command=command,
            metadata={
                "backends": report["backends"],
                "velocity_pass": report["velocity_pass"],
            },
        )

    return services.executor.execute(
        STAGE,
        inputs=[transkun_raw, amt_raw, amt_velocity],
        model={"name": "raw MIDI A/B diagnostics"},
        parameters=parameters,
        cache_context={"harmony_backend": "compare"},
        action=action,
    )
