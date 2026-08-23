"""Load and validate paths and parameters for isolated pipeline environments."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from trackscribe.errors import ConfigError


DEFAULT_CONFIG_PATH = (
    Path(__file__).resolve().parents[1] / "config" / "trackscribe.json"
)
LOCAL_CONFIG_PATH = DEFAULT_CONFIG_PATH.with_name("trackscribe.local.json")
UPSTREAM_AUTO = "upstream-auto"

REQUIRED_PROGRAMS = {
    "main": (),
    "bass": (),
    "piano": (),
    "mega": (),
    "amt": (),
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Merge a small developer-local override without changing default semantics."""

    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


@dataclass(frozen=True)
class PipelineConfig:
    """Resolved configuration with helpers for venv executables and model paths."""

    path: Path
    raw: dict[str, Any]

    @classmethod
    def load(cls, path: str | Path = DEFAULT_CONFIG_PATH) -> "PipelineConfig":
        """Read a JSON configuration file and validate its required structure."""

        config_path = Path(path).expanduser().resolve()
        if not config_path.is_file():
            raise ConfigError(f"Pipeline config not found: {config_path}")
        try:
            raw = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigError(f"Cannot read pipeline config {config_path}: {exc}") from exc
        if config_path == DEFAULT_CONFIG_PATH.resolve() and LOCAL_CONFIG_PATH.is_file():
            try:
                local = json.loads(LOCAL_CONFIG_PATH.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ConfigError(
                    f"Cannot read local config {LOCAL_CONFIG_PATH}: {exc}"
                ) from exc
            if not isinstance(local, dict):
                raise ConfigError(f"Local config must be an object: {LOCAL_CONFIG_PATH}")
            raw = _deep_merge(raw, local)
        for key in ("venvs", "models", "stages"):
            if not isinstance(raw.get(key), dict):
                raise ConfigError(f"Config section '{key}' must be an object")
        return cls(config_path, raw)

    def section(self, name: str) -> dict[str, Any]:
        """Return a defensive copy of one stage parameter section."""

        value = self.raw["stages"].get(name)
        if not isinstance(value, dict):
            raise ConfigError(f"Missing stage config: {name}")
        return deepcopy(value)

    def model(self, name: str) -> dict[str, Any]:
        """Return model metadata with known path fields resolved."""

        value = self.raw["models"].get(name)
        if not isinstance(value, dict):
            raise ConfigError(f"Missing model config: {name}")
        model = deepcopy(value)
        path_keys = {"checkpoint", "config", "weights", "model_dir"}
        for key, item in tuple(model.items()):
            upstream_checkpoint = (
                model.get("checkpoint_source") == UPSTREAM_AUTO
                and key.endswith("_checkpoint")
            )
            if item and not upstream_checkpoint and (key in path_keys or key.endswith("_checkpoint")):
                model[key] = str(self.resolve_path(item))
        return model

    def resolve_path(self, value: str | Path) -> Path:
        """Resolve environment variables and config-relative paths."""

        expanded = os.path.expandvars(os.path.expanduser(str(value)))
        path = Path(expanded)
        if not path.is_absolute():
            path = self.path.parent / path
        return path.resolve()

    def venv(self, name: str) -> Path:
        """Resolve one configured virtual environment root."""

        value = self.raw["venvs"].get(name)
        if not isinstance(value, str):
            raise ConfigError(f"Missing venv path: {name}")
        return self.resolve_path(value)

    def executable(self, venv_name: str, program: str) -> Path:
        """Return a platform-appropriate executable inside a configured venv."""

        venv = self.venv(venv_name)
        scripts = venv / ("Scripts" if (venv / "Scripts").is_dir() else "bin")
        candidates = [scripts / program]
        if os.name == "nt":
            candidates.insert(0, scripts / f"{program}.exe")
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        raise ConfigError(f"Executable '{program}' not found in venv: {venv}")

    def python(self, venv_name: str) -> Path:
        """Return the Python interpreter for one configured venv."""

        return self.executable(venv_name, "python")

    def validate(self) -> None:
        """Fail early if configured runtimes or explicit model assets are absent."""

        problems: list[str] = []
        for venv_name, programs in REQUIRED_PROGRAMS.items():
            try:
                self.python(venv_name)
                for program in programs:
                    self.executable(venv_name, program)
            except ConfigError as exc:
                problems.append(str(exc))
        for model_name in ("core", "adtof", "hf", "transkun", "mega53"):
            model = self.model(model_name)
            path_keys = {
                key
                for key in model
                if key in {"checkpoint", "config", "weights", "model_dir"}
                or key.endswith("_checkpoint")
            }
            if model.get("checkpoint_source") == UPSTREAM_AUTO:
                path_keys = {
                    key for key in path_keys if not key.endswith("_checkpoint")
                }
            for key in path_keys:
                if not Path(model[key]).exists():
                    problems.append(f"Missing {model_name}.{key}: {model[key]}")
        if problems:
            raise ConfigError("Invalid pipeline configuration:\n- " + "\n- ".join(problems))

    def snapshot(self) -> dict[str, Any]:
        """Return the serializable source configuration for project provenance."""

        return deepcopy(self.raw)
