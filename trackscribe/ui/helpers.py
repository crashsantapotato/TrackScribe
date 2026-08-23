"""Pure helpers shared by the TrackScribe desktop UI and its tests."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from trackscribe.audio import SUPPORTED_AUDIO_EXTENSIONS, supported_audio_description
from trackscribe.config import DEFAULT_CONFIG_PATH
from trackscribe.harmony_backends import AGNOSTIC_AMT, COMPARE, TRANSKUN
from trackscribe.modes import DETAILED_STEMS, PRESERVE_HARMONY, stages_for_run
from trackscribe.types import ProgressCallback, ProgressEvent


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "projects"
DEFAULT_UI_BACKEND = AGNOSTIC_AMT
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}

BACKEND_LABELS = {
    AGNOSTIC_AMT: "Agnostic AMT",
    TRANSKUN: "Transkun",
    COMPARE: "Compare",
}
MODE_LABELS = {
    PRESERVE_HARMONY: "Preserve harmony",
    DETAILED_STEMS: "Detailed stems (experimental)",
}
STAGE_LABELS = {
    "prepare_master": "Prepare master",
    "core_separation": "Core separation",
    "drums_transcription": "Drums transcription",
    "drums_velocity": "Drums velocity",
    "bass_transcription": "Bass transcription",
    "harmony_transcription": "Harmony Transkun",
    "harmony_amt_transcription": "Harmony AMT",
    "harmony_amt_velocity": "Harmony velocity",
    "harmony_cleanup": "Harmony cleanup",
    "harmony_compare": "A/B comparison",
    "mega53_separation": "Mega53 separation",
    "mega53_analysis": "Mega53 analysis",
    "guitar_transcription": "Guitar transcription",
    "guitar_velocity": "Guitar velocity",
    "electric_guitar_transcription": "Electric guitar transcription",
    "electric_guitar_velocity": "Electric guitar velocity",
    "keys_transcription": "Keys transcription",
    "synth_transcription": "Synth transcription",
}

PRIMARY_ARTIFACTS = (
    ("drums_midi", "Drums MIDI", "midi/drums.mid"),
    ("bass_midi", "Bass MIDI", "midi/bass.mid"),
    ("harmony_midi", "Harmony MIDI", "midi/harmony.mid"),
)
COMPARE_ARTIFACTS = (
    ("transkun_raw", "Transkun Raw", "midi/ab/harmony_transkun_raw.mid"),
    ("amt_raw", "AMT Raw", "midi/ab/harmony_amt_raw.mid"),
    ("amt_velocity", "AMT Velocity", "midi/ab/harmony_amt_velocity.mid"),
    ("compare_diagnostics", "A/B Diagnostics", "midi/ab/compare.json"),
)
DETAILED_ARTIFACTS = (
    ("guitar_midi", "Guitar MIDI", "midi/guitar.mid"),
    ("electric_guitar_midi", "Electric Guitar MIDI", "midi/electric-guitar.mid"),
    ("keys_midi", "Keys MIDI", "midi/keys.mid"),
    ("synth_midi", "Synth MIDI", "midi/synth.mid"),
)


@dataclass(frozen=True)
class PipelineJob:
    """Immutable parameters for one background pipeline invocation."""

    input_path: Path
    output_dir: Path
    harmony_backend: str = DEFAULT_UI_BACKEND
    mode: str = PRESERVE_HARMONY
    harmony_cleanup_enabled: bool = True
    verbose: bool = False
    config_path: Path = DEFAULT_CONFIG_PATH


@dataclass(frozen=True)
class ValidationResult:
    """Human-readable validation result for a prospective UI job."""

    valid: bool
    message: str = ""


@dataclass(frozen=True)
class Artifact:
    """One discovered project artifact suitable for an Open button."""

    key: str
    label: str
    path: Path
    group: str


@dataclass(frozen=True)
class ArtifactDiscovery:
    """Existing outputs and folders discovered without mutating a project."""

    artifacts: tuple[Artifact, ...]
    folders: dict[str, Path]
    project_dir: Path | None = None


@dataclass(frozen=True)
class StageViewState:
    """Display state derived from one backend ProgressEvent."""

    stage: str
    label: str
    state: str
    prefix: str
    index: int
    total: int
    percent: int
    message: str


def safe_project_name(filename: str, fallback: str = "track") -> str:
    """Convert an input filename to a safe, readable Windows project name."""

    sanitized = re.sub(
        r"[<>:\"/\\|?*\x00-\x1f]", "_", str(filename).strip()
    )
    stem = Path(sanitized).stem.strip()
    stem = re.sub(r"\s+", "_", stem)
    stem = re.sub(r"_+", "_", stem).strip(" ._")
    if not stem:
        stem = fallback
    if stem.upper() in WINDOWS_RESERVED_NAMES:
        stem = f"_{stem}"
    return stem[:100].rstrip(" ._") or fallback


def resolved_project_path(output_root: Path, project_name: str) -> Path:
    """Combine the independently selected root and project name."""

    return output_root.expanduser().resolve() / project_name


def default_project_path(project_name: str, root: Path = PROJECT_ROOT) -> Path:
    """Return the default project output without creating directories."""

    return resolved_project_path(root / "projects", safe_project_name(project_name))


def validate_output_root(output_root: str | Path, project_name: str) -> ValidationResult:
    """Validate a root/name pair without creating either directory."""

    raw_root = str(output_root).strip()
    if not raw_root:
        return ValidationResult(False, "Output root cannot be empty.")
    if not project_name.strip():
        return ValidationResult(False, "Project name cannot be empty.")
    if safe_project_name(project_name) != project_name:
        return ValidationResult(False, "Project name contains unsupported filename characters.")
    root = Path(raw_root).expanduser().resolve()
    if root.exists() and not root.is_dir():
        return ValidationResult(False, f"Output root is not a directory: {root}")
    ancestor = root
    while not ancestor.exists() and ancestor != ancestor.parent:
        ancestor = ancestor.parent
    if not ancestor.is_dir() or not os.access(ancestor, os.W_OK):
        return ValidationResult(False, f"Output root is not writable: {root}")
    project = resolved_project_path(root, project_name)
    if project.exists() and not project.is_dir():
        return ValidationResult(False, f"Project output is not a directory: {project}")
    return ValidationResult(True)


def project_uses_resume(output_dir: Path) -> bool:
    """Return true when an existing directory will be resumed, never overwritten."""

    return output_dir.exists() and output_dir.is_dir()


def validate_input(
    input_path: Path | None,
    project_name: str,
    output_dir: Path,
    supported_extensions: tuple[str, ...] = SUPPORTED_AUDIO_EXTENSIONS,
) -> ValidationResult:
    """Validate UI fields without creating or deleting any project content."""

    if input_path is None:
        return ValidationResult(False, "Choose an input audio file first.")
    if not input_path.is_file():
        return ValidationResult(False, f"Input file does not exist: {input_path}")
    if input_path.suffix.lower() not in supported_extensions:
        allowed = (
            supported_audio_description()
            if supported_extensions == SUPPORTED_AUDIO_EXTENSIONS
            else ", ".join(supported_extensions)
        )
        return ValidationResult(False, f"Unsupported audio format. Supported: {allowed}")
    if not project_name.strip():
        return ValidationResult(False, "Project name cannot be empty.")
    if safe_project_name(project_name) != project_name:
        return ValidationResult(False, "Project name contains unsupported filename characters.")
    if output_dir.exists() and not output_dir.is_dir():
        return ValidationResult(False, f"Project output is not a directory: {output_dir}")
    ancestor = output_dir.parent
    while not ancestor.exists() and ancestor != ancestor.parent:
        ancestor = ancestor.parent
    if not ancestor.is_dir() or not os.access(ancestor, os.W_OK):
        return ValidationResult(False, f"Project output is not writable: {output_dir}")
    return ValidationResult(True)


def build_pipeline_kwargs(
    job: PipelineJob, progress_callback: ProgressCallback
) -> dict[str, Any]:
    """Translate a UI job directly to the existing public API contract."""

    return {
        "input_path": job.input_path,
        "output_dir": job.output_dir,
        "config_path": job.config_path,
        "mode": job.mode,
        "progress_callback": progress_callback,
        "force": False,
        "harmony_cleanup_enabled": job.harmony_cleanup_enabled,
        "harmony_backend": job.harmony_backend,
    }


def stage_order_for_job(job: PipelineJob) -> tuple[str, ...]:
    """Return the exact backend stage graph used for progress rows."""

    return stages_for_run(job.mode, job.harmony_backend)


def stage_view_state(event: ProgressEvent, stage_order: tuple[str, ...]) -> StageViewState:
    """Map one structured backend event to honest stage-level UI text."""

    state_map = {
        "started": ("Processing", "▶"),
        "cached": ("Cached", "↻"),
        "completed": ("Done", "✓"),
        "skipped": ("Skipped", "–"),
        "failed": ("Failed", "✕"),
    }
    state, prefix = state_map.get(event.status, (event.status.title(), "○"))
    try:
        index = stage_order.index(event.stage) + 1
    except ValueError:
        index = 0
    percent = max(0, min(100, round(event.overall_progress * 100)))
    return StageViewState(
        stage=event.stage,
        label=STAGE_LABELS.get(event.stage, event.stage.replace("_", " ").title()),
        state=state,
        prefix=prefix,
        index=index,
        total=len(stage_order),
        percent=percent,
        message=event.message,
    )


def discover_artifacts(project_dir: Path) -> ArtifactDiscovery:
    """Discover known outputs defensively; missing files are simply omitted."""

    artifacts: list[Artifact] = []
    for group, specs in (
        ("Primary MIDI", PRIMARY_ARTIFACTS),
        ("A/B Results", COMPARE_ARTIFACTS),
        ("Detailed MIDI", DETAILED_ARTIFACTS),
    ):
        for key, label, relative in specs:
            path = project_dir / relative
            if path.is_file():
                artifacts.append(Artifact(key, label, path, group))
    folders = {
        key: path
        for key, path in {
            "project": project_dir,
            "midi": project_dir / "midi",
            "stems": project_dir / "stems",
            "logs": project_dir / "logs",
        }.items()
        if path.is_dir()
    }
    return ArtifactDiscovery(tuple(artifacts), folders, project_dir if project_dir.is_dir() else None)
