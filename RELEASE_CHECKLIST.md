# TrackScribe 0.1.0 release checklist

This checklist distinguishes automated evidence from owner/release-machine
decisions. Do not check an item based on an earlier release.

## Repository

- [ ] Review `git status --short` and the complete diff.
- [ ] Confirm no remote/push/tag/release was created during preparation.
- [ ] Run `python scripts/check_release_hygiene.py`.
- [ ] Confirm no secrets or credentials exist in the current tree or history.
- [ ] Confirm no developer paths are required by runtime source/config.
- [ ] Confirm no `.venv*`, `.bootstrap`, models, checkpoints, external repos,
      projects, logs, user audio, or MIDI are tracked.
- [ ] Confirm no copyrighted media fixture is present.
- [ ] Review historical local-path findings and decide whether the public branch
      should be a fresh/squashed source-release history.

## Licensing

- [ ] Owner reviews `LICENSE_AUDIT.md` and `THIRD_PARTY_NOTICES.md`.
- [ ] Do not claim unrestricted commercial use while ADTOF/Demucs restrictions
      remain.
- [ ] Recheck official model cards and revisions immediately before publishing.
- [ ] Confirm no third-party binary/model/source checkout was added to the release
      tree.

## Verification

- [ ] Backend unit tests green.
- [ ] Qt UI tests green with offscreen Qt.
- [ ] Bridge/REAPER integration tests green.
- [ ] Compile/import checks green.
- [ ] `git diff --check` green.
- [ ] Clean release-tree hygiene check green.
- [ ] Clean release-tree `pipeline.py --help` starts.
- [ ] Clean release-tree bootstrap `-DryRun` succeeds without downloads/writes.
- [ ] Full setup tested in a clean Windows directory without using developer
      environments.
- [ ] Setup second run verified idempotent.
- [ ] Desktop UI starts from the clean installation.
- [ ] Synthetic audio transcription smoke completes (no copyrighted fixture).
- [ ] REAPER integration smoke completed on an installed/licensed REAPER.
- [ ] Focused ACE-Step optional integration tests green; report separately from
      the ACE legacy suite.

## Release

- [ ] `trackscribe.__version__` is `0.1.0`.
- [ ] Changelog date/version checked.
- [ ] Public release audit verdict reviewed.
- [ ] Final commit created by owner: `Prepare TrackScribe 0.1.0 for public release`.
- [ ] Final commit is clean and contains only intended source/docs/config.
- [ ] Tag/version checked by owner.
- [ ] GitHub remote, repository, push, tag push, and release happen only after
      explicit owner approval.
