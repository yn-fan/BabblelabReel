from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "kokoro_audio.py"
RUN_INTEGRATION = (
    os.environ.get("BABBLELABREEL_RUN_AUDIO_INTEGRATION") == "1"
    and sys.version_info >= (3, 10)
    and (
        (
            platform.system() == "Darwin"
            and platform.machine().lower() in {"arm64", "aarch64"}
            and sys.version_info < (3, 13)
        )
        or (
            platform.system() in {"Windows", "Darwin", "Linux"}
            and not (
                platform.system() == "Darwin"
                and platform.machine().lower() in {"arm64", "aarch64"}
            )
            and sys.version_info < (3, 14)
        )
    )
)


@unittest.skipUnless(
    RUN_INTEGRATION,
    "Set BABBLELABREEL_RUN_AUDIO_INTEGRATION=1 on a supported MLX or ONNX host.",
)
class KokoroAudioIntegrationTests(unittest.TestCase):
    def test_pinned_model_generates_valid_wav_and_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            user_home = Path(temp) / "BabblelabReel"
            user_home.mkdir()
            environment = os.environ.copy()
            environment["BABBLELABREEL_USER_HOME"] = str(user_home)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "generate",
                    "--mode",
                    "enhanced",
                    "--text",
                    "Welcome to the BabblelabReel Kokoro audio integration test.",
                    "--output",
                    "integration.wav",
                ],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=environment,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
            payload = json.loads(completed.stdout)
            self.assertTrue(payload["success"])
            expected_backend = (
                "mlx"
                if platform.system() == "Darwin"
                and platform.machine().lower() in {"arm64", "aarch64"}
                else "onnx"
            )
            self.assertEqual(payload["engine"]["backend"], expected_backend)

            output = user_home / "outputs" / "audio-generator" / "integration.wav"
            sidecar = output.with_suffix(".wav.json")
            self.assertTrue(output.is_file())
            self.assertTrue(sidecar.is_file())
            with wave.open(str(output), "rb") as wav:
                self.assertEqual(wav.getnchannels(), 1)
                self.assertEqual(wav.getframerate(), 24000)
                self.assertGreater(wav.getnframes(), 0)


if __name__ == "__main__":
    unittest.main()
