"""Tests for virtual-environment entrypoints after project root relocation."""

from __future__ import annotations

import unittest
from pathlib import Path

from trackscribe.config import DEFAULT_CONFIG_PATH
from trackscribe.stages.base import StageServices


class FakeConfig:
    """Return one deterministic relocated Python path."""

    def python(self, name: str) -> Path:
        """Resolve a synthetic venv interpreter for command construction."""

        return Path("relocated") / name / "python.exe"


class RelocationTests(unittest.TestCase):
    """Ensure entrypoints and final project root remain relocation-safe."""

    def test_entrypoint_uses_venv_python_and_module_main(self) -> None:
        services = StageServices(FakeConfig(), None, None, Path("repository"))
        self.assertEqual(
            services.entrypoint("main", "package.cli"),
            [
                str(Path("relocated") / "main" / "python.exe"),
                "-c",
                "from package.cli import main; main()",
            ],
        )

    def test_runtime_root_does_not_use_historical_typo(self) -> None:
        paths = (Path(__file__).resolve(), DEFAULT_CONFIG_PATH.resolve())
        self.assertTrue(all("AudioPipline" not in str(path) for path in paths))


if __name__ == "__main__":
    unittest.main()
