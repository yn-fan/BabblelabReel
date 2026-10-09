"""Bounded, single-job client for the official ACE-Step Hugging Face Space.

Protocol evidence: ACE-Step/Ace-Step-v1.5, gradio_ui/events/__init__.py
(generation_wrapper inputs), events/results_handlers.py (streamed updates),
and Gradio 6.2.0 routes.py (named submission and raw queue events).
No local model or SDK is used.
"""

from __future__ import annotations

from http.client import HTTPException
import json
import math
import os
import re
import socket
import time
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


ENDPOINT = "https://ace-step-ace-step-v1-5.hf.space"
SPACE = "ACE-Step/Ace-Step-v1.5"
MODEL = "acestep-v15-turbo"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_AUDIO_BYTES = 300 * 1024 * 1024
CALL_PATH = "/gradio_api/call/generation_wrapper"


class HostedBgmError(ValueError):
    """A categorized failure that never includes provider payloads or credentials."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise HostedBgmError("redirect: hosted requests must not redirect")


# /info omits State inputs (including param_40), but HTTP requests retain them.
_NAMES = (
    ["selected_model", "generation_mode", "simple_query_input", "simple_vocal_language"]
    + [f"param_{i}" for i in range(4, 40)]
    + [f"param_{i}" for i in range(41, 50)]
)
_COMPONENTS = (
    "Dropdown Radio Textbox Dropdown Textbox Textbox Number Textbox Dropdown "
    "Dropdown Slider Slider Checkbox Textbox Audio Number Number Audio Textbox "
    "Number Number Textbox Slider Dropdown Checkbox Slider Slider Slider Dropdown "
    "Textbox Dropdown Slider Checkbox Slider Slider Slider Textbox Checkbox "
    "Checkbox Checkbox Checkbox Checkbox Checkbox Checkbox Slider Number Dropdown "
    "Checkboxgroup Checkbox"
).split()
_LABELS = {
    0: "models", 4: "Prompt", 5: "Lyrics", 6: "BPM (optional)",
    7: "Key Signature (optional)", 8: "Time Signature (optional)",
    12: "Random Seed", 13: "Seed", 15: "Audio Duration (seconds)",
    16: "batch size", 30: "Audio Format", 32: "Thinking",
}
_DEFAULTS = [
    MODEL, "custom", None, "unknown", "", "[Instrumental]", 0, "", "", "unknown",
    8, 7.0, False, "0", None, 10, 1, None, None, 0.0, -1,
    "Fill the audio semantic mask based on the given conditions:", 1.0, "text2music",
    False, 0.0, 1.0, 3.0, "ode", "", "flac", 0.85, False, 2.0, 0, 0.9,
    "NO USER INPUT", False, False, False, False, False, False, False, 0.5, 8,
    None, [], False,
]
_WIRE_INPUT_TYPES = (
    [c.lower() for c in _COMPONENTS[:40]] + ["state"]
    + [c.lower() for c in _COMPONENTS[40:]] + ["state"] * 4
)
_WIRE_OUTPUT_TYPES = (
    ["audio"] * 8 + ["file", "markdown"] + ["textbox"] * 18
    + ["accordion"] * 8 + ["textbox"] * 8 + ["state"] * 6
    + ["textbox", "button", "button", "textbox", "button"]
)


def _failure(value: object, fallback: str = "runtime") -> HostedBgmError:
    # Classify, but do not echo arbitrary server text (which can include prompts).
    text = str(value).lower()
    if any(term in text for term in ("quota", "gpu duration", "rate limit", "too many requests")):
        return HostedBgmError("quota: shared free GPU allowance is exhausted; try later manually")
    if any(term in text for term in ("unauthorized", "forbidden", "sign in", "login", "authentication")):
        return HostedBgmError("auth: the Space requires access; optionally set REEL_HF_TOKEN")
    if any(term in text for term in ("queue", "overloaded")):
        return HostedBgmError("queue: the shared Space queue is unavailable; try later manually")
    return HostedBgmError(
        f"{fallback}: official Space request failed; no job was resubmitted"
    )


def _number(value: object, label: str, minimum: float, maximum: float) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not minimum <= value <= maximum
    ):
        raise HostedBgmError(f"input: {label} must be between {minimum} and {maximum}")
    return float(value)


def _unwrap(value: object) -> object:
    if isinstance(value, dict) and value.get("__type__") == "update":
        return value.get("value")
    return value


class HostedAceStep:
    def __init__(self, timeout: float = 600):
        self.timeout = _number(timeout, "timeout", 0.001, 86400)
        self._opener = build_opener(ProxyHandler({}), _NoRedirect())
        self.last_event_id: str | None = None

    @staticmethod
    def _remaining(deadline: float) -> float:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise HostedBgmError("timeout: hosted deadline expired; no job was resubmitted")
        return remaining

    def _read(self, response, size: int, deadline: float) -> bytes:
        remaining = self._remaining(deadline)
        # HTTPResponse.read1 performs at most one underlying read, so a stream
        # of short heartbeats cannot keep resetting a long read() timeout.
        sock = getattr(getattr(getattr(response, "fp", None), "raw", None), "_sock", None)
        if sock is not None:
            sock.settimeout(remaining)
        data = response.read1(size)
        self._remaining(deadline)
        return data

    def _body(self, response, limit: int, deadline: float) -> bytes:
        length = response.headers.get("Content-Length")
        if length is not None:
            try:
                if not 0 <= int(length) <= limit:
                    raise HostedBgmError("size: hosted response exceeds the byte limit")
            except ValueError as error:
                if isinstance(error, HostedBgmError):
                    raise
                raise HostedBgmError("schema: invalid response content length") from None
        chunks = []
        total = 0
        while True:
            chunk = self._read(response, min(65536, limit + 1 - total), deadline)
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > limit:
                raise HostedBgmError("size: hosted response exceeds the byte limit")
        if length is not None and total != int(length):
            raise HostedBgmError("network: hosted response was truncated")
        return b"".join(chunks)

    def _open(self, url: str, deadline: float, payload: dict | None = None):
        if not (
            url.startswith(ENDPOINT + "/gradio_api/")
            or (url == ENDPOINT + "/config" and payload is None)
        ):
            raise HostedBgmError("download: request is outside the official Space")
        token = os.environ.get("REEL_HF_TOKEN", "")
        if any(ord(c) < 33 or ord(c) > 126 for c in token):
            raise HostedBgmError("auth: REEL_HF_TOKEN contains invalid characters")
        headers = {"Accept": "application/json, text/event-stream, audio/flac"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        body = None
        if payload is not None:
            body = json.dumps(payload, allow_nan=False).encode("utf-8")
            if len(body) > MAX_RESPONSE_BYTES:
                raise HostedBgmError("size: generation request exceeds the byte limit")
            headers["Content-Type"] = "application/json"
        try:
            response = self._opener.open(
                Request(url, data=body, headers=headers),
                timeout=self._remaining(deadline),
            )
        except HTTPError as error:
            with error:
                if 300 <= error.code < 400:
                    raise HostedBgmError("redirect: hosted requests must not redirect") from None
                if error.code in (401, 403):
                    raise _failure("authentication") from None
                if error.code == 429:
                    raise _failure("quota") from None
                text = self._body(error, MAX_RESPONSE_BYTES, deadline).decode("utf-8", "replace")
                raise _failure(text, "schema" if error.code in (404, 422) else "runtime") from None
        if response.geturl() != url:
            response.close()
            raise HostedBgmError("redirect: hosted requests must not redirect")
        return response

    @staticmethod
    def _json(data: bytes):
        try:
            return json.loads(data)
        except (ValueError, UnicodeError, RecursionError):
            raise HostedBgmError("schema: invalid hosted JSON response") from None

    def _contract(self, deadline: float) -> list[dict]:
        with self._open(ENDPOINT + "/gradio_api/info", deadline) as response:
            info = self._json(self._body(response, MAX_RESPONSE_BYTES, deadline))
        try:
            endpoint = info["named_endpoints"]["/generation_wrapper"]
            params = endpoint["parameters"]
            outputs = endpoint["returns"]
            valid = (
                len(params) == 49 and len(outputs) == 38
                and all(p["parameter_name"] == n and p["component"] == c
                        and isinstance(p["type"], dict)
                        for p, n, c in zip(params, _NAMES, _COMPONENTS))
                and all(params[i]["label"] == label for i, label in _LABELS.items())
                and all(outputs[i]["component"] == "Audio" for i in range(8))
                and outputs[8]["component"] == "File"
                and outputs[9]["label"] == "Generation Details"
                and outputs[10]["label"] == "Generation Status"
                and outputs[11]["label"] == "Seed"
            )
            if not valid:
                raise ValueError
            if MODEL not in params[0]["type"]["enum"]:
                raise HostedBgmError("model: official Space no longer offers standard turbo")
        except (KeyError, TypeError, IndexError, ValueError) as error:
            if isinstance(error, HostedBgmError):
                raise
            raise HostedBgmError("schema: official generation API contract changed") from None
        return params

    def models(self) -> list[str]:
        """Verify the live contract/selector, not model load or GPU availability."""
        return self._guard(self._models)

    def _models(self) -> list[str]:
        deadline = time.monotonic() + self.timeout
        self._contract(deadline)
        self._wire_contract(deadline)
        return [MODEL]

    def _wire_contract(self, deadline: float) -> None:
        with self._open(ENDPOINT + "/config", deadline) as response:
            config = self._json(self._body(response, MAX_RESPONSE_BYTES, deadline))
        try:
            components = {c["id"]: c for c in config["components"]}
            matches = [
                d for d in config["dependencies"]
                if isinstance(d, dict) and d.get("api_name") == "generation_wrapper"
            ]
            if len(matches) != 1:
                raise ValueError
            for field, expected in (("inputs", _WIRE_INPUT_TYPES), ("outputs", _WIRE_OUTPUT_TYPES)):
                actual = [components[cid] for cid in matches[0][field]]
                if [c["type"] for c in actual] != expected:
                    raise ValueError
                if any(c["skip_api"] is not (c["type"] in ("state", "accordion", "button")) for c in actual):
                    raise ValueError
        except (KeyError, TypeError, ValueError):
            raise HostedBgmError("schema: official wire-level generation contract changed; no job submitted") from None

    @staticmethod
    def _guard(operation, *args):
        try:
            return operation(*args)
        except HostedBgmError:
            raise
        except (TimeoutError, socket.timeout):
            raise HostedBgmError("timeout: hosted request timed out; no job was resubmitted") from None
        except (OSError, URLError, HTTPException):
            raise HostedBgmError("network: cannot reach official Space; no job was resubmitted") from None

    def generate(self, brief: dict, duration: float, model: str) -> bytes:
        return self._guard(self._generate, brief, duration, model)

    def _generate(self, brief: dict, duration: float, model: str) -> bytes:
        deadline = time.monotonic() + self.timeout
        self.last_event_id = None
        if model != MODEL:
            raise HostedBgmError("model: only acestep-v15-turbo is supported")
        duration = max(10, math.ceil(_number(duration, "duration", 0.001, 120)))
        if not isinstance(brief, dict) or brief.get("instrumental") is not True:
            raise HostedBgmError("input: brief must explicitly request instrumental music")
        prompt = brief.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 4000:
            raise HostedBgmError("input: prompt must contain 1–4000 characters")
        seed = brief.get("seed")
        _number(seed, "seed", 0, 2**31 - 1)
        if not isinstance(seed, int):
            raise HostedBgmError("input: seed must be an integer")
        bpm = brief.get("bpm")
        _number(bpm, "bpm", 30, 300)
        if not isinstance(bpm, int):
            raise HostedBgmError("input: bpm must be an integer")
        key = brief.get("keyScale")
        if not isinstance(key, str) or not re.fullmatch(r"[A-G](?:#|b)? (?:Major|Minor)", key):
            raise HostedBgmError("input: keyScale must name a musical key")
        signature = brief.get("timeSignature")
        if signature not in ("2", "3", "4"):
            raise HostedBgmError("input: hosted timeSignature must be 2, 3, or 4")
        params = self._contract(deadline)
        data = list(_DEFAULTS)
        data[4], data[6], data[7], data[8] = prompt, bpm, key, signature
        data[13], data[15] = str(seed), duration
        # Request the advertised lossless format; preserve the exact download.
        if "flac" not in params[30]["type"].get("enum", []):
            raise HostedBgmError(
                "format: official Space no longer advertises lossless FLAC; no job submitted"
            )
        for param, value in zip(params, data):
            choices = param["type"].get("enum")
            if choices is not None and value is not None and value not in choices:
                raise HostedBgmError("schema: official generation parameter choices changed")
        self._wire_contract(deadline)
        data = data[:40] + [None] + data[40:] + [None] * 4
        with self._open(ENDPOINT + CALL_PATH, deadline, {"data": data}) as response:
            job = self._json(self._body(response, MAX_RESPONSE_BYTES, deadline))
        if not isinstance(job, dict) or not isinstance(job.get("event_id"), str):
            raise _failure(job, "schema")
        event_id = job["event_id"]
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,128}", event_id):
            raise HostedBgmError("schema: invalid hosted event identifier")
        self.last_event_id = event_id
        # With no caller session_hash, Gradio uses event_id as the session.
        # Read that same job's raw queue stream: /call GET drops output.error.
        with self._open(ENDPOINT + "/gradio_api/queue/data?session_hash=" + event_id, deadline) as response:
            if response.headers.get_content_type() != "text/event-stream":
                raise HostedBgmError("schema: hosted job did not return an SSE stream")
            audio = self._events(response, deadline)
        url = self._audio_url(audio)
        with self._open(url, deadline) as response:
            audio_bytes = self._body(response, MAX_AUDIO_BYTES, deadline)
        self._validate_flac(audio_bytes)
        return audio_bytes

    @staticmethod
    def _validate_flac(audio: bytes) -> None:
        """Check the lossless container; publication validates STREAMINFO/audio."""
        if len(audio) < 43 or audio[:4] != b"fLaC":
            raise HostedBgmError("format: official download is not a nonempty FLAC file")
        offset = 4
        first = True
        while offset + 4 <= len(audio):
            header = audio[offset]
            kind = header & 0x7F
            size = int.from_bytes(audio[offset + 1:offset + 4], "big")
            offset += 4
            if (
                kind == 127 or offset + size > len(audio)
                or (first and (kind != 0 or size != 34))
                or (not first and kind == 0)
            ):
                raise HostedBgmError("format: official FLAC metadata is invalid or truncated")
            offset += size
            first = False
            if header & 0x80:
                if offset >= len(audio):
                    raise HostedBgmError("format: official FLAC contains no audio frames")
                return
        raise HostedBgmError("format: official FLAC metadata has no complete final block")

    def _events(self, response, deadline: float):
        buffer = b""
        total = 0
        lines = []
        audio = None
        while True:
            chunk = self._read(response, min(65536, MAX_RESPONSE_BYTES + 1 - total), deadline)
            if not chunk:
                raise HostedBgmError("network: hosted SSE ended before completion; no job resubmitted")
            total += len(chunk)
            if total > MAX_RESPONSE_BYTES:
                raise HostedBgmError("size: hosted SSE exceeds the byte limit")
            buffer += chunk
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                line = line.rstrip(b"\r")
                if line.startswith(b"data:"):
                    lines.append(line[5:].lstrip(b" "))
                elif not line and lines:
                    message = self._json(b"\n".join(lines))
                    lines = []
                    if not isinstance(message, dict):
                        raise HostedBgmError("schema: invalid hosted queue message")
                    event = message.get("msg")
                    if event in ("process_generating", "process_completed"):
                        if message.get("event_id") != self.last_event_id:
                            raise HostedBgmError("schema: hosted queue message belongs to another job")
                        output = message.get("output")
                        if not isinstance(output, dict):
                            raise HostedBgmError("schema: invalid hosted queue output")
                        if message.get("success") is not True:
                            detail = output.get("error")
                            if detail is not None:
                                raise _failure(detail)
                            raise HostedBgmError(
                                "runtime: Space returned an opaque SSE error; the queue "
                                "omitted its cause (backend, quota, auth, or parameters unknown); "
                                "no job was resubmitted"
                            )
                        result = output.get("data")
                        if not isinstance(result, list) or len(result) != len(_WIRE_OUTPUT_TYPES):
                            raise HostedBgmError("schema: hosted generation result changed")
                        status = _unwrap(result[10])
                        if isinstance(status, str) and re.search(
                            r"error|fail|quota|exceed|unauthor|forbidden|❌", status, re.I
                        ):
                            raise _failure(status)
                        candidate = result[0]
                        if not (isinstance(candidate, dict)
                                and candidate.get("__type__") == "update"
                                and "value" not in candidate):
                            audio = _unwrap(candidate)
                        if event == "process_completed":
                            if audio is None:
                                raise _failure(status)
                            return audio
                    elif event == "unexpected_error":
                        raise _failure(message.get("message"))
                    elif event not in ("heartbeat", "estimation", "process_starts", "progress", "log"):
                        raise HostedBgmError("schema: unexpected hosted SSE event")

    @staticmethod
    def _audio_url(audio: object) -> str:
        if not isinstance(audio, dict) or audio.get("is_stream") is True:
            raise HostedBgmError("download: invalid hosted audio descriptor")
        # Never construct a URL from path/orig_name or accept remote file URLs.
        url = audio.get("url")
        if not isinstance(url, str) or not url.startswith(ENDPOINT + "/gradio_api/file="):
            raise HostedBgmError("download: audio URL is not an official Gradio file")
        parsed = urlsplit(url)
        if parsed.query or parsed.fragment or parsed.netloc != urlsplit(ENDPOINT).netloc:
            raise HostedBgmError("download: unsafe hosted file URL")
        path = unquote(parsed.path[len("/gradio_api/file="):])
        if (
            not path.startswith("/") or path.startswith("//")
            or "\\" in path or "%" in path
            or any(part in (".", "..") for part in path.split("/"))
            or any(ord(c) < 32 or ord(c) == 127 for c in path)
            or not path.lower().endswith(".flac")
        ):
            raise HostedBgmError("download: unsafe hosted FLAC path")
        return url
