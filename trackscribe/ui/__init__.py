"""Optional PySide6 desktop interface for TrackScribe."""


def launch_ui() -> int:
    """Import Qt lazily and launch the desktop application."""

    from trackscribe.ui.main_window import launch_ui as launch

    return launch()


__all__ = ["launch_ui"]
