# ACE-Step integration

ACE-Step integration is optional. ACE-Step is a separate project and is not
vendored, installed, or relicensed by TrackScribe.

## Verified baseline

The local integration was audited against ACE-Step commit:

```text
1ddcfda4cbe69c972aae998e75a1a9de75089dd3
```

ACE-Step's local root `LICENSE` is MIT. Its model weights and other assets retain
their own terms. No ACE-Step source or asset is present in the TrackScribe public
tree.

## Integration contract

The ACE-side adapter:

1. receives the saved generated audio path;
2. derives a stable project name from a safe filename plus the audio SHA-256;
3. obtains an exclusive external GPU job slot;
4. releases/offloads ACE-Step DiT and language-model resources;
5. launches TrackScribe as a subprocess with `shell=False`;
6. reads newline-delimited JSON progress from `python -m trackscribe.bridge`;
7. keeps ACE models offloaded until the external job ends;
8. restores generation models lazily when the next ACE generation starts.

The TrackScribe side of this contract is public and UI-neutral:

```powershell
<TrackScribe>\.venv\Scripts\python.exe -m trackscribe.bridge `
  --input <generated-audio> `
  --output <project-directory> `
  --mode preserve-harmony `
  --harmony-backend agnostic-amt
```

It emits `stage`, `error`, and `completed` JSON objects on stdout. Human/backend
logs remain on stderr or in the project logs; the ACE adapter must not parse
human log text.

## ACE-side files audited

The working ACE tree contains a deliberately small integration layer:

```text
acestep/integrations/gpu_coordinator.py
acestep/integrations/model_handoff.py
acestep/integrations/trackscribe.py
acestep/ui/gradio/events/results/trackscribe_integration.py
acestep/ui/gradio/events/wiring/trackscribe_wiring.py
```

plus narrow UI wiring changes and colocated unit tests. The layer imports no
TrackScribe Python package into ACE's environment; all communication crosses a
subprocess boundary.

## Portable configuration requirement

The ACE-side working adapter resolves `TRACKSCRIBE_ROOT` from the environment.
Set it to the standalone installation before starting ACE-Step:

```powershell
$env:TRACKSCRIBE_ROOT = "C:\Apps\TrackScribe"
```

Do not publish a patch with a developer-specific fallback path. The currently
audited ACE working tree still has such a local fallback, so it is **not** copied
into this source release. Before a future public ACE patch is exported, replace
that fallback with explicit configuration/discovery and rerun its focused tests.

## Distribution decision

For TrackScribe 0.1.0 the public format is this protocol and integration guide,
not a vendored ACE-Step tree. A future optional patch/installer should:

- target the exact supported ACE-Step commit;
- include only the integration modules and minimal UI hunks;
- retain ACE-Step copyright/license headers;
- require explicit `TRACKSCRIBE_ROOT` configuration;
- include focused GPU handoff, adapter, presentation, and wiring tests;
- never include ACE models, environments, generated audio, or TrackScribe
  environments.

## Test boundary

TrackScribe standalone tests and ACE integration tests are reported separately.
The TrackScribe release does not claim that all legacy ACE-Step tests are green.
Only the focused integration tests are release evidence for this optional path.
