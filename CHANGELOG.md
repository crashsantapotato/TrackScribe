# Changelog

All notable public changes are documented here.

## 0.1.0 - 2026-08-23

- Added standalone PySide6 desktop UI and root-relative Windows bootstrap.
- Added common audio input preparation for WAV, MP3, FLAC, OGG, M4A, and AAC.
- Added htdemucs_ft drums, bass, vocals, and other separation; `other.wav` feeds
  harmony transcription.
- Added ADTOF drum transcription and HF bass transcription.
- Added Instrument-Agnostic AMT and Transkun harmony backends with raw compare
  mode.
- Added audio-derived MIDI velocity and conservative harmony cleanup.
- Added structured project manifests, progress reporting, cache, and resume.
- Added experimental Mega53 detailed-stems mode.
- Added optional REAPER project bridge.
- Added the public TrackScribe-side JSONL bridge and integration contract for
  optional ACE-Step handoff; the ACE-Step-side UI/GPU adapter is not shipped.
- Added public-source license, dependency notices, license audit, release hygiene,
  and lightweight CI preparation.
- Added process-scoped UTF-8 handling for bootstrap and runtime Python workers on
  legacy Windows code pages.
- Made Windows bootstrap diagnostic-path tests portable across 8.3 short-path
  aliases and canonical long paths without weakening SHA-256 assertions.
- Verified the public source with a full clean Windows setup, real eight-stage
  synthetic pipeline, non-WAV decoding, desktop launch, and a second idempotent
  setup run.
