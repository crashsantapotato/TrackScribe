"""Unit tests for artifact filtering and shell-free REAPER dispatch."""

from __future__ import annotations

import unittest
import wave
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import mido

from trackscribe.reaper_artifacts import ReaperSelection, collect_reaper_artifacts
from trackscribe.reaper_bridge import (
    COMMON_REASCRIPT,
    find_reaper_executable,
    send_project_to_reaper,
    write_project_wrapper,
)
from trackscribe.reaper_midi import write_absolute_time_copy


def _midi(path: Path, *, notes: bool = True) -> None:
    midi = mido.MidiFile(type=0, ticks_per_beat=480)
    track = mido.MidiTrack()
    midi.tracks.append(track)
    if notes:
        track.append(mido.Message("note_on", note=60, velocity=90, time=0))
        track.append(mido.Message("note_off", note=60, velocity=0, time=240))
    midi.save(path)


def _wav(path: Path) -> None:
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(8000)
        stream.writeframes(b"\0\0" * 80)


class ReaperBridgeTest(unittest.TestCase):
    def _project(self, root: Path) -> Path:
        project = root / "Track with ünicode"
        (project / "midi").mkdir(parents=True)
        (project / "stems").mkdir()
        _midi(project / "midi" / "drums.mid")
        _midi(project / "midi" / "bass.mid", notes=False)
        _midi(project / "midi" / "harmony.mid")
        _wav(project / "stems" / "vocals.wav")
        return project

    def test_missing_optional_and_empty_midi_are_skipped(self) -> None:
        with TemporaryDirectory() as temporary:
            project = self._project(Path(temporary))
            artifacts, skipped = collect_reaper_artifacts(
                project, ReaperSelection(vocals=False)
            )
            self.assertEqual([item.key for item in artifacts], ["drums", "harmony"])
            reasons = {item.key: item.reason for item in skipped}
            self.assertEqual(reasons["bass"], "MIDI contains 0 notes")
            self.assertEqual(reasons["vocals"], "not selected")

    def test_wrapper_calls_common_importer_and_escapes_paths(self) -> None:
        with TemporaryDirectory() as temporary:
            project = self._project(Path(temporary))
            artifacts, _ = collect_reaper_artifacts(project, ReaperSelection())
            wrapper = write_project_wrapper(project, artifacts)
            content = wrapper.read_text(encoding="utf-8")
            self.assertIn(COMMON_REASCRIPT.resolve().as_posix(), content)
            self.assertIn("importer.import", content)
            self.assertIn("import_result.tsv", content)
            self.assertIn("TrackScribe - Drums", content)
            self.assertIn("ünicode", content)

    def test_explicit_executable_discovery(self) -> None:
        with TemporaryDirectory() as temporary:
            executable = Path(temporary) / "reaper.exe"
            executable.touch()
            self.assertEqual(find_reaper_executable(executable), executable.resolve())

    def test_dispatch_uses_args_nonewinst_and_never_shell(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = self._project(root)
            executable = root / "reaper.exe"
            executable.touch()
            calls = []

            def launcher(command, **kwargs):
                calls.append((command, kwargs))
                return object()

            result = send_project_to_reaper(
                project, reaper_executable=executable, launcher=launcher
            )
            command, kwargs = calls[0]
            self.assertIsInstance(command, list)
            self.assertEqual(command[1], "-nonewinst")
            self.assertEqual(Path(command[2]), result.wrapper_path)
            self.assertIs(kwargs["shell"], False)
            self.assertEqual([item.key for item in result.imported], ["drums", "harmony", "vocals"])

    def test_common_lua_has_safe_timing_and_one_undo_block(self) -> None:
        source = COMMON_REASCRIPT.read_text(encoding="utf-8")
        self.assertIn("NEW_PROJECT_TAB = 40859", source)
        self.assertIn("SetMediaItemPosition(item, 0.0", source)
        self.assertIn('"D_PLAYRATE", 1.0', source)
        self.assertIn('"D_PITCH", 0.0', source)
        self.assertIn("Undo_BeginBlock2", source)
        self.assertIn("Undo_EndBlock2", source)
        self.assertNotIn("InsertMedia(", source)
        self.assertIn("SetTempoTimeSigMarker", source)

    def test_transport_copy_preserves_absolute_note_time_and_velocity(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "tempo-60.mid"
            midi = mido.MidiFile(type=0, ticks_per_beat=480)
            track = mido.MidiTrack()
            midi.tracks.append(track)
            track.append(mido.MetaMessage("set_tempo", tempo=1_000_000, time=0))
            track.append(mido.Message("note_on", note=64, velocity=77, time=480))
            track.append(mido.Message("note_off", note=64, velocity=0, time=240))
            midi.save(source)
            destination = write_absolute_time_copy(source, root / "reaper.mid")
            rewritten = mido.MidiFile(destination)
            self.assertAlmostEqual(rewritten.length, 1.5, places=3)
            notes = [
                message
                for message in rewritten.tracks[0]
                if message.type in {"note_on", "note_off"}
            ]
            self.assertEqual((notes[0].note, notes[0].velocity), (64, 77))


if __name__ == "__main__":
    unittest.main()
