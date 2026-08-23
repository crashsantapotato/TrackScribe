"""JSONL process boundary for callers outside TrackScribe's environment."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable, TextIO

from trackscribe import DEFAULT_CONFIG_PATH, ProgressEvent, run_pipeline
from trackscribe.harmony_backends import AGNOSTIC_AMT, HARMONY_BACKENDS
from trackscribe.modes import PIPELINE_MODES, PRESERVE_HARMONY, stages_for_run
from trackscribe.types import PipelineResult


PipelineRunner = Callable[..., PipelineResult]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TrackScribe machine integration bridge")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--mode", choices=PIPELINE_MODES, default=PRESERVE_HARMONY)
    parser.add_argument(
        "--harmony-backend", choices=HARMONY_BACKENDS, default=AGNOSTIC_AMT
    )
    return parser


def _write(stream: TextIO, payload: dict[str, object]) -> None:
    """Write one protocol object atomically enough for a line reader."""

    stream.write(json.dumps(payload, ensure_ascii=False) + "\n")
    stream.flush()


def run_bridge(
    args: argparse.Namespace,
    *,
    runner: PipelineRunner = run_pipeline,
    stream: TextIO = sys.stdout,
) -> int:
    """Run the public API and serialize callbacks without parsing human logs."""

    order = stages_for_run(args.mode, args.harmony_backend)
    last_stage = "pipeline"

    def progress(event: ProgressEvent) -> None:
        nonlocal last_stage
        last_stage = event.stage
        try:
            current = order.index(event.stage) + 1
        except ValueError:
            current = 0
        _write(
            stream,
            {
                "type": "stage",
                "stage": event.stage,
                "status": event.status,
                "message": event.message,
                "current": current,
                "total": len(order),
                "progress": event.overall_progress,
                "details": event.details,
            },
        )

    try:
        result = runner(
            input_path=args.input,
            output_dir=args.output,
            config_path=args.config,
            mode=args.mode,
            harmony_backend=args.harmony_backend,
            progress_callback=progress,
        )
    except Exception as exc:
        _write(
            stream,
            {
                "type": "error",
                "stage": last_stage,
                "message": str(exc) or type(exc).__name__,
                "project": str(args.output.resolve()),
            },
        )
        return 1
    _write(
        stream,
        {
            "type": "completed",
            "status": result.status,
            "project": str(result.project_dir),
            "manifest": str(result.manifest_path),
            "outputs": {key: str(path) for key, path in result.outputs.items()},
        },
    )
    return 0 if result.status in {"completed", "partial"} else 1


def main(argv: list[str] | None = None) -> int:
    """Parse bridge arguments and return a process exit code."""

    return run_bridge(_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
