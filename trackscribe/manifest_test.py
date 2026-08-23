"""Focused tests for project manifest persistence and stage cache invalidation."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from trackscribe.executor import StageExecutor
from trackscribe.layout import ProjectLayout
from trackscribe.manifest import ProjectManifest
from trackscribe.types import ProgressEvent, StageOutcome


class StageCacheTests(unittest.TestCase):
    """Verify successful reuse, mutation invalidation, and progress contracts."""

    def test_completed_stage_is_reused_until_an_input_changes(self) -> None:
        """A matching fingerprint and existing output should prevent repeated work."""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.wav"
            source.write_bytes(b"first")
            layout = ProjectLayout.create(root / "project")
            manifest = ProjectManifest(layout, source, {"fingerprint": "config"})
            events: list[ProgressEvent] = []
            executor = StageExecutor(layout, manifest, events.append, set())
            executor.set_position("example", 0, 1)
            output = layout.root / "result.bin"
            calls = 0

            def action() -> StageOutcome:
                nonlocal calls
                calls += 1
                output.write_bytes(f"run-{calls}".encode())
                return StageOutcome(outputs={"result": output})

            first = executor.execute(
                "example", inputs=[source], model={}, parameters={"value": 1}, action=action
            )
            second = executor.execute(
                "example", inputs=[source], model={}, parameters={"value": 1}, action=action
            )
            self.assertEqual(calls, 1)
            self.assertEqual(first.outputs, second.outputs)
            self.assertIn("cached", [event.status for event in events])

            source.write_bytes(b"changed-input")
            executor.execute(
                "example", inputs=[source], model={}, parameters={"value": 1}, action=action
            )
            self.assertEqual(calls, 2)
            self.assertEqual(manifest.data["stages"]["example"]["attempts"], 2)

    def test_missing_cached_output_forces_stage_to_run_again(self) -> None:
        """A manifest record alone must never count as a valid cache hit."""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.wav"
            source.write_bytes(b"audio")
            layout = ProjectLayout.create(root / "project")
            manifest = ProjectManifest(layout, source, {})
            executor = StageExecutor(layout, manifest, None, set())
            output = layout.root / "result.bin"
            calls = 0

            def action() -> StageOutcome:
                nonlocal calls
                calls += 1
                output.write_bytes(b"result")
                return StageOutcome(outputs={"result": output})

            arguments = {
                "inputs": [source],
                "model": {},
                "parameters": {},
                "action": action,
            }
            executor.execute("example", **arguments)
            output.unlink()
            executor.execute("example", **arguments)
            self.assertEqual(calls, 2)
            self.assertIn("result", manifest.public_outputs())
            executor.skip("example", "no longer selected", {"classification": "IGNORE"})
            self.assertNotIn("result", manifest.public_outputs())


if __name__ == "__main__":
    unittest.main()
