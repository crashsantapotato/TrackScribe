"""Stage lifecycle and cache tests for AMT harmony velocity processing."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from trackscribe.errors import ProcessError
from trackscribe.executor import StageExecutor
from trackscribe.layout import ProjectLayout
from trackscribe.manifest import ProjectManifest
from trackscribe.stages import harmony_velocity
from trackscribe.stages.base import StageServices
from trackscribe.types import StageOutcome


class FakeConfig:
    """Minimal configuration used to exercise the real stage adapter."""

    def __init__(self, version: str = "test-v1") -> None:
        self.parameters = {"algorithm_version": version, "enabled": True}

    def section(self, _name: str) -> dict:
        """Return a defensive parameter copy."""

        return dict(self.parameters)

    def python(self, _name: str) -> Path:
        """Use the unit-test interpreter as a command placeholder."""

        return Path(sys.executable)


class HarmonyVelocityStageTests(unittest.TestCase):
    """Verify manifest metadata, failure persistence, and downstream invalidation."""

    def test_success_records_statistics_and_outputs(self) -> None:
        services, manifest, audio, raw = self._services()

        def complete(_self, _stage, command, **_kwargs) -> None:
            Path(command[5]).write_bytes(b"processed-midi")
            Path(command[6]).write_text(json.dumps(_report()), encoding="utf-8")

        with patch.object(StageServices, "run_command", new=complete):
            result = harmony_velocity.add_velocity(
                services, audio=audio, raw_midi=raw
            )
        stage = manifest.data["stages"]["harmony_amt_velocity"]
        self.assertEqual(stage["status"], "completed")
        self.assertEqual(stage["metadata"]["changed_velocities"], 2)
        self.assertTrue(result.outputs["midi.harmony_amt_velocity"].is_file())

    def test_failure_is_persisted_in_manifest_and_lifecycle_log(self) -> None:
        services, manifest, audio, raw = self._services()
        manifest.start_run()

        def fail(_self, _stage, _command, **_kwargs) -> None:
            raise ProcessError(["worker"], 9, "velocity-worker.log")

        with patch.object(StageServices, "run_command", new=fail):
            with self.assertRaises(ProcessError):
                harmony_velocity.add_velocity(services, audio=audio, raw_midi=raw)
        stage = manifest.data["stages"]["harmony_amt_velocity"]
        log = services.layout.logs / "harmony_amt_velocity.log"
        self.assertEqual(stage["status"], "failed")
        self.assertIn("exit code 9", log.read_text(encoding="utf-8"))

    def test_parameter_change_reruns_velocity_and_downstream_only(self) -> None:
        services, _manifest, audio, raw = self._services()
        calls = {"amt": 0, "velocity": 0, "cleanup": 0}
        velocity = services.layout.midi / "harmony_amt_velocity.mid"
        final = services.layout.midi / "harmony.mid"

        def run(version: int) -> None:
            self._cached_stage(
                services.executor, "amt", [audio], raw, {}, calls, b"raw-midi"
            )
            self._cached_stage(
                services.executor,
                "velocity",
                [audio, raw],
                velocity,
                {"version": version},
                calls,
                f"velocity-{version}".encode(),
            )
            self._cached_stage(
                services.executor, "cleanup", [velocity], final, {}, calls, b"final"
            )

        run(1)
        run(1)
        run(2)
        self.assertEqual(calls, {"amt": 1, "velocity": 2, "cleanup": 2})

    def _services(self) -> tuple[StageServices, ProjectManifest, Path, Path]:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        source = root / "source.wav"
        source.write_bytes(b"source")
        layout = ProjectLayout.create(root / "project")
        audio = layout.stems / "other.wav"
        raw = layout.midi / "harmony_amt_raw.mid"
        audio.write_bytes(b"audio")
        raw.write_bytes(b"raw")
        manifest = ProjectManifest(layout, source, {})
        executor = StageExecutor(layout, manifest, None, set())
        return StageServices(FakeConfig(), layout, executor, root), manifest, audio, raw

    @staticmethod
    def _cached_stage(executor, name, inputs, output, parameters, calls, content) -> None:
        """Execute one synthetic cached stage with deterministic output content."""

        def action() -> StageOutcome:
            calls[name] += 1
            output.write_bytes(content)
            return StageOutcome({f"midi.{name}": output})

        executor.execute(
            name, inputs=inputs, model={}, parameters=parameters, action=action
        )


def _report() -> dict:
    """Return the diagnostic contract consumed by the stage adapter."""

    return {
        "algorithm_version": "test-v1",
        "input_notes": 2,
        "output_notes": 2,
        "changed_velocities": 2,
        "unchanged_velocities": 0,
        "structure_preserved": True,
        "fallback": False,
        "fallback_reason": None,
        "warnings": [],
        "velocity_before": {"min": 100, "max": 100},
        "velocity_after": {"min": 50, "max": 110},
    }


if __name__ == "__main__":
    unittest.main()
