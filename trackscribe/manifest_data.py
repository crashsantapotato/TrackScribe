"""Construction and loading of project manifest dictionaries."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from trackscribe.errors import PipelineError
from trackscribe.layout import ProjectLayout
from trackscribe.provenance import sha256_file, utc_now


def source_record(source: Path) -> dict[str, Any]:
    """Build stable identity and diagnostic metadata for the input audio."""

    return {
        "original_path": str(source),
        "original_extension": source.suffix.lower(),
        "sha256": sha256_file(source),
        "size": source.stat().st_size,
        "mtime_ns": source.stat().st_mtime_ns,
    }


def load_or_create(layout: ProjectLayout, source: dict[str, Any]) -> dict[str, Any]:
    """Load a compatible manifest or create a new schema-v1 dictionary."""

    if layout.manifest.is_file():
        try:
            data = json.loads(layout.manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PipelineError(f"Cannot read project manifest: {exc}") from exc
        if data.get("input", {}).get("sha256") != source["sha256"]:
            raise PipelineError(
                "Output project belongs to different input audio; choose another --output"
            )
        data["input"] = source
        return data
    return {
        "schema_version": 1,
        "project_id": str(uuid.uuid4()),
        "created_at": utc_now(),
        "status": "pending",
        "input": source,
        "stages": {},
        "outputs": {},
        "used_models": {},
        "runs": [],
    }
