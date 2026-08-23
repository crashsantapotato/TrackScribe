"""Tests for streaming subprocess logs and actionable process failures."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from trackscribe.errors import ProcessError
from trackscribe.process import run_process


class ProcessRunnerTests(unittest.TestCase):
    """Exercise the environment-neutral subprocess boundary with tiny commands."""

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


if __name__ == "__main__":
    unittest.main()
