#!/usr/bin/env python3
"""Render original local footage montages with Python's standard library + FFmpeg.

Version 1 plan (all objects reject unknown fields):
  {"version": 1, "output": {"fps": 30, "width": 1280, "height": 720},
   "clips": [{"path": "footage.mp4", "sourceStart": 0, "durationFrames": 90,
              "transition": {"type": "fade", "durationFrames": 15}},
             {"path": "other.mp4", "sourceStart": 1, "durationFrames": 90}],
   "audio": {"sourceVolume": 1,
             "music": {"path": "music.wav", "volume": 0.25,
                       "fadeInFrames": 15, "fadeOutFrames": 30, "ducking": true},
             "narration": {"path": "voice.wav", "volume": 1}},
   "captions": [{"startFrame": 0, "endFrame": 45, "text": "Hello"}],
   "attribution": {"text": "Track — creator — license", "startFrame": 0,
                   "endFrame": 90}}

Each transition is its clip's OUTGOING overlap; the last clip cannot have one.
Final frames = sum(durationFrames) - sum(transition.durationFrames). Incoming
and outgoing overlaps must leave at least one non-overlapping frame per clip.
Frame ranges are half-open. FPS is an integer 1..60; dimensions are even
integers 64..3840. At most 100 clips and one hour of output are accepted.
Source starts snap to the nearest output frame after frame-rate normalization.
Paths are local files, resolved relative to the JSON plan (absolute paths work).
Inputs must be ordinary self-contained media, not playlists or remote protocols.
Supported containers: MP4/MOV, Matroska/WebM, WAV, MP3, FLAC, Ogg, AAC, AVI,
MPEG-TS and MPEG. FFmpeg needs libx264 and AAC encoding.
Gains are linear 0..2. Source audio defaults to 1, music to .25, narration to 1.
Both external tracks start at frame zero: music must cover the final duration;
narration must fit without truncation. Music is not looped. Its default fades
are zero and ducking defaults to true when narration exists. Silence fills
missing source audio and the timeline after narration; video is never padded.
Captions and the optional credit panel require FFmpeg's libass `ass` filter.
Attribution defaults to the entire timeline and is retained verbatim in an
exclusive OUTPUT.mp4.licenses.txt companion; no license claims are invented.
Credits must fit the upper third of the image; oversized panels are rejected.
ASS reserved characters are escaped without substituting visible glyphs.

validate_plan(path, *, check_render_capabilities=True) returns a normalized
JSON-serializable dictionary and
raises EditError on invalid plans, unavailable capabilities, or invalid media.
Native draft adapters may set check_render_capabilities=False to omit only
FFmpeg filter/encoder checks; schema, frame ranges, and media checks still run.
render_plan(path, output) preflights before rendering, verifies staged streams,
then publishes without overwriting. The output's existing parent must be
writable. Staging lives only inside that parent and is automatically removed.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unicodedata


class EditError(ValueError):
    """A plan, capability, media, or publication failure."""


FORMATS = "mov,matroska,webm,wav,mp3,flac,ogg,aac,avi,mpegts,mpeg"
MAX_SECONDS = 3600
PROBE_TIMEOUT = 60
RENDER_TIMEOUT = 3600


def _run(args, *, timeout=PROBE_TIMEOUT, cwd=None):
    try:
        result = subprocess.run(
            [str(arg) for arg in args], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout, cwd=cwd,
            stdin=subprocess.DEVNULL, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise EditError(f"Media command failed: {exc}") from exc
    if result.returncode:
        raise EditError(f"{Path(args[0]).name} failed: {result.stderr[-4000:].strip()}")
    return result.stdout


def _tools():
    tools = {name: shutil.which(name) for name in ("ffmpeg", "ffprobe")}
    for name, path in tools.items():
        if not path:
            raise EditError(f"Required executable unavailable: {name}; install separately.")
    return tools


def _probe(path, ffprobe, *, count=False):
    args = [ffprobe, "-v", "error", "-protocol_whitelist", "file",
            "-format_whitelist", FORMATS]
    if count:
        args += ["-count_frames"]
    args += ["-show_streams", "-show_format", "-of", "json", str(path)]
    try:
        return json.loads(_run(args))
    except json.JSONDecodeError as exc:
        raise EditError(f"Invalid ffprobe response for {path}") from exc


def _object(value, allowed, required, label):
    if not isinstance(value, dict):
        raise EditError(f"{label} must be an object")
    unknown = set(value) - set(allowed)
    missing = set(required) - set(value)
    if unknown or missing:
        raise EditError(f"{label}: unknown fields {sorted(unknown)}; missing fields {sorted(missing)}")
    return value


def _integer(value, label, minimum=0, maximum=216000):
    if type(value) is not int or not minimum <= value <= maximum:
        raise EditError(f"{label} must be an integer in [{minimum}, {maximum}]")
    return value


def _number(value, label, minimum=0, maximum=MAX_SECONDS):
    if type(value) not in (int, float) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise EditError(f"{label} must be finite and in [{minimum}, {maximum}]")
    return value


def _text(value, label, maximum=2000):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise EditError(f"{label} must be nonempty text of at most {maximum} characters")
    if any((ord(char) < 32 and char not in "\n\t") or 0xD800 <= ord(char) <= 0xDFFF
           for char in value):
        raise EditError(f"{label} contains unsupported control characters")
    return value


def _local_path(value, base, label):
    if not isinstance(value, str) or not value or "\x00" in value:
        raise EditError(f"{label} must be a local filename")
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", value) or value.startswith(("//", "\\\\")):
        raise EditError(f"{label}: remote URLs and protocols are not supported")
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base / path
    try:
        path = path.resolve(strict=True)
        if not path.is_file() or not os.access(path, os.R_OK):
            raise EditError(f"{label} is not a readable regular file: {path}")
    except OSError as exc:
        raise EditError(f"{label}: {exc}") from exc
    return str(path)


def _duration(stream, probe):
    for value in (stream.get("duration"), stream.get("tags", {}).get("DURATION"),
                  probe.get("format", {}).get("duration")):
        try:
            if isinstance(value, str) and ":" in value:
                hours, minutes, seconds = value.split(":")
                result = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
            else:
                result = float(value)
            if math.isfinite(result) and result > 0:
                return result
        except (TypeError, ValueError):
            pass
    raise EditError("Media has no positive, finite duration")


def _stream(probe, kind):
    return next((s for s in probe.get("streams", []) if s.get("codec_type") == kind
                 and not s.get("disposition", {}).get("attached_pic")), None)


def _start_time(stream, probe):
    for value in (stream.get("start_time"), probe.get("format", {}).get("start_time")):
        try:
            result = float(value)
            if math.isfinite(result):
                return result
        except (TypeError, ValueError):
            pass
    return 0


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise EditError(f"Duplicate JSON field: {key}")
        result[key] = value
    return result


def _load(path):
    try:
        if path.stat().st_size > 1024 * 1024:
            raise EditError("Plan exceeds the 1 MiB limit")
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_pairs)
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise EditError(f"Cannot read plan: {exc}") from exc


def _check_render_capabilities(tools, clips, audio, captions, attribution):
    filters = _run([tools["ffmpeg"], "-hide_banner", "-filters"])
    required = {"scale", "pad", "fps", "aresample", "amix", "alimiter", "setpts",
                "asetpts", "trim", "atrim", "setsar", "settb", "format", "aformat",
                "apad", "volume", "anullsrc"}
    if len(clips) > 1:
        required.add("concat")
    if any("transition" in clip for clip in clips):
        required.update(("xfade", "acrossfade"))
    if captions or attribution:
        required.add("ass")
    if audio.get("music", {}).get("ducking"):
        required.update(("sidechaincompress", "asplit"))
    if audio.get("music"):
        required.add("afade")
    available = set(re.findall(r"^\s*[.A-Z|]{2,3}\s+(\w+)\s", filters, re.MULTILINE))
    missing = required - available
    if missing:
        raise EditError(f"Required FFmpeg filter(s) unavailable: {', '.join(sorted(missing))}"
                        + ("; captions/attribution require libass" if "ass" in missing else ""))
    encoders = _run([tools["ffmpeg"], "-hide_banner", "-encoders"])
    if not re.search(r"\blibx264\b", encoders) or not re.search(r"\baac\b", encoders):
        raise EditError("FFmpeg requires libx264 and aac encoders")


def preflight_media_tools():
    """Probe local tools without requiring any rendering filters or encoders."""
    tools = _tools()
    for path in tools.values():
        _run([path, "-version"], timeout=20)
    return tools


def preflight_capabilities(*, captions=False, credits=False, transitions=False,
                           music=False, narration=False):
    """Read-only selected-feature probe; no media inputs or render are required."""
    tools = preflight_media_tools()
    clips = [{"transition": {}} if transitions else {}, {}]
    audio = {"music": {"ducking": narration}} if music else {}
    _check_render_capabilities(tools, clips, audio, captions, credits)
    return tools


def validate_plan(plan_path, *, check_render_capabilities=True):
    """Validate schema and media; optionally check renderer-only filters/encoders."""
    if type(check_render_capabilities) is not bool:
        raise EditError("check_render_capabilities must be a boolean")
    plan_path = Path(plan_path).resolve()
    data = _object(_load(plan_path), ("version", "output", "clips", "audio", "captions",
                                    "attribution"), ("version", "output", "clips"), "plan")
    if type(data["version"]) is not int or data["version"] != 1:
        raise EditError("Only edit-plan version 1 is supported")
    output = _object(data["output"], ("fps", "width", "height"),
                     ("fps", "width", "height"), "output")
    fps = _integer(output["fps"], "output.fps", 1, 60)
    for key in ("width", "height"):
        if _integer(output[key], f"output.{key}", 64, 3840) % 2:
            raise EditError(f"output.{key} must be even")
    clips = data["clips"]
    if not isinstance(clips, list) or not 1 <= len(clips) <= 100:
        raise EditError("clips must contain 1..100 clips")
    for index, clip in enumerate(clips):
        label = f"clips[{index}]"
        _object(clip, ("path", "sourceStart", "durationFrames", "transition"),
                ("path", "sourceStart", "durationFrames"), label)
        clip["path"] = _local_path(clip["path"], plan_path.parent, f"{label}.path")
        _number(clip["sourceStart"], f"{label}.sourceStart", maximum=86400)
        _integer(clip["durationFrames"], f"{label}.durationFrames", 1)
        if "transition" in clip:
            transition = _object(clip["transition"], ("type", "durationFrames"),
                                 ("type", "durationFrames"), f"{label}.transition")
            if transition["type"] != "fade" or index == len(clips) - 1:
                raise EditError("Only outgoing fade transitions on non-final clips are supported")
            _integer(transition["durationFrames"], f"{label}.transition.durationFrames", 1)
    for index, clip in enumerate(clips):
        incoming = clips[index - 1].get("transition", {}).get("durationFrames", 0) if index else 0
        outgoing = clip.get("transition", {}).get("durationFrames", 0)
        if incoming + outgoing >= clip["durationFrames"]:
            raise EditError(f"clips[{index}] has colliding or overlong overlaps")
    frames = sum(c["durationFrames"] - c.get("transition", {}).get("durationFrames", 0) for c in clips)
    seconds = frames / fps
    if seconds > MAX_SECONDS:
        raise EditError("Final timeline exceeds one hour")
    audio = _object(data.get("audio", {}), ("sourceVolume", "music", "narration"), (), "audio")
    audio.setdefault("sourceVolume", 1)
    _number(audio["sourceVolume"], "audio.sourceVolume", maximum=2)
    for kind in ("music", "narration"):
        if kind not in audio:
            continue
        allowed = ("path", "volume", "fadeInFrames", "fadeOutFrames", "ducking") if kind == "music" else ("path", "volume")
        track = _object(audio[kind], allowed, ("path",), f"audio.{kind}")
        track["path"] = _local_path(track["path"], plan_path.parent, f"audio.{kind}.path")
        track.setdefault("volume", .25 if kind == "music" else 1)
        _number(track["volume"], f"audio.{kind}.volume", maximum=2)
        if kind == "music":
            for key in ("fadeInFrames", "fadeOutFrames"):
                track.setdefault(key, 0)
                _integer(track[key], f"audio.music.{key}", maximum=frames)
            if track["fadeInFrames"] + track["fadeOutFrames"] > frames:
                raise EditError("Music fade ranges overlap")
            track.setdefault("ducking", "narration" in audio)
            if type(track["ducking"]) is not bool:
                raise EditError("audio.music.ducking must be a boolean")
            if track["ducking"] and "narration" not in audio:
                raise EditError("Music ducking requires narration")
    captions = data.get("captions", [])
    if not isinstance(captions, list) or len(captions) > 1000:
        raise EditError("captions must be an array of at most 1000 entries")
    for caption in captions:
        _object(caption, ("startFrame", "endFrame", "text"),
                ("startFrame", "endFrame", "text"), "caption")
        _text(caption["text"], "caption.text", 1000)
        _frame_range(caption, frames, "caption")
    attribution = data.get("attribution")
    if "attribution" in data:
        _object(attribution, ("text", "startFrame", "endFrame"), ("text",), "attribution")
        _text(attribution["text"], "attribution.text")
        attribution.setdefault("startFrame", 0)
        attribution.setdefault("endFrame", frames)
        _frame_range(attribution, frames, "attribution")
        _credit_lines(attribution["text"], output)
    tools = _tools()
    if check_render_capabilities:
        _check_render_capabilities(tools, clips, audio, captions, attribution)
    probes = {}
    for clip in clips:
        path = clip["path"]
        if path not in probes:
            probes[path] = _probe(path, tools["ffprobe"])
        probe = probes[path]
        video = _stream(probe, "video")
        if video is None:
            raise EditError(f"No video stream: {path}")
        snapped_start = int(clip["sourceStart"] * fps + .5) / fps
        if max(clip["sourceStart"], snapped_start) + clip["durationFrames"] / fps > _duration(video, probe) + 1e-6:
            raise EditError(f"Trim exceeds source video duration: {path}")
        source_audio = _stream(probe, "audio")
        clip["hasAudio"] = source_audio is not None
        clip["audioOffset"] = (_start_time(source_audio, probe) - _start_time(video, probe)
                               if source_audio is not None else 0)
    for kind in ("music", "narration"):
        if kind not in audio:
            continue
        track = audio[kind]
        probe = _probe(track["path"], tools["ffprobe"])
        stream = _stream(probe, "audio")
        if stream is None:
            raise EditError(f"No audio stream: {track['path']}")
        duration = _duration(stream, probe)
        if kind == "music" and duration + 1e-6 < seconds:
            raise EditError("Music must cover the final timeline; looping is not supported")
        if kind == "narration" and duration > seconds + 1e-6:
            raise EditError("Narration exceeds the final timeline; truncation is not allowed")
        track["duration"] = duration
    return {"version": 1, "output": output, "clips": clips, "audio": audio,
            "captions": captions, "attribution": attribution, "durationFrames": frames,
            "durationSeconds": seconds, "tools": tools, "planPath": str(plan_path)}


def _frame_range(item, frames, label):
    _integer(item["startFrame"], f"{label}.startFrame", maximum=frames - 1)
    _integer(item["endFrame"], f"{label}.endFrame", 1, frames)
    if item["startFrame"] >= item["endFrame"]:
        raise EditError(f"{label} must have startFrame < endFrame")


def _seconds(value):
    return f"{value:.9f}"


def _input(path):
    return ["-protocol_whitelist", "file", "-format_whitelist", FORMATS, "-i", str(path)]


def _ffmpeg(plan):
    return [plan["tools"]["ffmpeg"], "-hide_banner", "-loglevel", "error",
            "-nostdin", "-n", "-filter_complex_threads", "1", "-filter_threads", "1"]


def _verify(path, plan, frames):
    probe = _probe(path, plan["tools"]["ffprobe"], count=True)
    video, audio = _stream(probe, "video"), _stream(probe, "audio")
    expected = frames / plan["output"]["fps"]
    if video is None or audio is None:
        raise EditError("Rendered output is missing a required video/audio stream")
    if (video.get("width"), video.get("height")) != (plan["output"]["width"], plan["output"]["height"]):
        raise EditError("Rendered dimensions do not match the plan")
    if video.get("avg_frame_rate") != f"{plan['output']['fps']}/1":
        raise EditError("Rendered frame rate does not match the plan")
    if audio.get("sample_rate") != "48000" or audio.get("channels") != 2:
        raise EditError("Rendered audio must be 48 kHz stereo")
    if video.get("nb_read_frames") != str(frames):
        raise EditError(f"Rendered frame count differs from plan ({video.get('nb_read_frames')} != {frames}); video is never padded")
    for kind, stream in (("video", video), ("audio", audio)):
        if abs(_duration(stream, probe) - expected) > max(1 / plan["output"]["fps"], .05):
            raise EditError(f"Rendered {kind} duration does not match the timeline")
    return probe


def _normalize(clip, index, plan, stage):
    fps, width, height = (plan["output"][key] for key in ("fps", "width", "height"))
    duration = clip["durationFrames"] / fps
    first_frame = int(clip["sourceStart"] * fps + .5)
    start = _seconds(first_frame / fps)
    end = _seconds(first_frame / fps + duration)
    video = (f"[0:v:0]setpts=PTS-STARTPTS,fps={fps}:round=near,"
             f"trim=start_frame={first_frame}:end_frame={first_frame + clip['durationFrames']},"
             "setpts=PTS-STARTPTS,"
             f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
             f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,"
             f"settb=1/{fps},setpts=N,format=yuv420p[v]")
    if clip["hasAudio"]:
        audio = (f"[0:a:0]asetpts=PTS-STARTPTS+{_seconds(clip['audioOffset'])}/TB,"
                 f"aresample=48000:async=1:first_pts=0,atrim=start={start}:end={end},"
                 "asetpts=PTS-STARTPTS,"
                 "aformat=sample_fmts=fltp:channel_layouts=stereo,")
    else:
        audio = "anullsrc=r=48000:cl=stereo,"
    audio += f"apad,atrim=duration={_seconds(duration)},asetpts=PTS-STARTPTS[a]"
    path = stage / f"clip-{index}.mp4"
    args = _ffmpeg(plan) + _input(clip["path"])
    args += ["-filter_complex", video + ";" + audio, "-map", "[v]", "-map", "[a]",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-ar", "48000", "-ac", "2", "-t", _seconds(duration), str(path)]
    _run(args, timeout=RENDER_TIMEOUT)
    _verify(path, plan, clip["durationFrames"])
    return path


def _ass_time(frame, fps):
    centiseconds = round(frame * 100 / fps)
    hours, rest = divmod(centiseconds, 360000)
    minutes, rest = divmod(rest, 6000)
    seconds, fraction = divmod(rest, 100)
    return f"{hours}:{minutes:02}:{seconds:02}.{fraction:02}"


def _ass_text(text):
    # The invisible separator keeps a literal backslash from becoming \N or \h.
    return (text.replace("\\", "\\\ufeff").replace("{", r"\{").replace("}", r"\}")
            .replace("\t", "    ").replace("\n", r"\N"))


def _credit_lines(text, output):
    font = max(12, round(max(12, round(output["height"] * .045)) * .8))
    margin = max(8, round(output["height"] * .05))
    capacity = max(1, int((output["width"] - 2 * margin - 8) / (font * .7)))
    lines = []
    for paragraph in text.expandtabs(4).split("\n"):
        line, units = "", 0
        for char in paragraph:
            width = 2 if unicodedata.east_asian_width(char) in ("W", "F") else 1
            if line and units + width > capacity:
                lines.append(line)
                line, units = "", 0
            line += char
            units += width
        lines.append(line)
    if len(lines) * font * 1.3 > output["height"] / 3 - margin:
        raise EditError("Attribution credit panel is too long to remain readable; shorten it or increase output dimensions")
    return "\n".join(lines)


def _write_ass(plan, stage):
    output = plan["output"]
    width, height, fps = output["width"], output["height"], output["fps"]
    font = max(12, round(height * .045))
    margin = max(8, round(height * .05))
    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {width}", f"PlayResY: {height}",
        "WrapStyle: 0", "ScaledBorderAndShadow: yes", "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Caption,Arial,{font},&H00FFFFFF,&H00FFFFFF,&H00000000,&H90000000,0,0,0,0,100,100,0,0,1,2,0,2,{margin},{margin},{margin},1",
        f"Style: Credit,Arial,{max(12, round(font * .8))},&H00FFFFFF,&H00FFFFFF,&H00000000,&H40000000,0,0,0,0,100,100,0,0,3,4,0,8,{margin},{margin},{margin},1",
        "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for style, items in (("Caption", plan["captions"]),
                         ("Credit", [plan["attribution"]] if plan["attribution"] else [])):
        for item in items:
            text = item["text"]
            if style == "Credit":
                text = _credit_lines(text, output)
            lines.append(f"Dialogue: 0,{_ass_time(item['startFrame'], fps)},"
                         f"{_ass_time(item['endFrame'], fps)},{style},,0,0,0,,{_ass_text(text)}")
    path = stage / "overlay.ass"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _assemble(plan, paths, stage):
    fps = plan["output"]["fps"]
    duration = plan["durationSeconds"]
    args = _ffmpeg(plan)
    for path in paths:
        args += _input(path)
    graph = []
    for index in range(len(paths)):
        clip_seconds = plan["clips"][index]["durationFrames"] / fps
        graph += [f"[{index}:v:0]settb=1/{fps},setpts=PTS-STARTPTS[v{index}]",
                  f"[{index}:a:0]aresample=48000,atrim=duration={_seconds(clip_seconds)},"
                  f"asetpts=PTS-STARTPTS[a{index}]"]
    video, audio = "v0", "a0"
    elapsed = plan["clips"][0]["durationFrames"]
    for index in range(1, len(paths)):
        next_video, next_audio = f"joinv{index}", f"joina{index}"
        fade = plan["clips"][index - 1].get("transition", {}).get("durationFrames", 0)
        if fade:
            graph += [f"[{video}][v{index}]xfade=transition=fade:duration={_seconds(fade / fps)}:"
                      f"offset={_seconds((elapsed - fade) / fps)}[{next_video}]",
                      f"[{audio}][a{index}]acrossfade=d={_seconds(fade / fps)}:c1=tri:c2=tri[{next_audio}]"]
        else:
            graph += [f"[{video}][v{index}]concat=n=2:v=1:a=0,fps={fps},"
                      f"settb=1/{fps},setpts=N[{next_video}]",
                      f"[{audio}][a{index}]concat=n=2:v=0:a=1[{next_audio}]"]
        video, audio = next_video, next_audio
        elapsed += plan["clips"][index]["durationFrames"] - fade
    graph += [f"[{video}]fps={fps},trim=end_frame={plan['durationFrames']},setpts=N/({fps}*TB)[picture]",
              f"[{audio}]volume={plan['audio']['sourceVolume']}[source]"]
    video = "picture"
    if plan["captions"] or plan["attribution"]:
        _write_ass(plan, stage)
        # A controlled basename + cwd avoids all filtergraph path quoting hazards.
        graph.append("[picture]ass=filename=overlay.ass[captioned]")
        video = "captioned"
    mix = ["source"]
    input_index = len(paths)
    for kind in ("music", "narration"):
        track = plan["audio"].get(kind)
        if not track:
            continue
        args += _input(track["path"])
        chain = (f"[{input_index}:a:0]asetpts=PTS-STARTPTS,"
                 "aresample=48000:async=1:first_pts=0,aformat=sample_fmts=fltp:channel_layouts=stereo,")
        if kind == "music":
            chain += f"atrim=duration={_seconds(duration)},"
            for direction, key in (("in", "fadeInFrames"), ("out", "fadeOutFrames")):
                length = track[key] / fps
                if length:
                    start = 0 if direction == "in" else duration - length
                    chain += f"afade=t={direction}:st={_seconds(start)}:d={_seconds(length)},"
        else:
            chain += f"apad,atrim=duration={_seconds(duration)},"
        chain += f"volume={track['volume']}[{kind}]"
        graph.append(chain)
        mix.append(kind)
        input_index += 1
    if plan["audio"].get("music", {}).get("ducking"):
        graph += ["[narration]asplit=2[voice][key]",
                  "[music][key]sidechaincompress=threshold=0.025:ratio=8:attack=20:release=250[ducked]"]
        mix = ["source", "ducked", "voice"]
    graph.append("".join(f"[{name}]" for name in mix)
                 + f"amix=inputs={len(mix)}:normalize=0:duration=longest,"
                 f"alimiter=limit=0.95:level=0:latency=1,apad,"
                 f"atrim=duration={_seconds(duration)},asetpts=PTS-STARTPTS[sound]")
    target = stage / "render.mp4"
    args += ["-filter_complex", ";".join(graph), "-map", f"[{video}]", "-map", "[sound]",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-ar", "48000", "-ac", "2",
             "-t", _seconds(duration), "-movflags", "+faststart", str(target)]
    _run(args, timeout=RENDER_TIMEOUT, cwd=stage)
    _verify(target, plan, plan["durationFrames"])
    return target


def _output_path(value):
    raw = str(value)
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", raw) or raw.startswith(("//", "\\\\")) or "\x00" in raw:
        raise EditError("Output must be a local MP4 path")
    path = Path(value).expanduser().absolute()
    if path.suffix.lower() != ".mp4":
        raise EditError("Output must have an .mp4 extension")
    if not path.parent.is_dir() or not os.access(path.parent, os.W_OK):
        raise EditError("Output parent must already exist and be writable")
    if os.path.lexists(path):
        raise EditError(f"Refusing to overwrite existing output: {path}")
    return path


def render_plan(plan_path, output):
    """Preflight, render in the output parent, verify, and publish exclusively."""
    output = _output_path(output)
    plan = validate_plan(plan_path)
    companion = Path(str(output) + ".licenses.txt") if plan["attribution"] else None
    if companion and os.path.lexists(companion):
        raise EditError(f"Refusing to overwrite existing license companion: {companion}")
    published = []
    try:
        with tempfile.TemporaryDirectory(prefix=".reel-edit-", dir=output.parent) as directory:
            stage = Path(directory)
            paths = [_normalize(clip, index, plan, stage) for index, clip in enumerate(plan["clips"])]
            target = _assemble(plan, paths, stage)
            if companion:
                license_file = stage / "licenses.txt"
                license_file.write_text(plan["attribution"]["text"], encoding="utf-8")
                os.link(license_file, companion)
                published.append((companion, companion.stat().st_ino))
            # Hard links publish an already complete file atomically and fail if it exists.
            os.link(target, output)
            published.append((output, output.stat().st_ino))
    except (OSError, EditError) as exc:
        for path, inode in reversed(published):
            try:
                if path.lstat().st_ino == inode:
                    path.unlink()
            except OSError:
                pass
        if isinstance(exc, EditError):
            raise
        raise EditError(f"Exclusive output publication failed: {exc}") from exc
    return {"ok": True, "output": str(output), "durationFrames": plan["durationFrames"],
            "durationSeconds": plan["durationSeconds"], "videoCodec": "h264", "audioCodec": "aac",
            "licenseInfo": str(companion) if companion else None}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate", help="Validate strict plan, media, and capabilities").add_argument("plan")
    render = commands.add_parser("render", help="Render verified MP4 without overwriting")
    render.add_argument("plan")
    render.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            plan = validate_plan(args.plan)
            result = {"ok": True, "version": 1, "durationFrames": plan["durationFrames"],
                      "durationSeconds": plan["durationSeconds"], "output": plan["output"]}
        else:
            result = render_plan(args.plan, args.output)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (EditError, OSError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
