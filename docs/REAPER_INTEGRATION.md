# REAPER integration

REAPER support is optional. REAPER is proprietary software from Cockos and must
be installed and licensed separately. TrackScribe does not distribute a REAPER
executable, installer, extension, theme, or other proprietary asset.

## Included TrackScribe components

```text
reaper/TrackScribe_Import.lua
trackscribe/reaper_artifacts.py
trackscribe/reaper_bridge.py
trackscribe/reaper_discovery.py
trackscribe/reaper_midi.py
```

These files are TrackScribe-owned and covered by the repository MIT license.

## What Send to REAPER imports

Selected, non-empty project artifacts are imported into a new REAPER project
tab, each starting at 0 seconds:

| Track | Source | Default |
| --- | --- | --- |
| TrackScribe - Drums | `midi/drums.mid` | selected |
| TrackScribe - Bass | `midi/bass.mid` | selected |
| TrackScribe - Harmony | `midi/harmony.mid` | selected |
| TrackScribe - Vocals | `stems/vocals.wav` | selected, optional |

Missing files, unselected files, and MIDI files containing zero notes are
reported as skipped. TrackScribe never creates guessed replacement tracks.

## Timing policy

The generated musical MIDI is not edited in place. Before dispatch, TrackScribe
creates transport copies under `<project>/reaper/media/`:

- original absolute event seconds are calculated from the source tempo map;
- delta ticks are rewritten against a canonical 120 BPM map;
- note/message semantics are preserved;
- the REAPER project tab is set to 120 BPM;
- items use time attachment and start at 0 seconds.

This avoids preference-dependent MIDI import dialogs and keeps audio/MIDI aligned
in absolute time. It is a transport representation, not tempo detection or
quantization. The source project MIDI remains unchanged.

## Dispatch flow

The desktop UI and ACE integration call the same Python bridge. It discovers a
working `reaper.exe`, validates artifacts, writes a small generated project
wrapper under `<project>/reaper/import_to_reaper.lua`, and launches:

```text
reaper.exe -nonewinst <project-wrapper.lua>
```

Subprocesses use argument lists and `shell=False`. The common checked-in Lua
script opens a new project tab and writes an import report to
`<project>/reaper/import_result.tsv`.

Manual bridge invocation:

```powershell
.venv\Scripts\python.exe -m trackscribe.reaper_bridge --project projects\track_name
```

Use `--no-vocals` to omit the vocal WAV. Other selections have matching
`--no-drums`, `--no-bass`, and `--no-harmony` flags.

## Safety and limitations

- REAPER discovery checks explicit configuration and standard installation
  locations; it does not bundle or download REAPER.
- A new project tab is used so the active project is not overwritten.
- TrackScribe does not assign virtual instruments, mixing, routing, or tempo maps
  beyond the canonical import transport.
- REAPER behavior outside the tested bridge and API calls remains controlled by
  the user's REAPER installation and preferences.
