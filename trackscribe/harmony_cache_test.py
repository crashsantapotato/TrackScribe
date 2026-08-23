"""Cache boundary tests for raw harmony transcription and cleanup tuning."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from trackscribe.executor import StageExecutor
from trackscribe.layout import ProjectLayout
from trackscribe.manifest import ProjectManifest
from trackscribe.types import StageOutcome


class HarmonyCacheTests(unittest.TestCase):
    """Ensure tuning and forced cleanup never invalidate Transkun raw output."""

    def test_cleanup_config_change_does_not_invalidate_raw_stage(self) -> None:
        calls, executor, source, raw, final = self._fixture()
        self._execute_pair(executor, source, raw, final, calls, 35)
        self._execute_pair(executor, source, raw, final, calls, 25)
        self.assertEqual(calls, {"raw": 1, "cleanup": 2})

    def test_forcing_cleanup_does_not_rerun_transcription(self) -> None:
        calls, executor, source, raw, final = self._fixture()
        self._execute_pair(executor, source, raw, final, calls, 35)
        executor.force_stages.add("harmony_cleanup")
        self._execute_pair(executor, source, raw, final, calls, 35)
        self.assertEqual(calls, {"raw": 1, "cleanup": 2})

    def _fixture(self) -> tuple[dict[str, int], StageExecutor, Path, Path, Path]:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        source = root / "source.wav"
        source.write_bytes(b"audio")
        layout = ProjectLayout.create(root / "project")
        manifest = ProjectManifest(layout, source, {})
        return (
            {"raw": 0, "cleanup": 0},
            StageExecutor(layout, manifest, None, set()),
            source,
            layout.midi / "harmony_raw.mid",
            layout.midi / "harmony.mid",
        )

    @staticmethod
    def _execute_pair(
        executor: StageExecutor,
        source: Path,
        raw: Path,
        final: Path,
        calls: dict[str, int],
        minimum_ms: int,
    ) -> None:
        """Execute both fingerprints with small deterministic output actions."""

        def raw_action() -> StageOutcome:
            calls["raw"] += 1
            raw.write_bytes(b"raw")
            return StageOutcome({"midi.harmony_raw": raw})

        def cleanup_action() -> StageOutcome:
            calls["cleanup"] += 1
            final.write_bytes(str(minimum_ms).encode())
            return StageOutcome({"midi.harmony": final})

        executor.execute(
            "harmony_transcription",
            inputs=[source],
            model={"name": "Transkun"},
            parameters={},
            cache_context={"output_contract": "harmony-raw-v1"},
            action=raw_action,
        )
        executor.execute(
            "harmony_cleanup",
            inputs=[source, raw],
            model={"name": "cleanup"},
            parameters={"min_note_duration_ms": minimum_ms},
            action=cleanup_action,
        )


if __name__ == "__main__":
    unittest.main()
