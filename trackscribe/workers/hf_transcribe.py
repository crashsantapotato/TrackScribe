"""Run hf-midi-transcription with threshold overrides missing from its stock CLI."""

from __future__ import annotations

import argparse
from pathlib import Path

from hf_midi_transcription import MidiTranscriptionModel


def _parser() -> argparse.ArgumentParser:
    """Build worker arguments used by bass and guitar stage adapters."""

    parser = argparse.ArgumentParser()
    parser.add_argument("audio", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--instrument", choices=("bass", "guitar"), required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--onset-threshold", type=float)
    parser.add_argument("--offset-threshold", type=float)
    parser.add_argument("--frame-threshold", type=float)
    return parser


def main() -> None:
    """Load one local checkpoint, apply tested thresholds, and write MIDI."""

    args = _parser().parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    model = MidiTranscriptionModel(
        instrument=args.instrument,
        device=args.device,
        batch_size=args.batch_size,
        checkpoint_path=str(args.checkpoint),
    )
    if args.onset_threshold is not None:
        model.transcriptor.onset_threshold = args.onset_threshold
    if args.offset_threshold is not None:
        # piano_transcription_inference intentionally exposes this historical typo.
        model.transcriptor.offset_threshod = args.offset_threshold
    if args.frame_threshold is not None:
        model.transcriptor.frame_threshold = args.frame_threshold
    model.transcribe(str(args.audio), str(args.output))
    print(f"Saved: {args.output}")


if __name__ == "__main__":
    main()
