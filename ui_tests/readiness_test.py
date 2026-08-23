"""Tests for lightweight UI installation readiness reporting."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from trackscribe.ui.readiness import REQUIRED_ENVIRONMENTS, check_readiness


class ReadinessTest(unittest.TestCase):
    """Readiness checks inspect files without importing any ML backend."""

    @staticmethod
    def _create_environment(root: Path, name: str) -> None:
        python = root / name / "Scripts" / "python.exe"
        python.parent.mkdir(parents=True, exist_ok=True)
        python.touch()

    def test_complete_file_layout_is_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "config" / "trackscribe.json"
            config.parent.mkdir(parents=True)
            config.write_text("{}", encoding="utf-8")
            for environment in REQUIRED_ENVIRONMENTS:
                self._create_environment(root, environment)
            infer = root / "tools" / "instrument-agnostic-amt" / "infer.py"
            infer.parent.mkdir(parents=True)
            infer.touch()
            ffmpeg = root / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe"
            ffmpeg.parent.mkdir(parents=True)
            ffmpeg.touch()
            report = check_readiness(root, ffmpeg_finder=lambda: ffmpeg)
            self.assertTrue(report.ready, report.user_message())
            self.assertEqual(report.missing, ())

    def test_missing_environment_and_ffmpeg_are_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "config" / "trackscribe.json"
            config.parent.mkdir(parents=True)
            config.write_text("{}", encoding="utf-8")
            for environment in REQUIRED_ENVIRONMENTS:
                if environment != ".venv-amt":
                    self._create_environment(root, environment)
            infer = root / "tools" / "instrument-agnostic-amt" / "infer.py"
            infer.parent.mkdir(parents=True)
            infer.touch()
            report = check_readiness(root, ffmpeg_finder=lambda: None)
            self.assertFalse(report.ready)
            self.assertEqual(report.missing, (".venv-amt", "FFmpeg"))
            self.assertIn("Please run setup.bat", report.user_message())


if __name__ == "__main__":
    unittest.main()
