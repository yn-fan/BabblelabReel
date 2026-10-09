#!/usr/bin/env python3
"""Generate deterministic English Kokoro speech with MLX or ONNX Runtime."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import urllib.error
import urllib.request
import wave
from contextlib import contextmanager, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parents[3]
TOOLS_SCRIPTS = REPO_ROOT / "tools" / "scripts"
if str(TOOLS_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(TOOLS_SCRIPTS))

from user_paths import cache_dir, output_dir  # noqa: E402


TOOL_NAME = "audio-generator"
DEFAULT_MODE = "basic"
BASIC_EDGE_VOICE = "en-US-JennyNeural"
BASIC_EDGE_VOICE_LABEL = "Jenny"
BASIC_MAC_VOICE = "Ava (Premium)"
BASIC_MAC_FALLBACK_VOICE = "Samantha"
BASIC_PACKAGE_VERSIONS = {
    "edge-tts": "7.2.8",
    "imageio-ffmpeg": "0.6.0",
}
MLX_MODEL = "mlx-community/Kokoro-82M-8bit"
MLX_MODEL_REVISION = "7e173a214392b1e0cb397e71c9745cbd14c06063"
MLX_MODEL_WEIGHT = "kokoro-v1_0.safetensors"
MLX_MODEL_WEIGHT_SHA256 = (
    "fb2b8f22b906f2e70e7dae4c337457784b079fb44142d8f4da93d8a9ace905ed"
)
MLX_VOICE_SHA256 = {
    "af_alloy": "7997b001760bbcb624594dc0baf1ac9a2c7aacfb45c158dbf63daf8c245182bc",
    "af_aoede": "fce9bf78661a0444ca333f5687183d850bfb73b71c67f2678dd5ddb3ac3a96d2",
    "af_bella": "a18024b9332f5ff217c7f604cbe94449a3ca51c3b8d85500e31cd3cbdc4ef6ce",
    "af_heart": "4e40b08984cd84a86b4d07960939bd85bb6b3747dd747b7de48dca3aaeab37ca",
    "af_jessica": "93930bbe363cf01040de0aa1cf08b29b4b624ed7a70a36f8cd71ea855c097003",
    "af_kore": "71fb664533d3bcbed8cf96eafe9280dfa7c244302ded62501a0b42d18377ed1b",
    "af_nicole": "769ee38efeb131196eaab5ed43592b315bba829881d4aee7411872efa6cf05c6",
    "af_nova": "6bf350f6649bde64c8cc79e17437fdd10dc7edf2b962702942e01a2d7af403bd",
    "af_river": "4068d50ad247f47b8938ed88fba45db8d5c1b44dbae552db523a919d0a953019",
    "af_sarah": "2bc36ea1b08925188da3c81e30858952bec28fbb61512bdd573312e5a62dd3f9",
    "af_sky": "7c8fafbc903f96ec8779adb0757ad36038bad5b66910d122260f90751b3ff007",
    "am_adam": "1dff8c742132e77fcee65886ede701eeed36de8d36a055f07c1bd2598c9228ce",
    "am_echo": "73f4473b2b74214efe97e0b4f09970015fea1ce7513ac6fc5e69631315a99cd4",
    "am_eric": "91bcd1a2c8b10ef25ae222ba99cace6beef3d7fca0c0047f22b5a2bb21c9d034",
    "am_fenrir": "843c5a6abcd2f25f242e1bf3b008c3c8fcc8f6d99f081767275e1c852eb7beee",
    "am_liam": "dd0b4852ec6aacb9d6a90625e8f6053a11ef835322e75b587d929ca8ea5e136d",
    "am_michael": "19a8661430456e2bbf0a68b52fa9b49678bb0fb7418619f868df77921f5aa43c",
    "am_onyx": "0d6ee75af61cf3bdfa66732394008f1786e09a247b4c6aa8b9661fb06fa7ba40",
    "am_puck": "a6be98717a1332b631c689c25b69e6e0e48693453002d160d0690a80cf989d47",
    "am_santa": "207b91319c811192393b0b38fe0815174420f49dd46d8e23e172bf3686398edc",
    "bf_alice": "23cc78a409207641fda6f0e5a8e5f3b3b2ea5d948471b85cd18c8740a4ccfaa7",
    "bf_emma": "ed92055e1ed96f2a0b4a52b76956dcfd76627bd548c33801743a62c0817dec01",
    "bf_isabella": "3a3f580cd78969b9bca33d85ebfa2d43c7bad9066f938108969d57f2856b9f08",
    "bf_lily": "4cfbc152f58d473aa80b666e48178ecfa6ca793197e1ffd92cfa2fb4b18956a9",
    "bm_daniel": "35b044b866eb8aa3f91ec376fdf457fea0ad0d3ebe8484f3dd32e1f5355c582a",
    "bm_fable": "146cd42da875a06d45b9808f5dbdc1b0485283a590187aaeffda64239f0faa54",
    "bm_george": "a3a6682cde622e7aee35597b91947fa018f78be101a97587a100effe227e5a21",
    "bm_lewis": "a3a1a67f5f1debde58bf7e972ff47e0ae575696f87f2d51f5c581cc48dc68f22",
}
ONNX_MODEL = "thewh1teagle/kokoro-onnx"
ONNX_MODEL_REVISION = "model-files-v1.1"
ONNX_MODEL_WEIGHT = "kokoro-v1.0.int8.onnx"
ONNX_MODEL_WEIGHT_SHA256 = (
    "ae315a79b623f244700e4afb9246c46a26066782e049ba174bf3ba433970ee9c"
)
ONNX_VOICES = "voices-v1.0.bin"
ONNX_VOICES_SHA256 = (
    "bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d"
)
ONNX_RELEASE_ROOT = (
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/"
    f"{ONNX_MODEL_REVISION}"
)
# Retain the original names for callers that inspect the Apple default.
DEFAULT_MODEL = MLX_MODEL
DEFAULT_MODEL_REVISION = MLX_MODEL_REVISION
MODEL_WEIGHT = MLX_MODEL_WEIGHT
MODEL_WEIGHT_SHA256 = MLX_MODEL_WEIGHT_SHA256
DEFAULT_VOICE = "af_heart"
DEFAULT_SPEED = 1.0
DEFAULT_PAUSE_MS = 120
SAMPLE_RATE = 24000
MAX_SEGMENT_CHARS = 400
MAX_TEXT_CHARS = 100_000
SUPPORTED_VOICES = (
    "af_alloy",
    "af_aoede",
    "af_bella",
    "af_heart",
    "af_jessica",
    "af_kore",
    "af_nicole",
    "af_nova",
    "af_river",
    "af_sarah",
    "af_sky",
    "am_adam",
    "am_echo",
    "am_eric",
    "am_fenrir",
    "am_liam",
    "am_michael",
    "am_onyx",
    "am_puck",
    "am_santa",
    "bf_alice",
    "bf_emma",
    "bf_isabella",
    "bf_lily",
    "bm_daniel",
    "bm_fable",
    "bm_george",
    "bm_lewis",
)
MLX_PACKAGE_VERSIONS = {
    "mlx-audio": "0.5.0",
    "misaki": "0.9.4",
}
ONNX_PACKAGE_VERSIONS = {
    "kokoro-onnx": "0.6.1",
}
PACKAGE_VERSIONS = MLX_PACKAGE_VERSIONS
BACKEND_MODULES = {
    "mlx": ("mlx", "mlx_audio", "huggingface_hub", "misaki", "numpy"),
    "onnx": ("kokoro_onnx", "onnxruntime", "numpy"),
}
BASIC_WINDOWS_MODULES = ("edge_tts", "imageio_ffmpeg")
ACCELERATOR_PROVIDERS = {
    "cpu": "CPUExecutionProvider",
    "directml": "DmlExecutionProvider",
    "cuda": "CUDAExecutionProvider",
    "openvino-npu": "OpenVINOExecutionProvider",
    "qnn-npu": "QNNExecutionProvider",
}
NPU_ACCELERATORS = frozenset({"openvino-npu", "qnn-npu"})
ONNX_RUNTIME_DISTRIBUTIONS = {
    "cpu": "onnxruntime",
    "directml": "onnxruntime-directml",
    "cuda": "onnxruntime-gpu",
    "openvino-npu": "onnxruntime-openvino",
    "qnn-npu": "onnxruntime-qnn",
}


class AudioGeneratorError(RuntimeError):
    """Expected validation, runtime, model, or output failure."""


def emit(payload: Dict[str, Any], exit_code: int = 0) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return exit_code


def fail(message: str, **details: Any) -> int:
    return emit({"success": False, "error": message, **details}, 1)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        raise AudioGeneratorError("English input text is empty.")
    if len(normalized) > MAX_TEXT_CHARS:
        raise AudioGeneratorError(
            f"Input has {len(normalized)} characters; the limit is {MAX_TEXT_CHARS}."
        )
    if not any(character.isalnum() for character in normalized):
        raise AudioGeneratorError("Input must contain at least one letter or number.")

    non_latin_letters = sorted(
        {
            character
            for character in normalized
            if character.isalpha()
            and "LATIN" not in unicodedata.name(character, "")
        }
    )
    if non_latin_letters:
        preview = "".join(non_latin_letters[:12])
        raise AudioGeneratorError(
            "Audio Generator is English-only; unsupported non-Latin letters were "
            f"found: {preview!r}."
        )
    return normalized


def validate_voice(voice: str) -> str:
    if voice not in SUPPORTED_VOICES:
        raise AudioGeneratorError(
            f"Unsupported voice {voice!r}. Run the 'voices' command for English choices."
        )
    return voice


def _list_macos_voices() -> List[str]:
    say = shutil.which("say")
    if not say:
        raise AudioGeneratorError("macOS 'say' command is unavailable.")
    try:
        completed = subprocess.run(
            [say, "-v", "?"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise AudioGeneratorError(f"Could not list macOS voices: {error}") from error
    if completed.returncode != 0:
        detail = completed.stderr.strip() or "unknown error"
        raise AudioGeneratorError(f"Could not list macOS voices: {detail}")

    voices: List[str] = []
    for line in completed.stdout.splitlines():
        match = re.match(r"^(.+?)\s+[a-z]{2}_[A-Z]{2}\s+#", line)
        if match:
            voices.append(match.group(1).strip())
    return voices


def resolve_basic_voice(
    requested: Optional[str] = None,
    *,
    system: Optional[str] = None,
    macos_voices: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    system = system or platform.system()
    normalized = requested.strip().lower() if requested else None
    if system == "Windows":
        accepted = {
            None,
            "jenny",
            BASIC_EDGE_VOICE.lower(),
            BASIC_EDGE_VOICE_LABEL.lower(),
        }
        if normalized not in accepted:
            raise AudioGeneratorError(
                "Windows basic mode supports Jenny "
                f"({BASIC_EDGE_VOICE}); use enhanced mode for Kokoro voices."
            )
        return {
            "id": BASIC_EDGE_VOICE,
            "label": BASIC_EDGE_VOICE_LABEL,
            "engine": "edge-tts",
            "fallback": False,
        }

    if system == "Darwin":
        accepted = {
            None,
            "ava",
            "ava premium",
            BASIC_MAC_VOICE.lower(),
            "samantha",
            BASIC_MAC_FALLBACK_VOICE.lower(),
        }
        if normalized not in accepted:
            raise AudioGeneratorError(
                "macOS basic mode supports Ava (Premium) with Samantha fallback; "
                "use enhanced mode for Kokoro voices."
            )
        available = set(macos_voices if macos_voices is not None else _list_macos_voices())
        if normalized == "samantha":
            if BASIC_MAC_FALLBACK_VOICE not in available:
                raise AudioGeneratorError(
                    "The macOS Samantha voice is not installed."
                )
            selected = BASIC_MAC_FALLBACK_VOICE
            fallback = False
        elif BASIC_MAC_VOICE in available:
            selected = BASIC_MAC_VOICE
            fallback = False
        elif BASIC_MAC_FALLBACK_VOICE in available:
            selected = BASIC_MAC_FALLBACK_VOICE
            fallback = True
        else:
            raise AudioGeneratorError(
                "Neither Ava (Premium) nor Samantha is installed in macOS voices."
            )
        return {
            "id": selected,
            "label": selected,
            "engine": "macos-say",
            "fallback": fallback,
        }

    raise AudioGeneratorError(
        f"Basic mode supports Windows and macOS; found {system}."
    )


def validate_speed(speed: float) -> float:
    if not 0.5 <= speed <= 2.0:
        raise AudioGeneratorError("Speed must be between 0.5 and 2.0.")
    return speed


def validate_pause_ms(pause_ms: int) -> int:
    if not 0 <= pause_ms <= 2_000:
        raise AudioGeneratorError("Segment pause must be between 0 and 2000 ms.")
    return pause_ms


def _hard_split(piece: str, max_chars: int) -> List[str]:
    words = piece.split()
    if not words:
        return []

    chunks: List[str] = []
    current = ""
    for word in words:
        if len(word) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(
                word[index : index + max_chars]
                for index in range(0, len(word), max_chars)
            )
            continue
        candidate = word if not current else f"{current} {word}"
        if len(candidate) <= max_chars:
            current = candidate
        else:
            chunks.append(current)
            current = word
    if current:
        chunks.append(current)
    return chunks


def _bounded_pieces(text: str, max_chars: int) -> List[str]:
    sentence_parts = re.split(r"(?<=[.!?…])\s+", text)
    pieces: List[str] = []
    for sentence in sentence_parts:
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(sentence) <= max_chars:
            pieces.append(sentence)
            continue

        clauses = re.split(r"(?<=[,;:—])\s+", sentence)
        for clause in clauses:
            clause = clause.strip()
            if not clause:
                continue
            if len(clause) <= max_chars:
                pieces.append(clause)
            else:
                pieces.extend(_hard_split(clause, max_chars))
    return pieces


def segment_text(text: str, max_chars: int = MAX_SEGMENT_CHARS) -> List[str]:
    if max_chars < 32:
        raise AudioGeneratorError("Segment size must be at least 32 characters.")

    pieces: List[str] = []
    for paragraph in re.split(r"\n+", text):
        paragraph = re.sub(r"[ \t]+", " ", paragraph).strip()
        if paragraph:
            pieces.extend(_bounded_pieces(paragraph, max_chars))

    segments: List[str] = []
    current = ""
    for piece in pieces:
        candidate = piece if not current else f"{current} {piece}"
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                segments.append(current)
            current = piece
    if current:
        segments.append(current)
    return segments


def select_backend(
    requested: str = "auto",
    *,
    system: Optional[str] = None,
    machine: Optional[str] = None,
) -> str:
    if requested not in {"auto", "mlx", "onnx"}:
        raise AudioGeneratorError(f"Unsupported backend {requested!r}.")
    system = system or platform.system()
    machine = (machine or platform.machine()).lower()
    if requested == "auto":
        if system == "Darwin" and machine in {"arm64", "aarch64"}:
            return "mlx"
        if system in {"Windows", "Darwin", "Linux"}:
            return "onnx"
        raise AudioGeneratorError(
            f"No Kokoro backend is supported on {system} {machine or 'unknown'}."
        )
    if requested == "mlx" and (
        system != "Darwin" or machine not in {"arm64", "aarch64"}
    ):
        raise AudioGeneratorError(
            f"The MLX backend requires native Apple Silicon macOS; found {system} "
            f"{machine or 'unknown'}."
        )
    if requested == "onnx" and system not in {"Windows", "Darwin", "Linux"}:
        raise AudioGeneratorError(
            f"The ONNX backend is not supported on {system} {machine or 'unknown'}."
        )
    return requested


def select_accelerator(backend: str, requested: str = "auto") -> str:
    if backend == "mlx":
        if requested in {"auto", "mlx"}:
            return "mlx"
        raise AudioGeneratorError(
            "The Apple MLX backend selects Apple Silicon automatically and does "
            "not accept an ONNX accelerator."
        )
    if requested not in {"auto", *ACCELERATOR_PROVIDERS}:
        raise AudioGeneratorError(f"Unsupported accelerator {requested!r}.")
    return "cpu" if requested == "auto" else requested


def model_descriptor(backend: str) -> Dict[str, Any]:
    if backend == "mlx":
        return {
            "id": MLX_MODEL,
            "revision": MLX_MODEL_REVISION,
            "quantization": "8-bit MLX",
            "weight": MLX_MODEL_WEIGHT,
            "weightSha256": MLX_MODEL_WEIGHT_SHA256,
        }
    return {
        "id": ONNX_MODEL,
        "revision": ONNX_MODEL_REVISION,
        "quantization": "INT8 ONNX",
        "weight": ONNX_MODEL_WEIGHT,
        "weightSha256": ONNX_MODEL_WEIGHT_SHA256,
        "voices": ONNX_VOICES,
        "voicesSha256": ONNX_VOICES_SHA256,
    }


def input_fingerprint(
    text: str,
    voice: str,
    speed: float,
    pause_ms: int,
    backend: str = "auto",
    accelerator: str = "auto",
) -> str:
    resolved_backend = select_backend(backend)
    resolved_accelerator = select_accelerator(resolved_backend, accelerator)
    model = model_descriptor(resolved_backend)
    payload = {
        "mode": "enhanced",
        "accelerator": resolved_accelerator,
        "backend": resolved_backend,
        "model": model["id"],
        "revision": model["revision"],
        "pauseMs": pause_ms,
        "speed": speed,
        "text": text,
        "voice": voice,
    }
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def basic_input_fingerprint(
    text: str,
    voice: Dict[str, Any],
    speed: float,
) -> str:
    payload = {
        "mode": "basic",
        "engine": voice["engine"],
        "speed": speed,
        "text": text,
        "voice": voice["id"],
    }
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def resolve_output_path(value: Optional[str], fingerprint: str) -> Path:
    root = output_dir(REPO_ROOT, TOOL_NAME).expanduser().resolve()
    raw = Path(value) if value else Path(f"audio-{fingerprint[:16]}.wav")
    candidate = raw.expanduser().resolve() if raw.is_absolute() else (root / raw).resolve()
    if candidate.suffix.lower() != ".wav":
        raise AudioGeneratorError("Output filename must use the .wav extension.")
    if not candidate.is_relative_to(root):
        raise AudioGeneratorError(f"Output must stay inside {root}.")
    return candidate


def sidecar_path(output_path: Path) -> Path:
    return output_path.with_suffix(f"{output_path.suffix}.json")


def load_cached_result(output_path: Path, fingerprint: str) -> Optional[Dict[str, Any]]:
    metadata_path = sidecar_path(output_path)
    if not output_path.is_file() or output_path.stat().st_size <= 44:
        return None
    if not metadata_path.is_file():
        return None
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(metadata, dict):
        return None
    input_metadata = metadata.get("input")
    output_metadata = metadata.get("output")
    if not isinstance(input_metadata, dict) or not isinstance(output_metadata, dict):
        return None
    if input_metadata.get("fingerprint") != fingerprint:
        return None
    if output_metadata.get("sha256") != sha256_file(output_path):
        return None
    metadata["success"] = True
    metadata["cached"] = True
    return metadata


def _installed_version(distribution: str) -> Optional[str]:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return None


def _numeric_version(value: str) -> Tuple[int, ...]:
    match = re.match(r"^(\d+(?:\.\d+)*)", value)
    if not match:
        return ()
    return tuple(int(part) for part in match.group(1).split("."))


def _available_onnx_providers() -> List[str]:
    try:
        import onnxruntime as ort
    except ImportError:
        return []
    return list(ort.get_available_providers())


def _collect_enhanced_preflight(
    backend: str = "auto", accelerator: str = "auto"
) -> Dict[str, Any]:
    issues: List[str] = []
    python_version = tuple(sys.version_info[:3])
    system = platform.system()
    machine = platform.machine().lower()

    try:
        resolved_backend = select_backend(backend, system=system, machine=machine)
        resolved_accelerator = select_accelerator(resolved_backend, accelerator)
    except AudioGeneratorError as error:
        resolved_backend = backend
        resolved_accelerator = accelerator
        issues.append(str(error))

    max_python = (3, 13) if resolved_backend == "mlx" else (3, 14)
    if python_version < (3, 10) or python_version >= max_python:
        supported = "3.10-3.12" if resolved_backend == "mlx" else "3.10-3.13"
        issues.append(
            f"Python {supported} is required by the pinned {resolved_backend.upper()} "
            "stack; "
            f"found {'.'.join(str(part) for part in python_version)}."
        )

    missing = [
        module_name
        for module_name in BACKEND_MODULES.get(resolved_backend, ())
        if importlib.util.find_spec(module_name) is None
    ]
    if missing:
        issues.append(f"Missing Python modules: {', '.join(missing)}.")

    versions: Dict[str, Optional[str]] = {}
    expected_versions = (
        MLX_PACKAGE_VERSIONS
        if resolved_backend == "mlx"
        else ONNX_PACKAGE_VERSIONS
    )
    for distribution, expected in expected_versions.items():
        installed = _installed_version(distribution)
        versions[distribution] = installed
        if installed is None:
            issues.append(f"Could not verify installed {distribution} version.")
        elif installed != expected:
            issues.append(
                f"{distribution} {expected} is required; found {installed}."
            )
    if resolved_backend == "onnx":
        runtime_distribution = ONNX_RUNTIME_DISTRIBUTIONS.get(
            resolved_accelerator, "onnxruntime"
        )
        runtime_version = _installed_version(runtime_distribution)
        versions[runtime_distribution] = runtime_version
        if runtime_version is None:
            issues.append(
                f"Could not verify installed {runtime_distribution} version."
            )
        elif (
            resolved_accelerator == "cpu"
            and not (1, 20, 1)
            <= _numeric_version(runtime_version)
            < (1, 25)
        ):
            issues.append(
                "onnxruntime >=1.20.1,<1.25 is required; "
                f"found {runtime_version}."
            )

    available_providers: List[str] = []
    provider = ACCELERATOR_PROVIDERS.get(resolved_accelerator)
    if resolved_backend == "onnx" and "onnxruntime" not in missing:
        available_providers = _available_onnx_providers()
        if provider not in available_providers:
            issues.append(
                f"{resolved_accelerator} requires {provider}; available ONNX Runtime "
                f"providers: {available_providers or ['none']}."
            )

    return {
        "success": not issues,
        "mode": "enhanced",
        "backend": resolved_backend,
        "runtime": {
            "system": system,
            "machine": machine,
            "python": ".".join(str(part) for part in python_version),
        },
        "packages": versions,
        "model": (
            model_descriptor(resolved_backend)
            if resolved_backend in {"mlx", "onnx"}
            else None
        ),
        "accelerator": {
            "selected": resolved_accelerator,
            "provider": provider if resolved_backend == "onnx" else "MLX",
            "availableProviders": available_providers,
            "experimental": resolved_accelerator in NPU_ACCELERATORS,
        },
        "cacheRoot": str(cache_dir(REPO_ROOT, TOOL_NAME).expanduser().resolve()),
        "issues": issues,
        "installCommand": (
            f'"{sys.executable}" -m pip install -r '
            "tools/audio-generator/requirements-enhanced.txt"
            if issues and resolved_accelerator in {"mlx", "cpu"}
            else None
        ),
        "providerSetupRequired": (
            resolved_backend == "onnx"
            and resolved_accelerator not in {"cpu"}
            and bool(issues)
        ),
    }


def _collect_basic_preflight() -> Dict[str, Any]:
    issues: List[str] = []
    system = platform.system()
    python_version = tuple(sys.version_info[:3])
    packages: Dict[str, Optional[str]] = {}
    selected_voice: Optional[Dict[str, Any]] = None

    if python_version < (3, 10):
        issues.append(
            "Python 3.10 or newer is required by Audio Generator; found "
            f"{'.'.join(str(part) for part in python_version)}."
        )

    if system == "Windows":
        missing = [
            module
            for module in BASIC_WINDOWS_MODULES
            if importlib.util.find_spec(module) is None
        ]
        if missing:
            issues.append(f"Missing Python modules: {', '.join(missing)}.")
        for distribution, expected in BASIC_PACKAGE_VERSIONS.items():
            installed = _installed_version(distribution)
            packages[distribution] = installed
            if installed is None:
                issues.append(f"Could not verify installed {distribution} version.")
            elif installed != expected:
                issues.append(
                    f"{distribution} {expected} is required; found {installed}."
                )
        selected_voice = resolve_basic_voice(system=system)
    elif system == "Darwin":
        for command in ("say", "afconvert"):
            if shutil.which(command) is None:
                issues.append(f"Required macOS command is unavailable: {command}.")
        if not issues:
            try:
                selected_voice = resolve_basic_voice(system=system)
            except AudioGeneratorError as error:
                issues.append(str(error))
    else:
        issues.append(f"Basic mode supports Windows and macOS; found {system}.")

    return {
        "success": not issues,
        "mode": "basic",
        "runtime": {
            "system": system,
            "machine": platform.machine().lower(),
            "python": ".".join(str(part) for part in python_version),
        },
        "packages": packages,
        "voice": selected_voice,
        "online": system == "Windows",
        "issues": issues,
        "installCommand": (
            f'"{sys.executable}" -m pip install -r '
            "tools/audio-generator/requirements-basic.txt"
            if issues and system == "Windows"
            else None
        ),
    }


def collect_preflight(
    mode: str = DEFAULT_MODE,
    backend: str = "auto",
    accelerator: str = "auto",
) -> Dict[str, Any]:
    if mode == "basic":
        return _collect_basic_preflight()
    if mode == "enhanced":
        return _collect_enhanced_preflight(backend, accelerator)
    raise AudioGeneratorError(f"Unsupported audio mode {mode!r}.")


def require_runtime(backend: str, accelerator: str) -> None:
    preflight = _collect_enhanced_preflight(backend, accelerator)
    if not preflight["success"]:
        raise AudioGeneratorError(
            f"Kokoro {backend.upper()} preflight failed: "
            + " ".join(preflight["issues"])
        )


def _load_mlx_runtime() -> Tuple[Any, Any, Any, Tuple[Any, ...]]:
    try:
        import numpy as np
        from huggingface_hub import snapshot_download
        from huggingface_hub.errors import HfHubHTTPError, LocalEntryNotFoundError
        from mlx_audio.tts.utils import load
    except ImportError as error:
        raise AudioGeneratorError(
            "Kokoro MLX dependencies are unavailable. Run preflight for details."
        ) from error
    return (
        np,
        snapshot_download,
        load,
        (HfHubHTTPError, LocalEntryNotFoundError, OSError, RuntimeError),
    )


# Backward-compatible test hook for the original MLX implementation.
_load_runtime = _load_mlx_runtime


def _load_onnx_runtime() -> Tuple[Any, Any, Any]:
    try:
        import numpy as np
        import onnxruntime as ort
        from kokoro_onnx import Kokoro
    except ImportError as error:
        raise AudioGeneratorError(
            "Kokoro ONNX dependencies are unavailable. Run preflight for details."
        ) from error
    return np, ort, Kokoro


def _download_model(
    snapshot_download: Any,
    voice: str,
    cache_root: Path,
    download_errors: Tuple[Any, ...],
) -> Path:
    try:
        snapshot = snapshot_download(
            repo_id=DEFAULT_MODEL,
            revision=DEFAULT_MODEL_REVISION,
            allow_patterns=[
                "config.json",
                MODEL_WEIGHT,
                f"voices/{voice}.safetensors",
            ],
            cache_dir=str(cache_root / "huggingface" / "hub"),
        )
    except download_errors as error:
        raise AudioGeneratorError(f"Could not download the pinned Kokoro model: {error}") from error

    snapshot_path = Path(snapshot)
    weight_path = snapshot_path / MODEL_WEIGHT
    voice_path = snapshot_path / "voices" / f"{voice}.safetensors"
    if not weight_path.is_file() or not voice_path.is_file():
        raise AudioGeneratorError("The pinned model snapshot is incomplete.")
    actual_hash = sha256_file(weight_path)
    if actual_hash != MODEL_WEIGHT_SHA256:
        raise AudioGeneratorError(
            f"Model weight integrity check failed: expected {MODEL_WEIGHT_SHA256}, "
            f"found {actual_hash}."
        )
    actual_voice_hash = sha256_file(voice_path)
    expected_voice_hash = MLX_VOICE_SHA256[voice]
    if actual_voice_hash != expected_voice_hash:
        raise AudioGeneratorError(
            f"Voice weight integrity check failed for {voice}: expected "
            f"{expected_voice_hash}, found {actual_voice_hash}."
        )
    return snapshot_path


def _download_verified_asset(
    *,
    url: str,
    destination: Path,
    expected_sha256: str,
) -> Path:
    if destination.is_file() and sha256_file(destination) == expected_sha256:
        return destination

    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        file_handle, temporary_name = tempfile.mkstemp(
            prefix=f".{destination.name}-",
            suffix=".download",
            dir=destination.parent,
        )
        os.close(file_handle)
    except OSError as error:
        raise AudioGeneratorError(f"Could not stage model download: {error}") from error

    temporary = Path(temporary_name)
    try:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "BabblelabReel-Audio-Generator/1.0"},
        )
        with urllib.request.urlopen(request, timeout=300) as response:
            with temporary.open("wb") as target:
                shutil.copyfileobj(response, target, length=1024 * 1024)
        actual_sha256 = sha256_file(temporary)
        if actual_sha256 != expected_sha256:
            raise AudioGeneratorError(
                f"Downloaded asset integrity check failed for {destination.name}: "
                f"expected {expected_sha256}, found {actual_sha256}."
            )
        os.replace(temporary, destination)
        return destination
    except AudioGeneratorError:
        raise
    except (OSError, urllib.error.URLError) as error:
        raise AudioGeneratorError(
            f"Could not download the pinned Kokoro asset {destination.name}: {error}"
        ) from error
    finally:
        if temporary.exists():
            temporary.unlink()


def _download_onnx_assets(cache_root: Path) -> Tuple[Path, Path]:
    asset_root = cache_root / "onnx" / ONNX_MODEL_REVISION
    model_path = _download_verified_asset(
        url=f"{ONNX_RELEASE_ROOT}/{ONNX_MODEL_WEIGHT}",
        destination=asset_root / ONNX_MODEL_WEIGHT,
        expected_sha256=ONNX_MODEL_WEIGHT_SHA256,
    )
    voices_path = _download_verified_asset(
        url=f"{ONNX_RELEASE_ROOT}/{ONNX_VOICES}",
        destination=asset_root / ONNX_VOICES,
        expected_sha256=ONNX_VOICES_SHA256,
    )
    return model_path, voices_path


def _create_onnx_session(
    ort: Any,
    model_path: Path,
    accelerator: str,
) -> Tuple[Any, List[str]]:
    provider = ACCELERATOR_PROVIDERS[accelerator]
    available = list(ort.get_available_providers())
    if provider not in available:
        raise AudioGeneratorError(
            f"{accelerator} requires {provider}; available ONNX Runtime providers: "
            f"{available or ['none']}."
        )

    options = ort.SessionOptions()
    options.intra_op_num_threads = os.cpu_count() or 1
    providers: List[Any]
    if accelerator == "directml":
        options.enable_mem_pattern = False
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        providers = [provider, "CPUExecutionProvider"]
    elif accelerator == "cuda":
        providers = [provider, "CPUExecutionProvider"]
    elif accelerator == "openvino-npu":
        options.add_session_config_entry("session.disable_cpu_ep_fallback", "1")
        providers = [(provider, {"device_type": "NPU"})]
    elif accelerator == "qnn-npu":
        options.add_session_config_entry("session.disable_cpu_ep_fallback", "1")
        providers = [(provider, {"backend_type": "htp"})]
    else:
        providers = [provider]

    try:
        session = ort.InferenceSession(
            str(model_path),
            sess_options=options,
            providers=providers,
        )
    except (OSError, RuntimeError, ValueError) as error:
        qualifier = "experimental " if accelerator in NPU_ACCELERATORS else ""
        raise AudioGeneratorError(
            f"Could not initialize the {qualifier}{accelerator} ONNX provider: {error}"
        ) from error
    return session, list(session.get_providers())


def _pcm16(audio: Any, np: Any) -> bytes:
    samples = np.asarray(audio, dtype=np.float32).reshape(-1)
    if samples.size == 0:
        return b""
    samples = np.nan_to_num(samples, nan=0.0, posinf=1.0, neginf=-1.0)
    samples = np.clip(samples, -1.0, 1.0)
    return (samples * 32767.0).astype("<i2").tobytes()


def _stage_metadata(path: Path, metadata: Dict[str, Any]) -> Path:
    file_handle, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}-", suffix=".tmp", dir=path.parent
    )
    os.close(file_handle)
    temporary = Path(temporary_name)
    try:
        temporary.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as error:
        if temporary.exists():
            temporary.unlink()
        raise AudioGeneratorError(f"Could not stage output metadata: {error}") from error
    return temporary


def _backup_path(path: Path) -> Path:
    file_handle, backup_name = tempfile.mkstemp(
        prefix=f".{path.name}-", suffix=".bak", dir=path.parent
    )
    os.close(file_handle)
    backup = Path(backup_name)
    backup.unlink()
    return backup


def _publish_outputs(
    staged_wav: Path,
    output_path: Path,
    staged_metadata: Path,
    metadata_path: Path,
    overwrite: bool,
) -> None:
    destinations = (output_path, metadata_path)
    if not overwrite and any(path.exists() for path in destinations):
        raise AudioGeneratorError(
            f"Output appeared while synthesis was running: {output_path}."
        )

    backups: List[Tuple[Path, Path]] = []
    published: List[Path] = []
    try:
        if overwrite:
            for destination in destinations:
                if destination.exists():
                    backup = _backup_path(destination)
                    os.replace(destination, backup)
                    backups.append((backup, destination))
        os.replace(staged_wav, output_path)
        published.append(output_path)
        os.replace(staged_metadata, metadata_path)
        published.append(metadata_path)
    except OSError as error:
        rollback_errors: List[str] = []
        backed_up_destinations = {destination for _, destination in backups}
        for destination in published:
            if destination in backed_up_destinations or not destination.exists():
                continue
            try:
                destination.unlink()
            except OSError as rollback_error:
                rollback_errors.append(f"remove {destination}: {rollback_error}")
        for backup, destination in reversed(backups):
            if backup.exists():
                try:
                    os.replace(backup, destination)
                except OSError as rollback_error:
                    rollback_errors.append(
                        f"restore {backup} to {destination}: {rollback_error}"
                    )
        if rollback_errors:
            preserved = [str(backup) for backup, _ in backups if backup.exists()]
            detail = "; ".join(rollback_errors)
            raise AudioGeneratorError(
                "Could not publish WAV and metadata, and rollback was incomplete. "
                f"Preserved backups: {preserved}. Details: {detail}"
            ) from error
        raise AudioGeneratorError(f"Could not publish WAV and metadata: {error}") from error

    for backup, _ in backups:
        try:
            if backup.exists():
                backup.unlink()
        except OSError as error:
            raise AudioGeneratorError(
                f"Outputs were published, but the prior-output backup could not be removed: {backup}."
            ) from error


def _render_mlx_wav(
    temporary_path: Path,
    model: Any,
    np: Any,
    segments: Sequence[str],
    voice_path: Path,
    voice: str,
    speed: float,
    pause_ms: int,
) -> Tuple[int, int]:
    sample_count = 0
    generated_chunks = 0
    silence_samples = round(SAMPLE_RATE * pause_ms / 1000)
    silence_bytes = b"\x00\x00" * silence_samples

    try:
        with wave.open(str(temporary_path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(SAMPLE_RATE)
            for segment in segments:
                try:
                    results: Iterable[Any] = model.generate(
                        text=segment,
                        voice=str(voice_path),
                        speed=speed,
                        lang_code=voice[0],
                        split_pattern=None,
                    )
                    for result in results:
                        result_rate = int(getattr(result, "sample_rate", SAMPLE_RATE))
                        if result_rate != SAMPLE_RATE:
                            raise AudioGeneratorError(
                                f"Unexpected Kokoro sample rate {result_rate}; expected {SAMPLE_RATE}."
                            )
                        frames = _pcm16(result.audio, np)
                        if not frames:
                            continue
                        if generated_chunks:
                            wav.writeframes(silence_bytes)
                            sample_count += silence_samples
                        wav.writeframes(frames)
                        sample_count += len(frames) // 2
                        generated_chunks += 1
                except AudioGeneratorError:
                    raise
                except (AssertionError, OSError, RuntimeError, ValueError) as error:
                    raise AudioGeneratorError(f"Kokoro synthesis failed: {error}") from error
    except (OSError, wave.Error) as error:
        raise AudioGeneratorError(f"Could not write staged WAV: {error}") from error

    if generated_chunks == 0 or sample_count == 0:
        raise AudioGeneratorError("Kokoro returned no audio.")
    return sample_count, generated_chunks


def _render_onnx_wav(
    temporary_path: Path,
    model: Any,
    np: Any,
    segments: Sequence[str],
    voice: str,
    speed: float,
    pause_ms: int,
) -> Tuple[int, int]:
    sample_count = 0
    generated_chunks = 0
    silence_samples = round(SAMPLE_RATE * pause_ms / 1000)
    silence_bytes = b"\x00\x00" * silence_samples
    language = "en-us" if voice.startswith("a") else "en-gb"

    try:
        with wave.open(str(temporary_path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(SAMPLE_RATE)
            for segment in segments:
                try:
                    audio, result_rate = model.create(
                        segment,
                        voice=voice,
                        speed=speed,
                        lang=language,
                    )
                except (AssertionError, OSError, RuntimeError, ValueError) as error:
                    raise AudioGeneratorError(
                        f"Kokoro ONNX synthesis failed: {error}"
                    ) from error
                if int(result_rate) != SAMPLE_RATE:
                    raise AudioGeneratorError(
                        f"Unexpected Kokoro sample rate {result_rate}; "
                        f"expected {SAMPLE_RATE}."
                    )
                frames = _pcm16(audio, np)
                if not frames:
                    continue
                if generated_chunks:
                    wav.writeframes(silence_bytes)
                    sample_count += silence_samples
                wav.writeframes(frames)
                sample_count += len(frames) // 2
                generated_chunks += 1
    except AudioGeneratorError:
        raise
    except (OSError, wave.Error) as error:
        raise AudioGeneratorError(f"Could not write staged WAV: {error}") from error

    if generated_chunks == 0 or sample_count == 0:
        raise AudioGeneratorError("Kokoro returned no audio.")
    return sample_count, generated_chunks


def _run_audio_command(
    command: Sequence[str],
    *,
    label: str,
    timeout: int = 300,
) -> None:
    try:
        completed = subprocess.run(
            list(command),
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise AudioGeneratorError(f"{label} failed: {error}") from error
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "unknown error"
        raise AudioGeneratorError(f"{label} failed: {detail}")


def _validate_staged_wav(path: Path) -> int:
    try:
        with wave.open(str(path), "rb") as wav:
            if wav.getnchannels() != 1:
                raise AudioGeneratorError(
                    f"Unexpected channel count {wav.getnchannels()}; expected mono."
                )
            if wav.getframerate() != SAMPLE_RATE:
                raise AudioGeneratorError(
                    f"Unexpected sample rate {wav.getframerate()}; expected {SAMPLE_RATE}."
                )
            if wav.getsampwidth() != 2:
                raise AudioGeneratorError(
                    f"Unexpected sample width {wav.getsampwidth() * 8}; expected 16-bit."
                )
            sample_count = wav.getnframes()
    except AudioGeneratorError:
        raise
    except (OSError, wave.Error) as error:
        raise AudioGeneratorError(f"Generated WAV is invalid: {error}") from error
    if sample_count <= 0:
        raise AudioGeneratorError("Basic voice engine returned no audio.")
    return sample_count


def _load_edge_runtime() -> Tuple[Any, Any, Tuple[Any, ...]]:
    try:
        import aiohttp
        import edge_tts
        import imageio_ffmpeg
        from edge_tts.exceptions import (
            NoAudioReceived,
            UnexpectedResponse,
            WebSocketError,
        )
    except ImportError as error:
        raise AudioGeneratorError(
            "Basic Edge TTS dependencies are unavailable. Run preflight for details."
        ) from error
    errors = (
        aiohttp.ClientError,
        asyncio.TimeoutError,
        NoAudioReceived,
        UnexpectedResponse,
        WebSocketError,
        OSError,
        RuntimeError,
        ValueError,
    )
    return edge_tts, imageio_ffmpeg, errors


def _edge_rate(speed: float) -> str:
    return f"{round((speed - 1.0) * 100):+d}%"


def _render_edge_wav(
    temporary_path: Path,
    text: str,
    voice: str,
    speed: float,
) -> int:
    edge_tts, imageio_ffmpeg, runtime_errors = _load_edge_runtime()
    file_handle, mp3_name = tempfile.mkstemp(
        prefix=f".{temporary_path.stem}-",
        suffix=".mp3",
        dir=temporary_path.parent,
    )
    os.close(file_handle)
    mp3_path = Path(mp3_name)

    async def save_edge_audio() -> None:
        communicator = edge_tts.Communicate(
            text,
            voice=voice,
            rate=_edge_rate(speed),
        )
        await communicator.save(str(mp3_path))

    try:
        try:
            asyncio.run(save_edge_audio())
        except runtime_errors as error:
            raise AudioGeneratorError(f"Edge TTS synthesis failed: {error}") from error
        try:
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        except (OSError, RuntimeError) as error:
            raise AudioGeneratorError(
                f"Could not locate the bundled FFmpeg converter: {error}"
            ) from error
        _run_audio_command(
            [
                ffmpeg,
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(mp3_path),
                "-vn",
                "-ac",
                "1",
                "-ar",
                str(SAMPLE_RATE),
                "-c:a",
                "pcm_s16le",
                str(temporary_path),
            ],
            label="Edge TTS WAV conversion",
        )
        return _validate_staged_wav(temporary_path)
    finally:
        if mp3_path.exists():
            mp3_path.unlink()


def _render_macos_wav(
    temporary_path: Path,
    text: str,
    voice: str,
    speed: float,
) -> int:
    say = shutil.which("say")
    afconvert = shutil.which("afconvert")
    if not say or not afconvert:
        raise AudioGeneratorError("macOS say and afconvert commands are required.")

    text_handle, text_name = tempfile.mkstemp(
        prefix=f".{temporary_path.stem}-",
        suffix=".txt",
        dir=temporary_path.parent,
    )
    os.close(text_handle)
    aiff_handle, aiff_name = tempfile.mkstemp(
        prefix=f".{temporary_path.stem}-",
        suffix=".aiff",
        dir=temporary_path.parent,
    )
    os.close(aiff_handle)
    text_path = Path(text_name)
    aiff_path = Path(aiff_name)
    try:
        text_path.write_text(text, encoding="utf-8")
        aiff_path.unlink()
        words_per_minute = max(80, round(180 * speed))
        _run_audio_command(
            [
                say,
                "-v",
                voice,
                "-r",
                str(words_per_minute),
                "-f",
                str(text_path),
                "-o",
                str(aiff_path),
            ],
            label=f"macOS {voice} synthesis",
        )
        temporary_path.unlink()
        _run_audio_command(
            [
                afconvert,
                "-f",
                "WAVE",
                "-d",
                f"LEI16@{SAMPLE_RATE}",
                "-c",
                "1",
                str(aiff_path),
                str(temporary_path),
            ],
            label="macOS WAV conversion",
        )
        return _validate_staged_wav(temporary_path)
    finally:
        for staged_path in (text_path, aiff_path):
            if staged_path.exists():
                staged_path.unlink()


# Backward-compatible name for existing callers of the MLX renderer.
_render_wav = _render_mlx_wav


@contextmanager
def _output_lock(output_path: Path) -> Iterator[None]:
    lock_key = hashlib.sha256(str(output_path).encode("utf-8")).hexdigest()
    lock_path = (
        cache_dir(REPO_ROOT, TOOL_NAME).expanduser().resolve()
        / "locks"
        / f"{lock_key}.lock"
    )
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(
            lock_path,
            os.O_RDWR | os.O_CREAT,
            0o600,
        )
    except OSError as error:
        raise AudioGeneratorError(f"Could not lock output path: {error}") from error

    locked = False
    try:
        try:
            if os.name == "nt":
                import msvcrt

                if os.fstat(descriptor).st_size == 0:
                    os.write(descriptor, b"\0")
                os.lseek(descriptor, 0, os.SEEK_SET)
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
        except OSError as error:
            raise AudioGeneratorError(
                f"Another synthesis is already publishing this output: {output_path}."
            ) from error

        os.ftruncate(descriptor, 0)
        os.write(
            descriptor,
            json.dumps(
                {
                    "pid": os.getpid(),
                    "createdAt": datetime.now(timezone.utc).isoformat(),
                }
            ).encode("utf-8"),
        )
        yield
    finally:
        try:
            if locked and os.name == "nt":
                import msvcrt

                os.lseek(descriptor, 0, os.SEEK_SET)
                msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
            elif locked:
                import fcntl

                fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


def synthesize_basic(
    *,
    text: str,
    voice: Dict[str, Any],
    speed: float,
    output_path: Path,
    overwrite: bool,
) -> Dict[str, Any]:
    fingerprint = basic_input_fingerprint(text, voice, speed)
    with _output_lock(output_path):
        if not overwrite:
            cached = load_cached_result(output_path, fingerprint)
            if cached is not None:
                return cached
            if output_path.exists() or sidecar_path(output_path).exists():
                raise AudioGeneratorError(
                    f"Output already exists: {output_path}. Choose a new name or "
                    "explicitly use --overwrite."
                )

        preflight = _collect_basic_preflight()
        if not preflight["success"]:
            raise AudioGeneratorError(
                "Basic voice preflight failed: " + " ".join(preflight["issues"])
            )

        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            file_handle, temporary_name = tempfile.mkstemp(
                prefix=f".{output_path.stem}-",
                suffix=".wav",
                dir=output_path.parent,
            )
            os.close(file_handle)
        except OSError as error:
            raise AudioGeneratorError(f"Could not stage output WAV: {error}") from error

        temporary_path = Path(temporary_name)
        staged_metadata: Optional[Path] = None
        try:
            if voice["engine"] == "edge-tts":
                sample_count = _render_edge_wav(
                    temporary_path,
                    text,
                    voice["id"],
                    speed,
                )
                engine = {
                    "name": "edge-tts",
                    "version": BASIC_PACKAGE_VERSIONS["edge-tts"],
                    "backend": "Microsoft Edge Read Aloud",
                    "online": True,
                }
            else:
                sample_count = _render_macos_wav(
                    temporary_path,
                    text,
                    voice["id"],
                    speed,
                )
                engine = {
                    "name": "macos-say",
                    "version": platform.mac_ver()[0] or None,
                    "backend": "macOS speech synthesis",
                    "online": False,
                }

            output_root = output_dir(REPO_ROOT, TOOL_NAME).expanduser().resolve()
            try:
                relative_output = output_path.relative_to(output_root).as_posix()
                relative_metadata = sidecar_path(output_path).relative_to(
                    output_root
                ).as_posix()
            except ValueError as error:
                raise AudioGeneratorError(
                    f"Output must stay inside {output_root}."
                ) from error

            metadata: Dict[str, Any] = {
                "schemaVersion": 1,
                "success": True,
                "cached": False,
                "generator": TOOL_NAME,
                "generatedAt": datetime.now(timezone.utc).isoformat(),
                "mode": "basic",
                "engine": engine,
                "model": None,
                "input": {
                    "fingerprint": fingerprint,
                    "characters": len(text),
                    "language": "en",
                    "textRetained": False,
                    "sentToOnlineService": voice["engine"] == "edge-tts",
                },
                "voice": voice["id"],
                "voiceLabel": voice["label"],
                "fallbackUsed": voice["fallback"],
                "speed": speed,
                "segments": len(segment_text(text)),
                "generatedChunks": 1,
                "output": {
                    "path": relative_output,
                    "metadataPath": relative_metadata,
                    "format": "wav",
                    "sampleRateHz": SAMPLE_RATE,
                    "channels": 1,
                    "sampleWidthBits": 16,
                    "durationSeconds": round(sample_count / SAMPLE_RATE, 3),
                    "bytes": temporary_path.stat().st_size,
                    "sha256": sha256_file(temporary_path),
                },
            }
            staged_metadata = _stage_metadata(sidecar_path(output_path), metadata)
            _publish_outputs(
                temporary_path,
                output_path,
                staged_metadata,
                sidecar_path(output_path),
                overwrite,
            )
            return metadata
        finally:
            if temporary_path.exists():
                temporary_path.unlink()
            if staged_metadata is not None and staged_metadata.exists():
                staged_metadata.unlink()


def _synthesize_with_lock_held(
    *,
    text: str,
    voice: str,
    speed: float,
    pause_ms: int,
    output_path: Path,
    overwrite: bool,
    backend: str = "auto",
    accelerator: str = "auto",
) -> Dict[str, Any]:
    resolved_backend = select_backend(backend)
    resolved_accelerator = select_accelerator(resolved_backend, accelerator)
    fingerprint = input_fingerprint(
        text,
        voice,
        speed,
        pause_ms,
        resolved_backend,
        resolved_accelerator,
    )
    if not overwrite:
        cached = load_cached_result(output_path, fingerprint)
        if cached is not None:
            return cached
        if output_path.exists() or sidecar_path(output_path).exists():
            raise AudioGeneratorError(
                f"Output already exists: {output_path}. Choose a new name or explicitly use --overwrite."
            )

    require_runtime(resolved_backend, resolved_accelerator)
    cache_root = cache_dir(REPO_ROOT, TOOL_NAME).expanduser().resolve()
    try:
        cache_root.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise AudioGeneratorError(f"Could not create model cache: {error}") from error
    active_providers: List[str]
    if resolved_backend == "mlx":
        os.environ["HF_HOME"] = str(cache_root / "huggingface")
        os.environ["HF_HUB_CACHE"] = str(cache_root / "huggingface" / "hub")
        with redirect_stdout(sys.stderr):
            np, snapshot_download, load_model, download_errors = _load_mlx_runtime()
            snapshot_path = _download_model(
                snapshot_download, voice, cache_root, download_errors
            )
        voice_path: Optional[Path] = (
            snapshot_path / "voices" / f"{voice}.safetensors"
        )
        try:
            with redirect_stdout(sys.stderr):
                model = load_model(snapshot_path, model_type="kokoro")
        except (ImportError, OSError, RuntimeError, ValueError) as error:
            raise AudioGeneratorError(
                f"Could not load the pinned Kokoro model: {error}"
            ) from error
        engine = {
            "name": "mlx-audio",
            "version": MLX_PACKAGE_VERSIONS["mlx-audio"],
            "backend": "mlx",
            "accelerator": "Apple Silicon",
            "providers": ["MLX"],
        }
        active_providers = ["MLX"]
    else:
        with redirect_stdout(sys.stderr):
            np, ort, Kokoro = _load_onnx_runtime()
            model_path, voices_path = _download_onnx_assets(cache_root)
            session, active_providers = _create_onnx_session(
                ort, model_path, resolved_accelerator
            )
            try:
                model = Kokoro.from_session(session, str(voices_path))
            except (OSError, RuntimeError, ValueError) as error:
                raise AudioGeneratorError(
                    f"Could not load the pinned Kokoro ONNX model: {error}"
                ) from error
        voice_path = None
        engine = {
            "name": "kokoro-onnx",
            "version": ONNX_PACKAGE_VERSIONS["kokoro-onnx"],
            "backend": "onnx",
            "accelerator": resolved_accelerator,
            "providers": active_providers,
            "experimental": resolved_accelerator in NPU_ACCELERATORS,
        }

    segments = segment_text(text)
    if not segments:
        raise AudioGeneratorError("No speakable English segments were found.")

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        file_handle, temporary_name = tempfile.mkstemp(
            prefix=f".{output_path.stem}-", suffix=".wav", dir=output_path.parent
        )
        os.close(file_handle)
    except OSError as error:
        raise AudioGeneratorError(f"Could not stage output WAV: {error}") from error
    temporary_path = Path(temporary_name)
    staged_metadata: Optional[Path] = None
    try:
        with redirect_stdout(sys.stderr):
            if resolved_backend == "mlx":
                assert voice_path is not None
                sample_count, generated_chunks = _render_mlx_wav(
                    temporary_path,
                    model,
                    np,
                    segments,
                    voice_path,
                    voice,
                    speed,
                    pause_ms,
                )
            else:
                sample_count, generated_chunks = _render_onnx_wav(
                    temporary_path,
                    model,
                    np,
                    segments,
                    voice,
                    speed,
                    pause_ms,
                )

        output_root = output_dir(REPO_ROOT, TOOL_NAME).expanduser().resolve()
        try:
            relative_output = output_path.relative_to(output_root).as_posix()
            relative_metadata = sidecar_path(output_path).relative_to(
                output_root
            ).as_posix()
        except ValueError as error:
            raise AudioGeneratorError(f"Output must stay inside {output_root}.") from error

        audio_hash = sha256_file(temporary_path)
        model_metadata = model_descriptor(resolved_backend)
        if resolved_backend == "mlx":
            model_metadata["voiceWeight"] = f"voices/{voice}.safetensors"
            model_metadata["voiceWeightSha256"] = MLX_VOICE_SHA256[voice]
        metadata: Dict[str, Any] = {
            "schemaVersion": 1,
            "success": True,
            "cached": False,
            "generator": TOOL_NAME,
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "mode": "enhanced",
            "engine": engine,
            "model": model_metadata,
            "input": {
                "fingerprint": fingerprint,
                "characters": len(text),
                "language": "en",
                "textRetained": False,
            },
            "voice": voice,
            "accent": (
                "American English" if voice.startswith("a") else "British English"
            ),
            "speed": speed,
            "segmentPauseMs": pause_ms,
            "segments": len(segments),
            "generatedChunks": generated_chunks,
            "output": {
                "path": relative_output,
                "metadataPath": relative_metadata,
                "format": "wav",
                "sampleRateHz": SAMPLE_RATE,
                "channels": 1,
                "sampleWidthBits": 16,
                "durationSeconds": round(sample_count / SAMPLE_RATE, 3),
                "bytes": temporary_path.stat().st_size,
                "sha256": audio_hash,
            },
        }
        staged_metadata = _stage_metadata(sidecar_path(output_path), metadata)
        _publish_outputs(
            temporary_path,
            output_path,
            staged_metadata,
            sidecar_path(output_path),
            overwrite,
        )
        return metadata
    finally:
        if temporary_path.exists():
            temporary_path.unlink()
        if staged_metadata is not None and staged_metadata.exists():
            staged_metadata.unlink()


def synthesize(
    *,
    text: str,
    voice: str,
    speed: float,
    pause_ms: int,
    output_path: Path,
    overwrite: bool,
    backend: str = "auto",
    accelerator: str = "auto",
) -> Dict[str, Any]:
    with _output_lock(output_path):
        return _synthesize_with_lock_held(
            text=text,
            voice=voice,
            speed=speed,
            pause_ms=pause_ms,
            output_path=output_path,
            overwrite=overwrite,
            backend=backend,
            accelerator=accelerator,
        )


def read_input_text(args: argparse.Namespace) -> str:
    if args.text is not None:
        return validate_text(args.text)
    try:
        return validate_text(Path(args.text_file).expanduser().read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as error:
        raise AudioGeneratorError(f"Could not read UTF-8 text file: {error}") from error


def generate(args: argparse.Namespace) -> Dict[str, Any]:
    text = read_input_text(args)
    speed = validate_speed(args.speed)
    pause_ms = validate_pause_ms(args.pause_ms)
    if args.mode == "basic":
        if args.backend != "auto" or args.accelerator != "auto":
            raise AudioGeneratorError(
                "Backend and accelerator options require --mode enhanced."
            )
        if pause_ms != DEFAULT_PAUSE_MS:
            raise AudioGeneratorError(
                "Custom segment pauses require --mode enhanced."
            )
        voice = resolve_basic_voice(args.voice)
        fingerprint = basic_input_fingerprint(text, voice, speed)
        output_path = resolve_output_path(args.output, fingerprint)
        result = synthesize_basic(
            text=text,
            voice=voice,
            speed=speed,
            output_path=output_path,
            overwrite=args.overwrite,
        )
        result["resolvedOutputPath"] = str(output_path)
        result["resolvedMetadataPath"] = str(sidecar_path(output_path))
        return result

    voice_name = validate_voice(args.voice or DEFAULT_VOICE)
    backend = select_backend(args.backend)
    accelerator = select_accelerator(backend, args.accelerator)
    fingerprint = input_fingerprint(
        text, voice_name, speed, pause_ms, backend, accelerator
    )
    output_path = resolve_output_path(args.output, fingerprint)
    result = synthesize(
        text=text,
        voice=voice_name,
        speed=speed,
        pause_ms=pause_ms,
        output_path=output_path,
        overwrite=args.overwrite,
        backend=backend,
        accelerator=accelerator,
    )
    result["resolvedOutputPath"] = str(output_path)
    result["resolvedMetadataPath"] = str(sidecar_path(output_path))
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate English speech in basic or enhanced mode."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    preflight_parser = subparsers.add_parser(
        "preflight", help="Check the selected mode and its dependencies."
    )
    preflight_parser.add_argument(
        "--mode", choices=("basic", "enhanced"), default=DEFAULT_MODE
    )
    preflight_parser.add_argument(
        "--backend", choices=("auto", "mlx", "onnx"), default="auto"
    )
    preflight_parser.add_argument(
        "--accelerator",
        choices=("auto", *ACCELERATOR_PROVIDERS),
        default="auto",
    )
    subparsers.add_parser("voices", help="List basic and enhanced English voices.")

    generate_parser = subparsers.add_parser("generate", help="Generate a WAV file.")
    text_group = generate_parser.add_mutually_exclusive_group(required=True)
    text_group.add_argument("--text", help="English text to synthesize.")
    text_group.add_argument("--text-file", help="UTF-8 file containing English text.")
    generate_parser.add_argument(
        "--mode", choices=("basic", "enhanced"), default=DEFAULT_MODE
    )
    generate_parser.add_argument(
        "--voice",
        help=(
            "Basic voice alias/name or enhanced Kokoro voice. Defaults by mode "
            "and platform."
        ),
    )
    generate_parser.add_argument("--speed", type=float, default=DEFAULT_SPEED)
    generate_parser.add_argument("--pause-ms", type=int, default=DEFAULT_PAUSE_MS)
    generate_parser.add_argument(
        "--backend", choices=("auto", "mlx", "onnx"), default="auto"
    )
    generate_parser.add_argument(
        "--accelerator",
        choices=("auto", *ACCELERATOR_PROVIDERS),
        default="auto",
        help=(
            "ONNX execution target. auto selects the reliable CPU baseline; "
            "NPU targets are experimental and never silently fall back to CPU."
        ),
    )
    generate_parser.add_argument(
        "--output",
        help="Relative .wav path below USER_HOME/outputs/audio-generator/.",
    )
    generate_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing WAV and sidecar after explicit user approval.",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "preflight":
            payload = collect_preflight(
                args.mode,
                args.backend,
                args.accelerator,
            )
            return emit(payload, 0 if payload["success"] else 1)
        if args.command == "voices":
            return emit(
                {
                    "success": True,
                    "defaultMode": DEFAULT_MODE,
                    "basic": {
                        "Windows": {
                            "default": BASIC_EDGE_VOICE,
                            "label": BASIC_EDGE_VOICE_LABEL,
                        },
                        "macOS": {
                            "default": BASIC_MAC_VOICE,
                            "fallback": BASIC_MAC_FALLBACK_VOICE,
                        },
                    },
                    "enhanced": {
                        "default": DEFAULT_VOICE,
                        "voices": list(SUPPORTED_VOICES),
                    },
                }
            )
        return emit(generate(args))
    except AudioGeneratorError as error:
        return fail(str(error))


if __name__ == "__main__":
    raise SystemExit(main())
