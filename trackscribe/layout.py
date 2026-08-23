"""Canonical project directory layout for audio and MIDI pipeline outputs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from trackscribe.errors import PipelineError


@dataclass(frozen=True)
class ProjectLayout:
    """All stable output and private working directories for one project."""

    root: Path
    master: Path
    stems: Path
    mega53: Path
    midi: Path
    logs: Path
    work: Path
    manifest: Path

    @classmethod
    def create(cls, root: str | Path) -> "ProjectLayout":
        """Create and return the structured project directory tree."""

        project_root = Path(root).expanduser().resolve()
        if project_root.exists() and not project_root.is_dir():
            raise PipelineError(f"Output path is not a directory: {project_root}")
        layout = cls(
            root=project_root,
            master=project_root / "master.wav",
            stems=project_root / "stems",
            mega53=project_root / "stems" / "mega53",
            midi=project_root / "midi",
            logs=project_root / "logs",
            work=project_root / ".work",
            manifest=project_root / "project.json",
        )
        for folder in (
            layout.root,
            layout.stems,
            layout.midi,
            layout.logs,
            layout.work,
        ):
            folder.mkdir(parents=True, exist_ok=True)
        return layout
