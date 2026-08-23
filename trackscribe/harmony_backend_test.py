"""Backend routing, API, manifest, and raw compare contract tests."""

from __future__ import annotations

import inspect
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pipeline
from trackscribe.api import run_pipeline
from trackscribe.harmony_backends import AGNOSTIC_AMT, COMPARE, TRANSKUN
from trackscribe.layout import ProjectLayout
from trackscribe.manifest import ProjectManifest
from trackscribe.modes import COMMON_STAGE_ORDER, stages_for_run
from trackscribe.orchestrator import PipelineOrchestrator
from trackscribe.workers.harmony_compare import export_comparison


class HarmonyBackendTests(unittest.TestCase):
    """Verify explicit backend selection never changes default production behavior."""

    def _orchestrator(self, backend: str) -> PipelineOrchestrator:
        services = SimpleNamespace(executor=SimpleNamespace(set_position=lambda *_args: None))
        manifest = SimpleNamespace(
            data={
                "stages": {
                    "harmony_transcription": {"duration_seconds": 10.0},
                    "harmony_amt_transcription": {"duration_seconds": 20.0},
                }
            },
            finish_run=Mock(),
        )
        return PipelineOrchestrator(
            services, manifest, None, harmony_backend=backend
        )

    def test_default_backend_remains_transkun(self) -> None:
        args = pipeline._build_parser().parse_args(["input.wav", "--output", "out"])
        self.assertEqual(args.harmony_backend, TRANSKUN)

    def test_agnostic_amt_does_not_run_transkun(self) -> None:
        orchestrator = self._orchestrator(AGNOSTIC_AMT)
        velocity = Path("amt-velocity.mid")
        orchestrator._run_amt = Mock(return_value=(Path("amt.mid"), velocity))
        orchestrator._run_transkun = Mock()
        orchestrator._run_cleanup = Mock()
        orchestrator._run_harmony()
        orchestrator._run_amt.assert_called_once_with()
        orchestrator._run_transkun.assert_not_called()
        orchestrator._run_cleanup.assert_called_once_with(velocity)

    def test_compare_runs_both_backends(self) -> None:
        orchestrator = self._orchestrator(COMPARE)
        orchestrator._run_transkun = Mock(return_value=Path("transkun.mid"))
        orchestrator._run_amt = Mock(
            return_value=(Path("amt.mid"), Path("amt-velocity.mid"))
        )
        orchestrator._invoke = Mock()
        orchestrator._run_harmony()
        orchestrator._run_transkun.assert_called_once_with()
        orchestrator._run_amt.assert_called_once_with()

    def test_compare_does_not_invoke_cleanup(self) -> None:
        orchestrator = self._orchestrator(COMPARE)
        orchestrator._run_transkun = Mock(return_value=Path("transkun.mid"))
        orchestrator._run_amt = Mock(
            return_value=(Path("amt.mid"), Path("amt-velocity.mid"))
        )
        orchestrator._run_cleanup = Mock()
        orchestrator._invoke = Mock()
        orchestrator._run_harmony()
        orchestrator._run_cleanup.assert_not_called()

    def test_compare_outputs_are_distinct_raw_copies(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            transkun = root / "transkun.mid"
            amt = root / "amt.mid"
            amt_velocity = root / "amt-velocity.mid"
            transkun.write_bytes(b"transkun-raw")
            amt.write_bytes(b"amt-raw")
            amt_velocity.write_bytes(b"amt-velocity")
            transkun_ab = root / "ab" / "harmony_transkun_raw.mid"
            amt_ab = root / "ab" / "harmony_amt_raw.mid"
            amt_velocity_ab = root / "ab" / "harmony_amt_velocity.mid"
            diagnostics = root / "ab" / "compare.json"
            fake = lambda _path, backend, seconds: {
                "backend": backend,
                "note_count": 1,
                "processing_seconds": seconds,
            }
            with patch(
                "trackscribe.workers.harmony_compare.midi_metrics", fake
            ), patch(
                "trackscribe.workers.harmony_compare.velocity_metrics",
                return_value={"note_count": 1},
            ):
                export_comparison(
                    transkun,
                    amt,
                    amt_velocity,
                    transkun_ab,
                    amt_ab,
                    amt_velocity_ab,
                    diagnostics,
                    1.0,
                    2.0,
                )
            self.assertNotEqual(transkun_ab, amt_ab)
            self.assertEqual(transkun_ab.read_bytes(), transkun.read_bytes())
            self.assertEqual(amt_ab.read_bytes(), amt.read_bytes())
            self.assertEqual(amt_velocity_ab.read_bytes(), amt_velocity.read_bytes())

    def test_compare_diagnostics_are_created_without_ranking(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first, second = root / "one.mid", root / "two.mid"
            processed = root / "processed.mid"
            first.write_bytes(b"one")
            second.write_bytes(b"two")
            processed.write_bytes(b"processed")
            diagnostics = root / "ab" / "compare.json"
            with patch(
                "trackscribe.workers.harmony_compare.midi_metrics",
                side_effect=lambda _path, backend, _seconds: {"backend": backend},
            ), patch(
                "trackscribe.workers.harmony_compare.velocity_metrics",
                return_value={"note_count": 1},
            ):
                export_comparison(
                    first,
                    second,
                    processed,
                    root / "ab" / "first.mid",
                    root / "ab" / "second.mid",
                    root / "ab" / "processed.mid",
                    diagnostics,
                    1.0,
                    2.0,
                )
            report = json.loads(diagnostics.read_text())
            self.assertIn("no automatic ranking", report["purpose"])

    def test_velocity_stage_is_only_in_amt_capable_graphs(self) -> None:
        self.assertNotIn(
            "harmony_amt_velocity", stages_for_run("preserve-harmony", TRANSKUN)
        )
        self.assertIn(
            "harmony_amt_velocity", stages_for_run("preserve-harmony", AGNOSTIC_AMT)
        )
        self.assertIn(
            "harmony_amt_velocity", stages_for_run("preserve-harmony", COMPARE)
        )

    def test_cli_accepts_velocity_force_and_stop_controls(self) -> None:
        args = pipeline._build_parser().parse_args(
            [
                "input.wav",
                "--output",
                "out",
                "--harmony-backend",
                AGNOSTIC_AMT,
                "--force-stage",
                "harmony_amt_velocity",
                "--stop-after",
                "harmony_amt_velocity",
            ]
        )
        self.assertEqual(args.force_stage, ["harmony_amt_velocity"])
        self.assertEqual(args.stop_after, "harmony_amt_velocity")

    def test_common_stages_are_identical_for_all_backends(self) -> None:
        for backend in (TRANSKUN, AGNOSTIC_AMT, COMPARE):
            self.assertEqual(
                stages_for_run("preserve-harmony", backend)[: len(COMMON_STAGE_ORDER)],
                COMMON_STAGE_ORDER,
            )

    def test_manifest_records_selected_backend(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.wav"
            source.write_bytes(b"audio")
            layout = ProjectLayout.create(root / "project")
            manifest = ProjectManifest(
                layout, source, {}, harmony_backend=COMPARE
            )
            self.assertEqual(manifest.data["harmony_backend"], COMPARE)

    def test_python_api_accepts_harmony_backend(self) -> None:
        parameter = inspect.signature(run_pipeline).parameters["harmony_backend"]
        self.assertEqual(parameter.default, TRANSKUN)


if __name__ == "__main__":
    unittest.main()
