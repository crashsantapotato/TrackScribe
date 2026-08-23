"""Validate bootstrap environment imports and pinned distribution versions."""

from __future__ import annotations

import argparse
import base64
import importlib
from importlib import metadata
import json
import sys
import traceback
from typing import Any


TORCH_LOCAL_BUILD_DISTRIBUTIONS = frozenset({"torch", "torchaudio", "torchvision"})


class VersionValidationError(RuntimeError):
    """Raised when an installed distribution does not satisfy its bootstrap pin."""


def _distribution_key(name: str) -> str:
    return name.lower().replace("_", "-").replace(".", "-")


def validate_distribution_version(
    distribution: str,
    actual: str,
    expected: str,
) -> str:
    """Validate one version and return the applied policy (``exact`` or ``base``).

    PyTorch-family pins without local metadata accept the same PEP 440 public
    version with any legitimate local build identifier. A pin that includes a
    local identifier remains exact. All other distributions retain the
    bootstrap's existing strict string-equality contract.
    """

    if _distribution_key(distribution) not in TORCH_LOCAL_BUILD_DISTRIBUTIONS:
        if actual != expected:
            raise VersionValidationError(
                f"{distribution} version mismatch: installed {actual}; "
                f"expected exact {expected}"
            )
        return "exact"

    try:
        from packaging.version import InvalidVersion, Version
    except ImportError as exc:  # pragma: no cover - guarded by locked ML requirements
        raise VersionValidationError(
            f"{distribution} version validation requires the pinned packaging distribution"
        ) from exc

    try:
        actual_version = Version(actual)
        expected_version = Version(expected)
    except InvalidVersion as exc:
        raise VersionValidationError(
            f"Invalid PEP 440 version while checking {distribution}: "
            f"installed {actual!r}; expected {expected!r}"
        ) from exc

    if expected_version.local is None:
        if actual_version.public != expected_version.public:
            raise VersionValidationError(
                f"{distribution} version mismatch: installed {actual}; "
                f"expected base {expected_version.public}"
            )
        return "base"

    if actual_version != expected_version:
        raise VersionValidationError(
            f"{distribution} version mismatch: installed {actual}; "
            f"expected exact {expected}"
        )
    return "exact"


def check_environment(specification: dict[str, Any]) -> None:
    """Run the import and distribution checks described by a trusted spec."""

    expected_python = str(specification["python_version"])
    actual_python = ".".join(str(part) for part in sys.version_info[:3])
    if actual_python != expected_python:
        raise RuntimeError(
            f"Python version mismatch: installed {actual_python}; "
            f"expected exact {expected_python}"
        )
    print(f"[OK] Python {actual_python}")

    for module_name in specification["imports"]:
        importlib.import_module(str(module_name))

    for distribution, expected in specification["versions"].items():
        actual = metadata.version(distribution)
        policy = validate_distribution_version(distribution, actual, str(expected))
        if policy == "base":
            from packaging.version import Version

            print(
                f"[OK] {distribution} {actual} "
                f"(expected base: {Version(str(expected)).public})"
            )
        else:
            print(f"[OK] {distribution} {actual}")


def _decode_specification(encoded: str) -> dict[str, Any]:
    payload = base64.b64decode(encoded, validate=True).decode("utf-8")
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise TypeError("Environment self-check specification must be a JSON object")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec-base64", required=True)
    arguments = parser.parse_args(argv)
    environment_name = "unknown environment"
    try:
        specification = _decode_specification(arguments.spec_base64)
        environment_name = str(specification.get("name", environment_name))
        check_environment(specification)
    except Exception:
        print(f"Environment self-check failed: {environment_name}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
