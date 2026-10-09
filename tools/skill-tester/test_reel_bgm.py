import importlib.util
import hashlib
from contextlib import contextmanager, redirect_stdout, redirect_stderr
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import shutil
import subprocess
import struct
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import wave


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "skills/reel/scripts/generate_bgm.py"
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("reel_bgm", SCRIPT)
bgm = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bgm)


def wav_bytes(seconds=2):
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setnchannels(2)
        output.setsampwidth(2)
        output.setframerate(8000)
        output.writeframes(b"\x01\x00" * (int(seconds * 8000) * 2))
    return buffer.getvalue()


def library_asset():
    audio = wav_bytes()
    return {
        "audio": audio, "audioFormat": "wav",
        "provenance": {
            "kind": "licensed-library-music", "provider": "wikimedia-commons",
            "license": "CC0-1.0",
            "licenseUrl": "https://creativecommons.org/publicdomain/zero/1.0/",
            "sourceUrl": "https://commons.wikimedia.org/wiki/File:Fixture.wav",
            "sourceDownloadUrl": "https://upload.wikimedia.org/wikipedia/commons/a/ab/Fixture.wav",
            "title": "Parser fixture, not real music", "creator": "Fixture author",
            "sourceRevisionId": 123,
            "sourceFileSha1": hashlib.sha1(audio).hexdigest(),
            "verifiedAt": "2026-09-10T12:00:00Z",
            "attributionRequired": False, "allowsProjectRedistribution": True,
            "selectionRationale": "Matches the fixture's calm piano tags.",
        },
    }


def dynamic_library_asset():
    """MPEG header/parser fixture; not real music or an acquisition proof."""
    audio = (b"\xff\xfb\x90\x00" + b"\x00" * 413) * 90
    provenance = library_asset()["provenance"]
    provenance.pop("sourceRevisionId")
    provenance.update(
        provider="incompetech", license="CC-BY-4.0",
        licenseUrl="https://creativecommons.org/licenses/by/4.0/",
        attributionRequired=True, creator="Kevin MacLeod",
        creditCreators="Kevin MacLeod (incompetech.com)", trackId="USUAN1100001",
        sourceUrl="https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1100001",
        sourceDownloadUrl="https://incompetech.com/music/royalty-free/mp3-royaltyfree/Fixture.mp3",
        sourceCatalogSha256="1" * 64, sourceLicenseSha256="2" * 64,
        sourceFileSha1=hashlib.sha1(audio).hexdigest(),
        sourceSha256=hashlib.sha256(audio).hexdigest(),
    )
    return {"audio": audio, "audioFormat": "mp3", "provenance": provenance}


def flac_metadata_fixture(seconds=2):
    """Metadata/parser fixture, not decodable music or generation evidence."""
    packed = (8000 << 44) | (1 << 41) | (15 << 36) | int(seconds * 8000)
    streaminfo = b"\x00\x10\x00\x10" + b"\x00" * 6 + packed.to_bytes(8, "big") + b"\x00" * 16
    return b"fLaC\x80\x00\x00\x22" + streaminfo + b"\xff\xf8" + b"\x00" * 8


def model_inventory(loaded=True):
    return {
        "models": [{
            "name": bgm.SUPPORTED_MODEL,
            "is_loaded": loaded,
            "supported_task_types": ["text2music"],
        }]
    }


@contextmanager
def local_provider():
    """Protocol fixture only; the synthetic WAV is not generated music."""
    calls = []
    polls = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def respond(self, value, audio=False):
            content = value if audio else json.dumps({
                "code": 200, "error": None, "data": value,
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "audio/wav" if audio else "application/json")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def do_GET(self):
            calls.append((self.path, None, self.headers.get("Authorization")))
            if self.path == "/v1/models":
                self.respond(model_inventory())
            elif self.path == "/v1/audio?path=generated.wav":
                self.respond(wav_bytes(), audio=True)
            else:
                self.send_error(404)

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            calls.append((self.path, payload, self.headers.get("Authorization")))
            if self.path == "/release_task":
                self.respond({"task_id": "fixture-job", "status": "queued"})
            elif self.path == "/query_result":
                polls.append(payload)
                self.respond([{
                    "task_id": "fixture-job",
                    "status": 0 if len(polls) == 1 else 1,
                    "result": json.dumps([{
                        "file": "/v1/audio?path=generated.wav", "status": 1,
                    }]),
                }])
            else:
                self.send_error(404)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


class BgmPreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        (self.project / "src/reel").mkdir(parents=True)
        self.story_path = self.project / "src/reel/story.json"
        self.story = {
            "format": {"fps": 30},
            "scenes": [{"durationSeconds": 2, "narration": ""}],
            "shots": [{"startSeconds": 0, "durationSeconds": 2}],
            "audio": {"narration": None},
        }
        self.brief_path = self.project / "music-brief.json"
        self.brief = {
            "direction": {
                "emotion": "Warm and confident",
                "arc": "Focused opening, hopeful ending",
                "instruments": "Piano and soft synthesizer",
                "pace": "Moderate, restrained pulse",
                "narration": "Low presence beneath speech",
            },
            "prompt": "Warm minimal instrumental piano; no vocals.",
            "rationale": "Supports the hopeful ending.",
            "instrumental": True,
            "seed": 42,
            "bpm": 96,
            "keyScale": "C Major",
            "timeSignature": "4",
            "libraryTags": ["calm", "piano"],
        }
        self.write_inputs()

    def write_inputs(self):
        self.story_path.write_text(json.dumps(self.story), encoding="utf-8")
        self.brief_path.write_text(json.dumps(self.brief), encoding="utf-8")

    def prepare(self):
        return bgm.prepare(self.project, self.brief_path, "underscore")

    def approve(self, mode="approved"):
        self.brief["approval"] = {
            "mode": mode,
            "fingerprint": bgm.approval_fingerprint(self.prepare()),
            "decisionRef": "fixture user decision, not real approval",
        }
        self.write_inputs()

    def auto(self, *extra):
        output, error = io.StringIO(), io.StringIO()
        with patch("sys.argv", [
            str(SCRIPT), "generate", "--provider", "auto",
            "--library-source", "commons",
            "--project", str(self.project), "--brief", str(self.brief_path), *extra,
        ]), redirect_stdout(output), redirect_stderr(error):
            code = bgm.main()
        return code, output.getvalue(), error.getvalue()

    def test_auto_ai_failure_searches_dynamic_library_and_publishes_mp3(self):
        self.approve()
        with patch.object(bgm, "HostedAceStep") as hosted, patch.object(
            bgm, "IncompetechMusic"
        ) as dynamic, patch.object(bgm, "LibraryMusic") as curated:
            hosted.return_value.models.side_effect = bgm.HostedBgmError("quota: no GPU")
            dynamic.return_value.acquire.return_value = dynamic_library_asset()
            code, output, error = self.auto("--library-source", "auto")
        self.assertEqual(code, 0, error)
        result = json.loads(output)
        self.assertEqual(result["provider"], "incompetech")
        self.assertTrue(result["output"].endswith(".mp3"))
        self.assertTrue(Path(result["licenseFile"]).is_file())
        sidecar = json.loads(Path(result["provenance"]).read_text())
        self.assertNotIn("sourceRevisionId", sidecar)
        self.assertNotIn("model", sidecar)
        self.assertEqual(sidecar["fallback"]["reason"], "quota: no GPU")
        self.assertIn("Kevin MacLeod (incompetech.com)", json.loads(self.story_path.read_text())["audio"]["music"]["attribution"])
        self.assertIn("Source catalog SHA-256:", Path(result["licenseFile"]).read_text())
        dynamic.return_value.acquire.assert_called_once_with(self.brief, 2)
        curated.assert_not_called()
        for name in ("MusicCredits.tsx", "Reel.tsx"):
            shutil.copyfile(
                REPO_ROOT / "skills/reel/assets/remotion-starter/src/reel" / name,
                self.project / "src/reel" / name,
            )
        module = (REPO_ROOT / "skills/reel/assets/remotion-starter/scripts/validate-music.mjs").as_uri()
        script = (
            f"import {{validateMusic}} from {json.dumps(module)};"
            "import {readFileSync} from 'node:fs';"
            "const errors=validateMusic(JSON.parse(readFileSync('src/reel/story.json')),2,()=>2);"
            "console.log(JSON.stringify(errors));process.exitCode=errors.length?1:0;"
        )
        validated = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            cwd=self.project, capture_output=True, text=True,
        )
        self.assertEqual(validated.returncode, 0, validated.stdout + validated.stderr)

    def test_dynamic_failure_uses_curated_library_and_retains_both_failures(self):
        self.approve()
        with patch.object(bgm, "HostedAceStep") as hosted, patch.object(
            bgm, "IncompetechMusic"
        ) as dynamic, patch.object(bgm, "LibraryMusic") as curated:
            dynamic.return_value.acquire.side_effect = bgm.LibraryBgmError("network: catalog unavailable")
            curated.return_value.acquire.return_value = library_asset()
            code, output, error = self.auto("--library-source", "auto", "--known-ai-blocker", "quota")
        self.assertEqual(code, 0, error)
        hosted.assert_not_called()
        result = json.loads(output)
        self.assertEqual(result["provider"], "wikimedia-commons")
        self.assertEqual(result["libraryFailures"][0]["provider"], "incompetech")
        self.assertEqual(result["fallback"]["reason"], "known-quota")

    def test_no_credit_brief_never_contacts_dynamic_cc_by_library(self):
        self.brief["allowAttribution"] = False
        self.write_inputs()
        self.approve()
        with patch.object(bgm, "IncompetechMusic") as dynamic, patch.object(bgm, "LibraryMusic") as curated:
            curated.return_value.acquire.return_value = library_asset()
            code, _, error = self.auto("--library-source", "auto", "--known-ai-blocker", "quota")
        self.assertEqual(code, 0, error)
        dynamic.assert_not_called()

    def test_dynamic_invalid_audio_falls_back_without_publishing_it(self):
        self.approve()
        asset = dynamic_library_asset()
        asset["audio"] = b"not an MP3"
        with patch.object(bgm, "IncompetechMusic") as dynamic, patch.object(bgm, "LibraryMusic") as curated:
            dynamic.return_value.acquire.return_value = asset
            curated.return_value.acquire.return_value = library_asset()
            code, output, error = self.auto("--library-source", "auto", "--known-ai-blocker", "quota")
        self.assertEqual(code, 0, error)
        self.assertEqual(json.loads(output)["provider"], "wikimedia-commons")
        self.assertFalse((self.project / "public/audio/bgm.mp3").exists())

    def test_explicit_dynamic_source_failure_does_not_try_curated(self):
        self.approve()
        before = self.story_path.read_bytes()
        with patch.object(bgm, "IncompetechMusic") as dynamic, patch.object(bgm, "LibraryMusic") as curated:
            dynamic.return_value.acquire.side_effect = bgm.LibraryBgmError("selection: no match")
            code, _, error = self.auto("--library-source", "incompetech", "--known-ai-blocker", "quota")
        self.assertEqual(code, 1)
        self.assertIn("no match", error)
        curated.assert_not_called()
        self.assertEqual(self.story_path.read_bytes(), before)

    def test_dynamic_mp3_collision_stops_before_network(self):
        self.approve()
        output = self.project / "public/audio/bgm.mp3"
        output.parent.mkdir(parents=True)
        output.write_bytes(b"existing soundtrack")
        with patch.object(bgm, "IncompetechMusic") as dynamic, patch.object(bgm, "LibraryMusic") as curated:
            code, _, error = self.auto("--library-source", "auto", "--known-ai-blocker", "quota")
        self.assertEqual(code, 1)
        self.assertIn("already exists", error)
        dynamic.assert_not_called()
        curated.assert_not_called()
        self.assertEqual(output.read_bytes(), b"existing soundtrack")

    def test_auto_provider_failure_selects_library_without_confirmation(self):
        self.approve()
        with patch.object(bgm, "HostedAceStep") as hosted, patch.object(bgm, "LibraryMusic") as library:
            hosted.return_value.models.side_effect = bgm.HostedBgmError("quota: unavailable")
            library.return_value.acquire.return_value = library_asset()
            code, output, error = self.auto()
        self.assertEqual(code, 0, error)
        result = json.loads(output)
        self.assertEqual(result["kind"], "licensed-library-music")
        self.assertEqual(result["provider"], "wikimedia-commons")
        self.assertEqual(result["fallback"]["reason"], "quota: unavailable")
        self.assertFalse(result["fallback"]["generationSubmitted"])
        hosted.return_value.generate.assert_not_called()
        library.return_value.acquire.assert_called_once_with(self.brief, 2)
        sidecar = json.loads(Path(result["provenance"]).read_text())
        self.assertEqual(sidecar["license"], "CC0-1.0")
        self.assertNotIn("model", sidecar)
        self.assertNotIn("seed", sidecar)
        self.assertEqual(sidecar["directionApproval"]["mode"], "approved")

    def test_known_quota_skips_ai_and_fetches_library(self):
        self.approve()
        with patch.object(bgm, "HostedAceStep") as hosted, patch.object(bgm, "LibraryMusic") as library:
            library.return_value.acquire.return_value = library_asset()
            code, output, error = self.auto("--known-ai-blocker", "quota")
        self.assertEqual(code, 0, error)
        hosted.assert_not_called()
        self.assertFalse(json.loads(output)["fallback"]["providerContacted"])
        library.return_value.acquire.assert_called_once()

    def test_auto_rejects_invalid_tags_before_hosted_request(self):
        self.brief["libraryTags"] = ["invented-tag"]
        self.write_inputs()
        self.approve()
        with patch.object(bgm, "HostedAceStep") as hosted:
            code, _, error = self.auto()
        self.assertEqual(code, 1)
        self.assertIn("libraryTags", error)
        hosted.assert_not_called()

    def test_auto_cloud_success_does_not_download_library(self):
        self.approve()
        with patch.object(bgm, "HostedAceStep") as hosted, patch.object(bgm, "LibraryMusic") as library:
            hosted.return_value.models.return_value = [bgm.SUPPORTED_MODEL]
            hosted.return_value.generate.return_value = flac_metadata_fixture()
            code, output, error = self.auto()
        self.assertEqual(code, 0, error)
        self.assertEqual(json.loads(output)["provider"], "huggingface")
        library.assert_not_called()
        self.assertNotIn("fallback", json.loads(output))

    def test_invalid_generated_audio_uses_library(self):
        self.approve()
        with patch.object(bgm, "HostedAceStep") as hosted, patch.object(bgm, "LibraryMusic") as library:
            hosted.return_value.models.return_value = [bgm.SUPPORTED_MODEL]
            hosted.return_value.generate.return_value = b"invalid audio"
            hosted.return_value.last_event_id = "failed-audio-job"
            library.return_value.acquire.return_value = library_asset()
            code, output, error = self.auto()
        self.assertEqual(code, 0, error)
        result = json.loads(output)
        self.assertTrue(result["fallback"]["generationSubmitted"])
        self.assertEqual(result["fallback"]["eventId"], "failed-audio-job")
        self.assertEqual(result["provider"], "wikimedia-commons")

    def test_both_sources_fail_without_publishing_music(self):
        self.approve()
        before = self.story_path.read_bytes()
        with patch.object(bgm, "HostedAceStep") as hosted, patch.object(bgm, "LibraryMusic") as library:
            hosted.return_value.models.side_effect = bgm.HostedBgmError("quota: unavailable")
            library.return_value.acquire.side_effect = bgm.LibraryBgmError("license: rejected")
            code, output, error = self.auto()
        self.assertEqual(code, 1)
        self.assertIn("quota: unavailable", error)
        self.assertIn("license: rejected", error)
        self.assertEqual(output, "")
        self.assertEqual(self.story_path.read_bytes(), before)
        self.assertFalse((self.project / "public").exists())

    def test_auto_does_not_hide_story_change_as_provider_failure(self):
        self.approve()

        def models():
            self.story["scenes"][0]["purpose"] = "User changed the story"
            self.write_inputs()
            return [bgm.SUPPORTED_MODEL]

        with patch.object(bgm, "HostedAceStep") as hosted, patch.object(bgm, "LibraryMusic") as library:
            hosted.return_value.models.side_effect = models
            code, _, error = self.auto()
        self.assertEqual(code, 1)
        self.assertIn("Story changed", error)
        hosted.return_value.generate.assert_not_called()
        library.assert_not_called()

    def test_library_sidecar_validates_without_ai_fields(self):
        self.approve()
        asset = library_asset()
        plan = self.prepare()
        bgm.publish(plan, asset["audio"], None, "wikimedia-commons", library_provenance=asset["provenance"])
        sidecar = json.loads(plan["sidecar"].read_text())
        module = (REPO_ROOT / "skills/reel/assets/remotion-starter/scripts/validate-music.mjs").as_uri()
        script = (
            f"import {{validateMusic}} from {json.dumps(module)};"
            "import {readFileSync} from 'node:fs';"
            "const story=JSON.parse(readFileSync('src/reel/story.json','utf8'));"
            "const errors=validateMusic(story,2,()=>2);"
            "console.log(JSON.stringify(errors));process.exitCode=errors.length?1:0;"
        )
        for change in (
            {}, {"license": "CC-BY-NC-4.0"}, {"model": "fake-ai"},
            {"allowsProjectRedistribution": False}, {"creator": ""},
            {"sourceUrl": "https://untrusted.invalid/audio"},
            {"sourceFileSha1": "not-a-hash"}, {"sourceFileSha1": "a" * 40}, {"verifiedAt": ""},
        ):
            with self.subTest(change=change):
                plan["sidecar"].write_text(json.dumps({**sidecar, **change}))
                result = subprocess.run(
                    ["node", "--input-type=module", "-e", script],
                    cwd=self.project, capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 1 if change else 0, result.stdout + result.stderr)

    def test_library_license_cannot_be_faked_at_publication(self):
        asset = library_asset()
        asset["provenance"]["license"] = "CC-BY-NC-4.0"
        plan = self.prepare()
        with self.assertRaisesRegex(bgm.BgmError, "license"):
            bgm.publish(plan, asset["audio"], None, "wikimedia-commons", library_provenance=asset["provenance"])
        self.assertFalse(plan["output"].exists())

    def test_cc_by_publication_requires_visible_credit_and_license_file(self):
        self.approve()
        for name in ("MusicCredits.tsx", "Reel.tsx"):
            shutil.copyfile(
                REPO_ROOT / "skills/reel/assets/remotion-starter/src/reel" / name,
                self.project / "src/reel" / name,
            )
        asset = library_asset()
        asset["provenance"].update(
            license="CC-BY-4.0", licenseUrl="https://creativecommons.org/licenses/by/4.0/",
            attributionRequired=True,
            creditCreators="Fixture author; drums: Second contributor",
        )
        plan = self.prepare()
        bgm.publish(plan, asset["audio"], None, "wikimedia-commons", library_provenance=asset["provenance"])
        story = json.loads(self.story_path.read_text())
        sidecar = json.loads(plan["sidecar"].read_text())
        self.assertEqual(story["audio"]["music"]["attribution"], sidecar["attributionText"])
        self.assertIn("Second contributor", story["audio"]["music"]["attribution"])
        license_path = plan["output"].with_name(plan["output"].name + ".license.txt")
        self.assertIn("creativecommons.org/licenses/by/4.0/", license_path.read_text())
        module = (REPO_ROOT / "skills/reel/assets/remotion-starter/scripts/validate-music.mjs").as_uri()
        script = (
            f"import {{validateMusic}} from {json.dumps(module)};"
            "import {readFileSync} from 'node:fs';"
            "const errors=validateMusic(JSON.parse(readFileSync('src/reel/story.json')),2,()=>2);"
            "console.log(JSON.stringify(errors));process.exitCode=errors.length?1:0;"
        )
        for change in ("valid", "missing-credit", "wrong-credit", "missing-renderer", "missing-license-file"):
            current = json.loads(json.dumps(story))
            if change == "missing-credit":
                del current["audio"]["music"]["attribution"]
            elif change == "wrong-credit":
                current["audio"]["music"]["attribution"] = "Free music"
            elif change == "missing-license-file":
                license_path.unlink()
            elif change == "missing-renderer":
                (self.project / "src/reel/MusicCredits.tsx").unlink()
            self.story_path.write_text(json.dumps(current))
            result = subprocess.run(
                ["node", "--input-type=module", "-e", script],
                cwd=self.project, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0 if change == "valid" else 1, result.stdout + result.stderr)

    def test_library_license_collision_rolls_back_owned_outputs(self):
        self.approve()
        plan = self.prepare()
        before = self.story_path.read_bytes()
        license_path = plan["output"].with_name(plan["output"].name + ".license.txt")
        license_path.parent.mkdir(parents=True, exist_ok=True)
        license_path.write_text("Existing file must remain unchanged")
        asset = library_asset()
        with self.assertRaises(FileExistsError):
            bgm.publish(plan, asset["audio"], None, "wikimedia-commons", library_provenance=asset["provenance"])
        self.assertFalse(plan["output"].exists())
        self.assertFalse(plan["sidecar"].exists())
        self.assertEqual(license_path.read_text(), "Existing file must remain unchanged")
        self.assertEqual(self.story_path.read_bytes(), before)

    def test_review_is_local_and_does_not_approve(self):
        before = self.brief_path.read_bytes()
        output = io.StringIO()
        with patch.object(bgm, "HostedAceStep") as hosted, patch.object(
            bgm, "LocalAceStep"
        ) as local, patch("sys.argv", [
            str(SCRIPT), "review", "--provider", "huggingface",
            "--project", str(self.project), "--brief", str(self.brief_path),
        ]), redirect_stdout(output):
            self.assertEqual(bgm.main(), 0)
        card = json.loads(output.getvalue())
        self.assertEqual(card["direction"], self.brief["direction"])
        self.assertEqual(card["fingerprint"], bgm.approval_fingerprint(self.prepare()))
        self.assertEqual(card["status"], "awaiting-user-decision")
        self.assertEqual(self.brief_path.read_bytes(), before)
        self.assertFalse((self.project / "public").exists())
        hosted.assert_not_called()
        local.assert_not_called()

    def test_unapproved_generation_never_contacts_either_provider(self):
        for state in ("missing", "pending", "stale"):
            if state != "missing":
                self.approve()
                if state == "pending":
                    self.brief["approval"]["mode"] = "pending"
                else:
                    self.brief["prompt"] += " Changed direction."
                self.write_inputs()
            for provider in ("local", "huggingface", "auto", "library"):
                with self.subTest(state=state, provider=provider), patch.object(
                    bgm, "HostedAceStep"
                ) as hosted, patch.object(bgm, "LocalAceStep") as local, patch.object(
                    bgm, "LibraryMusic"
                ) as library, patch(
                    "sys.argv", [
                        str(SCRIPT), "generate", "--provider", provider,
                        "--project", str(self.project), "--brief", str(self.brief_path),
                    ]
                ), redirect_stderr(io.StringIO()) as error:
                    self.assertEqual(bgm.main(), 1)
                    self.assertIn("approval:", error.getvalue())
                    hosted.assert_not_called()
                    local.assert_not_called()
                    library.assert_not_called()

    def test_approval_and_explicit_delegation_bind_the_current_brief(self):
        for mode in ("approved", "delegated"):
            self.approve(mode)
            self.assertEqual(bgm.require_approval(self.prepare())["mode"], mode)
        self.brief["approval"]["decisionRef"] = ""
        self.write_inputs()
        with self.assertRaisesRegex(bgm.BgmError, "actual confirmation"):
            bgm.require_approval(self.prepare())

    def test_changed_music_or_story_invalidates_approval(self):
        for change in ("direction", "prompt", "seed", "story", "duration", "shots", "treatment"):
            with self.subTest(change=change):
                self.approve()
                if change == "direction":
                    self.brief["direction"]["emotion"] += " and tense"
                elif change == "prompt":
                    self.brief["prompt"] += " Strong percussion."
                elif change == "seed":
                    self.brief["seed"] += 1
                elif change == "story":
                    self.story["scenes"][0]["purpose"] = "Changed emotional context"
                elif change == "duration":
                    self.story["scenes"][0]["durationSeconds"] = 3
                    self.story["shots"][0]["durationSeconds"] = 3
                elif change == "shots":
                    self.story["shots"][0]["purpose"] = "Different visual beat"
                else:
                    self.story["treatment"] = "energetic"
                self.write_inputs()
                with self.assertRaisesRegex(bgm.BgmError, "changed"):
                    bgm.require_approval(self.prepare())

    def test_brief_changed_during_generation_is_not_attached(self):
        self.approve()
        plan = self.prepare()
        self.brief["direction"]["emotion"] = "Different direction"
        self.write_inputs()
        with self.assertRaisesRegex(bgm.BgmError, "Music brief changed"):
            bgm.publish(plan, wav_bytes(), bgm.SUPPORTED_MODEL)
        self.assertFalse(plan["output"].exists())

    def test_brief_changed_during_preflight_never_submits_a_job(self):
        self.approve()

        def models():
            self.brief["direction"]["emotion"] = "Reconsidered direction"
            self.write_inputs()
            return [bgm.SUPPORTED_MODEL]

        before = self.story_path.read_bytes()
        with patch.object(bgm, "HostedAceStep") as hosted, patch("sys.argv", [
            str(SCRIPT), "generate", "--provider", "huggingface",
            "--project", str(self.project), "--brief", str(self.brief_path),
        ]), redirect_stderr(io.StringIO()) as error:
            hosted.return_value.models.side_effect = models
            self.assertEqual(bgm.main(), 1)
            self.assertIn("Music brief changed", error.getvalue())
            hosted.return_value.generate.assert_not_called()
        self.assertEqual(self.story_path.read_bytes(), before)
        self.assertFalse((self.project / "public").exists())

    def test_preparation_preserves_story_and_derives_duration(self):
        before = self.story_path.read_bytes()
        result = self.prepare()
        self.assertEqual(result["duration"], 2)
        self.assertEqual(result["brief"]["seed"], 42)
        self.assertEqual(self.story_path.read_bytes(), before)
        self.assertFalse(result["output"].exists())

    def test_existing_music_and_files_are_protected(self):
        self.story["audio"]["music"] = {"src": "audio/existing.wav"}
        self.write_inputs()
        with self.assertRaisesRegex(bgm.BgmError, "protected"):
            self.prepare()
        self.story["audio"].pop("music")
        self.write_inputs()
        target = self.project / "public/audio/underscore.wav"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"existing")
        with self.assertRaisesRegex(bgm.BgmError, "already exists"):
            self.prepare()
        self.assertEqual(target.read_bytes(), b"existing")

    def test_music_requires_locked_narration(self):
        self.story["scenes"][0]["narration"] = "Approved speech."
        self.write_inputs()
        with self.assertRaisesRegex(bgm.BgmError, "Lock"):
            self.prepare()

    def test_rendered_timeline_must_match_scene_duration(self):
        self.story["shots"][0]["durationSeconds"] = 3
        self.write_inputs()
        with self.assertRaisesRegex(bgm.BgmError, "disagree"):
            self.prepare()
        self.story["shots"][0]["startSeconds"] = 1
        self.write_inputs()
        with self.assertRaisesRegex(bgm.BgmError, "contiguous"):
            self.prepare()

    def test_invalid_briefs_do_not_start_generation(self):
        for field, value in [
            ("seed", -1), ("seed", True), ("seed", 1.5),
            ("bpm", 301), ("bpm", "96"), ("instrumental", False),
            ("prompt", ""), ("rationale", None),
        ]:
            with self.subTest(field=field, value=value):
                original = self.brief[field]
                self.brief[field] = value
                self.write_inputs()
                with self.assertRaises(bgm.BgmError):
                    self.prepare()
                self.brief[field] = original

    def test_output_symlinks_cannot_escape_project(self):
        with tempfile.TemporaryDirectory() as outside:
            (self.project / "public").mkdir()
            (self.project / "public/audio").symlink_to(outside, target_is_directory=True)
            with self.assertRaisesRegex(bgm.BgmError, "inside"):
                self.prepare()
            self.assertEqual(list(Path(outside).iterdir()), [])

    def test_wav_measurement_and_rejection(self):
        self.assertEqual(bgm.wav_duration(wav_bytes(2)), 2)
        invalid_float = bytearray(wav_bytes())
        struct.pack_into("<H", invalid_float, 20, 3)
        partial_sample = bytearray(wav_bytes()[:-2])
        struct.pack_into("<I", partial_sample, 4, len(partial_sample) - 8)
        struct.pack_into("<I", partial_sample, 40, len(partial_sample) - 44)
        for audio in (b"not audio", wav_bytes(2)[:-1], wav_bytes(0), invalid_float, partial_sample):
            with self.assertRaises(bgm.BgmError):
                bgm.wav_duration(audio)

    def test_flac_metadata_measurement_and_rejection(self):
        self.assertEqual(bgm.flac_duration(flac_metadata_fixture()), 2)
        for audio in (b"bad", flac_metadata_fixture()[:42], flac_metadata_fixture(0)):
            with self.assertRaises(bgm.BgmError):
                bgm.flac_duration(audio)

    @unittest.skipUnless(shutil.which("ffmpeg"), "Existing ffmpeg is required")
    def test_native_flac_from_actual_encoder(self):
        target = self.project / "encoder.flac"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-f", "wav", "-i", "pipe:0",
             "-c:a", "flac", str(target)],
            input=wav_bytes(), capture_output=True, check=True,
        )
        self.assertEqual(bgm.flac_duration(target.read_bytes()), 2)

    def test_publish_attaches_measured_hash_backed_music(self):
        plan = self.prepare()
        result = bgm.publish(plan, wav_bytes(2), "ace-step-test-fixture")
        self.assertTrue(result["success"])
        story = json.loads(self.story_path.read_text())
        self.assertIsNone(story["audio"]["narration"])
        self.assertEqual(story["scenes"], self.story["scenes"])
        self.assertEqual(story["audio"]["music"]["endSeconds"], 2)
        metadata = json.loads(plan["sidecar"].read_text())
        self.assertEqual(metadata["outputSha256"], hashlib.sha256(wav_bytes(2)).hexdigest())
        self.assertEqual(metadata["promptSha256"], hashlib.sha256(self.brief["prompt"].encode()).hexdigest())
        self.assertNotIn(self.brief["prompt"], plan["sidecar"].read_text())
        self.assertNotIn("rationale", metadata)

    def test_failed_or_short_audio_does_not_modify_story(self):
        for audio in (b"error page", wav_bytes(1)):
            with self.subTest(audio_size=len(audio)):
                plan = self.prepare()
                before = self.story_path.read_bytes()
                with self.assertRaises(bgm.BgmError):
                    bgm.publish(plan, audio, "ace-step-test-fixture")
                self.assertEqual(self.story_path.read_bytes(), before)
                self.assertFalse(plan["output"].exists())

    def test_fractional_video_and_low_fps_mix_timing(self):
        self.story["scenes"][0]["durationSeconds"] = 2.02
        self.story["shots"][0]["durationSeconds"] = 2.02
        self.write_inputs()
        plan = self.prepare()
        self.assertEqual(plan["duration"], 2.02)
        with self.assertRaisesRegex(bgm.BgmError, "shorter"):
            bgm.publish(plan, wav_bytes(2.02), bgm.SUPPORTED_MODEL)
        bgm.publish(plan, wav_bytes(3), bgm.SUPPORTED_MODEL)
        track = json.loads(self.story_path.read_text())["audio"]["music"]
        self.assertEqual(track["endSeconds"], 2.02)
        self.story["format"]["fps"] = 1
        self.write_inputs()
        low_fps = bgm.prepare(self.project, self.brief_path, "low-fps")
        bgm.publish(low_fps, wav_bytes(3), bgm.SUPPORTED_MODEL)
        track = json.loads(self.story_path.read_text())["audio"]["music"]
        self.assertEqual(track["fadeInSeconds"], 0)
        self.assertEqual(track["duckAttackSeconds"], 1)

    @unittest.skipUnless(shutil.which("node"), "Node.js is required")
    def test_provider_artifacts_pass_the_full_starter_validator(self):
        reel_root = REPO_ROOT / "skills/reel"
        for provider in ("ace-step", "huggingface"):
            with self.subTest(provider=provider):
                project = self.project / f"full-{provider}"
                shutil.copytree(reel_root / "assets/remotion-starter", project)
                shutil.copy2(reel_root / "evals/files/production-story.json", project / "src/reel/story.json")
                shutil.copy2(reel_root / "evals/files/production-REEL.md", project / "REEL.md")
                audio_format = "flac" if provider == "huggingface" else "wav"
                plan = bgm.prepare(project, self.brief_path, "generated", audio_format)
                audio = flac_metadata_fixture(plan["duration"]) if audio_format == "flac" else wav_bytes(plan["duration"])
                bgm.publish(plan, audio, bgm.SUPPORTED_MODEL, provider)
                result = subprocess.run(
                    ["node", "scripts/validate-story.mjs"], cwd=project,
                    capture_output=True, text=True, check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                if provider == "huggingface":
                    metadata = json.loads(plan["sidecar"].read_text())
                    metadata["space"] = "unverified/space"
                    plan["sidecar"].write_text(json.dumps(metadata), encoding="utf-8")
                    invalid = subprocess.run(
                        ["node", "scripts/validate-story.mjs"], cwd=project,
                        capture_output=True, text=True, check=False,
                    )
                    self.assertNotEqual(invalid.returncode, 0)
                    self.assertIn("official Space", invalid.stderr)

    def test_concurrent_changes_and_collisions_are_protected(self):
        plan = self.prepare()
        self.story_path.write_text('{"changed":true}', encoding="utf-8")
        with self.assertRaisesRegex(bgm.BgmError, "changed"):
            bgm.publish(plan, wav_bytes(), "ace-step-test-fixture")
        self.assertFalse(plan["output"].exists())
        self.write_inputs()
        plan = self.prepare()
        plan["sidecar"].parent.mkdir(parents=True)
        plan["sidecar"].write_text("user content", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            bgm.publish(plan, wav_bytes(), "ace-step-test-fixture")
        self.assertFalse(plan["output"].exists())
        self.assertEqual(plan["sidecar"].read_text(), "user content")
        self.assertNotIn("music", json.loads(self.story_path.read_text())["audio"])

    def test_only_explicit_local_origins_and_no_redirects(self):
        for url in (
            "https://example.com", "http://127.0.0.1.evil.test",
            "http://user:secret@localhost", "http://localhost/api",
            "file:///tmp/song.wav", "http://localhost/?token=secret",
        ):
            with self.subTest(url=url), self.assertRaises(bgm.BgmError):
                bgm.LocalAceStep(url, 10)
        client = bgm.LocalAceStep("http://127.0.0.1:8001", 10)
        with patch.object(client.opener, "open") as request:
            for url in ("http://evil.test/song.wav", "//evil.test/song.wav"):
                with self.assertRaises(bgm.BgmError):
                    client.request(url, audio=True)
            request.assert_not_called()
        with self.assertRaisesRegex(bgm.BgmError, "redirect"):
            bgm.NoRedirect().redirect_request(None, None, 302, "", {}, "http://evil.test")

    def test_real_http_protocol_and_cli_attach(self):
        self.approve()
        stdout, stderr = io.StringIO(), io.StringIO()
        with local_provider() as (url, calls), patch.dict(
            "os.environ", {"ACE_STEP_API_KEY": "fixture-test-key"}
        ), patch.object(bgm.time, "sleep"), patch(
            "sys.argv", [
                str(SCRIPT), "generate", "--project", str(self.project),
                "--brief", str(self.brief_path), "--model", bgm.SUPPORTED_MODEL,
                "--base-url", url, "--timeout", "10",
            ]
        ), redirect_stdout(stdout), redirect_stderr(stderr):
            code = bgm.main()
        self.assertEqual(code, 0, stderr.getvalue())
        self.assertTrue(json.loads(stdout.getvalue())["success"])
        self.assertNotIn("fixture-test-key", stdout.getvalue() + stderr.getvalue())
        self.assertEqual([call[0] for call in calls], [
            "/v1/models", "/release_task", "/query_result",
            "/query_result", "/v1/audio?path=generated.wav",
        ])
        self.assertTrue(all(call[2] == "Bearer fixture-test-key" for call in calls))
        payload = calls[1][1]
        self.assertEqual(payload["audio_duration"], 10)
        self.assertEqual(payload["lyrics"], "[Instrumental]")
        self.assertEqual(payload["batch_size"], 1)
        self.assertEqual(payload["seed"], 42)
        self.assertEqual(payload["key_scale"], "C Major")
        self.assertFalse(payload["thinking"])
        self.assertFalse(payload["use_format"])
        self.assertNotIn("rationale", payload)
        self.assertNotIn("instrumental", payload)
        self.assertNotIn("approval", payload)
        self.assertNotIn("direction", payload)
        self.assertEqual(json.loads(self.story_path.read_text())["audio"]["music"]["src"], "audio/bgm.wav")

    def test_unloaded_or_unknown_models_are_not_initialized(self):
        client = bgm.LocalAceStep("http://127.0.0.1:8001", 10)
        for data in (model_inventory(False), {"models": [{"name": bgm.SUPPORTED_MODEL}]}):
            with patch.object(client, "data", return_value=data) as request:
                with self.assertRaisesRegex(bgm.BgmError, "known readiness"):
                    client.models()
                request.assert_called_once_with("/v1/models")

    def test_hosted_cli_generates_without_local_setup(self):
        self.approve("delegated")
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(bgm, "HostedAceStep") as hosted, patch.object(
            bgm, "LocalAceStep"
        ) as local, patch(
            "sys.argv", [
                str(SCRIPT), "generate", "--provider", "huggingface",
                "--project", str(self.project), "--brief", str(self.brief_path),
            ]
        ), redirect_stdout(stdout), redirect_stderr(stderr):
            hosted.return_value.models.return_value = [bgm.SUPPORTED_MODEL]
            hosted.return_value.generate.return_value = flac_metadata_fixture()
            code = bgm.main()
        self.assertEqual(code, 0, stderr.getvalue())
        local.assert_not_called()
        hosted.return_value.generate.assert_called_once_with(self.brief, 2, bgm.SUPPORTED_MODEL)
        sidecar = json.loads((self.project / "public/audio/bgm.flac.json").read_text())
        self.assertEqual(sidecar["provider"], "huggingface")
        self.assertEqual(sidecar["space"], "ACE-Step/Ace-Step-v1.5")
        self.assertEqual(sidecar["directionApproval"]["mode"], "delegated")
        self.assertNotIn("decisionRef", sidecar["directionApproval"])

    def test_hosted_failure_does_not_fallback_or_change_story(self):
        self.approve()
        before = self.story_path.read_bytes()
        stderr = io.StringIO()
        with patch.object(bgm, "HostedAceStep") as hosted, patch.object(
            bgm, "LocalAceStep"
        ) as local, patch(
            "sys.argv", [
                str(SCRIPT), "generate", "--provider", "huggingface",
                "--project", str(self.project), "--brief", str(self.brief_path),
            ]
        ), redirect_stderr(stderr):
            hosted.return_value.models.return_value = [bgm.SUPPORTED_MODEL]
            hosted.return_value.generate.side_effect = bgm.HostedBgmError("Free GPU quota exhausted")
            hosted.return_value.last_event_id = "fixture-event"
            code = bgm.main()
        self.assertEqual(code, 1)
        self.assertIn("quota", stderr.getvalue())
        self.assertEqual(json.loads(stderr.getvalue())["eventId"], "fixture-event")
        self.assertEqual(self.story_path.read_bytes(), before)
        self.assertFalse((self.project / "public/audio/bgm.flac").exists())
        local.assert_not_called()

    def test_hosted_limits_fail_before_contacting_service(self):
        self.story["scenes"][0]["durationSeconds"] = 121
        self.story["shots"][0]["durationSeconds"] = 121
        self.write_inputs()
        self.approve()
        stderr = io.StringIO()
        with patch.object(bgm, "HostedAceStep") as hosted, patch(
            "sys.argv", [
                str(SCRIPT), "generate", "--provider", "huggingface",
                "--project", str(self.project), "--brief", str(self.brief_path),
            ]
        ), redirect_stderr(stderr):
            code = bgm.main()
        self.assertEqual(code, 1)
        self.assertIn("120 seconds", stderr.getvalue())
        hosted.assert_not_called()

    def test_failure_malformed_results_and_remote_audio_are_rejected(self):
        client = bgm.LocalAceStep("http://127.0.0.1:8001", 10)
        for row in (
            {"task_id": "job", "status": 2},
            {"task_id": "wrong-job", "status": 1, "result": "[]"},
            {"task_id": "job", "status": 1, "result": "bad-json"},
            {"task_id": "job", "status": 1, "result": []},
            {"task_id": "job", "status": 1, "result": json.dumps([{"status": 1, "file": "/tmp/file.wav"}])},
            {"task_id": "job", "status": 1, "result": json.dumps([{"status": 1, "file": "https://example.com/v1/audio"}])},
        ):
            with self.subTest(row=row), patch.object(
                client, "data", side_effect=[{"task_id": "job"}, [row]]
            ), patch.object(client.opener, "open") as network:
                with self.assertRaises(bgm.BgmError):
                    client.generate(self.brief, 2, bgm.SUPPORTED_MODEL)
                network.assert_not_called()

    def test_timeout_does_not_resubmit(self):
        client = bgm.LocalAceStep("http://127.0.0.1:8001", 10)
        client.deadline = 0
        with patch.object(client, "data", return_value={"task_id": "job"}) as request:
            with self.assertRaisesRegex(bgm.BgmError, "timed out"):
                client.generate(self.brief, 2, bgm.SUPPORTED_MODEL)
            self.assertEqual(request.call_count, 1)
            self.assertEqual(request.call_args.args[0], "/release_task")

    def test_bad_envelopes_and_oversized_responses_fail(self):
        client = bgm.LocalAceStep("http://127.0.0.1:8001", 10)
        for response in (None, [], {"code": 500, "data": {}}, {"code": 200, "error": "private", "data": {}}):
            with patch.object(client, "request", return_value=response):
                with self.assertRaises(bgm.BgmError):
                    client.models()
        with local_provider() as (url, _), patch.object(bgm, "MAX_JSON_BYTES", 10):
            with self.assertRaisesRegex(bgm.BgmError, "size limit"):
                bgm.LocalAceStep(url, 10).models()


if __name__ == "__main__":
    unittest.main()
