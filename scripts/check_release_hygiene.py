"""Fail when a public TrackScribe source tree contains private/runtime assets."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAX_SOURCE_BYTES = 5 * 1024 * 1024

FORBIDDEN_SUFFIXES = {
    ".7z",
    ".aac",
    ".bin",
    ".ckpt",
    ".dll",
    ".exe",
    ".flac",
    ".m4a",
    ".mid",
    ".midi",
    ".mp3",
    ".onnx",
    ".ogg",
    ".pt",
    ".pth",
    ".safetensors",
    ".wav",
    ".wave",
    ".zip",
}
FORBIDDEN_PARTS = {
    ".bootstrap",
    ".venv",
    ".venv-ui",
    ".venv-bass",
    ".venv-piano",
    ".venv-mega",
    ".venv-amt",
    "checkpoints",
    "models",
    "projects",
}
FORBIDDEN_TREES = {
    "tools/ffmpeg",
    "tools/instrument-agnostic-amt",
}
TEXT_SUFFIXES = {
    "",
    ".bat",
    ".cfg",
    ".ini",
    ".json",
    ".lua",
    ".md",
    ".ps1",
    ".py",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
PATH_SCAN_ALLOWLIST = {"trackscribe/bootstrap_test.py"}
SECRET_SCAN_ALLOWLIST = {"scripts/check_release_hygiene.py"}

SECRET_PATTERNS = (
    re.compile(r"hf_[A-Za-z0-9]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"Bearer[ =:]+[A-Za-z0-9._-]{16,}", re.IGNORECASE),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(
        r"(?:api[_-]?key|password|secret|token)[ =:]+[^ <>\"']{12,}",
        re.IGNORECASE,
    ),
)
PRIVATE_PATH_PATTERNS = (
    re.compile(r"[A-Za-z]:[/\\]Users[/\\][^/\\\s<>\"']+", re.IGNORECASE),
    re.compile(r"[A-Za-z]:[/\\]AI[/\\]", re.IGNORECASE),
)


def _candidate_files() -> list[Path]:
    """Return Git candidates, or all files when checking an exported tree."""

    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    if result.returncode == 0:
        names = result.stdout.decode("utf-8", errors="surrogateescape").split("\0")
        return sorted(
            path
            for name in names
            if name and (path := ROOT / name).is_file()
        )
    return sorted(
        path
        for path in ROOT.rglob("*")
        if path.is_file() and ".git" not in path.relative_to(ROOT).parts
    )


def _read_text(path: Path) -> str | None:
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return None
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


def audit() -> list[str]:
    """Return human-readable hygiene violations."""

    issues: list[str] = []
    for path in _candidate_files():
        relative = path.relative_to(ROOT).as_posix()
        parts = set(path.relative_to(ROOT).parts)
        suffix = path.suffix.lower()
        if suffix in FORBIDDEN_SUFFIXES:
            issues.append(f"forbidden release artifact: {relative}")
        if parts & FORBIDDEN_PARTS:
            issues.append(f"forbidden runtime tree: {relative}")
        if any(relative == tree or relative.startswith(tree + "/") for tree in FORBIDDEN_TREES):
            issues.append(f"external/downloaded tree: {relative}")
        if path.stat().st_size > MAX_SOURCE_BYTES:
            issues.append(f"source file exceeds 5 MiB: {relative}")
        text = _read_text(path)
        if text is None:
            continue
        if relative not in SECRET_SCAN_ALLOWLIST:
            for pattern in SECRET_PATTERNS:
                if pattern.search(text):
                    issues.append(f"possible secret ({pattern.pattern}): {relative}")
                    break
        if relative not in PATH_SCAN_ALLOWLIST:
            for pattern in PRIVATE_PATH_PATTERNS:
                if pattern.search(text):
                    issues.append(f"developer-specific path: {relative}")
                    break
    return sorted(set(issues))


def main() -> int:
    issues = audit()
    if issues:
        print("Release hygiene check failed:")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print(f"Release hygiene check passed for {len(_candidate_files())} source files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
