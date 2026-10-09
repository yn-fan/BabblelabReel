"""Offline and local-fixture tests; never contact a video platform."""

from contextlib import redirect_stdout, redirect_stderr
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
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills/reel/scripts/download_video.py"
SPEC = importlib.util.spec_from_file_location("reel_video_download", SCRIPT)
video = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(video)
URL = "https://www.xiaohongshu.com/explore/fixture?xsec_token=secret%2Bvalue&xsec_source=share"


def completed(stdout="", stderr="", returncode=0):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


class VideoTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.home = self.root / "home"
        environment = patch.dict(os.environ, {
            "BABBLELABREEL_USER_HOME": str(self.home), "BABBLELABREEL_USER_ALIAS": "fixture",
            "COPILOT_PLUGIN_DATA": str(self.root / "plugin-data"),
        })
        environment.start()
        self.addCleanup(environment.stop)
        self.args = video.parser().parse_args(["--rights", "owned", "--run-id", "fixture-run"])

    def invoke(self, *args):
        output = io.StringIO()
        with redirect_stdout(output):
            code = video.main(list(args))
        return code, json.loads(output.getvalue())

    def run_item(self, fake, *, probe=False, url=URL):
        self.args.probe = probe
        with patch.object(video, "backend", return_value=["yt-dlp"]), \
                patch.object(video.shutil, "which", side_effect=lambda name: name), \
                patch.object(video, "run_process", side_effect=fake):
            return video.run_one(self.args, url, 1, self.root / "batch")

    def receipt_backend(self, argv, **kwargs):
        folder = Path(argv[argv.index("-P") + 1])
        media = folder / "media.mp4"
        media.write_bytes(b"synthetic")
        receipt = Path(argv[argv.index("--print-to-file") + 2])
        receipt.write_text(json.dumps(str(media)) + "\n", encoding="utf-8")
        self.assertEqual(kwargs["input"], URL + "\n")
        self.assertNotIn(URL, argv)
        return completed()

    def test_chinese_multi_url_dedup_and_exact_query(self):
        other = "https://b23.tv/abc"
        self.assertEqual(video.links(f"看看：{URL}中文说明 {other} {URL}"), [URL, other])
        punctuation = "https://xhslink.com/a?token=abc.!?="
        self.assertEqual(video.links(punctuation), [punctuation])
        self.assertEqual(video.links("无链接卡片"), [])

    def test_domain_boundaries_and_wechat(self):
        for url in ("https://youtube.com.attacker.test/a", "https://evil.test/youtube.com",
                    "https://user:password@youtube.com/a", "https://youtu.be:444/a",
                    "https://youtu.be:bad/a", "https://[invalid", "file:///video.mp4"):
            with self.subTest(url=url):
                self.assertIsNone(video.platform(url))
        for host, name in (
            ("youtu.be", "youtube"), ("m.bilibili.com", "bilibili"), ("b23.tv", "bilibili"),
            ("instagram.com", "instagram"), ("v.douyin.com", "douyin"),
            ("iesdouyin.com", "douyin"), ("xhslink.com", "xiaohongshu"),
            ("channels.weixin.qq.com", "wechat-channels"), ("finder.video.qq.com", "wechat-channels"),
        ):
            self.assertEqual(video.platform("https://" + host + "/item"), name)

    def test_plan_is_offline_redacted_and_read_only(self):
        with patch.object(video, "backend", side_effect=AssertionError("dependency lookup")), \
                patch.object(video, "run_process", side_effect=AssertionError("network")):
            code, output = self.invoke(URL + " https://weixin.qq.com/a https://evil.test/a", "--plan")
        self.assertEqual(code, 0)
        self.assertEqual([r["status"] for r in output["results"]],
                         ["planned", "needs_wechat_capture", "unsupported_url"])
        self.assertEqual(output["results"][0]["source"]["sha256"], hashlib.sha256(URL.encode()).hexdigest())
        self.assertNotIn("secret", json.dumps(output))
        self.assertFalse(self.home.exists())

    def test_empty_input_and_scope_permissions(self):
        for args in (
            ("无链接", "--plan"), (URL,), (URL, "--run-id", "run"),
            (URL, "--probe", "--run-id", "../escape"),
            (URL, "--probe", "--run-id", "run", "--master-skill", "review"),
            (URL, "--probe", "--run-id", "run", "--browser", "chrome"),
            (URL, "--probe", "--run-id", "run", "--cookies", str(self.root / "absent"), "--allow-auth"),
        ):
            with self.subTest(args=args):
                self.assertEqual(self.invoke(*args)[0], 2)
        self.assertFalse(self.home.exists())

    def test_numeric_and_mutually_exclusive_options(self):
        for argv in (["--timeout", "0"], ["--max-mb", "-1"], ["--max-mb", "x"],
                     ["--probe", "--plan"], ["--cookies", "jar", "--browser", "chrome"]):
            with self.subTest(argv=argv), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                video.parser().parse_args(argv)

    def test_command_arguments_and_cookie_file(self):
        jar = self.root / "cookies.txt"
        jar.write_text("# local synthetic cookie jar", encoding="utf-8")
        args = video.parser().parse_args(["--cookies", str(jar), "--allow-auth", "--timeout", "12", "--max-mb", "7"])
        with patch.object(video.shutil, "which", return_value=None):
            argv = video.command(args, self.root, self.root / "receipt", ["tool with spaces"])
        self.assertEqual(argv[0], "tool with spaces")
        for flag in ("--ignore-config", "--no-cache-dir", "--no-playlist", "--no-overwrites"):
            self.assertIn(flag, argv)
        self.assertEqual(argv[argv.index("--playlist-items") + 1], "1")
        self.assertEqual(argv[argv.index("--max-filesize") + 1], "7M")
        self.assertEqual(argv[argv.index("--format-sort") + 1], "res")
        self.assertEqual(argv[argv.index("--match-filter") + 1], "!is_live & !is_upcoming")
        self.assertEqual(argv[-2:], ["--batch-file", "-"])
        self.assertNotIn("--cookies-from-browser", argv)
        args.cookies, args.browser, args.probe = None, "firefox", True
        with patch.object(video.shutil, "which", return_value=None):
            argv = video.command(args, self.root, self.root / "receipt", ["yt-dlp"])
        self.assertIn("--skip-download", argv)
        self.assertIn("--dump-single-json", argv)
        self.assertNotIn("--print-to-file", argv)
        self.assertEqual(argv[argv.index("--cookies-from-browser") + 1], "firefox")

    def test_backend_uses_selected_python_then_path_not_skill_venv(self):
        with patch.object(video.importlib.util, "find_spec", return_value=object()):
            self.assertEqual(video.backend(), [sys.executable, "-m", "yt_dlp"])
        with patch.object(video.importlib.util, "find_spec", return_value=None), \
                patch.object(video.shutil, "which", return_value="C:/Tools/yt-dlp.exe"):
            self.assertEqual(video.backend(), ["C:/Tools/yt-dlp.exe"])

    def managed_environment(self, root):
        root.mkdir(parents=True)
        (root / "pyvenv.cfg").write_text("home = fixture\n", encoding="utf-8")
        python = root / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        python.parent.mkdir()
        python.write_text("fixture interpreter; never executed", encoding="utf-8")
        return python

    def test_default_python_finds_previously_installed_state_environment(self):
        python = self.managed_environment(self.home / "profile/reel/dependencies/reel-video")
        with patch.object(video.importlib.util, "find_spec", return_value=None), \
                patch.object(video.shutil, "which", return_value=None), \
                patch.object(video, "run_process", return_value=completed("2026.08.19\n")):
            self.assertEqual(video.backend(), [str(python), "-I", "-m", "yt_dlp"])

    def test_plugin_data_environment_is_preferred_over_state(self):
        python = self.managed_environment(self.root / "plugin-data/dependencies/reel-video")
        self.managed_environment(self.home / "profile/reel/dependencies/reel-video")
        with patch.object(video.importlib.util, "find_spec", return_value=None), \
                patch.object(video.shutil, "which", return_value=None), \
                patch.object(video, "run_process", return_value=completed("2026.08.19\n")):
            self.assertEqual(video.backend(), [str(python), "-I", "-m", "yt_dlp"])

    def test_managed_discovery_is_read_only_without_installation(self):
        with patch.object(video.importlib.util, "find_spec", return_value=None), \
                patch.object(video.shutil, "which", return_value=None), \
                patch.object(video, "run_process", side_effect=AssertionError("nothing installed")):
            self.assertIsNone(video.backend())
        self.assertFalse(self.home.exists())
        self.assertFalse((self.root / "plugin-data").exists())

    def test_broken_managed_environment_is_explicit_and_does_not_reinstall(self):
        self.managed_environment(self.root / "plugin-data/dependencies/reel-video")
        with patch.object(video.importlib.util, "find_spec", return_value=None), \
                patch.object(video.shutil, "which", return_value=None), \
                patch.object(video, "run_process", return_value=completed(
                    stderr="No module named yt_dlp " + URL, returncode=1,
                )) as execute:
            code, result = self.invoke("--doctor")
            self.assertEqual(code, 1)
            self.assertEqual(result["status"], "dependency_error")
            self.assertNotIn("secret", json.dumps(result))
            self.assertEqual(execute.call_args.args[0][-1], "--version")
            item = video.run_one(self.args, URL, 1, self.root / "batch")
            self.assertEqual(item["status"], "dependency_error")
            self.assertFalse((self.root / "batch").exists())

    def test_managed_interpreter_timeout_is_sanitized(self):
        self.managed_environment(self.root / "plugin-data/dependencies/reel-video")
        with patch.object(video.importlib.util, "find_spec", return_value=None), \
                patch.object(video.shutil, "which", return_value=None), \
                patch.object(video, "run_process", side_effect=subprocess.TimeoutExpired([URL], 10)):
            code, result = self.invoke("--doctor")
            self.assertEqual(code, 1)
            self.assertEqual(result["status"], "dependency_error")
            self.assertNotIn("secret", json.dumps(result))

    def test_managed_root_rejects_relative_or_runtime_paths(self):
        for root in ("relative-data", str(ROOT)):
            with self.subTest(root=root), patch.dict(os.environ, {"COPILOT_PLUGIN_DATA": root}), \
                    patch.object(video.importlib.util, "find_spec", return_value=None), \
                    patch.object(video.shutil, "which", return_value=None), \
                    patch.object(video, "run_process", side_effect=AssertionError("unsafe root")):
                self.assertEqual(self.invoke("--doctor")[1]["status"], "dependency_error")

    def test_managed_python_layouts_are_cross_platform(self):
        self.assertEqual(video.environment_python(self.root, "win32"), self.root / "Scripts/python.exe")
        self.assertEqual(video.environment_python(self.root, "darwin"), self.root / "bin/python")
        self.assertEqual(video.environment_python(self.root, "linux"), self.root / "bin/python")

    def test_cookie_setup_progress_does_not_turn_network_error_into_login(self):
        self.assertEqual(video.failure_kind(
            "Extracting cookies from chrome\nExtracted 42 cookies from chrome\n"
            "ERROR: Unable to download webpage: Connection reset by peer"
        ), "network_error")

    def test_local_output_permission_is_not_browser_permission(self):
        self.assertEqual(video.failure_kind(
            "ERROR: unable to open for writing: [Errno 13] Permission denied: media.mp4"
        ), "local_error")

    def test_cookie_diagnostics_distinguish_store_and_remote_login(self):
        for message, expected in (
            ("ERROR: Fresh cookies (not necessarily logged in) are needed", "site_response_or_verification_blocked"),
            ("ERROR: could not find chrome cookies database", "browser_cookie_error"),
            ("ERROR: Failed to decrypt cookies with DPAPI", "browser_cookie_error"),
            ("Extracted cookies from chrome\nERROR: Unsupported URL " + URL, "unsupported_url"),
            ("Extracted cookies from chrome\nERROR: Video unavailable", "unavailable"),
            ("Extracted cookies from chrome\nERROR: extractor crashed", "extractor_or_download_error"),
        ):
            with self.subTest(expected=expected):
                self.assertEqual(video.failure_kind(message), expected)

    def test_explicit_browser_profile_is_scoped_and_passed_as_one_argument(self):
        args = video.parser().parse_args([
            "--browser", "chrome", "--browser-profile", "Profile 1", "--allow-auth",
        ])
        with patch.object(video.shutil, "which", return_value=None):
            argv = video.command(args, self.root, self.root / "receipt", ["yt-dlp"])
        self.assertEqual(argv[argv.index("--cookies-from-browser") + 1], "chrome:Profile 1")
        for options in (
            ["--browser-profile", "Profile 1"],
            ["--browser", "safari", "--browser-profile", "Profile 1", "--allow-auth"],
            ["--browser", "chrome", "--browser-profile", "Profile 1::another", "--allow-auth"],
            ["--browser", "chrome", "--browser-profile", "../outside", "--allow-auth"],
        ):
            with self.subTest(options=options):
                code, result = self.invoke(URL, "--probe", "--run-id", "profile", *options)
                self.assertEqual(code, 2)
                self.assertEqual(result["status"], "invalid_request")
        self.assertFalse(self.home.exists())

    def test_required_resolution_filters_download_without_low_quality_fallback(self):
        args = video.parser().parse_args(["--min-resolution", "2160"])
        with patch.object(video.shutil, "which", return_value=None):
            argv = video.command(args, self.root, self.root / "receipt", ["yt-dlp"])
        self.assertEqual(argv[argv.index("-f") + 1],
                         "bv*[width>=2160][height>=2160]+ba/b[width>=2160][height>=2160]")
        self.assertEqual(video.failure_kind("ERROR: Requested format is not available"),
                         "requested_quality_unavailable")
        for mode in ("--plan", "--probe", "--doctor"):
            self.assertEqual(self.invoke(URL, mode, "--min-resolution", "2160")[0], 2)

    def test_required_resolution_checks_actual_downloaded_dimensions(self):
        self.args.min_resolution = 2160
        def fake(argv, **kwargs):
            if "-P" in argv:
                return self.receipt_backend(argv, **kwargs)
            return completed(json.dumps({"streams": [{
                "codec_type": "video", "duration": "2", "width": 1920, "height": 1080,
            }]}))
        result = self.run_item(fake)
        self.assertEqual(result["status"], "validation_failed")
        self.assertEqual(result["reason"], "requested_resolution_not_met")
        self.assertNotIn("files", result)

    def test_missing_dependencies_and_wechat_make_no_process(self):
        with patch.object(video, "backend", return_value=None), \
                patch.object(video.shutil, "which", return_value=None), \
                patch.object(video, "run_process", side_effect=AssertionError("must not run")):
            self.assertEqual(video.run_one(self.args, URL, 1, self.root)["missing"],
                             ["yt-dlp", "ffmpeg", "ffprobe"])
            self.assertEqual(video.run_one(self.args, "https://weixin.qq.com/a", 2, self.root)["status"],
                             "needs_wechat_capture")
            self.assertEqual(video.run_one(self.args, "https://evil.test/a", 3, self.root)["status"],
                             "unsupported_url")
            self.assertEqual(self.invoke("--doctor")[0], 1)

    def test_probe_sanitizes_metadata_and_is_not_download(self):
        def fake(argv, **kwargs):
            self.assertIn("--skip-download", argv)
            self.assertNotIn("--print-to-file", argv)
            return completed(json.dumps({"title": URL, "id": "secret", "duration": 3.2,
                                         "formats": [{"vcodec": "h264"}], "url": URL}))
        result = self.run_item(fake, probe=True)
        self.assertEqual(result["status"], "resolved")
        self.assertEqual(result["duration"], 3.2)
        self.assertNotIn("secret", json.dumps(result))
        self.assertNotIn("files", result)

    def test_probe_reports_available_resolutions_without_private_format_fields(self):
        result = video.metadata(json.dumps({
            "duration": 3, "url": URL,
            "formats": [
                {"vcodec": "h264", "width": 1920, "height": 1080, "fps": 30, "tbr": 2500,
                 "format_id": "private-token", "url": URL, "http_headers": {"Cookie": "secret"}},
                {"vcodec": "h264", "width": 1920, "height": 1080, "fps": 30, "tbr": 2500},
                {"vcodec": "h264", "width": 1280, "height": 720, "fps": 30, "tbr": 1000},
                {"vcodec": "none", "acodec": "aac"},
            ],
        }))
        self.assertEqual(result["formats"], [
            {"width": 1920, "height": 1080, "fps": 30.0, "bitrate_kbps": 2500.0},
            {"width": 1280, "height": 720, "fps": 30.0, "bitrate_kbps": 1000.0},
        ])
        self.assertNotIn("secret", json.dumps(result))
        self.assertNotIn("private-token", json.dumps(result))
        self.assertEqual(result["status"], "resolved")

    def test_format_inventory_caps_and_rejects_invalid_numbers(self):
        result = video.metadata(json.dumps({"formats": [
            {"vcodec": "h264", "width": 1000 + i, "height": 500 + i}
            for i in range(257)
        ]}))
        self.assertEqual(len(result["formats"]), 256)
        self.assertTrue(result["formats_truncated"])
        self.assertEqual(result["formats"][0]["height"], 756)
        result = video.metadata(json.dumps({"formats": [{
            "vcodec": "h264", "width": True, "height": -3, "fps": "nan", "tbr": "secret",
        }]}))
        self.assertEqual(result["formats"][0],
                         {"width": None, "height": None, "fps": None, "bitrate_kbps": None})
        json.dumps(result, allow_nan=False)

    def test_metadata_live_image_and_malformed(self):
        for data, status in (
            ({"is_live": True}, "live_not_supported"),
            ({"live_status": "is_upcoming"}, "live_not_supported"),
            ({"formats": [{"vcodec": "none"}]}, "no_video_metadata"),
            ({"width": 1080, "ext": "jpg"}, "no_video_metadata"),
            ({"formats": [{"width": 1080, "ext": "webm"}]}, "resolved"),
            ({"formats": [{"vcodec": "h264"}], "duration": "nan"}, "resolved"),
        ):
            self.assertEqual(video.metadata(json.dumps(data))["status"], status)
        for data in ([], {"_type": "playlist", "entries": [{}, {}]}):
            with self.assertRaises(video.VideoError):
                video.metadata(json.dumps(data))
        self.assertEqual(video.metadata(json.dumps({
            "_type": "multi_video", "entries": [{"formats": [{"vcodec": "h264"}]}],
        }))["status"], "resolved")

    def test_errors_are_explicit_without_stderr(self):
        for message, kind in (
            ("Permission denied reading cookies " + URL, "browser_access_denied"),
            ("Operation not permitted: Safari Cookies", "browser_access_denied"),
            ("Sign in using cookies " + URL, "needs_login"),
            ("429 captcha cookies " + URL, "rate_limited"),
            ("Connection timed out", "network_error"),
            ("Video unavailable", "unavailable"),
            ("Unsupported URL", "unsupported_url"),
            ("Extractor exploded " + URL, "extractor_or_download_error"),
        ):
            with self.subTest(kind=kind):
                self.assertEqual(video.failure_kind(message), kind)
        result = self.run_item(lambda *_a, **_k: completed(stderr="login " + URL, returncode=1))
        self.assertEqual(result["status"], "needs_login")
        self.assertNotIn("secret", json.dumps(result))

    def test_timeout_is_not_downloaded(self):
        result = self.run_item(lambda *_a, **_k: (_ for _ in ()).throw(subprocess.TimeoutExpired([], 1)))
        self.assertEqual(result["status"], "timeout")

    def test_no_receipt_is_not_downloaded(self):
        self.assertEqual(self.run_item(lambda *_a, **_k: completed())["status"], "no_video_saved")

    def test_probe_malformed_response_and_missing_ffprobe(self):
        result = self.run_item(lambda *_a, **_k: completed("not JSON " + URL), probe=True)
        self.assertEqual(result["status"], "local_error")
        self.assertNotIn("secret", json.dumps(result))
        self.args.probe = False
        with patch.object(video, "backend", return_value=["yt-dlp"]), \
                patch.object(video.shutil, "which", side_effect=lambda name: None if name == "ffprobe" else name), \
                patch.object(video, "run_process", side_effect=AssertionError("must not run")):
            result = video.run_one(self.args, URL, 2, self.root)
        self.assertEqual(result["missing"], ["ffprobe"])

    def test_verified_receipt_success_and_cleanup(self):
        def fake(argv, **kwargs):
            if "-P" in argv:
                return self.receipt_backend(argv, **kwargs)
            return completed(json.dumps({"streams": [{"codec_type": "video", "duration": "2"}]}))
        result = self.run_item(fake)
        self.assertEqual(result["status"], "downloaded")
        self.assertEqual(result["files"][0]["duration"], 2)
        self.assertEqual(result["files"][0]["sha256"], hashlib.sha256(b"synthetic").hexdigest())
        self.assertFalse((self.root / "batch/item-1/.completed.jsonl").exists())

    def test_missing_outside_audio_and_malformed_receipts_fail(self):
        for variant in ("missing", "outside", "audio", "malformed", "multiple", "empty", "oversize", "symlink"):
            with self.subTest(variant=variant):
                root = self.root / variant
                def fake(argv, **kwargs):
                    if "-P" not in argv:
                        return completed('{"streams":[{"codec_type":"audio"}],"format":{"duration":"3"}}')
                    folder = Path(argv[argv.index("-P") + 1])
                    media = folder / "media.mp4"
                    if variant == "outside":
                        media = self.root / "outside.mp4"
                    if variant != "missing":
                        media.write_bytes(b"" if variant == "empty" else b"x")
                    if variant == "oversize":
                        with media.open("wb") as stream:
                            stream.truncate(self.args.max_mb * 1024 * 1024 + 1)
                    if variant == "symlink":
                        media.unlink()
                        target = self.root / "target.mp4"
                        target.write_bytes(b"data")
                        media.symlink_to(target)
                    receipt = Path(argv[argv.index("--print-to-file") + 2])
                    receipt.write_text("garbage" if variant == "malformed" else
                                       (json.dumps(str(media)) + "\n") * (2 if variant == "multiple" else 1))
                    return completed()
                with patch.object(video, "backend", return_value=["yt-dlp"]), \
                        patch.object(video.shutil, "which", side_effect=lambda name: name), \
                        patch.object(video, "run_process", side_effect=fake):
                    result = video.run_one(self.args, URL, 1, root)
                self.assertIn(result["status"], ("local_error", "validation_failed"))
                self.assertNotIn("files", result)

    def test_ffprobe_rejects_nonfinite_duration_and_cover_art(self):
        path = self.root / "media.mp4"
        path.write_bytes(b"fixture")
        for payload in (
            {"streams": [{"codec_type": "video"}], "format": {"duration": "NaN"}},
            {"streams": [{"codec_type": "video", "duration": "-1"}]},
            {"streams": [{"codec_type": "video", "disposition": {"attached_pic": 1}}], "format": {"duration": "2"}},
            {"streams": None}, [],
        ):
            with self.subTest(payload=payload), patch.object(video, "run_process", return_value=completed(json.dumps(payload))):
                with self.assertRaises(video.VideoError):
                    video.verify_video(path, self.root, 100, 10)

    def test_artifact_bindings_manifest_append_and_partial_batch(self):
        with patch.object(video, "backend", return_value=None):
            args = [URL + " https://weixin.qq.com/a", "--probe", "--run-id", "run", "--feature-name", "demo"]
            code, result = self.invoke(*args)
            self.assertEqual(code, 1)
            record = Path(result["provenance"])
            self.assertEqual(record.parent, self.home / "reports/reel/demo/run")
            self.assertEqual(len(result["results"]), 2)
            self.invoke(*args)
        manifest = json.loads((record.parent / "_manifest.json").read_text())
        self.assertEqual(len(manifest["artifacts"]), 2)
        for path in self.home.rglob("*.json"):
            self.assertNotIn("secret", path.read_text())
        self.assertFalse((self.home / "outputs").exists())

    def test_child_owner_manifest_and_download_output(self):
        def fake(args, url, index, root):
            self.assertEqual(root.parent, self.home / "reports/design/topic/master/reel/outputs/videos")
            return dict(video.source_ref(url, index), status="no_video_saved")
        with patch.object(video, "run_one", side_effect=fake):
            _, result = self.invoke(URL, "--run-id", "child", "--rights", "licensed",
                                    "--master-skill", "design", "--master-run-id", "master",
                                    "--master-feature-name", "topic")
        record = Path(result["provenance"])
        parent = json.loads((record.parent.parent / "_manifest.json").read_text())
        self.assertEqual(parent["session_id"], "master")
        self.assertEqual(parent["artifacts"][0]["file"], "reel/" + record.name)

    def test_manifest_corruption_or_output_symlink_blocks_before_network(self):
        report = self.home / "reports/reel/run"
        report.mkdir(parents=True)
        manifest = report / "_manifest.json"
        manifest.write_text('{"session_id":"wrong","artifacts":[]}')
        with patch.object(video, "run_one", side_effect=AssertionError("must not run")):
            self.assertEqual(self.invoke(URL, "--probe", "--run-id", "run")[0], 2)
        manifest.unlink()
        output = self.home / "outputs"
        output.symlink_to(self.root, target_is_directory=True)
        with patch.object(video, "run_one", side_effect=AssertionError("must not run")):
            self.assertEqual(self.invoke(URL, "--rights", "owned", "--run-id", "run")[0], 2)

    def test_real_local_process_stdin_and_timeout(self):
        result = video.run_process([sys.executable, "-c", "import sys; print(sys.stdin.read())"],
                                   input="local fixture", timeout=5)
        self.assertEqual(result.stdout.strip(), "local fixture")
        with self.assertRaises(subprocess.TimeoutExpired):
            video.run_process([sys.executable, "-c", "import time; time.sleep(20)"], timeout=1)

    @unittest.skipIf(os.name == "nt", "POSIX process-tree assertion")
    def test_timeout_stops_merger_descendants(self):
        pid_file = self.root / "child.pid"
        code = (
            "import subprocess,sys,time; from pathlib import Path; "
            "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); "
            "Path(sys.argv[1]).write_text(str(child.pid)); time.sleep(30)"
        )
        with self.assertRaises(subprocess.TimeoutExpired):
            video.run_process([sys.executable, "-c", code, str(pid_file)], timeout=1)
        pid = int(pid_file.read_text())
        process = subprocess.run(["ps", "-p", str(pid), "-o", "stat="], capture_output=True, text=True)
        self.assertTrue(process.returncode != 0 or process.stdout.strip().startswith("Z"),
                        "Timed-out extractor left a live descendant")

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "local ffmpeg/ffprobe unavailable")
    def test_actual_local_video_and_invalid_media(self):
        path = self.root / "media.mp4"
        subprocess.run([shutil.which("ffmpeg"), "-v", "error", "-f", "lavfi", "-i",
                        "color=c=black:s=32x32:d=0.4", "-c:v", "mpeg4", str(path)], check=True)
        result = video.verify_video(path, self.root, 1024 * 1024, 10)
        self.assertGreater(result["duration"], 0)
        self.assertEqual((result["width"], result["height"]), (32, 32))
        self.assertEqual(result["bytes"], path.stat().st_size)
        path.write_bytes(b"this is not a video")
        with self.assertRaises(video.VideoError):
            video.verify_video(path, self.root, 1024 * 1024, 10)

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "local ffmpeg/ffprobe unavailable")
    def test_full_pipeline_fake_downloader_real_video_and_provenance(self):
        source = self.root / "fixture.mp4"
        subprocess.run([shutil.which("ffmpeg"), "-v", "error", "-f", "lavfi", "-i",
                        "color=c=blue:s=32x32:d=0.4", "-c:v", "mpeg4", str(source)], check=True)
        fake = self.root / "fake_downloader.py"
        fake.write_text(
            "import sys,json,shutil\nfrom pathlib import Path\n"
            "source=Path(sys.argv[1]); args=sys.argv[2:]\n"
            "assert sys.stdin.read().startswith('https://')\n"
            "out=Path(args[args.index('-P')+1])/'media.mp4'\n"
            "shutil.copyfile(source,out)\n"
            "receipt=Path(args[args.index('--print-to-file')+2])\n"
            "receipt.write_text(json.dumps(str(out))+'\\n')\n", encoding="utf-8",
        )
        with patch.object(video, "backend", return_value=[sys.executable, str(fake), str(source)]):
            code, result = self.invoke(URL + " https://weixin.qq.com/item",
                                       "--rights", "authorized", "--run-id", "pipeline")
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "incomplete")
        first, second = result["results"]
        self.assertEqual(first["status"], "downloaded")
        self.assertEqual((first["files"][0]["width"], first["files"][0]["height"]), (32, 32))
        self.assertEqual(second["status"], "needs_wechat_capture")
        file = Path(first["files"][0]["path"])
        self.assertTrue(file.is_relative_to(self.home / "outputs/reel/videos"))
        self.assertEqual(file.read_bytes(), source.read_bytes())
        report = json.loads(Path(result["provenance"]).read_text())
        self.assertEqual(report["results"], result["results"])
        self.assertNotIn("secret", json.dumps(report))
        self.assertFalse(list(self.home.rglob(".completed.jsonl")))
        plan = self.root / "edit-plan.json"
        plan.write_text(json.dumps({
            "version": 1,
            "output": {"fps": 25, "width": 64, "height": 64},
            "clips": [{"path": str(file), "sourceStart": 0, "durationFrames": 5}],
        }), encoding="utf-8")
        output = self.root / "montage.mp4"
        subprocess.run(
            [sys.executable, str(ROOT / "skills/reel/scripts/edit_video.py"),
             "render", str(plan), "--output", str(output)],
            check=True, capture_output=True, text=True,
        )
        rendered = video.verify_video(output, self.root, 1024 * 1024, 10)
        self.assertEqual((rendered["width"], rendered["height"]), (64, 64))
        self.assertAlmostEqual(rendered["duration"], 0.2, places=2)
        self.assertEqual(hashlib.sha256(file.read_bytes()).hexdigest(), first["files"][0]["sha256"])


if __name__ == "__main__":
    unittest.main()
