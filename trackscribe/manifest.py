"""Persistent project manifest and cache metadata for resumable pipeline stages."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from trackscribe.layout import ProjectLayout
from trackscribe.manifest_data import load_or_create, source_record
from trackscribe.manifest_io import (
    atomic_write_json,
    display_input,
    drop_stage_outputs,
    relative_output,
)
from trackscribe.manifest_modes import activate_harmony_backend, activate_mode
from trackscribe.provenance import utc_now


class ProjectManifest:
    """Own atomic updates to project.json and validate cached stage artifacts."""
    def __init__(
        self,
        layout: ProjectLayout,
        input_path: Path,
        config: dict[str, Any],
        *,
        pipeline_mode: str | None = None,
        active_stages: set[str] | None = None,
        harmony_backend: str | None = None,
    ) -> None:
        """Load or initialize a project manifest for the requested source audio."""

        self.layout = layout
        self.data = load_or_create(layout, source_record(input_path.resolve()))
        for key, default in (
            ("stages", {}),
            ("outputs", {}),
            ("used_models", {}),
            ("runs", []),
        ):
            self.data.setdefault(key, default)
        self.data["config"] = config
        if pipeline_mode is not None:
            activate_mode(self.data, pipeline_mode, active_stages or set())
        activate_harmony_backend(self.data, harmony_backend)
        self.data["updated_at"] = utc_now()
        self._save()

    def start_run(self) -> None:
        """Record a new invocation while retaining completed stage cache records."""

        self.data["status"] = "running"
        self.data["runs"].append(
            {
                "started_at": utc_now(),
                "status": "running",
                "pipeline_mode": self.data.get("pipeline_mode"),
            }
        )
        self._save()

    def cached_stage(self, name: str, fingerprint: str) -> dict[str, Any] | None:
        """Return a completed cache record only when every declared output still exists."""

        stage = self.data["stages"].get(name)
        if not stage or stage.get("status") != "completed":
            return None
        if stage.get("fingerprint") != fingerprint:
            return None
        output_paths = list(stage.get("outputs", {}).values())
        outputs_exist = all((self.layout.root / value).is_file() for value in output_paths)
        if not output_paths or not outputs_exist:
            return None
        return stage

    def start_stage(
        self,
        name: str,
        fingerprint: str,
        inputs: list[Path],
        input_signatures: list[dict[str, Any]],
        model: dict[str, Any],
        parameters: dict[str, Any],
        cache_context: dict[str, Any],
    ) -> None:
        """Persist a running record before executing external work."""

        previous = self.data["stages"].get(name, {})
        drop_stage_outputs(self.data, name)
        self.data["stages"][name] = {
            "status": "running",
            "started_at": utc_now(),
            "fingerprint": fingerprint,
            "attempts": int(previous.get("attempts", 0)) + 1,
            "inputs": [display_input(self.layout.root, path) for path in inputs],
            "input_signatures": input_signatures,
            "model": model,
            "parameters": parameters,
            "cache_context": cache_context,
            "cache_hit": False,
            "active_in_mode": True,
        }
        self._save()

    def complete_stage(
        self,
        name: str,
        outputs: dict[str, Path],
        duration_seconds: float,
        command: list[str] | None,
        metadata: dict[str, Any],
        output_signatures: dict[str, dict[str, Any]],
    ) -> None:
        """Commit outputs and provenance for a successful stage."""

        stage = self.data["stages"][name]
        relative_outputs = {
            key: relative_output(self.layout.root, path) for key, path in outputs.items()
        }
        stage.update(
            {
                "status": "completed",
                "completed_at": utc_now(),
                "duration_seconds": round(duration_seconds, 3),
                "outputs": relative_outputs,
                "command": command,
                "executable": command[0] if command else None,
                "metadata": metadata,
                "output_signatures": output_signatures,
            }
        )
        self.data["outputs"].update(relative_outputs)
        if stage["model"]:
            self.data["used_models"][name] = stage["model"]
        self._save()

    def record_stage_runtime(
        self,
        name: str,
        command: list[str],
        metadata: dict[str, Any],
    ) -> None:
        """Persist runtime provenance before an external command can fail."""

        stage = self.data["stages"].get(name)
        if not stage or stage.get("status") != "running":
            raise RuntimeError(f"Stage '{name}' is not running")
        stage.update(
            {
                "command": command,
                "executable": command[0] if command else None,
                "metadata": metadata,
            }
        )
        self._save()

    def mark_cache_hit(self, name: str) -> None:
        """Record that a completed stage was reused by the current invocation."""

        stage = self.data["stages"][name]
        stage["cache_hit"] = True
        stage["last_cache_hit_at"] = utc_now()
        stage["cache_hits"] = int(stage.get("cache_hits", 0)) + 1
        self._save()

    def skip_stage(self, name: str, reason: str, metadata: dict[str, Any]) -> None:
        """Record a deliberate conditional skip, such as an IGNORE stem."""

        drop_stage_outputs(self.data, name)
        self.data["stages"][name] = {
            "status": "skipped",
            "completed_at": utc_now(),
            "reason": reason,
            "metadata": metadata,
        }
        self._save()

    def fail_stage(self, name: str, error: BaseException, duration_seconds: float) -> None:
        """Persist an actionable failure without discarding prior completed stages."""

        stage = self.data["stages"].setdefault(name, {})
        stage.update(
            {
                "status": "failed",
                "completed_at": utc_now(),
                "duration_seconds": round(duration_seconds, 3),
                "error": {"type": type(error).__name__, "message": str(error)},
            }
        )
        self.finish_run("failed")

    def finish_run(self, status: str) -> None:
        """Set project and current invocation terminal status."""

        completed_at = utc_now()
        self.data["status"] = status
        self.data["updated_at"] = completed_at
        if self.data["runs"]:
            current_run = self.data["runs"][-1]
            started_at = datetime.fromisoformat(current_run["started_at"])
            duration = datetime.fromisoformat(completed_at) - started_at
            current_run.update(
                {
                    "completed_at": completed_at,
                    "duration_seconds": round(duration.total_seconds(), 3),
                    "status": status,
                }
            )
        self._save()

    def public_outputs(self) -> dict[str, Path]:
        """Return manifest output names as absolute project paths."""

        return {key: self.layout.root / value for key, value in self.data["outputs"].items()}

    def _save(self) -> None:
        self.data["updated_at"] = utc_now()
        atomic_write_json(self.layout.manifest, self.data)
