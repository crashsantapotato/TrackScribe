"""Unit tests for deterministic harmony velocity normalization."""

from __future__ import annotations

import unittest

from trackscribe.harmony_velocity_logic import (
    VelocityFeature,
    assign_velocities,
    velocity_statistics,
)


PARAMETERS = {
    "min_velocity": 45,
    "max_velocity": 118,
    "fallback_velocity": 100,
    "gamma": 0.85,
    "percentile_low": 10.0,
    "percentile_high": 95.0,
    "log_gain": 100.0,
    "attack_weight": 0.5,
    "sustain_weight": 0.3,
    "onset_weight": 0.2,
    "chord_window_ms": 35.0,
    "chord_blend": 0.65,
    "minimum_dynamic_spread": 0.00001,
}


class HarmonyVelocityLogicTests(unittest.TestCase):
    """Verify bounds, dynamics, chord stability, fallback, and determinism."""

    def test_uneven_evidence_produces_bounded_non_uniform_velocities(self) -> None:
        features = [
            VelocityFeature(0.01, 0.01, 0.1),
            VelocityFeature(0.10, 0.06, 0.8),
            VelocityFeature(0.50, 0.30, 2.0),
        ]
        result = assign_velocities([0.0, 1.0, 2.0], features, PARAMETERS)
        self.assertFalse(result.fallback)
        self.assertGreater(len(set(result.velocities)), 1)
        self.assertGreaterEqual(min(result.velocities), PARAMETERS["min_velocity"])
        self.assertLessEqual(max(result.velocities), PARAMETERS["max_velocity"])

    def test_stronger_onset_is_not_quieter_when_other_features_match(self) -> None:
        features = [
            VelocityFeature(0.2, 0.2, 0.1),
            VelocityFeature(0.2, 0.2, 2.0),
            VelocityFeature(0.2, 0.2, 0.5),
        ]
        result = assign_velocities([0.0, 1.0, 2.0], features, PARAMETERS)
        self.assertGreaterEqual(result.velocities[1], result.velocities[0])

    def test_full_chord_blend_gives_simultaneous_notes_one_dynamic_level(self) -> None:
        parameters = {**PARAMETERS, "chord_blend": 1.0}
        features = [
            VelocityFeature(0.01, 0.01, 0.1),
            VelocityFeature(0.8, 0.5, 2.0),
            VelocityFeature(0.2, 0.2, 0.5),
            VelocityFeature(0.4, 0.3, 1.0),
        ]
        result = assign_velocities([0.0, 0.01, 1.0, 2.0], features, parameters)
        self.assertEqual(result.velocities[0], result.velocities[1])

    def test_silence_uses_configured_fallback(self) -> None:
        features = [VelocityFeature(0.0, 0.0, 0.0)] * 3
        result = assign_velocities(
            [0.0, 1.0, 2.0], features, PARAMETERS, audio_silent=True
        )
        self.assertTrue(result.fallback)
        self.assertEqual(result.fallback_reason, "silent_audio")
        self.assertEqual(result.velocities, [100, 100, 100])

    def test_uniform_evidence_uses_safe_fallback(self) -> None:
        features = [VelocityFeature(0.2, 0.2, 0.2)] * 3
        result = assign_velocities([0.0, 1.0, 2.0], features, PARAMETERS)
        self.assertEqual(result.fallback_reason, "uniform_evidence")
        self.assertEqual(result.velocities, [100, 100, 100])

    def test_results_are_deterministic(self) -> None:
        features = [
            VelocityFeature(0.1, 0.2, 0.3),
            VelocityFeature(0.4, 0.5, 0.6),
            VelocityFeature(0.2, 0.3, 0.4),
        ]
        first = assign_velocities([0.0, 1.0, 2.0], features, PARAMETERS)
        second = assign_velocities([0.0, 1.0, 2.0], features, PARAMETERS)
        self.assertEqual(first, second)

    def test_velocity_statistics_cover_empty_and_populated_lists(self) -> None:
        self.assertIsNone(velocity_statistics([])["mean"])
        stats = velocity_statistics([20, 40, 60, 80, 100])
        self.assertEqual(stats["min"], 20)
        self.assertEqual(stats["median"], 60.0)


if __name__ == "__main__":
    unittest.main()
