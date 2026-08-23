"""Streaming subprocess execution for tools isolated in dedicated venvs."""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Callable

from trackscribe.errors import ProcessError


ProcessEvent = Callable[[str, str, dict[str, Any]], None]


def run_process(
    command: list[str],
    *,
    stage: str,
    cwd: Path,
    log_path: Path,
    emit: ProcessEvent,
) -> None:
    """Run one command, stream combined output, and persist a complete stage log."""

    normalized = [str(part) for part in command]
    log_path.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    logging.info("[%s] running %s", stage, subprocess.list2cmdline(normalized))
    with log_path.open("a", encoding="utf-8", errors="replace") as log_file:
        log_file.write(f"\n$ {subprocess.list2cmdline(normalized)}\n")
        log_file.flush()
        with subprocess.Popen(
            normalized,
            cwd=str(cwd),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        ) as process:
            assert process.stdout is not None
            for line in process.stdout:
                log_file.write(line)
                log_file.flush()
                message = line.rstrip()
                if message:
                    logging.debug("[%s] %s", stage, message)
                    emit("running", message, {"source": "subprocess"})
            returncode = process.wait()
    if returncode:
        raise ProcessError(normalized, returncode, str(log_path))
