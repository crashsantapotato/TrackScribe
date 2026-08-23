"""Contract tests for the JSONL external-process bridge."""

from __future__ import annotations

import io
import json
import unittest
from argparse import Namespace
from pathlib import Path
from tempfile import TemporaryDirectory

from trackscribe.bridge import _parser, run_bridge
from trackscribe.config import DEFAULT_CONFIG_PATH
from trackscribe.harmony_backends import AGNOSTIC_AMT
from trackscribe.modes import PRESERVE_HARMONY
from trackscribe.types import PipelineResult, ProgressEvent


class BridgeTest(unittest.TestCase):
    def test_integration_defaults_use_preserve_harmony_and_agnostic_amt(self) -> None:
        args = _parser().parse_args(["--input", "input.wav", "--output", "project"])
        self.assertEqual(args.mode, "preserve-harmony")
        self.assertEqual(args.harmony_backend, "agnostic-amt")

    def _args(self, root: Path) -> Namespace:
        return Namespace(
            input=root / "input.wav",
            output=root / "project",
            config=DEFAULT_CONFIG_PATH,
            mode=PRESERVE_HARMONY,
            harmony_backend=AGNOSTIC_AMT,
        )

    def test_bridge_forwards_defaults_and_serializes_progress(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            captured = {}
            stream = io.StringIO()

            def runner(**kwargs):
                captured.update(kwargs)
                kwargs["progress_callback"](
                    ProgressEvent("prepare_master", "started", "started", 0.0)
                )
                project = root / "project"
                return PipelineResult(project, project / "project.json", "completed", {})

            self.assertEqual(run_bridge(self._args(root), runner=runner, stream=stream), 0)
            events = [json.loads(line) for line in stream.getvalue().splitlines()]
            self.assertEqual(captured["mode"], PRESERVE_HARMONY)
            self.assertEqual(captured["harmony_backend"], AGNOSTIC_AMT)
            self.assertEqual(events[0]["type"], "stage")
            self.assertEqual(events[0]["current"], 1)
            self.assertGreater(events[0]["total"], 1)
            self.assertEqual(events[-1]["type"], "completed")

    def test_failure_is_one_json_error_with_last_stage(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            stream = io.StringIO()

            def runner(**kwargs):
                kwargs["progress_callback"](
                    ProgressEvent("core_separation", "started", "started", 0.1)
                )
                raise RuntimeError("synthetic failure")

            self.assertEqual(run_bridge(self._args(root), runner=runner, stream=stream), 1)
            events = [json.loads(line) for line in stream.getvalue().splitlines()]
            self.assertEqual(events[-1]["type"], "error")
            self.assertEqual(events[-1]["stage"], "core_separation")
            self.assertIn("synthetic failure", events[-1]["message"])

    def test_bridge_module_has_no_ace_import(self) -> None:
        source = Path(__file__).parents[1] / "trackscribe" / "bridge.py"
        self.assertNotIn("acestep", source.read_text(encoding="utf-8").lower())


if __name__ == "__main__":
    unittest.main()
