# TrackScribe 0.1.0 release checklist

This checklist distinguishes automated evidence from owner/release-machine
decisions. Do not check an item based on an earlier release.

Clean-install/runtime evidence below was recorded on one Windows acceptance
machine. Final GitHub Actions confirmation for the release-preparation commit is
a separate gate and must not be inferred from local results.

## Repository

- [x] Review `git status --short` and the complete diff.
- [x] Confirm no `v0.1.0` tag or GitHub Release was created during preparation.
- [x] Run `python scripts/check_release_hygiene.py`.
- [x] Confirm no secrets or credentials exist in the current tree or history.
- [x] Confirm no developer paths are required by runtime source/config.
- [x] Confirm no `.venv*`, `.bootstrap`, models, checkpoints, external repos,
      projects, logs, user audio, or MIDI are tracked.
- [x] Confirm no copyrighted media fixture is present.
- [x] Retain the existing published history without amend/rebase/squash; confirm
      the current runtime/config has no required developer path.

## Licensing

- [ ] Owner reviews `LICENSE_AUDIT.md` and `THIRD_PARTY_NOTICES.md`.
- [x] Do not claim unrestricted commercial use while ADTOF/Demucs restrictions
      remain.
- [ ] Recheck official model cards and revisions immediately before publishing.
- [x] Confirm no third-party binary/model/source checkout was added to the release
      tree.

## Verification

- [x] Backend unit tests green.
- [x] Qt UI tests green with offscreen Qt.
- [x] Bridge/REAPER integration tests green.
- [x] Compile/import checks green.
- [x] `git diff --check` green.
- [x] Clean release-tree hygiene check green.
- [x] Clean release-tree `pipeline.py --help` starts.
- [x] Clean release-tree bootstrap `-DryRun` succeeds without downloads/writes.
- [x] Full setup tested in a clean Windows directory without using developer
      environments.
- [x] Setup second run verified idempotent on the acceptance machine.
- [x] Desktop UI starts from the clean installation.
- [x] Synthetic audio transcription smoke completes (no copyrighted fixture).
- [x] Real MP3 input and all supported non-WAV FFmpeg decode smokes pass.
- [x] CUDA backends and the full eight-stage Agnostic AMT pipeline pass.
- [x] Git remains clean after setup, pipeline, MP3, UI, and second setup.
- [ ] REAPER integration smoke completed on an installed/licensed REAPER.
- [ ] Focused ACE-Step optional integration tests green; report separately from
      the ACE legacy suite.

## Release

- [x] `trackscribe.__version__` is `0.1.0`.
- [x] Changelog date/version checked.
- [ ] Public release audit verdict reviewed.
- [x] Final release-preparation commit is a normal child of published history and
      contains only the Windows CI test fix plus documentation.
- [ ] GitHub Actions for the final release-preparation commit is green.
- [ ] Tag/version checked by owner.
- [x] No tag or GitHub Release was created during preparation.
- [ ] Tag push and GitHub Release happen only after separate owner approval.
