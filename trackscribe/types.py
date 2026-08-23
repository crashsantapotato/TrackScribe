"""Shared typed values used by the pipeline API and stage adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class ProgressEvent:
    """One UI-neutral progress notification emitted by the service."""

    stage: str
    status: str
    message: str
    overall_progress: float
    details: dict[str, Any] = field(default_factory=dict)


ProgressCallback = Callable[[ProgressEvent], None]


@dataclass(frozen=True)
class PipelineResult:
    """Final paths and status returned to CLI or a future Gradio handler."""

    project_dir: Path
    manifest_path: Path
    status: str
    outputs: dict[str, Path]


@dataclass
class StageOutcome:
    """Files and provenance produced by a completed stage action."""

    outputs: dict[str, Path]
    command: list[str] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
