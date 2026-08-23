"""Signal-level tests for the background pipeline worker with a mocked runner."""

from __future__ import annotations

import os
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication  # noqa: E402

from trackscribe.harmony_backends import AGNOSTIC_AMT, COMPARE, TRANSKUN  # noqa: E402
from trackscribe.types import PipelineResult, ProgressEvent  # noqa: E402
from trackscribe.ui.helpers import PipelineJob  # noqa: E402
from trackscribe.ui.worker import PipelineFailure, PipelineWorker  # noqa: E402
from trackscribe.ui.reaper_worker import ReaperJob, ReaperWorker  # noqa: E402


class WorkerTest(unittest.TestCase):
    """Verify API parameter forwarding, progress signals, and exception containment."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def _run_worker(self, job: PipelineJob, runner):
        progress: list[ProgressEvent] = []
        completed: list[PipelineResult] = []
        failed: list[PipelineFailure] = []
        finished: list[bool] = []
        worker = PipelineWorker(job, runner=runner)
        worker.progress.connect(progress.append)
        worker.completed.connect(completed.append)
        worker.failed.connect(failed.append)
        worker.finished.connect(lambda: finished.append(True))
        worker.run()
        return progress, completed, failed, finished

    def _assert_backend_forwarded(self, backend: str) -> None:
        captured = {}

        def runner(**kwargs):
            captured.update(kwargs)
            return PipelineResult(Path("project"), Path("project/project.json"), "completed", {})

        job = PipelineJob(Path("input.wav"), Path("project"), harmony_backend=backend)
        _, completed, failed, finished = self._run_worker(job, runner)
        self.assertEqual(captured["harmony_backend"], backend)
        self.assertFalse(captured["force"])
        self.assertEqual(len(completed), 1)
        self.assertEqual(failed, [])
        self.assertEqual(finished, [True])

    def test_agnostic_amt_backend_forwarded(self) -> None:
        self._assert_backend_forwarded(AGNOSTIC_AMT)

    def test_transkun_backend_forwarded(self) -> None:
        self._assert_backend_forwarded(TRANSKUN)

    def test_compare_backend_forwarded(self) -> None:
        self._assert_backend_forwarded(COMPARE)

    def test_cleanup_setting_forwarded(self) -> None:
        captured = {}

        def runner(**kwargs):
            captured.update(kwargs)
            return PipelineResult(Path("project"), Path("manifest"), "completed", {})

        job = PipelineJob(
            Path("input.wav"),
            Path("project"),
            harmony_cleanup_enabled=False,
        )
        self._run_worker(job, runner)
        self.assertFalse(captured["harmony_cleanup_enabled"])

    def test_progress_event_is_bridged_through_signal(self) -> None:
        emitted = ProgressEvent(
            stage="prepare_master",
            status="cached",
            message="reused cached outputs",
            overall_progress=0.125,
        )

        def runner(**kwargs):
            kwargs["progress_callback"](emitted)
            return PipelineResult(Path("project"), Path("manifest"), "completed", {})

        progress, completed, failed, _ = self._run_worker(
            PipelineJob(Path("input.wav"), Path("project")), runner
        )
        self.assertEqual(progress, [emitted])
        self.assertEqual(len(completed), 1)
        self.assertEqual(failed, [])

    def test_pipeline_exception_becomes_error_signal(self) -> None:
        def runner(**kwargs):
            kwargs["progress_callback"](
                ProgressEvent("core_separation", "started", "started", 0.2)
            )
            raise RuntimeError("GPU unavailable")

        progress, completed, failed, finished = self._run_worker(
            PipelineJob(Path("input.wav"), Path("project")), runner
        )
        self.assertEqual(len(progress), 1)
        self.assertEqual(completed, [])
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0].stage, "core_separation")
        self.assertIn("GPU unavailable", failed[0].message)
        self.assertEqual(finished, [True])

    def test_reaper_worker_command_forwards_every_selection(self) -> None:
        worker = ReaperWorker(
            ReaperJob(
                Path("project"),
                Path("reaper.exe"),
                drums=True,
                bass=False,
                harmony=True,
                vocals=False,
            )
        )
        command = worker.command()
        self.assertIn("trackscribe.reaper_bridge", command)
        self.assertIn("--drums", command)
        self.assertIn("--no-bass", command)
        self.assertIn("--harmony", command)
        self.assertIn("--no-vocals", command)


if __name__ == "__main__":
    unittest.main()
