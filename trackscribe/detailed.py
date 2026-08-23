"""Experimental Mega53 branch retained behind detailed-stems mode."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from trackscribe.stages import hf_midi, mega53, transkun

if TYPE_CHECKING:
    from trackscribe.orchestrator import PipelineOrchestrator


def run(orchestrator: PipelineOrchestrator) -> None:
    """Run Mega53 analysis followed by selected instrument transcriptions."""

    services = orchestrator.services
    context = {"pipeline_mode": orchestrator.mode}
    mega = orchestrator._invoke(
        "mega53_separation",
        lambda: mega53.separate(
            services, services.layout.stems / "other.wav", cache_context=context
        ),
    )
    analysis = orchestrator._invoke(
        "mega53_analysis",
        lambda: mega53.analyze(
            services, sorted(mega.outputs.values()), cache_context=context
        ),
    )
    statuses = mega53.statuses(analysis)
    _run_guitar(orchestrator, "guitar", statuses)
    _run_guitar(orchestrator, "electric-guitar", statuses)
    _run_transkun(orchestrator, "keys", statuses)
    _run_transkun(orchestrator, "synth", statuses)


def _run_guitar(
    orchestrator: PipelineOrchestrator, stem: str, statuses: dict[str, str]
) -> None:
    services = orchestrator.services
    prefix = stem.replace("-", "_")
    transcribe_stage = f"{prefix}_transcription"
    velocity_stage = f"{prefix}_velocity"
    status = statuses.get(stem, "IGNORE")
    if not orchestrator._selected(status):
        reason = f"Mega53 classified {stem} as {status}"
        for stage in (transcribe_stage, velocity_stage):
            orchestrator._invoke(
                stage,
                lambda stage=stage: orchestrator._skip(stage, reason, stem, status),
            )
        return
    audio = services.layout.mega53 / f"{stem}.wav"
    raw_midi = services.layout.work / f"{stem}.raw.mid"
    orchestrator._require(audio)
    context = {"pipeline_mode": orchestrator.mode}
    orchestrator._invoke(
        transcribe_stage,
        lambda: hf_midi.transcribe(
            services,
            stage=transcribe_stage,
            audio=audio,
            instrument="guitar",
            output=raw_midi,
            output_key=f"intermediate.{prefix}_midi",
            parameter_section="guitar_transcription",
            cache_context=context,
        ),
    )
    orchestrator._invoke(
        velocity_stage,
        lambda: hf_midi.add_guitar_velocity(
            services,
            stage=velocity_stage,
            audio=audio,
            raw_midi=raw_midi,
            output=services.layout.midi / f"{stem}.mid",
            output_key=f"midi.{prefix}",
            cache_context=context,
        ),
    )


def _run_transkun(
    orchestrator: PipelineOrchestrator, stem: str, statuses: dict[str, str]
) -> None:
    services = orchestrator.services
    stage = f"{stem}_transcription"
    status = statuses.get(stem, "IGNORE")
    if not orchestrator._selected(status):
        reason = f"Mega53 classified {stem} as {status}"
        orchestrator._invoke(
            stage, lambda: orchestrator._skip(stage, reason, stem, status)
        )
        return
    audio = services.layout.mega53 / f"{stem}.wav"
    orchestrator._require(audio)
    orchestrator._invoke(
        stage,
        lambda: transkun.transcribe(
            services,
            stage=stage,
            audio=audio,
            output=services.layout.midi / f"{stem}.mid",
            output_key=f"midi.{stem}",
            cache_context={"pipeline_mode": orchestrator.mode},
        ),
    )
