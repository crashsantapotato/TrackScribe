"""Main TrackScribe window and desktop application lifecycle."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QSettings, QThread, QUrl, Qt
from PySide6.QtGui import QCloseEvent, QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from trackscribe.audio import (
    AUDIO_FILE_DIALOG_FILTER,
    is_supported_audio,
    supported_audio_description,
)
from trackscribe.harmony_backends import COMPARE, TRANSKUN
from trackscribe.modes import DETAILED_STEMS, PRESERVE_HARMONY
from trackscribe.reaper_discovery import find_reaper_executable
from trackscribe.types import PipelineResult, ProgressEvent
from trackscribe.ui.helpers import (
    BACKEND_LABELS,
    DEFAULT_OUTPUT_ROOT,
    DEFAULT_UI_BACKEND,
    MODE_LABELS,
    PROJECT_ROOT,
    STAGE_LABELS,
    ArtifactDiscovery,
    PipelineJob,
    discover_artifacts,
    project_uses_resume,
    resolved_project_path,
    safe_project_name,
    stage_order_for_job,
    stage_view_state,
    validate_input,
    validate_output_root,
)
from trackscribe.ui.readiness import check_readiness
from trackscribe.ui.reaper_worker import ReaperJob, ReaperWorker
from trackscribe.ui.widgets import CollapsibleSection, DropArea
from trackscribe.ui.worker import PipelineFailure, PipelineRunner, PipelineWorker


def _setting_bool(settings: QSettings, key: str, default: bool) -> bool:
    """Read a QSettings boolean consistently across native and INI backends."""

    value = settings.value(key, default)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


class MainWindow(QMainWindow):
    """Thin single-job desktop shell over the public TrackScribe API."""

    def __init__(
        self,
        *,
        settings: QSettings | None = None,
        runner: PipelineRunner | None = None,
    ) -> None:
        """Build controls and keep all pipeline work outside the GUI thread."""

        super().__init__()
        self.settings = settings or QSettings()
        self._runner = runner
        self.input_path: Path | None = None
        self._running = False
        self._exit_after_job = False
        self._thread: QThread | None = None
        self._worker: PipelineWorker | None = None
        self._reaper_thread: QThread | None = None
        self._reaper_worker: ReaperWorker | None = None
        self._reaper_running = False
        self._current_project_dir: Path | None = None
        self._stage_order: tuple[str, ...] = ()
        self._stage_items: dict[str, QListWidgetItem] = {}
        self._folder_paths: dict[str, Path] = {}
        self._previous_backend = DEFAULT_UI_BACKEND
        self._last_input_directory = str(PROJECT_ROOT)

        self.setWindowTitle("TrackScribe")
        self.resize(780, 900)
        self.setMinimumSize(680, 680)
        self._build_ui()
        self._load_settings()
        self._update_mode_constraints()

    def _build_ui(self) -> None:
        """Construct the utilitarian v1 interface."""

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(24, 20, 24, 24)
        outer.setSpacing(14)
        scroll.setWidget(container)
        self.setCentralWidget(scroll)

        title = QLabel("TrackScribe")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 28px; font-weight: 700;")
        subtitle = QLabel("Local audio-to-MIDI transcription")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("font-size: 14px; color: #666;")
        outer.addWidget(title)
        outer.addWidget(subtitle)

        self.drop_area = DropArea()
        self.drop_area.file_selected.connect(lambda value: self._set_input(Path(value)))
        self.drop_area.unsupported_file.connect(self._show_unsupported_input)
        outer.addWidget(self.drop_area)
        browse_row = QHBoxLayout()
        browse_row.addStretch()
        self.browse_button = QPushButton("Browse…")
        self.browse_button.clicked.connect(self._browse_input)
        browse_row.addWidget(self.browse_button)
        browse_row.addStretch()
        outer.addLayout(browse_row)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.input_label = QLabel("No file selected")
        self.input_label.setWordWrap(True)
        self.input_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        form.addRow("Input:", self.input_label)
        output_root_widget = QWidget()
        output_root_layout = QHBoxLayout(output_root_widget)
        output_root_layout.setContentsMargins(0, 0, 0, 0)
        self.output_root_edit = QLineEdit()
        self.output_root_edit.setPlaceholderText(str(DEFAULT_OUTPUT_ROOT))
        self.output_root_edit.textChanged.connect(self._update_resolved_path)
        self.output_root_browse_button = QPushButton("Browse…")
        self.output_root_browse_button.clicked.connect(self._browse_output_root)
        output_root_layout.addWidget(self.output_root_edit, 1)
        output_root_layout.addWidget(self.output_root_browse_button)
        form.addRow("Output root:", output_root_widget)
        self.project_name_edit = QLineEdit()
        self.project_name_edit.setPlaceholderText("Project name")
        self.project_name_edit.textEdited.connect(self._project_name_edited)
        self.project_name_edit.editingFinished.connect(self._normalize_project_name)
        form.addRow("Project:", self.project_name_edit)
        self.resolved_output_label = QLabel("")
        self.resolved_output_label.setWordWrap(True)
        self.resolved_output_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        form.addRow("Resolved project path:", self.resolved_output_label)
        self.backend_combo = QComboBox()
        for backend in (DEFAULT_UI_BACKEND, TRANSKUN, COMPARE):
            self.backend_combo.addItem(BACKEND_LABELS[backend], backend)
        form.addRow("Harmony backend:", self.backend_combo)
        outer.addLayout(form)

        self.collision_label = QLabel("")
        self.collision_label.setStyleSheet("color: #8a5b00;")
        outer.addWidget(self.collision_label)

        self.advanced = CollapsibleSection("Advanced")
        advanced_layout = QFormLayout(self.advanced.body)
        self.mode_combo = QComboBox()
        for mode in (PRESERVE_HARMONY, DETAILED_STEMS):
            self.mode_combo.addItem(MODE_LABELS[mode], mode)
        self.mode_combo.currentIndexChanged.connect(self._update_mode_constraints)
        advanced_layout.addRow("Mode:", self.mode_combo)
        self.cleanup_checkbox = QCheckBox("Harmony cleanup")
        self.cleanup_checkbox.setChecked(True)
        advanced_layout.addRow("", self.cleanup_checkbox)
        self.verbose_checkbox = QCheckBox("Verbose logging")
        advanced_layout.addRow("", self.verbose_checkbox)
        outer.addWidget(self.advanced)

        self.transcribe_button = QPushButton("TRANSCRIBE")
        self.transcribe_button.setObjectName("transcribeButton")
        self.transcribe_button.setMinimumHeight(48)
        self.transcribe_button.clicked.connect(self._start_job)
        self.transcribe_button.setStyleSheet(
            "#transcribeButton { font-size: 16px; font-weight: 700; padding: 8px; }"
        )
        outer.addWidget(self.transcribe_button)

        progress_group = QGroupBox("Progress")
        progress_layout = QVBoxLayout(progress_group)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Ready")
        self.stage_label = QLabel("Choose an audio file to begin")
        self.stage_label.setWordWrap(True)
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("font-weight: 600;")
        self.stage_list = QListWidget()
        self.stage_list.setMinimumHeight(185)
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.stage_label)
        progress_layout.addWidget(self.status_label)
        progress_layout.addWidget(self.stage_list)
        outer.addWidget(progress_group)

        output_group = QGroupBox("Outputs")
        output_layout = QVBoxLayout(output_group)
        self.artifact_container = QWidget()
        self.artifact_layout = QVBoxLayout(self.artifact_container)
        self.artifact_layout.setContentsMargins(0, 0, 0, 0)
        self.no_outputs_label = QLabel("Outputs will appear after a completed or resumed project.")
        self.no_outputs_label.setWordWrap(True)
        self.artifact_layout.addWidget(self.no_outputs_label)
        output_layout.addWidget(self.artifact_container)
        folder_row = QHBoxLayout()
        self.midi_folder_button = QPushButton("Open MIDI Folder")
        self.stems_folder_button = QPushButton("Open Stems Folder")
        self.project_folder_button = QPushButton("Open Project Folder")
        for key, button in (
            ("midi", self.midi_folder_button),
            ("stems", self.stems_folder_button),
            ("project", self.project_folder_button),
        ):
            button.setEnabled(False)
            button.clicked.connect(
                lambda checked=False, folder_key=key: self._open_folder(folder_key)
            )
            folder_row.addWidget(button)
        output_layout.addLayout(folder_row)
        outer.addWidget(output_group)

        reaper_group = QGroupBox("REAPER")
        reaper_layout = QVBoxLayout(reaper_group)
        selection_row = QHBoxLayout()
        self.reaper_checkboxes = {
            "drums": QCheckBox("Drums MIDI"),
            "bass": QCheckBox("Bass MIDI"),
            "harmony": QCheckBox("Harmony MIDI"),
            "vocals": QCheckBox("Vocals WAV"),
        }
        for checkbox in self.reaper_checkboxes.values():
            checkbox.setChecked(True)
            selection_row.addWidget(checkbox)
        reaper_layout.addLayout(selection_row)
        executable_row = QHBoxLayout()
        self.reaper_executable_edit = QLineEdit()
        self.reaper_executable_edit.setPlaceholderText("REAPER executable")
        self.reaper_executable_edit.textChanged.connect(self._update_reaper_controls)
        self.reaper_browse_button = QPushButton("Configure REAPER…")
        self.reaper_browse_button.clicked.connect(self._browse_reaper)
        executable_row.addWidget(self.reaper_executable_edit, 1)
        executable_row.addWidget(self.reaper_browse_button)
        reaper_layout.addLayout(executable_row)
        self.send_reaper_button = QPushButton("Send to REAPER")
        self.send_reaper_button.setEnabled(False)
        self.send_reaper_button.clicked.connect(self._send_to_reaper)
        reaper_layout.addWidget(self.send_reaper_button)
        for checkbox in self.reaper_checkboxes.values():
            checkbox.toggled.connect(self._update_reaper_controls)
        outer.addWidget(reaper_group)

        self.logs_section = CollapsibleSection("Logs")
        logs_layout = QVBoxLayout(self.logs_section.body)
        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumBlockCount(600)
        self.log_text.setMinimumHeight(150)
        self.open_logs_button = QPushButton("Open Logs Folder")
        self.open_logs_button.setEnabled(False)
        self.open_logs_button.clicked.connect(lambda: self._open_folder("logs"))
        logs_layout.addWidget(self.log_text)
        logs_layout.addWidget(self.open_logs_button)
        outer.addWidget(self.logs_section)
        outer.addStretch()

    def _load_settings(self) -> None:
        """Restore UI-only preferences without touching pipeline state."""

        backend = str(self.settings.value("backend", DEFAULT_UI_BACKEND))
        if backend not in BACKEND_LABELS:
            backend = DEFAULT_UI_BACKEND
        self._set_combo_value(self.backend_combo, backend)
        self._previous_backend = backend
        mode = str(self.settings.value("mode", PRESERVE_HARMONY))
        if mode not in MODE_LABELS:
            mode = PRESERVE_HARMONY
        self._set_combo_value(self.mode_combo, mode)
        self.cleanup_checkbox.setChecked(_setting_bool(self.settings, "cleanup", True))
        self.verbose_checkbox.setChecked(_setting_bool(self.settings, "verbose", False))
        for key, checkbox in self.reaper_checkboxes.items():
            checkbox.setChecked(_setting_bool(self.settings, f"reaper_{key}", True))
        saved_reaper = str(self.settings.value("reaper_executable", "")).strip()
        discovered_reaper = find_reaper_executable(saved_reaper or None)
        self.reaper_executable_edit.setText(
            str(discovered_reaper) if discovered_reaper else saved_reaper
        )
        self.advanced.set_expanded(_setting_bool(self.settings, "advanced", False))
        output_root = str(
            self.settings.value("output_root", str(DEFAULT_OUTPUT_ROOT))
        ).strip()
        self.output_root_edit.setText(output_root or str(DEFAULT_OUTPUT_ROOT))
        self._last_input_directory = str(
            self.settings.value("last_input_directory", str(PROJECT_ROOT))
        )
        geometry = self.settings.value("geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
        self._update_resolved_path()

    def _save_settings(self) -> None:
        """Persist only user-interface preferences with QSettings."""

        backend = (
            self._previous_backend
            if self.mode_combo.currentData() == DETAILED_STEMS
            else self.backend_combo.currentData()
        )
        self.settings.setValue("backend", backend)
        self.settings.setValue("mode", self.mode_combo.currentData())
        self.settings.setValue("cleanup", self.cleanup_checkbox.isChecked())
        self.settings.setValue("verbose", self.verbose_checkbox.isChecked())
        for key, checkbox in self.reaper_checkboxes.items():
            self.settings.setValue(f"reaper_{key}", checkbox.isChecked())
        self.settings.setValue(
            "reaper_executable", self.reaper_executable_edit.text().strip()
        )
        self.settings.setValue("advanced", self.advanced.is_expanded())
        self.settings.setValue("output_root", self.output_root_edit.text().strip())
        self.settings.setValue("last_input_directory", self._last_input_directory)
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.sync()

    @staticmethod
    def _set_combo_value(combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _browse_input(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose input audio",
            self._last_input_directory,
            AUDIO_FILE_DIALOG_FILTER,
        )
        if path:
            self._set_input(Path(path))

    def _set_input(self, path: Path) -> None:
        """Accept one supported local audio file from Browse or drag/drop."""

        resolved = path.expanduser().resolve()
        if not resolved.is_file():
            QMessageBox.warning(self, "Input file not found", f"File does not exist:\n{resolved}")
            return
        if not is_supported_audio(resolved):
            self._show_unsupported_input(str(resolved))
            return
        self.input_path = resolved
        self._last_input_directory = str(resolved.parent)
        self.drop_area.set_file(resolved)
        self.input_label.setText(str(resolved))
        project_name = safe_project_name(resolved.name)
        self.project_name_edit.setText(project_name)
        self._update_resolved_path()
        self.status_label.setText("Ready")
        self._append_log(f"Selected input: {resolved}")

    def _show_unsupported_input(self, value: str) -> None:
        """Explain an unsupported Browse or drop selection instead of ignoring it."""

        path = Path(value)
        suffix = path.suffix.lower() or "(none)"
        QMessageBox.warning(
            self,
            "Unsupported audio format",
            f"Unsupported audio format: {suffix}\n\nSupported: {supported_audio_description()}",
        )

    def _project_name_edited(self, _value: str) -> None:
        self._update_resolved_path()

    def _normalize_project_name(self) -> None:
        value = safe_project_name(self.project_name_edit.text())
        self.project_name_edit.setText(value)
        self._update_resolved_path()

    def _browse_output_root(self) -> None:
        start = self.output_root_edit.text().strip() or str(DEFAULT_OUTPUT_ROOT)
        path = QFileDialog.getExistingDirectory(self, "Choose output root", start)
        if path:
            self.output_root_edit.setText(str(Path(path).resolve()))

    def _browse_reaper(self) -> None:
        """Choose reaper.exe without introducing a second application config."""

        start = self.reaper_executable_edit.text().strip() or "C:/Program Files"
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose REAPER executable", start, "REAPER (reaper.exe);;All files (*)"
        )
        if path:
            self.reaper_executable_edit.setText(str(Path(path).resolve()))

    def _output_root_path(self) -> Path:
        value = self.output_root_edit.text().strip()
        return Path(value).expanduser().resolve() if value else DEFAULT_OUTPUT_ROOT.resolve()

    def _update_resolved_path(self) -> None:
        if not self.project_name_edit.text().strip():
            self.resolved_output_label.clear()
            self.collision_label.clear()
            self._show_artifacts(ArtifactDiscovery((), {}))
            return
        output_dir = self._output_path()
        self.resolved_output_label.setText(str(output_dir))
        self._update_collision(output_dir)

    def _output_path(self) -> Path:
        return resolved_project_path(
            self._output_root_path(), self.project_name_edit.text().strip()
        )

    def _update_collision(self, output_dir: Path | None = None) -> None:
        output_dir = output_dir or self._output_path()
        if project_uses_resume(output_dir):
            self.collision_label.setText(
                "Existing project — resume/cache will be used"
            )
            self._show_artifacts(discover_artifacts(output_dir))
        else:
            self.collision_label.setText("New project")
            self._show_artifacts(ArtifactDiscovery((), {}))

    def _update_mode_constraints(self) -> None:
        detailed = self.mode_combo.currentData() == DETAILED_STEMS
        if detailed:
            current = self.backend_combo.currentData()
            if current != TRANSKUN:
                self._previous_backend = current
            self._set_combo_value(self.backend_combo, TRANSKUN)
            self.backend_combo.setEnabled(False)
            self.backend_combo.setToolTip(
                "Detailed stems uses the existing Transkun-compatible backend graph."
            )
        else:
            self.backend_combo.setEnabled(not self._running)
            self.backend_combo.setToolTip("")
            if self.backend_combo.currentData() == TRANSKUN and self._previous_backend:
                self._set_combo_value(self.backend_combo, self._previous_backend)

    def _build_job(self) -> PipelineJob:
        mode = self.mode_combo.currentData()
        backend = TRANSKUN if mode == DETAILED_STEMS else self.backend_combo.currentData()
        return PipelineJob(
            input_path=self.input_path or Path(),
            output_dir=self._output_path(),
            harmony_backend=backend,
            mode=mode,
            harmony_cleanup_enabled=self.cleanup_checkbox.isChecked(),
            verbose=self.verbose_checkbox.isChecked(),
        )

    def _start_job(self) -> None:
        """Validate and launch exactly one background worker."""

        if self._running:
            return
        self._normalize_project_name()
        output_validation = validate_output_root(
            self.output_root_edit.text(), self.project_name_edit.text()
        )
        if not output_validation.valid:
            QMessageBox.warning(self, "Cannot transcribe", output_validation.message)
            return
        job = self._build_job()
        validation = validate_input(
            self.input_path,
            self.project_name_edit.text(),
            job.output_dir,
        )
        if not validation.valid:
            QMessageBox.warning(self, "Cannot transcribe", validation.message)
            return
        try:
            self._output_root_path().mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            QMessageBox.warning(
                self, "Cannot transcribe", f"Cannot create output root: {exc}"
            )
            return
        try:
            self._stage_order = stage_order_for_job(job)
        except Exception as exc:
            QMessageBox.warning(self, "Invalid settings", str(exc))
            return
        self._initialize_stage_list()
        self._set_running(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("0%")
        self.status_label.setText("Processing")
        self.stage_label.setText(f"Stage 0 / {len(self._stage_order)}")
        self._append_log(
            f"Starting {job.mode} with {BACKEND_LABELS[job.harmony_backend]}"
        )

        thread = QThread(self)
        worker = PipelineWorker(job, runner=self._runner)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_progress)
        worker.completed.connect(self._on_completed)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(self._on_thread_finished)
        thread.finished.connect(thread.deleteLater)
        self._thread = thread
        self._worker = worker
        thread.start()

    def _initialize_stage_list(self) -> None:
        self.stage_list.clear()
        self._stage_items.clear()
        for stage in self._stage_order:
            item = QListWidgetItem(f"○ {STAGE_LABELS.get(stage, stage)}")
            self.stage_list.addItem(item)
            self._stage_items[stage] = item

    def _on_progress(self, event: ProgressEvent) -> None:
        state = stage_view_state(event, self._stage_order)
        self.progress_bar.setValue(state.percent)
        self.progress_bar.setFormat(f"{state.percent}%")
        position = f"Stage {state.index} / {state.total}" if state.index else "Pipeline"
        self.stage_label.setText(f"{position} — {state.label} — {state.state}")
        item = self._stage_items.get(state.stage)
        if item is not None:
            item.setText(f"{state.prefix} {state.label} — {state.state}")
            self.stage_list.scrollToItem(item)
        self._append_log(f"{state.label}: {state.state} — {state.message}")
        if self.verbose_checkbox.isChecked() and event.details:
            self._append_log(f"  details: {event.details}")

    def _on_completed(self, result: PipelineResult) -> None:
        completed = result.status == "completed"
        self.status_label.setText("Completed" if completed else result.status.title())
        if completed:
            self.progress_bar.setValue(100)
            self.progress_bar.setFormat("100%")
        self.stage_label.setText(f"Project {result.status}: {result.project_dir}")
        self._append_log(f"Pipeline {result.status}: {result.manifest_path}")
        self._show_artifacts(discover_artifacts(result.project_dir))

    def _on_failed(self, failure: PipelineFailure) -> None:
        self.status_label.setText("Failed")
        self.stage_label.setText(f"{failure.stage} — Failed")
        self._append_log(f"FAILED at {failure.stage}: {failure.message}")
        if self.verbose_checkbox.isChecked():
            self._append_log(failure.traceback_text)
        if not self._exit_after_job:
            QMessageBox.critical(
                self,
                "TrackScribe stage failed",
                f"Stage: {failure.stage}\n{failure.message}\n\n"
                f"Partial project was kept at:\n{failure.project_dir}",
            )

    def _on_thread_finished(self) -> None:
        self._thread = None
        self._worker = None
        self._set_running(False)
        if self._exit_after_job:
            self._save_settings()
            app = QApplication.instance()
            if app is not None:
                app.quit()

    def _send_to_reaper(self) -> None:
        """Dispatch the current project through TrackScribe's isolated bridge."""

        if self._reaper_running or self._current_project_dir is None:
            return
        executable = find_reaper_executable(self.reaper_executable_edit.text().strip())
        if executable is None:
            QMessageBox.warning(self, "REAPER not found", "Configure a valid reaper.exe first.")
            return
        job = ReaperJob(
            project_dir=self._current_project_dir,
            reaper_executable=executable,
            **{key: box.isChecked() for key, box in self.reaper_checkboxes.items()},
        )
        self._reaper_running = True
        self._update_reaper_controls()
        self._append_log("Sending selected artifacts to REAPER...")
        thread = QThread(self)
        worker = ReaperWorker(job)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.completed.connect(self._on_reaper_completed)
        worker.failed.connect(self._on_reaper_failed)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(self._on_reaper_finished)
        thread.finished.connect(thread.deleteLater)
        self._reaper_thread = thread
        self._reaper_worker = worker
        thread.start()

    def _on_reaper_completed(self, payload: dict[str, object]) -> None:
        imported = ", ".join(str(value) for value in payload.get("imported", []))
        self._append_log(f"REAPER import dispatched: {imported}")
        self.status_label.setText("Sent to REAPER")

    def _on_reaper_failed(self, message: str) -> None:
        self._append_log(f"REAPER bridge failed: {message}")
        QMessageBox.critical(self, "Cannot send to REAPER", message)

    def _on_reaper_finished(self) -> None:
        self._reaper_thread = None
        self._reaper_worker = None
        self._reaper_running = False
        self._update_reaper_controls()
        if self._exit_after_job and not self._running:
            self._save_settings()
            app = QApplication.instance()
            if app is not None:
                app.quit()

    def _set_running(self, running: bool) -> None:
        self._running = running
        enabled = not running
        for widget in (
            self.drop_area,
            self.browse_button,
            self.project_name_edit,
            self.mode_combo,
            self.cleanup_checkbox,
            self.verbose_checkbox,
            self.output_root_edit,
            self.output_root_browse_button,
        ):
            widget.setEnabled(enabled)
        self.backend_combo.setEnabled(
            enabled and self.mode_combo.currentData() != DETAILED_STEMS
        )
        self.transcribe_button.setEnabled(enabled)
        self._update_reaper_controls()

    def _update_reaper_controls(self, _checked: bool | None = None) -> None:
        """Enable only artifacts that exist in the currently displayed project."""

        project = self._current_project_dir
        relative_paths = {
            "drums": "midi/drums.mid",
            "bass": "midi/bass.mid",
            "harmony": "midi/harmony.mid",
            "vocals": "stems/vocals.wav",
        }
        available = {}
        for key, checkbox in self.reaper_checkboxes.items():
            exists = project is not None and (project / relative_paths[key]).is_file()
            available[key] = exists
            checkbox.setEnabled(exists and not self._running and not self._reaper_running)
        executable = find_reaper_executable(self.reaper_executable_edit.text().strip())
        selected = any(
            available[key] and checkbox.isChecked()
            for key, checkbox in self.reaper_checkboxes.items()
        )
        self.send_reaper_button.setEnabled(
            bool(executable) and selected and not self._running and not self._reaper_running
        )
        self.reaper_browse_button.setEnabled(not self._running and not self._reaper_running)
        self.reaper_executable_edit.setEnabled(not self._running and not self._reaper_running)

    def _show_artifacts(self, discovery: ArtifactDiscovery) -> None:
        while self.artifact_layout.count():
            item = self.artifact_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        if not discovery.artifacts:
            label = QLabel("No MIDI artifacts found yet.")
            label.setWordWrap(True)
            self.artifact_layout.addWidget(label)
        current_group = ""
        for artifact in discovery.artifacts:
            if artifact.group != current_group:
                current_group = artifact.group
                heading = QLabel(current_group)
                heading.setStyleSheet("font-weight: 600; margin-top: 4px;")
                self.artifact_layout.addWidget(heading)
            row = QFrame()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            label = QLabel(artifact.label)
            button = QPushButton("Open")
            button.clicked.connect(
                lambda checked=False, path=artifact.path: self._open_path(path)
            )
            row_layout.addWidget(label, 1)
            row_layout.addWidget(button)
            self.artifact_layout.addWidget(row)
        self._folder_paths = discovery.folders
        self._current_project_dir = discovery.project_dir
        for key, button in (
            ("midi", self.midi_folder_button),
            ("stems", self.stems_folder_button),
            ("project", self.project_folder_button),
            ("logs", self.open_logs_button),
        ):
            button.setEnabled(key in self._folder_paths)
        self._update_reaper_controls()

    def _open_folder(self, key: str) -> None:
        path = self._folder_paths.get(key)
        if path is not None:
            self._open_path(path)

    def _open_path(self, path: Path) -> None:
        if not path.exists():
            QMessageBox.warning(self, "Missing output", f"Path does not exist:\n{path}")
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
            QMessageBox.warning(self, "Cannot open", f"Windows could not open:\n{path}")

    def _append_log(self, message: str) -> None:
        self.log_text.appendPlainText(message)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Never destroy a running QThread without an explicit safe choice."""

        if self._running or self._reaper_running:
            box = QMessageBox(self)
            box.setWindowTitle("TrackScribe is processing")
            box.setText(
                "TrackScribe is currently processing a track.\n"
                "Closing immediately could interrupt the pipeline."
            )
            box.setInformativeText(
                "Close Anyway hides the window and exits safely after the current job ends."
            )
            keep_button = box.addButton("Keep Running", QMessageBox.ButtonRole.RejectRole)
            close_button = box.addButton(
                "Close Anyway", QMessageBox.ButtonRole.DestructiveRole
            )
            box.setDefaultButton(keep_button)
            box.exec()
            if box.clickedButton() is close_button:
                self._exit_after_job = True
                self.hide()
                self._append_log("Window hidden; waiting for the active job to finish safely.")
            event.ignore()
            return
        self._save_settings()
        event.accept()


def launch_ui() -> int:
    """Create QApplication, show MainWindow, and run the native Qt event loop."""

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    app.setOrganizationName("TrackScribe")
    app.setApplicationName("TrackScribe")
    readiness = check_readiness()
    if not readiness.ready:
        QMessageBox.critical(
            None,
            "TrackScribe setup is incomplete",
            readiness.user_message(),
        )
        return 1
    window = MainWindow()
    window.show()
    setattr(app, "_trackscribe_main_window", window)
    return app.exec()
