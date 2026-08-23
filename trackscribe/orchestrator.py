"""Sequential, VRAM-safe orchestration of the audio-to-stems-to-MIDI stage graph."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, TypeVar

from trackscribe import detailed
from trackscribe.errors import StageError
from trackscribe.harmony_backends import AGNOSTIC_AMT, COMPARE, TRANSKUN
from trackscribe.manifest import ProjectManifest
from trackscribe.modes import DETAILED_STEMS, PRESERVE_HARMONY, stages_for_run
from trackscribe.stages import (
    agnostic_amt, core, drums, harmony, harmony_compare,
    harmony_velocity, hf_midi, master, transkun,
)
from trackscribe.stages.base import StageServices


T = TypeVar("T")
class _RequestedStop(Exception):
    """Internal control flow used after a requested --stop-after stage."""
class PipelineOrchestrator:
    """Coordinate stage adapters without importing any Gradio implementation."""

    def __init__(
        self,
        services: StageServices,
        manifest: ProjectManifest,
        stop_after: str | None,
        mode: str = PRESERVE_HARMONY,
        harmony_cleanup_enabled: bool | None = None,
        harmony_backend: str = TRANSKUN,
    ) -> None:
        """Store service boundaries and an optional staged-validation stop point."""

        self.services = services
        self.manifest = manifest
        self.stop_after = stop_after
        self.mode = mode
        self.harmony_cleanup_enabled = harmony_cleanup_enabled
        self.harmony_backend = harmony_backend
        self.stage_order = stages_for_run(mode, harmony_backend)

    def run(self, input_path: Path) -> str:
        """Run the fixed stage graph, reusing valid cached outputs automatically."""

        try:
            self._run_common(input_path)
            if self.mode == PRESERVE_HARMONY:
                self._run_harmony()
            elif self.mode == DETAILED_STEMS:
                self._run_detailed()
        except _RequestedStop:
            self.manifest.finish_run("partial")
            return "partial"
        except Exception:
            if self.manifest.data.get("status") != "failed":
                self.manifest.finish_run("failed")
            raise
        self.manifest.finish_run("completed")
        return "completed"

    def _run_common(self, input_path: Path) -> None:
        self._invoke("prepare_master", lambda: master.run(self.services, input_path))
        self._invoke(
            "core_separation", lambda: core.run(self.services, self.services.layout.master)
        )
        raw = self._invoke(
            "drums_transcription",
            lambda: drums.transcribe(
                self.services, self.services.layout.stems / "drums.wav"
            ),
        )
        self._invoke(
            "drums_velocity",
            lambda: drums.add_velocity(
                self.services,
                self.services.layout.stems / "drums.wav",
                raw.outputs["intermediate.drums_midi"],
            ),
        )
        self._invoke(
            "bass_transcription",
            lambda: hf_midi.transcribe(
                self.services,
                stage="bass_transcription",
                audio=self.services.layout.stems / "bass.wav",
                instrument="bass",
                output=self.services.layout.midi / "bass.mid",
                output_key="midi.bass",
                parameter_section="bass_transcription",
            ),
        )

    def _run_harmony(self) -> None:
        if self.harmony_backend == TRANSKUN:
            self._run_cleanup(self._run_transkun())
        elif self.harmony_backend == AGNOSTIC_AMT:
            _raw, velocity = self._run_amt()
            self._run_cleanup(velocity)
        elif self.harmony_backend == COMPARE:
            transkun_raw = self._run_transkun()
            amt_raw, amt_velocity = self._run_amt()
            self._invoke(
                "harmony_compare",
                lambda: harmony_compare.export(
                    self.services,
                    transkun_raw=transkun_raw,
                    amt_raw=amt_raw,
                    amt_velocity=amt_velocity,
                    processing_seconds={
                        "transkun": float(self.manifest.data["stages"]
                                          ["harmony_transcription"]["duration_seconds"]),
                        "agnostic-amt": float(self.manifest.data["stages"]
                                             ["harmony_amt_transcription"]["duration_seconds"]),
                    },
                ),
            )

    def _run_transkun(self) -> Path:
        outcome = self._invoke(
            "harmony_transcription",
            lambda: transkun.transcribe(
                self.services,
                stage="harmony_transcription",
                audio=self.services.layout.stems / "other.wav",
                output=self.services.layout.midi / "harmony_raw.mid",
                output_key="midi.harmony_raw",
                parameter_section="harmony_transcription",
                cache_context={
                    "pipeline_mode": self.mode,
                    "output_contract": "harmony-raw-v1",
                },
            ),
        )
        return outcome.outputs["midi.harmony_raw"]

    def _run_amt(self) -> tuple[Path, Path]:
        outcome = self._invoke(
            "harmony_amt_transcription",
            lambda: agnostic_amt.transcribe(
                self.services, self.services.layout.stems / "other.wav"
            ),
        )
        raw = outcome.outputs["midi.harmony_amt_raw"]
        velocity = self._invoke(
            "harmony_amt_velocity",
            lambda: harmony_velocity.add_velocity(
                self.services,
                audio=self.services.layout.stems / "other.wav",
                raw_midi=raw,
            ),
        )
        return raw, velocity.outputs["midi.harmony_amt_velocity"]

    def _run_cleanup(self, raw_midi: Path) -> None:
        self._invoke(
            "harmony_cleanup",
            lambda: harmony.cleanup(
                self.services,
                audio=self.services.layout.stems / "other.wav",
                raw_midi=raw_midi,
                enabled_override=self.harmony_cleanup_enabled,
                cache_context={
                    "pipeline_mode": self.mode,
                    "harmony_backend": self.harmony_backend,
                },
            ),
        )

    def _run_detailed(self) -> None:
        detailed.run(self)

    def _invoke(self, name: str, action: Callable[[], T]) -> T:
        self.services.executor.set_position(
            name, self.stage_order.index(name), len(self.stage_order)
        )
        result = action()
        if self.stop_after == name:
            raise _RequestedStop
        return result

    def _selected(self, status: str) -> bool:
        allowed = self.services.config.section("mega53_selection")["transcribe_statuses"]
        return status in allowed

    def _skip(self, stage: str, reason: str, stem: str, status: str) -> None:
        self.services.executor.skip(stage, reason, {"stem": stem, "classification": status})

    @staticmethod
    def _require(path: Path) -> None:
        if not path.is_file():
            raise StageError(f"Required classified stem is missing: {path}")
