"""Cache and failure-provenance tests for the external AMT adapter."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from trackscribe.errors import ProcessError
from trackscribe.executor import StageExecutor
from trackscribe.layout import ProjectLayout
from trackscribe.manifest import ProjectManifest
from trackscribe.stages import agnostic_amt
from trackscribe.stages.base import StageServices
from trackscribe.types import StageOutcome


class FakeConfig:
    """Minimal external backend configuration for process-failure testing."""

    def __init__(self, repo_dir: Path) -> None:
        self.repo_dir = repo_dir

    def section(self, _name: str) -> dict:
        """Return valid AMT parameters pointing at the fake checkout."""

        return {
            "enabled": True,
            "repo_dir": str(self.repo_dir),
            "repo_revision": "test",
            "model_type": "other",
            "checkpoint": None,
            "checkpoint_filename": "best_model_other.pth",
            "device": "cuda",
            "amp": True,
            "window_batch_size": 1,
            "max_midi_melodic_instruments": 1,
        }

    def resolve_path(self, value: str) -> Path:
        """Resolve the fake repository path."""

        return Path(value).resolve()

    def python(self, _name: str) -> Path:
        """Use the unit-test interpreter for the deliberately failing script."""

        return Path(sys.executable)


class AgnosticAmtTests(unittest.TestCase):
    """Verify isolated invalidation, forcing, and external process diagnostics."""

    def test_amt_config_change_invalidates_only_amt_stage(self) -> None:
        calls, executor, source, common, amt = self._cache_fixture()
        self._execute_pair(executor, source, common, amt, calls, 1)
        self._execute_pair(executor, source, common, amt, calls, 2)
        self.assertEqual(calls, {"common": 1, "amt": 2})

    def test_force_amt_stage_reruns_only_amt(self) -> None:
        calls, executor, source, common, amt = self._cache_fixture()
        self._execute_pair(executor, source, common, amt, calls, 1)
        executor.force_stages.add("harmony_amt_transcription")
        self._execute_pair(executor, source, common, amt, calls, 1)
        self.assertEqual(calls, {"common": 1, "amt": 2})

    def test_external_failure_is_recorded_in_manifest_and_log(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / "tool"
            repo.mkdir()
            (repo / "infer.py").write_text(
                "print('deliberate amt failure')\nraise SystemExit(7)\n",
                encoding="utf-8",
            )
            source = root / "source.wav"
            source.write_bytes(b"source")
            layout = ProjectLayout.create(root / "project")
            audio = layout.stems / "other.wav"
            audio.write_bytes(b"audio")
            manifest = ProjectManifest(layout, source, {}, harmony_backend="agnostic-amt")
            manifest.start_run()
            executor = StageExecutor(layout, manifest, None, set())
            services = StageServices(FakeConfig(repo), layout, executor, root)
            with self.assertRaises(ProcessError):
                agnostic_amt.transcribe(services, audio)
            stage = manifest.data["stages"]["harmony_amt_transcription"]
            log = layout.logs / "harmony_amt_transcription.log"
            self.assertEqual(stage["status"], "failed")
            self.assertIn("deliberate amt failure", log.read_text())

    def _cache_fixture(
        self,
    ) -> tuple[dict[str, int], StageExecutor, Path, Path, Path]:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        source = root / "source.wav"
        source.write_bytes(b"audio")
        layout = ProjectLayout.create(root / "project")
        manifest = ProjectManifest(layout, source, {})
        return (
            {"common": 0, "amt": 0},
            StageExecutor(layout, manifest, None, set()),
            source,
            layout.stems / "other.wav",
            layout.midi / "harmony_amt_raw.mid",
        )

    @staticmethod
    def _execute_pair(
        executor: StageExecutor,
        source: Path,
        common: Path,
        amt: Path,
        calls: dict[str, int],
        window_batch_size: int,
    ) -> None:
        """Execute a common stage and an AMT stage with independent parameters."""

        def common_action() -> StageOutcome:
            calls["common"] += 1
            common.write_bytes(b"other")
            return StageOutcome({"stems.other": common})

        def amt_action() -> StageOutcome:
            calls["amt"] += 1
            amt.write_bytes(str(window_batch_size).encode())
            return StageOutcome({"midi.harmony_amt_raw": amt})

        executor.execute(
            "core_separation",
            inputs=[source],
            model={},
            parameters={},
            action=common_action,
        )
        executor.execute(
            "harmony_amt_transcription",
            inputs=[common],
            model={"name": "amt"},
            parameters={"window_batch_size": window_batch_size},
            action=amt_action,
        )


if __name__ == "__main__":
    unittest.main()
