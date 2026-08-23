"""Generic stage lifecycle, fingerprinting, cache reuse, and progress emission."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Callable

from trackscribe.errors import StageError
from trackscribe.layout import ProjectLayout
from trackscribe.manifest import ProjectManifest
from trackscribe.provenance import file_signature, stable_hash
from trackscribe.types import ProgressCallback, ProgressEvent, StageOutcome


StageAction = Callable[[], StageOutcome]


class StageExecutor:
    """Execute stage actions with shared cache, manifest, and callback behavior."""

    def __init__(
        self,
        layout: ProjectLayout,
        manifest: ProjectManifest,
        callback: ProgressCallback | None,
        force_stages: set[str],
    ) -> None:
        """Store project services used by every stage adapter."""

        self.layout = layout
        self.manifest = manifest
        self.callback = callback
        self.force_stages = force_stages
        self.stage_index = 0
        self.stage_total = 1
        self.current_stage = "pipeline"

    def set_position(self, name: str, index: int, total: int) -> None:
        """Set stage position used to calculate UI-neutral overall progress."""

        self.current_stage = name
        self.stage_index = index
        self.stage_total = max(total, 1)

    def execute(
        self,
        name: str,
        *,
        inputs: list[Path],
        model: dict[str, Any],
        parameters: dict[str, Any],
        cache_context: dict[str, Any] | None = None,
        action: StageAction,
    ) -> StageOutcome:
        """Reuse a valid cached stage or execute and verify its declared files."""

        input_signatures = [file_signature(path) for path in inputs]
        context = cache_context or {}
        fingerprint_data = {
            "stage": name,
            "inputs": input_signatures,
            "model": model,
            "parameters": parameters,
        }
        if context:
            fingerprint_data["cache_context"] = context
        fingerprint = stable_hash(fingerprint_data)
        if name not in self.force_stages:
            cached = self.manifest.cached_stage(name, fingerprint)
            if cached:
                self.manifest.mark_cache_hit(name)
                outputs = {
                    key: self.layout.root / value for key, value in cached["outputs"].items()
                }
                self._log_lifecycle(name, "cached", "reused cached outputs")
                self.emit("cached", "reused cached outputs", completed=True)
                return StageOutcome(
                    outputs=outputs,
                    command=cached.get("command"),
                    metadata=cached.get("metadata", {}),
                )

        self.manifest.start_stage(
            name, fingerprint, inputs, input_signatures, model, parameters, context
        )
        self._log_lifecycle(name, "started", "started")
        self.emit("started", "started")
        started = time.perf_counter()
        try:
            outcome = action()
            missing = [path for path in outcome.outputs.values() if not path.is_file()]
            if not outcome.outputs or missing:
                raise StageError(f"Stage '{name}' did not create outputs: {missing}")
            duration = time.perf_counter() - started
            output_signatures = {
                key: file_signature(path) for key, path in outcome.outputs.items()
            }
            self.manifest.complete_stage(
                name,
                outcome.outputs,
                duration,
                outcome.command,
                outcome.metadata,
                output_signatures,
            )
            self._log_lifecycle(name, "completed", f"completed in {duration:.1f}s")
            self.emit("completed", f"completed in {duration:.1f}s", completed=True)
            return outcome
        except Exception as exc:
            duration = time.perf_counter() - started
            self.manifest.fail_stage(name, exc, duration)
            self._log_lifecycle(name, "failed", str(exc))
            self.emit("failed", str(exc), completed=True)
            raise

    def skip(self, name: str, reason: str, metadata: dict[str, Any]) -> None:
        """Record and announce a deliberate conditional stage skip."""

        self.manifest.skip_stage(name, reason, metadata)
        self._log_lifecycle(name, "skipped", reason)
        self.emit("skipped", reason, completed=True)

    def emit(
        self,
        status: str,
        message: str,
        details: dict[str, Any] | None = None,
        *,
        completed: bool = False,
    ) -> None:
        """Emit a callback event while isolating callback failures from pipeline work."""

        if not self.callback:
            return
        numerator = self.stage_index + (1 if completed else 0)
        event = ProgressEvent(
            stage=self.current_stage,
            status=status,
            message=message,
            overall_progress=min(max(numerator / self.stage_total, 0.0), 1.0),
            details=details or {},
        )
        try:
            self.callback(event)
        except Exception:
            logging.exception("Progress callback failed; pipeline execution continues")

    def _log_lifecycle(self, name: str, status: str, message: str) -> None:
        """Append lifecycle events even for stages that launch no subprocess."""

        log_path = self.layout.logs / f"{name}.log"
        with log_path.open("a", encoding="utf-8") as stream:
            stream.write(f"[{status}] {message}\n")
