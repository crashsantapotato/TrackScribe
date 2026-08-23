"""Tests for double-click runtime bootstrapping without opening a real window."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ui


class LauncherTest(unittest.TestCase):
    """Ensure system Python delegates to the isolated pythonw executable."""

    def test_missing_qt_relaunches_with_ui_pythonw(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pythonw = root / ".venv-ui" / "Scripts" / "pythonw.exe"
            pythonw.parent.mkdir(parents=True)
            pythonw.touch()
            with (
                patch.object(ui, "PROJECT_ROOT", root),
                patch.object(ui, "UI_PYTHON", pythonw),
                patch.object(ui.importlib.util, "find_spec", return_value=None),
                patch.object(ui.subprocess, "Popen") as popen,
                patch.object(ui.sys, "argv", ["ui.py"]),
            ):
                self.assertEqual(ui.main(), 0)
            popen.assert_called_once_with(
                [str(pythonw), str(Path(ui.__file__).resolve())],
                cwd=str(root),
                close_fds=True,
            )

    def test_missing_environment_shows_actionable_message(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            missing = root / ".venv-ui" / "Scripts" / "pythonw.exe"
            with (
                patch.object(ui, "PROJECT_ROOT", root),
                patch.object(ui, "UI_PYTHON", missing),
                patch.object(ui.importlib.util, "find_spec", return_value=None),
                patch.object(ui, "_show_windows_message") as show_message,
            ):
                self.assertEqual(ui.main(), 1)
            show_message.assert_called_once()
            self.assertIn("environment is missing", show_message.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
