"""Static portability checks for the Windows bootstrap contract."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class BootstrapContractTest(unittest.TestCase):
    """Guard the no-system-Python and root-relative setup workflow."""

    def test_bootstrap_entrypoints_exist(self) -> None:
        for relative in ("setup.bat", "run.bat", "scripts/bootstrap.ps1"):
            with self.subTest(relative=relative):
                self.assertTrue((PROJECT_ROOT / relative).is_file())

    def test_run_bat_uses_only_isolated_ui_python(self) -> None:
        content = (PROJECT_ROOT / "run.bat").read_text(encoding="utf-8").lower()
        self.assertIn(r"%~dp0", content)
        self.assertIn(r".venv-ui\scripts\pythonw.exe", content)
        self.assertNotIn(r"\python.exe", content)
        self.assertIn("run setup.bat first", content)

    def test_setup_launcher_is_root_relative_and_does_not_call_python(self) -> None:
        content = (PROJECT_ROOT / "setup.bat").read_text(encoding="utf-8").lower()
        self.assertIn(r"%~dp0", content)
        self.assertIn(r"scripts\bootstrap.ps1", content)
        self.assertIn("executionpolicy bypass", content)
        self.assertNotIn("python.exe", content)

    def test_bootstrap_pins_verified_runtime_and_all_environments(self) -> None:
        content = (PROJECT_ROOT / "scripts" / "bootstrap.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn('$UvVersion = "0.12.5"', content)
        self.assertIn('$PythonVersion = "3.12.14"', content)
        self.assertIn('$FfmpegVersion = "8.1.2"', content)
        self.assertIn("Assert-FileSha256", content)
        self.assertIn("$UvArchiveSha256", content)
        self.assertIn("$AmtArchiveSha256", content)
        self.assertIn("$FfmpegArchiveSha256", content)
        self.assertIn("$PSScriptRoot", content)
        self.assertIn("UV_PYTHON_INSTALL_DIR", content)
        self.assertIn("-DryRun", (PROJECT_ROOT / "README.md").read_text(encoding="utf-8"))
        for environment in (
            ".venv",
            ".venv-ui",
            ".venv-bass",
            ".venv-piano",
            ".venv-mega",
            ".venv-amt",
        ):
            self.assertIn(f'Directory = "{environment}"', content)
        self.assertNotIn("F:/AI/TrackScribe", content)
        self.assertNotIn("C:/Users/Anton", content)
        self.assertIn('"audio-separator" = "0.44.5"', content)
        self.assertIn('"PySide6" = "6.11.2"', content)
        self.assertIn('"torch" = "2.13.0+cu130"', content)

    def test_public_version_has_single_source_of_truth(self) -> None:
        import trackscribe

        self.assertEqual(trackscribe.__version__, "0.1.0")

    def test_default_config_contains_only_portable_paths(self) -> None:
        config_path = PROJECT_ROOT / "config" / "trackscribe.json"
        raw_text = config_path.read_text(encoding="utf-8")
        raw = json.loads(raw_text)
        self.assertNotIn("F:/AI/TrackScribe", raw_text)
        self.assertNotIn("C:/Users/Anton", raw_text)
        for path in raw["venvs"].values():
            self.assertFalse(Path(path).is_absolute(), path)

    def test_core_import_does_not_load_qt_or_bootstrap(self) -> None:
        code = (
            "import sys, trackscribe; "
            "assert not any(name == 'PySide6' or name.startswith('PySide6.') "
            "for name in sys.modules); "
            "assert 'trackscribe.ui' not in sys.modules"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
