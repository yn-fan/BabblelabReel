from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "kokoro_audio.py"
SPEC = importlib.util.spec_from_file_location("kokoro_audio", SCRIPT)
assert SPEC and SPEC.loader
kokoro_audio = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = kokoro_audio
SPEC.loader.exec_module(kokoro_audio)


class KokoroAudioTests(unittest.TestCase):
    def test_basic_mode_is_default_with_platform_voices(self) -> None:
        args = kokoro_audio.build_parser().parse_args(
            ["generate", "--text", "Hello BabblelabReel."]
        )
        self.assertEqual(args.mode, "basic")
        self.assertIsNone(args.voice)
        self.assertEqual(kokoro_audio.DEFAULT_MODE, "basic")
        windows_voice = kokoro_audio.resolve_basic_voice(system="Windows")
        self.assertEqual(windows_voice["id"], "en-US-JennyNeural")
        self.assertEqual(windows_voice["label"], "Jenny")

    def test_macos_basic_voice_prefers_ava_and_falls_back_to_samantha(self) -> None:
        preferred = kokoro_audio.resolve_basic_voice(
            system="Darwin",
            macos_voices=["Ava (Premium)", "Samantha"],
        )
        self.assertEqual(preferred["id"], "Ava (Premium)")
        self.assertFalse(preferred["fallback"])

        fallback = kokoro_audio.resolve_basic_voice(
            system="Darwin",
            macos_voices=["Samantha"],
        )
        self.assertEqual(fallback["id"], "Samantha")
        self.assertTrue(fallback["fallback"])

    def test_windows_basic_preflight_checks_edge_dependencies(self) -> None:
        versions = {
            "edge-tts": "7.2.8",
            "imageio-ffmpeg": "0.6.0",
        }
        with (
            mock.patch.object(
                kokoro_audio.platform, "system", return_value="Windows"
            ),
            mock.patch.object(
                kokoro_audio.platform, "machine", return_value="AMD64"
            ),
            mock.patch.object(
                kokoro_audio.importlib.util, "find_spec", return_value=object()
            ),
            mock.patch.object(
                kokoro_audio,
                "_installed_version",
                side_effect=lambda name: versions.get(name),
            ),
        ):
            result = kokoro_audio.collect_preflight()
        self.assertTrue(result["success"], result["issues"])
        self.assertEqual(result["mode"], "basic")
        self.assertEqual(result["voice"]["id"], "en-US-JennyNeural")
        self.assertTrue(result["online"])

    def test_default_is_pinned_english_8bit_model(self) -> None:
        self.assertEqual(
            kokoro_audio.DEFAULT_MODEL, "mlx-community/Kokoro-82M-8bit"
        )
        self.assertEqual(len(kokoro_audio.DEFAULT_MODEL_REVISION), 40)
        self.assertEqual(kokoro_audio.DEFAULT_VOICE, "af_heart")
        self.assertEqual(
            kokoro_audio.ONNX_MODEL_WEIGHT, "kokoro-v1.0.int8.onnx"
        )
        self.assertEqual(len(kokoro_audio.ONNX_MODEL_WEIGHT_SHA256), 64)
        self.assertTrue(
            all(
                voice.startswith(("af_", "am_", "bf_", "bm_"))
                for voice in kokoro_audio.SUPPORTED_VOICES
            )
        )
        self.assertEqual(
            set(kokoro_audio.MLX_VOICE_SHA256),
            set(kokoro_audio.SUPPORTED_VOICES),
        )

    def test_backend_selection_prefers_platform_native_runtime(self) -> None:
        self.assertEqual(
            kokoro_audio.select_backend(
                "auto", system="Darwin", machine="arm64"
            ),
            "mlx",
        )
        self.assertEqual(
            kokoro_audio.select_backend(
                "auto", system="Windows", machine="AMD64"
            ),
            "onnx",
        )
        self.assertEqual(
            kokoro_audio.select_backend(
                "auto", system="Darwin", machine="x86_64"
            ),
            "onnx",
        )
        self.assertEqual(kokoro_audio.select_accelerator("onnx", "auto"), "cpu")
        with self.assertRaisesRegex(
            kokoro_audio.AudioGeneratorError, "requires native Apple Silicon"
        ):
            kokoro_audio.select_backend(
                "mlx", system="Windows", machine="AMD64"
            )

    def test_validation_rejects_non_english_scripts(self) -> None:
        self.assertEqual(
            kokoro_audio.validate_text("BabblelabReel’s café narration — take two."),
            "BabblelabReel’s café narration — take two.",
        )
        with self.assertRaisesRegex(kokoro_audio.AudioGeneratorError, "English-only"):
            kokoro_audio.validate_text("你好，BabblelabReel")
        with self.assertRaisesRegex(kokoro_audio.AudioGeneratorError, "English-only"):
            kokoro_audio.validate_text("Привет, BabblelabReel")

    def test_long_text_segments_stay_bounded(self) -> None:
        text = (
            "This is the first sentence with enough detail to sound natural. "
            "This second sentence adds another complete thought, with a useful pause. "
        ) * 20
        segments = kokoro_audio.segment_text(text, max_chars=120)
        self.assertGreater(len(segments), 1)
        self.assertTrue(all(0 < len(segment) <= 120 for segment in segments))

    def test_output_path_stays_in_canonical_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with mock.patch.object(kokoro_audio, "output_dir", return_value=root):
                output = kokoro_audio.resolve_output_path("narration/launch.wav", "a" * 64)
                self.assertEqual(output, (root / "narration" / "launch.wav").resolve())
                with self.assertRaises(kokoro_audio.AudioGeneratorError):
                    kokoro_audio.resolve_output_path("../outside.wav", "a" * 64)
                with self.assertRaisesRegex(
                    kokoro_audio.AudioGeneratorError, ".wav extension"
                ):
                    kokoro_audio.resolve_output_path("narration.mp3", "a" * 64)

    def test_cached_output_requires_matching_fingerprint_and_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "speech.wav"
            output.write_bytes(b"RIFF" + b"\x00" * 100)
            fingerprint = "f" * 64
            metadata = {
                "input": {"fingerprint": fingerprint},
                "output": {"sha256": kokoro_audio.sha256_file(output)},
            }
            kokoro_audio.sidecar_path(output).write_text(
                json.dumps(metadata), encoding="utf-8"
            )

            cached = kokoro_audio.load_cached_result(output, fingerprint)
            self.assertIsNotNone(cached)
            self.assertTrue(cached["cached"])
            self.assertIsNone(
                kokoro_audio.load_cached_result(output, "different-fingerprint")
            )

            kokoro_audio.sidecar_path(output).write_text("[]", encoding="utf-8")
            self.assertIsNone(
                kokoro_audio.load_cached_result(output, fingerprint)
            )
            kokoro_audio.sidecar_path(output).write_text(
                json.dumps({"input": [], "output": {}}),
                encoding="utf-8",
            )
            self.assertIsNone(
                kokoro_audio.load_cached_result(output, fingerprint)
            )

    def test_preflight_reports_python_39_as_unsupported(self) -> None:
        with (
            mock.patch.object(kokoro_audio.sys, "version_info", (3, 9, 5)),
            mock.patch.object(kokoro_audio.platform, "system", return_value="Darwin"),
            mock.patch.object(kokoro_audio.platform, "machine", return_value="arm64"),
            mock.patch.object(
                kokoro_audio.importlib.util, "find_spec", return_value=object()
            ),
            mock.patch.object(
                kokoro_audio.importlib.metadata,
                "version",
                side_effect=lambda name: kokoro_audio.PACKAGE_VERSIONS[name],
            ),
        ):
            result = kokoro_audio.collect_preflight("enhanced")
        self.assertFalse(result["success"])
        self.assertIn("Python 3.10-3.12", result["issues"][0])

    def test_windows_preflight_selects_pinned_onnx_cpu_backend(self) -> None:
        versions = {
            "kokoro-onnx": "0.6.1",
            "onnxruntime": "1.24.4",
        }
        with (
            mock.patch.object(kokoro_audio.sys, "version_info", (3, 12, 10)),
            mock.patch.object(
                kokoro_audio.platform, "system", return_value="Windows"
            ),
            mock.patch.object(
                kokoro_audio.platform, "machine", return_value="AMD64"
            ),
            mock.patch.object(
                kokoro_audio.importlib.util, "find_spec", return_value=object()
            ),
            mock.patch.object(
                kokoro_audio,
                "_installed_version",
                side_effect=lambda name: versions.get(name),
            ),
            mock.patch.object(
                kokoro_audio,
                "_available_onnx_providers",
                return_value=["CPUExecutionProvider"],
            ),
        ):
            result = kokoro_audio.collect_preflight("enhanced")
        self.assertTrue(result["success"], result["issues"])
        self.assertEqual(result["backend"], "onnx")
        self.assertEqual(result["model"]["quantization"], "INT8 ONNX")
        self.assertEqual(result["accelerator"]["selected"], "cpu")
        self.assertFalse(result["accelerator"]["experimental"])

    def test_windows_preflight_rejects_out_of_range_onnx_runtime(self) -> None:
        versions = {
            "kokoro-onnx": "0.6.1",
            "onnxruntime": "1.19.2",
        }
        with (
            mock.patch.object(kokoro_audio.sys, "version_info", (3, 12, 10)),
            mock.patch.object(
                kokoro_audio.platform, "system", return_value="Windows"
            ),
            mock.patch.object(
                kokoro_audio.platform, "machine", return_value="AMD64"
            ),
            mock.patch.object(
                kokoro_audio.importlib.util, "find_spec", return_value=object()
            ),
            mock.patch.object(
                kokoro_audio,
                "_installed_version",
                side_effect=lambda name: versions.get(name),
            ),
            mock.patch.object(
                kokoro_audio,
                "_available_onnx_providers",
                return_value=["CPUExecutionProvider"],
            ),
        ):
            result = kokoro_audio.collect_preflight("enhanced")
        self.assertFalse(result["success"])
        self.assertTrue(
            any("onnxruntime >=1.20.1,<1.25" in issue for issue in result["issues"])
        )

    def test_generate_parser_accepts_text_file_and_british_voice(self) -> None:
        args = kokoro_audio.build_parser().parse_args(
            [
                "generate",
                "--mode",
                "enhanced",
                "--text-file",
                "script.txt",
                "--voice",
                "bf_emma",
                "--speed",
                "0.95",
            ]
        )
        self.assertEqual(args.voice, "bf_emma")
        self.assertEqual(args.speed, 0.95)

    def test_synthesis_writes_wav_and_provenance_sidecar(self) -> None:
        class Result:
            audio = object()
            sample_rate = kokoro_audio.SAMPLE_RATE

        class Model:
            def generate(self, **kwargs):
                self.kwargs = kwargs
                print("Creating new KokoroPipeline for language: a")
                return [Result()]

        model = Model()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = (root / "speech.wav").resolve()
            snapshot = root / "snapshot"
            load_model = mock.Mock(return_value=model)
            with (
                mock.patch.object(
                    kokoro_audio, "select_backend", return_value="mlx"
                ),
                mock.patch.object(kokoro_audio, "require_runtime"),
                mock.patch.object(
                    kokoro_audio,
                    "_load_mlx_runtime",
                    return_value=(
                        object(),
                        object(),
                        load_model,
                        (OSError, RuntimeError),
                    ),
                ),
                mock.patch.object(
                    kokoro_audio, "_download_model", return_value=snapshot
                ),
                mock.patch.object(
                    kokoro_audio,
                    "_pcm16",
                    return_value=b"\x01\x00" * kokoro_audio.SAMPLE_RATE,
                ),
                mock.patch.object(
                    kokoro_audio, "cache_dir", return_value=root / "cache"
                ),
                mock.patch.object(
                    kokoro_audio, "output_dir", return_value=root
                ),
            ):
                captured_stdout = io.StringIO()
                captured_stderr = io.StringIO()
                with (
                    mock.patch.object(kokoro_audio.sys, "stdout", captured_stdout),
                    mock.patch.object(kokoro_audio.sys, "stderr", captured_stderr),
                ):
                    metadata = kokoro_audio.synthesize(
                        text="A short English test.",
                        voice="af_heart",
                        speed=1.0,
                        pause_ms=120,
                        output_path=output,
                        overwrite=False,
                        backend="mlx",
                    )

            self.assertTrue(output.is_file())
            self.assertGreater(output.stat().st_size, 44)
            self.assertTrue(kokoro_audio.sidecar_path(output).is_file())
            self.assertEqual(metadata["output"]["durationSeconds"], 1.0)
            self.assertEqual(metadata["output"]["path"], "speech.wav")
            self.assertEqual(metadata["output"]["metadataPath"], "speech.wav.json")
            self.assertFalse(metadata["input"]["textRetained"])
            self.assertEqual(model.kwargs["lang_code"], "a")
            self.assertTrue(model.kwargs["voice"].endswith("af_heart.safetensors"))
            load_model.assert_called_once_with(snapshot, model_type="kokoro")
            self.assertEqual(captured_stdout.getvalue(), "")
            self.assertIn("Creating new KokoroPipeline", captured_stderr.getvalue())

    def test_basic_synthesis_writes_jenny_metadata(self) -> None:
        voice = kokoro_audio.resolve_basic_voice(system="Windows")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = (root / "basic.wav").resolve()
            with (
                mock.patch.object(
                    kokoro_audio,
                    "_collect_basic_preflight",
                    return_value={"success": True, "issues": []},
                ),
                mock.patch.object(
                    kokoro_audio,
                    "_render_edge_wav",
                    return_value=kokoro_audio.SAMPLE_RATE * 2,
                ) as render,
                mock.patch.object(
                    kokoro_audio, "cache_dir", return_value=root / "cache"
                ),
                mock.patch.object(
                    kokoro_audio, "output_dir", return_value=root
                ),
            ):
                staged = root / "staged-source.wav"
                with wave.open(str(staged), "wb") as wav:
                    wav.setnchannels(1)
                    wav.setsampwidth(2)
                    wav.setframerate(kokoro_audio.SAMPLE_RATE)
                    wav.writeframes(
                        b"\x01\x00" * kokoro_audio.SAMPLE_RATE * 2
                    )

                def render_wav(path, text, voice_id, speed):
                    path.write_bytes(staged.read_bytes())
                    return kokoro_audio.SAMPLE_RATE * 2

                render.side_effect = render_wav
                metadata = kokoro_audio.synthesize_basic(
                    text="Hello from Jenny.",
                    voice=voice,
                    speed=1.0,
                    output_path=output,
                    overwrite=False,
                )

        self.assertEqual(metadata["mode"], "basic")
        self.assertEqual(metadata["voice"], "en-US-JennyNeural")
        self.assertEqual(metadata["engine"]["name"], "edge-tts")
        self.assertTrue(metadata["engine"]["online"])
        self.assertTrue(metadata["input"]["sentToOnlineService"])
        self.assertEqual(metadata["output"]["durationSeconds"], 2.0)

    def test_edge_speed_maps_to_percent_rate(self) -> None:
        self.assertEqual(kokoro_audio._edge_rate(1.0), "+0%")
        self.assertEqual(kokoro_audio._edge_rate(0.75), "-25%")
        self.assertEqual(kokoro_audio._edge_rate(1.5), "+50%")

    def test_macos_renderer_uses_say_then_afconvert(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "speech.wav"
            output.touch()
            calls = []

            def run_audio_command(command, *, label):
                calls.append((command, label))
                destination = Path(command[-1])
                self.assertFalse(destination.exists())
                if command[0] == "/usr/bin/say":
                    destination.write_bytes(b"AIFF")
                else:
                    with wave.open(str(destination), "wb") as wav:
                        wav.setnchannels(1)
                        wav.setsampwidth(2)
                        wav.setframerate(kokoro_audio.SAMPLE_RATE)
                        wav.writeframes(b"\x01\x00" * kokoro_audio.SAMPLE_RATE)

            with (
                mock.patch.object(
                    kokoro_audio.shutil,
                    "which",
                    side_effect=lambda command: f"/usr/bin/{command}",
                ),
                mock.patch.object(
                    kokoro_audio,
                    "_run_audio_command",
                    side_effect=run_audio_command,
                ),
            ):
                frames = kokoro_audio._render_macos_wav(
                    output,
                    "Hello from Ava.",
                    "Ava (Premium)",
                    1.0,
                )

        self.assertEqual(frames, kokoro_audio.SAMPLE_RATE)
        self.assertEqual(calls[0][0][0], "/usr/bin/say")
        self.assertEqual(calls[1][0][0], "/usr/bin/afconvert")

    def test_onnx_synthesis_writes_provider_metadata(self) -> None:
        class Model:
            def create(self, text, *, voice, speed, lang):
                self.call = {
                    "text": text,
                    "voice": voice,
                    "speed": speed,
                    "lang": lang,
                }
                return object(), kokoro_audio.SAMPLE_RATE

        model = Model()

        class Kokoro:
            @classmethod
            def from_session(cls, session, voices_path):
                cls.session = session
                cls.voices_path = voices_path
                return model

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = (root / "speech.wav").resolve()
            model_path = root / kokoro_audio.ONNX_MODEL_WEIGHT
            voices_path = root / kokoro_audio.ONNX_VOICES
            with (
                mock.patch.object(kokoro_audio, "require_runtime"),
                mock.patch.object(
                    kokoro_audio,
                    "_load_onnx_runtime",
                    return_value=(object(), object(), Kokoro),
                ),
                mock.patch.object(
                    kokoro_audio,
                    "_download_onnx_assets",
                    return_value=(model_path, voices_path),
                ),
                mock.patch.object(
                    kokoro_audio,
                    "_create_onnx_session",
                    return_value=(object(), ["CPUExecutionProvider"]),
                ),
                mock.patch.object(
                    kokoro_audio,
                    "_pcm16",
                    return_value=b"\x01\x00" * kokoro_audio.SAMPLE_RATE,
                ),
                mock.patch.object(
                    kokoro_audio, "cache_dir", return_value=root / "cache"
                ),
                mock.patch.object(
                    kokoro_audio, "output_dir", return_value=root
                ),
            ):
                metadata = kokoro_audio.synthesize(
                    text="A short British English test.",
                    voice="bf_emma",
                    speed=1.0,
                    pause_ms=120,
                    output_path=output,
                    overwrite=False,
                    backend="onnx",
                )

        self.assertEqual(metadata["engine"]["backend"], "onnx")
        self.assertEqual(
            metadata["engine"]["providers"], ["CPUExecutionProvider"]
        )
        self.assertEqual(metadata["model"]["quantization"], "INT8 ONNX")
        self.assertEqual(model.call["lang"], "en-gb")

    def test_npu_provider_is_strict_and_does_not_add_cpu_fallback(self) -> None:
        class Options:
            def __init__(self):
                self.entries = {}
                self.intra_op_num_threads = 0

            def add_session_config_entry(self, name, value):
                self.entries[name] = value

        class Session:
            def get_providers(self):
                return ["OpenVINOExecutionProvider"]

        class Ort:
            SessionOptions = Options
            InferenceSession = mock.Mock(return_value=Session())

            @staticmethod
            def get_available_providers():
                return ["OpenVINOExecutionProvider", "CPUExecutionProvider"]

        _, providers = kokoro_audio._create_onnx_session(
            Ort, Path("model.onnx"), "openvino-npu"
        )
        self.assertEqual(providers, ["OpenVINOExecutionProvider"])
        supplied = Ort.InferenceSession.call_args.kwargs["providers"]
        self.assertEqual(
            supplied,
            [("OpenVINOExecutionProvider", {"device_type": "NPU"})],
        )
        options = Ort.InferenceSession.call_args.kwargs["sess_options"]
        self.assertEqual(
            options.entries["session.disable_cpu_ep_fallback"], "1"
        )

    def test_output_lock_rejects_concurrent_synthesis(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / "speech.wav"
            with mock.patch.object(kokoro_audio, "cache_dir", return_value=root):
                with kokoro_audio._output_lock(output):
                    with self.assertRaisesRegex(
                        kokoro_audio.AudioGeneratorError, "Another synthesis"
                    ):
                        with kokoro_audio._output_lock(output):
                            self.fail("concurrent lock should not be acquired")
                with kokoro_audio._output_lock(output):
                    pass
            self.assertEqual(len(list((root / "locks").glob("*.lock"))), 1)

    def test_text_file_with_invalid_utf8_returns_tool_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "invalid.txt"
            source.write_bytes(b"\xff\xfe\x00")
            args = kokoro_audio.build_parser().parse_args(
                ["generate", "--text-file", str(source)]
            )
            with self.assertRaisesRegex(
                kokoro_audio.AudioGeneratorError, "Could not read UTF-8"
            ):
                kokoro_audio.read_input_text(args)

    def test_publish_failure_restores_overwritten_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / "speech.wav"
            metadata = kokoro_audio.sidecar_path(output)
            staged_wav = root / "staged.wav"
            staged_metadata = root / "staged.json"
            output.write_bytes(b"old wav")
            metadata.write_text("old metadata", encoding="utf-8")
            staged_wav.write_bytes(b"new wav")
            staged_metadata.write_text("new metadata", encoding="utf-8")
            real_replace = kokoro_audio.os.replace

            def fail_second_publish(source, destination):
                if Path(source) == staged_metadata:
                    raise OSError("simulated failure")
                return real_replace(source, destination)

            with mock.patch.object(
                kokoro_audio.os, "replace", side_effect=fail_second_publish
            ):
                with self.assertRaisesRegex(
                    kokoro_audio.AudioGeneratorError, "Could not publish"
                ):
                    kokoro_audio._publish_outputs(
                        staged_wav,
                        output,
                        staged_metadata,
                        metadata,
                        overwrite=True,
                    )

            self.assertEqual(output.read_bytes(), b"old wav")
            self.assertEqual(metadata.read_text(encoding="utf-8"), "old metadata")


if __name__ == "__main__":
    unittest.main()
