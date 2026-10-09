#!/usr/bin/env python3
"""Adapter contract tests with faithful doubles, NOT native Jianying verification.

Run: python3 tools/skill-tester/test_reel_jianying.py
No optional package is installed. Fixture files stay beneath the repository.
The actual edit_video validator runs; only FFmpeg probes/capability calls and
pyJianYingDraft are doubled. No native editor is opened or exported.
"""

import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import shutil
import sys
import types
import unittest
from unittest import mock
import uuid


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills/reel/scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("reel_export_jianying", SCRIPTS / "export_jianying.py")
adapter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adapter)


def fake_dependency(*, save_error=None, save_mode="valid"):
    """Mirror researched signatures, non-chainable tracks, and overlap checks."""
    module = types.ModuleType("pyJianYingDraft")
    module.__file__ = "faithful-test-double-not-an-installed-package"
    module.__version__ = "test-double"
    module.TrackType = types.SimpleNamespace(video="video", audio="audio", text="text")
    module.created = []

    class Timerange:
        def __init__(self, start, duration):
            assert type(start) is int and type(duration) is int
            assert start >= 0 and duration > 0
            self.start, self.duration = start, duration

    class TrackSpec:
        def __init__(self, track_type, name):
            self.type, self.name = track_type, name

    class ClipSettings:
        def __init__(self, *, transform_y=0):
            self.transform_y = transform_y

    class VideoSegment:
        def __init__(self, material, target_timerange, *, source_timerange=None, volume=1.0):
            assert Path(material).is_absolute() and Path(material).is_file()
            self.data = {"path": material, "start": target_timerange.start,
                         "duration": target_timerange.duration,
                         "sourceStart": source_timerange.start,
                         "sourceDuration": source_timerange.duration, "volume": volume}

    class AudioSegment(VideoSegment):
        def add_fade(self, in_duration, out_duration):
            assert type(in_duration) is int and type(out_duration) is int
            if "fade" in self.data:
                raise ValueError("fade already set")
            self.data["fade"] = {"in": in_duration, "out": out_duration}
            return self

    class TextSegment:
        def __init__(self, text, target_timerange, *, clip_settings=None):
            self.data = {"text": text, "start": target_timerange.start,
                         "duration": target_timerange.duration,
                         "transform_y": clip_settings.transform_y}

    class ScriptFile:
        def __init__(self, path):
            self.path, self.tracks = path, {}

        def append_tracks(self, tracks):
            for track in tracks:
                if track.name in self.tracks:
                    raise ValueError("duplicate track")
                self.tracks[track.name] = {"type": track.type, "segments": []}
            return tuple(tracks)

        def add_segment(self, segment, track_name):
            data = segment.data
            for previous in self.tracks[track_name]["segments"]:
                if max(data["start"], previous["start"]) < min(
                        data["start"] + data["duration"],
                        previous["start"] + previous["duration"]):
                    raise ValueError("overlapping segments")
            self.tracks[track_name]["segments"].append(copy.deepcopy(data))

        def save(self):
            if save_error:
                raise save_error
            if save_mode == "missing":
                return
            content = self.path / "draft_content.json"
            content.write_text(json.dumps({"tracks": self.tracks}), encoding="utf-8")
            (self.path / "draft_meta_info.json").write_text('{"draft_name":"fixture"}')
            if save_mode == "invalid":
                content.write_text("{not-json")
            elif save_mode == "empty":
                content.write_text("{}")

    class DraftFolder:
        def __init__(self, folder_path):
            self.path = Path(folder_path)
            assert self.path.is_dir()

        def create_draft(self, name, width, height, *, fps=30,
                         maintrack_adsorb=False, allow_replace=False):
            assert not allow_replace
            assert not maintrack_adsorb
            path = self.path / name
            path.mkdir()
            script = ScriptFile(path)
            module.created.append({"name": name, "width": width, "height": height,
                                   "fps": fps, "script": script})
            return script

    for cls in (Timerange, TrackSpec, ClipSettings, VideoSegment, AudioSegment,
                TextSegment, ScriptFile, DraftFolder):
        setattr(module, cls.__name__, cls)
    return module


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.base = ROOT / (".reel-jianying-test-" + uuid.uuid4().hex)
        self.base.mkdir()
        self.addCleanup(shutil.rmtree, self.base)
        self.media = self.base / "片 段.mp4"
        self.media.write_bytes(b"fake video bytes")
        self.music = self.base / "music.wav"
        self.music.write_bytes(b"fake music bytes")
        self.narration = self.base / "voice.wav"
        self.narration.write_bytes(b"fake narration bytes")
        self.path = self.base / "edit-plan.json"
        self.stage = self.base / "handoff"
        self.credit = "Song — Composer\nCC-BY-4.0; https://example.org/license"
        self.data = {
            "version": 1, "output": {"fps": 24, "width": 1280, "height": 720},
            "clips": [{"path": self.media.name, "sourceStart": 1.25, "durationFrames": 24},
                      {"path": self.media.name, "sourceStart": 4, "durationFrames": 12}],
            "audio": {
                "sourceVolume": 0.7, "music": {"path": self.music.name, "volume": 0.2,
                                            "ducking": False},
                "narration": {"path": self.narration.name, "volume": 0.9}},
            "captions": [{"startFrame": 0, "endFrame": 12, "text": "Hello"},
                         {"startFrame": 12, "endFrame": 24, "text": "世界"}],
            "attribution": {"text": self.credit},
        }
        self.filters = "\n".join(f" ... {name} A->A" for name in (
            "scale", "pad", "fps", "aresample", "amix", "alimiter", "xfade",
            "acrossfade", "ass", "sidechaincompress", "setpts", "asetpts", "trim",
            "atrim", "setsar", "settb", "format", "aformat", "apad", "volume",
            "concat", "anullsrc", "asplit", "afade"))
        self.dependency = fake_dependency()
        self.addCleanup(mock.patch.stopall)
        mock.patch.dict(sys.modules, {"pyJianYingDraft": self.dependency}).start()
        mock.patch.object(adapter.edit_video, "_tools",
                          return_value={"ffmpeg": "ffmpeg", "ffprobe": "ffprobe"}).start()
        mock.patch.object(adapter.edit_video, "_probe", side_effect=self.probe).start()
        mock.patch.object(adapter.edit_video, "_run", side_effect=lambda args, **kw:
                          self.filters if "-filters" in args else "libx264 aac").start()

    def probe(self, path, *_args, **_kwargs):
        if Path(path) == self.narration:
            return {"streams": [{"codec_type": "audio", "duration": "0.75"}]}
        return {"streams": [{"codec_type": "video", "duration": "10"},
                            {"codec_type": "audio", "duration": "10"}]}

    def write(self):
        self.path.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")

    def export(self, **kwargs):
        self.write()
        return adapter.export_plan(self.path, self.stage, target_app_version="user-requested-6.0",
                                   confirm_staging_only=True, **kwargs)

    def assert_no_output(self):
        self.assertFalse(self.stage.exists())

    def tracks(self, result):
        saved = Path(result["draftDirectory"]) / "draft_content.json"
        return json.loads(saved.read_text())["tracks"]

    def test_straight_cut_ranges_separate_audio_and_visible_credits(self):
        result = self.export()
        tracks = self.tracks(result)
        self.assertEqual(set(tracks), {"main_video", "music", "narration", "captions", "credits"})
        first, second = tracks["main_video"]["segments"]
        self.assertEqual((first["start"], first["duration"], first["sourceStart"]),
                         (0, 1000000, 1250000))
        self.assertEqual((second["start"], second["duration"], second["sourceStart"]),
                         (1000000, 500000, 4000000))
        self.assertEqual(first["sourceDuration"], 1000000)
        self.assertEqual(first["volume"], .7)
        self.assertEqual(tracks["music"]["segments"][0]["duration"], 1500000)
        self.assertEqual(tracks["music"]["segments"][0]["volume"], .2)
        self.assertEqual(tracks["narration"]["segments"][0]["duration"], 750000)
        self.assertEqual(tracks["narration"]["segments"][0]["volume"], .9)
        self.assertEqual(tracks["credits"]["segments"][0]["text"], self.credit)
        self.assertEqual(tracks["credits"]["segments"][0]["transform_y"], .8)
        self.assertEqual(tracks["captions"]["segments"][0]["transform_y"], -.8)
        self.assertEqual(self.dependency.created[0]["fps"], 24)
        self.assertEqual((self.dependency.created[0]["width"], self.dependency.created[0]["height"]),
                         (1280, 720))

    def test_all_media_copied_and_paths_remain_final(self):
        other = self.base / "other"
        other.mkdir()
        same_name = other / self.media.name
        same_name.write_bytes(b"second media with same name")
        self.data["clips"][1]["path"] = str(same_name)
        result = self.export()
        tracks = self.tracks(result)
        copied = [Path(clip["path"]) for clip in tracks["main_video"]["segments"]]
        self.assertNotEqual(copied[0], copied[1])
        self.assertEqual(copied[0].read_bytes(), self.media.read_bytes())
        self.assertEqual(copied[1].read_bytes(), same_name.read_bytes())
        for entry in result["media"]:
            self.assertTrue(Path(entry["copy"]).is_relative_to(self.stage))
            self.assertTrue(Path(entry["copy"]).is_file())
            self.assertNotEqual(entry["source"], entry["copy"])
        bundle = Path(result["handoffDirectory"])
        self.assertEqual((bundle / "original-edit-plan.json").read_bytes(), self.path.read_bytes())
        normalized = json.loads((bundle / "normalized-edit-plan.json").read_text())
        self.assertEqual(normalized["durationFrames"], 36)
        self.assertRegex(bundle.name, r"^emma-[0-9a-f]{32}$")

    def test_manifest_is_honest_and_persisted(self):
        result = self.export()
        persisted = json.loads((Path(result["handoffDirectory"]) / "handoff.json").read_text())
        self.assertEqual(result, persisted)
        self.assertTrue(result["generatedDraft"])
        self.assertFalse(result["nativeOpenVerified"])
        self.assertFalse(result["nativeExportVerified"])
        self.assertFalse(result["dependency"]["installedRevisionVerified"])
        self.assertEqual(result["requestedTargetAppVersion"], "user-requested-6.0")
        self.assertEqual(result["dependency"]["referenceRevision"], adapter.REFERENCE_REVISION)
        self.assertIn("UNVERIFIED", result["nativeCompatibility"])
        self.assertTrue(result["supportedScope"] and result["unsupportedScope"])

    def test_sidecars_and_license_evidence_preserved_byte_for_byte(self):
        metadata = self.music.with_name(self.music.name + ".json")
        metadata.write_text(json.dumps({"license": "CC-BY-4.0", "attributionRequired": True,
                                        "attributionText": self.credit}), encoding="utf-8")
        license_file = self.music.with_name(self.music.name + ".license.txt")
        license_file.write_text(self.credit + "\n\nOriginal license evidence\n")
        subtitle = self.media.with_suffix(".srt")
        subtitle.write_bytes(b"subtitle evidence")
        extra = self.base / "rights-evidence.txt"
        extra.write_bytes(b"supplied rights record")
        result = self.export(sidecars=[extra])
        sidecars = [item for entry in result["media"] for item in entry["sidecars"]]
        self.assertEqual(len(sidecars), 3)
        for item in sidecars + result["explicitSidecars"]:
            self.assertEqual(Path(item["source"]).read_bytes(), Path(item["copy"]).read_bytes())
        self.assertIn(self.credit, result["verbatimRequiredCredits"])

    def test_missing_or_modified_mandatory_credits_fail_before_mutation(self):
        metadata = self.music.with_name(self.music.name + ".json")
        for text, attribution in ((self.credit, None),
                                  (self.credit, {"text": "Paraphrased credit"}),
                                  (None, {"text": self.credit})):
            with self.subTest(text=text, attribution=attribution):
                metadata.write_text(json.dumps({"attributionRequired": True, "attributionText": text}))
                if attribution is None:
                    self.data.pop("attribution", None)
                else:
                    self.data["attribution"] = attribution
                with self.assertRaisesRegex(adapter.ExportError, "credit|attributionText"):
                    self.export()
                self.assert_no_output()

    def test_license_file_without_metadata_requires_verbatim_credit(self):
        self.music.with_name(self.music.name + ".license.txt").write_text("Different required credit\n")
        with self.assertRaisesRegex(adapter.ExportError, "verbatim"):
            self.export()
        self.assert_no_output()

    def test_cc_by_cannot_disable_credit_requirement(self):
        self.music.with_name(self.music.name + ".json").write_text(json.dumps({
            "license": "CC-BY-4.0", "attributionRequired": False}))
        with self.assertRaisesRegex(adapter.ExportError, "Mandatory"):
            self.export()
        self.assert_no_output()

    def test_music_fades_use_microseconds_before_track_insertion(self):
        self.data["audio"]["music"].update(fadeInFrames=6, fadeOutFrames=12)
        tracks = self.tracks(self.export())
        self.assertEqual(tracks["music"]["segments"][0]["fade"], {"in": 250000, "out": 500000})
        self.assertNotIn("fade", tracks["narration"]["segments"][0])
        self.assertNotIn("fade", tracks["main_video"]["segments"][0])

    def test_touching_music_fades_do_not_overlap_from_rounding(self):
        self.data["output"]["fps"] = 60
        self.data["clips"] = [{"path": self.media.name, "sourceStart": 0, "durationFrames": 2}]
        self.data["audio"].pop("narration")
        self.data["audio"]["music"].update(fadeInFrames=1, fadeOutFrames=1)
        self.data["captions"] = []
        tracks = self.tracks(self.export())
        music = tracks["music"]["segments"][0]
        self.assertEqual(music["fade"], {"in": 16667, "out": 16666})
        self.assertEqual(sum(music["fade"].values()), music["duration"])

    def test_unsupported_transitions_and_implicit_ducking(self):
        baseline = copy.deepcopy(self.data)
        cases = [
            ("transition", lambda d: d["clips"][0].update(
                transition={"type": "fade", "durationFrames": 6})),
            ("ducking", lambda d: d["audio"]["music"].update(ducking=True)),
            ("implicit ducking", lambda d: d["audio"]["music"].pop("ducking")),
        ]
        for label, mutate in cases:
            with self.subTest(label=label):
                self.data = copy.deepcopy(baseline)
                mutate(self.data)
                with self.assertRaisesRegex(adapter.ExportError, "Unsupported"):
                    self.export()
                self.assert_no_output()

    def test_unknown_filters_and_keyframes_use_actual_validator(self):
        for field in ("filters", "keyframes", "speed"):
            with self.subTest(field=field):
                self.data["clips"][0][field] = []
                with self.assertRaisesRegex(adapter.edit_video.EditError, "unknown fields"):
                    self.export()
                self.data["clips"][0].pop(field)
                self.assert_no_output()

    def test_validator_still_rejects_source_overrun(self):
        self.data["clips"][0]["sourceStart"] = 100
        with self.assertRaisesRegex(adapter.edit_video.EditError, "Trim exceeds"):
            self.export()
        self.assert_no_output()

    def test_native_text_does_not_require_libass_or_renderer_encoders(self):
        with mock.patch.object(adapter.edit_video, "_run",
                               side_effect=AssertionError("Native export must not probe renderer filters")):
            tracks = self.tracks(self.export())
        self.assertEqual(tracks["credits"]["segments"][0]["text"], self.credit)
        self.assertEqual(tracks["captions"]["segments"][0]["text"], "Hello")

    def test_silent_source_without_optional_tracks(self):
        self.data.pop("audio")
        self.data.pop("attribution")
        self.data.pop("captions")
        with mock.patch.object(adapter.edit_video, "_probe", return_value={
                "streams": [{"codec_type": "video", "duration": "10"}]}):
            tracks = self.tracks(self.export())
        self.assertEqual(set(tracks), {"main_video"})
        self.assertEqual(tracks["main_video"]["segments"][0]["volume"], 0)

    def test_duplicate_license_metadata_cannot_remove_mandatory_credits(self):
        self.music.with_name(self.music.name + ".json").write_text(
            '{"attributionRequired":true,"attributionRequired":false}')
        with self.assertRaisesRegex(adapter.edit_video.EditError, "Duplicate"):
            self.export()
        self.assert_no_output()

    def test_overlap_captions_rejected_but_unsorted_disjoint_supported(self):
        self.data["captions"][1]["startFrame"] = 6
        with self.assertRaisesRegex(adapter.ExportError, "overlapping captions"):
            self.export()
        self.assert_no_output()
        self.data["captions"][1]["startFrame"] = 12
        self.data["captions"].reverse()
        tracks = self.tracks(self.export())
        self.assertEqual([item["start"] for item in tracks["captions"]["segments"]], [0, 500000])

    def test_integer_microseconds_prevent_adjacent_frame_overlap(self):
        self.data["output"]["fps"] = 30
        self.data["clips"] = [{"path": self.media.name, "sourceStart": .034, "durationFrames": 1}
                              for _ in range(30)]
        self.data["captions"] = []
        tracks = self.tracks(self.export())
        segments = tracks["main_video"]["segments"]
        self.assertEqual(segments[0]["sourceStart"], 33333)
        self.assertEqual(segments[-1]["start"] + segments[-1]["duration"], 1000000)
        for left, right in zip(segments, segments[1:]):
            self.assertEqual(left["start"] + left["duration"], right["start"])

    def test_delayed_source_audio_rejected_unless_muted(self):
        original = self.probe

        def delayed(path, *_args, **_kwargs):
            result = original(path)
            if Path(path) == self.media:
                result["streams"][1]["start_time"] = "0.2"
            return result

        with mock.patch.object(adapter.edit_video, "_probe", side_effect=delayed):
            with self.assertRaisesRegex(adapter.ExportError, "audioOffset"):
                self.export()
            self.assert_no_output()
            self.data["audio"]["sourceVolume"] = 0
            tracks = self.tracks(self.export())
            self.assertEqual(tracks["main_video"]["segments"][0]["volume"], 0)

    def test_existing_output_never_overwritten(self):
        self.stage.mkdir()
        sentinel = self.stage / "keep.txt"
        sentinel.write_bytes(b"do not change")
        with self.assertRaisesRegex(adapter.ExportError, "absent or empty"):
            self.export()
        self.assertEqual(sentinel.read_bytes(), b"do not change")
        self.assertEqual(list(self.stage.iterdir()), [sentinel])

    def test_empty_existing_root_is_supported(self):
        self.stage.mkdir()
        self.assertTrue(self.export()["generatedDraft"])
        self.assertEqual(len(list(self.stage.iterdir())), 1)

    def test_second_export_to_used_staging_root_fails(self):
        result = self.export()
        before = (Path(result["draftDirectory"]) / "draft_content.json").read_bytes()
        with self.assertRaisesRegex(adapter.ExportError, "absent or empty"):
            self.export()
        self.assertEqual((Path(result["draftDirectory"]) / "draft_content.json").read_bytes(), before)

    def test_target_version_and_staging_attestation_required(self):
        self.write()
        for kwargs in ({"target_app_version": "", "confirm_staging_only": True},
                       {"target_app_version": "6.0"}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(adapter.ExportError):
                    adapter.export_plan(self.path, self.stage, **kwargs)
                self.assert_no_output()

    def test_native_database_and_symlink_destinations_rejected(self):
        for name in ("com.lveditor.draft", "JianyingPro", "CapCut"):
            with self.subTest(name=name):
                self.stage = self.base / name / "new"
                self.stage.parent.mkdir()
                with self.assertRaisesRegex(adapter.ExportError, "live editor"):
                    self.export()
                self.assert_no_output()
        self.stage = self.base / "ordinary" / "new"
        self.stage.parent.mkdir()
        (self.stage.parent / "root_meta_info.json").write_text("{}")
        with self.assertRaisesRegex(adapter.ExportError, "live editor"):
            self.export()
        self.stage = self.base / "link"
        self.stage.symlink_to(self.base, target_is_directory=True)
        with self.assertRaisesRegex(adapter.ExportError, "symlinks"):
            self.export()

    def test_symlink_sidecar_is_not_followed(self):
        secret = self.base / "private.txt"
        secret.write_text("not a supplied sidecar")
        self.music.with_name(self.music.name + ".json").symlink_to(secret)
        with self.assertRaisesRegex(adapter.ExportError, "non-symlink"):
            self.export()
        self.assert_no_output()

    def test_missing_dependency_json_failure_before_output(self):
        self.write()
        with mock.patch.dict(sys.modules, {"pyJianYingDraft": None}), contextlib.redirect_stdout(io.StringIO()) as out:
            code = adapter.main(["--plan", str(self.path), "--staging-root", str(self.stage),
                                 "--target-app-version", "6.0", "--confirm-staging-only"])
        result = json.loads(out.getvalue())
        self.assertEqual(code, 1)
        self.assertFalse(result["generatedDraft"])
        self.assertIn("dependency unavailable", result["error"])
        self.assert_no_output()

    def test_missing_and_old_api_fail_before_mutation(self):
        def old_create(self, name, width, height):
            raise AssertionError("must never call an incompatible constructor")

        with mock.patch.object(self.dependency.DraftFolder, "create_draft", old_create):
            with self.assertRaisesRegex(adapter.ExportError, "Incompatible"):
                self.export()
            self.assert_no_output()
        del self.dependency.ScriptFile.append_tracks
        with self.assertRaisesRegex(adapter.ExportError, "Incompatible"):
            self.export()
        self.assert_no_output()

    def test_save_failure_returns_actual_error_and_cleans_new_paths(self):
        failed = fake_dependency(save_error=OSError("simulated disk failure"))
        self.write()
        with mock.patch.dict(sys.modules, {"pyJianYingDraft": failed}), contextlib.redirect_stdout(io.StringIO()) as out:
            code = adapter.main(["--plan", str(self.path), "--staging-root", str(self.stage),
                                 "--target-app-version", "6.0", "--confirm-staging-only"])
        self.assertEqual(code, 1)
        result = json.loads(out.getvalue())
        self.assertFalse(result["generatedDraft"])
        self.assertIn("simulated disk failure", result["error"])
        self.assert_no_output()
        self.assertEqual(self.media.read_bytes(), b"fake video bytes")

    def test_save_failure_preserves_supplied_empty_root(self):
        self.stage.mkdir()
        with mock.patch.dict(sys.modules, {"pyJianYingDraft": fake_dependency(
                save_error=ValueError("save failed"))}):
            with self.assertRaisesRegex(adapter.ExportError, "save failed"):
                self.export()
        self.assertTrue(self.stage.is_dir())
        self.assertEqual(list(self.stage.iterdir()), [])

    def test_missing_malformed_and_empty_saved_json_are_not_success(self):
        for mode in ("missing", "invalid", "empty"):
            with self.subTest(mode=mode), mock.patch.dict(
                    sys.modules, {"pyJianYingDraft": fake_dependency(save_mode=mode)}):
                with self.assertRaisesRegex(adapter.ExportError, "Draft save"):
                    self.export()
                self.assert_no_output()

    def test_copy_failure_cleans_only_owned_output(self):
        with mock.patch.object(adapter.shutil, "copyfile", side_effect=OSError("copy denied")):
            with self.assertRaisesRegex(OSError, "copy denied"):
                self.export()
        self.assert_no_output()
        self.assertTrue(self.media.is_file())


if __name__ == "__main__":
    unittest.main()
