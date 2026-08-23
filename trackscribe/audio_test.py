"""Tests for the shared public input-audio contract."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from trackscribe.audio import (
    AUDIO_FILE_DIALOG_FILTER,
    SUPPORTED_AUDIO_EXTENSIONS,
    is_supported_audio,
)
from trackscribe.api import run_pipeline
from trackscribe.errors import PipelineError


class AudioInputContractTests(unittest.TestCase):
    """Keep backend and UI input format declarations synchronized."""

    def test_required_extensions_are_publicly_supported(self) -> None:
        self.assertEqual(
            SUPPORTED_AUDIO_EXTENSIONS,
            (".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac"),
        )

    def test_extension_matching_is_case_insensitive(self) -> None:
        self.assertTrue(is_supported_audio(Path("TRACK.MP3")))
        self.assertTrue(is_supported_audio(Path("TRACK.FLAC")))
        self.assertFalse(is_supported_audio(Path("TRACK.WMA")))

    def test_file_dialog_filter_is_derived_from_shared_extensions(self) -> None:
        for extension in SUPPORTED_AUDIO_EXTENSIONS:
            self.assertIn(f"*{extension}", AUDIO_FILE_DIALOG_FILTER)
        self.assertIn("All files (*)", AUDIO_FILE_DIALOG_FILTER)

    def test_api_validation_accepts_every_supported_extension(self) -> None:
        class ReachedConfig(Exception):
            pass

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch(
                "trackscribe.api.PipelineConfig.load", side_effect=ReachedConfig
            ):
                for extension in SUPPORTED_AUDIO_EXTENSIONS:
                    with self.subTest(extension=extension):
                        source = root / f"input{extension}"
                        source.touch()
                        with self.assertRaises(ReachedConfig):
                            run_pipeline(source, root / "project")

    def test_api_rejects_unsupported_extension_before_loading_config(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "input.wma"
            source.touch()
            with (
                patch("trackscribe.api.PipelineConfig.load") as load_config,
                self.assertRaisesRegex(PipelineError, "Unsupported audio format"),
            ):
                run_pipeline(source, root / "project")
            load_config.assert_not_called()


if __name__ == "__main__":
    unittest.main()
