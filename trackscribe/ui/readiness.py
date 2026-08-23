"""Lightweight installation readiness checks for desktop startup."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from trackscribe.audio import find_ffmpeg


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REQUIRED_ENVIRONMENTS = (
    ".venv",
    ".venv-ui",
    ".venv-bass",
    ".venv-piano",
    ".venv-mega",
    ".venv-amt",
)


@dataclass(frozen=True)
class ReadinessReport:
    """One cheap readiness snapshot suitable for a native error dialog."""

    missing: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return not self.missing

    def user_message(self) -> str:
        lines = ["TrackScribe setup is incomplete.", ""]
        if self.missing:
            lines.append("Missing:")
            lines.extend(f"- {item}" for item in self.missing)
            lines.append("")
        lines.append("Please run setup.bat.")
        return "\n".join(lines)


def _venv_python(root: Path, name: str) -> Path:
    scripts = root / name / ("Scripts" if (root / name / "Scripts").is_dir() else "bin")
    executable = "python.exe" if scripts.name == "Scripts" else "python"
    return scripts / executable


def check_readiness(
    root: Path = PROJECT_ROOT,
    *,
    ffmpeg_finder: Callable[[], Path | None] = find_ffmpeg,
) -> ReadinessReport:
    """Check files only; never import ML packages or mutate installation state."""

    resolved_root = root.expanduser().resolve()
    missing: list[str] = []
    config = resolved_root / "config" / "trackscribe.json"
    if not config.is_file():
        missing.append("config/trackscribe.json")
    for environment in REQUIRED_ENVIRONMENTS:
        if not _venv_python(resolved_root, environment).is_file():
            missing.append(environment)
    if not (resolved_root / "tools" / "instrument-agnostic-amt" / "infer.py").is_file():
        missing.append("tools/instrument-agnostic-amt")
    try:
        ffmpeg = ffmpeg_finder()
    except OSError:
        ffmpeg = None
    if ffmpeg is None or not ffmpeg.is_file():
        missing.append("FFmpeg")
    return ReadinessReport(tuple(missing))
