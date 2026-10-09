from __future__ import annotations

import importlib.util
import json
import math
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "skills/reel/scripts/analyze_media.py"
SPEC = importlib.util.spec_from_file_location("reel_media_analysis", SCRIPT)
media = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(media)


class AnalysisTests(unittest.TestCase):
    def test_measured_pulses_not_generated_grid(self):
        rate = 8000
        samples = [0] * (rate * 3)
        expected = [0.5, 1.0, 1.5, 2.0, 2.5]
        for second in expected:
            start = int(second * rate)
            for i in range(400):
                samples[start + i] = int(20000 * math.sin(i * 0.2))
        peaks = media.onset_candidates(samples)
        self.assertEqual(len(peaks), len(expected))
        for peak, second in zip(peaks, expected):
            self.assertAlmostEqual(peak["seconds"], second, delta=0.02)
            self.assertEqual(peak["frame"], round(second * 30))
        self.assertEqual(media.onset_candidates([0] * rate), [])

    def test_snapping_is_bounded_and_non_destructive(self):
        cuts = [30, 60, 90]
        result = media.snap_cuts(cuts, [10, 29, 62, 98], tolerance=3)
        self.assertEqual([r["proposedFrame"] for r in result], [29, 62, 90])
        self.assertEqual(cuts, [30, 60, 90])
        guarded = media.snap_cuts([12, 24], [14, 23])
        self.assertEqual([r["proposedFrame"] for r in guarded], [12, 24])
        for invalid in ([10, 9], [12, 12], [True], [-1]):
            with self.assertRaises(media.MediaError):
                media.snap_cuts(invalid, [])

    def test_invalid_analysis_settings(self):
        for fps in (float("nan"), 0, True):
            with self.assertRaises(media.MediaError):
                media.onset_candidates([0], fps=fps)
        with self.assertRaises(media.MediaError):
            media.local_file("https://example.invalid/private.mov")

    def test_cli_rejects_invalid_or_mismatched_beat_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "beats.json"
            for evidence in (
                [],
                {"kind": "onset-candidates", "fps": 24, "candidates": []},
                {"kind": "onset-candidates", "fps": 30, "candidates": [None]},
                {"kind": "onset-candidates", "fps": 30, "candidates": [{"frame": True}]},
            ):
                source.write_text(json.dumps(evidence))
                result = subprocess.run([
                    sys.executable, str(SCRIPT), "snap", "--beats", str(source),
                    "--cuts", "30", "--fps", "30",
                ], capture_output=True, text=True)
                self.assertEqual(result.returncode, 1)
                self.assertIn("media analysis failed:", result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "requires FFmpeg")
    def test_real_probe_storyboard_and_audio(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "sample with spaces.mp4"
            subprocess.run([
                "ffmpeg", "-v", "error", "-nostdin",
                "-f", "lavfi", "-i", "color=c=blue:s=96x64:r=30:d=2",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
                "-c:v", "libx264", "-c:a", "aac", "-shortest", str(source),
            ], check=True, capture_output=True)
            self.assertAlmostEqual(media.inspect_media(source)["durationSeconds"], 2, delta=0.1)
            result = media.storyboard(source, [0, 1, 1.9], root / "board")
            self.assertEqual(len(result["frames"]), 3)
            self.assertIn("not a semantic analysis", (root / "board/index.html").read_text())
            with self.assertRaises(FileExistsError):
                media.storyboard(source, [0], root / "board")
            with self.assertRaises(media.MediaError):
                media.storyboard(source, [2], root / "invalid")
            self.assertFalse((root / "invalid").exists())
            beats = media.analyze_beats(source)
            self.assertTrue(beats["reviewRequired"])
            self.assertEqual(beats["kind"], "onset-candidates")


if __name__ == "__main__":
    unittest.main()
