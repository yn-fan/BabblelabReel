# Kokoro runtime compatibility

## Basic mode

Basic is Audio Generator's default and does not load Kokoro.

- Windows uses `edge-tts==7.2.8` with `en-US-JennyNeural`. The package connects
  to Microsoft Edge's online Read Aloud service and returns 24 kHz, 48 kbps
  mono MP3. Audio Generator converts it to 24 kHz mono 16-bit PCM WAV with the
  FFmpeg binary bundled by `imageio-ffmpeg==0.6.0`.
- macOS uses the native `say` command with the exact installed voice
  `Ava (Premium)`. When that voice is absent, it selects `Samantha`. The native
  AIFF output is converted to PCM WAV with macOS `afconvert`.

The Windows path sends input text to Microsoft's service; the macOS path is
local. Neither path stores source text in the sidecar. The Edge TTS protocol
and voice availability can change independently of this tool, so a failed
service call is surfaced rather than replaced with another online provider.

References:

- <https://pypi.org/project/edge-tts/7.2.8/>
- <https://github.com/rany2/edge-tts>
- <https://pypi.org/project/imageio-ffmpeg/0.6.0/>

## Supported runtime

Enhanced mode selects a local Kokoro backend by platform:

- Apple Silicon macOS: MLX with Python 3.10–3.12.
- Windows, Intel macOS, and Linux: ONNX Runtime CPU with Python 3.10–3.13.

Preflight runs before importing either native runtime so unsupported or
incomplete hosts receive a clear error instead of a native-module failure.
Basic and enhanced dependencies are isolated in `requirements-basic.txt` and
`requirements-enhanced.txt`; `requirements.txt` installs both when a complete
setup is wanted. Platform markers prevent Windows from trying to install MLX.

## Why Python 3.9 is not supported

Python 3.9 was not an BabblelabReel-authored restriction. It comes from the current
upstream inference stack:

- `mlx-audio` declares `requires-python = ">=3.10"` in
  <https://github.com/Blaizzy/mlx-audio/blob/main/pyproject.toml>.
- Apple MLX currently publishes `Requires-Python: >=3.10` on
  <https://pypi.org/project/mlx/>.
- `misaki` 0.9.4 allows Python 3.8–3.12, so it is not the lower-bound blocker,
  but its `<3.13` upper bound makes Python 3.12 the highest supported version
  for this pinned tool.

The adjacent Kokoro runtimes do not provide a supported Python 3.9 path:

- Official `kokoro` 0.9.4 declares `>=3.10,<3.14`.
- `kokoro-onnx` 0.6.1 declares `>=3.10,<3.14`, so the ONNX backend widens the
  upper end to Python 3.13.
- `kokoro-mlx` 0.1.2 declares `>=3.10,<3.13`.

Changing only BabblelabReel's version check would not widen compatibility: package
installation would still be rejected, current MLX wheels would be unavailable,
and portions of the current stack use Python 3.10-era typing syntax. A bespoke
fork could pin and backport old MLX and audio packages, but that would freeze
security and compatibility fixes around an end-of-life Python release. It is
therefore not a reliable default and is intentionally unsupported.

## Apple Silicon default

Default model: `mlx-community/Kokoro-82M-8bit`

- Revision: `7e173a214392b1e0cb397e71c9745cbd14c06063`
- Weight: `kokoro-v1_0.safetensors`
- Weight SHA-256:
  `fb2b8f22b906f2e70e7dae4c337457784b079fb44142d8f4da93d8a9ace905ed`
- Quantization: 8-bit, group size 64
- Model license: Apache-2.0
- Runtime: Apple MLX through `mlx-audio`

The pinned model card identifies English as its language and records the MLX
conversion. The wrapper downloads only the config, model weight, and selected
English voice from that exact revision.

## Windows and Intel Mac default

Default runtime: `kokoro-onnx==0.6.1` with ONNX Runtime CPU.

Default model assets come from the `model-files-v1.1` release of
`thewh1teagle/kokoro-onnx`:

- Model: `kokoro-v1.0.int8.onnx`
- Model size: 114,119,327 bytes
- Model SHA-256:
  `ae315a79b623f244700e4afb9246c46a26066782e049ba174bf3ba433970ee9c`
- Voice archive: `voices-v1.0.bin`
- Voice archive SHA-256:
  `bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d`
- Quantization: INT8
- Model license: Apache-2.0
- Wrapper license: MIT

The release reports spectral correlation of 0.916 against its FP32 export.
The matching FP16 export reports 0.999 but is about 164 MB and is not the
broadly optimized CPU default. The INT8 export is the reliable Windows
baseline because it is packaged with the wrapper's current graph contract,
embedded vocabulary, duration output, and matching 54-voice archive. The tool
verifies both downloaded assets before loading them.

The MLX backend also verifies the selected voice safetensors file against the
hash published by the pinned model revision. All 28 exposed English voice
hashes are recorded in the wrapper.

Two smaller quantized repositories were considered but not selected:

- `onnx-community/Kokoro-82M-v1.0-ONNX` has valid 86 MB mixed-precision and
  92 MB INT8 files, but its per-voice raw `.bin` layout targets Transformers.js
  rather than the `kokoro-onnx` voice archive contract.
- `NeuML/kokoro-int8-onnx` has a valid 92 MB model but uses txtai's JSON voice
  format, which would introduce a second wrapper contract.

## Windows GPU and NPU status

ONNX Runtime execution providers accelerate graphs; they do not make a model
"Windows optimized" by name. CPU remains automatic because it is present and
portable. Other providers require an explicit `--accelerator` selection:

- `directml`: broad DirectX 12 GPU support. ONNX Runtime now describes DirectML
  as sustained engineering and recommends Windows ML for new Windows
  deployments. Unsupported graph nodes may remain on CPU.
- `cuda`: NVIDIA GPU support through ONNX Runtime GPU. Unsupported graph nodes
  may remain on CPU.
- `openvino-npu`: Intel Core Ultra NPU through OpenVINO. The provider supports
  an explicit NPU device, but this Kokoro graph has not been validated on the
  required hardware.
- `qnn-npu`: Qualcomm Snapdragon NPU through QNN on Windows ARM64. ONNX Runtime
  documents stricter package, Python, quantization, and graph requirements;
  this Kokoro export has not been validated against them.

NPU targets disable ONNX Runtime's CPU execution-provider fallback. This avoids
reporting "NPU audio" when unsupported operators actually ran on CPU. A
provider being installed is only a readiness signal; preflight plus successful
real synthesis on that device is required before calling it compatible.

No trustworthy AMD Ryzen AI default was found. In particular,
`magicunicorn/kokoro-npu-quantized` advertises 121.9 MB and 169.8 MB models, but
the pinned repository revision contains 134-byte Git LFS pointer objects whose
declared payload sizes are also 134 bytes. Its sample depends on an
unpublished `unicorn_execution_engine` contract. Those assets are not usable
models and are intentionally excluded.

Authoritative references:

- <https://pypi.org/project/kokoro-onnx/0.6.1/>
- <https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.1>
- <https://onnxruntime.ai/docs/execution-providers/DirectML-ExecutionProvider.html>
- <https://onnxruntime.ai/docs/execution-providers/OpenVINO-ExecutionProvider.html>
- <https://onnxruntime.ai/docs/execution-providers/QNN-ExecutionProvider.html>
