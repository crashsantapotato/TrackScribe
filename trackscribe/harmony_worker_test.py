"""File-contract tests for disabled harmony cleanup behavior."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from trackscribe.workers.harmony_cleanup import copy_raw_midi


class HarmonyWorkerTests(unittest.TestCase):
    """Ensure the cleanup off switch is a lossless bypass."""

    def test_disabled_cleanup_preserves_midi_byte_for_byte(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = root / "harmony_raw.mid"
            final = root / "harmony.mid"
            raw.write_bytes(b"MThd\x00\x00\x00\x06raw-midi-notes")
            copy_raw_midi(raw, final)
            self.assertEqual(final.read_bytes(), raw.read_bytes())


if __name__ == "__main__":
    unittest.main()
