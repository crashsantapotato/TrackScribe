"""Pipeline modes and their ordered active stage graphs."""

from __future__ import annotations

from trackscribe.errors import PipelineError
from trackscribe.harmony_backends import (
    AGNOSTIC_AMT,
    COMPARE,
    TRANSKUN,
    validate_harmony_backend,
)


PRESERVE_HARMONY = "preserve-harmony"
DETAILED_STEMS = "detailed-stems"
PIPELINE_MODES = (PRESERVE_HARMONY, DETAILED_STEMS)

COMMON_STAGE_ORDER = (
    "prepare_master",
    "core_separation",
    "drums_transcription",
    "drums_velocity",
    "bass_transcription",
)

PRESERVE_HARMONY_STAGE_ORDER = COMMON_STAGE_ORDER + (
    "harmony_transcription",
    "harmony_cleanup",
)

AGNOSTIC_AMT_STAGE_ORDER = COMMON_STAGE_ORDER + (
    "harmony_amt_transcription",
    "harmony_amt_velocity",
    "harmony_cleanup",
)

COMPARE_STAGE_ORDER = COMMON_STAGE_ORDER + (
    "harmony_transcription",
    "harmony_amt_transcription",
    "harmony_amt_velocity",
    "harmony_compare",
)

DETAILED_STEMS_STAGE_ORDER = COMMON_STAGE_ORDER + (
    "mega53_separation",
    "mega53_analysis",
    "guitar_transcription",
    "guitar_velocity",
    "electric_guitar_transcription",
    "electric_guitar_velocity",
    "keys_transcription",
    "synth_transcription",
)

MODE_STAGE_ORDERS = {
    PRESERVE_HARMONY: PRESERVE_HARMONY_STAGE_ORDER,
    DETAILED_STEMS: DETAILED_STEMS_STAGE_ORDER,
}

STAGE_ORDER = tuple(
    dict.fromkeys(
        PRESERVE_HARMONY_STAGE_ORDER
        + AGNOSTIC_AMT_STAGE_ORDER
        + COMPARE_STAGE_ORDER
        + DETAILED_STEMS_STAGE_ORDER
    )
)


def stages_for_mode(mode: str) -> tuple[str, ...]:
    """Return the active ordered graph for a validated pipeline mode."""

    try:
        return MODE_STAGE_ORDERS[mode]
    except KeyError as exc:
        raise PipelineError(
            f"Unknown pipeline mode {mode!r}; expected one of {PIPELINE_MODES}"
        ) from exc


def stages_for_run(mode: str, harmony_backend: str) -> tuple[str, ...]:
    """Return the backend-specific active graph for one invocation."""

    backend = validate_harmony_backend(harmony_backend)
    if mode == DETAILED_STEMS:
        if backend != TRANSKUN:
            raise PipelineError("Harmony backends are available only in preserve-harmony mode")
        return DETAILED_STEMS_STAGE_ORDER
    if mode != PRESERVE_HARMONY:
        return stages_for_mode(mode)
    return {
        TRANSKUN: PRESERVE_HARMONY_STAGE_ORDER,
        AGNOSTIC_AMT: AGNOSTIC_AMT_STAGE_ORDER,
        COMPARE: COMPARE_STAGE_ORDER,
    }[backend]
