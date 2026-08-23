"""Headless construction smoke test for the native Qt window."""

from __future__ import annotations

import inspect
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QMimeData, QSettings, QUrl  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox  # noqa: E402

from pipeline import _build_parser  # noqa: E402
from trackscribe import run_pipeline  # noqa: E402
from trackscribe.audio import AUDIO_FILE_DIALOG_FILTER  # noqa: E402
from trackscribe.harmony_backends import AGNOSTIC_AMT, COMPARE, TRANSKUN  # noqa: E402
from trackscribe.modes import PRESERVE_HARMONY  # noqa: E402
from trackscribe.types import PipelineResult, ProgressEvent  # noqa: E402
from trackscribe.ui.helpers import DEFAULT_OUTPUT_ROOT, discover_artifacts  # noqa: E402
from trackscribe.ui.main_window import MainWindow  # noqa: E402


class MainWindowSmokeTest(unittest.TestCase):
    """Build the complete window without displaying it or touching user settings."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_window_builds_with_safe_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            settings = QSettings(
                str(Path(temporary) / "ui-test.ini"), QSettings.Format.IniFormat
            )
            window = MainWindow(settings=settings)
            self.assertEqual(window.windowTitle(), "TrackScribe")
            self.assertEqual(window.backend_combo.currentData(), AGNOSTIC_AMT)
            self.assertEqual(window.mode_combo.currentData(), PRESERVE_HARMONY)
            self.assertTrue(window.cleanup_checkbox.isChecked())
            self.assertFalse(window.advanced.is_expanded())
            self.assertFalse(window._running)
            self.assertTrue(all(box.isChecked() for box in window.reaper_checkboxes.values()))
            self.assertFalse(window.send_reaper_button.isEnabled())
            self.assertEqual(
                Path(window.output_root_edit.text()), DEFAULT_OUTPUT_ROOT
            )
            self.assertEqual(window.resolved_output_label.text(), "")
            self.assertEqual(window.collision_label.text(), "")
            window.close()

    def test_reaper_selection_is_saved_and_restored(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "reaper-settings.ini"
            window = MainWindow(
                settings=QSettings(str(path), QSettings.Format.IniFormat)
            )
            window.reaper_checkboxes["bass"].setChecked(False)
            window.reaper_checkboxes["vocals"].setChecked(False)
            window.close()
            restored = MainWindow(
                settings=QSettings(str(path), QSettings.Format.IniFormat)
            )
            self.assertTrue(restored.reaper_checkboxes["drums"].isChecked())
            self.assertFalse(restored.reaper_checkboxes["bass"].isChecked())
            self.assertFalse(restored.reaper_checkboxes["vocals"].isChecked())
            restored.close()

    def test_reaper_selection_is_forwarded_to_worker_job(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            (project / "midi").mkdir(parents=True)
            (project / "stems").mkdir()
            for relative in ("midi/drums.mid", "midi/bass.mid", "midi/harmony.mid"):
                (project / relative).touch()
            (project / "stems" / "vocals.wav").touch()
            executable = root / "reaper.exe"
            executable.touch()
            window = MainWindow(
                settings=QSettings(
                    str(root / "selection.ini"), QSettings.Format.IniFormat
                )
            )
            window.reaper_executable_edit.setText(str(executable))
            window._show_artifacts(discover_artifacts(project))
            window.reaper_checkboxes["bass"].setChecked(False)
            window.reaper_checkboxes["vocals"].setChecked(False)
            with patch("trackscribe.ui.main_window.QThread.start"):
                window._send_to_reaper()
            job = window._reaper_worker.job
            self.assertTrue(job.drums)
            self.assertFalse(job.bass)
            self.assertTrue(job.harmony)
            self.assertFalse(job.vocals)
            window._reaper_running = False
            window._reaper_thread = None
            window._reaper_worker = None
            window.close()

    def test_custom_output_root_is_saved_and_restored(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            settings_path = root / "output-root.ini"
            custom = root / "custom-projects"
            settings = QSettings(str(settings_path), QSettings.Format.IniFormat)
            window = MainWindow(settings=settings)
            window.output_root_edit.setText(str(custom))
            window.close()
            restored_settings = QSettings(
                str(settings_path), QSettings.Format.IniFormat
            )
            restored = MainWindow(settings=restored_settings)
            self.assertEqual(Path(restored.output_root_edit.text()), custom)
            restored.close()

    def test_custom_root_and_project_name_update_resolved_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            settings = QSettings(
                str(root / "resolved.ini"), QSettings.Format.IniFormat
            )
            window = MainWindow(settings=settings)
            custom = root / "custom"
            window.project_name_edit.setText("first")
            window.output_root_edit.setText(str(custom))
            self.assertEqual(
                Path(window.resolved_output_label.text()), custom / "first"
            )
            window.project_name_edit.setFocus()
            window.project_name_edit.selectAll()
            QTest.keyClicks(window.project_name_edit, "second")
            self.app.processEvents()
            self.assertEqual(
                Path(window.resolved_output_label.text()), custom / "second"
            )
            window.close()

    def test_output_root_browse_uses_existing_directory_dialog(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            chosen = root / "chosen"
            chosen.mkdir()
            settings = QSettings(
                str(root / "root-browse.ini"), QSettings.Format.IniFormat
            )
            window = MainWindow(settings=settings)
            with patch.object(
                QFileDialog, "getExistingDirectory", return_value=str(chosen)
            ) as dialog:
                window._browse_output_root()
            dialog.assert_called_once()
            self.assertEqual(Path(window.output_root_edit.text()), chosen)
            window.close()

    def test_existing_custom_project_enables_exact_project_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            custom = root / "custom"
            project = custom / "existing"
            project.mkdir(parents=True)
            settings = QSettings(
                str(root / "existing.ini"), QSettings.Format.IniFormat
            )
            window = MainWindow(settings=settings)
            window.project_name_edit.setText("existing")
            window.output_root_edit.setText(str(custom))
            self.assertEqual(
                window.collision_label.text(),
                "Existing project — resume/cache will be used",
            )
            self.assertTrue(window.project_folder_button.isEnabled())
            with patch.object(window, "_open_path") as open_path:
                window.project_folder_button.click()
            open_path.assert_called_once_with(project)
            window.close()

    def test_saved_transkun_is_restored(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            settings = QSettings(
                str(Path(temporary) / "transkun.ini"), QSettings.Format.IniFormat
            )
            settings.setValue("backend", TRANSKUN)
            settings.sync()
            window = MainWindow(settings=settings)
            self.assertEqual(window.backend_combo.currentData(), TRANSKUN)
            window.close()

    def test_saved_compare_is_restored(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            settings = QSettings(
                str(Path(temporary) / "compare.ini"), QSettings.Format.IniFormat
            )
            settings.setValue("backend", COMPARE)
            settings.sync()
            window = MainWindow(settings=settings)
            self.assertEqual(window.backend_combo.currentData(), COMPARE)
            window.close()

    def test_changed_backend_is_saved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "persist.ini"
            settings = QSettings(str(path), QSettings.Format.IniFormat)
            window = MainWindow(settings=settings)
            window.backend_combo.setCurrentIndex(
                window.backend_combo.findData(COMPARE)
            )
            window.close()
            saved = QSettings(str(path), QSettings.Format.IniFormat)
            self.assertEqual(saved.value("backend"), COMPARE)
            restored = MainWindow(settings=saved)
            self.assertEqual(restored.backend_combo.currentData(), COMPARE)
            restored.close()

    def test_cli_and_api_defaults_remain_transkun(self) -> None:
        api_default = inspect.signature(run_pipeline).parameters[
            "harmony_backend"
        ].default
        cli_args = _build_parser().parse_args(
            ["input.wav", "--output", "project"]
        )
        self.assertEqual(api_default, TRANSKUN)
        self.assertEqual(cli_args.harmony_backend, TRANSKUN)

    def test_browse_filter_contains_all_supported_audio_formats(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            settings = QSettings(
                str(Path(temporary) / "browse.ini"), QSettings.Format.IniFormat
            )
            window = MainWindow(settings=settings)
            with patch.object(
                QFileDialog, "getOpenFileName", return_value=("", "")
            ) as dialog:
                window._browse_input()
            self.assertEqual(dialog.call_args.args[3], AUDIO_FILE_DIALOG_FILTER)
            for glob in ("*.wav", "*.mp3", "*.flac", "*.ogg", "*.m4a", "*.aac"):
                self.assertIn(glob, dialog.call_args.args[3])
            window.close()

    def test_drag_drop_emits_all_supported_audio_formats(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            settings = QSettings(
                str(root / "drop.ini"), QSettings.Format.IniFormat
            )
            window = MainWindow(settings=settings)
            selected: list[str] = []
            window.drop_area.file_selected.connect(selected.append)
            for extension in (".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac"):
                with self.subTest(extension=extension):
                    source = root / f"drop{extension}"
                    source.touch()
                    mime = QMimeData()
                    mime.setUrls([QUrl.fromLocalFile(str(source))])
                    event = Mock()
                    event.mimeData.return_value = mime
                    window.drop_area.dragEnterEvent(event)
                    event.acceptProposedAction.assert_called_once_with()
                    window.drop_area.dropEvent(event)
                    self.assertEqual(selected[-1], str(source))
            window.close()

    def test_unsupported_drop_shows_explicit_message(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "unsupported.wma"
            source.touch()
            settings = QSettings(
                str(root / "unsupported.ini"), QSettings.Format.IniFormat
            )
            window = MainWindow(settings=settings)
            mime = QMimeData()
            mime.setUrls([QUrl.fromLocalFile(str(source))])
            event = Mock()
            event.mimeData.return_value = mime
            with patch.object(QMessageBox, "warning") as warning:
                window.drop_area.dropEvent(event)
            warning.assert_called_once()
            self.assertEqual(warning.call_args.args[1], "Unsupported audio format")
            self.assertIn("Unsupported audio format", warning.call_args.args[2])
            self.assertIsNone(window.input_path)
            window.close()

    def test_mocked_pipeline_runs_in_qthread_and_updates_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "input.wav"
            source.write_bytes(b"RIFF")
            output_root = root / "custom-output"
            project = output_root / "project"
            main_thread_id = threading.get_ident()
            observed: dict[str, object] = {}

            def runner(**kwargs):
                observed["thread_id"] = threading.get_ident()
                observed["output_dir"] = kwargs["output_dir"]
                callback = kwargs["progress_callback"]
                callback(
                    ProgressEvent(
                        "prepare_master", "started", "started", 0.0
                    )
                )
                callback(
                    ProgressEvent(
                        "prepare_master",
                        "cached",
                        "reused cached outputs",
                        0.125,
                    )
                )
                midi = project / "midi"
                midi.mkdir(parents=True)
                for filename in ("drums.mid", "bass.mid", "harmony.mid"):
                    (midi / filename).touch()
                manifest = project / "project.json"
                manifest.write_text("{}", encoding="utf-8")
                return PipelineResult(project, manifest, "completed", {})

            settings = QSettings(
                str(root / "thread-test.ini"), QSettings.Format.IniFormat
            )
            window = MainWindow(settings=settings, runner=runner)
            window._set_input(source)
            window.output_root_edit.setText(str(output_root))
            window.project_name_edit.setText("project")
            window._start_job()
            deadline = time.monotonic() + 5.0
            while window._running and time.monotonic() < deadline:
                self.app.processEvents()
                QTest.qWait(5)
            self.app.processEvents()

            self.assertFalse(window._running, "Mocked QThread job timed out")
            self.assertNotEqual(observed["thread_id"], main_thread_id)
            self.assertEqual(observed["output_dir"], project)
            self.assertEqual(window.status_label.text(), "Completed")
            self.assertTrue(window.midi_folder_button.isEnabled())
            self.assertTrue(window.transcribe_button.isEnabled())
            self.assertIn("Cached", window.log_text.toPlainText())
            window.close()

    def test_invalid_output_root_blocks_pipeline_start(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "input.wav"
            source.write_bytes(b"RIFF")
            invalid_root = root / "not-a-directory"
            invalid_root.touch()
            settings = QSettings(
                str(root / "invalid-root.ini"), QSettings.Format.IniFormat
            )
            runner = Mock()
            window = MainWindow(settings=settings, runner=runner)
            window._set_input(source)
            window.output_root_edit.setText(str(invalid_root))
            with patch.object(QMessageBox, "warning") as warning:
                window._start_job()
            warning.assert_called_once()
            self.assertEqual(warning.call_args.args[1], "Cannot transcribe")
            self.assertIn("not a directory", warning.call_args.args[2])
            self.assertFalse(window._running)
            runner.assert_not_called()
            window.close()


if __name__ == "__main__":
    unittest.main()
