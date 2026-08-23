"""Dependency-free discovery for a local REAPER executable."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


REAPER_COMMON_PATHS = (
    Path("C:/Program Files/REAPER (x64)/reaper.exe"),
    Path("C:/Program Files/REAPER/reaper.exe"),
)


def _registry_candidates() -> tuple[Path, ...]:
    """Read uninstall metadata when winreg exists; registry failures are harmless."""

    if sys.platform != "win32":
        return ()
    try:
        import winreg
    except ImportError:
        return ()
    candidates: list[Path] = []
    roots = (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE)
    keys = (
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\REAPER",
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\REAPER (x64)",
        r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\REAPER",
        r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\REAPER (x64)",
    )
    for root in roots:
        for name in keys:
            try:
                with winreg.OpenKey(root, name) as key:
                    location, _ = winreg.QueryValueEx(key, "InstallLocation")
            except OSError:
                continue
            candidates.append(Path(location) / "reaper.exe")
    return tuple(candidates)


def find_reaper_executable(configured: str | Path | None = None) -> Path | None:
    """Prefer an explicit path, PATH, common installs, then registry metadata."""

    candidates: list[Path] = []
    if configured:
        candidates.append(Path(configured).expanduser())
    on_path = shutil.which("reaper.exe") or shutil.which("reaper")
    if on_path:
        candidates.append(Path(on_path))
    candidates.extend(REAPER_COMMON_PATHS)
    candidates.extend(_registry_candidates())
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return None
