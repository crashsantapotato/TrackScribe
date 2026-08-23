"""Analyze Mega53 WAV activity and classify useful signal versus likely leakage."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import librosa
import numpy as np


def dbfs(value: float, floor: float = -120.0) -> float:
    """Convert a linear amplitude to dBFS with a stable silence floor."""

    return floor if value <= 1e-12 else float(20.0 * np.log10(value))


def analyze_file(path: Path) -> dict:
    """Measure loudness, activity ratio, and onset density for one stem."""

    y, sr = librosa.load(path, sr=None, mono=True)
    if not len(y):
        return {
            "name": path.stem,
            "path": str(path),
            "duration_s": 0.0,
            "rms_dbfs": -120.0,
            "p95_dbfs": -120.0,
            "peak_dbfs": -120.0,
            "active_ratio": 0.0,
            "onsets_per_s": 0.0,
        }
    hop = 512
    frame_rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=hop)[0]
    duration = len(y) / sr
    rms_db = dbfs(float(np.sqrt(np.mean(np.square(y)))))
    p95_db = dbfs(float(np.percentile(frame_rms, 95)))
    peak_db = dbfs(float(np.max(np.abs(y))))
    frame_db = librosa.amplitude_to_db(np.maximum(frame_rms, 1e-12), ref=1.0, top_db=None)
    activity_threshold = max(-50.0, p95_db - 18.0)
    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
    onset_frames = librosa.onset.onset_detect(
        onset_envelope=onset_env,
        sr=sr,
        hop_length=hop,
        backtrack=False,
        units="frames",
    )
    return {
        "name": path.stem,
        "path": str(path),
        "duration_s": duration,
        "rms_dbfs": rms_db,
        "p95_dbfs": p95_db,
        "peak_dbfs": peak_db,
        "active_ratio": float(np.mean(frame_db >= activity_threshold)),
        "onsets_per_s": len(onset_frames) / max(duration, 1e-6),
    }


def classify(rows: list[dict], settings: dict) -> None:
    """Mutate analyzed rows with conservative KEEP, REVIEW, or IGNORE labels."""

    strongest = max(row["rms_dbfs"] for row in rows)
    for row in rows:
        relative = row["rms_dbfs"] - strongest
        row["relative_db"] = relative
        if (
            relative >= settings["keep_relative_db"]
            and row["active_ratio"] >= settings["keep_active_ratio"]
            and row["p95_dbfs"] >= settings["keep_p95_dbfs"]
        ):
            status = "KEEP"
        elif (
            relative >= settings["review_relative_db"]
            and row["active_ratio"] >= settings["review_active_ratio"]
            and row["p95_dbfs"] >= settings["review_p95_dbfs"]
        ):
            status = "REVIEW"
        else:
            status = "IGNORE"
        if (
            status == "IGNORE"
            and relative >= settings["transient_review_relative_db"]
            and row["onsets_per_s"] >= settings["transient_review_onsets_per_s"]
            and row["peak_dbfs"] >= settings["transient_review_peak_dbfs"]
        ):
            status = "REVIEW"
        row["status"] = status


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path)
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--settings-json", default="{}")
    return parser


def main() -> None:
    """Analyze all WAVs in a folder and write machine-readable JSON and CSV reports."""

    args = _parser().parse_args()
    wavs = sorted(args.folder.glob("*.wav"))
    if not wavs:
        raise SystemExit(f"No WAV files found under: {args.folder}")
    settings = {
        "keep_relative_db": -18.0,
        "review_relative_db": -28.0,
        "keep_active_ratio": 0.02,
        "review_active_ratio": 0.005,
        "keep_p95_dbfs": -45.0,
        "review_p95_dbfs": -55.0,
        "transient_review_relative_db": -24.0,
        "transient_review_onsets_per_s": 0.08,
        "transient_review_peak_dbfs": -30.0,
    }
    settings.update(json.loads(args.settings_json))
    rows = [analyze_file(path) for path in wavs]
    classify(rows, settings)
    priority = {"KEEP": 0, "REVIEW": 1, "IGNORE": 2}
    rows.sort(key=lambda row: (priority[row["status"]], -row["rms_dbfs"]))
    summary = {
        status: sum(row["status"] == status for row in rows)
        for status in ("KEEP", "REVIEW", "IGNORE")
    }
    report = {"summary": summary, "stems": rows}
    args.json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    fieldnames = [
        "status", "name", "rms_dbfs", "relative_db", "p95_dbfs", "peak_dbfs",
        "active_ratio", "onsets_per_s", "duration_s", "path",
    ]
    with args.csv.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"KEEP={summary['KEEP']} | REVIEW={summary['REVIEW']} | IGNORE={summary['IGNORE']}")
    print(f"JSON saved: {args.json}")
    print(f"CSV saved: {args.csv}")


if __name__ == "__main__":
    main()
