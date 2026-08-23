# TrackScribe 0.1.0 public release audit

Audit date: 2026-08-23
Scope: local TrackScribe source repository and optional ACE-Step/REAPER boundaries
Runtime-tested public baseline: `cec2dbadf780daf8ce29510b784b68f948a03b4b`
Public `main`: **published**
`v0.1.0` tag and GitHub Release: **not created**
Final release-preparation GitHub Actions result: **pending after push**

## Recommended release status

# READY WITH DOCUMENTED RESTRICTIONS — TAG GATED ON FINAL CI

TrackScribe's own source tree is suitable for a public source release after the
owner reviews the final diff, license audit, and remaining release checklist,
and the final GitHub Actions run is green.
The complete ML workflow must **not** be described as unrestricted for
commercial use because external ADTOF and pretrained Demucs assets have material
restrictions. Mega53 model terms also remain unverified.

## Repository hygiene

Initial pre-publication audit state (historical):

- Git branch: `main`.
- Git remotes: none.
- Commits audited: 5.
- Tracked files before preparation: 103.
- Tracked source bytes before preparation: 392,888 bytes (0.375 MiB).
- Git loose-object storage: 274.51 KiB; no packs or garbage.

Prepared release candidate:

- Candidate files after final source/test additions: 115.
- Clean public source size remains under 0.5 MiB (approximately 0.45 MiB after
  this documentation update).
- Candidate is source/config/docs/tests only; `.git` is not part of the export.
- Added production ignore rules, text/binary attributes, license/docs, lightweight
  CI, and a release hygiene checker.

Removed as obsolete after reference/import search:

- `bass_sensitive.py` — unreferenced one-off local experiment with absolute
  developer input/output paths.
- `add_drum_velocity.py` — superseded by
  `trackscribe/workers/drum_velocity.py`.
- `add_guitar_velocity.py` — superseded by
  `trackscribe/workers/guitar_velocity.py`.
- `analyze_mega53_stems.py` — superseded by the packaged Mega53 analysis worker.
- `trackscribe/README.md` — stale duplicate of the public root README.

Retained intentionally:

- `mega53_fixed.yaml` — production Mega53 architecture/config input.
- `requirements-ui.txt` — compatibility include for the existing UI development
  command.

Test organization was not moved solely for appearance; the current colocated
backend tests and separate `ui_tests/` / `integration_tests/` are clear and a
mass refactor would add release risk.

## Ignored local installation state

The following valuable local resources were not removed and are excluded from
the release candidate:

- `.venv`, `.venv-ui`, `.venv-bass`, `.venv-piano`, `.venv-mega`, `.venv-amt`;
- `.bootstrap` and downloaded uv/managed Python;
- `models`, `checkpoints`, and all `*.pth`, `*.pt`, `*.ckpt`, `*.onnx`,
  `*.safetensors`;
- `projects`, logs, generated audio, and generated MIDI;
- `tools/ffmpeg` and `tools/instrument-agnostic-amt` external trees;
- machine-local config override.

No `git clean`, environment deletion, checkpoint deletion, or cache deletion was
performed.

## Secrets and personal data

The current candidate and every reachable commit were searched for Hugging Face
tokens, GitHub tokens, AWS-style keys, bearer credentials, authorization/token/
credential assignments, API credentials, and private-key markers.

- Confirmed secrets: **none found**.
- Private credential files: **none found**.
- Private URLs or credential-bearing config: **none found**.
- The only `hf_`-like source match was the legitimate module/worker name for HF
  MIDI transcription, not a token.

The automated current-tree checker uses stronger token-shaped patterns so normal
identifiers do not become false positives.

## Large files and Git history

- Git object blobs inspected: 131.
- Largest historical blob: `trackscribe/ui/main_window.py`, 33,506 bytes.
- No large historical blob was found.
- No current or historical `wav`, `mp3`, `flac`, `ogg`, `m4a`, `aac`, `mid`,
  `midi`, `pth`, `pt`, `ckpt`, `onnx`, `safetensors`, `bin`, `exe`, `dll`, `zip`,
  or `7z` artifact was found.
- No history rewrite was performed.

Older local commits contain non-sensitive developer paths in the now-deleted
`bass_sensitive.py` and older revisions of README/config. Current operational
source/config contains no required developer path; the bootstrap test retains
two path strings only as negative assertions. The existing history is now
published on public `main`; no amend, rebase, squash, or force-push was used
during final preparation.

## Portable configuration

`config/trackscribe.json` uses repository-relative venv, model, checkout, and
checkpoint paths. No machine-specific absolute path is required by TrackScribe
runtime configuration. `config/trackscribe.local.json` remains ignored for
explicit developer overrides. Pipeline config semantics and musical defaults
were not changed.

The public version has one source of truth:

```python
trackscribe.__version__ == "0.1.0"
```

## Bootstrap

`setup.bat`, `run.bat`, and `scripts/bootstrap.ps1` remain root-relative.
`run.bat` does not silently run setup; it gives an actionable message when the
UI environment is missing.

Pinned/bootstrap-verified inputs now include:

- uv 0.12.5 official ZIP and SHA-256;
- managed CPython 3.12.14;
- exact package snapshots for all six environments;
- Instrument-Agnostic AMT source commit and source-archive SHA-256;
- Gyan FFmpeg 8.1.2 essentials fallback URL and SHA-256;
- Mega53 download through the external downloader's recorded checkpoint/config
  SHA-256 values.

Normal setup performs full imports and exact critical-version checks. Structural
`-DryRun` checks only runtime presence, so it remains fast and does not initialize
heavy GPU libraries.

Clean exported-tree bootstrap dry run: **passed**; all six environments, AMT,
FFmpeg, and Mega53 were correctly reported as planned, and no file was created or
downloaded.

Full clean Windows acceptance from the published source baseline: **passed**.

- First `setup.bat`: exit 0 in 405.54 seconds; all six environments healthy.
- Mega53 checkpoint: 1,368,919,887 bytes with the pinned SHA-256 verified.
- CUDA 13.0: healthy across all GPU environments on an NVIDIA RTX 4070 Ti SUPER.
- FFmpeg 9.0 system integration and the PySide6 `run.bat` launch: verified.
- Clean first-launch backend: Agnostic AMT; output root resolved to the clean
  installation's `projects` directory.
- Targeted real HF bass download/runtime: passed, including Unicode output under
  the legacy Windows CP1251 scenario.
- Full synthetic `preserve-harmony` + Agnostic AMT pipeline: all eight production
  stages completed.
- MP3 and every documented non-WAV decode smoke: passed.
- Second `setup.bat`: exit 0 in 32.73 seconds; uv, managed Python, all six
  environments, AMT source, Mega53 checkpoint, and FFmpeg were reused without
  unnecessary large downloads.
- Git remained clean after every setup/runtime/UI checkpoint.

This demonstrates setup reuse/idempotency on the acceptance machine; it is not a
guarantee for every Windows host.

## Tests

Final local release verification plus the separate clean runtime acceptance:

| Suite | Result |
| --- | --- |
| Backend/unit | 87 passed |
| Qt UI (offscreen) | 45 passed |
| Bridge/REAPER integration | 10 passed |
| **TrackScribe total** | **142/142 passed** |

The clean acceptance had a working FFmpeg and the real container-decode
integration passed. GitHub Actions may explicitly skip that one test when its
lightweight runner has no FFmpeg; this is acceptable and is not a failure.

The GitHub Actions backend run immediately before this final preparation had two
CI-only Windows 8.3-path assertion failures and one explicit FFmpeg skip. The
assertions now compare filesystem identity rather than lexical aliases without
changing production bootstrap/hash code. This document does not claim the final
workflow is green until GitHub Actions confirms the pushed preparation commit.

Additional verification:

- source compile: passed (current and clean export);
- core import and CLI `--help`: passed;
- PowerShell parser check: passed;
- bootstrap dry run in clean export: passed;
- release hygiene in current and clean export: passed;
- Git whitespace check: passed before the final preparation commit and required
  once more after any owner edits.

Focused optional ACE-Step tests were run separately: **13 passed** across the
adapter, GPU coordinator, model handoff, presentation, and exact UI wiring. They
do not imply that the entire legacy ACE-Step suite was run or is green.

No copyrighted commercial recording is included in the repository or used as a
release test fixture. Manual development testing outside the release-fixture
scope is not covered by this statement.

## Licensing and model weights

The detailed evidence is in `LICENSE_AUDIT.md`. Release-level conclusions:

- TrackScribe-owned Python/Lua/PowerShell/batch/config/docs source: MIT, source
  release **GREEN**.
- Instrument-Agnostic AMT code and official HF model repo: MIT metadata,
  external/not bundled, **GREEN**.
- HF bass/guitar code and official model repo: MIT, external/not bundled,
  **GREEN**.
- Transkun package and bundled checkpoint: MIT package with no separate model
  exclusion found, but no independent model card; **YELLOW**.
- ADTOF-pytorch: no explicit source license; converted official ADTOF weights;
  original ADTOF is CC BY-NC-SA 4.0; **RED** for redistribution or an
  unrestricted-commercial claim.
- Demucs code: MIT; pretrained htdemucs_ft weights: maintainer says not MIT and
  scientific-purpose-only; **RED** for redistribution/unrestricted commercial
  claims.
- BS-Roformer-Infer code: MIT; exact Mega53 model registry says
  `license = "not-reviewed"`; external/experimental, **YELLOW**.
- PySide6 6.11.2: LGPL/GPL options (or commercial Qt terms), installed externally;
  **GREEN** for this source-only form. Frozen distribution requires a new audit.
- FFmpeg fallback: external GPLv3 static build, not in Git; **GREEN** for this
  source-only download architecture. Bundling requires a new audit.

## ACE-Step integration

ACE-Step is not vendored. The public TrackScribe JSONL bridge is included and the
integration contract is documented. The audited local ACE adapter targets commit
`1ddcfda4cbe69c972aae998e75a1a9de75089dd3` and its 13 focused tests pass.

The local ACE adapter still contains a developer fallback path; therefore no ACE
patch was exported into this release. A future public patch must require portable
`TRACKSCRIBE_ROOT` configuration and target the documented commit. This limits
distribution of the optional ACE UI adapter but does not block standalone
TrackScribe source publication.

## REAPER integration

Only TrackScribe-owned Lua/Python bridge source is included. REAPER binaries and
assets are absent. Unit/integration coverage validates exact artifacts,
missing/empty handling, safe argument-list subprocesses, wrapper escaping, a new
project tab, and absolute-time MIDI transport copies.

A real GUI smoke against an installed/licensed REAPER was not repeated during
this audit and remains on the owner checklist.

## Clean public tree

The candidate was copied from current tracked plus intended untracked,
non-ignored files into a temporary directory. It did not use any TrackScribe
venv, contained no `.git`, and was deleted after verification.

```text
.github/
config/
docs/
integration_tests/
reaper/
requirements/
scripts/
trackscribe/
ui_tests/
.gitattributes
.gitignore
CHANGELOG.md
LICENSE
LICENSE_AUDIT.md
PUBLIC_RELEASE_AUDIT.md
README.md
RELEASE_CHECKLIST.md
THIRD_PARTY_NOTICES.md
mega53_fixed.yaml
pipeline.py
requirements-ui.txt
run.bat
setup.bat
ui.py
```

The completed audit snapshot contains 115 files and remains under 0.5 MiB. The
count/size should be regenerated after any owner edits because documentation
changes alter the exact byte count.

## Public source vs commercial use

### A. May the TrackScribe source repository be published?

**Yes, with the included notices and owner release checklist.** External
environments, tools, checkouts, binaries, weights, caches, projects, and media are
not part of the source tree.

### B. May the entire workflow be advertised as unrestricted for commercial use?

**No. Commercial-use status: RESTRICTED / UNVERIFIED.** ADTOF provenance and
Demucs pretrained-weight terms are incompatible with that claim, and Mega53
needs clarification.

## Remaining owner actions

1. Read and accept `LICENSE_AUDIT.md` and this verdict.
2. Review `git status`, the final diff, and `git diff --check`.
3. Confirm the final GitHub Actions workflow is green; an explicit missing-FFmpeg
   skip is acceptable.
4. Optionally repeat the real REAPER GUI smoke on an installed/licensed REAPER.
5. Create `v0.1.0` and a GitHub Release only after separate owner approval.
