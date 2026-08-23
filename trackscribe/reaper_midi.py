"""Create REAPER transport copies that preserve MIDI absolute event times."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import mido

from trackscribe.reaper_artifacts import ReaperArtifact


CANONICAL_TEMPO = 500_000  # 120 BPM; matches the dedicated REAPER tab.


class _TempoMap:
    """Convert original absolute ticks to seconds across its global tempo events."""

    def __init__(self, midi: mido.MidiFile) -> None:
        events: list[tuple[int, int, int, int]] = []
        for track_index, track in enumerate(midi.tracks):
            tick = 0
            for event_index, message in enumerate(track):
                tick += int(message.time)
                if message.type == "set_tempo":
                    events.append((tick, track_index, event_index, int(message.tempo)))
        self.ticks_per_beat = midi.ticks_per_beat
        self.segments: list[tuple[int, float, int]] = [(0, 0.0, CANONICAL_TEMPO)]
        previous_tick = 0
        seconds = 0.0
        tempo = CANONICAL_TEMPO
        for tick, _track, _event, new_tempo in sorted(events):
            seconds += mido.tick2second(
                tick - previous_tick, self.ticks_per_beat, tempo
            )
            if tick == self.segments[-1][0]:
                self.segments[-1] = (tick, seconds, new_tempo)
            else:
                self.segments.append((tick, seconds, new_tempo))
            previous_tick, tempo = tick, new_tempo

    def seconds(self, tick: int) -> float:
        segment_tick, segment_seconds, tempo = self.segments[0]
        for candidate in self.segments[1:]:
            if candidate[0] > tick:
                break
            segment_tick, segment_seconds, tempo = candidate
        return segment_seconds + mido.tick2second(
            tick - segment_tick, self.ticks_per_beat, tempo
        )


def write_absolute_time_copy(source: Path, destination: Path) -> Path:
    """Rewrite only delta ticks/tempo metadata while preserving event semantics."""

    midi = mido.MidiFile(str(source), clip=True)
    tempo_map = _TempoMap(midi)
    output = mido.MidiFile(type=midi.type, ticks_per_beat=midi.ticks_per_beat)
    for track_index, track in enumerate(midi.tracks):
        target = mido.MidiTrack()
        output.tracks.append(target)
        if track_index == 0:
            target.append(mido.MetaMessage("set_tempo", tempo=CANONICAL_TEMPO, time=0))
        source_tick = 0
        target_tick = 0
        for message in track:
            source_tick += int(message.time)
            if message.type == "set_tempo":
                continue
            seconds = tempo_map.seconds(source_tick)
            absolute_target = round(
                mido.second2tick(seconds, midi.ticks_per_beat, CANONICAL_TEMPO)
            )
            delta = max(0, absolute_target - target_tick)
            target.append(message.copy(time=delta))
            target_tick = absolute_target
    destination.parent.mkdir(parents=True, exist_ok=True)
    output.save(str(destination))
    return destination


def prepare_reaper_media(
    project_dir: Path, artifacts: tuple[ReaperArtifact, ...]
) -> tuple[ReaperArtifact, ...]:
    """Return artifacts using canonical copies only for selected MIDI files."""

    media_dir = project_dir / "reaper" / "media"
    prepared: list[ReaperArtifact] = []
    for artifact in artifacts:
        if artifact.media_type != "midi":
            prepared.append(artifact)
            continue
        destination = media_dir / f"{artifact.key}.mid"
        write_absolute_time_copy(artifact.path, destination)
        prepared.append(replace(artifact, path=destination))
    return tuple(prepared)
