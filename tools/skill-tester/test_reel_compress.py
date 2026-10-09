#!/usr/bin/env python3
"""Run: python3 tools/skill-tester/test_reel_compress.py

Stdlib tests with generated local FFmpeg fixtures; no downloads/installations.
All fixture/staging directories are beneath this checkout, never system /tmp.
"""

import contextlib
import copy
from decimal import Decimal
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills/reel/scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("reel_compress", SCRIPTS / "compress_video.py")
compressor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(compressor)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ValidationTests(unittest.TestCase):
    def test_decimal_byte_ceiling(self):
        for value, expected in [(1, 1000000), (.2, 200000),
                                (Decimal("0.1234569"), 123456), (1.000001, 1000001)]:
            self.assertEqual(compressor._target_bytes(value), expected)
        for value in (True, "1", None, 0, -1, float("inf"), float("nan"),
                      Decimal("NaN"), 5000, .0000001):
            with self.subTest(value=value), self.assertRaises(compressor.CompressionError):
                compressor._target_bytes(value)

    def test_missing_dependency(self):
        with mock.patch.object(compressor.media.shutil, "which", return_value=None):
            with self.assertRaisesRegex(compressor.CompressionError, "Required executable"):
                compressor.preflight_compression()

    def test_missing_encoder_filter_muxer(self):
        valid = {"-encoders": " V..... libx264 test\n A..... aac test",
                 "-filters": " ..C scale test", "-muxers": " E mp4 test"}
        for absent in valid:
            def run(args, **kwargs):
                return "" if args[-1] == absent else valid[args[-1]]
            with self.subTest(absent=absent), mock.patch.object(
                    compressor.media, "preflight_media_tools",
                    return_value={"ffmpeg": "ffmpeg", "ffprobe": "ffprobe"}), mock.patch.object(
                    compressor.media, "_run", side_effect=run):
                with self.assertRaises(compressor.CompressionError):
                    compressor.preflight_compression()

    def test_dimensions_never_upscale_and_keep_exact_aspect(self):
        info = {"dimensions": (1920, 1080)}
        self.assertEqual(compressor._dimensions(info, None), (1920, 1080))
        self.assertEqual(compressor._dimensions(info, 2160), (1920, 1080))
        self.assertEqual(compressor._dimensions(info, 721), (1280, 720))
        self.assertEqual(compressor._dimensions(info, 719), (1248, 702))
        with self.assertRaises(compressor.CompressionError):
            compressor._dimensions({"dimensions": (1922, 1080)}, 720)

    def test_cli_rejects_combined_modes(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            compressor.main(["a.mp4", "--output", "b.mp4", "--target-mb", "1", "--crf", "23"])
        self.assertEqual(caught.exception.code, 2)

    def test_cli_rejects_nonnumeric_target(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            compressor.main(["a.mp4", "--output", "b.mp4", "--target-mb", "bad"])
        self.assertEqual(caught.exception.code, 2)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "Local FFmpeg/ffprobe unavailable")
class MediaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix=".reel-compress-test-", dir=ROOT)
        cls.addClassCleanup(cls.directory.cleanup)
        cls.base = Path(cls.directory.name)
        cls.tools = compressor.preflight_compression()
        cls.source = cls.base / "source ' [x],; 片段.mp4"
        cls.command([
            "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=24:duration=3",
            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=3",
            "-f", "lavfi", "-i", "sine=frequency=880:sample_rate=48000:duration=3",
            "-map", "0:v", "-map", "1:a", "-map", "2:a",
            "-vf", "noise=alls=40:allf=t:all_seed=42", "-c:v", "libx264", "-crf", "0",
            "-preset", "ultrafast", "-threads", "2", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-metadata:s:a:0", "language=eng",
            "-metadata:s:a:1", "language=fra", "-disposition:a:0", "default",
            "-disposition:a:1", "0", cls.source,
        ])
        cls.source_hash = digest(cls.source)
        cls.credits = Path(str(cls.source) + ".licenses.txt")
        cls.credits.write_bytes(b"Test fixture credits only; retain verbatim.\n")

    @classmethod
    def command(cls, args):
        completed = subprocess.run(
            [cls.tools["ffmpeg"], "-hide_banner", "-loglevel", "error", "-nostdin", "-n"]
            + [str(item) for item in args], capture_output=True, text=True, timeout=120,
        )
        if completed.returncode:
            raise AssertionError(completed.stderr)

    def setUp(self):
        self.output = self.base / (self._testMethodName + ".mp4")

    def tearDown(self):
        self.assertEqual(digest(self.source), self.source_hash)
        self.assertFalse(list(self.base.glob(".reel-compress-*")))

    def test_real_crf_smaller_full_duration_audio_credits(self):
        result = compressor.compress_video(self.source, self.output)
        self.assertTrue(result["ok"])
        self.assertEqual(result["method"], "crf")
        self.assertEqual(result["crf"], 23)
        self.assertLess(result["outputBytes"], result["sourceBytes"])
        self.assertEqual(result["outputBytes"], self.output.stat().st_size)
        self.assertEqual(result["sourceBytes"], self.source.stat().st_size)
        self.assertAlmostEqual(result["outputToSourceRatio"], result["outputBytes"] / result["sourceBytes"])
        self.assertEqual(result["dimensions"], [320, 240])
        self.assertEqual(result["frameCount"], 72)
        self.assertEqual(result["frameRate"], "24")
        self.assertAlmostEqual(result["durationSeconds"], 3, places=3)
        self.assertEqual(result["audioTracks"], 2)
        self.assertEqual(Path(result["licenseInfo"]).read_bytes(), self.credits.read_bytes())
        probe = compressor.media._probe(self.output, self.tools["ffprobe"], count=True)
        audio = [s for s in probe["streams"] if s["codec_type"] == "audio"]
        self.assertEqual([s["tags"]["language"] for s in audio], ["eng", "fra"])
        self.assertEqual([s["disposition"]["default"] for s in audio], [1, 0])
        self.assertEqual(probe["streams"][0]["nb_read_frames"], "72")

    def test_real_two_pass_hard_decimal_target(self):
        result = compressor.compress_video(self.source, self.output, target_mb=Decimal("0.1500019"))
        self.assertEqual(result["method"], "two-pass")
        self.assertEqual(result["targetBytes"], 150001)
        self.assertLessEqual(self.output.stat().st_size, 150001)
        self.assertLess(result["outputBytes"], self.source.stat().st_size)
        self.assertEqual(result["frameCount"], 72)
        self.assertEqual(result["audioTracks"], 2)
        self.assertLessEqual(result["attempts"], 3)

    def test_real_cli_downscale(self):
        completed = subprocess.run([
            sys.executable, str(SCRIPTS / "compress_video.py"), str(self.source),
            "--output", str(self.output), "--crf", "25", "--max-height", "120",
        ], capture_output=True, text=True, timeout=120)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result["dimensions"], [160, 120])
        self.assertEqual(result["sourceDimensions"], [320, 240])
        self.assertEqual(result["frameCount"], 72)

    def test_real_silent_video(self):
        source = self.base / "silent.mp4"
        self.command(["-i", self.source, "-map", "0:v", "-c", "copy", source])
        result = compressor.compress_video(source, self.output)
        self.assertEqual(result["audioTracks"], 0)
        self.assertIsNone(result["audioCodec"])
        self.assertIsNone(result["licenseInfo"])

    def test_real_fractional_frame_cadence_is_preserved(self):
        source = self.base / "fractional.mp4"
        self.command([
            "-f", "lavfi", "-i", "testsrc2=size=160x120:rate=30000/1001:duration=1.001",
            "-c:v", "libx264", "-crf", "0", "-preset", "ultrafast", "-threads", "2", source,
        ])
        result = compressor.compress_video(source, self.output, max_height=240)
        self.assertEqual(result["frameRate"], "30000/1001")
        self.assertEqual(result["frameCount"], 30)
        self.assertEqual(result["dimensions"], [160, 120])
        self.assertAlmostEqual(result["durationSeconds"], 1.001, places=3)

    def test_invalid_parameters_and_paths_before_encoding(self):
        cases = [{"crf": True}, {"crf": 52}, {"crf": 2.1}, {"crf": -1},
                 {"target_mb": 0}, {"target_mb": float("nan")},
                 {"target_mb": 1, "crf": 24}, {"max_height": True},
                 {"max_height": 0}, {"max_height": 5000}, {"max_height": 100.5}]
        for options in cases:
            with self.subTest(options=options), self.assertRaises(compressor.CompressionError):
                compressor.compress_video(self.source, self.output, **options)
        for path in ("https://example.invalid/a.mp4", "file:source.mp4", "//host/a.mp4",
                     "concat:one|two", self.base, self.base / "missing.mp4"):
            with self.subTest(path=path), self.assertRaises(compressor.CompressionError):
                compressor.compress_video(path, self.output)
        for path in (self.base / "out.mkv", self.base / "absent" / "out.mp4"):
            with self.assertRaises(compressor.CompressionError):
                compressor.compress_video(self.source, path)
        self.assertFalse(self.output.exists())

    def test_existing_and_dangling_symlink_outputs_are_untouched(self):
        self.output.write_bytes(b"existing")
        with self.assertRaisesRegex(compressor.CompressionError, "overwrite"):
            compressor.compress_video(self.source, self.output)
        self.assertEqual(self.output.read_bytes(), b"existing")
        self.output.unlink()
        self.output.symlink_to(self.base / "absent")
        with self.assertRaisesRegex(compressor.CompressionError, "overwrite"):
            compressor.compress_video(self.source, self.output)
        self.assertTrue(self.output.is_symlink())
        with self.assertRaisesRegex(compressor.CompressionError, "overwrite"):
            compressor.compress_video(self.source, self.source)

    def test_source_size_limits(self):
        empty = self.base / "empty.mp4"
        empty.touch()
        with self.assertRaisesRegex(compressor.CompressionError, "nonempty"):
            compressor.compress_video(empty, self.output)
        with mock.patch.object(compressor, "MAX_BYTES", self.source.stat().st_size - 1):
            with self.assertRaisesRegex(compressor.CompressionError, "4 GiB"):
                compressor.compress_video(self.source, self.output)

    def test_impossible_target_publishes_nothing(self):
        with self.assertRaisesRegex(compressor.CompressionError, "Impossible target"):
            compressor.compress_video(self.source, self.output, target_mb=.001)
        self.assertFalse(self.output.exists())
        self.assertFalse(Path(str(self.output) + ".licenses.txt").exists())

    def test_encoder_and_decode_failures_cleanup(self):
        for operation in ("_encode", "_verify"):
            with self.subTest(operation=operation), mock.patch.object(
                    compressor, operation, side_effect=compressor.CompressionError("forced failure")):
                with self.assertRaisesRegex(compressor.CompressionError, "forced failure"):
                    compressor.compress_video(self.source, self.output)
                self.assertFalse(self.output.exists())
                self.assertFalse(Path(str(self.output) + ".licenses.txt").exists())

    def test_no_saving_is_failure(self):
        def encode(source, target, *args):
            target.write_bytes(b"x" * source.stat().st_size)
        with mock.patch.object(compressor, "_encode", side_effect=encode):
            with self.assertRaisesRegex(compressor.CompressionError, "No size saving"):
                compressor.compress_video(self.source, self.output)
        self.assertFalse(self.output.exists())

    def test_target_retries_are_bounded_and_never_fallback(self):
        def encode(source, target, *args):
            target.write_bytes(b"x" * 200000)
        with mock.patch.object(compressor, "_encode", side_effect=encode) as encoded:
            with self.assertRaisesRegex(compressor.CompressionError, "three bounded"):
                compressor.compress_video(self.source, self.output, target_mb=.15)
            self.assertEqual(encoded.call_count, 3)
        self.assertFalse(self.output.exists())

    def test_publication_race_never_overwrites_and_rolls_back_credits(self):
        link = os.link
        def race(source, destination):
            if destination == self.output:
                self.output.symlink_to(self.base / "do-not-touch")
            return link(source, destination)
        with mock.patch.object(compressor.os, "link", side_effect=race):
            with self.assertRaisesRegex(compressor.CompressionError, "nothing published"):
                compressor.compress_video(self.source, self.output)
        self.assertTrue(self.output.is_symlink())
        self.assertFalse((self.base / "do-not-touch").exists())
        self.assertFalse(Path(str(self.output) + ".licenses.txt").exists())

    def test_existing_credit_companion_is_not_overwritten(self):
        companion = Path(str(self.output) + ".licenses.txt")
        companion.write_bytes(b"existing credits")
        with self.assertRaisesRegex(compressor.CompressionError, "license companion"):
            compressor.compress_video(self.source, self.output)
        self.assertEqual(companion.read_bytes(), b"existing credits")
        self.assertFalse(self.output.exists())

    def test_unsafe_source_credit_companions_fail_without_blocking(self):
        source = self.base / "unsafe-credits.mp4"
        shutil.copyfile(self.source, source)
        companion = Path(str(source) + ".licenses.txt")
        companion.symlink_to(self.credits)
        with self.assertRaises(compressor.CompressionError):
            compressor.compress_video(source, self.output)
        self.assertFalse(self.output.exists())
        companion.unlink()
        os.mkfifo(companion)
        with self.assertRaisesRegex(compressor.CompressionError, "regular file"):
            compressor.compress_video(source, self.output)
        self.assertFalse(self.output.exists())

    def test_actual_subtitle_track_rejected(self):
        subtitle = self.base / "captions.srt"
        subtitle.write_text("1\n00:00:00,000 --> 00:00:02,000\nCaption\n")
        source = self.base / "subtitled.mp4"
        self.command(["-i", self.source, "-i", subtitle, "-map", "0", "-map", "1",
                      "-c", "copy", "-c:s", "mov_text", source])
        with self.assertRaisesRegex(compressor.CompressionError, "subtitle"):
            compressor.compress_video(source, self.output)
        self.assertFalse(self.output.exists())

    def test_actual_chapters_and_rotation_rejected(self):
        metadata = self.base / "chapters.ffmetadata"
        metadata.write_text(";FFMETADATA1\n[CHAPTER]\nTIMEBASE=1/1000\nSTART=0\nEND=2000\ntitle=Chapter\n")
        source = self.base / "chapters.mp4"
        self.command(["-i", self.source, "-i", metadata, "-map", "0", "-map_chapters", "1",
                      "-c", "copy", source])
        with self.assertRaisesRegex(compressor.CompressionError, "Chapters"):
            compressor.compress_video(source, self.output)
        rotated = self.base / "rotated.mp4"
        help_text = compressor.media._run([self.tools["ffmpeg"], "-hide_banner", "-h", "full"])
        rotation_input = ["-display_rotation:v:0", "90"] if "-display_rotation" in help_text else []
        self.command(rotation_input + ["-i", self.source, "-map", "0", "-c", "copy",
                                      "-metadata:s:v:0", "rotate=90", rotated])
        with self.assertRaisesRegex(compressor.CompressionError, "Rotation"):
            compressor.compress_video(rotated, self.output)
        self.assertFalse(self.output.exists())

    def test_unsupported_stream_metadata_rejected(self):
        original = compressor.media._probe(self.source, self.tools["ffprobe"])
        cases = [
            ("pix_fmt", "yuv420p10le"), ("sample_aspect_ratio", "4:3"),
            ("field_order", "tt"), ("color_transfer", "smpte2084"),
            ("color_primaries", "bt2020"), ("closed_captions", 1),
            ("side_data_list", [{"side_data_type": "Display Matrix", "rotation": 90}]),
            ("width", 319), ("duration", "3601"),
        ]
        for field, value in cases:
            probe = copy.deepcopy(original)
            probe["streams"][0][field] = value
            with self.subTest(field=field), mock.patch.object(
                    compressor.media, "_probe", return_value=probe), self.assertRaises(compressor.CompressionError):
                compressor.compress_video(self.source, self.output)
        for kind in ("data", "attachment", "video"):
            probe = copy.deepcopy(original)
            probe["streams"].append({"codec_type": kind})
            with self.subTest(kind=kind), mock.patch.object(
                    compressor.media, "_probe", return_value=probe), self.assertRaises(compressor.CompressionError):
                compressor.compress_video(self.source, self.output)

    def test_frame_captions_hdr_and_vfr_rejected(self):
        info = compressor._inspect(self.source, self.tools)
        for side in ("A/53 Closed Captions", "Mastering display metadata", "Unknown"):
            raw = {"frames": [{"best_effort_timestamp_time": "0", "side_data_list": [
                {"side_data_type": side}]}]}
            with self.subTest(side=side), mock.patch.object(compressor.media, "_run", return_value=json.dumps(raw)):
                with self.assertRaisesRegex(compressor.CompressionError, "side data"):
                    compressor._timeline(self.source, self.tools, info)
        raw = {"frames": [{"best_effort_timestamp_time": str(value)} for value in (0, .041667, .15)]}
        with mock.patch.object(compressor.media, "_run", return_value=json.dumps(raw)):
            with self.assertRaisesRegex(compressor.CompressionError, "Variable frame cadence"):
                compressor._timeline(self.source, self.tools, info)

    def test_verification_catches_dropped_frames_audio_and_decode_failure(self):
        output = self.base / "verify-valid.mp4"
        compressor.compress_video(self.source, output)
        info = compressor._inspect(self.source, self.tools)
        points = compressor._timeline(self.source, self.tools, info)
        with self.assertRaisesRegex(compressor.CompressionError, "duration/frame cadence"):
            compressor._verify(output, self.tools, info, points[:-1], (320, 240))
        missing_audio = copy.deepcopy(info)
        missing_audio["audio"].pop()
        with self.assertRaisesRegex(compressor.CompressionError, "audio track count"):
            compressor._verify(output, self.tools, missing_audio, points, (320, 240))
        original_run = compressor.media._run
        def run(args, **kwargs):
            if "-err_detect" in args and args[-1] == "-":
                raise compressor.CompressionError("full decode failed")
            return original_run(args, **kwargs)
        with mock.patch.object(compressor.media, "_run", side_effect=run):
            with self.assertRaisesRegex(compressor.CompressionError, "full decode failed"):
                compressor._verify(output, self.tools, info, points, (320, 240))


if __name__ == "__main__":
    unittest.main()
