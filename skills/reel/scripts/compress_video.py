#!/usr/bin/env python3
"""Local, lossy H.264/AAC MP4 compression (Python 3.9+, FFmpeg/ffprobe).

compress_video(source, output, *, target_mb=None, crf=23, max_height=None)
never overwrites, trims, changes cadence, or publishes an unverified/non-smaller
file. target_mb is a hard decimal MB ceiling, not an expected exact file size.
It uses at most three two-pass attempts; impossible budgets fail explicitly.
CRF 0..51 defaults to 23. The API permits target_mb with the default crf only;
the CLI makes --target-mb and --crf mutually exclusive.

Bounded support: self-contained local media, <=4 GiB, <=1 hour, one progressive
8-bit YUV420 SDR CFR video, 1..60 fps, even square-pixel dimensions <=4096 on
each axis / <=8,847,360 pixels. Zero-based video and audio timelines only.
Up to eight mono/stereo audio tracks at standard AAC rates <=48 kHz are
re-encoded, with language and default disposition retained. Other dispositions,
rotation/display transforms, non-square SAR, VFR, HDR/10-bit, interlacing,
embedded captions, subtitles, data, attachments, chapters, and unknown side
data are rejected rather than silently discarded. Burned-in captions remain
image pixels. Other container metadata is not copied.

Default dimensions/aspect are unchanged. --max-height only downscales, using
the largest exact-aspect even dimensions within the bound; it fails when such
dimensions cannot be represented. No perceptually lossless claim is made.
The canonical source's .licenses.txt companion, if present, is copied verbatim
and exclusively. Callers must retain any other externally supplied credits.
Staging is in the existing output parent; source files are never modified.
"""

from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation, ROUND_FLOOR
from fractions import Fraction
import json
import math
import os
from pathlib import Path
import re
import stat
import tempfile

import edit_video as media


CompressionError = media.EditError
MAX_BYTES = 4 * 1024 ** 3
MAX_FRAMES = 216000
MAX_AUDIO = 8
MAX_ATTEMPTS = 3
MIN_VIDEO_BITRATE = 16000
COLOR_VALUES = {
    "color_range": {"tv", "pc"},
    "color_space": {"bt709", "bt470bg", "smpte170m"},
    "color_transfer": {"bt709", "bt470bg", "smpte170m", "gamma22", "gamma28"},
    "color_primaries": {"bt709", "bt470bg", "smpte170m"},
}


def preflight_compression():
    """Read-only tool/encoder/filter/muxer probe; returns ffmpeg/ffprobe paths.

    Raises edit_video.EditError (also exported as CompressionError). No inputs,
    network requests, installation, or encoding are involved.
    """
    tools = media.preflight_media_tools()
    encoders = media._run([tools["ffmpeg"], "-hide_banner", "-encoders"])
    for name in ("libx264", "aac"):
        if not re.search(r"^\s*[A-Z.]{6}\s+" + name + r"\s", encoders, re.M):
            raise CompressionError(f"Compression requires the FFmpeg {name} encoder")
    filters = media._run([tools["ffmpeg"], "-hide_banner", "-filters"])
    if not re.search(r"^\s*[A-Z.|]{2,3}\s+scale\s", filters, re.M):
        raise CompressionError("Compression requires the FFmpeg scale filter")
    muxers = media._run([tools["ffmpeg"], "-hide_banner", "-muxers"])
    if not re.search(r"^\s*E\s+mp4\s", muxers, re.M):
        raise CompressionError("Compression requires the FFmpeg MP4 muxer")
    return tools


def _target_bytes(value):
    if type(value) not in (int, float, Decimal) or isinstance(value, bool):
        raise CompressionError("target_mb must be a finite positive decimal MB value")
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number <= 0 or number > Decimal(MAX_BYTES) / 1000000:
            raise CompressionError("target_mb must be positive and at most 4 GiB in decimal MB")
        result = int((number * 1000000).to_integral_value(rounding=ROUND_FLOOR))
    except (InvalidOperation, OverflowError) as exc:
        raise CompressionError("Invalid target_mb") from exc
    if result < 1:
        raise CompressionError("target_mb is smaller than one byte")
    return result


def _fraction(value, label):
    try:
        result = Fraction(str(value))
        if result <= 0:
            raise ValueError()
        return result
    except (ValueError, ZeroDivisionError) as exc:
        raise CompressionError(f"Missing/invalid {label}") from exc


def _dispositions(stream):
    return {key for key, value in stream.get("disposition", {}).items() if value}


def _inspect(path, tools):
    probe = media._probe(path, tools["ffprobe"])
    chapters = json.loads(media._run([
        tools["ffprobe"], "-v", "error", "-protocol_whitelist", "file",
        "-format_whitelist", media.FORMATS, "-show_chapters", "-of", "json", path,
    ]))
    if chapters.get("chapters"):
        raise CompressionError("Chapters are unsupported; compression does not silently drop them")
    streams = probe.get("streams", [])
    videos = [s for s in streams if s.get("codec_type") == "video"]
    audio = [s for s in streams if s.get("codec_type") == "audio"]
    if len(videos) != 1 or len(audio) > MAX_AUDIO or len(streams) != 1 + len(audio):
        raise CompressionError("Require one video and <=8 audio tracks; subtitle/data/attachment/multivideo tracks are unsupported")
    video = videos[0]
    for stream in streams:
        if stream.get("side_data_list") or "rotate" in stream.get("tags", {}):
            raise CompressionError("Rotation/transforms/HDR or other stream side data are unsupported")
        if _dispositions(stream) - {"default"}:
            raise CompressionError("Only default stream disposition is supported (no attachments or special dispositions)")
        if abs(media._start_time(stream, probe)) > .001:
            raise CompressionError("Only zero-based, aligned video/audio timelines are supported")
    if video.get("pix_fmt") not in ("yuv420p", "yuvj420p"):
        raise CompressionError("Only 8-bit YUV420 SDR video is supported; HDR/10-bit is unsupported")
    if video.get("field_order", "unknown") not in ("progressive", "unknown"):
        raise CompressionError("Interlaced video is unsupported")
    if video.get("sample_aspect_ratio", "1:1") not in ("1:1", "N/A"):
        raise CompressionError("Non-square sample aspect ratio (SAR) is unsupported")
    for field, allowed in COLOR_VALUES.items():
        if video.get(field, "unknown") not in allowed | {"unknown", "unspecified"}:
            raise CompressionError(f"Unsupported SDR color metadata: {field}={video[field]} (HDR is unsupported)")
    if video.get("closed_captions", 0) or video.get("film_grain", 0):
        raise CompressionError("Embedded captions or film grain metadata are unsupported")
    width = media._integer(video.get("width"), "video width", 16, 4096)
    height = media._integer(video.get("height"), "video height", 16, 4096)
    if width % 2 or height % 2 or width * height > 8847360:
        raise CompressionError("Require even H264 dimensions and <=8,847,360 pixels")
    fps = _fraction(video.get("avg_frame_rate"), "average frame rate")
    time_base = _fraction(video.get("time_base"), "video time base")
    if not 1 <= fps <= 60 or time_base.numerator != 1 or time_base.denominator > 1000000:
        raise CompressionError("Supported cadence is 1..60 fps with a 1/N time base, N <=1,000,000")
    duration = media._number(media._duration(video, probe), "video duration", .05, media.MAX_SECONDS)
    if duration * float(fps) > MAX_FRAMES + 1:
        raise CompressionError("Video exceeds the 216,000 frame limit")
    for stream in audio:
        if stream.get("channels") not in (1, 2) or stream.get("channel_layout") not in ("mono", "stereo"):
            raise CompressionError("Only mono/stereo audio with a known channel layout is supported")
        if str(stream.get("sample_rate")) not in {"8000", "11025", "12000", "16000", "22050", "24000", "32000", "44100", "48000"}:
            raise CompressionError("Only standard AAC sample rates up to 48 kHz are supported")
        language = stream.get("tags", {}).get("language", "und")
        if not re.fullmatch(r"[a-z]{3}", language):
            raise CompressionError("Audio language must be a three-letter lowercase code")
        audio_duration = media._duration(stream, probe)
        if audio_duration > duration + .05 or audio_duration <= 0:
            raise CompressionError("Audio extending beyond the video timeline is unsupported")
    return {"probe": probe, "video": video, "audio": audio, "duration": duration,
            "fps": fps, "timeBase": time_base, "dimensions": (width, height)}


def _timeline(path, tools, info):
    # A packet limit bounds diagnostic output even if container duration lies.
    raw = media._run([
        tools["ffprobe"], "-v", "error", "-protocol_whitelist", "file",
        "-format_whitelist", media.FORMATS, "-select_streams", "v:0",
        "-read_intervals", f"%+#{MAX_FRAMES + 1}", "-show_frames",
        "-show_entries",
        "frame=best_effort_timestamp_time,interlaced_frame,repeat_pict:frame_side_data=side_data_type",
        "-of", "json", path,
    ], timeout=media.RENDER_TIMEOUT)
    frames = json.loads(raw).get("frames", [])
    if not 1 <= len(frames) <= MAX_FRAMES:
        raise CompressionError("Missing frames or frame count exceeds the 216,000 frame limit")
    points = []
    tick = float(info["timeBase"])
    period = 1 / float(info["fps"])
    for index, frame in enumerate(frames):
        if frame.get("interlaced_frame") or frame.get("repeat_pict"):
            raise CompressionError("Interlacing/repeated-field cadence is unsupported")
        for side in frame.get("side_data_list", []):
            if side.get("side_data_type") not in {
                "H.26[45] User Data Unregistered SEI message",
                "H.264 User Data Unregistered SEI message",
            }:
                raise CompressionError("Embedded captions/HDR/unknown frame side data are unsupported")
        point = media._number(float(frame.get("best_effort_timestamp_time", "nan")),
                              "frame timestamp", 0, media.MAX_SECONDS)
        if abs(point - index * period) > max(tick * 1.1, .00001):
            raise CompressionError("Variable frame cadence or non-zero video start is unsupported")
        points.append(point)
    if abs(points[-1] + period - info["duration"]) > max(tick * 1.1, .002):
        raise CompressionError("Frame timeline does not cover the full declared video duration")
    return points


def _dimensions(info, max_height):
    width, height = info["dimensions"]
    if max_height is None or height <= max_height:
        return width, height
    divisor = math.gcd(width, height)
    unit_w, unit_h = width // divisor, height // divisor
    multiplier = min(max_height // unit_h, divisor)
    if unit_w % 2 or unit_h % 2:
        multiplier -= multiplier % 2
    result = unit_w * multiplier, unit_h * multiplier
    if min(result) < 16:
        raise CompressionError("max_height cannot represent exact aspect ratio with even dimensions >=16")
    return result


def _input_args(source, tools):
    return [tools["ffmpeg"], "-hide_banner", "-loglevel", "error", "-nostdin",
            "-xerror", "-err_detect", "explode", "-protocol_whitelist", "file",
            "-format_whitelist", media.FORMATS, "-noautorotate", "-i", source]


def _encode(source, target, stage, tools, info, dimensions, crf, bitrate):
    args = _input_args(source, tools) + ["-map", "0:v:0", "-map_metadata", "-1",
                                       "-map_chapters", "-1"]
    args += ["-c:v", "libx264", "-preset", "medium", "-threads", "2",
             "-pix_fmt", "yuv420p", "-vsync", "0", "-enc_time_base",
             str(info["timeBase"]), "-video_track_timescale",
             str(info["timeBase"].denominator), "-disposition:v:0",
             "default" if "default" in _dispositions(info["video"]) else "0"]
    if dimensions != info["dimensions"]:
        args += ["-vf", f"scale={dimensions[0]}:{dimensions[1]}:flags=lanczos"]
    for field in COLOR_VALUES:
        value = info["video"].get(field)
        if value in COLOR_VALUES[field]:
            option = "colorspace" if field == "color_space" else field
            args += ["-" + option, value]
    if bitrate is None:
        args += ["-crf", str(crf)]
    else:
        args += ["-b:v", str(bitrate), "-passlogfile", str(stage / "pass")]
        media._run(args + ["-pass", "1", "-an", "-f", "null", "-y", os.devnull],
                   timeout=media.RENDER_TIMEOUT)
        args += ["-pass", "2"]
    for index, stream in enumerate(info["audio"]):
        args += ["-map", f"0:{stream['index']}", f"-c:a:{index}", "aac",
                 f"-b:a:{index}", str(64000 * stream["channels"]),
                 f"-ar:a:{index}", str(stream["sample_rate"]),
                 f"-metadata:s:a:{index}", "language=" + stream.get("tags", {}).get("language", "und"),
                 f"-disposition:a:{index}", "default" if "default" in _dispositions(stream) else "0"]
    media._run(args + ["-movflags", "+faststart", "-f", "mp4", "-n", target],
               timeout=media.RENDER_TIMEOUT)


def _verify(target, tools, source_info, source_points, dimensions):
    # Decode every mapped stream, not just a sample or a successful encoder exit.
    media._run(_input_args(target, tools) + ["-map", "0:v", "-map", "0:a?",
                                           "-f", "null", "-"],
               timeout=media.RENDER_TIMEOUT)
    output = _inspect(target, tools)
    points = _timeline(target, tools, output)
    if output["video"].get("codec_name") != "h264" or output["dimensions"] != dimensions:
        raise CompressionError("Verification failed: H264 codec/dimensions differ")
    if (len(points) != len(source_points)
            or any(abs(a - b) > .000002 for a, b in zip(points, source_points))
            or abs(output["duration"] - source_info["duration"]) > .002):
        raise CompressionError("Verification failed: full video duration/frame cadence differs")
    if len(output["audio"]) != len(source_info["audio"]):
        raise CompressionError("Verification failed: audio track count differs")
    for before, after in zip(source_info["audio"], output["audio"]):
        if (after.get("codec_name") != "aac"
                or any(before.get(key) != after.get(key) for key in ("channels", "sample_rate", "channel_layout"))
                or _dispositions(before) != _dispositions(after)
                or before.get("tags", {}).get("language", "und") != after.get("tags", {}).get("language", "und")
                or abs(media._duration(before, source_info["probe"])
                       - media._duration(after, output["probe"])) > .05):
            raise CompressionError("Verification failed: audio codec/layout/language/disposition/duration differs")
    for field in COLOR_VALUES:
        value = source_info["video"].get(field)
        if value in COLOR_VALUES[field] and output["video"].get(field) != value:
            raise CompressionError(f"Verification failed: {field} differs")
    return output


def _credits(source):
    path = Path(str(source) + ".licenses.txt")
    if not os.path.lexists(path):
        return None
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb") as handle:
        metadata = os.fstat(handle.fileno())
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > 1024 * 1024:
            raise CompressionError("License companion must be a regular file <=1 MiB")
        data = handle.read(1024 * 1024 + 1)
        if len(data) > 1024 * 1024:
            raise CompressionError("License companion exceeds 1 MiB")
        return data


def _identity(path):
    value = path.stat()
    return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns


def compress_video(source, output, *, target_mb=None, crf=23, max_height=None):
    """Return factual JSON-serializable verification results or raise EditError."""
    media._integer(crf, "crf", 0, 51)
    if target_mb is not None and crf != 23:
        raise CompressionError("target_mb and a nondefault crf are mutually exclusive")
    ceiling = _target_bytes(target_mb) if target_mb is not None else None
    if max_height is not None:
        media._integer(max_height, "max_height", 16, 4096)
    output = media._output_path(output)
    output = output.parent.resolve(strict=True) / output.name
    companion = Path(str(output) + ".licenses.txt")
    if os.path.lexists(companion):
        raise CompressionError("Refusing to overwrite existing output license companion")
    source = Path(media._local_path(str(source), Path.cwd(), "source"))
    identity = _identity(source)
    if not 0 < identity[2] <= MAX_BYTES:
        raise CompressionError("Source must be nonempty and at most 4 GiB")
    tools = preflight_compression()
    published = []
    try:
        info = _inspect(source, tools)
        points = _timeline(source, tools, info)
        dimensions = _dimensions(info, max_height)
        credits = _credits(source)
        effective = min(ceiling, identity[2] - 1) if ceiling is not None else None
        audio_rate = sum(64000 * stream["channels"] for stream in info["audio"])
        bitrate = None
        if effective is not None:
            reserved = max(8192, math.ceil(effective * .03))
            bitrate = min(100000000, math.floor((effective - reserved) * 8 / info["duration"] - audio_rate))
            if bitrate < MIN_VIDEO_BITRATE:
                raise CompressionError("Impossible target: insufficient budget for audio, container, and video")
        with tempfile.TemporaryDirectory(prefix=".reel-compress-", dir=output.parent) as directory:
            stage = Path(directory)
            target = stage / "compressed.mp4"
            for attempt in range(1, MAX_ATTEMPTS + 1):
                _encode(source, target, stage, tools, info, dimensions, crf, bitrate)
                size = target.stat().st_size
                if not size:
                    raise CompressionError("Encoder produced an empty file")
                if effective is None or size <= effective:
                    break
                if attempt == MAX_ATTEMPTS:
                    raise CompressionError("Unable to meet byte target after three bounded two-pass attempts")
                bitrate = math.floor(bitrate * effective / size * .90)
                if bitrate < MIN_VIDEO_BITRATE:
                    raise CompressionError("Impossible target after measured bitrate correction")
                target.unlink()
            if size >= identity[2]:
                raise CompressionError("No size saving: output is not smaller than source; nothing published")
            verified = _verify(target, tools, info, points, dimensions)
            if _identity(source) != identity:
                raise CompressionError("Source changed during compression; nothing published")
            if credits is not None:
                license_stage = stage / "licenses.txt"
                license_stage.write_bytes(credits)
                inode = _identity(license_stage)[:2]
                os.link(license_stage, companion)
                published.append((companion, inode))
            inode = _identity(target)[:2]
            os.link(target, output)
            published.append((output, inode))
    except (OSError, ValueError) as exc:
        for path, identity_pair in reversed(published):
            try:
                metadata = path.lstat()
                if (metadata.st_dev, metadata.st_ino) == identity_pair:
                    path.unlink()
            except OSError:
                pass
        if isinstance(exc, CompressionError):
            raise
        raise CompressionError(f"Compression failed; nothing published: {exc}") from exc
    return {
        "ok": True, "source": str(source), "output": str(output),
        "sourceBytes": identity[2], "outputBytes": size,
        "outputToSourceRatio": size / identity[2], "bytesSaved": identity[2] - size,
        "targetBytes": ceiling, "method": "two-pass" if ceiling is not None else "crf",
        "crf": crf if ceiling is None else None, "videoBitrate": bitrate,
        "attempts": attempt, "sourceDimensions": list(info["dimensions"]),
        "dimensions": list(dimensions), "durationSeconds": verified["duration"],
        "frameCount": len(points), "frameRate": str(info["fps"]),
        "audioTracks": len(verified["audio"]), "videoCodec": "h264",
        "audioCodec": "aac" if verified["audio"] else None,
        "licenseInfo": str(companion) if credits is not None else None,
        "creditsNote": "Only the source .licenses.txt companion is copied; retain any other external credits.",
        "qualityNote": "Lossy re-encoding; no perceptually lossless guarantee.",
    }


def _decimal_argument(value):
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise argparse.ArgumentTypeError("Expected a decimal MB value") from exc


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input")
    parser.add_argument("--output", required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--target-mb", type=_decimal_argument)
    mode.add_argument("--crf", type=int)
    parser.add_argument("--max-height", type=int)
    args = parser.parse_args(argv)
    try:
        result = compress_video(args.input, args.output, target_mb=args.target_mb,
                                crf=23 if args.crf is None else args.crf, max_height=args.max_height)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
