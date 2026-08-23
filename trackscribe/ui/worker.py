"""QThread-compatible bridge from TrackScribe callbacks to Qt signals."""

from __future__ import annotations

import traceback
from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import QObject, Signal, Slot

from trackscribe import run_pipeline
from trackscribe.types import PipelineResult, ProgressEvent
from trackscribe.ui.helpers import PipelineJob, build_pipeline_kwargs


PipelineRunner = Callable[..., PipelineResult]


@dataclass(frozen=True)
class PipelineFailure:
    """Serializable error state emitted instead of raising into the Qt event loop."""

    stage: str
    message: str
    traceback_text: str
    project_dir: str


class PipelineWorker(QObject):
    """Run one immutable job outside the GUI thread and emit structured signals."""

    progress = Signal(object)
    completed = Signal(object)
    failed = Signal(object)
    finished = Signal()

    def __init__(
        self, job: PipelineJob, runner: PipelineRunner | None = None
    ) -> None:
        """Store the job and optional mocked runner used by UI tests."""

        super().__init__()
        self.job = job
        self._runner = runner or run_pipeline
        self._last_stage = "pipeline"

    def _progress_callback(self, event: ProgressEvent) -> None:
        """Bridge a backend callback from the worker thread to a Qt signal."""

        self._last_stage = event.stage
        self.progress.emit(event)

    @Slot()
    def run(self) -> None:
        """Execute the public API once, containing every exception."""

        try:
            result = self._runner(
                **build_pipeline_kwargs(self.job, self._progress_callback)
            )
        except Exception as exc:
            self.failed.emit(
                PipelineFailure(
                    stage=self._last_stage,
                    message=str(exc) or type(exc).__name__,
                    traceback_text=traceback.format_exc(),
                    project_dir=str(self.job.output_dir),
                )
            )
        else:
            self.completed.emit(result)
        finally:
            self.finished.emit()
