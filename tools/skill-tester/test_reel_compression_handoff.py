from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[2] / "skills/reel/scripts"
sys.path.insert(0, str(SCRIPTS))
import compress_video
import edit_video


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "Local FFmpeg/ffprobe unavailable")
class CompressionHandoffTests(unittest.TestCase):
    def test_rendered_reel_compresses_without_changing_master_or_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.mp4"
            subprocess.run([
                shutil.which("ffmpeg"), "-v", "error", "-f", "lavfi", "-i",
                "testsrc2=size=320x180:rate=30:duration=2",
                "-c:v", "mpeg4", "-q:v", "2", str(source),
            ], check=True, capture_output=True)
            plan = root / "edit-plan.json"
            plan.write_text(json.dumps({
                "version": 1, "output": {"fps": 30, "width": 320, "height": 180},
                "clips": [{"path": str(source), "sourceStart": 0, "durationFrames": 60}],
            }), encoding="utf-8")
            master = root / "master.mp4"
            edit_video.render_plan(plan, master)
            before = hashlib.sha256(master.read_bytes()).hexdigest()
            plan_before = plan.read_bytes()
            credits = Path(str(master) + ".licenses.txt")
            credits.write_text("Synthetic fixture; preserve this supplied credit.\n", encoding="utf-8")
            output = root / "delivery.mp4"
            result = compress_video.compress_video(master, output, crf=32)
            self.assertTrue(result["ok"])
            self.assertLess(output.stat().st_size, master.stat().st_size)
            self.assertEqual(hashlib.sha256(master.read_bytes()).hexdigest(), before)
            self.assertEqual(plan.read_bytes(), plan_before)
            self.assertEqual(Path(str(output) + ".licenses.txt").read_bytes(), credits.read_bytes())


if __name__ == "__main__":
    unittest.main()
