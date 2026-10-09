"""Offline protocol tests: no model, network access, credentials, or file writes."""

from email.message import Message
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError


SCRIPT = Path(__file__).resolve().parents[2] / "skills/reel/scripts/hosted_bgm.py"
SPEC = importlib.util.spec_from_file_location("reel_hosted_bgm", SCRIPT)
hosted = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(hosted)

BRIEF = {
    "prompt": "Gentle instrumental piano and warm strings, no vocals.",
    "instrumental": True, "seed": 42, "bpm": 80, "keyScale": "C Major",
    "timeSignature": "4", "rationale": "PRIVATE rationale", "story": "PRIVATE story",
}
FILE_URL = hosted.ENDPOINT + "/gradio_api/file=/data/gradio/abc/generated.flac"
# Container fixture only; the parent's stream validator owns audio measurement.
FLAC = b"fLaC\x80\x00\x00\x22" + b"\x00" * 34 + b"\xff\xf8\x00"


def contract(flac=True):
    params = [
        {"parameter_name": name, "component": component,
         "label": hosted._LABELS.get(i, f"parameter_{i}"), "type": {},
         "parameter_default": value}
        for i, (name, component, value) in enumerate(
            zip(hosted._NAMES, hosted._COMPONENTS, hosted._DEFAULTS)
        )
    ]
    params[0]["type"]["enum"] = ["acestep-v15-xl-turbo", hosted.MODEL]
    params[0]["parameter_default"] = "acestep-v15-xl-turbo"
    params[8]["type"]["enum"] = ["", "2", "3", "4"]
    params[30]["type"]["enum"] = ["mp3"] + (["flac"] if flac else [])
    outputs = [{"component": "Audio", "label": f"Sample {i}"} for i in range(8)]
    outputs.extend([
        {"component": "File", "label": "All Generated Files"},
        {"component": "Markdown", "label": "Generation Details"},
        {"component": "Textbox", "label": "Generation Status"},
        {"component": "Textbox", "label": "Seed"},
    ])
    outputs.extend({"component": "Textbox"} for _ in range(26))
    return {"named_endpoints": {"/generation_wrapper": {"parameters": params, "returns": outputs}}}


def result(audio=None, status="Generation completed successfully"):
    data = [None] * 55
    data[0], data[10] = audio, status
    return data


def wire_config():
    # Public Space revision 7403460: /info omits these /config wire slots.
    input_types = [c.lower() for c in hosted._COMPONENTS]
    input_types.insert(40, "state")
    input_types.extend(["state"] * 4)
    output_types = (
        ["audio"] * 8 + ["file", "markdown"] + ["textbox"] * 18
        + ["accordion"] * 8 + ["textbox"] * 8 + ["state"] * 6
        + ["textbox", "button", "button", "textbox", "button"]
    )
    components = [
        {"id": i, "type": kind, "skip_api": kind in ("state", "accordion", "button")}
        for i, kind in enumerate(input_types + output_types)
    ]
    return {
        "components": components,
        "dependencies": [{
            "api_name": "generation_wrapper",
            "inputs": list(range(54)),
            "outputs": list(range(54, 109)),
        }],
    }


def sse(event, data, event_id="abc123"):
    if event in ("generating", "complete", "error"):
        message = {
            "msg": "process_generating" if event == "generating" else "process_completed",
            "event_id": event_id,
            "success": event != "error",
            "output": {"error": data} if event == "error" else {"data": data},
        }
    else:
        message = {"msg": event}
    return f"data: {json.dumps(message)}\r\n\r\n".encode()


class Response(io.BytesIO):
    def __init__(self, data, content_type="application/json", url=None, fragment=23):
        super().__init__(data if isinstance(data, bytes) else json.dumps(data).encode())
        self.headers = Message()
        self.headers["Content-Type"] = content_type
        self.url = url
        self.fragment = fragment

    def geturl(self):
        return self.url

    def read1(self, size=-1):
        return self.read(min(size, self.fragment))


class HostedTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict("os.environ", {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.client = hosted.HostedAceStep()
        self.calls = []

    def install(self, responses):
        responses = iter(responses)

        def open_request(request, timeout):
            self.calls.append(request)
            response = next(responses)
            if isinstance(response, Exception):
                raise response
            if response.url is None:
                response.url = request.full_url
            return response

        self.client._opener.open = open_request

    def success(self, stream=None, audio=FLAC, info=None):
        if stream is None:
            stream = (
                sse("heartbeat", None)
                + sse("generating", result({"__type__": "update", "value": {
                    "url": FILE_URL, "path": "/ignored", "meta": {"_type": "gradio.FileData"},
                }}))
                + sse("complete", result({"__type__": "update"}))
            )
        self.install([
            Response(info or contract()), Response(wire_config()), Response({"event_id": "abc123"}),
            Response(stream, "text/event-stream"), Response(audio, "audio/flac"),
        ])

    def test_real_wire_state_slots_and_unprojected_results(self):
        raw_result = [None] * 55
        raw_result[0] = {"url": FILE_URL}
        raw_result[10] = "Generation completed successfully"

        def server(request, timeout):
            self.calls.append(request)
            url = request.full_url
            if url.endswith("/info"):
                response = Response(contract())
            elif url.endswith("/config"):
                response = Response(wire_config())
            elif request.data is not None:
                data = json.loads(request.data)["data"]
                self.assertEqual(len(data), 54, "Gradio validates all wire inputs, not only /info parameters")
                self.assertIsNone(data[40])
                self.assertEqual(data[50:54], [None] * 4)
                self.assertEqual(data[41:50], [False, False, False, False, 0.5, 8, None, [], False])
                response = Response({"event_id": "wire-test"})
            elif url.endswith("/queue/data?session_hash=wire-test"):
                response = Response(sse("complete", raw_result, "wire-test"), "text/event-stream")
            else:
                self.assertEqual(url, FILE_URL)
                response = Response(FLAC, "audio/flac")
            response.url = url
            return response

        self.client._opener.open = server
        self.assertEqual(self.client.generate(BRIEF, 10, hosted.MODEL), FLAC)

    def test_single_job_stream_updates_and_private_fields(self):
        self.success()
        self.assertEqual(self.client.generate(BRIEF, 10.1, hosted.MODEL), FLAC)
        self.assertEqual(self.client.last_event_id, "abc123")
        self.assertEqual(len(self.calls), 5)
        posts = [r for r in self.calls if r.data]
        self.assertEqual(len(posts), 1)
        self.assertNotIn("PRIVATE", posts[0].data.decode())
        values = json.loads(posts[0].data)["data"]
        self.assertEqual(len(values), 54)
        self.assertEqual(values[0], hosted.MODEL)
        self.assertEqual(values[4], BRIEF["prompt"])
        self.assertEqual(values[5], "[Instrumental]")
        self.assertEqual(values[6:9], [80, "C Major", "4"])
        self.assertEqual(values[12:17], [False, "42", None, 11, 1])
        self.assertEqual(values[30], "flac")
        for i in (32, 37, 38, 39, 41, 42, 43, 44, 49):
            self.assertIs(values[i], False)
        self.assertTrue(all(r.get_header("Authorization") is None for r in self.calls))

    def test_lossless_format_drift_is_an_explicit_pre_submit_blocker(self):
        self.install([Response(contract(flac=False))])
        with self.assertRaisesRegex(hosted.HostedBgmError, "^format:.*no job submitted"):
            self.client.generate(BRIEF, 10, hosted.MODEL)
        self.assertEqual(len(self.calls), 1)

    def test_models_checks_contract_not_hardware(self):
        self.install([Response(contract()), Response(wire_config())])
        self.assertEqual(self.client.models(), [hosted.MODEL])
        self.assertEqual(len(self.calls), 2)

    def test_wire_contract_drift_blocks_submission(self):
        for mutation in ("state-slot", "skip-api", "output", "duplicate-endpoint"):
            config = wire_config()
            if mutation == "state-slot":
                config["dependencies"][0]["inputs"].pop(40)
            elif mutation == "skip-api":
                config["components"][40]["skip_api"] = False
            elif mutation == "output":
                config["dependencies"][0]["outputs"].pop()
            else:
                config["dependencies"].append(dict(config["dependencies"][0]))
            with self.subTest(mutation=mutation):
                self.calls.clear()
                self.install([Response(contract()), Response(config)])
                with self.assertRaisesRegex(hosted.HostedBgmError, "^schema:.*wire-level"):
                    self.client.generate(BRIEF, 10, hosted.MODEL)
                self.assertEqual(len(self.calls), 2)
                self.assertTrue(all(request.data is None for request in self.calls))

    def test_queue_progress_and_job_identity(self):
        self.success(stream=(
            sse("estimation", None) + sse("process_starts", None)
            + sse("progress", None) + sse("log", None)
            + sse("complete", result({"url": FILE_URL}))
        ))
        self.assertEqual(self.client.generate(BRIEF, 10, hosted.MODEL), FLAC)
        self.success(stream=sse("complete", result({"url": FILE_URL}), "another-job"))
        with self.assertRaisesRegex(hosted.HostedBgmError, "another job"):
            self.client.generate(BRIEF, 10, hosted.MODEL)

    def test_model_and_schema_drift(self):
        for mutation in ("model", "name", "label", "count", "component", "output"):
            info = contract()
            endpoint = info["named_endpoints"]["/generation_wrapper"]
            params = endpoint["parameters"]
            if mutation == "model":
                params[0]["type"]["enum"] = ["acestep-v15-xl-turbo"]
            elif mutation == "name":
                params[37]["parameter_name"] = "different"
            elif mutation == "label":
                params[30]["label"] = "Changed Format"
            elif mutation == "count":
                params.pop()
            elif mutation == "component":
                params[48]["component"] = "Textbox"
            else:
                endpoint["returns"][10]["label"] = "Other Output"
            with self.subTest(mutation=mutation):
                self.install([Response(info)])
                with self.assertRaisesRegex(hosted.HostedBgmError, "^(model|schema):"):
                    self.client.models()

    def test_bad_inputs_do_not_access_network(self):
        self.install([])
        for change in (
            {"duration": 121}, {"duration": float("nan")}, {"duration": True},
            {"model": "acestep-v15-xl-turbo"}, {"seed": -1}, {"seed": True},
            {"seed": 1.5}, {"prompt": ""}, {"prompt": "x" * 4001},
            {"instrumental": False}, {"bpm": 80.5}, {"keyScale": "PRIVATE story"},
            {"timeSignature": "6"},
        ):
            brief = dict(BRIEF, **{k: v for k, v in change.items() if k not in ("duration", "model")})
            with self.subTest(change=change):
                with self.assertRaises(hosted.HostedBgmError):
                    self.client.generate(brief, change.get("duration", 10), change.get("model", hosted.MODEL))
        self.assertFalse(self.calls)

    def test_duration_floor(self):
        self.success()
        self.client.generate(BRIEF, 1, hosted.MODEL)
        self.assertEqual(json.loads(self.calls[2].data)["data"][15], 10)

    def test_error_status_rejects_even_previous_valid_audio(self):
        self.success(stream=(
            sse("generating", result({"url": FILE_URL}))
            + sse("complete", result({"__type__": "update"}, "Error: GPU quota exceeded"))
        ))
        with self.assertRaisesRegex(hosted.HostedBgmError, "^quota:"):
            self.client.generate(BRIEF, 10, hosted.MODEL)
        self.assertEqual(len(self.calls), 4)

    def test_error_events_and_null_audio(self):
        for data, category in (
            ("GPU quota exceeded", "quota"), ("queue is full", "queue"),
            ("authentication needed", "auth"), (None, "runtime"),
        ):
            with self.subTest(category=category):
                self.success(stream=sse("error", data))
                with self.assertRaisesRegex(hosted.HostedBgmError, "^" + category + ":"):
                    self.client.generate(BRIEF, 10, hosted.MODEL)
        self.success(stream=sse("complete", result(None, "Failed: model not initialized")))
        with self.assertRaisesRegex(hosted.HostedBgmError, "^runtime:"):
            self.client.generate(BRIEF, 10, hosted.MODEL)

    def test_no_retry_http_network_and_redirect_failures(self):
        for status, category in ((401, "auth"), (403, "auth"), (429, "quota"), (503, "queue"), (302, "redirect")):
            self.calls.clear()
            self.install([HTTPError(hosted.ENDPOINT, status, "", Message(), io.BytesIO(b"queue full PRIVATE"))])
            with self.subTest(status=status):
                with self.assertRaisesRegex(hosted.HostedBgmError, "^" + category + ":") as error:
                    self.client.models()
                self.assertNotIn("PRIVATE", str(error.exception))
                self.assertEqual(len(self.calls), 1)
        self.install([URLError("secret")])
        with self.assertRaisesRegex(hosted.HostedBgmError, "^network:"):
            self.client.models()
        with self.assertRaisesRegex(hosted.HostedBgmError, "^redirect:"):
            hosted._NoRedirect().redirect_request(None, None, 302, "", {}, "https://evil.invalid")

    def test_token_only_environment_and_only_allowlisted_origin(self):
        with patch.dict("os.environ", {"REEL_HF_TOKEN": "fixture-token"}):
            self.success()
            self.client.generate(BRIEF, 10, hosted.MODEL)
        self.assertTrue(all(r.get_header("Authorization") == "Bearer fixture-token" for r in self.calls))
        self.assertTrue(all(r.full_url.startswith(hosted.ENDPOINT + "/") for r in self.calls))
        self.assertNotIn("fixture-token", str(self.client.__dict__))

    def test_file_url_restrictions(self):
        for url in (
            "https://evil.invalid/gradio_api/file=/a.flac",
            hosted.ENDPOINT.replace("https:", "http:") + "/gradio_api/file=/a.flac",
            hosted.ENDPOINT + ".evil.invalid/gradio_api/file=/a.flac",
            hosted.ENDPOINT + "/gradio_api/file=https://evil.invalid/a.flac",
            hosted.ENDPOINT + "/gradio_api/file=/a/../secret.flac",
            hosted.ENDPOINT + "/gradio_api/file=/a/%2e%2e/secret.flac",
            hosted.ENDPOINT + "/gradio_api/file=/a/%252e%252e/secret.flac",
            FILE_URL + "?token=secret", FILE_URL + "#fragment",
            FILE_URL.replace(".flac", ".wav"), FILE_URL.replace("/data/", "//data/"),
        ):
            with self.subTest(url=url):
                with self.assertRaisesRegex(hosted.HostedBgmError, "^download:"):
                    hosted.HostedAceStep._audio_url({"url": url})
        with self.assertRaises(hosted.HostedBgmError):
            hosted.HostedAceStep._audio_url({"path": FILE_URL})
        self.assertEqual(hosted.HostedAceStep._audio_url({"url": FILE_URL}), FILE_URL)

    def test_malformed_stream_response_and_event_id(self):
        for stream in (sse("complete", []), sse("heartbeat", None), sse("unknown", None), b"event: complete\ndata: [invalid]\n\n"):
            self.success(stream=stream)
            with self.assertRaises(hosted.HostedBgmError):
                self.client.generate(BRIEF, 10, hosted.MODEL)
        self.install([Response(contract()), Response(wire_config()), Response({"event_id": "../escape"})])
        with self.assertRaisesRegex(hosted.HostedBgmError, "^schema:"):
            self.client.generate(BRIEF, 10, hosted.MODEL)

    def test_limits_deadline_and_invalid_audio(self):
        self.install([Response(b"x" * 101)])
        with patch.object(hosted, "MAX_RESPONSE_BYTES", 100):
            with self.assertRaisesRegex(hosted.HostedBgmError, "^size:"):
                self.client.models()
        self.success()
        with patch.object(hosted, "MAX_AUDIO_BYTES", 44):
            with self.assertRaisesRegex(hosted.HostedBgmError, "^size:"):
                self.client.generate(BRIEF, 10, hosted.MODEL)
        for audio in (
            b"fLaC" + b"x" * 100, FLAC[:42], b"<html>login</html>",
            FLAC[:41], b"fLaC\x00\x00\x00\x22" + b"\x00" * 34,
            b"fLaC\x80\x00\x00\x23" + b"\x00" * 36,
        ):
            self.success(audio=audio)
            with self.assertRaisesRegex(hosted.HostedBgmError, "^format:"):
                self.client.generate(BRIEF, 10, hosted.MODEL)
        self.install([TimeoutError()])
        with self.assertRaisesRegex(hosted.HostedBgmError, "^timeout:"):
            self.client.models()
        with patch.object(hosted.time, "monotonic", return_value=20):
            with self.assertRaisesRegex(hosted.HostedBgmError, "^timeout:"):
                self.client._remaining(10)

    def test_flac_metadata_blocks_and_nonempty_audio(self):
        padded = b"fLaC\x00\x00\x00\x22" + b"\x00" * 34 + b"\x81\x00\x00\x02\x00\x00\xff\xf8"
        self.success(audio=padded)
        self.assertEqual(self.client.generate(BRIEF, 10, hosted.MODEL), padded)
        for audio in (
            padded[:-2],
            b"fLaC\x00\x00\x00\x22" + b"\x00" * 34 + FLAC[4:],
            b"fLaC\xff\x00\x00\x22" + b"\x00" * 34 + b"\xff\xf8",
        ):
            with self.assertRaisesRegex(hosted.HostedBgmError, "^format:"):
                hosted.HostedAceStep._validate_flac(audio)

    def test_opaque_sse_error_is_not_misclassified(self):
        self.success(stream=sse("error", None))
        with self.assertRaisesRegex(hosted.HostedBgmError, "opaque SSE error.*unknown"):
            self.client.generate(BRIEF, 10, hosted.MODEL)
        self.assertEqual(self.client.last_event_id, "abc123")
        self.assertEqual(len(self.calls), 4)


if __name__ == "__main__":
    unittest.main()
