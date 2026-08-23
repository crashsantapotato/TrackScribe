"""Pure normalization logic for audio-derived harmony note velocities."""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class VelocityFeature:
    """Pitch-aware attack, body, and broadband onset measurements for one note."""

    attack: float
    sustain: float
    onset: float


@dataclass(frozen=True)
class VelocityAssignment:
    """Calculated MIDI velocities plus fallback diagnostics."""

    velocities: list[int]
    fallback: bool
    fallback_reason: str | None


def assign_velocities(
    starts: list[float],
    features: list[VelocityFeature],
    parameters: dict[str, Any],
    *,
    audio_silent: bool = False,
) -> VelocityAssignment:
    """Map note evidence to bounded deterministic velocities.

    Args:
        starts: Note onset times in seconds, in original MIDI event order.
        features: One audio feature record for every onset.
        parameters: Configured normalization and dynamic-range parameters.
        audio_silent: Whether the audio analyser detected only silence.

    Returns:
        Velocities and an explicit fallback reason when dynamics were unavailable.

    Raises:
        ValueError: If note and feature counts or configured bounds are invalid.
    """

    if len(starts) != len(features):
        raise ValueError("Every MIDI note must have exactly one velocity feature")
    if not starts:
        return VelocityAssignment([], False, None)
    minimum = int(parameters["min_velocity"])
    maximum = int(parameters["max_velocity"])
    fallback = int(parameters["fallback_velocity"])
    if not 1 <= minimum <= maximum <= 127:
        raise ValueError("Velocity bounds must satisfy 1 <= minimum <= maximum <= 127")
    fallback = min(max(fallback, minimum), maximum)
    if audio_silent:
        return VelocityAssignment([fallback] * len(starts), True, "silent_audio")

    low = float(parameters["percentile_low"])
    high = float(parameters["percentile_high"])
    gain = float(parameters["log_gain"])
    columns = (
        [feature.attack for feature in features],
        [feature.sustain for feature in features],
        [feature.onset for feature in features],
    )
    normalized = [_robust_scale(values, low, high, gain) for values in columns]
    weights = [
        float(parameters["attack_weight"]),
        float(parameters["sustain_weight"]),
        float(parameters["onset_weight"]),
    ]
    weight_sum = sum(weights)
    if weight_sum <= 0.0:
        raise ValueError("At least one harmony velocity feature weight must be positive")
    scores = [
        sum(weights[column] * normalized[column][index] for column in range(3))
        / weight_sum
        for index in range(len(starts))
    ]
    scores = _blend_chords(
        starts,
        scores,
        float(parameters["chord_window_ms"]) / 1000.0,
        float(parameters["chord_blend"]),
    )
    scaled = _percentile_scale(scores, low, high)
    spread = max(scores) - min(scores)
    if spread <= float(parameters["minimum_dynamic_spread"]):
        return VelocityAssignment([fallback] * len(starts), True, "uniform_evidence")
    gamma = float(parameters["gamma"])
    velocities = [
        min(max(round(minimum + value**gamma * (maximum - minimum)), 1), 127)
        for value in scaled
    ]
    return VelocityAssignment(velocities, False, None)


def velocity_statistics(values: list[int]) -> dict[str, float | int | None]:
    """Return stable summary statistics for a list of MIDI velocities."""

    if not values:
        return {key: None for key in ("min", "max", "mean", "median", "p05", "p95")}
    ordered = sorted(values)
    return {
        "min": min(values),
        "max": max(values),
        "mean": round(statistics.fmean(values), 4),
        "median": round(float(statistics.median(values)), 4),
        "p05": round(_percentile(ordered, 5.0), 4),
        "p95": round(_percentile(ordered, 95.0), 4),
    }


def _robust_scale(values: list[float], low: float, high: float, gain: float) -> list[float]:
    """Log-compress and percentile-normalize one feature column."""

    compressed = [math.log1p(max(value, 0.0) * gain) for value in values]
    return _percentile_scale(compressed, low, high)


def _percentile_scale(values: list[float], low: float, high: float) -> list[float]:
    """Map a sequence to zero-to-one using interpolated percentile anchors."""

    ordered = sorted(values)
    floor = _percentile(ordered, low)
    ceiling = _percentile(ordered, high)
    if ceiling <= floor + 1e-12:
        return [0.5] * len(values)
    return [min(max((value - floor) / (ceiling - floor), 0.0), 1.0) for value in values]


def _blend_chords(
    starts: list[float], scores: list[float], window: float, blend: float
) -> list[float]:
    """Reduce artificial within-chord contrast without changing note ordering."""

    output = list(scores)
    ordered = sorted(range(len(starts)), key=lambda index: (starts[index], index))
    cursor = 0
    blend = min(max(blend, 0.0), 1.0)
    while cursor < len(ordered):
        group = [ordered[cursor]]
        cursor += 1
        anchor = starts[group[0]]
        while cursor < len(ordered) and starts[ordered[cursor]] - anchor <= window:
            group.append(ordered[cursor])
            cursor += 1
        group_score = statistics.fmean(scores[index] for index in group)
        for index in group:
            output[index] = (1.0 - blend) * scores[index] + blend * group_score
    return output


def _percentile(ordered: list[float] | list[int], percentile: float) -> float:
    """Return a linearly interpolated percentile for an already sorted sequence."""

    if not ordered:
        return 0.0
    position = min(max(percentile, 0.0), 100.0) / 100.0 * (len(ordered) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return float(ordered[lower])
    fraction = position - lower
    return float(ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction)
