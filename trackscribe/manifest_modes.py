"""Mode activation helpers for legacy and multi-mode project manifests."""

from __future__ import annotations

from typing import Any

from trackscribe.provenance import utc_now


def activate_mode(
    data: dict[str, Any], pipeline_mode: str, active_stages: set[str]
) -> None:
    """Select one stage graph while retaining inactive records as reusable cache."""

    previous = data.get("pipeline_mode")
    if previous != pipeline_mode:
        data.setdefault("mode_history", []).append(
            {
                "from": previous or "legacy",
                "to": pipeline_mode,
                "changed_at": utc_now(),
            }
        )
    data["pipeline_mode"] = pipeline_mode
    for name, stage in data["stages"].items():
        stage["active_in_mode"] = name in active_stages
    rebuild_public_maps(data, active_stages)


def rebuild_public_maps(data: dict[str, Any], active_stages: set[str]) -> None:
    """Expose only successful outputs and models belonging to the active graph."""

    outputs: dict[str, str] = {}
    models: dict[str, Any] = {}
    for name, stage in data["stages"].items():
        if name not in active_stages or stage.get("status") != "completed":
            continue
        outputs.update(stage.get("outputs", {}))
        if stage.get("model"):
            models[name] = stage["model"]
    data["outputs"] = outputs
    data["used_models"] = models


def activate_harmony_backend(data: dict[str, Any], backend: str | None) -> None:
    """Record backend selection and retain a concise switch history."""

    if backend is None:
        return
    previous = data.get("harmony_backend")
    if previous != backend:
        data.setdefault("harmony_backend_history", []).append(
            {
                "from": previous or "legacy",
                "to": backend,
                "changed_at": utc_now(),
            }
        )
    data["harmony_backend"] = backend
