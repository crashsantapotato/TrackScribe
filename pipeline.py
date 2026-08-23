"""Command-line entry point for the TrackScribe audio-to-MIDI pipeline."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from trackscribe import DEFAULT_CONFIG_PATH, ProgressEvent, run_pipeline
from trackscribe.errors import PipelineError
from trackscribe.harmony_backends import HARMONY_BACKENDS, TRANSKUN
from trackscribe.modes import PIPELINE_MODES, PRESERVE_HARMONY, STAGE_ORDER


def _build_parser() -> argparse.ArgumentParser:
    """Build the public CLI parser."""

    parser = argparse.ArgumentParser(
        description="TrackScribe: prepare input audio and transcribe useful stems to MIDI."
    )
    parser.add_argument("input", type=Path, help="Input audio file")
    parser.add_argument("--output", type=Path, required=True, help="Project output folder")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument(
        "--mode",
        choices=PIPELINE_MODES,
        default=PRESERVE_HARMONY,
        help="Harmony-preserving default or experimental detailed stem transcription",
    )
    parser.add_argument(
        "--harmony-backend",
        choices=HARMONY_BACKENDS,
        default=TRANSKUN,
        help="Harmony transcription backend; compare exports untouched raw A/B MIDI",
    )
    parser.add_argument("--force", action="store_true", help="Re-run every stage")
    parser.add_argument(
        "--force-stage",
        action="append",
        choices=STAGE_ORDER,
        default=[],
        help="Re-run one stage; may be repeated",
    )
    parser.add_argument(
        "--stop-after",
        choices=STAGE_ORDER,
        help="Stop cleanly after this stage (useful for staged validation)",
    )
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument(
        "--no-harmony-cleanup",
        action="store_true",
        help="Keep harmony_raw.mid unchanged as harmony.mid while writing diagnostics",
    )
    return parser


def _console_progress(event: ProgressEvent) -> None:
    """Render concise stage-level progress for terminal users."""

    if event.status in {"started", "completed", "cached", "skipped", "failed"}:
        percent = round(event.overall_progress * 100)
        print(f"[{percent:3d}%] {event.stage}: {event.message}", flush=True)


def main() -> int:
    """Run the pipeline CLI and return a process exit code."""

    args = _build_parser().parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    try:
        result = run_pipeline(
            input_path=args.input,
            output_dir=args.output,
            config_path=args.config,
            mode=args.mode,
            progress_callback=_console_progress,
            force=args.force,
            force_stages=set(args.force_stage),
            stop_after=args.stop_after,
            harmony_cleanup_enabled=False if args.no_harmony_cleanup else None,
            harmony_backend=args.harmony_backend,
        )
    except PipelineError as exc:
        logging.error("%s", exc)
        return 1
    print(f"Project manifest: {result.manifest_path}")
    return 0 if result.status in {"completed", "partial"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
