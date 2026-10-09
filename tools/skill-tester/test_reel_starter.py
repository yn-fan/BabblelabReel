import base64
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import wave


REPO_ROOT = Path(__file__).resolve().parents[2]
REEL_ROOT = REPO_ROOT / "skills" / "reel"
SCAFFOLD_PATH = REEL_ROOT / "scripts" / "scaffold_reel.py"
STARTER_ROOT = REEL_ROOT / "assets" / "remotion-starter"
FIXTURE_ROOT = REEL_ROOT / "evals" / "files"


def load_scaffold_module():
    spec = importlib.util.spec_from_file_location("reel_scaffold", SCAFFOLD_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load Reel scaffold module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReelStarterTests(unittest.TestCase):
    def test_optimized_video_presets_are_distinct_and_complete(self) -> None:
        presets_root = STARTER_ROOT / "src" / "reel" / "presets"
        launch = json.loads(
            (presets_root / "product-launch.json").read_text(encoding="utf-8")
        )
        vision = json.loads(
            (presets_root / "vision-video.json").read_text(encoding="utf-8")
        )

        self.assertEqual(launch["id"], "product-launch")
        self.assertEqual(vision["id"], "vision-video")
        self.assertEqual(launch["formatDefaults"]["fps"], 60)
        self.assertEqual(vision["formatDefaults"]["fps"], 30)
        self.assertLess(
            launch["shotDefaults"]["maximumUnchangedNarratedSeconds"],
            vision["shotDefaults"]["maximumUnchangedNarratedSeconds"],
        )
        self.assertIn(
            "real product capture",
            launch["assetDefaults"]["dominantSource"],
        )
        self.assertIn(
            "human context",
            vision["assetDefaults"]["dominantSource"],
        )
        self.assertEqual(vision["assetDefaults"]["minimumHumanContextScenes"], 3)
        self.assertTrue(
            vision["assetDefaults"]["rasterOrFootageRequiredForPeopleCenteredStories"]
        )
        self.assertFalse(vision["assetDefaults"]["vectorOnlyFallbackAllowed"])
        self.assertLessEqual(
            vision["assetDefaults"]["maximumVectorGraphicRuntimePercent"],
            35,
        )
        self.assertEqual(len(launch["assetDefaults"]["styleFrames"]), 3)
        self.assertEqual(len(vision["assetDefaults"]["styleFrames"]), 3)
        self.assertGreaterEqual(len(launch["failureConditions"]), 5)
        self.assertGreaterEqual(len(vision["failureConditions"]), 5)
        for preset in (launch, vision):
            self.assertIn("free hosted AI BGM", preset["audioDefaults"]["sound"])
            self.assertIn("supplied licensed music", preset["audioDefaults"]["sound"])
            self.assertIn("explicit silence", preset["audioDefaults"]["sound"])

        skill = (REEL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        production = (
            REEL_ROOT / "references" / "remotion-production.md"
        ).read_text(encoding="utf-8")
        defaults = (
            REEL_ROOT / "references" / "video-type-defaults.md"
        ).read_text(encoding="utf-8")
        self.assertIn("references/remotion-production.md", skill)
        self.assertIn("do not count as human-context", production)
        self.assertIn("do not turn the planned", defaults)

    def test_narration_defaults_to_enhanced_kokoro(self) -> None:
        skill = (REEL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        production = (REEL_ROOT / "references" / "remotion-production.md").read_text(
            encoding="utf-8"
        )
        prompt = (REEL_ROOT / "references" / "production-prompt.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("references/remotion-production.md", skill)
        for required in (
            "Pass `--mode enhanced`",
            "do not silently retry with basic mode",
            "`mode: enhanced`",
            "Kokoro engine/model",
        ):
            self.assertIn(required, production)
        self.assertIn("audio-generator enhanced mode", prompt)
        self.assertIn("do not silently fall back to basic synthesis", prompt)

    def test_starter_is_neutral_and_versions_are_aligned(self) -> None:
        source = (STARTER_ROOT / "src" / "reel" / "Reel.tsx").read_text(
            encoding="utf-8"
        )
        for forbidden in (
            "Northstar",
            "300M+",
            "blue/cyan",
            "sceneOpacity",
            "Math.sin",
            "scale: zoom",
            "Replace this timing placeholder",
        ):
            self.assertNotIn(forbidden, source)
        self.assertNotIn("scene.caption", source)
        self.assertIn("<AudioTrack />", source)
        self.assertIn("<MusicTrack />", source)
        self.assertIn("<CaptionTrack />", source)
        self.assertIn("reelStory.shots.map", source)
        self.assertIn("<ShotFrame", source)
        self.assertIn("beat.kind === 'action' || beat.kind === 'state'", source)
        self.assertIn("hasSceneCaptions(scene.id) ? 190 : 106", source)

        caption_track = (
            STARTER_ROOT / "src" / "reel" / "CaptionTrack.tsx"
        ).read_text(encoding="utf-8")
        audio_track = (
            STARTER_ROOT / "src" / "reel" / "AudioTrack.tsx"
        ).read_text(encoding="utf-8")
        self.assertIn("reelStory.captionCues.find", caption_track)
        self.assertNotIn("borderRadius", caption_track)
        self.assertIn("staticFile(narration.src)", audio_track)
        self.assertIn("volume={narrationGain(narration, reelStory.audio.music)}", audio_track)

        package = json.loads(
            (STARTER_ROOT / "package.json").read_text(encoding="utf-8")
        )
        versions = {
            value
            for name, value in package["dependencies"].items()
            if name == "remotion" or name.startswith("@remotion/")
        }
        self.assertEqual(versions, {"4.0.514"})
        self.assertIn("validate", package["scripts"])
        self.assertIn("qa:plan", package["scripts"])

        story = json.loads(
            (STARTER_ROOT / "src" / "reel" / "story.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(len(story["shots"]), len(story["scenes"]))
        self.assertTrue(
            all(
                any(beat["shotId"] == shot["id"] for beat in story["beats"])
                for shot in story["shots"]
            )
        )
        self.assertIsNone(story["audio"]["narration"])
        self.assertIsNone(story["audio"]["music"])
        self.assertEqual(story["captionCues"], [])
        self.assertEqual(story["captures"], [])
        self.assertTrue(all("caption" not in scene for scene in story["scenes"]))

        treatment = json.loads(
            (
                STARTER_ROOT
                / "src"
                / "reel"
                / "treatments"
                / "tim-kochjar-reference.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(len(treatment["dimensions"]), 8)
        for dimension in treatment["dimensions"]:
            if dimension["name"] != "composition":
                self.assertIn("unknown", dimension["referenceEvidence"])

    @unittest.skipUnless(shutil.which("node"), "Node.js is required")
    def test_story_validator_rejects_placeholders_and_accepts_fixture(self) -> None:
        scaffold = load_scaffold_module()

        with tempfile.TemporaryDirectory(prefix=".reel-test-", dir=REPO_ROOT) as temp_dir:
            project = Path(temp_dir) / "reel"
            scaffold.materialize(project, "reel-test")

            starter = subprocess.run(
                [
                    "node",
                    "scripts/validate-story.mjs",
                    "--allow-placeholders",
                ],
                cwd=project,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(starter.returncode, 0, starter.stderr)

            production = subprocess.run(
                ["node", "scripts/validate-story.mjs"],
                cwd=project,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(production.returncode, 0)
            self.assertIn("Unresolved REPLACE_ME", production.stderr)

            shutil.copy2(
                FIXTURE_ROOT / "production-story.json",
                project / "src" / "reel" / "story.json",
            )
            shutil.copy2(
                FIXTURE_ROOT / "production-REEL.md",
                project / "REEL.md",
            )
            valid = subprocess.run(
                ["node", "scripts/validate-story.mjs"],
                cwd=project,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(valid.returncode, 0, valid.stderr)
            self.assertIn("Story valid: 3 scenes, 16s", valid.stdout)

            review_plan = subprocess.run(
                ["node", "scripts/build-review-plan.mjs"],
                cwd=project,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(review_plan.returncode, 0, review_plan.stderr)
            plan = json.loads(
                (project / "out" / "review-plan.json").read_text(encoding="utf-8")
            )
            purposes = {
                purpose
                for frame in plan["frames"]
                for purpose in frame["purposes"]
            }
            self.assertIn("opening-motion", purposes)
            self.assertIn("boundary:opening-1:cut", purposes)
            self.assertIn("hold:task-1:compare", purposes)
            self.assertIn("shot:task-1:entry", purposes)
            self.assertIn("shot:task-1:focus:state", purposes)
            self.assertIn("final-frame", purposes)
            self.assertEqual(plan["schemaVersion"], 2)
            self.assertEqual(
                [entry["shotId"] for entry in plan["shotEvidence"]],
                ["opening-1", "task-1", "conclusion-1"],
            )

            valid_brief = (project / "REEL.md").read_text(encoding="utf-8")
            valid_story = json.loads(
                (project / "src" / "reel" / "story.json").read_text(
                    encoding="utf-8"
                )
            )

            capture_dir = project / "public" / "captures"
            capture_dir.mkdir(parents=True, exist_ok=True)
            png_file = base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwC"
                "AAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
            )
            (capture_dir / "approval-full.png").write_bytes(png_file)
            (capture_dir / "approval-layout.json").write_text(
                '{"pageWidth": 1, "pageHeight": 1, "elements": {}}',
                encoding="utf-8",
            )
            capture_story = json.loads(json.dumps(valid_story))
            capture_story["captures"] = [
                {
                    "id": "approval-state",
                    "sourceRef": "spec-approval-flow",
                    "route": "/reviews/demo",
                    "state": "direction selected; approval available",
                    "fullFrameSrc": "captures/approval-full.png",
                    "layoutSrc": "captures/approval-layout.json",
                    "cutoutSrcs": [],
                    "viewport": {
                        "width": 1,
                        "height": 1,
                        "deviceScaleFactor": 1,
                    },
                    "privacyClass": "synthetic",
                }
            ]
            capture_story["shots"][1]["captureRef"] = "approval-state"
            capture_brief = valid_brief.replace(
                "|---|---|---|---|---|---|---|---|\n\n## Timeline",
                "|---|---|---|---|---|---|---|---|\n"
                "| approval-state | spec-approval-flow | "
                "/reviews/demo :: direction selected; approval available | "
                "captures/approval-full.png | "
                "captures/approval-layout.json | none | 1x1@1x | synthetic |\n"
                "\n## Timeline",
            )
            (project / "REEL.md").write_text(
                capture_brief,
                encoding="utf-8",
            )
            (project / "src" / "reel" / "story.json").write_text(
                json.dumps(capture_story, indent=2),
                encoding="utf-8",
            )
            valid_capture = subprocess.run(
                ["node", "scripts/validate-story.mjs"],
                cwd=project,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(valid_capture.returncode, 0, valid_capture.stderr)

            capture_story["shots"][1]["captureRef"] = None
            (project / "src" / "reel" / "story.json").write_text(
                json.dumps(capture_story, indent=2),
                encoding="utf-8",
            )
            null_capture_ref = subprocess.run(
                ["node", "scripts/validate-story.mjs"],
                cwd=project,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(null_capture_ref.returncode, 0)
            self.assertIn(
                "captureRef must be a non-empty string",
                null_capture_ref.stderr,
            )
            capture_story["shots"][1]["captureRef"] = "approval-state"

            capture_story["captures"][0]["fullFrameSrc"] = (
                "captures/missing.png"
            )
            (project / "src" / "reel" / "story.json").write_text(
                json.dumps(capture_story, indent=2),
                encoding="utf-8",
            )
            missing_capture = subprocess.run(
                ["node", "scripts/validate-story.mjs"],
                cwd=project,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(missing_capture.returncode, 0)
            self.assertIn(
                "fullFrameSrc does not exist in public",
                missing_capture.stderr,
            )
            (project / "src" / "reel" / "story.json").write_text(
                json.dumps(valid_story, indent=2),
                encoding="utf-8",
            )
            (project / "REEL.md").write_text(valid_brief, encoding="utf-8")

            drifted_brief = valid_brief.replace(
                "| opening-1 | opening | 0–3s | Approval task |",
                "| opening-1 | opening | 0–3s | Approval dashboard |",
            )
            (project / "REEL.md").write_text(drifted_brief, encoding="utf-8")
            drifted_shot_plan = subprocess.run(
                ["node", "scripts/validate-story.mjs"],
                cwd=project,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(drifted_shot_plan.returncode, 0)
            self.assertIn(
                "must match its executable story contract",
                drifted_shot_plan.stderr,
            )
            (project / "REEL.md").write_text(valid_brief, encoding="utf-8")

            subframe_story = json.loads(json.dumps(valid_story))
            subframe_story["shots"][0]["durationSeconds"] = 0.001
            subframe_story["shots"][1]["startSeconds"] = 0.001
            (project / "src" / "reel" / "story.json").write_text(
                json.dumps(subframe_story, indent=2),
                encoding="utf-8",
            )
            subframe_shot = subprocess.run(
                ["node", "scripts/validate-story.mjs"],
                cwd=project,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(subframe_shot.returncode, 0)
            self.assertIn("must occupy at least one frame", subframe_shot.stderr)
            (project / "src" / "reel" / "story.json").write_text(
                json.dumps(valid_story, indent=2),
                encoding="utf-8",
            )

            frame_gap_story = json.loads(json.dumps(valid_story))
            frame_gap_story["shots"][0]["durationSeconds"] = 3.016
            frame_gap_story["shots"][1]["startSeconds"] = 3.025
            frame_gap_story["shots"][1]["durationSeconds"] = 8.975
            (project / "src" / "reel" / "story.json").write_text(
                json.dumps(frame_gap_story, indent=2),
                encoding="utf-8",
            )
            frame_gap = subprocess.run(
                ["node", "scripts/validate-story.mjs"],
                cwd=project,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(frame_gap.returncode, 0)
            self.assertIn("must start on contiguous frame", frame_gap.stderr)
            (project / "src" / "reel" / "story.json").write_text(
                json.dumps(valid_story, indent=2),
                encoding="utf-8",
            )

            invalid_preset_story = {**valid_story, "preset": "launch-ish"}
            (project / "src" / "reel" / "story.json").write_text(
                json.dumps(invalid_preset_story, indent=2),
                encoding="utf-8",
            )
            invalid_preset = subprocess.run(
                ["node", "scripts/validate-story.mjs"],
                cwd=project,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(invalid_preset.returncode, 0)
            self.assertIn("Unsupported preset launch-ish", invalid_preset.stderr)

            optimized_story = {**valid_story, "preset": "product-launch"}
            (project / "src" / "reel" / "story.json").write_text(
                json.dumps(optimized_story, indent=2),
                encoding="utf-8",
            )
            incomplete_shot_plan = valid_brief.replace(
                "- Preset: custom",
                "- Preset: product-launch",
            ).replace(
                "| task-1 | task | 3–12s | Approval control and result | controlled-crop | Select, acknowledge, and approve | 2s | cut |\n",
                "",
            )
            (project / "REEL.md").write_text(
                incomplete_shot_plan,
                encoding="utf-8",
            )
            invalid_shot_plan = subprocess.run(
                ["node", "scripts/validate-story.mjs"],
                cwd=project,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(invalid_shot_plan.returncode, 0)
            self.assertIn(
                "product-launch requires a shot plan for scene task",
                invalid_shot_plan.stderr,
            )

            (project / "src" / "reel" / "story.json").write_text(
                json.dumps(valid_story, indent=2),
                encoding="utf-8",
            )
            (project / "REEL.md").write_text(valid_brief, encoding="utf-8")

            missing_timeline = "\n".join(
                line
                for line in valid_brief.splitlines()
                if not (
                    line.startswith("| 0–3s")
                    or line.startswith("| 3–12s")
                    or line.startswith("| 12–16s")
                )
            )
            (project / "REEL.md").write_text(
                missing_timeline,
                encoding="utf-8",
            )
            invalid_timeline = subprocess.run(
                ["node", "scripts/validate-story.mjs"],
                cwd=project,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(invalid_timeline.returncode, 0)
            self.assertIn("timeline scene order", invalid_timeline.stderr)
            (project / "REEL.md").write_text(valid_brief, encoding="utf-8")

            wrong_timing = valid_brief.replace(
                "| 0–3s | opening",
                "| 0–2s | opening",
            )
            (project / "REEL.md").write_text(wrong_timing, encoding="utf-8")
            invalid_timing = subprocess.run(
                ["node", "scripts/validate-story.mjs"],
                cwd=project,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(invalid_timing.returncode, 0)
            self.assertIn("timeline range for opening", invalid_timing.stderr)
            (project / "REEL.md").write_text(valid_brief, encoding="utf-8")

            active_story = json.loads(
                (project / "src" / "reel" / "story.json").read_text(
                    encoding="utf-8"
                )
            )
            active_story["scriptLocked"] = True
            active_story["scenes"][0]["narration"] = "Introduce the approval task."
            active_story["audio"]["narration"] = {
                "src": "audio/approval.wav",
                "durationSeconds": 2.5,
                "provenanceRef": "audio/approval.provenance.json",
                "qualityGate": "enhanced-kokoro",
                "approvalNote": "",
                "volume": 1,
            }
            active_story["beats"].insert(
                1,
                {
                    "id": "opening-speech",
                    "sceneId": "opening",
                    "shotId": "opening-1",
                    "atSeconds": 0.75,
                    "kind": "speech",
                    "anchorText": "approval task",
                    "purpose": "Align the approval phrase",
                },
            )
            narrated_brief = valid_brief.replace(
                "| opening-reveal | opening-1 | 0.5s | action | none |",
                "| opening-reveal | opening-1 | 0.5s | action | none |\n"
                "| opening-speech | opening-1 | 0.75s | speech | approval task |",
            )
            (project / "REEL.md").write_text(narrated_brief, encoding="utf-8")
            audio_dir = project / "public" / "audio"
            audio_dir.mkdir(parents=True, exist_ok=True)
            (audio_dir / "approval.wav").write_bytes(b"fixture")
            (audio_dir / "approval.provenance.json").write_text(
                '{"mode":"enhanced","engine":{"name":"kokoro-onnx"},'
                '"model":{"id":"thewh1teagle/kokoro-onnx"}}',
                encoding="utf-8",
            )
            (project / "src" / "reel" / "story.json").write_text(
                json.dumps(active_story, indent=2),
                encoding="utf-8",
            )

            invalid_audio = subprocess.run(
                ["node", "scripts/validate-story.mjs"],
                cwd=project,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(invalid_audio.returncode, 0)
            self.assertIn("must be a readable WAV file", invalid_audio.stderr)
            with wave.open(str(audio_dir / "approval.wav"), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(8000)
                wav.writeframes(b"\x00\x00" * 20000)

            (audio_dir / "approval.provenance.json").write_text(
                "null",
                encoding="utf-8",
            )
            null_provenance = subprocess.run(
                ["node", "scripts/validate-story.mjs"],
                cwd=project,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(null_provenance.returncode, 0)
            self.assertIn(
                "must contain a JSON object",
                null_provenance.stderr,
            )
            (audio_dir / "approval.provenance.json").write_text(
                '{"mode":"enhanced","engine":{"name":"kokoro-onnx"},'
                '"model":{"id":"thewh1teagle/kokoro-onnx"}}',
                encoding="utf-8",
            )
            (project / "src" / "reel" / "story.json").write_text(
                json.dumps(active_story, indent=2),
                encoding="utf-8",
            )
            missing_caption = subprocess.run(
                ["node", "scripts/validate-story.mjs"],
                cwd=project,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(missing_caption.returncode, 0)
            self.assertIn(
                "Narrated scene opening requires a caption cue",
                missing_caption.stderr,
            )

            active_story["captionCues"] = [
                {
                    "id": "opening-caption",
                    "sceneId": "opening",
                    "startSeconds": 0.5,
                    "endSeconds": 2,
                    "text": "Introduce the approval task.",
                }
            ]
            empty_caption_story = json.loads(json.dumps(active_story))
            empty_caption_story["beats"][1]["atSeconds"] = 1.005
            empty_caption_story["captionCues"][0]["startSeconds"] = 1.001
            empty_caption_story["captionCues"][0]["endSeconds"] = 1.02
            (project / "src" / "reel" / "story.json").write_text(
                json.dumps(empty_caption_story, indent=2),
                encoding="utf-8",
            )
            empty_caption = subprocess.run(
                ["node", "scripts/validate-story.mjs"],
                cwd=project,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(empty_caption.returncode, 0)
            self.assertIn(
                "must contain at least one rendered frame",
                empty_caption.stderr,
            )
            (project / "src" / "reel" / "story.json").write_text(
                json.dumps(active_story, indent=2),
                encoding="utf-8",
            )
            valid_narration_story = subprocess.run(
                ["node", "scripts/validate-story.mjs"],
                cwd=project,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                valid_narration_story.returncode,
                0,
                valid_narration_story.stderr,
            )

            (audio_dir / "approval.provenance.json").write_text(
                "not-json",
                encoding="utf-8",
            )
            malformed_provenance = subprocess.run(
                ["node", "scripts/validate-story.mjs"],
                cwd=project,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(malformed_provenance.returncode, 0)
            self.assertIn(
                "must contain valid JSON",
                malformed_provenance.stderr,
            )
            (audio_dir / "approval.provenance.json").write_text(
                '{"mode":"enhanced","engine":{"name":"kokoro-onnx"},'
                '"model":{"id":"thewh1teagle/kokoro-onnx"}}',
                encoding="utf-8",
            )

            (audio_dir / "approval.provenance.json").write_text(
                '{"mode":"enhanced","engine":{"name":"not-kokoro"},'
                '"model":{"id":"not-kokoro"}}',
                encoding="utf-8",
            )
            false_kokoro_match = subprocess.run(
                ["node", "scripts/validate-story.mjs"],
                cwd=project,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(false_kokoro_match.returncode, 0)
            self.assertIn(
                "must report enhanced mode and Kokoro",
                false_kokoro_match.stderr,
            )
            (audio_dir / "approval.provenance.json").write_text(
                '{"mode":"enhanced","engine":{"name":"kokoro-onnx"},'
                '"model":{"id":"thewh1teagle/kokoro-onnx"}}',
                encoding="utf-8",
            )

            active_story["captionCues"][0]["text"] = "Approval task"
            (project / "src" / "reel" / "story.json").write_text(
                json.dumps(active_story, indent=2),
                encoding="utf-8",
            )
            incomplete_caption = subprocess.run(
                ["node", "scripts/validate-story.mjs"],
                cwd=project,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(incomplete_caption.returncode, 0)
            self.assertIn(
                "must cover its locked narration",
                incomplete_caption.stderr,
            )
            active_story["captionCues"][0]["text"] = (
                "Introduce the approval task."
            )

            active_story["beats"][1]["atSeconds"] = 3
            (project / "src" / "reel" / "story.json").write_text(
                json.dumps(active_story, indent=2),
                encoding="utf-8",
            )
            end_boundary_beat = subprocess.run(
                ["node", "scripts/validate-story.mjs"],
                cwd=project,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(end_boundary_beat.returncode, 0)
            self.assertIn(
                "Beat opening-speech falls outside shot opening-1",
                end_boundary_beat.stderr,
            )
            active_story["beats"][1]["atSeconds"] = 0.75

            active_story["beats"][1]["atSeconds"] = 2.25
            (project / "src" / "reel" / "story.json").write_text(
                json.dumps(active_story, indent=2),
                encoding="utf-8",
            )
            misaligned_speech = subprocess.run(
                ["node", "scripts/validate-story.mjs"],
                cwd=project,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(misaligned_speech.returncode, 0)
            self.assertIn(
                "must align with a caption cue",
                misaligned_speech.stderr,
            )
            active_story["beats"][1]["atSeconds"] = 0.75

            active_story["scenes"][0]["kind"] = "narration"
            (project / "src" / "reel" / "story.json").write_text(
                json.dumps(active_story, indent=2),
                encoding="utf-8",
            )
            unsupported_kind = subprocess.run(
                ["node", "scripts/validate-story.mjs"],
                cwd=project,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(unsupported_kind.returncode, 0)
            self.assertIn("unsupported kind narration", unsupported_kind.stderr)

            active_story["scenes"][0]["kind"] = "opening"
            active_story["treatment"] = "tim-kochjar-reference"
            (project / "src" / "reel" / "story.json").write_text(
                json.dumps(active_story, indent=2),
                encoding="utf-8",
            )
            incomplete_treatment = subprocess.run(
                ["node", "scripts/validate-story.mjs"],
                cwd=project,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(incomplete_treatment.returncode, 0)
            self.assertIn(
                "treatment map contains unresolved REPLACE_ME",
                incomplete_treatment.stderr,
            )

            treatment_path = (
                project
                / "src"
                / "reel"
                / "treatments"
                / "tim-kochjar-reference.json"
            )
            treatment = json.loads(treatment_path.read_text(encoding="utf-8"))
            for dimension in treatment["dimensions"]:
                dimension["transferDecision"] = "transfer"
                dimension["implementation"] = "source-backed implementation"
                dimension["verification"] = "playback and frame check"
            treatment["dimensions"][0]["referenceEvidence"] = (
                "Exact proprietary camera system recovered"
            )
            treatment_path.write_text(
                json.dumps(treatment, indent=2),
                encoding="utf-8",
            )
            changed_evidence = subprocess.run(
                ["node", "scripts/validate-story.mjs"],
                cwd=project,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(changed_evidence.returncode, 0)
            self.assertIn(
                "reference evidence differs from the canonical map",
                changed_evidence.stderr,
            )

    @unittest.skipUnless(shutil.which("node"), "Node.js is required")
    def test_optional_music_validation(self) -> None:
        scaffold = load_scaffold_module()
        with tempfile.TemporaryDirectory(prefix=".reel-test-", dir=REPO_ROOT) as work:
            project = Path(work) / "reel"
            scaffold.materialize(project, "music-test")
            shutil.copy2(FIXTURE_ROOT / "production-REEL.md", project / "REEL.md")
            story_path = project / "src" / "reel" / "story.json"
            old_story = json.loads(
                (FIXTURE_ROOT / "production-story.json").read_text(encoding="utf-8")
            )
            old_story["audio"].pop("music", None)

            def validate(story):
                story_path.write_text(json.dumps(story), encoding="utf-8")
                return subprocess.run(
                    ["node", "scripts/validate-story.mjs"], cwd=project,
                    capture_output=True, text=True, check=False,
                )

            for audio in (old_story["audio"], {**old_story["audio"], "music": None}):
                result = validate({**old_story, "audio": audio})
                self.assertEqual(result.returncode, 0, result.stderr)

            audio_dir = project / "public" / "audio"
            audio_dir.mkdir(parents=True, exist_ok=True)
            wav_path = audio_dir / "music.wav"
            with wave.open(str(wav_path), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(8000)
                wav.writeframes(b"\x00\x00" * 8000 * 8)
            wav_bytes = wav_path.read_bytes()
            provenance = {
                "schemaVersion": 1, "success": True,
                "kind": "ai-generated-music", "provider": "ace-step",
                "model": "ace-step-v1", "promptSha256": "a" * 64,
                "outputSha256": hashlib.sha256(wav_bytes).hexdigest(),
                "durationSeconds": 8, "instrumental": True, "seed": 42,
                "licenseNote": "Synthetic test audio; not production clearance.",
            }
            sidecar = audio_dir / "music.wav.json"
            sidecar.write_text(json.dumps(provenance), encoding="utf-8")
            music = {
                "src": "audio/music.wav", "durationSeconds": 8,
                "provenanceRef": "audio/music.wav.json",
                "startSeconds": 2, "endSeconds": 8, "sourceStartSeconds": 1,
                "volume": 0.3, "duckVolume": 0.1,
                "fadeInSeconds": 0.5, "fadeOutSeconds": 0.5,
                "duckAttackSeconds": 0.2, "duckReleaseSeconds": 0.4,
            }
            story = copy.deepcopy(old_story)
            story["audio"]["music"] = music
            result = validate(story)
            self.assertEqual(result.returncode, 0, result.stderr)
            for channels in (1, 2):
                for sample_width, format_tag in ((2, 1), (3, 1), (4, 1), (4, 3)):
                    with self.subTest(channels=channels, width=sample_width, format=format_tag):
                        with wave.open(str(wav_path), "wb") as wav:
                            wav.setnchannels(channels)
                            wav.setsampwidth(sample_width)
                            wav.setframerate(8000)
                            wav.writeframes(bytes(8000 * 8 * channels * sample_width))
                        generated = bytearray(wav_path.read_bytes())
                        generated[20:22] = format_tag.to_bytes(2, "little")
                        wav_path.write_bytes(generated)
                        sidecar.write_text(json.dumps({
                            **provenance,
                            "outputSha256": hashlib.sha256(generated).hexdigest(),
                        }), encoding="utf-8")
                        result = validate(story)
                        self.assertEqual(result.returncode, 0, result.stderr)
            wav_path.write_bytes(wav_bytes)
            sidecar.write_text(json.dumps(provenance), encoding="utf-8")
            fps = story["format"]["fps"]
            music_cases = [
                ({"sourceStartSeconds": 3}, "source duration"),
                ({"durationSeconds": 7.9}, "measured full audio"),
                ({"startSeconds": -1}, "non-negative"),
                ({"endSeconds": 17}, "bounded by the composition"),
                ({"volume": 1.1}, "volume must be"),
                ({"duckVolume": 0.4}, "duckVolume"),
                ({"volume": "0.3"}, "finite non-negative"),
                ({"sourceStartSeconds": None}, "finite non-negative"),
                ({"fadeInSeconds": -1}, "non-negative"),
                ({"fadeInSeconds": 4, "fadeOutSeconds": 4}, "fade lengths"),
                ({"fadeOutSeconds": 0.01 / fps}, "at least one frame"),
                ({"duckAttackSeconds": 0}, "at least one frame"),
                ({"duckReleaseSeconds": -1}, "at least one frame"),
                ({"startSeconds": 2, "endSeconds": 2 + 0.1 / fps}, "at least one frame"),
                ({
                    "startSeconds": 0.49 / fps, "endSeconds": 8 - 0.49 / fps,
                    "sourceStartSeconds": 0.51 / fps,
                }, "including frame quantization"),
            ]
            for changes, expected in music_cases:
                with self.subTest(music=changes):
                    candidate = copy.deepcopy(story)
                    candidate["audio"]["music"].update(changes)
                    result = validate(candidate)
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertIn(expected, result.stderr)

            for malformed in (False, [], "", 42):
                with self.subTest(malformed=malformed):
                    result = validate({**story, "audio": {**story["audio"], "music": malformed}})
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("must be an object", result.stderr)
            for field in music:
                with self.subTest(missing=field):
                    candidate = copy.deepcopy(story)
                    del candidate["audio"]["music"][field]
                    self.assertNotEqual(validate(candidate).returncode, 0)

            provenance_cases = [
                ("outputSha256", "0" * 64), ("provider", "unsupported"),
                ("schemaVersion", 2), ("success", False),
                ("kind", "stock-music"), ("model", ""),
                ("promptSha256", "A" * 64), ("durationSeconds", 7.9),
                ("instrumental", False), ("seed", -1), ("seed", True),
                ("licenseNote", " "),
            ]
            for field, value in provenance_cases:
                with self.subTest(provenance=field, value=value):
                    sidecar.write_text(json.dumps({**provenance, field: value}), encoding="utf-8")
                    result = validate(story)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(f"provenance {field}", result.stderr)
            for invalid_json in ("{broken", "null", "[]"):
                sidecar.write_text(invalid_json, encoding="utf-8")
                self.assertNotEqual(validate(story).returncode, 0)
            sidecar.write_text(json.dumps(provenance), encoding="utf-8")

            # Out-of-root files are local fixture data, never host-private files.
            (project / "outside.wav").write_bytes(wav_bytes)
            (project / "outside.json").write_text(json.dumps(provenance), encoding="utf-8")
            (audio_dir / "escape.wav").symlink_to(project / "outside.wav")
            (audio_dir / "escape.json").symlink_to(project / "outside.json")
            for field, extension in (("src", "wav"), ("provenanceRef", "json")):
                for path in (
                    f"audio/../../outside.{extension}", f"/audio/music.{extension}",
                    f"audio/%2e%2e/outside.{extension}", f"audio\\music.{extension}",
                    f"audio//music.{extension}", f"audio/./music.{extension}",
                    f"https://example.com/music.{extension}", f"audio/escape.{extension}",
                    f"audio/music.{extension}?query", f"audio/music.{extension}\x00",
                ):
                    with self.subTest(field=field, path=path):
                        candidate = copy.deepcopy(story)
                        candidate["audio"]["music"][field] = path
                        result = validate(candidate)
                        self.assertNotEqual(result.returncode, 0)
                        self.assertIn(f"audio.music {field}", result.stderr)
                        self.assertNotIn("readable WAV", result.stderr)
                        self.assertNotIn("provenance outputSha256", result.stderr)

            bad_format = bytearray(wav_bytes)
            bad_format[20:22] = (7).to_bytes(2, "little")
            bad_rate = bytearray(wav_bytes)
            bad_rate[28:32] = (1).to_bytes(4, "little")
            for bad_wav in (b"invalid", wav_bytes[:-1], bad_format, bad_rate):
                wav_path.write_bytes(bad_wav)
                result = validate(story)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("readable WAV", result.stderr)
            wav_path.write_bytes(wav_bytes)
            # Nonzero fractional timing is valid when both raw and rounded source fit.
            candidate = copy.deepcopy(story)
            candidate["audio"]["music"].update({
                "startSeconds": 2.01, "endSeconds": 7.99,
                "sourceStartSeconds": 0.51 / fps,
            })
            result = validate(candidate)
            self.assertEqual(result.returncode, 0, result.stderr)

            narrated = copy.deepcopy(story)
            narrated["scriptLocked"] = True
            narrated["scenes"][0]["narration"] = "Introduce the approval task."
            narrated["audio"]["narration"] = {
                "src": "audio/voice.wav", "durationSeconds": 2.5,
                "provenanceRef": "audio/voice.json", "qualityGate": "enhanced-kokoro",
                "approvalNote": "", "volume": 0.9,
            }
            with wave.open(str(audio_dir / "voice.wav"), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(8000)
                wav.writeframes(b"\x00\x00" * 20000)
            (audio_dir / "voice.json").write_text(json.dumps({
                "mode": "enhanced", "engine": "kokoro-onnx", "model": "kokoro",
            }), encoding="utf-8")
            narrated["captionCues"] = [{
                "id": "opening-caption", "sceneId": "opening",
                "startSeconds": 0, "endSeconds": 2.5,
                "text": "Introduce the approval task.",
            }]
            narrated["beats"].insert(1, {
                "id": "opening-speech", "sceneId": "opening", "shotId": "opening-1",
                "atSeconds": 0.75, "kind": "speech", "anchorText": "approval task",
                "purpose": "Align the approval phrase",
            })
            brief = (project / "REEL.md").read_text(encoding="utf-8")
            (project / "REEL.md").write_text(brief.replace(
                "| opening-reveal | opening-1 | 0.5s | action | none |",
                "| opening-reveal | opening-1 | 0.5s | action | none |\n"
                "| opening-speech | opening-1 | 0.75s | speech | approval task |",
            ), encoding="utf-8")
            result = validate(narrated)
            self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipUnless(shutil.which("node"), "Node.js is required")
    def test_music_envelope_is_frame_deterministic(self) -> None:
        result = subprocess.run(
            ["node", "--experimental-strip-types", "--input-type=module", "-e", """
import assert from 'node:assert/strict';
import {musicGain, musicTiming, narrationGain} from './src/reel/music-envelope.ts';
const music = {
  startSeconds: 2, endSeconds: 8, sourceStartSeconds: 1, durationSeconds: 10,
  volume: 0.6, duckVolume: 0.3, fadeInSeconds: 0.5, fadeOutSeconds: 0.5,
  duckAttackSeconds: 0.5, duckReleaseSeconds: 0.5,
};
const narration = {volume: 0.85, durationSeconds: 8};
const cues = [{startSeconds: 4, endSeconds: 5}, {startSeconds: 5.1, endSeconds: 6}];
const fps = 30;
const gain = (frame, voice = narration, intervals = cues) =>
  musicGain(frame, fps, music, voice, intervals);
assert.deepEqual(musicTiming(music, fps), {from: 60, durationInFrames: 180, trimBefore: 30});
assert.equal(gain(59), 0);
assert.equal(gain(60), 0);
assert.equal(gain(239), 0);
assert.equal(gain(240), 0);
assert.equal(gain(100, null), 0.6);
assert.equal(gain(130, null), 0.6);
assert.equal(gain(130, narration, []), 0.6);
assert.equal(narrationGain(narration), narration.volume);
assert.equal(narrationGain(narration, null), narration.volume);
assert.equal(narrationGain(narration, music), narration.volume * (1 - music.volume));
assert.equal(gain(130), music.duckVolume);
assert.ok(gain(130) + narrationGain(narration, music) <= 1);
const defaultMusic = {...music, volume: 0.18, duckVolume: 0.06};
const fullVoice = {...narration, volume: 1};
assert.equal(narrationGain(fullVoice, defaultMusic), 1 - 0.18);
assert.equal(musicGain(130, fps, defaultMusic, fullVoice, cues), 0.06);
assert.equal(gain(130), gain(130, narration, [...cues].reverse()));
assert.equal(gain(130), musicGain(130, fps, {...music, sourceStartSeconds: 3}, narration, cues));
assert.equal(musicGain(60, fps, {...music, fadeInSeconds: 0}, null, []), 0.6);
assert.equal(musicGain(239, fps, {...music, fadeOutSeconds: 0}, null, []), 0.6);
for (let frame = 60; frame < 75; frame++) assert.ok(gain(frame) <= gain(frame + 1));
for (let frame = 105; frame < 120; frame++) assert.ok(gain(frame) >= gain(frame + 1));
for (let frame = 180; frame < 195; frame++) assert.ok(gain(frame) <= gain(frame + 1));
for (let frame = 224; frame < 239; frame++) assert.ok(gain(frame) >= gain(frame + 1));
for (let frame = 150; frame <= 153; frame++) assert.ok(gain(frame) < 0.35, 'short phrase gap stays ducked');
for (const rate of [24, 30, 60]) {
  const frames = Array.from({length: 10 * rate}, (_, frame) =>
    musicGain(frame, rate, music, narration, cues));
  for (let frame = 0; frame < frames.length; frame++) {
    assert.ok(Number.isFinite(frames[frame]));
    assert.ok(frames[frame] >= 0 && frames[frame] <= music.volume);
    assert.ok(frames[frame] + narrationGain(fullVoice, music) <= 1);
    assert.equal(frames[frame], musicGain(frame, rate, music, narration, cues));
    if (frame) assert.ok(Math.abs(frames[frame] - frames[frame - 1]) < 0.08);
  }
}
assert.equal(gain(Number.NaN), 0);
"""],
            cwd=STARTER_ROOT, check=False, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipUnless(shutil.which("node"), "Node.js is required")
    def test_review_plan_includes_intra_scene_shot_boundaries(self) -> None:
        scaffold = load_scaffold_module()

        with tempfile.TemporaryDirectory(prefix=".reel-test-", dir=REPO_ROOT) as temp_dir:
            project = Path(temp_dir) / "reel"
            scaffold.materialize(project, "reel-review-plan-test")
            story = json.loads(
                (FIXTURE_ROOT / "production-story.json").read_text(
                    encoding="utf-8"
                )
            )
            story["beats"][0]["atSeconds"] = 2
            task_shot = story["shots"][1]
            story["shots"][1:2] = [
                {
                    **task_shot,
                    "id": "task-entry",
                    "durationSeconds": 4,
                },
                {
                    **task_shot,
                    "id": "task-result",
                    "startSeconds": 7,
                    "durationSeconds": 5,
                },
            ]
            for beat in story["beats"]:
                if beat["shotId"] == "task-1":
                    beat["shotId"] = (
                        "task-entry" if beat["atSeconds"] < 7 else "task-result"
                    )
            (project / "src" / "reel" / "story.json").write_text(
                json.dumps(story, indent=2),
                encoding="utf-8",
            )

            result = subprocess.run(
                ["node", "scripts/build-review-plan.mjs"],
                cwd=project,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            plan = json.loads(
                (project / "out" / "review-plan.json").read_text(encoding="utf-8")
            )
            purposes = {
                purpose
                for frame in plan["frames"]
                for purpose in frame["purposes"]
            }
            self.assertIn("boundary:task-entry:cut", purposes)
            self.assertTrue(
                any(
                    frame["frame"] == 60
                    and "opening-motion" in frame["purposes"]
                    for frame in plan["frames"]
                )
            )


if __name__ == "__main__":
    unittest.main()
