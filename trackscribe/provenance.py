"""Deterministic hashes and file signatures used by stage cache fingerprints."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from trackscribe.errors import PipelineError


def utc_now() -> str:
    """Return an ISO-8601 timestamp in UTC."""

    return datetime.now(timezone.utc).isoformat()


def stable_hash(value: Any) -> str:
    """Hash a JSON-serializable value with deterministic key ordering."""

    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Calculate a file SHA-256 without loading it all into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def file_signature(path: Path, *, include_sha256: bool = False) -> dict[str, Any]:
    """Return a mutation signature, optionally including the complete content hash."""

    resolved = path.resolve()
    if not resolved.is_file():
        raise PipelineError(f"Required stage input is missing: {resolved}")
    stat = resolved.stat()
    signature = {
        "path": str(resolved), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns
    }
    if include_sha256:
        signature["sha256"] = sha256_file(resolved)
    return signature
