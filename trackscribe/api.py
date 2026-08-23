"""UI-neutral public service API for the resumable stem and MIDI pipeline."""

from __future__ import annotations

from pathlib import Path

from trackscribe.audio import (
    is_supported_audio,
    supported_audio_description,
)
from trackscribe.config import DEFAULT_CONFIG_PATH, PipelineConfig
from trackscribe.errors import PipelineError
from trackscribe.executor import StageExecutor
from trackscribe.harmony_backends import TRANSKUN
from trackscribe.layout import ProjectLayout
from trackscribe.manifest import ProjectManifest
from trackscribe.modes import PRESERVE_HARMONY, STAGE_ORDER, stages_for_run
from trackscribe.orchestrator import PipelineOrchestrator
from trackscribe.provenance import stable_hash
from trackscribe.stages.base import StageServices
from trackscribe.types import PipelineResult, ProgressCallback


def run_pipeline(
    input_path: str | Path,
    output_dir: str | Path,
    *,
    config_path: str | Path = DEFAULT_CONFIG_PATH,
    mode: str = PRESERVE_HARMONY,
    progress_callback: ProgressCallback | None = None,
    force: bool = False,
    force_stages: set[str] | None = None,
    stop_after: str | None = None,
    harmony_cleanup_enabled: bool | None = None,
    harmony_backend: str = TRANSKUN,
) -> PipelineResult:
    """Run or resume one project and return paths suitable for CLI or Gradio.

    Args:
        input_path: Supported source audio decoded to project-local master.wav.
        output_dir: Structured project directory.
        config_path: JSON file describing isolated venvs, models, and parameters.
        mode: Harmony-preserving default or experimental detailed stem mode.
        progress_callback: Optional callback receiving UI-neutral progress events.
        force: Re-run every stage even when its fingerprint and outputs match.
        force_stages: Specific stage names to invalidate.
        stop_after: Optional stage after which to return a partial project.
        harmony_cleanup_enabled: Optional per-run override for conservative cleanup.
        harmony_backend: Transkun, external agnostic AMT, or raw A/B compare.

    Returns:
        Completed or partial project paths and status.

    Raises:
        PipelineError: If input, configuration, or a stage is invalid.
    """

    source = Path(input_path).expanduser().resolve()
    if not source.is_file():
        raise PipelineError(f"Input audio not found: {source}")
    if not is_supported_audio(source):
        raise PipelineError(
            f"Unsupported audio format '{source.suffix.lower() or '(none)'}'. "
            f"Supported: {supported_audio_description()}"
        )
    active_stages = stages_for_run(mode, harmony_backend)
    if stop_after is not None and stop_after not in active_stages:
        raise PipelineError(f"Stage '{stop_after}' is not active in mode '{mode}'")
    requested_force = set(force_stages or set())
    unknown = requested_force.difference(STAGE_ORDER)
    if unknown:
        raise PipelineError(f"Unknown force stages: {sorted(unknown)}")
    inactive_force = requested_force.difference(active_stages)
    if inactive_force:
        raise PipelineError(
            f"Force stages are not active in mode '{mode}': {sorted(inactive_force)}"
        )
    if force:
        requested_force.update(active_stages)

    config = PipelineConfig.load(config_path)
    config.validate()
    layout = ProjectLayout.create(output_dir)
    snapshot = config.snapshot()
    manifest = ProjectManifest(
        layout,
        source,
        {
            "path": str(config.path),
            "fingerprint": stable_hash(snapshot),
            "snapshot": snapshot,
        },
        pipeline_mode=mode,
        active_stages=set(active_stages),
        harmony_backend=harmony_backend,
    )
    manifest.start_run()
    executor = StageExecutor(layout, manifest, progress_callback, requested_force)
    repository_root = Path(__file__).resolve().parents[1]
    services = StageServices(config, layout, executor, repository_root)
    status = PipelineOrchestrator(
        services,
        manifest,
        stop_after,
        mode=mode,
        harmony_cleanup_enabled=harmony_cleanup_enabled,
        harmony_backend=harmony_backend,
    ).run(source)
    return PipelineResult(
        project_dir=layout.root,
        manifest_path=layout.manifest,
        status=status,
        outputs=manifest.public_outputs(),
    )
