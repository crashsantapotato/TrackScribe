"""Tests for canonical master.wav preparation and provenance."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from trackscribe.audio import find_ffmpeg
from trackscribe.errors import ProcessError, StageError
from trackscribe.executor import StageExecutor
from trackscribe.layout import ProjectLayout
from trackscribe.manifest import ProjectManifest
from trackscribe.stages import master
from trackscribe.stages.base import StageServices


class MasterStageTests(unittest.TestCase):
    """Exercise copy/decode paths without invoking downstream musical stages."""

    def _services(
        self,
        root: Path,
        source: Path,
        run_command=None,
    ) -> tuple[SimpleNamespace | StageServices, ProjectManifest]:
        layout = ProjectLayout.create(root / "project")
        manifest = ProjectManifest(layout, source, {"fingerprint": "test"})
        manifest.start_run()
        executor = StageExecutor(layout, manifest, None, set())
        if run_command is None:
            services = StageServices(
                config=SimpleNamespace(),
                layout=layout,
                executor=executor,
                repository_root=root,
            )
        else:
            services = SimpleNamespace(
                layout=layout,
                executor=executor,
                repository_root=root,
                run_command=run_command,
            )
        return services, manifest

    def test_wav_fast_path_is_lossless_and_does_not_invoke_ffmpeg(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.wav"
            source.write_bytes(b"RIFF-byte-identical-test")
            run_command = Mock(side_effect=AssertionError("FFmpeg must not run"))
            services, manifest = self._services(root, source, run_command)

            with patch(
                "trackscribe.stages.master.find_ffmpeg",
                side_effect=AssertionError("FFmpeg discovery must not run"),
            ):
                outcome = master.run(services, source)

            self.assertEqual(outcome.outputs["master"].read_bytes(), source.read_bytes())
            run_command.assert_not_called()
            stage = manifest.data["stages"][master.STAGE]
            self.assertEqual(stage["metadata"]["decoder_used"], "file-copy")
            self.assertFalse(stage["metadata"]["conversion_performed"])
            self.assertIsNone(stage["command"])
            self.assertIsNone(stage["metadata"]["ffmpeg_executable"])

    def test_non_wav_invokes_ffmpeg_with_safe_command_list(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.mp3"
            source.write_bytes(b"synthetic-mp3-placeholder")
            calls: list[tuple[str, list[str]]] = []

            def fake_run(stage: str, command: list[str]) -> None:
                calls.append((stage, command))
                Path(command[-1]).write_bytes(b"RIFF-decoded")

            services, manifest = self._services(root, source, fake_run)
            ffmpeg = Path("C:/tools/ffmpeg.exe")
            with patch("trackscribe.stages.master.find_ffmpeg", return_value=ffmpeg):
                outcome = master.run(services, source)

            self.assertEqual(len(calls), 1)
            stage_name, command = calls[0]
            self.assertEqual(stage_name, master.STAGE)
            self.assertIsInstance(command, list)
            self.assertEqual(command[0], str(ffmpeg))
            self.assertEqual(command[command.index("-i") + 1], str(source.resolve()))
            self.assertIn("0:a:0", command)
            self.assertEqual(outcome.outputs["master"].read_bytes(), b"RIFF-decoded")
            record = manifest.data["stages"][master.STAGE]
            self.assertEqual(record["command"], command)
            self.assertEqual(record["metadata"]["decoder_used"], "ffmpeg")
            self.assertEqual(record["metadata"]["original_extension"], ".mp3")
            self.assertTrue(record["metadata"]["conversion_performed"])
            self.assertIn("sha256", record["metadata"]["input_signature"])

    def test_ffmpeg_error_marks_stage_failed_and_keeps_log(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "broken.mp3"
            source.write_bytes(b"not-an-mp3")
            layout_holder: dict[str, Path] = {}

            def failing_run(_stage: str, command: list[str]) -> None:
                log = layout_holder["log"]
                log.write_text("synthetic ffmpeg stderr\n", encoding="utf-8")
                raise ProcessError(command, 1, str(log))

            services, manifest = self._services(root, source, failing_run)
            layout_holder["log"] = services.layout.logs / "prepare_master.log"
            with (
                patch(
                    "trackscribe.stages.master.find_ffmpeg",
                    return_value=Path("C:/tools/ffmpeg.exe"),
                ),
                self.assertRaisesRegex(StageError, "FFmpeg could not decode input audio"),
            ):
                master.run(services, source)

            record = manifest.data["stages"][master.STAGE]
            self.assertEqual(record["status"], "failed")
            self.assertEqual(manifest.data["status"], "failed")
            self.assertIn("FFmpeg could not decode", record["error"]["message"])
            self.assertEqual(record["command"][0], "C:\\tools\\ffmpeg.exe")
            self.assertEqual(record["executable"], "C:\\tools\\ffmpeg.exe")
            self.assertEqual(record["metadata"]["decoder_used"], "ffmpeg")
            log_text = layout_holder["log"].read_text(encoding="utf-8")
            self.assertIn("synthetic ffmpeg stderr", log_text)
            self.assertIn("[failed]", log_text)

    def test_content_hash_invalidates_cache_even_when_size_and_mtime_match(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "same-name.wav"
            source.write_bytes(b"AAAA")
            fixed_ns = 1_700_000_000_000_000_000
            os.utime(source, ns=(fixed_ns, fixed_ns))
            services, manifest = self._services(
                root, source, Mock(side_effect=AssertionError("No FFmpeg"))
            )

            master.run(services, source)
            master.run(services, source)
            self.assertEqual(manifest.data["stages"][master.STAGE]["attempts"], 1)
            self.assertEqual(manifest.data["stages"][master.STAGE]["cache_hits"], 1)

            source.write_bytes(b"BBBB")
            os.utime(source, ns=(fixed_ns, fixed_ns))
            master.run(services, source)

            record = manifest.data["stages"][master.STAGE]
            self.assertEqual(record["attempts"], 2)
            self.assertEqual(services.layout.master.read_bytes(), b"BBBB")
            self.assertEqual(
                record["cache_context"]["source_content_signature"]["sha256"],
                record["metadata"]["input_signature"]["sha256"],
            )

    @unittest.skipUnless(find_ffmpeg(), "FFmpeg is not available")
    def test_installed_ffmpeg_decodes_all_supported_non_wav_formats(self) -> None:
        ffmpeg = find_ffmpeg()
        assert ffmpeg is not None
        encoders = {
            ".mp3": ["-c:a", "libmp3lame"],
            ".flac": ["-c:a", "flac"],
            ".ogg": ["-c:a", "libvorbis"],
            ".m4a": ["-c:a", "aac"],
            ".aac": ["-c:a", "aac", "-f", "adts"],
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            synthetic = root / "synthetic.wav"
            with wave.open(str(synthetic), "wb") as audio:
                audio.setnchannels(2)
                audio.setsampwidth(2)
                audio.setframerate(44100)
                audio.writeframes(b"\x00\x00\x00\x00" * 4410)

            for extension, encoder_args in encoders.items():
                with self.subTest(extension=extension):
                    encoded = root / f"synthetic{extension}"
                    subprocess.run(
                        [
                            str(ffmpeg),
                            "-hide_banner",
                            "-loglevel",
                            "error",
                            "-nostdin",
                            "-y",
                            "-i",
                            str(synthetic),
                            *encoder_args,
                            str(encoded),
                        ],
                        check=True,
                        capture_output=True,
                    )
                    project_root = root / f"project-{extension[1:]}"
                    services, manifest = self._services(project_root, encoded)
                    outcome = master.run(services, encoded)
                    with wave.open(str(outcome.outputs["master"]), "rb") as decoded:
                        self.assertEqual(decoded.getframerate(), 44100)
                        self.assertEqual(decoded.getnchannels(), 2)
                    record = manifest.data["stages"][master.STAGE]
                    self.assertEqual(record["status"], "completed")
                    self.assertEqual(
                        Path(record["metadata"]["ffmpeg_executable"]), ffmpeg
                    )


if __name__ == "__main__":
    unittest.main()
