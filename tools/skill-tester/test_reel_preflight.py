from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[2] / "skills/reel/scripts"
sys.path.insert(0, str(SCRIPTS))
import edit_video
import export_jianying
import download_video
import compress_video
import preflight_reel as preflight


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def manifest(self, **extra):
        data = {"dependencies": {"remotion": "4.0.514", "@remotion/cli": "4.0.514"}}
        data.update(extra)
        (self.root / "package.json").write_text(json.dumps(data), encoding="utf-8")
        return data

    def test_remotion_does_not_probe_unrelated_backends(self):
        with patch.object(preflight, "executable", return_value={"path": "/node", "version": "v22"}) as tools, \
             patch.object(edit_video, "preflight_capabilities", side_effect=AssertionError("wrong engine")), \
             patch.object(export_jianying, "preflight_dependency", side_effect=AssertionError("wrong engine")):
            result = preflight.preflight("remotion", captions=True, credits=True)
        self.assertEqual(result["status"], "ready")
        self.assertEqual([call.args[0] for call in tools.call_args_list], ["node", "npm"])
        self.assertEqual(result["readinessScope"], "local-prerequisites-only")
        self.assertTrue(any(c["status"] == "not-checked" for c in result["checks"]))
        self.assertEqual(list(self.root.iterdir()), [])

    def test_missing_node_is_an_actionable_blocker(self):
        with patch.object(preflight, "executable", side_effect=preflight.PreflightError("missing")):
            result = preflight.preflight("remotion")
        self.assertEqual(result["status"], "blocked")
        self.assertIn("permission", result["checks"][1]["action"])

    def test_feature_flags_reach_renderer(self):
        with patch.object(edit_video, "preflight_capabilities", return_value={"ffmpeg": "/ffmpeg"}) as check:
            result = preflight.preflight("ffmpeg", captions=True, credits=True, music=True,
                                        transitions=True, narration=True)
        self.assertEqual(result["status"], "ready")
        check.assert_called_once_with(captions=True, credits=True, music=True,
                                      transitions=True, narration=True)

    def test_missing_libass_is_not_silent_success(self):
        with patch.object(edit_video, "preflight_capabilities",
                          side_effect=edit_video.EditError("captions/attribution require libass")):
            result = preflight.preflight("ffmpeg", credits=True)
        self.assertEqual(result["status"], "blocked")
        self.assertIn("libass", result["checks"][-1]["detail"])
        self.assertIn("never omit", result["checks"][-1]["action"])

    def test_native_text_needs_no_render_filters_or_node(self):
        with patch.object(edit_video, "preflight_media_tools", return_value={"ffprobe": "/ffprobe"}), \
             patch.object(edit_video, "preflight_capabilities", side_effect=AssertionError("render filter probe")), \
             patch.object(preflight, "executable", side_effect=AssertionError("Node probe")), \
             patch.object(export_jianying, "preflight_dependency", return_value={"apiContract": "verified signatures"}):
            result = preflight.preflight("jianying", captions=True, credits=True)
        self.assertEqual(result["status"], "ready")
        self.assertTrue(any("unverified" in item for item in result["limitations"]))

    def test_missing_native_dependency_retains_explicit_blocker(self):
        with patch.object(edit_video, "preflight_media_tools", return_value={}), \
             patch.object(export_jianying, "preflight_dependency",
                          side_effect=export_jianying.ExportError("Optional dependency unavailable")):
            result = preflight.preflight("jianying")
        self.assertEqual(result["status"], "blocked")
        self.assertIn("compatible optional", result["checks"][-1]["action"])

    def test_download_preflight_reuses_doctor_without_production_or_acquisition(self):
        state = {"status": "ready", "yt_dlp": True, "ffmpeg": True, "ffprobe": True, "js_runtime": "node"}
        with patch.object(download_video, "doctor", return_value=state) as doctor, \
             patch.object(download_video, "execute", side_effect=AssertionError("must not download")), \
             patch.object(edit_video, "preflight_capabilities", side_effect=AssertionError("no renderer")), \
             patch.object(preflight, "executable", side_effect=AssertionError("no new runtimes")):
            result = preflight.preflight("download", alias="fixture")
        doctor.assert_called_once_with("fixture")
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["checks"][-1]["detail"]["operation"], "download")
        self.assertTrue(any("quality" in limitation for limitation in result["limitations"]))
        self.assertFalse(any(self.root.iterdir()))

    def test_metadata_preflight_does_not_require_ffmpeg_or_ffprobe(self):
        state = {"status": "missing_dependency", "yt_dlp": True,
                 "ffmpeg": False, "ffprobe": False, "js_runtime": None}
        with patch.object(download_video, "doctor", return_value=state):
            self.assertEqual(preflight.preflight("download", metadata_only=True)["status"], "ready")
            blocked = preflight.preflight("download")
        self.assertEqual(blocked["status"], "blocked")
        self.assertIn("ffprobe", blocked["checks"][-1]["detail"])

    def test_download_dependency_error_is_not_hidden_by_another_runtime(self):
        state = {"status": "dependency_error", "message": "Approved environment needs repair"}
        with patch.object(download_video, "doctor", return_value=state):
            result = preflight.preflight("download", metadata_only=True)
        self.assertEqual(result["status"], "blocked")
        self.assertIn("needs repair", result["checks"][-1]["detail"])

    def test_download_and_production_flags_do_not_mix(self):
        for engine, options in (
            ("download", {"captions": True}), ("ffmpeg", {"metadata_only": True}),
            ("remotion", {"alias": "fixture"}), ("download", {"project": self.root}),
            ("compress", {"music": True}), ("compress", {"metadata_only": True}),
            ("compress", {"project": self.root}),
        ):
            with self.assertRaises(preflight.PreflightError):
                preflight.preflight(engine, **options)

    def test_compression_preflight_has_no_other_engine_requirements(self):
        with patch.object(compress_video, "preflight_compression",
                          return_value={"ffmpeg": "/ffmpeg", "ffprobe": "/ffprobe"}) as check, \
             patch.object(edit_video, "preflight_capabilities", side_effect=AssertionError("no editing")), \
             patch.object(download_video, "doctor", side_effect=AssertionError("no downloading")), \
             patch.object(preflight, "executable", side_effect=AssertionError("no Node")):
            result = preflight.preflight("compress")
        check.assert_called_once_with()
        self.assertEqual(result["status"], "ready")
        self.assertTrue(any("byte ceiling" in item for item in result["limitations"]))
        self.assertFalse(list(self.root.iterdir()))

    def test_missing_compression_codec_reports_explicit_blocker(self):
        with patch.object(compress_video, "preflight_compression",
                          side_effect=edit_video.EditError("libx264 unavailable")):
            result = preflight.preflight("compress")
        self.assertEqual(result["status"], "blocked")
        self.assertIn("libx264", result["checks"][-1]["detail"])
        self.assertIn("permission", result["checks"][-1]["action"])

    def test_manager_follows_manifest_then_lockfiles(self):
        self.assertEqual(preflight.package_manager(self.root, {"packageManager": "pnpm@10.0.0"}), "pnpm")
        (self.root / "yarn.lock").touch()
        self.assertEqual(preflight.package_manager(self.root, {}), "yarn")
        (self.root / "package-lock.json").touch()
        with self.assertRaisesRegex(preflight.PreflightError, "Multiple"):
            preflight.package_manager(self.root, {})
        with self.assertRaises(preflight.PreflightError):
            preflight.package_manager(self.root, {"packageManager": "unknown@1"})

    def test_project_flag_cannot_cross_engines_or_create_missing_directory(self):
        with self.assertRaises(preflight.PreflightError):
            preflight.preflight("ffmpeg", project=self.root)
        missing = self.root / "missing"
        with patch.object(preflight, "executable", return_value={"path": "/node", "version": "v22"}):
            result = preflight.preflight("remotion", project=missing)
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(missing.exists())

    def test_exact_aligned_remotion_versions_are_required(self):
        for dependency in (
            {"remotion": "^4.0.514"},
            {"remotion": "4.0.514", "@remotion/cli": "4.0.513"},
            {},
        ):
            with self.assertRaises(preflight.PreflightError), \
                 patch.object(preflight, "command", side_effect=AssertionError("no runtime needed")):
                preflight.installed_dependencies(self.root, {"dependencies": dependency}, "/node")

    def test_missing_and_mismatched_installed_packages_fail(self):
        manifest = self.manifest()
        for installed in (
            {"remotion": {"error": "missing"}},
            {"remotion": {"version": "4.0.514"}, "@remotion/cli": {"version": "4.0.513"}},
        ):
            with patch.object(preflight, "command", return_value=json.dumps(installed)), \
                 self.assertRaises(preflight.PreflightError):
                preflight.installed_dependencies(self.root, manifest, "/node")

    def test_no_npx_or_package_scripts_and_no_project_write(self):
        manifest = self.manifest(packageManager="pnpm@10.0.0")
        before = (self.root / "package.json").read_bytes()
        installed = {name: {"version": version} for name, version in manifest["dependencies"].items()}
        with patch.object(preflight, "executable", return_value={"path": "/node", "version": "v22"}) as tools, \
             patch.object(preflight, "command", return_value=json.dumps(installed)) as commands:
            result = preflight.preflight("remotion", project=self.root)
        self.assertEqual(result["status"], "ready")
        self.assertEqual([call.args[0] for call in tools.call_args_list], ["node", "pnpm"])
        args = commands.call_args.args[0]
        self.assertEqual(args[:2], ["/node", "-e"])
        self.assertNotIn("npx", args)
        self.assertEqual((self.root / "package.json").read_bytes(), before)
        self.assertEqual(len(list(self.root.iterdir())), 1)

    def test_empty_versions_and_timeouts_are_explicit(self):
        with patch.object(shutil, "which", return_value="/tool"), \
             patch.object(preflight, "command", return_value=""), \
             self.assertRaises(preflight.PreflightError):
            preflight.executable("node")
        with patch.object(subprocess, "run", side_effect=subprocess.TimeoutExpired("node", 20)), \
             self.assertRaises(preflight.PreflightError):
            preflight.command(["node", "--version"])

    def test_package_manager_launcher_is_not_executed_or_bootstrapped(self):
        with patch.object(shutil, "which", return_value="/corepack/pnpm"), \
             patch.object(preflight, "command", side_effect=AssertionError("would bootstrap")):
            result = preflight.executable("pnpm", probe_version=False)
        self.assertEqual(result["version"], "not-probed")

    def test_pnp_loader_is_not_executed_or_misreported_as_missing_packages(self):
        (self.root / ".pnp.cjs").write_text("throw new Error('must not run');")
        with patch.object(preflight, "command", side_effect=AssertionError("project loader")), \
             self.assertRaisesRegex(preflight.PreflightError, "Yarn PnP detected"):
            preflight.installed_dependencies(self.root, self.manifest(), "/node")

    def test_shared_renderer_probe_is_selected_feature_aware(self):
        with patch.object(edit_video, "preflight_media_tools", return_value={"ffmpeg": "/ffmpeg"}), \
             patch.object(edit_video, "_check_render_capabilities") as check:
            edit_video.preflight_capabilities(music=True, narration=True, credits=True)
        _, clips, audio, captions, credits = check.call_args.args
        self.assertEqual(len(clips), 2)
        self.assertTrue(audio["music"]["ducking"])
        self.assertFalse(captions)
        self.assertTrue(credits)

    @unittest.skipUnless(shutil.which("node"), "Node unavailable")
    def test_real_node_resolves_hoisted_metadata_without_executing_packages(self):
        manifest = self.manifest()
        for name, version in manifest["dependencies"].items():
            folder = self.root / "node_modules" / name
            folder.mkdir(parents=True)
            (folder / "package.json").write_text(json.dumps({"name": name, "version": version}))
            (folder / "index.js").write_text("throw new Error('must not execute package');")
        nested = self.root / "packages/video"
        nested.mkdir(parents=True)
        result = preflight.installed_dependencies(nested, manifest, shutil.which("node"))
        self.assertEqual(result, manifest["dependencies"])


if __name__ == "__main__":
    unittest.main()
