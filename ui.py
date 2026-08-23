"""Launch the TrackScribe Qt desktop interface."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import traceback
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
UI_PYTHON = PROJECT_ROOT / ".venv-ui" / "Scripts" / "pythonw.exe"
ERROR_LOG = PROJECT_ROOT / "ui-launch-error.log"


def _show_windows_message(title: str, message: str) -> None:
    """Show startup feedback even when Qt and a persistent console are unavailable."""

    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, message, title, 0x10)
    except Exception:
        print(f"{title}: {message}", file=sys.stderr)


def _bootstrap_ui_runtime() -> bool:
    """Relaunch with the isolated GUI interpreter when current Python lacks Qt."""

    if importlib.util.find_spec("PySide6") is not None:
        return False
    if not UI_PYTHON.is_file():
        _show_windows_message(
            "TrackScribe UI environment is missing",
            "PySide6 is not available and .venv-ui was not found.\n\n"
            "Create it from the TrackScribe folder:\n"
            ".venv\\Scripts\\python.exe -m venv .venv-ui\n"
            ".venv-ui\\Scripts\\python.exe -m pip install -r requirements-ui.txt",
        )
        return False
    subprocess.Popen(
        [str(UI_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]],
        cwd=str(PROJECT_ROOT),
        close_fds=True,
    )
    return True


def _report_startup_error() -> None:
    """Persist a traceback and show a native message instead of silently closing."""

    details = traceback.format_exc()
    try:
        ERROR_LOG.write_text(details, encoding="utf-8")
        log_message = f"\n\nDetails were written to:\n{ERROR_LOG}"
    except OSError:
        log_message = ""
    _show_windows_message(
        "TrackScribe could not start",
        f"The desktop UI failed during startup.{log_message}",
    )


def main() -> int:
    """Start the desktop application and return its exit code."""

    if _bootstrap_ui_runtime():
        return 0
    if importlib.util.find_spec("PySide6") is None:
        return 1
    from trackscribe.ui import launch_ui

    return launch_ui()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        _report_startup_error()
        raise SystemExit(1)
