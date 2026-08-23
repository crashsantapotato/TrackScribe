# Windows installation

## Supported host

TrackScribe 0.1.0 is prepared for 64-bit Windows 10 or newer and the pinned
CPython 3.12.14 environments. Several configured backends expect an NVIDIA GPU
with a driver compatible with PyTorch CUDA 13.0 wheels.

System Python, pip, Git, uv, and a global CUDA Toolkit are not prerequisites.

## Install

1. Clone or extract TrackScribe into a writable directory.
2. Double-click `setup.bat`.
3. Keep the terminal open until it reports `TrackScribe is ready`.
4. Double-click `run.bat`.

`run.bat` does not silently run setup. If `.venv-ui` is unavailable it exits
with a message asking you to run `setup.bat` first.

Setup creates only root-relative ignored paths:

```text
.bootstrap/
.venv/
.venv-ui/
.venv-bass/
.venv-piano/
.venv-mega/
.venv-amt/
models/
tools/ffmpeg/
tools/instrument-agnostic-amt/
```

These directories are local runtime state and are never part of a source
release. Moving a fully installed directory is not guaranteed to relocate every
virtual environment; moving a clean source tree and running setup again is the
supported path.

## What setup downloads

- SHA-256-verified portable uv 0.12.5.
- uv-managed CPython 3.12.14.
- Six exact package snapshots from `requirements/`.
- SHA-256-verified Instrument-Agnostic AMT source at the pinned commit.
- A pinned, SHA-256-verified FFmpeg 8.1.2 essentials build only when neither a
  working local copy nor system `ffmpeg.exe` exists.
- The large Mega53 checkpoint through BS-Roformer-Infer's SHA-256-verifying
  downloader.

The first use of htdemucs_ft, HF MIDI transcription, and Instrument-Agnostic AMT
may download additional checkpoints. ADTOF and Transkun package installs already
contain their weights.

Review `LICENSE_AUDIT.md` before setup if external model license restrictions are
relevant to your intended use.

## Structural dry run

This command changes nothing and downloads nothing:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/bootstrap.ps1 -DryRun
```

It reports environment runtime presence, the AMT checkout, FFmpeg discovery,
and the Mega53 checkpoint plan. Full imports and exact package-version checks
run during normal setup, not during the structural dry run.

## Repair and second run

Setup is designed to be run repeatedly. It checks actual Python versions,
imports, critical package versions, and requirement-file hashes. Healthy
components are reused. A changed environment definition is synchronized; an
invalid environment is repaired in its own directory.

Do not manually install one backend's packages into another backend environment.

## Common failures

### PowerShell policy

Use `setup.bat`, which invokes the checked-in script with a process-local
`ExecutionPolicy Bypass`. No permanent policy change is required.

### Download or SHA-256 failure

Retry setup after confirming network/proxy access. A checksum mismatch is a hard
failure and the bad archive is removed. Do not disable verification; compare the
pinned source and checksum with `scripts/bootstrap.ps1` instead.

### CUDA unavailable

Bootstrap completes with a warning when a GPU environment cannot see CUDA. Check
the NVIDIA driver and reboot if it was just updated. Installing a global CUDA
Toolkit normally does not repair an incompatible driver/wheel combination.

### FFmpeg decode failure

Inspect the `prepare_master` stage log and `project.json`. TrackScribe records the
executable and command. The fallback build supports the documented input
containers, but a specific damaged/encrypted file may still fail.

### Model download failure

Rerun the same project after connectivity is restored. Completed earlier stages
are reused when their fingerprints and outputs still match.

### UI opens and closes immediately

Start `run.bat` from a terminal to preserve its error message, or run:

```powershell
.venv-ui\Scripts\python.exe ui.py
```

Do not use a random system Python for the UI.
