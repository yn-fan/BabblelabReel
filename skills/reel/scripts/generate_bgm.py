#!/usr/bin/env python3
"""Produce Reel BGM with hosted AI, automatic licensed music backup, or explicit sources."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import hashlib
from http.client import HTTPException
import json
import math
import os
from pathlib import Path
import re
import struct
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from hosted_bgm import HostedAceStep, HostedBgmError
from library_bgm import LibraryMusic, LibraryBgmError, LICENSES
from incompetech_bgm import IncompetechMusic
from mp3_audio import Mp3Error, mp3_duration


MAX_AUDIO_BYTES = 300 * 1024 * 1024
MAX_JSON_BYTES = 2 * 1024 * 1024
SUPPORTED_MODEL = "acestep-v15-turbo"


class BgmError(ValueError):
    """An actionable failure without provider payloads or credentials."""


def number(value: object, label: str, minimum: float, maximum: float) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not minimum <= value <= maximum
    ):
        raise BgmError(f"{label} must be between {minimum} and {maximum}")
    return float(value)


def wav_duration(audio: bytes) -> float:
    """Measure uncompressed PCM/float WAV without codec dependencies."""
    if len(audio) < 44 or audio[:4] != b"RIFF" or audio[8:12] != b"WAVE":
        raise BgmError("Provider output is not a RIFF/WAVE file")
    if struct.unpack_from("<I", audio, 4)[0] + 8 != len(audio):
        raise BgmError("Provider WAV has an invalid RIFF size")
    offset = 12
    byte_rate = None
    data_size = None
    alignment = None
    while offset + 8 <= len(audio):
        kind, size = struct.unpack_from("<4sI", audio, offset)
        start = offset + 8
        if start + size > len(audio):
            raise BgmError("Provider WAV contains a truncated chunk")
        if kind == b"fmt ":
            if size < 16 or byte_rate is not None:
                raise BgmError("Provider WAV has an invalid format chunk")
            codec, channels, rate, byte_rate, alignment, bits = struct.unpack_from(
                "<HHIIHH", audio, start
            )
            if (
                codec not in (1, 3)
                or channels not in (1, 2)
                or not 8000 <= rate <= 192000
                or bits not in ((16, 24, 32) if codec == 1 else (32,))
                or alignment != channels * bits // 8
                or byte_rate != rate * alignment
            ):
                raise BgmError("Provider WAV must be mono/stereo uncompressed PCM or float")
        elif kind == b"data":
            if data_size is not None:
                raise BgmError("Provider WAV has multiple audio chunks")
            data_size = size
        offset = start + size + size % 2
    if (
        offset != len(audio)
        or not byte_rate
        or not data_size
        or not alignment
        or data_size % alignment
    ):
        raise BgmError("Provider WAV is missing complete nonempty audio")
    return data_size / byte_rate


def flac_duration(audio: bytes) -> float:
    """Measure native lossless FLAC from its mandatory STREAMINFO block."""
    if len(audio) < 44 or audio[:4] != b"fLaC":
        raise BgmError("Provider output is not a native FLAC file")
    offset = 4
    duration = None
    while offset + 4 <= len(audio):
        header = audio[offset]
        kind = header & 0x7F
        size = int.from_bytes(audio[offset + 1:offset + 4], "big")
        start = offset + 4
        if start + size > len(audio) or kind == 127:
            raise BgmError("Provider FLAC has invalid or truncated metadata")
        if offset == 4 and kind != 0:
            raise BgmError("Provider FLAC must start with STREAMINFO")
        if kind == 0:
            if size != 34 or duration is not None:
                raise BgmError("Provider FLAC has invalid STREAMINFO")
            packed = int.from_bytes(audio[start + 10:start + 18], "big")
            rate = packed >> 44
            channels = ((packed >> 41) & 7) + 1
            bits = ((packed >> 36) & 31) + 1
            samples = packed & ((1 << 36) - 1)
            if not 8000 <= rate <= 192000 or channels not in (1, 2) or bits not in (16, 24, 32) or samples == 0:
                raise BgmError("Provider FLAC must declare a nonempty mono/stereo PCM stream")
            duration = samples / rate
        offset = start + size
        if header & 0x80:
            if duration is None or offset + 2 > len(audio) or audio[offset] != 0xFF or audio[offset + 1] & 0xFE != 0xF8:
                raise BgmError("Provider FLAC has no audio frame after metadata")
            return duration
    raise BgmError("Provider FLAC has incomplete metadata")


def read_object(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise BgmError(f"Cannot read JSON object: {path.name}") from error
    if not isinstance(value, dict):
        raise BgmError(f"Expected JSON object: {path.name}")
    return value


def prepare(project: Path, brief_path: Path, name: str, audio_format: str = "wav") -> dict:
    if audio_format not in ("wav", "flac", "mp3"):
        raise BgmError("Unsupported BGM audio format")
    project = project.expanduser().resolve(strict=True)
    story_path = project / "src/reel/story.json"
    if not story_path.resolve().is_relative_to(project):
        raise BgmError("Story must remain inside the selected project")
    story_bytes = story_path.read_bytes()
    story = read_object(story_path)
    brief = read_object(brief_path)
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", name):
        raise BgmError("name must be a lowercase filename slug of at most 64 characters")
    if not isinstance(story.get("audio"), dict):
        raise BgmError("Reel story must contain an audio object")
    if story["audio"].get("music") is not None:
        raise BgmError("Existing audio.music is protected; explicitly remove it before replacement")
    scenes = story.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise BgmError("Story must contain scenes")
    if any(not isinstance(scene, dict) for scene in scenes):
        raise BgmError("Each scene must be an object")
    if any(scene.get("narration") for scene in scenes) and story.get("scriptLocked") is not True:
        raise BgmError("Lock the narration script before generating music")
    duration = sum(
        number(scene.get("durationSeconds"), "scene duration", 0.01, 600)
        for scene in scenes
    )
    number(duration, "composition duration", 1, 600)
    shots = story.get("shots")
    if not isinstance(shots, list) or not shots:
        raise BgmError("Story must contain the rendered shot timeline")
    end = 0.0
    for shot in shots:
        if not isinstance(shot, dict):
            raise BgmError("Each shot must be an object")
        start = number(shot.get("startSeconds"), "shot start", 0, 600)
        length = number(shot.get("durationSeconds"), "shot duration", 0.01, 600)
        if abs(start - end) > 0.001:
            raise BgmError("Shot timeline must be contiguous before music generation")
        end = start + length
    if abs(end - duration) > 0.001:
        raise BgmError("Scene and rendered shot durations disagree")
    if not isinstance(story.get("format"), dict):
        raise BgmError("Story must contain a format object")
    fps = number(story["format"].get("fps"), "fps", 1, 120)
    rendered_duration = math.floor(end * fps + 0.5) / fps
    for field in ("prompt", "rationale"):
        if not isinstance(brief.get(field), str) or not brief[field].strip():
            raise BgmError(f"Music brief requires nonempty {field}")
        if len(brief[field]) > 4000:
            raise BgmError(f"Music brief {field} must not exceed 4000 characters")
    direction = brief.get("direction")
    if not isinstance(direction, dict):
        raise BgmError("Music brief requires a human-readable direction card")
    for field in ("emotion", "arc", "instruments", "pace", "narration"):
        if not isinstance(direction.get(field), str) or not direction[field].strip() or len(direction[field]) > 1000:
            raise BgmError(f"Music direction requires nonempty {field} (at most 1000 characters)")
    if brief.get("instrumental") is not True:
        raise BgmError("Music brief must explicitly set instrumental: true")
    seed = brief.get("seed")
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 2**31 - 1:
        raise BgmError("Music brief seed must be an integer from 0 to 2147483647")
    bpm = brief.get("bpm")
    number(bpm, "bpm", 30, 300)
    if not isinstance(bpm, int):
        raise BgmError("bpm must be an integer")
    if not isinstance(brief.get("keyScale"), str) or not re.fullmatch(
        r"[A-G](?:#|b)? (?:Major|Minor)", brief["keyScale"]
    ):
        raise BgmError("keyScale must name a key, such as C Major or A Minor")
    if brief.get("timeSignature") not in ("2", "3", "4", "6"):
        raise BgmError("timeSignature must be 2, 3, 4, or 6")
    audio_dir = project / "public/audio"
    public_dir = project / "public"
    if (
        not public_dir.resolve().is_relative_to(project)
        or not audio_dir.resolve().is_relative_to(public_dir.resolve())
        or audio_dir.resolve() != audio_dir
    ):
        raise BgmError("Audio output must remain inside the selected project's public directory")
    output = audio_dir / f"{name}.{audio_format}"
    sidecar = audio_dir / f"{name}.{audio_format}.json"
    license_file = output.with_name(output.name + ".license.txt")
    if any(path.exists() or path.is_symlink() for path in (output, sidecar, license_file)):
        raise BgmError("BGM output already exists; choose a new name")
    return {
        "project": project,
        "storyPath": story_path,
        "storyBytes": story_bytes,
        "story": story,
        "brief": brief,
        "briefPath": brief_path.expanduser().resolve(),
        "duration": duration,
        "renderedDuration": rendered_duration,
        "fps": fps,
        "audioFormat": audio_format,
        "output": output,
        "sidecar": sidecar,
    }


def approval_fingerprint(plan: dict) -> str:
    context = {
        "brief": {key: value for key, value in plan["brief"].items() if key != "approval"},
        "durationSeconds": plan["duration"],
        "scenes": plan["story"]["scenes"],
        "shots": plan["story"]["shots"],
        "treatment": plan["story"].get("treatment"),
    }
    encoded = json.dumps(context, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def require_approval(plan: dict) -> dict:
    approval = plan["brief"].get("approval")
    if not isinstance(approval, dict) or approval.get("mode") not in ("approved", "delegated"):
        raise BgmError("approval: confirm the music direction first, or record explicit user delegation")
    decision_ref = approval.get("decisionRef")
    if not isinstance(decision_ref, str) or not decision_ref.strip() or len(decision_ref) > 500:
        raise BgmError("approval: a reference to the user's actual confirmation or delegation is required")
    if approval.get("fingerprint") != approval_fingerprint(plan):
        raise BgmError("approval: music direction or story changed; obtain confirmation for the current brief")
    return approval


def require_current_inputs(plan: dict) -> None:
    if plan["storyPath"].read_bytes() != plan["storyBytes"]:
        raise BgmError("Story changed after preparation; nothing was attached")
    if read_object(plan["briefPath"]) != plan["brief"]:
        raise BgmError("Music brief changed after preparation; nothing was attached")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise BgmError("Local music API redirects are not allowed")


class LocalAceStep:
    def __init__(self, base_url: str, timeout: float):
        parsed = urlsplit(base_url)
        if (
            parsed.scheme != "http"
            or parsed.hostname not in ("127.0.0.1", "localhost", "::1")
            or parsed.username
            or parsed.password
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
        ):
            raise BgmError("Use a local ACE-Step HTTP origin, such as http://127.0.0.1:8001")
        self.base_url = base_url.rstrip("/")
        self.deadline = time.monotonic() + number(timeout, "timeout", 1, 7200)
        self.opener = build_opener(ProxyHandler({}), NoRedirect())
        self.api_key = os.environ.get("ACE_STEP_API_KEY")

    def request(self, path: str, payload: dict | None = None, audio: bool = False):
        url = urljoin(self.base_url + "/", path)
        origin = urlsplit(self.base_url)
        parsed = urlsplit(url)
        if (
            (parsed.scheme, parsed.netloc) != (origin.scheme, origin.netloc)
            or parsed.username
            or parsed.password
            or parsed.fragment
        ):
            raise BgmError("Provider returned an audio URL outside the configured local origin")
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise BgmError("ACE-Step operation timed out; inspect the server before retrying")
        headers = {"Accept": "audio/wav" if audio else "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        data = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(payload).encode("utf-8")
        maximum = MAX_AUDIO_BYTES if audio else MAX_JSON_BYTES
        try:
            with self.opener.open(
                Request(url, data=data, headers=headers), timeout=min(remaining, 30)
            ) as response:
                chunks = []
                size = 0
                while size <= maximum:
                    if time.monotonic() >= self.deadline:
                        raise BgmError("ACE-Step download timed out; nothing was attached")
                    chunk = response.read(min(65536, maximum + 1 - size))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    size += len(chunk)
                result = b"".join(chunks)
        except HTTPError as error:
            raise BgmError(f"ACE-Step HTTP {error.code}; check server configuration and authentication") from error
        except (URLError, TimeoutError, OSError, HTTPException) as error:
            raise BgmError("Local ACE-Step is unavailable or timed out; no automatic installation or provider fallback") from error
        if len(result) > maximum:
            raise BgmError("ACE-Step response exceeds the size limit")
        if audio:
            return result
        try:
            return json.loads(result)
        except (ValueError, UnicodeError) as error:
            raise BgmError("ACE-Step returned invalid JSON") from error

    def data(self, path: str, payload: dict | None = None):
        response = self.request(path, payload)
        if (
            not isinstance(response, dict)
            or response.get("code") != 200
            or response.get("error")
            or "data" not in response
        ):
            raise BgmError("ACE-Step returned an unsuccessful or unsupported response envelope")
        return response["data"]

    def models(self) -> list[str]:
        data = self.data("/v1/models")
        if not isinstance(data, dict) or not isinstance(data.get("models"), list):
            raise BgmError("ACE-Step model inventory is invalid")
        models = [
            item["name"] for item in data["models"]
            if isinstance(item, dict)
            and item.get("name") == SUPPORTED_MODEL
            and item.get("is_loaded") is True
            and isinstance(item.get("supported_task_types"), list)
            and "text2music" in item["supported_task_types"]
        ]
        if not models:
            raise BgmError(
                "No loaded acestep-v15-turbo text2music model with known readiness; "
                "configure the local server separately (no automatic initialization or download)"
            )
        return models

    def generate(self, brief: dict, duration: float, model: str) -> bytes:
        if model != SUPPORTED_MODEL:
            raise BgmError("This adapter supports only the verified acestep-v15-turbo model")
        payload = {
            "task_type": "text2music",
            "model": model,
            "prompt": brief["prompt"],
            "lyrics": "[Instrumental]",
            "audio_duration": max(10, math.ceil(duration)),
            "audio_format": "wav",
            "batch_size": 1,
            "inference_steps": 8,
            "use_random_seed": False,
            "seed": brief["seed"],
            "thinking": False,
            "sample_mode": False,
            "use_format": False,
            "use_cot_caption": False,
            "use_cot_language": False,
            "bpm": brief["bpm"],
            "key_scale": brief["keyScale"],
            "time_signature": brief["timeSignature"],
        }
        submitted = self.data("/release_task", payload)
        if not isinstance(submitted, dict) or not isinstance(submitted.get("task_id"), str):
            raise BgmError("ACE-Step did not return a task ID; inspect the server before retrying")
        task_id = submitted["task_id"]
        if not task_id:
            raise BgmError("ACE-Step returned an empty task ID")
        while time.monotonic() < self.deadline:
            rows = self.data("/query_result", {"task_id_list": [task_id]})
            if not isinstance(rows, list):
                raise BgmError("ACE-Step poll response must contain a task array")
            matches = [row for row in rows if isinstance(row, dict) and row.get("task_id") == task_id]
            if len(matches) != 1:
                raise BgmError("ACE-Step poll response did not match the submitted task")
            task = matches[0]
            status = task.get("status")
            if type(status) is not int or status not in (0, 1, 2):
                raise BgmError("ACE-Step returned an unsupported task status")
            if status == 2:
                raise BgmError("ACE-Step music generation failed; inspect the local server (no automatic resubmission)")
            if status == 1:
                if not isinstance(task.get("result"), str):
                    raise BgmError("ACE-Step task result must be a JSON-encoded string")
                try:
                    results = json.loads(task["result"])
                except ValueError as error:
                    raise BgmError("ACE-Step task result contains invalid JSON") from error
                if (
                    not isinstance(results, list)
                    or len(results) != 1
                    or not isinstance(results[0], dict)
                    or results[0].get("status") != 1
                    or not isinstance(results[0].get("file"), str)
                ):
                    raise BgmError("ACE-Step must return one successful audio result")
                audio_url = results[0]["file"]
                if urlsplit(audio_url).path != "/v1/audio":
                    raise BgmError("ACE-Step returned an unsupported audio download path")
                return self.request(audio_url, audio=True)
            time.sleep(min(2, max(0, self.deadline - time.monotonic())))
        raise BgmError("ACE-Step generation timed out; inspect the existing job before retrying")


def validate_library_provenance(provenance: dict) -> None:
    required = {
        "kind": "licensed-library-music",
        "allowsProjectRedistribution": True,
    }
    if not isinstance(provenance, dict):
        raise BgmError("Library provenance must be an object")
    provider = provenance.get("provider")
    if provider not in ("wikimedia-commons", "incompetech"):
        raise BgmError("Unsupported library provenance provider")
    policy = LICENSES.get(provenance.get("license")) if isinstance(provenance.get("license"), str) else None
    if policy is None:
        raise BgmError("Library provenance requires an allowed CC0/CC BY license")
    required.update(licenseUrl=policy[0], attributionRequired=policy[1])
    for key, expected in required.items():
        if type(provenance.get(key)) is not type(expected) or provenance[key] != expected:
            raise BgmError(f"Library provenance requires {key}: {expected}")
    for key in ("title", "creator", "verifiedAt", "selectionRationale"):
        if not isinstance(provenance.get(key), str) or not provenance[key].strip():
            raise BgmError(f"Library provenance requires {key}")
    if "creditCreators" in provenance and (
        not isinstance(provenance["creditCreators"], str)
        or provenance["creator"] not in provenance["creditCreators"]
    ):
        raise BgmError("Library credit must retain the source creator and credited contributors")
    try:
        verified = datetime.fromisoformat(provenance["verifiedAt"].replace("Z", "+00:00"))
        if verified.utcoffset() != timedelta(0):
            raise ValueError
    except ValueError as error:
        raise BgmError("Library provenance requires a UTC verification timestamp") from error
    if provider == "wikimedia-commons":
        revision = provenance.get("sourceRevisionId")
        if type(revision) is not int or revision <= 0:
            raise BgmError("Library provenance requires a source revision")
    else:
        if "sourceRevisionId" in provenance:
            raise BgmError("Incompetech uses catalog evidence, not a Commons source revision")
        if provenance["license"] != "CC-BY-4.0" or provenance["creator"] != "Kevin MacLeod":
            raise BgmError("Incompetech requires its original composer and CC BY 4.0 license")
        if provenance.get("creditCreators") != "Kevin MacLeod (incompetech.com)":
            raise BgmError("Incompetech requires its composer and site credit")
        for key in ("sourceCatalogSha256", "sourceLicenseSha256", "sourceSha256"):
            if not isinstance(provenance.get(key), str) or not re.fullmatch(r"[0-9a-f]{64}", provenance[key]):
                raise BgmError(f"Incompetech requires {key}")
    if not isinstance(provenance.get("sourceFileSha1"), str) or not re.fullmatch(
        r"[0-9a-f]{40}", provenance["sourceFileSha1"]
    ):
        raise BgmError("Library provenance requires the verified source SHA-1")
    urls = (
        ("sourceUrl", "commons.wikimedia.org", "/wiki/File:"),
        ("sourceDownloadUrl", "upload.wikimedia.org", "/wikipedia/commons/"),
    ) if provider == "wikimedia-commons" else (
        ("sourceUrl", "incompetech.com", "/music/royalty-free/index.html"),
        ("sourceDownloadUrl", "incompetech.com", "/music/royalty-free/mp3-royaltyfree/"),
    )
    for key, host, prefix in urls:
        value = provenance.get(key)
        parsed = urlsplit(value) if isinstance(value, str) else None
        if (
            parsed is None or parsed.scheme != "https" or parsed.netloc != host
            or not parsed.path.startswith(prefix) or parsed.fragment
            or (parsed.query and not (provider == "incompetech" and key == "sourceUrl"))
            or "\\" in unquote(parsed.path)
            or any(part in (".", "..") for part in unquote(parsed.path).split("/"))
            or any(ord(c) < 32 for c in unquote(value))
        ):
            raise BgmError(f"Library provenance requires a trusted {key}")
        if provider == "incompetech":
            if key == "sourceUrl":
                track_id = provenance.get("trackId")
                if (
                    not isinstance(track_id, str) or not re.fullmatch(r"USUAN[0-9]{7}", track_id)
                    or parsed.path != prefix or parsed.query != "isrc=" + track_id
                ):
                    raise BgmError("Incompetech requires the exact recording's source URL")
            elif not re.fullmatch(r"[^/]+\.mp3", unquote(parsed.path[len(prefix):])):
                raise BgmError("Incompetech requires a direct MP3 filename")
    if any(key in provenance for key in ("model", "seed", "promptSha256", "generation")):
        raise BgmError("Library music must not contain AI-generation provenance")


def measure_audio(audio: bytes, audio_format: str) -> float:
    if audio_format == "mp3":
        try:
            return mp3_duration(audio)
        except Mp3Error as error:
            raise BgmError(str(error)) from error
    return flac_duration(audio) if audio_format == "flac" else wav_duration(audio)


def publish(
    plan: dict, audio: bytes, model: str | None, provider: str = "ace-step",
    *, library_provenance: dict | None = None, fallback: dict | None = None,
) -> dict:
    is_library = provider in ("wikimedia-commons", "incompetech")
    if provider not in ("ace-step", "huggingface", "wikimedia-commons", "incompetech"):
        raise BgmError("Unsupported BGM provenance provider")
    if is_library:
        validate_library_provenance(library_provenance)
        if library_provenance["provider"] != provider:
            raise BgmError("Library source and publication provider must agree")
        if hashlib.sha1(audio).hexdigest() != library_provenance["sourceFileSha1"]:
            raise BgmError("Library audio must match its verified original source SHA-1")
        if provider == "incompetech" and (
            plan["audioFormat"] != "mp3"
            or hashlib.sha256(audio).hexdigest() != library_provenance["sourceSha256"]
        ):
            raise BgmError("Incompetech audio must match its acquired MP3 and source SHA-256")
    elif library_provenance is not None:
        raise BgmError("AI-generated music cannot use library provenance")
    elif plan["audioFormat"] == "mp3":
        raise BgmError("MP3 is supported only for licensed library recordings")
    if provider == "huggingface" and model != SUPPORTED_MODEL:
        raise BgmError("Hosted BGM requires the standard turbo model")
    measured = measure_audio(audio, plan["audioFormat"])
    if measured + 1e-9 < max(plan["duration"], plan["renderedDuration"]):
        raise BgmError("Generated audio is shorter than the video; adjust the brief and regenerate")
    story_path = plan["storyPath"]
    require_current_inputs(plan)
    duration = plan["duration"]
    frame_seconds = 1 / plan["fps"]
    fade_in = min(1, duration / 4)
    fade_out = min(2, duration / 4)
    track = {
        "src": f"audio/{plan['output'].name}",
        "durationSeconds": measured,
        "provenanceRef": f"audio/{plan['sidecar'].name}",
        "startSeconds": 0,
        "endSeconds": duration,
        "sourceStartSeconds": 0,
        "volume": 0.18,
        "duckVolume": 0.06,
        "fadeInSeconds": fade_in if fade_in >= frame_seconds else 0,
        "fadeOutSeconds": fade_out if fade_out >= frame_seconds else 0,
        "duckAttackSeconds": max(0.2, frame_seconds),
        "duckReleaseSeconds": max(0.4, frame_seconds),
    }
    provenance = {
        "schemaVersion": 1,
        "success": True,
        "kind": "ai-generated-music",
        "provider": provider,
        "model": model,
        "promptSha256": hashlib.sha256(plan["brief"]["prompt"].encode("utf-8")).hexdigest(),
        "outputSha256": hashlib.sha256(audio).hexdigest(),
        "durationSeconds": measured,
        "audioFormat": plan["audioFormat"],
        "instrumental": True,
        "seed": plan["brief"]["seed"],
        "generation": {
            "requestedDurationSeconds": max(10, math.ceil(plan["duration"])),
            "bpm": plan["brief"]["bpm"],
            "keyScale": plan["brief"]["keyScale"],
            "timeSignature": plan["brief"]["timeSignature"],
            "inferenceSteps": 8,
        },
        "licenseNote": "ACE-Step: verify the selected checkpoint license and intended output use; model licensing is not output clearance.",
    }
    if provider == "huggingface":
        provenance["space"] = "ACE-Step/Ace-Step-v1.5"
    if is_library:
        provenance = {
            **library_provenance,
            "schemaVersion": 1, "success": True, "instrumental": True,
            "outputSha256": hashlib.sha256(audio).hexdigest(),
            "durationSeconds": measured, "audioFormat": plan["audioFormat"],
        }
        attribution = (
            f"{provenance['title']} - {provenance.get('creditCreators', provenance['creator'])}\n"
            f"{provenance['license']}; {provenance['licenseUrl']}\n"
            f"{provenance['sourceUrl']}\n"
            "Edited for this video: excerpt, fades, and volume mix."
        )
        provenance["attributionText"] = attribution
        if provenance["attributionRequired"]:
            track["attribution"] = attribution
    if fallback is not None:
        provenance["fallback"] = fallback
    if "approval" in plan["brief"]:
        approval = require_approval(plan)
        provenance["directionApproval"] = {
            "mode": approval["mode"],
            "fingerprint": approval["fingerprint"],
        }
    story = {**plan["story"], "audio": {**plan["story"]["audio"], "music": track}}
    created = []
    temporary_story = None
    public_dir = plan["project"] / "public"
    if (
        not public_dir.resolve().is_relative_to(plan["project"])
        or not plan["output"].parent.resolve().is_relative_to(public_dir.resolve())
        or plan["output"].parent.resolve() != plan["output"].parent
    ):
        raise BgmError("Audio directory changed during generation; nothing was attached")
    plan["output"].parent.mkdir(parents=True, exist_ok=True)
    try:
        outputs = [
            (plan["output"], audio),
            (plan["sidecar"], (json.dumps(provenance, indent=2) + "\n").encode("utf-8")),
        ]
        if is_library:
            source_evidence = (
                f"Source revision: {provenance['sourceRevisionId']}"
                if provider == "wikimedia-commons"
                else f"Source catalog SHA-256: {provenance['sourceCatalogSha256']}"
            )
            outputs.append((
                plan["output"].with_name(plan["output"].name + ".license.txt"),
                (provenance["attributionText"] + "\n\n"
                 "Original recording licensed by its creator under the linked license.\n"
                 f"{source_evidence}\n"
                 f"Source verified: {provenance['verifiedAt']}\n").encode("utf-8"),
            ))
        for path, content in outputs:
            with path.open("xb") as output:
                created.append(path)
                output.write(content)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=story_path.parent, delete=False, suffix=".tmp"
        ) as output:
            temporary_story = Path(output.name)
            json.dump(story, output, indent=2)
            output.write("\n")
        require_current_inputs(plan)
        temporary_story.replace(story_path)
        temporary_story = None
    except (OSError, ValueError):
        for path in created:
            path.unlink()
        raise
    finally:
        if temporary_story is not None:
            temporary_story.unlink()
    result = {
        "success": True,
        "provider": provider,
        "kind": provenance["kind"],
        "output": str(plan["output"]),
        "provenance": str(plan["sidecar"]),
        "durationSeconds": measured,
        "storyUpdated": True,
    }
    if model is not None:
        result["model"] = model
    if is_library:
        result.update(
            title=provenance["title"], license=provenance["license"],
            sourceUrl=provenance["sourceUrl"],
            attributionRequired=provenance["attributionRequired"],
            licenseFile=str(plan["output"].with_name(plan["output"].name + ".license.txt")),
        )
        if provenance.get("libraryFailures"):
            result["libraryFailures"] = provenance["libraryFailures"]
    if fallback is not None:
        result["fallback"] = fallback
    return result


def generate_with_library(args, plan: dict) -> dict:
    if args.base_url:
        raise BgmError("--base-url is only supported by the local provider")
    if args.model != SUPPORTED_MODEL:
        raise BgmError("Automatic BGM uses only the standard turbo model")
    LibraryMusic.validate_brief(plan["brief"])
    fallback = None
    if args.provider == "auto":
        client = None
        blocker = args.known_ai_blocker
        if blocker or plan["duration"] > 120:
            fallback = {
                "from": "huggingface",
                "reason": f"known-{blocker}" if blocker else "hosted-duration-limit",
                "providerContacted": False, "generationSubmitted": False,
            }
        else:
            try:
                client = HostedAceStep(timeout=args.timeout)
                if args.model not in client.models():
                    raise HostedBgmError("model: standard turbo is unavailable")
                require_current_inputs(plan)
                audio = client.generate(plan["brief"], plan["duration"], args.model)
                try:
                    measured = flac_duration(audio)
                    if measured + 1e-9 < max(plan["duration"], plan["renderedDuration"]):
                        raise BgmError("Source does not cover the video")
                except BgmError as error:
                    raise HostedBgmError("format: generated audio is invalid or too short") from error
            except HostedBgmError as error:
                fallback = {
                    "from": "huggingface", "reason": str(error),
                    "providerContacted": True, "generationSubmitted": False,
                }
                event_id = getattr(client, "last_event_id", None)
                if isinstance(event_id, str) and re.fullmatch(r"[a-zA-Z0-9_-]{1,128}", event_id):
                    fallback.update(eventId=event_id, generationSubmitted=True)
            else:
                return publish(plan, audio, args.model, "huggingface")
        print(json.dumps({"status": "using-library-fallback", **fallback}), file=sys.stderr)
    require_current_inputs(plan)
    try:
        asset = acquire_library_music(args, plan)
    except LibraryBgmError as error:
        if fallback is not None:
            raise LibraryBgmError(f"AI music unavailable ({fallback['reason']}); library failed: {error}") from error
        raise
    require_current_inputs(plan)
    library_plan = prepare(args.project, args.brief, args.name, asset["audioFormat"])
    require_approval(library_plan)
    return publish(
        library_plan, asset["audio"], None, asset["provenance"]["provider"],
        library_provenance=asset["provenance"], fallback=fallback,
    )


def acquire_library_music(args, plan: dict) -> dict:
    source = args.library_source
    sources = ["incompetech", "commons"] if source == "auto" else [source]
    if source == "auto" and not plan["brief"].get("allowAttribution", True):
        sources = ["commons"]
    failures = []
    for source in sources:
        require_current_inputs(plan)
        if source == "incompetech":
            # Detect local collisions before spending a catalog or download request.
            prepare(args.project, args.brief, args.name, "mp3")
        provider = "incompetech" if source == "incompetech" else "wikimedia-commons"
        client_type = IncompetechMusic if source == "incompetech" else LibraryMusic
        client = (
            client_type(timeout=args.timeout, cache_dir=args.library_cache)
            if args.library_cache else client_type(timeout=args.timeout)
        )
        try:
            asset = client.acquire(plan["brief"], max(plan["duration"], plan["renderedDuration"]))
            if asset["audioFormat"] not in ("wav", "flac", "mp3"):
                raise LibraryBgmError("format: unsupported library audio format")
            measured = measure_audio(asset["audio"], asset["audioFormat"])
            if measured + 1e-9 < max(plan["duration"], plan["renderedDuration"]):
                raise LibraryBgmError("duration: library recording is shorter than the video")
            validate_library_provenance(asset["provenance"])
            if asset["provenance"]["provider"] != provider:
                raise LibraryBgmError("source: library provider does not match the acquisition")
        except (LibraryBgmError, BgmError) as error:
            failures.append({"provider": provider, "reason": str(error)})
            print(json.dumps({"status": "library-source-unavailable", **failures[-1]}), file=sys.stderr)
            continue
        if failures:
            asset = {**asset, "provenance": {**asset["provenance"], "libraryFailures": failures}}
        return asset
    detail = "; ".join(f"{failure['provider']}: {failure['reason']}" for failure in failures)
    raise LibraryBgmError(f"No matching licensed soundtrack could be acquired ({detail})")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    preflight = commands.add_parser("preflight", help="Inspect the selected music service and its API")
    review = commands.add_parser("review", help="Show the music direction and fingerprint without contacting a provider")
    generate = commands.add_parser("generate", help="Generate or select, measure, and attach instrumental BGM")
    for command in (preflight, review, generate):
        command.add_argument(
            "--provider",
            choices=("local", "huggingface") if command is preflight else ("local", "huggingface", "auto", "library"),
            default="local",
            help="auto tries hosted AI once, then selects CC0/CC BY music with required end credits",
        )
        command.add_argument("--base-url", help="Local ACE-Step origin; not used for huggingface")
        command.add_argument("--timeout", type=float, default=600)
    for command in (review, generate):
        command.add_argument("--project", required=True, type=Path)
        command.add_argument("--brief", required=True, type=Path)
        command.add_argument("--name", default="bgm")
    generate.add_argument("--model", default=SUPPORTED_MODEL)
    generate.add_argument(
        "--library-source", choices=("auto", "incompetech", "commons"), default="auto",
        help="Library acquisition: dynamic mood search first, then the reviewed Commons catalog",
    )
    generate.add_argument(
        "--library-cache", type=Path,
        help="Optional directory of previously acquired originals; current source and byte hashes are still verified",
    )
    generate.add_argument(
        "--known-ai-blocker", choices=("quota", "auth", "unavailable"),
        help="auto only: reuse an already observed blocker without another hosted request",
    )
    args = parser.parse_args()
    client = None
    try:
        # Validate local inputs before contacting the service or submitting a job.
        plan = prepare(
            args.project, args.brief, args.name,
            "flac" if args.provider in ("huggingface", "auto", "library") else "wav",
        ) if args.command in ("review", "generate") else None
        if args.command == "review":
            print(json.dumps({
                "success": True,
                "status": "awaiting-user-decision",
                "direction": plan["brief"]["direction"],
                "rationale": plan["brief"]["rationale"],
                "durationSeconds": plan["duration"],
                "provider": args.provider,
                "fingerprint": approval_fingerprint(plan),
            }, ensure_ascii=False, indent=2))
            return 0
        if args.command == "generate":
            require_approval(plan)
            if args.known_ai_blocker and args.provider != "auto":
                raise BgmError("--known-ai-blocker is only supported with --provider auto")
            if args.provider in ("auto", "library"):
                result = generate_with_library(args, plan)
                print(json.dumps(result, indent=2))
                return 0
        if args.provider == "huggingface":
            if args.base_url:
                raise BgmError("--base-url is only supported by the local provider")
            if plan and plan["duration"] > 120:
                raise BgmError("The free hosted provider supports Reel clips up to 120 seconds; no automatic splitting or repeated jobs")
            client = HostedAceStep(timeout=args.timeout)
            provider = "huggingface"
        else:
            client = LocalAceStep(args.base_url or "http://127.0.0.1:8001", args.timeout)
            provider = "ace-step"
        models = client.models()
        if args.command == "preflight":
            result = {
                "success": True, "provider": provider, "models": models,
                "status": "api-compatible" if provider == "huggingface" else "model-loaded",
            }
        else:
            if args.model not in models:
                raise BgmError("Selected model is unavailable; choose one reported by preflight")
            require_current_inputs(plan)
            audio = client.generate(plan["brief"], plan["duration"], args.model)
            result = publish(plan, audio, args.model, provider)
    except (BgmError, HostedBgmError, LibraryBgmError) as error:
        failure = {"success": False, "error": str(error)}
        event_id = getattr(client, "last_event_id", None)
        if isinstance(event_id, str) and re.fullmatch(r"[a-zA-Z0-9_-]{1,128}", event_id):
            failure["eventId"] = event_id
        print(json.dumps(failure), file=sys.stderr)
        return 1
    except (OSError, ValueError) as error:
        # Do not echo request headers, provider bodies, prompts, or private file contents.
        print(json.dumps({"success": False, "error": f"Local BGM operation failed ({type(error).__name__}); check input files and permissions"}), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
