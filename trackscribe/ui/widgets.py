"""Small reusable Qt widgets for the TrackScribe desktop window."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from trackscribe.audio import is_supported_audio


class DropArea(QFrame):
    """Large Windows drag-and-drop target for supported local audio files."""

    file_selected = Signal(str)
    unsupported_file = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the drop target without handling pipeline concerns."""

        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumHeight(135)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setObjectName("dropArea")
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title = QLabel("Drop audio file here")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setStyleSheet("font-size: 17px; font-weight: 600;")
        self.hint = QLabel("or use Browse…")
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint.setStyleSheet("color: #666;")
        layout.addWidget(self.title)
        layout.addWidget(self.hint)
        self.setStyleSheet(
            "#dropArea { border: 2px dashed #8a8a8a; border-radius: 8px; "
            "background: #fafafa; }"
        )

    def set_file(self, path: Path) -> None:
        """Show the selected filename while the full path remains in the form."""

        self.title.setText(path.name)
        self.hint.setText("Ready to transcribe")

    def _local_path(self, event: QDragEnterEvent | QDropEvent) -> Path | None:
        mime = event.mimeData()
        if not mime.hasUrls():
            return None
        for url in mime.urls():
            if not url.isLocalFile():
                continue
            path = Path(url.toLocalFile())
            if path.is_file():
                return path
        return None

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        """Accept local files so unsupported drops can receive an explicit error."""

        if self.isEnabled() and self._local_path(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        """Emit a supported selection or an explicit unsupported-file signal."""

        path = self._local_path(event)
        if path:
            event.acceptProposedAction()
            signal = self.file_selected if is_supported_audio(path) else self.unsupported_file
            signal.emit(str(path))
        else:
            event.ignore()


class CollapsibleSection(QWidget):
    """Simple accessible disclosure widget with a reusable content area."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        """Create a collapsed section and expose its body for child controls."""

        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.toggle = QToolButton(text=title, checkable=True, checked=False)
        self.toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle.setArrowType(Qt.ArrowType.RightArrow)
        self.toggle.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.toggle.setStyleSheet("QToolButton { text-align: left; font-weight: 600; }")
        self.body = QWidget()
        self.body.setVisible(False)
        self.toggle.toggled.connect(self.set_expanded)
        layout.addWidget(self.toggle)
        layout.addWidget(self.body)

    def set_expanded(self, expanded: bool) -> None:
        """Show or hide content and keep the arrow state synchronized."""

        self.toggle.blockSignals(True)
        self.toggle.setChecked(expanded)
        self.toggle.blockSignals(False)
        self.toggle.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow
        )
        self.body.setVisible(expanded)

    def is_expanded(self) -> bool:
        """Return the current disclosure state for QSettings persistence."""

        return self.toggle.isChecked()
