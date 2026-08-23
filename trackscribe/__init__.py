"""Public API for the standalone TrackScribe stem and MIDI service."""

from trackscribe.api import run_pipeline
from trackscribe.config import DEFAULT_CONFIG_PATH
from trackscribe.types import PipelineResult, ProgressCallback, ProgressEvent

__version__ = "0.1.0"

__all__ = [
    "DEFAULT_CONFIG_PATH",
    "PipelineResult",
    "ProgressCallback",
    "ProgressEvent",
    "__version__",
    "run_pipeline",
]
