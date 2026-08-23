"""Tests for streaming subprocess logs and actionable process failures."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from trackscribe.errors import ProcessError
from trackscribe.process import build_python_utf8_env, run_process


class ProcessRunnerTests(unittest.TestCase):
    """Exercise the environment-neutral subprocess boundary with tiny commands."""

    def test_python_utf8_environment_merges_overrides_and_enforces_policy(self) -> None:
        """Caller overrides should survive without weakening the UTF-8 contract."""

        environment = build_python_utf8_env(
            {"TRACKSCRIBE_RUNTIME_TEST": "kept", "PYTHONUTF8": "0"}
        )
        self.assertEqual(environment["TRACKSCRIBE_RUNTIME_TEST"], "kept")
        self.assertEqual(environment["PYTHONUTF8"], "1")
        self.assertEqual(environment["PYTHONIOENCODING"], "utf-8")

    def test_combined_output_is_streamed_and_logged(self) -> None:
        """Successful output should reach both the callback and stage log."""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            log = root / "stage.log"
            messages: list[str] = []
            run_process(
                [sys.executable, "-c", "print('worker-ok')"],
                stage="test",
                cwd=root,
                log_path=log,
                emit=lambda _status, message, _details: messages.append(message),
            )
            self.assertIn("worker-ok", messages)
            self.assertIn("worker-ok", log.read_text(encoding="utf-8"))

    def test_nonzero_exit_raises_process_error_with_log_path(self) -> None:
        """A worker failure should expose the code and persistent log location."""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            log = root / "stage.log"
            with self.assertRaises(ProcessError) as raised:
                run_process(
                    [sys.executable, "-c", "raise SystemExit(3)"],
                    stage="test",
                    cwd=root,
                    log_path=log,
                    emit=lambda _status, _message, _details: None,
                )
            self.assertEqual(raised.exception.returncode, 3)
            self.assertEqual(raised.exception.log_path, str(log))

    def test_python_utf8_overrides_hostile_child_encoding_without_parent_mutation(
        self,
    ) -> None:
        """Python workers should emit full Unicode even under a CP1251 parent."""

        expected = "TrackScribe \u2713 \U0001f4e6 Unicode runtime test"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            log = root / "stage.log"
            messages: list[str] = []
            with mock.patch.dict(
                os.environ,
                {"PYTHONUTF8": "0", "PYTHONIOENCODING": "cp1251"},
            ):
                run_process(
                    [sys.executable, "-c", f"print({expected!r})"],
                    stage="test",
                    cwd=root,
                    log_path=log,
                    emit=lambda _status, message, _details: messages.append(message),
                    python_utf8=True,
                )
                self.assertEqual(os.environ["PYTHONUTF8"], "0")
                self.assertEqual(os.environ["PYTHONIOENCODING"], "cp1251")
            self.assertIn(expected, messages)
            self.assertIn(expected, log.read_text(encoding="utf-8"))

    def test_python_utf8_preserves_unicode_output_and_nonzero_failure(self) -> None:
        """Unicode output must be logged before the worker's exit code is raised."""

        expected = "TrackScribe \u2713 \U0001f4e6 Unicode runtime test"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            log = root / "stage.log"
            messages: list[str] = []
            with mock.patch.dict(
                os.environ,
                {"PYTHONUTF8": "0", "PYTHONIOENCODING": "cp1251"},
            ):
                with self.assertRaises(ProcessError) as raised:
                    run_process(
                        [
                            sys.executable,
                            "-c",
                            f"print({expected!r}); raise SystemExit(7)",
                        ],
                        stage="test",
                        cwd=root,
                        log_path=log,
                        emit=lambda _status, message, _details: messages.append(
                            message
                        ),
                        python_utf8=True,
                    )
                self.assertEqual(os.environ["PYTHONUTF8"], "0")
                self.assertEqual(os.environ["PYTHONIOENCODING"], "cp1251")
            self.assertEqual(raised.exception.returncode, 7)
            self.assertEqual(raised.exception.log_path, str(log))
            self.assertIn(expected, messages)
            self.assertIn(expected, log.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
