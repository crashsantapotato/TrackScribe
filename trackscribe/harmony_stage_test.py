"""Stage graph, manifest, and cache tests for harmony cleanup integration."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from trackscribe.executor import StageExecutor
from trackscribe.layout import ProjectLayout
from trackscribe.manifest import ProjectManifest
from trackscribe.orchestrator import PipelineOrchestrator
from trackscribe.stages import harmony
from trackscribe.types import StageOutcome


PARAMETERS = {
    "enabled": True,
    "mode": "conservative",
    "audio_validation": True,
    "min_note_duration_ms": 35,
    "merge_same_pitch_gap_ms": 30,
    "chord_window_ms": 40,
    "pitch_support_threshold": 0.08,
    "neighbor_support_threshold": 0.08,
    "chord_pitch_support_threshold": 0.03,
    "chord_neighbor_support_threshold": 0.04,
    "onset_support_threshold": 0.18,
}


class HarmonyStageTests(unittest.TestCase):
    """Verify raw/final contracts and isolated cleanup invalidation."""

    def test_harmony_transcription_targets_raw_midi(self) -> None:
        layout = SimpleNamespace(stems=Path("stems"), midi=Path("midi"))
        services = SimpleNamespace(
            layout=layout, executor=SimpleNamespace(set_position=lambda *_args: None)
        )
        manifest = SimpleNamespace(data={}, finish_run=Mock())
        orchestrator = PipelineOrchestrator(services, manifest, None)
        raw = layout.midi / "harmony_raw.mid"
        with patch("trackscribe.orchestrator.transkun.transcribe") as transcribe:
            with patch("trackscribe.orchestrator.harmony.cleanup") as cleanup:
                transcribe.return_value = StageOutcome({"midi.harmony_raw": raw})
                orchestrator._run_harmony()
        self.assertEqual(transcribe.call_args.kwargs["output"], raw)
        self.assertEqual(cleanup.call_args.kwargs["raw_midi"], raw)

    def test_cleanup_stage_creates_final_midi_output(self) -> None:
        outcome, _manifest, layout = self._run_cleanup_stage()
        self.assertEqual(outcome.outputs["midi.harmony"], layout.midi / "harmony.mid")
        self.assertTrue(outcome.outputs["midi.harmony"].is_file())

    def test_cleanup_stage_creates_diagnostic_json(self) -> None:
        outcome, _manifest, _layout = self._run_cleanup_stage()
        diagnostic = outcome.outputs["diagnostics.harmony_cleanup"]
        self.assertEqual(json.loads(diagnostic.read_text())["input_notes"], 12)

    def test_manifest_contains_cleanup_parameters_and_statistics(self) -> None:
        _outcome, manifest, _layout = self._run_cleanup_stage()
        stage = manifest.data["stages"]["harmony_cleanup"]
        self.assertEqual(stage["parameters"]["min_note_duration_ms"], 35)
        self.assertEqual(stage["metadata"]["statistics"]["output_notes"], 10)

    def _run_cleanup_stage(self) -> tuple[StageOutcome, ProjectManifest, ProjectLayout]:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        source = root / "source.wav"
        source.write_bytes(b"source")
        layout = ProjectLayout.create(root / "project")
        audio = layout.stems / "other.wav"
        raw = layout.midi / "harmony_raw.mid"
        audio.write_bytes(b"audio")
        raw.write_bytes(b"raw")
        manifest = ProjectManifest(layout, source, {})
        executor = StageExecutor(layout, manifest, None, set())
        config = SimpleNamespace(
            section=lambda _name: dict(PARAMETERS),
            python=lambda _name: Path(sys.executable),
        )
        services = SimpleNamespace(config=config, layout=layout, executor=executor)

        def run_command(_stage: str, command: list[str]) -> None:
            Path(command[5]).write_bytes(b"clean")
            report = {
                "input_notes": 12,
                "output_notes": 10,
                "removed": {"short_and_unsupported": 2},
                "removed_total": 2,
                "merged_retriggers": 0,
                "duration_seconds": 0.1,
            }
            Path(command[6]).write_text(json.dumps(report), encoding="utf-8")

        services.run_command = run_command
        return harmony.cleanup(services, audio=audio, raw_midi=raw), manifest, layout

if __name__ == "__main__":
    unittest.main()
