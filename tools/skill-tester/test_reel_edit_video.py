#!/usr/bin/env python3
"""Strict-plan and real-media tests; requires no third-party Python packages.

Run: python3 tools/skill-tester/test_reel_edit_video.py
Fixtures and renderer staging stay beneath the repository, never system /tmp.
Live FFmpeg tests skip only when the installed executables are unavailable;
caption integration skips when FFmpeg was built without libass.
"""

import copy
import importlib.util
import json
import math
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills/reel/scripts/edit_video.py"
SPEC = importlib.util.spec_from_file_location("reel_edit_video", SCRIPT)
editor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(editor)


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix=".reel-plan-test-", dir=ROOT)
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name)
        self.media = self.base / "片 段 ' [x],;:foo.mp4"
        self.media.touch()
        self.plan = self.base / "plan.json"
        self.data = {
            "version": 1, "output": {"fps": 30, "width": 320, "height": 240},
            "clips": [{"path": self.media.name, "sourceStart": 0, "durationFrames": 60}],
        }
        self.filters = "\n".join(f" ... {name} A->A" for name in (
            "scale", "pad", "fps", "aresample", "amix", "alimiter", "xfade",
            "acrossfade", "ass", "sidechaincompress", "setpts", "asetpts", "trim",
            "atrim", "setsar", "settb", "format", "aformat", "apad", "volume",
            "concat", "anullsrc", "asplit", "afade"))
        self.probe = {"streams": [
            {"codec_type": "video", "duration": "10"},
            {"codec_type": "audio", "duration": "2"}],
            "format": {"duration": "10"}}
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(editor, "_tools", return_value={"ffmpeg": "ffmpeg", "ffprobe": "ffprobe"}).start()
        mock.patch.object(editor, "_probe", return_value=self.probe).start()
        mock.patch.object(editor, "_run", side_effect=lambda args, **kw:
                          self.filters if "-filters" in args else "libx264 aac").start()

    def validate(self, data=None):
        self.plan.write_text(json.dumps(self.data if data is None else data), encoding="utf-8")
        return editor.validate_plan(self.plan)

    def test_defaults_and_safe_local_filename(self):
        result = self.validate()
        self.assertEqual(result["clips"][0]["path"], str(self.media))
        self.assertEqual(result["audio"]["sourceVolume"], 1)
        self.assertEqual(result["durationFrames"], 60)
        self.assertEqual(result["durationSeconds"], 2)

    def test_three_clip_outgoing_overlap_math(self):
        self.data["clips"] = [copy.deepcopy(self.data["clips"][0]) for _ in range(3)]
        self.data["clips"][0]["transition"] = {"type": "fade", "durationFrames": 10}
        self.data["clips"][1]["transition"] = {"type": "fade", "durationFrames": 15}
        result = self.validate()
        self.assertEqual(result["durationFrames"], 155)
        self.assertAlmostEqual(result["durationSeconds"], 155 / 30)

    def test_invalid_shapes_and_scalar_values(self):
        cases = [
            (("version",), True), (("version",), 2), (("extra",), 1),
            (("output", "fps"), 29.97), (("output", "fps"), True),
            (("output", "width"), 321), (("output", "height"), 0),
            (("output", "extra"), 1), (("clips",), []), (("clips",), {}),
            (("clips", 0, "durationFrames"), 0), (("clips", 0, "durationFrames"), True),
            (("clips", 0, "sourceStart"), -1), (("clips", 0, "sourceStart"), float("nan")),
            (("clips", 0, "sourceStart"), float("inf")), (("clips", 0, "speed"), 2),
            (("clips", 0, "path"), "https://example.com/a.mp4"),
            (("clips", 0, "path"), "concat:a.mp4|b.mp4"),
            (("clips", 0, "path"), "file:local.mp4"),
            (("clips", 0, "path"), "//server/a.mp4"),
            (("clips", 0, "path"), "missing.mp4"),
            (("clips", 0, "path"), "."),
            (("audio",), {"sourceVolume": 2.1}),
            (("audio",), {"sourceVolume": False}),
            (("audio",), {"narration": {"path": self.media.name, "offset": 1}}),
            (("audio",), {"music": {"path": self.media.name, "loop": True}}),
            (("audio",), {"music": {"path": self.media.name, "ducking": "true"}}),
            (("audio",), {"music": {"path": self.media.name, "ducking": True}}),
            (("audio",), {"music": {"path": self.media.name, "fadeInFrames": 40, "fadeOutFrames": 40}}),
            (("captions",), {}), (("captions",), [{"startFrame": 0, "endFrame": 61, "text": "bad"}]),
            (("captions",), [{"startFrame": 1, "endFrame": 1, "text": "bad"}]),
            (("captions",), [{"startFrame": 0, "endFrame": 1, "text": ""}]),
            (("captions",), [{"startFrame": 0, "endFrame": 1, "text": "x", "font": "x"}]),
            (("attribution",), None), (("attribution",), {"text": "x", "license": "CC0"}),
            (("attribution",), {"text": "bad\x00text"}),
            (("attribution",), {"text": "x" * 1000}),
            (("attribution",), {"text": "\ud800"}),
        ]
        for keys, value in cases:
            with self.subTest(keys=keys, value=value):
                data = copy.deepcopy(self.data)
                item = data
                for key in keys[:-1]:
                    item = item[key]
                item[keys[-1]] = value
                with self.assertRaises(editor.EditError):
                    self.validate(data)

    def test_duplicate_keys_and_missing_required(self):
        self.plan.write_text('{"version":1,"version":1}', encoding="utf-8")
        with self.assertRaisesRegex(editor.EditError, "Duplicate"):
            editor.validate_plan(self.plan)
        del self.data["clips"][0]["sourceStart"]
        with self.assertRaisesRegex(editor.EditError, "missing"):
            self.validate()

    def test_overlap_collisions_and_unsupported_effects(self):
        for transition in ({"type": "wipe", "durationFrames": 10},
                           {"type": "fade", "durationFrames": 0},
                           {"type": "fade", "durationFrames": 60},
                           {"type": "fade", "durationFrames": 10, "easing": "linear"}):
            with self.subTest(transition=transition):
                data = copy.deepcopy(self.data)
                data["clips"].append(copy.deepcopy(data["clips"][0]))
                data["clips"][0]["transition"] = transition
                with self.assertRaises(editor.EditError):
                    self.validate(data)
        self.data["clips"][0]["transition"] = {"type": "fade", "durationFrames": 10}
        with self.assertRaises(editor.EditError):
            self.validate()
        self.data["clips"] = [copy.deepcopy(self.data["clips"][0]) for _ in range(3)]
        self.data["clips"][1]["durationFrames"] = 20
        del self.data["clips"][-1]["transition"]
        with self.assertRaisesRegex(editor.EditError, "colliding"):
            self.validate()

    def test_media_lengths_reject_freezing_looping_and_narration_truncation(self):
        self.data["clips"][0]["sourceStart"] = 9
        with self.assertRaisesRegex(editor.EditError, "Trim exceeds"):
            self.validate()
        self.data["clips"][0]["sourceStart"] = 0
        self.data["audio"] = {"music": {"path": self.media.name}}
        self.probe["streams"][1]["duration"] = "1.5"
        with self.assertRaisesRegex(editor.EditError, "Music must cover"):
            self.validate()
        self.data["audio"] = {"narration": {"path": self.media.name}}
        self.probe["streams"][1]["duration"] = "2.1"
        with self.assertRaisesRegex(editor.EditError, "truncation"):
            self.validate()

    def test_missing_audio_or_video_rejected(self):
        self.probe["streams"].pop(0)
        with self.assertRaisesRegex(editor.EditError, "No video"):
            self.validate()
        self.probe["streams"] = [{"codec_type": "video", "duration": "10"}]
        self.data["audio"] = {"music": {"path": self.media.name}}
        with self.assertRaisesRegex(editor.EditError, "No audio"):
            self.validate()

    def test_missing_libass_explicit_failure(self):
        self.filters = self.filters.replace(" ... ass A->A", "")
        for key, value in (
            ("captions", [{"startFrame": 0, "endFrame": 30, "text": "hello"}]),
            ("attribution", {"text": "Track — creator — license"}),
        ):
            with self.subTest(key=key):
                data = copy.deepcopy(self.data)
                data[key] = value
                with self.assertRaisesRegex(editor.EditError, "libass"):
                    self.validate(data)

    def test_native_validation_skips_only_render_capabilities(self):
        self.data["captions"] = [{"startFrame": 0, "endFrame": 30, "text": "Native caption"}]
        self.data["attribution"] = {"text": "Track — CC BY 4.0"}
        self.filters = ""
        self.plan.write_text(json.dumps(self.data), encoding="utf-8")
        with mock.patch.object(editor, "_run") as run:
            result = editor.validate_plan(self.plan, check_render_capabilities=False)
            run.assert_not_called()
        self.assertEqual(result["captions"], self.data["captions"])
        self.assertEqual(result["attribution"]["text"], self.data["attribution"]["text"])
        self.assertEqual(result["durationFrames"], 60)
        self.assertTrue(result["clips"][0]["hasAudio"])
        with self.assertRaisesRegex(editor.EditError, "libass"):
            editor.validate_plan(self.plan)
        with self.assertRaisesRegex(editor.EditError, "libass"):
            editor.render_plan(self.plan, self.base / "requires-libass.mp4")
        self.assertFalse((self.base / "requires-libass.mp4").exists())
        self.data["clips"][0]["sourceStart"] = 9
        self.plan.write_text(json.dumps(self.data), encoding="utf-8")
        with self.assertRaisesRegex(editor.EditError, "Trim exceeds"):
            editor.validate_plan(self.plan, check_render_capabilities=False)
        self.data["captions"][0]["endFrame"] = 61
        self.plan.write_text(json.dumps(self.data), encoding="utf-8")
        with self.assertRaisesRegex(editor.EditError, "caption.endFrame"):
            editor.validate_plan(self.plan, check_render_capabilities=False)

    def test_ass_content_never_becomes_filtergraph_or_override_tags(self):
        text = "Quotes ' : ; , [v] {\\pos(0,0)} \\N\nUnicode: 你好"
        self.data["captions"] = [{"startFrame": 0, "endFrame": 30, "text": text}]
        self.data["attribution"] = {"text": "Track — Owner — CC BY 4.0"}
        plan = self.validate()
        editor._write_ass(plan, self.base)
        content = (self.base / "overlay.ass").read_text(encoding="utf-8")
        self.assertIn("\\{\\\ufeffpos(0,0)\\} \\\ufeffN\\NUnicode: 你好", content)
        self.assertNotIn("{\\pos", content)
        self.assertNotIn("｛", content)
        self.assertIn("Track — Owner — CC BY 4.0", content)

    def test_existing_output_and_companion_are_unchanged(self):
        target = self.base / "out.mp4"
        target.write_bytes(b"existing")
        with self.assertRaisesRegex(editor.EditError, "overwrite"):
            editor.render_plan(self.plan, target)
        self.assertEqual(target.read_bytes(), b"existing")
        target.unlink()
        companion = Path(str(target) + ".licenses.txt")
        companion.write_text("existing license", encoding="utf-8")
        self.data["attribution"] = {"text": "license"}
        self.validate()
        with self.assertRaisesRegex(editor.EditError, "license companion"):
            editor.render_plan(self.plan, target)
        self.assertEqual(companion.read_text(), "existing license")
        self.assertFalse(target.exists())

    def test_dangling_output_symlink_not_overwritten(self):
        target = self.base / "out.mp4"
        target.symlink_to(self.base / "missing")
        with self.assertRaisesRegex(editor.EditError, "overwrite"):
            editor.render_plan(self.plan, target)
        self.assertTrue(target.is_symlink())

    def test_publication_race_preserves_other_writer_and_removes_staging(self):
        self.data["attribution"] = {"text": "Track — CC0"}
        self.validate()
        target = self.base / "out.mp4"

        def assemble(plan, paths, stage):
            target.write_bytes(b"racing writer")
            result = stage / "render.mp4"
            result.write_bytes(b"our render")
            return result

        with mock.patch.object(editor, "_normalize", return_value=self.media), \
                mock.patch.object(editor, "_assemble", side_effect=assemble):
            with self.assertRaisesRegex(editor.EditError, "publication"):
                editor.render_plan(self.plan, target)
        self.assertEqual(target.read_bytes(), b"racing writer")
        self.assertFalse(Path(str(target) + ".licenses.txt").exists())
        self.assertEqual(list(self.base.glob(".reel-edit-*")), [])

    def test_attribution_companion_preserves_text_exactly(self):
        self.data["attribution"] = {"text": "Track {original} \\ credits\nCC BY 4.0"}
        self.validate()
        target = self.base / "credits.mp4"

        def assemble(plan, paths, stage):
            result = stage / "render.mp4"
            result.write_bytes(b"verified by the mocked renderer")
            return result

        with mock.patch.object(editor, "_normalize", return_value=self.media), \
                mock.patch.object(editor, "_assemble", side_effect=assemble):
            result = editor.render_plan(self.plan, target)
        self.assertEqual(Path(result["licenseInfo"]).read_text(encoding="utf-8"),
                         self.data["attribution"]["text"])


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg/ffprobe unavailable")
class MediaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix=".reel-media-test-", dir=ROOT)
        cls.base = Path(cls.directory.name)
        try:
            cls.ffmpeg = shutil.which("ffmpeg")
            cls.ffprobe = shutil.which("ffprobe")
            for name, color, size, fps, frequency in (
                ("片 段 ' [x],;:1.mp4", "red", "320x180", 24, 440),
                ("silent.mp4", "green", "180x320", 30, None),
                ("third.mp4", "blue", "256x192", 15, 660),
            ):
                args = [cls.ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-n",
                        "-f", "lavfi", "-i", f"color=c={color}:s={size}:r={fps}:d=2"]
                if frequency:
                    args += ["-f", "lavfi", "-i", f"sine=frequency={frequency}:sample_rate=44100:duration=2"]
                args += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-threads", "1"]
                if frequency:
                    args += ["-c:a", "aac"]
                args += [str(cls.base / name)]
                editor._run(args)
            for name, seconds, frequency in (("music.wav", 8, 220), ("voice.wav", 1, 880)):
                editor._run([cls.ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-n",
                             "-f", "lavfi", "-i", f"sine=frequency={frequency}:sample_rate=48000:duration={seconds}",
                             "-c:a", "pcm_s16le", str(cls.base / name)])
            editor._run([
                cls.ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-n",
                "-f", "lavfi", "-i", "color=c=red:s=320x240:r=30:d=2",
                "-itsoffset", "0.5", "-f", "lavfi", "-i", "sine=frequency=440:duration=1.5",
                "-c:v", "libx264", "-threads", "1", "-c:a", "aac", str(cls.base / "delayed.mp4"),
            ])
        except Exception:
            cls.directory.cleanup()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="case-", dir=self.base)
        self.addCleanup(self.directory.cleanup)
        self.case = Path(self.directory.name)
        self.plan = self.case / "plan.json"
        self.target = self.case / "result ' [:],;你好.mp4"
        self.data = {
            "version": 1, "output": {"fps": 30, "width": 320, "height": 240},
            "clips": [
                {"path": str(self.base / "片 段 ' [x],;:1.mp4"), "sourceStart": .2, "durationFrames": 45},
                {"path": str(self.base / "silent.mp4"), "sourceStart": .1, "durationFrames": 45},
                {"path": str(self.base / "third.mp4"), "sourceStart": .2, "durationFrames": 45},
            ],
        }

    def render(self):
        self.plan.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")
        result = editor.render_plan(self.plan, self.target)
        probe = editor._probe(self.target, self.ffprobe, count=True)
        self.assertTrue(result["ok"])
        self.assertEqual(editor._stream(probe, "video")["codec_name"], "h264")
        self.assertEqual(editor._stream(probe, "audio")["codec_name"], "aac")
        self.assertEqual(editor._stream(probe, "audio")["sample_rate"], "48000")
        self.assertEqual(list(self.case.glob(".reel-edit-*")), [])
        self.assertAlmostEqual(float(probe["format"]["duration"]), result["durationSeconds"], delta=.05)
        return result, probe

    def rms(self, start, length=.2):
        samples = self.samples(start, length)
        return math.sqrt(sum(sample * sample for sample in samples) / len(samples))

    def samples(self, start, length=.2):
        args = [self.ffmpeg, "-v", "error", "-i", str(self.target), "-ss", str(start),
                "-t", str(length), "-vn", "-ac", "1", "-ar", "8000", "-f", "f32le", "pipe:1"]
        result = subprocess.run(args, capture_output=True, timeout=30, check=True)
        return struct.unpack("<" + "f" * (len(result.stdout) // 4), result.stdout)

    def tone_amplitude(self, start, frequency):
        samples = self.samples(start)
        real = sum(sample * math.cos(2 * math.pi * frequency * i / 8000) for i, sample in enumerate(samples))
        imaginary = sum(sample * math.sin(2 * math.pi * frequency * i / 8000) for i, sample in enumerate(samples))
        return math.hypot(real, imaginary) * 2 / len(samples)

    def pixel(self, at):
        result = subprocess.run(
            [self.ffmpeg, "-v", "error", "-i", str(self.target), "-ss", str(at), "-frames:v", "1",
             "-vf", "crop=2:2:(iw-2)/2:(ih-2)/2", "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1"],
            capture_output=True, timeout=30, check=True)
        return tuple(result.stdout[:3])

    def test_hard_cuts_mixed_dimensions_fps_and_audio_presence(self):
        result, probe = self.render()
        self.assertEqual(result["durationFrames"], 135)
        self.assertEqual(editor._stream(probe, "video")["nb_read_frames"], "135")
        self.assertGreater(self.rms(.5), .04)
        self.assertLess(self.rms(2), .001)
        self.assertGreater(self.rms(3.5), .04)

    def test_three_clips_fade_then_hard_cut(self):
        self.data["clips"][0]["transition"] = {"type": "fade", "durationFrames": 15}
        result, probe = self.render()
        self.assertEqual(result["durationFrames"], 120)
        self.assertEqual(editor._stream(probe, "video")["nb_read_frames"], "120")
        red, green, blue = self.pixel(1.25)
        self.assertTrue(70 < red < 190 and 20 < green < 110 and blue < 20, (red, green, blue))
        self.assertGreater(self.pixel(3)[2], 200)

    def test_three_clips_hard_cut_then_fade(self):
        self.data["clips"][1]["transition"] = {"type": "fade", "durationFrames": 15}
        result, _ = self.render()
        self.assertEqual(result["durationFrames"], 120)

    def test_three_clips_two_fades(self):
        for clip in self.data["clips"][:-1]:
            clip["transition"] = {"type": "fade", "durationFrames": 15}
        result, _ = self.render()
        self.assertEqual(result["durationFrames"], 105)

    def test_nondecimal_frame_timing_and_fades(self):
        self.data["output"]["fps"] = 24
        for clip in self.data["clips"]:
            clip["durationFrames"] = 24
        for clip in self.data["clips"][:-1]:
            clip["transition"] = {"type": "fade", "durationFrames": 5}
        result, _ = self.render()
        self.assertEqual(result["durationFrames"], 62)
        self.assertAlmostEqual(result["durationSeconds"], 62 / 24)

    def test_subframe_source_start_with_mixed_frame_rates(self):
        self.data["clips"][0]["sourceStart"] = .23
        self.data["clips"][2]["sourceStart"] = .23
        self.render()

    def test_playlist_input_is_not_a_self_contained_media_file(self):
        playlist = self.case / "list.ffconcat"
        playlist.write_text(f"ffconcat version 1.0\nfile '{self.base / 'silent.mp4'}'\n", encoding="utf-8")
        self.data["clips"] = [{"path": str(playlist), "sourceStart": 0, "durationFrames": 30}]
        self.plan.write_text(json.dumps(self.data), encoding="utf-8")
        with self.assertRaisesRegex(editor.EditError, "whitelist"):
            editor.validate_plan(self.plan)

    def test_music_narration_fades_and_ducking(self):
        self.data["audio"] = {
            "sourceVolume": 0,
            "music": {"path": str(self.base / "music.wav"), "volume": .5,
                      "fadeInFrames": 6, "fadeOutFrames": 15, "ducking": True},
            "narration": {"path": str(self.base / "voice.wav"), "volume": 1},
        }
        self.render()
        self.assertGreater(self.rms(.5), .05)
        self.assertGreater(self.rms(2), .02)
        self.assertLess(self.rms(4.4, .08), self.rms(2) * .4)
        self.assertLess(self.tone_amplitude(.5, 220), self.tone_amplitude(2, 220) * .7)
        self.assertGreater(self.tone_amplitude(.5, 880), .08)

    def test_explicit_source_mute_and_short_source_rejection(self):
        self.data["audio"] = {"sourceVolume": 0}
        self.render()
        self.assertLess(self.rms(.5), .001)
        self.data["clips"][0]["durationFrames"] = 90
        self.plan.write_text(json.dumps(self.data), encoding="utf-8")
        with self.assertRaisesRegex(editor.EditError, "Trim exceeds"):
            editor.validate_plan(self.plan)

    def test_source_audio_delay_is_preserved(self):
        self.data["clips"] = [{"path": str(self.base / "delayed.mp4"),
                               "sourceStart": 0, "durationFrames": 60}]
        self.render()
        self.assertLess(self.rms(.1), .001)
        self.assertGreater(self.rms(.7), .04)

    def test_caption_attribution_safe_paths_and_companion(self):
        filters = editor._run([self.ffmpeg, "-hide_banner", "-filters"])
        if not __import__("re").search(r"\s ass\s", filters):
            self.skipTest("Installed FFmpeg has no libass ass filter")
        self.data["captions"] = [{"startFrame": 0, "endFrame": 45,
                                  "text": "Hello ' ; : [out] {\\pos(0,0)} \\N\n你好"}]
        self.data["attribution"] = {"text": "Track — Creator — CC BY 4.0\nhttps://example.com/license"}
        result, _ = self.render()
        self.assertEqual(Path(result["licenseInfo"]).read_text(encoding="utf-8"),
                         self.data["attribution"]["text"])

    def test_native_caption_validation_keeps_real_media_checks(self):
        self.data["captions"] = [{"startFrame": 0, "endFrame": 30, "text": "Native caption"}]
        self.data["attribution"] = {"text": "Track — CC0"}
        self.plan.write_text(json.dumps(self.data), encoding="utf-8")
        with mock.patch.object(editor, "_check_render_capabilities") as capabilities:
            result = editor.validate_plan(self.plan, check_render_capabilities=False)
            capabilities.assert_not_called()
        self.assertEqual(result["durationFrames"], 135)
        self.assertTrue(result["clips"][0]["hasAudio"])
        self.assertFalse(result["clips"][1]["hasAudio"])
        self.assertEqual(result["attribution"]["text"], "Track — CC0")

    def test_cli_json_validation_errors_and_help(self):
        self.plan.write_text(json.dumps(self.data), encoding="utf-8")
        import sys
        result = subprocess.run([sys.executable, str(SCRIPT), "validate", str(self.plan)],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(json.loads(result.stdout)["durationFrames"], 135)
        self.plan.write_text('{"version": 2}', encoding="utf-8")
        result = subprocess.run([sys.executable, str(SCRIPT), "validate", str(self.plan)],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(json.loads(result.stdout)["ok"])
        result = subprocess.run([sys.executable, str(SCRIPT), "--help"],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0)
        self.assertIn("OUTGOING overlap", result.stdout)


if __name__ == "__main__":
    unittest.main()
