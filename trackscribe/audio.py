"""Shared input-audio contract and existing FFmpeg discovery."""

from __future__ import annotations

import shutil
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCAL_FFMPEG = PROJECT_ROOT / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe"

SUPPORTED_AUDIO_EXTENSIONS = (
    ".wav",
    ".mp3",
    ".flac",
    ".ogg",
    ".m4a",
    ".aac",
)
AUDIO_FILE_GLOBS = " ".join(f"*{suffix}" for suffix in SUPPORTED_AUDIO_EXTENSIONS)
AUDIO_FILE_DIALOG_FILTER = f"Audio files ({AUDIO_FILE_GLOBS});;All files (*)"


def is_supported_audio(path: str | Path) -> bool:
    """Return whether a path has one of the public input extensions."""

    return Path(path).suffix.lower() in SUPPORTED_AUDIO_EXTENSIONS


def supported_audio_description() -> str:
    """Return the supported suffixes in a concise user-facing form."""

    return ", ".join(SUPPORTED_AUDIO_EXTENSIONS)


def find_ffmpeg() -> Path | None:
    """Prefer TrackScribe's portable FFmpeg, then use an executable from PATH."""

    if LOCAL_FFMPEG.is_file():
        return LOCAL_FFMPEG.resolve()
    executable = shutil.which("ffmpeg")
    return Path(executable).resolve() if executable else None
