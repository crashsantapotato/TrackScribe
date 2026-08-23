# TrackScribe

Local audio-to-MIDI transcription pipeline for Windows.

TrackScribe turns a normal audio file into separated stems and editable MIDI while
preserving a reproducible project manifest. It runs each ML backend in its own
isolated Python environment, supports resume/cache at stage level, and provides a
native PySide6 desktop UI plus a CLI and Python API.

```text
Audio (.wav/.mp3/.flac/.ogg/.m4a/.aac)
  -> canonical master.wav
  -> htdemucs_ft source separation
     |- drums -> ADTOF -> audio-derived velocity -> drums.mid
     |- bass -> HF MIDI transcription -> bass.mid
     |- vocals -> vocals.wav
     `- other -> harmony AMT (Agnostic AMT or Transkun) -> cleanup -> harmony.mid
```

The optional REAPER integration is included. For ACE-Step, TrackScribe 0.1.0
includes the public TrackScribe JSONL bridge and integration contract; the
ACE-Step-side UI/GPU handoff adapter is prepared separately and is not shipped in
this release. `ACE-Step -> TrackScribe -> REAPER` remains a supported
architecture. The ACE-Step and REAPER applications are separate products and are
not included in this repository.

> [!IMPORTANT]
> The MIT license in this repository covers TrackScribe-owned source only. Some
> external model weights used by the workflow have non-commercial or unclear
> terms. In particular, the ADTOF provenance and pretrained Demucs weights do
> **not** support a claim that the complete workflow is unrestricted for
> commercial use. Read [LICENSE_AUDIT.md](LICENSE_AUDIT.md) before use or
> redistribution.

## Features

- Native Windows desktop UI with drag-and-drop and remembered settings.
- WAV, MP3, FLAC, OGG, M4A, and AAC input through a canonical `master.wav` stage.
- Four-stem drums, bass, vocals, and other separation with `htdemucs_ft`;
  `other.wav` is then used as the harmony AMT source.
- Drum transcription with ADTOF-pytorch and audio-derived velocities.
- Bass transcription with `hf-midi-transcription`.
- Harmony transcription with Instrument-Agnostic AMT or Transkun.
- Raw A/B `compare` mode without automatic winner selection.
- Conservative, audio-backed harmony cleanup.
- Experimental Mega53 detailed-stems mode.
- Stage-level cache/resume, structured logs, and atomic `project.json` provenance.
- Included optional TrackScribe integration for REAPER.
- Public TrackScribe JSONL bridge and documented ACE-Step integration contract;
  the ACE-Step-side UI/GPU handoff adapter is not shipped in 0.1.0.

## Requirements

- 64-bit Windows 10 or newer.
- An NVIDIA GPU and a driver compatible with the pinned PyTorch CUDA 13.0 wheels
  for the configured GPU backends.
- Internet access during setup and first use of lazy-downloaded models.
- Enough free disk space for six isolated environments and model caches.

There is no universal VRAM minimum because it depends on backend, track length,
and model settings. As a practical recommendation, 8 GB is a starting point and
12 GB or more is preferable for the main workflow. The experimental Mega53 model
is substantially heavier; its inference package recommends at least 16 GB.
CPU-only operation is not supported by every configured backend.

System Python, pip, Git, uv, a global CUDA Toolkit, ACE-Step, and REAPER are not
required for standalone TrackScribe setup.

## Installation

1. Clone or download the source into a writable directory.
2. Run `setup.bat`.
3. Wait for the bootstrap and its model downloads to finish.
4. Run `run.bat`.

Setup installs local, root-relative components only. It is designed to be
idempotent: subsequent runs reuse healthy environments and repair missing or
changed components. A clean-install acceptance test on Windows verified this
behavior from the public source: the first `setup.bat` run completed in 405.54
seconds, and a second run completed in 32.73 seconds while reusing uv, managed
Python, all six environments, the AMT source, Mega53 checkpoint, and FFmpeg.
These timings describe that acceptance machine, not a guarantee for every
Windows host.

The bootstrap currently pins:

- uv 0.12.5;
- managed CPython 3.12.14;
- six environment snapshots under `requirements/`;
- Instrument-Agnostic AMT source commit
  `c210559a481ed22fc72af2f54e020250f9aabae1`;
- FFmpeg 8.1.2 essentials build as a SHA-256-verified fallback when no working
  local/system FFmpeg is available.

Setup downloads the large experimental Mega53 checkpoint. The `htdemucs_ft`, HF
MIDI transcription, and Instrument-Agnostic AMT checkpoints are downloaded by
their upstream tools on first use. ADTOF and Transkun weights arrive inside their
pinned packages. None of these external binaries or weights is tracked by Git.

The same clean Windows acceptance verified the PySide6 UI, CUDA 13.0 on an
NVIDIA RTX 4070 Ti SUPER, a complete eight-stage `preserve-harmony` pipeline
with Agnostic AMT, the real HF bass download/runtime path, MP3 input, and the
documented non-WAV decode formats. See
[PUBLIC_RELEASE_AUDIT.md](PUBLIC_RELEASE_AUDIT.md) for the scoped evidence.

To inspect setup without changing or downloading anything:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/bootstrap.ps1 -DryRun
```

See [docs/INSTALL_WINDOWS.md](docs/INSTALL_WINDOWS.md) for setup details and
troubleshooting.

## Quick start

### Desktop UI

Run `run.bat`, then:

1. Drop an audio file or choose **Browse**.
2. Choose an output root and project name.
3. Select Agnostic AMT, Transkun, or Compare.
4. Press **Transcribe** and follow stage/cache progress.
5. Open the generated MIDI or project folder, or use the included integration to
   send the result to REAPER.

On a clean first launch the UI selects Agnostic AMT. Later launches restore the
last UI selection. This does not change the CLI/API default, which remains
Transkun.

ACE-Step-generated audio can enter the same normal input flow. Automated GPU
handoff requires the separately prepared ACE-Step-side adapter; TrackScribe
0.1.0 includes the public JSONL bridge and the documented integration contract.

For UI development on an existing installation:

```powershell
.venv-ui\Scripts\python.exe ui.py
```

### CLI

```powershell
.venv\Scripts\python.exe pipeline.py input.mp3 --output projects\track_name
```

The default mode is `preserve-harmony`; its default harmony backend is Transkun.
Select Instrument-Agnostic AMT or a raw A/B export explicitly:

```powershell
.venv\Scripts\python.exe pipeline.py input.flac --output projects\track_name --harmony-backend agnostic-amt
.venv\Scripts\python.exe pipeline.py input.wav --output projects\track_name --harmony-backend compare
```

The experimental detailed-stems branch runs Mega53 and optional per-stem MIDI
transcription:

```powershell
.venv\Scripts\python.exe pipeline.py input.wav --output projects\track_name --mode detailed-stems
```

Useful cache and diagnostics controls:

```powershell
.venv\Scripts\python.exe pipeline.py input.wav --output projects\track_name --stop-after harmony_transcription
.venv\Scripts\python.exe pipeline.py input.wav --output projects\track_name --force-stage bass_transcription
.venv\Scripts\python.exe pipeline.py input.wav --output projects\track_name --no-harmony-cleanup
.venv\Scripts\python.exe pipeline.py --help
```

Every normal invocation resumes automatically. A stage is reused only when its
input signatures, model configuration, parameters, and outputs still match.
`--force` reruns everything; `--force-stage` reruns one named stage and the
dependent work selected by the orchestrator.

### Python API

```python
from trackscribe import ProgressEvent, run_pipeline


def on_progress(event: ProgressEvent) -> None:
    print(event.stage, event.status, event.overall_progress)


result = run_pipeline(
    "input.wav",
    "projects/track_name",
    mode="preserve-harmony",
    progress_callback=on_progress,
)
```

The callback and result types contain no UI-framework objects.

## Output structure

```text
track_name/
  master.wav
  project.json
  stems/
    drums.wav
    bass.wav
    vocals.wav
    other.wav
  midi/
    drums.mid
    bass.mid
    harmony_raw.mid
    harmony.mid
    harmony_cleanup.json
  logs/
    <stage>.log
```

Compare mode also creates immutable Transkun and AMT hypotheses under `midi/ab/`
and descriptive metrics in `midi/ab/compare.json`. Detailed-stems mode adds all
Mega53 WAVs, activity analysis, and supported guitar/keys/synth MIDI outputs.

`project.json` records stage status, attempts, timing, cache decisions, commands,
model identities, parameters, errors, signatures, and relative output paths.

## Harmony behavior

- `transkun` is the CLI/API default and preserves Transkun velocity.
- `agnostic-amt` keeps the raw MIDI immutable, derives velocity from
  `stems/other.wav`, and then applies conservative cleanup.
- `compare` exports both raw hypotheses and never ranks or automatically selects
  a winner.

Cleanup does not scale-snap, transpose, quantize, replace chords, or rewrite raw
MIDI. It removes a very short note only when duration and multiple audio/harmonic
evidence checks all agree. Its JSON report keeps the evidence for each removal.

## Integrations

- [REAPER integration](docs/REAPER_INTEGRATION.md) explains the included optional
  Lua action and Python bridge, imported tracks, vocals handling, and timing
  policy. The REAPER application must be installed and licensed separately.
- [ACE-Step integration](docs/ACE_STEP_INTEGRATION.md) documents the supported
  ACE-Step commit, public TrackScribe JSONL bridge, and integration contract. The
  ACE-Step-side UI/GPU handoff adapter is prepared separately and is not shipped
  in TrackScribe 0.1.0; ACE-Step itself is not vendored or installed.

## Portable configuration

`config/trackscribe.json` is the tracked portable default. Relative paths are
resolved from the project/config location and continue to work when the source
directory moves. Machine-specific overrides may be placed in the ignored
`config/trackscribe.local.json` and passed explicitly through the existing config
option. Configuration semantics and pipeline defaults are unchanged.

## Known limitations

- Output is a machine transcription and normally requires musical review.
- Dense mixes, distortion, bleed, unusual tunings, and underrepresented
  instruments can reduce accuracy.
- Source separation can introduce artifacts or small timing differences.
- `detailed-stems` and Mega53 are experimental and memory-heavy.
- A working NVIDIA/CUDA path is currently expected by several backends.
- The first run may download large checkpoints and can take substantially longer.
- External model licenses differ from their inference-code licenses; see the
  audit before commercial or redistributed use.

## Troubleshooting

- Run `setup.bat` again to repair an incomplete installation.
- Run the bootstrap `-DryRun` command above to inspect missing components.
- Check the failed stage under `<project>/logs/` and its record in `project.json`.
- If an input container fails, confirm the selected FFmpeg can decode it.
- Update the NVIDIA driver if PyTorch cannot expose CUDA; do not install packages
  into a different TrackScribe environment to work around a backend error.
- Use a new project name when intentionally comparing different source audio, or
  rely on the input signature to invalidate `prepare_master` safely.

## License and notices

TrackScribe-owned source is licensed under the [MIT License](LICENSE). This does
not relicense any dependency, model, downloaded third-party tool (including
FFmpeg), ACE-Step, or REAPER.

- [Third-party notices](THIRD_PARTY_NOTICES.md)
- [Code/model license audit](LICENSE_AUDIT.md)
- [Dependency/environment inventory](docs/DEPENDENCIES.md)
- [Public release audit](PUBLIC_RELEASE_AUDIT.md)

TrackScribe is a transcription tool. You are responsible for having the rights
or permission required to process input audio and to use generated MIDI or
stems. Transcription does not by itself remove copyright or other rights from
the source material.
