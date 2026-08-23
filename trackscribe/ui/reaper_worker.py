"""Qt worker for the isolated TrackScribe-to-REAPER process bridge."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CORE_PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"


@dataclass(frozen=True)
class ReaperJob:
    """Immutable artifact selection for one REAPER bridge invocation."""

    project_dir: Path
    reaper_executable: Path
    drums: bool
    bass: bool
    harmony: bool
    vocals: bool


class ReaperWorker(QObject):
    """Run the core-environment bridge without blocking the Qt event loop."""

    completed = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, job: ReaperJob) -> None:
        super().__init__()
        self.job = job

    def command(self) -> list[str]:
        """Build a shell-free command preserving the selected artifacts."""

        command = [
            str(CORE_PYTHON),
            "-m",
            "trackscribe.reaper_bridge",
            "--project",
            str(self.job.project_dir),
            "--reaper",
            str(self.job.reaper_executable),
        ]
        for key in ("drums", "bass", "harmony", "vocals"):
            command.append(f"--{key}" if getattr(self.job, key) else f"--no-{key}")
        return command

    @Slot()
    def run(self) -> None:
        """Contain subprocess and protocol failures inside Qt signals."""

        try:
            completed = subprocess.run(
                self.command(),
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=False,
                check=False,
            )
            lines = [line for line in completed.stdout.splitlines() if line.strip()]
            payload = json.loads(lines[-1]) if lines else {}
            if completed.returncode or payload.get("type") != "dispatched":
                message = payload.get("message") or completed.stderr.strip()
                raise RuntimeError(message or "REAPER bridge failed without details")
        except Exception as exc:
            self.failed.emit(str(exc) or type(exc).__name__)
        else:
            self.completed.emit(payload)
        finally:
            self.finished.emit()
