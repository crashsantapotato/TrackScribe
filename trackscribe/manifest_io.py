"""Path normalization and atomic JSON helpers for the project manifest."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from trackscribe.errors import PipelineError


def relative_output(root: Path, path: Path) -> str:
    """Return a portable project-relative output path and reject escaped outputs."""

    resolved = path.resolve()
    try:
        return resolved.relative_to(root).as_posix()
    except ValueError as exc:
        raise PipelineError(f"Stage output escaped project directory: {resolved}") from exc


def display_input(root: Path, path: Path) -> str:
    """Use a relative path for project inputs and an absolute path for external inputs."""

    try:
        return relative_output(root, path)
    except PipelineError:
        return str(path.resolve())


def drop_stage_outputs(data: dict[str, Any], name: str) -> None:
    """Remove stale public output/model mappings before rerunning or skipping a stage."""

    stage = data["stages"].get(name, {})
    for key, value in stage.get("outputs", {}).items():
        if data["outputs"].get(key) == value:
            data["outputs"].pop(key)
    data["used_models"].pop(name, None)


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    """Write formatted JSON to a sibling temporary file before atomic replacement."""

    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)
