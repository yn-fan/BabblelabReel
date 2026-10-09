#!/usr/bin/env python3
"""Local footage metadata, storyboard frames, and measured musical onset candidates.

Requires ffmpeg/ffprobe, not a vision service or speech/model installation.
Onsets are edit suggestions, not verified musical beats or a semantic shot analysis.
"""

from __future__ import annotations

import argparse
import array
import html
import json
import math
import shutil
import statistics
import subprocess
import sys
from pathlib import Path


class MediaError(ValueError):
    pass


def number(value, label, minimum=0):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MediaError(f"{label} must be a finite number")
    if not math.isfinite(value) or value < minimum:
        raise MediaError(f"{label} must be finite and >= {minimum}")
    return value


def run(tool, args, timeout=120):
    executable = shutil.which(tool)
    if executable is None:
        raise MediaError(f"{tool} is required; installation needs user permission")
    try:
        result = subprocess.run(
            [executable, *args], capture_output=True, timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise MediaError(f"{tool} exceeded {timeout}s") from error
    if result.returncode:
        raise MediaError(f"{tool} failed: {result.stderr.decode(errors='replace')[-3000:]}")
    return result.stdout


def local_file(path):
    path = Path(path).expanduser().resolve()
    if not path.is_file():
        raise MediaError(f"Local media file does not exist: {path}")
    return path


def inspect_media(path):
    path = local_file(path)
    raw = run("ffprobe", [
        "-v", "error", "-protocol_whitelist", "file,pipe", "-show_format",
        "-show_streams", "-of", "json", str(path),
    ])
    data = json.loads(raw)
    try:
        duration = float(data["format"]["duration"])
    except (KeyError, TypeError, ValueError) as error:
        raise MediaError("Media has no measurable duration") from error
    number(duration, "duration", 0.001)
    streams = [
        {key: stream[key] for key in (
            "index", "codec_type", "codec_name", "width", "height",
            "avg_frame_rate", "sample_rate", "channels", "duration",
        ) if key in stream}
        for stream in data.get("streams", [])
    ]
    if not streams:
        raise MediaError("Media contains no streams")
    return {"path": str(path), "durationSeconds": duration, "streams": streams}


def onset_candidates(samples, sample_rate=8000, fps=30, minimum_gap=0.2):
    """Detect positive RMS-energy peaks at 10ms resolution; never invent a grid."""
    number(fps, "fps", 1)
    number(minimum_gap, "minimum gap", 0.05)
    if not isinstance(sample_rate, int) or sample_rate < 100:
        raise MediaError("sample rate must be an integer >= 100")
    hop = sample_rate // 100
    energy = [
        math.sqrt(sum(float(x) ** 2 for x in samples[start:start + hop]) / hop)
        for start in range(0, len(samples) - hop + 1, hop)
    ]
    novelty = [
        max(0, level - statistics.mean(energy[max(0, i - 3):i] or [0]))
        for i, level in enumerate(energy)
    ]
    maximum = max(novelty, default=0)
    if maximum < 1:
        return []
    baseline = statistics.median(novelty)
    deviation = statistics.median(abs(x - baseline) for x in novelty)
    threshold = max(maximum * 0.12, baseline + 4 * deviation)
    peaks = [
        i for i, level in enumerate(novelty)
        if level > threshold
        and (i == 0 or level > novelty[i - 1])
        and (i == len(novelty) - 1 or level >= novelty[i + 1])
    ]
    selected = []
    for i in sorted(peaks, key=lambda i: (-novelty[i], i)):
        if all(abs(i - prior) * hop / sample_rate >= minimum_gap for prior in selected):
            selected.append(i)
    return [
        {
            "seconds": round(i * hop / sample_rate, 6),
            "frame": round(i * hop / sample_rate * fps),
            "strength": round(novelty[i] / maximum, 4),
        }
        for i in sorted(selected)
    ]


def analyze_beats(path, fps=30):
    number(fps, "fps", 1)
    media = inspect_media(path)
    if not any(s.get("codec_type") == "audio" for s in media["streams"]):
        raise MediaError("Beat analysis requires an audio stream")
    if media["durationSeconds"] > 1200:
        raise MediaError("Beat analysis is limited to 20 minutes; supply a shorter excerpt")
    pcm = run("ffmpeg", [
        "-v", "error", "-nostdin", "-protocol_whitelist", "file,pipe",
        "-i", media["path"], "-map", "0:a:0", "-vn", "-t", "1200",
        "-ac", "1", "-ar", "8000", "-f", "s16le", "pipe:1",
    ], timeout=180)
    samples = array.array("h")
    samples.frombytes(pcm)
    if sys.byteorder != "little":
        samples.byteswap()
    candidates = onset_candidates(samples, fps=fps)
    return {
        "schemaVersion": 1, "kind": "onset-candidates", "source": media["path"],
        "fps": fps, "durationSeconds": media["durationSeconds"],
        "method": "positive RMS-energy peaks; 10ms windows; no synthesized beat grid",
        "candidates": candidates,
        "reviewRequired": True,
        "warning": "Transients may not be musical beats. Audition before aligning edits.",
    }


def snap_cuts(cuts, beat_frames, tolerance=3, minimum_shot=12):
    for value in [*cuts, *beat_frames, tolerance, minimum_shot]:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise MediaError("Frames, tolerance and minimum shot must be nonnegative integers")
    if minimum_shot < 1 or cuts != sorted(set(cuts)):
        raise MediaError("Cuts must be strictly increasing; minimum shot must be positive")
    prior = 0
    for cut in cuts:
        if cut - prior < minimum_shot:
            raise MediaError("Original cuts violate the minimum shot duration")
        prior = cut
    result = []
    for i, cut in enumerate(cuts):
        lower = (result[-1]["proposedFrame"] if result else 0) + minimum_shot
        upper = cuts[i + 1] - minimum_shot if i + 1 < len(cuts) else math.inf
        eligible = [b for b in beat_frames if lower <= b <= upper and abs(b - cut) <= tolerance]
        chosen = min(eligible, key=lambda b: (abs(b - cut), b)) if eligible else cut
        result.append({"originalFrame": cut, "proposedFrame": chosen, "deltaFrames": chosen - cut})
    return result


def storyboard(path, seconds, destination):
    media = inspect_media(path)
    if not any(s.get("codec_type") == "video" for s in media["streams"]):
        raise MediaError("Storyboard extraction requires a video stream")
    if not 1 <= len(seconds) <= 48:
        raise MediaError("Select between 1 and 48 sample times per storyboard")
    for second in seconds:
        number(second, "sample time")
        if second >= media["durationSeconds"]:
            raise MediaError("Sample times must precede the end of the media")
    destination = Path(destination).expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=False)
    created = []
    try:
        rows = []
        for index, second in enumerate(seconds):
            filename = f"frame-{index:03d}.jpg"
            target = destination / filename
            created.append(target)
            run("ffmpeg", [
                "-v", "error", "-nostdin", "-n", "-protocol_whitelist", "file,pipe",
                "-i", media["path"], "-ss", str(second), "-frames:v", "1",
                "-vf", "scale=640:-2", str(target),
            ])
            if not target.is_file() or target.stat().st_size == 0:
                raise MediaError(f"No frame decoded at {second}s")
            rows.append({"seconds": second, "image": filename})
        manifest = {**media, "frames": rows, "semanticAnalysis": "not performed"}
        manifest_path = destination / "frames.json"
        created.append(manifest_path)
        with manifest_path.open("x", encoding="utf-8") as output:
            json.dump(manifest, output, indent=2)
        page = (
            '<!doctype html><meta charset="utf-8"><title>Footage storyboard</title>'
            '<style>body{font:16px system-ui;margin:24px}main{display:flex;flex-wrap:wrap}'
            'figure{margin:8px;max-width:320px}img{width:100%}</style>'
            f"<h1>{html.escape(Path(media['path']).name)}</h1>"
            "<p>Sampled frames, not a semantic analysis. Review motion and audio separately.</p><main>"
            + "".join(
                f'<figure><img src="{r["image"]}" alt="Frame at {r["seconds"]} seconds">'
                f'<figcaption>{r["seconds"]:.3f}s</figcaption></figure>' for r in rows
            ) + "</main>"
        )
        index_path = destination / "index.html"
        created.append(index_path)
        with index_path.open("x", encoding="utf-8") as output:
            output.write(page)
        return {"directory": str(destination), "frames": rows}
    except (OSError, ValueError):
        for target in reversed(created):
            target.unlink(missing_ok=True)
        destination.rmdir()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("inspect", "beats", "storyboard"):
        command = commands.add_parser(name)
        command.add_argument("source", type=Path)
        if name == "beats":
            command.add_argument("--fps", type=int, default=30)
        if name == "storyboard":
            command.add_argument("--at", type=float, nargs="+", required=True)
            command.add_argument("--output", type=Path, required=True)
    command = commands.add_parser("snap", help="Suggest cut frames, never rewrite the edit plan")
    command.add_argument("--beats", type=Path, required=True)
    command.add_argument("--cuts", type=int, nargs="+", required=True)
    command.add_argument("--fps", type=int, required=True)
    command.add_argument("--tolerance", type=int, default=3)
    command.add_argument("--minimum-shot", type=int, default=12)
    args = parser.parse_args()
    try:
        if args.command == "inspect":
            result = inspect_media(args.source)
        elif args.command == "beats":
            result = analyze_beats(args.source, args.fps)
        elif args.command == "storyboard":
            result = storyboard(args.source, args.at, args.output)
        else:
            beats = json.loads(args.beats.read_text(encoding="utf-8"))
            if not isinstance(beats, dict):
                raise MediaError("Beat evidence must be an object")
            if beats.get("kind") != "onset-candidates" or beats.get("fps") != args.fps:
                raise MediaError("Beat candidates must match the edit's fps")
            candidates = beats.get("candidates")
            if not isinstance(candidates, list) or any(
                not isinstance(candidate, dict) or "frame" not in candidate
                for candidate in candidates
            ):
                raise MediaError("Beat evidence must contain a list of frame candidates")
            result = {"reviewRequired": True, "cuts": snap_cuts(
                args.cuts, [b["frame"] for b in candidates],
                args.tolerance, args.minimum_shot,
            )}
        print(json.dumps(result, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"media analysis failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
