# TrackScribe License Audit

Audit date: 2026-08-23
Scope: public **source-only** TrackScribe 0.1.0 repository

This is an engineering inventory, not legal advice. It separates the license of
inference code from the license of pretrained weights. `Bundled: No` means the
artifact is excluded from Git and obtained from its upstream by setup or first
use.

Status meanings:

- **GREEN** — sufficiently clear for the current source-only distribution.
- **YELLOW** — usable only with a notice or upstream clarification; do not make
  broad redistribution/commercial claims.
- **RED** — do not bundle or represent as commercially unrestricted in the
  current form.

## Critical component matrix

| Component | Purpose / exact version | Code source and license | Model source and license | Bundled? | Download path | Commercial / redistribution assessment | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| TrackScribe-owned source and Lua ReaScript | Application 0.1.0 | This repository; MIT | No model | Source only | N/A | MIT applies only to files owned by TrackScribe contributors | **GREEN** |
| Instrument-Agnostic AMT code | Harmony AMT, commit `c210559a481ed22fc72af2f54e020250f9aabae1` | [anime-song/instrument-agnostic-amt](https://github.com/anime-song/instrument-agnostic-amt), MIT | Separate row below | No | Setup downloads pinned source archive; SHA-256 `eff3abd93ec953f637964f55c77e4a7a382052fc59cb34ef5bdbec5d0723ccee` | Code may be obtained under MIT; retain its notice if redistributed | **GREEN** |
| Instrument-Agnostic AMT `best_model_other.pth` | Agnostic harmony checkpoint, 57,169,117 bytes | Same inference code | [Official HF model repo](https://huggingface.co/anime-song/instrument_agnostic_amt), model card `license: mit`, repo revision observed `201ff0f015429b27636fdc8897d6e4ae7fd6f144`; SHA-256 `4f190130d1fede948810ad8e7871ab5447e40f811e68516ce0396c1b4370224f` | No | Lazy first use | MIT metadata explicitly covers the model repository; do not relicense it as TrackScribe code | **GREEN** |
| Instrument-Agnostic AMT velocity checkpoint | Upstream `best_velocity_model.pth`; TrackScribe does **not** use it (TrackScribe has its own signal-derived pass) | Same inference code | Same official HF repo, `license: mit`; SHA-256 `df8b0877c8b71cb5c3c224d69d386d67520417ecbc03728f02a2951abc4d2ae1` | No | Not downloaded by the current pipeline | Inventory only; not part of the TrackScribe runtime result | **GREEN** |
| Transkun | Harmony AMT 2.0.1 | [Yujia-Yan/Transkun](https://github.com/Yujia-Yan/Transkun), MIT | `transkun/pretrained/2.0.pt` is shipped inside the licensed Python package; local audited SHA-256 `50a80010effc2a59ffcd068a95cd2b29bd7f23a27a3515bc3ccd209c89a3d44c` | No | Installed from pinned PyPI package | Package includes MIT notice and no model-specific exclusion was found, but no separate model card/grant was found | **YELLOW** |
| `hf-midi-transcription` code | Bass/guitar AMT 0.1.1, commit `96f6797881e9497cbfc8f8e5deccea9c1f2f7adc` | [xavriley/hf_midi_transcription](https://github.com/xavriley/hf_midi_transcription), MIT | Separate row below | No | Installed from immutable GitHub archive | Retain MIT attribution if redistributed | **GREEN** |
| HF MIDI weights | `filobass_20000_iterations.pth`, `guitar-gaps.pth` | Above | [Official HF model card](https://huggingface.co/xavriley/midi-transcription-models), MIT, revision observed `b7bec65a2b860aca72856b0feef58b5df407b777`; bass SHA-256 `cbc792a1b6b6002a73ee0a433c0fe5e097ee728034fe2ea70b24bd06b5026e84`, guitar SHA-256 `65483e7c0e340a90415b15b520687587698c8c728f5fa470a205f13ee45c6513` | No | Lazy first use | MIT model metadata is explicit | **GREEN** |
| ADTOF-pytorch source | Drum AMT 0.1.0, commit `85c192e78f716ea0b111cc8a5ee4a8f6a3a4f8a9` | [xavriley/ADTOF-pytorch](https://github.com/xavriley/ADTOF-pytorch); **no LICENSE file or package license metadata found** | Bundles a converted original ADTOF checkpoint; separate row below | No | Installed from pinned GitHub archive by setup | Absence of a license grant means do not treat the port as MIT or redistribute it from TrackScribe | **RED** |
| ADTOF-pytorch converted weights | `adtof_frame_rnn_pytorch_weights.pth`, 3,617,805 bytes | Port above | Port README says weights were converted directly from officially released ADTOF weights; local audited SHA-256 `1bc986e596ec47ba0b44916f87cd4a39f0b2bec23596df3fb5d0e87749217320` | No | Arrives inside the external port package | Original provenance is non-commercial/share-alike; no separate permissive grant found for the conversion | **RED** |
| Original ADTOF | Weight/source provenance | [MZehren/ADTOF](https://github.com/MZehren/ADTOF), CC BY-NC-SA 4.0 for repository content | Official original weights under the same repository terms unless upstream states otherwise | No | Not downloaded directly | NonCommercial prohibits an unrestricted-commercial claim; attribution/share-alike obligations apply within license scope | **RED** |
| audio-separator | Separation launcher 0.44.5 | [karaokenerds/python-audio-separator](https://github.com/karaokenerds/python-audio-separator), MIT | Does not license the selected Demucs weights; separate row below | No | Installed from PyPI | Credit upstream model authors/trainers as requested by the project | **GREEN** |
| Demucs code | `htdemucs_ft` inference | [facebookresearch/demucs](https://github.com/facebookresearch/demucs), MIT | Separate row below | No | Transitive dependency | Source code is MIT | **GREEN** |
| Demucs `htdemucs_ft` weights | Four fine-tuned checkpoints (`f7e0c4bc-ba3fe64a.th`, `d12395a8-e57c48e6.th`, `92cfc3b6-ef3bcb9c.th`, `04573f0d-f3cf25b2.th`) | Demucs code above | Hosted by Meta/Demucs. The maintainer states in [official issue #327](https://github.com/facebookresearch/demucs/issues/327) that model weights are not MIT and are provided only for scientific purposes. Filename suffixes are integrity prefixes, not a published full license grant | No | Lazy first use through audio-separator/Demucs | Do not bundle, redistribute, or describe the pretrained weights as commercially unrestricted | **RED** |
| BS-Roformer-Infer | Mega53 inference 0.1.6, commit `b0f1386fcced25f559f3e61c9f08a73cd9bddf80` | [openmirlab/bs-roformer-infer](https://github.com/openmirlab/bs-roformer-infer), MIT | Registry explicitly separates model metadata | No | Installed from immutable GitHub archive | Code is clear; model is separate | **GREEN** |
| MVSep Mega 53 checkpoint/config | Experimental detailed-stems model from ZFTurbo release v1.0.21 | Training/inference source [ZFTurbo/Music-Source-Separation-Training](https://github.com/ZFTurbo/Music-Source-Separation-Training), MIT | `mvsep_mega_model_bs_roformer_53_stems_v1.ckpt`; package registry says `license = "not-reviewed"`; SHA-256 `c62820893bbf86d4e734f966bd142d9157cfc8bb8e79e9d8f9ea553f3ff3519f`. Config SHA-256 `7e198062a251587088adb91215a4f44ab59e67bd62fcc805cf54d6e7dfc51103` | No | Setup invokes the official package downloader, which verifies both hashes | Redistribution and commercial status remain unverified; keep experimental and external | **YELLOW** |
| PySide6 / Qt for Python | Desktop UI 6.11.2 | [Qt for Python](https://doc.qt.io/qtforpython-6/), package metadata: `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only` (or commercial Qt terms) | No model | No | PyPI environment install | Source-only dependency install is acceptable with notice. Re-audit LGPL/GPL obligations before bundling Qt DLLs in an installer/executable | **GREEN** |
| FFmpeg fallback | Audio decoding, Gyan FFmpeg 8.1.2 essentials static build | [Gyan Windows builds](https://www.gyan.dev/ffmpeg/builds/), GPLv3 build; FFmpeg sources linked by provider | No model | No | Bootstrap downloads fixed ZIP and verifies SHA-256 `db580001caa24ac104c8cb856cd113a87b0a443f7bdf47d8c12b1d740584a2ec`; a working local/system FFmpeg is preferred | External executable is not in Git. Re-audit and provide GPL source/notice obligations before bundling a binary installer | **GREEN** for current source-only form |
| uv | Bootstrap tool 0.12.5 | [astral-sh/uv](https://github.com/astral-sh/uv), MIT OR Apache-2.0 | No model | No | Official release ZIP, SHA-256 `4c4d49d8738847d9b71ba319e49a5688c93eac0fe6204b1df24e98528dddf39a` | External bootstrap tool, not redistributed in Git | **GREEN** |
| ACE-Step | Optional generator integration; supported local baseline commit `1ddcfda4cbe69c972aae998e75a1a9de75089dd3` | Separate [ACE-Step](https://github.com/ace-step/ACE-Step) project; local audited root license MIT | ACE-Step models/assets have their own upstream terms and are outside this audit | No | User installs separately | TrackScribe does not vendor or relicense ACE-Step | **GREEN** for TrackScribe-owned bridge/docs integration |
| REAPER | Optional DAW target | Proprietary product from [Cockos](https://www.reaper.fm/); not open-source TrackScribe content | No model | No | User installs and licenses separately | Never redistribute REAPER binaries/installers/assets. TrackScribe's own Lua bridge remains MIT | **GREEN** for bridge-only source |

## Supporting numerical/audio libraries

These libraries are installed into ignored environments, not committed to the
source tree. Versions are pinned in `requirements/*.txt`.

| Component | Audited version(s) | Declared/upstream license | Current distribution status |
| --- | --- | --- | --- |
| PyTorch | 2.13.0+cu130 | BSD-style PyTorch license plus bundled third-party notices | External wheel only; **GREEN** for source repo |
| torchaudio | 2.11.0 / 2.11.0+cu130 | BSD-2-Clause | External wheel only; **GREEN** |
| ONNX Runtime GPU | 1.29.0 | MIT | External wheel only; **GREEN** |
| librosa | 0.11.0 (core; other env snapshots may differ) | ISC | External wheel only; **GREEN** |
| pretty_midi | 0.2.11.post0 | MIT | External wheel only; **GREEN** |
| NumPy | 2.5.2 | BSD-3-Clause with bundled notices | External wheel only; **GREEN** |

Full package snapshots and environment counts are recorded in
`docs/DEPENDENCIES.md` and `requirements/`.

## Decisions and restrictions

1. **TrackScribe source may be published under MIT.** The repository does not
   contain external model weights, Python environments, FFmpeg/uv binaries,
   external repositories, ACE-Step, or REAPER.
2. **The complete default workflow is not cleared for unrestricted commercial
   use.** ADTOF is the decisive restriction; pretrained Demucs weights also carry
   a scientific-purpose-only upstream statement.
3. **No ADTOF or Demucs weights may be redistributed by the TrackScribe source
   release.** Setup/first-use access points to upstream sources and users remain
   responsible for complying with their terms.
4. **Mega53 stays experimental and external.** Its exact artifact hashes are
   known, but its model license is marked `not-reviewed` by the downloader's own
   registry.
5. **Future frozen EXE/installers require a new audit.** Bundling Qt DLLs,
   FFmpeg, CUDA/PyTorch runtimes, models, or any checkout materially changes the
   distribution analysis.

## Recommended follow-up

- Ask ADTOF-pytorch's author to add an explicit source license and clarify the
  converted checkpoint's license.
- Ask original ADTOF rights holders whether commercial inference and automatic
  user-side checkpoint download may be licensed separately.
- Obtain written clarification or use a separately trained/permissive drum model
  before marketing an unrestricted-commercial workflow.
- Obtain explicit model terms for Mega53 before redistributing it.
- Recheck every model card and upstream revision before each public release.
