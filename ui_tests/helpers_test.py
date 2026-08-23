"""Unit tests for QSettings-independent desktop UI helpers."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from trackscribe.audio import SUPPORTED_AUDIO_EXTENSIONS
from trackscribe.harmony_backends import AGNOSTIC_AMT, COMPARE
from trackscribe.modes import PRESERVE_HARMONY
from trackscribe.types import ProgressEvent
from trackscribe.ui.helpers import (
    DEFAULT_OUTPUT_ROOT,
    PipelineJob,
    build_pipeline_kwargs,
    default_project_path,
    discover_artifacts,
    project_uses_resume,
    resolved_project_path,
    safe_project_name,
    stage_order_for_job,
    stage_view_state,
    validate_input,
    validate_output_root,
)


class HelpersTest(unittest.TestCase):
    """Exercise all filesystem and progress mapping without Qt widgets."""

    def test_safe_project_name(self) -> None:
        self.assertEqual(safe_project_name("Someone Like You.wav"), "Someone_Like_You")
        self.assertEqual(safe_project_name('bad<>:"/\\|?* name.wav'), "bad_name")
        self.assertEqual(safe_project_name("CON.wav"), "_CON")

    def test_default_project_path(self) -> None:
        root = Path("X:/TrackScribe")
        self.assertEqual(
            default_project_path("My_Track", root), root / "projects" / "My_Track"
        )

    def test_default_output_root_is_repository_projects(self) -> None:
        self.assertEqual(DEFAULT_OUTPUT_ROOT, Path(__file__).resolve().parents[1] / "projects")

    def test_custom_root_and_project_name_resolve_independently(self) -> None:
        root = Path("D:/TrackScribeProjects")
        self.assertEqual(
            resolved_project_path(root, "Billie_Jean"),
            root.resolve() / "Billie_Jean",
        )

    def test_output_root_validation_rejects_a_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output_file = root / "not-a-directory"
            output_file.touch()
            result = validate_output_root(output_file, "track")
            self.assertFalse(result.valid)
            self.assertIn("not a directory", result.message)

    def test_input_validation_accepts_existing_wav(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "track.wav"
            source.touch()
            result = validate_input(source, "track", root / "projects" / "track")
            self.assertTrue(result.valid, result.message)

    def _assert_extension_is_valid(self, extension: str) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / f"track{extension}"
            source.touch()
            result = validate_input(source, "track", root / "projects" / "track")
            self.assertTrue(result.valid, result.message)

    def test_input_validation_accepts_mp3(self) -> None:
        self._assert_extension_is_valid(".mp3")

    def test_input_validation_accepts_flac(self) -> None:
        self._assert_extension_is_valid(".flac")

    def test_input_validation_accepts_ogg(self) -> None:
        self._assert_extension_is_valid(".ogg")

    def test_input_validation_accepts_m4a(self) -> None:
        self._assert_extension_is_valid(".m4a")

    def test_input_validation_accepts_aac(self) -> None:
        self._assert_extension_is_valid(".aac")

    def test_input_validation_rejects_missing_and_wrong_extension(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            missing = validate_input(
                root / "missing.wav", "track", root / "projects" / "track"
            )
            self.assertFalse(missing.valid)
            source = root / "track.wma"
            source.touch()
            wrong_type = validate_input(
                source, "track", root / "projects" / "track"
            )
            self.assertFalse(wrong_type.valid)
            self.assertIn("Unsupported audio format", wrong_type.message)
            self.assertEqual(SUPPORTED_AUDIO_EXTENSIONS[0], ".wav")

    def test_artifact_discovery_finds_primary_and_compare_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            expected = (
                project / "midi" / "drums.mid",
                project / "midi" / "harmony.mid",
                project / "midi" / "ab" / "compare.json",
            )
            for path in expected:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
            (project / "stems").mkdir()
            discovery = discover_artifacts(project)
            self.assertEqual({item.path for item in discovery.artifacts}, set(expected))
            self.assertEqual(discovery.folders["midi"], project / "midi")
            self.assertEqual(discovery.folders["stems"], project / "stems")
            self.assertEqual(discovery.project_dir, project)

    def test_missing_artifacts_do_not_crash(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            discovery = discover_artifacts(Path(temporary) / "not-created")
            self.assertEqual(discovery.artifacts, ())
            self.assertEqual(discovery.folders, {})
            self.assertIsNone(discovery.project_dir)

    def test_existing_project_uses_resume_without_deletion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "projects" / "track"
            project.mkdir(parents=True)
            marker = project / "project.json"
            marker.write_text("{}", encoding="utf-8")
            self.assertTrue(project_uses_resume(project))
            job = PipelineJob(Path("input.wav"), project)
            kwargs = build_pipeline_kwargs(job, lambda event: None)
            self.assertFalse(kwargs["force"])
            self.assertTrue(marker.is_file())

    def test_cache_event_maps_to_cached_stage_state(self) -> None:
        job = PipelineJob(
            Path("input.wav"),
            Path("project"),
            harmony_backend=AGNOSTIC_AMT,
        )
        order = stage_order_for_job(job)
        event = ProgressEvent(
            stage="core_separation",
            status="cached",
            message="reused cached outputs",
            overall_progress=0.25,
        )
        state = stage_view_state(event, order)
        self.assertEqual(state.state, "Cached")
        self.assertEqual(state.prefix, "↻")
        self.assertEqual(state.index, 2)
        self.assertEqual(state.percent, 25)

    def test_compare_stage_order_uses_existing_backend_graph(self) -> None:
        job = PipelineJob(
            Path("input.wav"),
            Path("project"),
            harmony_backend=COMPARE,
            mode=PRESERVE_HARMONY,
        )
        order = stage_order_for_job(job)
        self.assertIn("harmony_compare", order)
        self.assertIn("harmony_amt_transcription", order)


if __name__ == "__main__":
    unittest.main()
