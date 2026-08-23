"""Tests for harmony-preserving mode selection and mode-aware resume behavior."""

from __future__ import annotations

import inspect
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pipeline
from trackscribe.api import run_pipeline
from trackscribe.executor import StageExecutor
from trackscribe.layout import ProjectLayout
from trackscribe.manifest import ProjectManifest
from trackscribe.modes import (
    DETAILED_STEMS,
    DETAILED_STEMS_STAGE_ORDER,
    PRESERVE_HARMONY,
)
from trackscribe.orchestrator import PipelineOrchestrator
from trackscribe.types import StageOutcome


class PipelineModeTests(unittest.TestCase):
    """Cover CLI/API defaults, routing, cache isolation, and manifest compatibility."""

    def _orchestrator(self, mode: str = PRESERVE_HARMONY) -> PipelineOrchestrator:
        executor = SimpleNamespace(set_position=lambda *_args: None)
        services = SimpleNamespace(executor=executor)
        manifest = SimpleNamespace(data={}, finish_run=Mock())
        return PipelineOrchestrator(services, manifest, None, mode=mode)

    def test_default_mode_is_preserve_harmony(self) -> None:
        args = pipeline._build_parser().parse_args(["input.wav", "--output", "out"])
        self.assertEqual(args.mode, PRESERVE_HARMONY)

    def test_default_mode_runs_harmony_transcription(self) -> None:
        orchestrator = self._orchestrator()
        orchestrator._run_common = Mock()
        orchestrator._run_harmony = Mock()
        orchestrator._run_detailed = Mock()
        self.assertEqual(orchestrator.run(Path("input.wav")), "completed")
        orchestrator._run_harmony.assert_called_once_with()

    def test_default_mode_does_not_run_mega53_branch(self) -> None:
        orchestrator = self._orchestrator()
        orchestrator._run_common = Mock()
        orchestrator._run_harmony = Mock()
        orchestrator._run_detailed = Mock()
        orchestrator.run(Path("input.wav"))
        orchestrator._run_detailed.assert_not_called()

    def test_detailed_stems_preserves_old_branch(self) -> None:
        orchestrator = self._orchestrator(DETAILED_STEMS)
        orchestrator._run_common = Mock()
        orchestrator._run_harmony = Mock()
        orchestrator._run_detailed = Mock()
        orchestrator.run(Path("input.wav"))
        orchestrator._run_detailed.assert_called_once_with()
        orchestrator._run_harmony.assert_not_called()
        self.assertEqual(orchestrator.stage_order, DETAILED_STEMS_STAGE_ORDER)

    def test_cache_distinguishes_mode_context(self) -> None:
        calls, executor, source, output = self._cache_fixture()

        def action() -> StageOutcome:
            calls.append(1)
            output.write_bytes(b"midi")
            return StageOutcome(outputs={"midi.harmony": output})

        kwargs = dict(inputs=[source], model={}, parameters={}, action=action)
        executor.execute("harmony_transcription", cache_context={"mode": "a"}, **kwargs)
        executor.execute("harmony_transcription", cache_context={"mode": "a"}, **kwargs)
        executor.execute("harmony_transcription", cache_context={"mode": "b"}, **kwargs)
        self.assertEqual(len(calls), 2)

    def test_stop_after_harmony_transcription(self) -> None:
        orchestrator = self._orchestrator()
        orchestrator.stop_after = "harmony_transcription"
        orchestrator._run_common = Mock()
        orchestrator._run_harmony = lambda: orchestrator._invoke(
            "harmony_transcription", lambda: None
        )
        self.assertEqual(orchestrator.run(Path("input.wav")), "partial")
        orchestrator.manifest.finish_run.assert_called_once_with("partial")

    def test_force_stage_harmony_transcription(self) -> None:
        calls, executor, source, output = self._cache_fixture()

        def action() -> StageOutcome:
            calls.append(1)
            output.write_bytes(b"midi")
            return StageOutcome(outputs={"midi.harmony": output})

        kwargs = dict(inputs=[source], model={}, parameters={}, action=action)
        executor.execute("harmony_transcription", **kwargs)
        executor.force_stages.add("harmony_transcription")
        executor.execute("harmony_transcription", **kwargs)
        self.assertEqual(len(calls), 2)

    def test_manifest_updates_atomically_and_loads_legacy_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.wav"
            source.write_bytes(b"audio")
            layout = ProjectLayout.create(root / "project")
            ProjectManifest(layout, source, {})
            data = json.loads(layout.manifest.read_text(encoding="utf-8"))
            self.assertFalse(layout.manifest.with_suffix(".json.tmp").exists())
            data.pop("pipeline_mode", None)
            layout.manifest.write_text(json.dumps(data), encoding="utf-8")
            loaded = ProjectManifest(
                layout,
                source,
                {},
                pipeline_mode=PRESERVE_HARMONY,
                active_stages={"prepare_master"},
            )
            self.assertEqual(loaded.data["pipeline_mode"], PRESERVE_HARMONY)

    def test_repeated_run_uses_cache(self) -> None:
        calls, executor, source, output = self._cache_fixture()

        def action() -> StageOutcome:
            calls.append(1)
            output.write_bytes(b"midi")
            return StageOutcome(outputs={"midi.harmony": output})

        kwargs = dict(inputs=[source], model={}, parameters={}, action=action)
        executor.execute("harmony_transcription", **kwargs)
        executor.execute("harmony_transcription", **kwargs)
        self.assertEqual(len(calls), 1)

    def test_python_api_accepts_mode(self) -> None:
        parameter = inspect.signature(run_pipeline).parameters["mode"]
        self.assertEqual(parameter.default, PRESERVE_HARMONY)

    def test_cli_accepts_cleanup_controls(self) -> None:
        args = pipeline._build_parser().parse_args(
            [
                "input.wav",
                "--output",
                "out",
                "--force-stage",
                "harmony_cleanup",
                "--stop-after",
                "harmony_cleanup",
                "--no-harmony-cleanup",
            ]
        )
        self.assertEqual(args.force_stage, ["harmony_cleanup"])
        self.assertEqual(args.stop_after, "harmony_cleanup")
        self.assertTrue(args.no_harmony_cleanup)

    def _cache_fixture(self) -> tuple[list[int], StageExecutor, Path, Path]:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        source = root / "source.wav"
        source.write_bytes(b"audio")
        layout = ProjectLayout.create(root / "project")
        manifest = ProjectManifest(layout, source, {})
        executor = StageExecutor(layout, manifest, None, set())
        return [], executor, source, layout.midi / "harmony.mid"


if __name__ == "__main__":
    unittest.main()
