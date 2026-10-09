---
name: babblelabreel-audio
description: Generate English speech, narration, voiceovers, and WAV audio on Windows or macOS in basic or enhanced mode. Use whenever the user asks BabblelabReel to turn English text or a script into spoken audio, read text aloud, create a voice track, synthesize speech, or use Kokoro, even when they do not name text-to-speech explicitly. Basic is the default and uses Jenny through Edge TTS on Windows or Ava (Premium) with Samantha fallback on macOS; enhanced uses Kokoro. Produces deterministic artifacts with provenance metadata.
---

Resolve the bundle root two directories above this file. Read its `AGENTS.md` and shared artifact routing; run relative commands from that root. This is a bundled BabblelabReel child, not a dependency on the original Emma plugin.


# Audio Generator

Generate English speech on Windows or macOS and save it under the resolved
`USER_HOME/outputs/audio-generator/` directory.

## Modes

### Basic — default

- Windows uses `en-US-JennyNeural` through `edge-tts`.
- macOS prefers the exact installed `Ava (Premium)` system voice and falls back
  to `Samantha` only when Ava (Premium) is unavailable.
- Windows Edge TTS is online: the text is sent to Microsoft Edge's Read Aloud
  service. macOS `say` synthesis stays on the device.
- Basic accepts normal speed control and always publishes 24 kHz mono PCM WAV.

### Enhanced

- Apple Silicon uses pinned `mlx-community/Kokoro-82M-8bit` through MLX.
- Windows and Intel Mac use pinned `kokoro-v1.0.int8.onnx` through ONNX Runtime
  CPU.
- Enhanced defaults to Kokoro `af_heart`, normal speed, and 120 ms between
  generated segments. American voices start with `af_` or `am_`; British
  voices start with `bf_` or `bm_`.
- Enhanced synthesis stays local after pinned model assets download.

Support English only. Do not silently switch modes, voices, models, backends,
or accelerators. The only automatic voice substitution is Ava (Premium) to
Samantha on macOS basic mode.

MLX supports Python 3.10–3.12. ONNX supports Python 3.10–3.13. For exact
constraints, model evidence, and Windows accelerator status, read
`references/compatibility.md`.

## Workflow

Commands below use Windows' `py -3.12` launcher. On macOS, replace that launcher
with `python3`; always keep preflight, installation, and generation on the same
interpreter.

1. Run preflight before the first synthesis in a session. With no mode, it
   checks the default basic voice:

   ```bash
   py -3.12 tools/audio-generator/scripts/kokoro_audio.py preflight
   ```

2. If dependencies are missing, explain the reported blocker. Installing them
   requires the user's separate explicit permission:

   ```bash
   py -3.12 -m pip install -r tools/audio-generator/requirements-basic.txt
   ```

   Do not run this install merely because the user requested audio generation.

3. Use basic mode unless the user asks for enhanced, premium-quality local
   Kokoro, a Kokoro voice, or an explicit accelerator. To inspect both voice
   sets:

   ```bash
   py -3.12 tools/audio-generator/scripts/kokoro_audio.py voices
   ```

4. Generate a default basic voice:

   ```console
   py -3.12 tools/audio-generator/scripts/kokoro_audio.py generate --text "The exact English text to speak." --output "descriptive-name.wav"
   ```

   For long or quote-sensitive input, prefer a UTF-8 text file:

   ```console
   py -3.12 tools/audio-generator/scripts/kokoro_audio.py generate --text-file "script.txt" --speed 0.95 --output "release-narration.wav"
   ```

5. Generate enhanced Kokoro speech only with `--mode enhanced`:

   ```console
   py -3.12 tools/audio-generator/scripts/kokoro_audio.py generate --mode enhanced --text-file "script.txt" --voice bf_emma --output "enhanced-narration.wav"
   ```

   The automatic enhanced backend is MLX on native Apple Silicon and ONNX
   elsewhere. `auto` intentionally selects ONNX CPU on Windows. If enhanced
   preflight reports missing packages and the user approves installation, use:

   ```console
   py -3.12 -m pip install -r tools/audio-generator/requirements-enhanced.txt
   ```

6. Use another ONNX execution provider only when the user explicitly requests
   it and preflight reports that provider:

   ```console
   py -3.12 tools/audio-generator/scripts/kokoro_audio.py preflight --mode enhanced --backend onnx --accelerator directml
   ```

   Supported explicit targets are `directml`, `cuda`, `openvino-npu`, and
   `qnn-npu`. DirectML and CUDA may partition unsupported graph operations to
   CPU. NPU targets are experimental and strict: they fail rather than silently
   running on CPU. Never describe an available provider as compatible until
   preflight and real synthesis succeed on that machine.

7. Treat the JSON printed by the command as authoritative. Do not claim
   completion when `success` is false.

The wrapper records the mode, selected voice, fallback use, online/local
processing, engine, duration, and output hash. Enhanced mode also records and
verifies pinned model assets. The `.wav.json` sidecar never retains source text.

## Output rules

- `--output` is relative to `USER_HOME/outputs/audio-generator/`; absolute
  paths are accepted only when they remain inside that directory.
- Use a new descriptive `.wav` filename. Existing named outputs are protected
  unless the user explicitly requests replacement and `--overwrite` is passed.
- When `--output` is omitted, the deterministic input fingerprint becomes the
  filename and a verified prior result is reused.
- Never put source text, credentials, private URLs, or identity data in the
  metadata sidecar.

## Completion

A run is complete only when the WAV and its `.wav.json` sidecar exist, the WAV
is non-empty, and the command returns `success: true`. Report the mode, selected
voice, fallback status when relevant, speed, duration, sample rate, engine or
model, and saved path.
