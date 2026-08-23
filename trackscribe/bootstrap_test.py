"""Static portability checks for the Windows bootstrap contract."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class BootstrapContractTest(unittest.TestCase):
    """Guard the no-system-Python and root-relative setup workflow."""

    def test_bootstrap_entrypoints_exist(self) -> None:
        for relative in (
            "setup.bat",
            "run.bat",
            "scripts/bootstrap.ps1",
            "scripts/bootstrap_hash.ps1",
        ):
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
        self.assertIn("trackscribe_no_pause", content)
        self.assertNotIn("python.exe", content)

    def test_bootstrap_pins_verified_runtime_and_all_environments(self) -> None:
        content = (PROJECT_ROOT / "scripts" / "bootstrap.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn('$UvVersion = "0.12.5"', content)
        self.assertIn('$PythonVersion = "3.12.14"', content)
        self.assertIn('$FfmpegVersion = "8.1.2"', content)
        self.assertIn("Assert-FileSha256", content)
        self.assertIn("Get-Sha256Hex", content)
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

    @unittest.skipUnless(sys.platform == "win32", "Windows PowerShell bootstrap test")
    def test_dotnet_hash_helper_known_file_and_case_insensitive_expected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            sample = Path(temporary) / "known.bin"
            payload = b"TrackScribe SHA-256 regression\n"
            sample.write_bytes(payload)
            expected = hashlib.sha256(payload).hexdigest()
            result = self._run_hash_command(
                "$actual = Get-Sha256Hex -Path %s; "
                "Assert-FileSha256 -Path %s -Expected %s -Description 'known file'; "
                "Write-Output $actual"
                % (
                    self._powershell_quote(sample),
                    self._powershell_quote(sample),
                    self._powershell_quote(expected.upper()),
                )
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(result.stdout.strip().splitlines()[-1], expected)

    @unittest.skipUnless(sys.platform == "win32", "Windows PowerShell bootstrap test")
    def test_dotnet_hash_helper_rejects_mismatch_with_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            sample = Path(temporary) / "wrong.bin"
            payload = b"wrong hash regression"
            sample.write_bytes(payload)
            actual = hashlib.sha256(payload).hexdigest()
            expected = "0" * 64
            result = self._run_hash_command(
                "Assert-FileSha256 -Path %s -Expected %s -Description 'wrong artifact'"
                % (self._powershell_quote(sample), self._powershell_quote(expected))
            )
            output = result.stdout + result.stderr
            compact_output = "".join(output.split())
            self.assertNotEqual(result.returncode, 0, output)
            self.assertIn("wrong artifact", output)
            self.assertIn(str(sample), output)
            self.assertIn(expected, compact_output)
            self.assertIn(actual, compact_output)
            self.assertFalse(sample.exists(), "A mismatched downloaded artifact must be removed")

    @unittest.skipUnless(sys.platform == "win32", "Windows PowerShell bootstrap test")
    def test_dotnet_hash_helper_reports_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            missing = Path(temporary) / "missing.zip"
            result = self._run_hash_command(
                "Get-Sha256Hex -Path %s" % self._powershell_quote(missing)
            )
            output = result.stdout + result.stderr
            self.assertNotEqual(result.returncode, 0, output)
            self.assertIn("SHA-256 input file not found", output)
            self.assertIn(str(missing), output)

    def test_bootstrap_hashing_does_not_use_get_file_hash(self) -> None:
        scripts = "\n".join(
            (PROJECT_ROOT / relative).read_text(encoding="utf-8")
            for relative in ("scripts/bootstrap.ps1", "scripts/bootstrap_hash.ps1")
        )
        self.assertNotIn("Get-FileHash", scripts)

    @unittest.skipUnless(sys.platform == "win32", "Windows batch bootstrap test")
    def test_setup_no_pause_preserves_success_and_failure_exit_codes(self) -> None:
        environment = os.environ.copy()
        environment["TRACKSCRIBE_NO_PAUSE"] = "1"
        success = subprocess.run(
            ["cmd.exe", "/d", "/c", "setup.bat", "-DryRun"],
            cwd=PROJECT_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            check=False,
        )
        self.assertEqual(success.returncode, 0, success.stdout + success.stderr)
        failure = subprocess.run(
            ["cmd.exe", "/d", "/c", "setup.bat", "-NotARealBootstrapParameter"],
            cwd=PROJECT_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            check=False,
        )
        self.assertEqual(failure.returncode, 1, failure.stdout + failure.stderr)

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

    @staticmethod
    def _powershell_quote(value: str | Path) -> str:
        return "'" + str(value).replace("'", "''") + "'"

    def _run_hash_command(self, body: str) -> subprocess.CompletedProcess[str]:
        helper = PROJECT_ROOT / "scripts" / "bootstrap_hash.ps1"
        command = (
            "$ErrorActionPreference = 'Stop'; "
            f". {self._powershell_quote(helper)}; "
            f"{body}"
        )
        return subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                command,
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )


if __name__ == "__main__":
    unittest.main()
