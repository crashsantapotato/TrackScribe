"""Domain exceptions raised by the stem and MIDI pipeline."""


class PipelineError(RuntimeError):
    """Base error for a pipeline configuration or execution failure."""


class ConfigError(PipelineError):
    """Raised when required runtime or model configuration is invalid."""


class StageError(PipelineError):
    """Raised when one pipeline stage cannot produce its declared outputs."""


class ProcessError(StageError):
    """Raised when an isolated-environment subprocess exits unsuccessfully."""

    def __init__(self, command: list[str], returncode: int, log_path: str) -> None:
        """Store the failed command, exit code, and detailed log location."""

        super().__init__(
            f"Command failed with exit code {returncode}; see log: {log_path}"
        )
        self.command = command
        self.returncode = returncode
        self.log_path = log_path
