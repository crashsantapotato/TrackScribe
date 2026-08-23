# Dependency and environment inventory

Audit date: 2026-08-23. All six environments were inspected with
`importlib.metadata` under CPython 3.12.14. Package `License` fields are useful
inventory data but are not treated as licenses for model weights.

| Environment | Purpose | Installed distributions observed | Exact manifest |
| --- | --- | ---: | --- |
| `.venv` | separation, ADTOF, velocity/audio processing | 63 | [`requirements/core.txt`](../requirements/core.txt) |
| `.venv-ui` | PySide6 desktop UI | 5 | [`requirements/ui.txt`](../requirements/ui.txt) |
| `.venv-bass` | HF bass/guitar transcription | 60 | [`requirements/bass.txt`](../requirements/bass.txt) |
| `.venv-piano` | Transkun | 48 | [`requirements/piano.txt`](../requirements/piano.txt) |
| `.venv-mega` | BS-Roformer/Mega53 | 29 | [`requirements/mega.txt`](../requirements/mega.txt) |
| `.venv-amt` | Instrument-Agnostic AMT runtime | 26 | [`requirements/amt.txt`](../requirements/amt.txt) |

The manifests are complete snapshots, not minimal dependency lists. `uv pip
sync` makes each environment match its own file exactly. Do not merge the
environments: their PyTorch/audio dependency graphs were validated separately.

## Critical direct pins

| Component | Exact pin/source | Environment |
| --- | --- | --- |
| audio-separator | 0.44.5 | core |
| ADTOF-pytorch | commit `85c192e78f716ea0b111cc8a5ee4a8f6a3a4f8a9` | core |
| PyTorch | 2.13.0+cu130 | GPU environments |
| ONNX Runtime GPU | 1.29.0 | core |
| librosa | 0.11.0 in core | core |
| NumPy | 2.5.2 | runtime environments |
| pretty_midi | 0.2.11.post0 | MIDI environments |
| PySide6 | 6.11.2 | UI |
| hf-midi-transcription | commit `96f6797881e9497cbfc8f8e5deccea9c1f2f7adc` (package 0.1.1) | bass |
| piano-transcription-inference fork | commit `7568dc7f78b625e40cf9776e2806d164006610e3` | bass |
| Transkun | 2.0.1 | piano |
| BS-Roformer-Infer | commit `b0f1386fcced25f559f3e61c9f08a73cd9bddf80` (package 0.1.6) | mega |
| torchaudio | 2.11.0 / 2.11.0+cu130 | piano/AMT |
| mido | 1.3.3 | MIDI environments |
| soundfile | 0.14.0 | audio environments |

## Non-package bootstrap assets

| Asset | Source | Integrity/provenance |
| --- | --- | --- |
| uv 0.12.5 | Official GitHub release | ZIP SHA-256 `4c4d49d8738847d9b71ba319e49a5688c93eac0fe6204b1df24e98528dddf39a` |
| CPython 3.12.14 | Managed by pinned uv | Installed below `.bootstrap/python`; not system Python |
| Instrument-Agnostic AMT source | Official commit archive `c210559a481ed22fc72af2f54e020250f9aabae1` | ZIP SHA-256 `eff3abd93ec953f637964f55c77e4a7a382052fc59cb34ef5bdbec5d0723ccee` |
| FFmpeg fallback | Gyan 8.1.2 essentials ZIP | SHA-256 `db580001caa24ac104c8cb856cd113a87b0a443f7bdf47d8c12b1d740584a2ec` |
| Mega53 checkpoint | ZFTurbo v1.0.21 via BS-Roformer registry | SHA-256 `c62820893bbf86d4e734f966bd142d9157cfc8bb8e79e9d8f9ea553f3ff3519f` |

## Model inventory

| Model | Filename(s) | Acquisition |
| --- | --- | --- |
| ADTOF | `adtof_frame_rnn_pytorch_weights.pth` | Bundled inside pinned external Python package |
| htdemucs_ft | `f7e0c4bc-ba3fe64a.th`, `d12395a8-e57c48e6.th`, `92cfc3b6-ef3bcb9c.th`, `04573f0d-f3cf25b2.th` | Lazy upstream download |
| HF bass/guitar | `filobass_20000_iterations.pth`, `guitar-gaps.pth` | Lazy official Hugging Face download |
| Transkun | `pretrained/2.0.pt` plus `2.0.conf` | Installed inside Transkun package |
| Agnostic AMT | `best_model_other.pth` | Lazy official Hugging Face download |
| Mega53 | `mvsep_mega_model_bs_roformer_53_stems_v1.ckpt` plus YAML | Setup via official package downloader |

Exact model hashes and separate license conclusions are in
[`LICENSE_AUDIT.md`](../LICENSE_AUDIT.md).

## Updating dependencies

An upgrade is not complete when `pip` succeeds. For the affected environment:

1. update only its manifest;
2. run bootstrap twice to check synchronization and idempotency;
3. run the complete lightweight test suite;
4. run the synthetic and backend-specific smoke checks;
5. verify CUDA availability and output provenance;
6. re-audit code and model licenses independently;
7. update this inventory and third-party notices.
