"""Shared services passed to focused pipeline stage adapters."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from trackscribe.config import PipelineConfig
from trackscribe.executor import StageExecutor
from trackscribe.layout import ProjectLayout
from trackscribe.process import run_process


@dataclass(frozen=True)
class StageServices:
    """Configuration, paths, executor, and subprocess bridge for stage functions."""

    config: PipelineConfig
    layout: ProjectLayout
    executor: StageExecutor
    repository_root: Path

    def run_command(
        self,
        stage: str,
        command: list[str],
        *,
        cwd: Path | None = None,
        python_utf8: bool = False,
    ) -> None:
        """Run one isolated command with the current stage's log and callbacks."""

        run_process(
            command,
            stage=stage,
            cwd=cwd or self.repository_root,
            log_path=self.layout.logs / f"{stage}.log",
            emit=lambda status, message, details: self.executor.emit(
                status, message, details
            ),
            python_utf8=python_utf8,
        )

    def worker(self, name: str) -> Path:
        """Resolve a worker script executed by one of the dedicated venv Pythons."""

        return Path(__file__).resolve().parents[1] / "workers" / name

    def entrypoint(self, venv_name: str, module: str) -> list[str]:
        """Call a console entrypoint's main function through relocatable venv Python."""

        return [
            str(self.config.python(venv_name)),
            "-c",
            f"from {module} import main; main()",
        ]
