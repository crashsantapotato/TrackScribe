"""Static portability checks for the Windows bootstrap contract."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VERSION_CHECKER = PROJECT_ROOT / "scripts" / "bootstrap_versions.py"


class BootstrapContractTest(unittest.TestCase):
    """Guard the no-system-Python and root-relative setup workflow."""

    def test_bootstrap_entrypoints_exist(self) -> None:
        for relative in (
            "setup.bat",
            "run.bat",
            "scripts/bootstrap.ps1",
            "scripts/bootstrap_hash.ps1",
            "scripts/bootstrap_environment.ps1",
            "scripts/bootstrap_versions.py",
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
        self.assertIn('"torchvision" = "0.28.0"', content)
        self.assertIn("bootstrap_versions.py", content)
        self.assertIn("Invoke-PythonUtf8Checked $megaPython", content)
        self.assertNotIn("assert metadata.version", content)

    def test_torchaudio_base_pin_accepts_pep440_local_builds(self) -> None:
        versions = self._load_version_checker()
        for actual in (
            "2.11.0",
            "2.11.0+cu130",
            "2.11.0+cu130.some_local_tag",
        ):
            with self.subTest(actual=actual):
                self.assertEqual(
                    versions.validate_distribution_version(
                        "torchaudio", actual, "2.11.0"
                    ),
                    "base",
                )

    def test_torchaudio_base_pin_rejects_other_releases(self) -> None:
        versions = self._load_version_checker()
        for actual in (
            "2.10.0+cu130",
            "2.11.1+cu130",
            "3.0.0",
        ):
            with self.subTest(actual=actual):
                with self.assertRaises(versions.VersionValidationError):
                    versions.validate_distribution_version(
                        "torchaudio", actual, "2.11.0"
                    )

    def test_torch_family_policy_preserves_full_local_and_base_pins(self) -> None:
        versions = self._load_version_checker()
        self.assertEqual(
            versions.validate_distribution_version(
                "torchvision", "0.28.0+cu130", "0.28.0"
            ),
            "base",
        )
        self.assertEqual(
            versions.validate_distribution_version(
                "torch", "2.13.0+cu130", "2.13.0+cu130"
            ),
            "exact",
        )
        with self.assertRaises(versions.VersionValidationError):
            versions.validate_distribution_version(
                "torch", "2.13.0+cu128", "2.13.0+cu130"
            )
        with self.assertRaises(versions.VersionValidationError):
            versions.validate_distribution_version(
                "audio-separator", "0.44.6", "0.44.5"
            )

    @unittest.skipUnless(sys.platform == "win32", "Windows PowerShell bootstrap test")
    def test_environment_self_check_preserves_actionable_traceback(self) -> None:
        python_version = ".".join(str(part) for part in sys.version_info[:3])
        command = (
            "$definition = [ordered]@{"
            "Name = 'Regression environment'; "
            "Imports = @('json'); "
            "Versions = [ordered]@{'numpy' = '0.0.0'}"
            "}; "
            "$result = Invoke-EnvironmentSelfCheck "
            f"-PythonExecutable {self._powershell_quote(sys.executable)} "
            f"-CheckerPath {self._powershell_quote(VERSION_CHECKER)} "
            f"-ExpectedPythonVersion {self._powershell_quote(python_version)} "
            "-Definition $definition; "
            "Write-Output $result.StdOut; Write-Output $result.StdErr; "
            "if ($result.Success) { exit 9 } else { exit 0 }"
        )
        result = self._run_environment_command(command)
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertIn("Environment self-check failed: Regression environment", output)
        self.assertIn("Traceback (most recent call last):", output)
        self.assertIn("numpy version mismatch", output)
        self.assertIn("expected exact 0.0.0", output)

    @unittest.skipUnless(sys.platform == "win32", "Windows PowerShell bootstrap test")
    def test_python_utf8_launcher_overrides_hostile_legacy_encoding(self) -> None:
        code = (
            "import sys; "
            "print('ENCODING=' + sys.stdout.encoding); "
            "print('TrackScribe ' + chr(0x1f4e6) + ' UTF-8 test')"
        )
        hostile_environment = os.environ.copy()
        hostile_environment["PYTHONUTF8"] = "0"
        hostile_environment["PYTHONIOENCODING"] = "cp1251"
        baseline = subprocess.run(
            [sys.executable, "-c", code],
            cwd=PROJECT_ROOT,
            env=hostile_environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
        self.assertNotEqual(baseline.returncode, 0)
        self.assertIn("UnicodeEncodeError", baseline.stderr)

        command = (
            "$arguments = @('-c', %s); "
            "Invoke-PythonUtf8Checked -Executable %s -Arguments $arguments "
            "-Description 'UTF-8 regression'; "
            "Write-Output ('RESTORED=' + $env:PYTHONUTF8 + '|' + "
            "$env:PYTHONIOENCODING)"
            % (self._powershell_quote(code), self._powershell_quote(sys.executable))
        )
        result = self._run_environment_command(command, environment=hostile_environment)
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertIn("ENCODING=utf-8", output)
        self.assertIn("TrackScribe", output)
        self.assertIn("UTF-8 test", output)
        self.assertNotIn("UnicodeEncodeError", output)
        self.assertIn("RESTORED=0|cp1251", output)

    @unittest.skipUnless(sys.platform == "win32", "Windows PowerShell bootstrap test")
    def test_python_utf8_launcher_preserves_nonzero_failure(self) -> None:
        code = "import sys; sys.stderr.write('UTF-8 failure detail\\n'); sys.exit(7)"
        command = (
            "$arguments = @('-c', %s); try { "
            "Invoke-PythonUtf8Checked -Executable %s -Arguments $arguments "
            "-Description 'UTF-8 failure regression'; exit 9 "
            "} catch { Write-Output $_.Exception.Message; "
            "if ($_.Exception.Message -match 'exit code 7') { exit 0 } else { exit 8 } }"
            % (self._powershell_quote(code), self._powershell_quote(sys.executable))
        )
        result = self._run_environment_command(command)
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertIn("UTF-8 failure detail", output)
        self.assertIn("UTF-8 failure regression failed with exit code 7", output)

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
            self.assertIn("failed SHA-256 verification", output)
            self.assertIn(expected, compact_output)
            self.assertIn(actual, compact_output)
            self.assertFalse(sample.exists(), "A mismatched downloaded artifact must be removed")
            diagnostic_path = self._extract_diagnostic_path(
                r"Path:\s*(?P<path>.+?)\.\s*Expected:", output
            )
            sample.write_bytes(payload)
            self.assertTrue(os.path.samefile(diagnostic_path, sample))

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
            diagnostic_path = self._extract_diagnostic_path(
                r"SHA-256 input file not found:\s*(?P<path>[^\r\n]+)", output
            )
            self._assert_nonexistent_paths_equivalent(diagnostic_path, missing)

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

    def _extract_diagnostic_path(self, pattern: str, output: str) -> Path:
        """Extract a path from a PowerShell diagnostic without lexical assumptions."""

        match = re.search(pattern, output)
        self.assertIsNotNone(match, output)
        assert match is not None
        return Path(match.group("path").strip())

    def _assert_nonexistent_paths_equivalent(
        self, actual: Path, expected: Path
    ) -> None:
        """Compare missing paths using same-file ancestors and relative suffixes."""

        actual_ancestor, actual_suffix = self._existing_ancestor(actual)
        expected_ancestor, expected_suffix = self._existing_ancestor(expected)
        self.assertTrue(actual_ancestor.exists(), actual_ancestor)
        self.assertTrue(expected_ancestor.exists(), expected_ancestor)
        self.assertTrue(os.path.samefile(actual_ancestor, expected_ancestor))
        self.assertEqual(
            tuple(os.path.normcase(part) for part in actual_suffix),
            tuple(os.path.normcase(part) for part in expected_suffix),
        )

    @staticmethod
    def _existing_ancestor(path: Path) -> tuple[Path, tuple[str, ...]]:
        """Return the nearest existing ancestor and the missing relative suffix."""

        suffix: list[str] = []
        while not path.exists() and path != path.parent:
            suffix.append(path.name)
            path = path.parent
        return path, tuple(reversed(suffix))

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

    def _run_environment_command(
        self,
        body: str,
        *,
        environment: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        helper = PROJECT_ROOT / "scripts" / "bootstrap_environment.ps1"
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
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )

    @staticmethod
    def _load_version_checker():
        specification = importlib.util.spec_from_file_location(
            "trackscribe_bootstrap_versions", VERSION_CHECKER
        )
        if specification is None or specification.loader is None:
            raise RuntimeError(f"Could not load {VERSION_CHECKER}")
        module = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(module)
        return module


if __name__ == "__main__":
    unittest.main()
