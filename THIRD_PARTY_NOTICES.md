# Third-Party Notices

TrackScribe-owned source code is licensed under the repository `LICENSE`. That
license does not apply to the projects, executables, or model weights listed
below. TrackScribe's Git tree contains none of the external binaries, model
checkpoints, environments, or source checkouts described here.

This notice is a practical attribution index. `LICENSE_AUDIT.md` is the detailed
code-versus-weights review and controls when the two documents differ.

## Separation

### audio-separator

- Project: [python-audio-separator](https://github.com/karaokenerds/python-audio-separator)
- Purpose: common source-separation interface.
- Version: 0.44.5.
- Code license: MIT.
- Distribution: installed into `.venv`; not bundled in Git.
- Attribution: the project requests credit for Ultimate Vocal Remover and the
  developers/trainers of the selected models.

### Demucs / htdemucs_ft

- Project: [facebookresearch/demucs](https://github.com/facebookresearch/demucs)
- Purpose: four-stem drums/bass/vocals/other separation.
- Code license: MIT, copyright Meta Platforms, Inc. and affiliates.
- Model license: **not MIT**. The maintainer states in
  [issue #327](https://github.com/facebookresearch/demucs/issues/327) that the
  pretrained weights are provided only for scientific purposes.
- Distribution: code is an external dependency; weights are downloaded on first
  use and are not bundled by TrackScribe.

## Music transcription

### ADTOF and ADTOF-pytorch

- Original project: [MZehren/ADTOF](https://github.com/MZehren/ADTOF).
- Port: [xavriley/ADTOF-pytorch](https://github.com/xavriley/ADTOF-pytorch),
  pinned commit `85c192e78f716ea0b111cc8a5ee4a8f6a3a4f8a9`.
- Purpose: drum transcription.
- Original repository license: CC BY-NC-SA 4.0.
- Port code license: **no explicit license found**.
- Model license/provenance: the port says its bundled checkpoint is converted
  from official ADTOF weights; no separate permissive grant was found.
- Distribution: setup installs the port and its weights from upstream; neither is
  included in the TrackScribe Git tree.
- Restriction: treat this backend as non-commercial/uncleared and retain required
  attribution. See `LICENSE_AUDIT.md`.

### hf-midi-transcription and model weights

- Code: [xavriley/hf_midi_transcription](https://github.com/xavriley/hf_midi_transcription),
  commit `96f6797881e9497cbfc8f8e5deccea9c1f2f7adc`, MIT.
- Models: [xavriley/midi-transcription-models](https://huggingface.co/xavriley/midi-transcription-models),
  model card license MIT.
- Purpose: bass and guitar transcription.
- Distribution: code installs into `.venv-bass`; model files download on first
  use; nothing is bundled in Git.

### Instrument-Agnostic AMT

- Code: [anime-song/instrument-agnostic-amt](https://github.com/anime-song/instrument-agnostic-amt),
  commit `c210559a481ed22fc72af2f54e020250f9aabae1`, MIT.
- Model: [anime-song/instrument_agnostic_amt](https://huggingface.co/anime-song/instrument_agnostic_amt),
  model card license MIT.
- Purpose: optional harmony transcription.
- Distribution: setup downloads the pinned source checkout; the checkpoint is
  downloaded on first use. Both remain ignored and external.
- Note: TrackScribe does not use the upstream velocity checkpoint. Its AMT
  velocity pass is TrackScribe-owned signal processing.

### Transkun

- Project: [Yujia-Yan/Transkun](https://github.com/Yujia-Yan/Transkun).
- Purpose: default CLI/API harmony transcription.
- Version: 2.0.1.
- Code/package license: MIT.
- Model: `pretrained/2.0.pt` is distributed inside the package; no separate model
  card was found. See the yellow assessment in `LICENSE_AUDIT.md`.
- Distribution: external package in `.venv-piano`; not bundled in Git.

## Experimental detailed stems

### BS-Roformer-Infer

- Project: [openmirlab/bs-roformer-infer](https://github.com/openmirlab/bs-roformer-infer).
- Version: 0.1.6 at commit `b0f1386fcced25f559f3e61c9f08a73cd9bddf80`.
- Code license: MIT, copyright OpenMIRLab.
- Distribution: installed into `.venv-mega`; not bundled in Git.

### MVSep Mega 53 Stems by ZFTurbo

- Upstream: [Music-Source-Separation-Training](https://github.com/ZFTurbo/Music-Source-Separation-Training),
  release v1.0.21.
- Purpose: experimental 53-stem separation.
- Inference/training code license: MIT.
- Checkpoint license: **UNVERIFIED**; the BS-Roformer registry records
  `license = "not-reviewed"` for this exact model.
- Distribution: downloaded from the upstream GitHub release by the external
  package and verified by SHA-256; not bundled in Git.

## Runtime libraries and tools

### PyTorch and torchaudio

- Projects: [PyTorch](https://github.com/pytorch/pytorch) and
  [torchaudio](https://github.com/pytorch/audio).
- Versions: PyTorch 2.13.0+cu130; torchaudio 2.11.0/2.11.0+cu130.
- Licenses: PyTorch BSD-style license with bundled notices; torchaudio
  BSD-2-Clause.
- Distribution: external wheels only.

### ONNX Runtime, librosa, pretty_midi, NumPy

- [ONNX Runtime](https://github.com/microsoft/onnxruntime) 1.29.0 — MIT.
- [librosa](https://github.com/librosa/librosa) 0.11.0 — ISC.
- [pretty_midi](https://github.com/craffel/pretty-midi) 0.2.11.post0 — MIT,
  copyright Colin Raffel.
- [NumPy](https://github.com/numpy/numpy) 2.5.2 — BSD-3-Clause plus bundled
  third-party notices.
- Distribution: external wheels only.

### PySide6 / Qt for Python

- Project: [Qt for Python](https://doc.qt.io/qtforpython-6/).
- Version: 6.11.2.
- Package license declaration: LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only;
  commercial Qt licensing is also available.
- Distribution: installed by the user into `.venv-ui`; Qt DLLs are not bundled in
  this source release.
- Future packaging: a frozen executable/installer must receive a new Qt LGPL/GPL
  compliance review.

### FFmpeg

- Provider: [Gyan FFmpeg Windows builds](https://www.gyan.dev/ffmpeg/builds/).
- Fallback version: 8.1.2 essentials static build.
- Provider declaration: all of these Windows builds are GPLv3.
- Distribution: bootstrap downloads and verifies the external ZIP only if a
  working local/system FFmpeg is unavailable; no binary is in Git.
- Future packaging: bundling FFmpeg requires a separate GPL redistribution
  review, including source/notice obligations.

### uv

- Project: [astral-sh/uv](https://github.com/astral-sh/uv).
- Version: 0.12.5.
- License: MIT OR Apache-2.0.
- Distribution: bootstrap downloads an official SHA-256-verified release asset;
  `uv.exe` is ignored and not bundled.

## Optional external applications

### ACE-Step

ACE-Step is a separate MIT-licensed project and is not part of this repository.
TrackScribe includes its own public JSONL bridge and documents the integration
contract. The ACE-Step-side UI/GPU handoff adapter is prepared separately and is
not shipped in TrackScribe 0.1.0. ACE-Step models and third-party assets remain
subject to their own terms.

### REAPER

REAPER is proprietary software from [Cockos](https://www.reaper.fm/) and must be
installed and licensed separately. TrackScribe includes only its own Lua importer
and Python bridge. No REAPER executable, installer, or proprietary asset is
distributed.
