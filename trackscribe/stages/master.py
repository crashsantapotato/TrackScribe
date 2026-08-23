"""Prepare the canonical project-local WAV from a supported audio input."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from trackscribe.audio import find_ffmpeg
from trackscribe.errors import ProcessError, StageError
from trackscribe.provenance import file_signature
from trackscribe.stages.base import StageServices
from trackscribe.types import StageOutcome


STAGE = "prepare_master"
CANONICAL_CONTRACT = {
    "container": "wav",
    "sample_rate": "preserve-source",
    "channel_layout": "preserve-source",
    "wav_fast_path": "byte-copy",
    "decoded_sample_format": "ffmpeg-wav-default",
}


def run(services: StageServices, input_path: Path) -> StageOutcome:
    """Copy WAV losslessly or decode another supported input through FFmpeg."""

    source = input_path.resolve()
    extension = source.suffix.lower()
    copy_path = extension == ".wav"
    source_signature = file_signature(source, include_sha256=True)
    ffmpeg = None if copy_path else find_ffmpeg()
    parameters = {
        "contract_version": 2,
        "strategy": "byte-copy" if copy_path else "ffmpeg-decode",
        "canonical_contract": CANONICAL_CONTRACT,
        "ffmpeg_executable": str(ffmpeg) if ffmpeg else None,
    }
    metadata = {
        "original_input_path": str(source),
        "original_extension": extension,
        "input_signature": source_signature,
        "decoder_used": "file-copy" if copy_path else "ffmpeg",
        "ffmpeg_executable": str(ffmpeg) if ffmpeg else None,
        "conversion_performed": not copy_path,
        "resulting_master": str(services.layout.master),
        "canonical_contract": CANONICAL_CONTRACT,
    }


    def action() -> StageOutcome:
        if copy_path:
            with tempfile.TemporaryDirectory(
                prefix="prepare-master-", dir=services.layout.work
            ) as temporary:
                staged_master = Path(temporary) / "master.wav"
                shutil.copyfile(source, staged_master)
                os.replace(staged_master, services.layout.master)
            return StageOutcome(
                outputs={"master": services.layout.master}, metadata=metadata
            )

        if ffmpeg is None:
            raise StageError(
                f"FFmpeg is required to decode {extension or 'this audio format'}, "
                "but no ffmpeg executable was found in PATH."
            )
        with tempfile.TemporaryDirectory(
            prefix="prepare-master-", dir=services.layout.work
        ) as temporary:
            staged_master = Path(temporary) / "master.wav"
            command = [
                str(ffmpeg),
                "-hide_banner",
                "-nostdin",
                "-y",
                "-i",
                str(source),
                "-map",
                "0:a:0",
                "-vn",
                str(staged_master),
            ]
            services.executor.manifest.record_stage_runtime(STAGE, command, metadata)
            try:
                services.run_command(STAGE, command)
            except ProcessError as exc:
                raise StageError(
                    f"FFmpeg could not decode input audio '{source.name}'. {exc}"
                ) from exc
            if not staged_master.is_file():
                raise StageError(
                    f"FFmpeg completed without creating canonical master.wav: {source}"
                )
            os.replace(staged_master, services.layout.master)
        return StageOutcome(
            outputs={"master": services.layout.master},
            command=command,
            metadata=metadata,
        )

    return services.executor.execute(
        STAGE,
        inputs=[source],
        model={},
        parameters=parameters,
        cache_context={"source_content_signature": source_signature},
        action=action,
    )
