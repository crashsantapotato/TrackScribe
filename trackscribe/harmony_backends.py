"""Supported harmony transcription backend identifiers."""

from __future__ import annotations

from trackscribe.errors import PipelineError


TRANSKUN = "transkun"
AGNOSTIC_AMT = "agnostic-amt"
COMPARE = "compare"
HARMONY_BACKENDS = (TRANSKUN, AGNOSTIC_AMT, COMPARE)


def validate_harmony_backend(backend: str) -> str:
    """Return a supported backend name or raise an actionable pipeline error."""

    if backend not in HARMONY_BACKENDS:
        raise PipelineError(
            f"Unknown harmony backend {backend!r}; expected one of {HARMONY_BACKENDS}"
        )
    return backend
