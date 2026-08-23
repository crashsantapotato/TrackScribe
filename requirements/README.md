# Environment definitions

These files are exact snapshots of the six working TrackScribe environments
audited on 2026-08-23. They intentionally remain separate because the audio
backends have incompatible dependency graphs.

| File | Environment | Purpose |
| --- | --- | --- |
| `core.txt` | `.venv` | separation, ADTOF, velocity processing |
| `ui.txt` | `.venv-ui` | PySide6 desktop UI |
| `bass.txt` | `.venv-bass` | HF bass/guitar transcription |
| `piano.txt` | `.venv-piano` | Transkun |
| `mega.txt` | `.venv-mega` | BS-Roformer / Mega53 |
| `amt.txt` | `.venv-amt` | Instrument-Agnostic AMT runtime |

`ci.txt` is a separate lightweight CPU/mock dependency set for GitHub Actions.
It is not a seventh runtime environment and intentionally excludes PyTorch,
CUDA, backend packages, and model downloads.

All environments use CPython 3.12.14. ML environments retain the verified
PyTorch/CUDA 13.0 wheel builds. Direct upstream dependencies use immutable
GitHub commit archives, so setup does not require Git.

The bootstrap synchronizes one file into one environment with local `uv.exe`.
Do not merge the files or upgrade individual packages without validating the
corresponding musical backend.

The legacy root-level `requirements-ui.txt` includes `ui.txt`, so the existing
UI development command remains valid.
