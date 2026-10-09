#!/usr/bin/env python3
"""Optional, staging-only Jianying handoff for the strict Reel edit-plan.

No dependency installation, native app discovery, database writes, or automated
export. This adapter targets the API researched at GuanYixuan/pyJianYingDraft
c3318066d964744e2bfc66f75c71745fe8cea52a, not every release named 0.3.0.
Native opening, rendering, fonts, and application-version compatibility remain
unverified. Dependency/API preflight and edit_video.validate_plan run before
any output is created. Shared schema and media bounds remain mandatory; native
text/audio tracks do not require FFmpeg rendering filters or encoders.

Use --staging-root EMPTY_OR_ABSENT_PATH --confirm-staging-only to attest that
the destination is outside the live editor database. Its parent must exist.
Media and adjacent sidecars are copied; --sidecar adds explicitly named evidence.
The resulting directory must stay at its generated location: draft media paths
are absolute. Import/open a copy manually after reviewing handoff.json.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.metadata
import inspect
import json
from pathlib import Path
import shutil
import sys
import uuid

import edit_video


REFERENCE_REVISION = "c3318066d964744e2bfc66f75c71745fe8cea52a"
SUPPORTED = [
    "Straight cuts with frame-snapped source ranges and integer-microsecond timing",
    "Source video volume; separate narration and music audio tracks starting at zero",
    "Music fade-in/out durations mapped to native audio fades before track insertion",
    "Non-overlapping captions and a separate visible verbatim credit track",
    "Original plan, normalized plan, copied media, and discovered/explicit source sidecars",
]
UNSUPPORTED = [
    "Transitions, overlapping video, filters, keyframes, speed changes",
    "Ducking, looping, or delayed source-audio synchronization",
    "Overlapping captions on the caption track",
    "FFmpeg pixel/audio-mix parity (including its automatic limiter), automatic native import/open/export",
    "Moving the handoff without relinking its absolute media paths",
]
PACKAGE_ERRORS = (OSError, ValueError, TypeError, AttributeError, RuntimeError,
                  KeyError, IndexError, ImportError)
MEDIA_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm", ".wav", ".mp3", ".flac",
                  ".ogg", ".aac", ".avi", ".ts", ".mpeg", ".mpg", ".m4a"}
LIVE_NAMES = {"com.lveditor.draft", "drafts", "jianyingpro", "capcut",
              "com.lemon.lvoverseas", "com.lemon.lv"}
LIVE_MARKERS = {"draft_content.json", "draft_info.json", "draft_meta_info.json",
                "root_meta_info.json"}


class ExportError(ValueError):
    """An explicit dependency, subset, staging, or draft-generation failure."""


def _bind(function, *args, **kwargs):
    try:
        inspect.signature(function).bind(*args, **kwargs)
    except (TypeError, ValueError) as exc:
        raise ExportError(f"Incompatible pyJianYingDraft API: {function}: {exc}") from exc


def _dependency():
    try:
        draft = importlib.import_module("pyJianYingDraft")
    except ImportError as exc:
        raise ExportError(
            f"Optional pyJianYingDraft dependency unavailable: {exc}. "
            "No installation or fallback was attempted."
        ) from exc
    try:
        for kind in ("video", "audio", "text"):
            getattr(draft.TrackType, kind)
        _bind(draft.DraftFolder, "existing-staging-directory")
        _bind(draft.DraftFolder.create_draft, None, "safe-name", 1280, 720,
              fps=30, maintrack_adsorb=False, allow_replace=False)
        _bind(draft.TrackSpec, draft.TrackType.video, "main_video")
        _bind(draft.Timerange, 0, 1000000)
        for segment in (draft.VideoSegment, draft.AudioSegment):
            _bind(segment, "/absolute/media", object(),
                  source_timerange=object(), volume=1.0)
        _bind(draft.AudioSegment.add_fade, None, 0, 1000000)
        _bind(draft.ClipSettings, transform_y=-0.8)
        _bind(draft.TextSegment, "credit", object(), clip_settings=object())
        # Inspect the script type without creating a draft to test compatibility.
        _bind(draft.ScriptFile.append_tracks, None, [])
        _bind(draft.ScriptFile.add_segment, None, object(), "main_video")
        _bind(draft.ScriptFile.save, None)
    except AttributeError as exc:
        raise ExportError(f"Incompatible pyJianYingDraft API: {exc}") from exc
    try:
        installed_version = importlib.metadata.version("pyJianYingDraft")
    except importlib.metadata.PackageNotFoundError:
        installed_version = None
    identity = {
        "module": "pyJianYingDraft",
        "modulePath": str(getattr(draft, "__file__", None)),
        "declaredVersion": str(getattr(draft, "__version__", "unknown")),
        "distributionVersion": installed_version,
        "referenceRepository": "GuanYixuan/pyJianYingDraft",
        "referenceRevision": REFERENCE_REVISION,
        "installedRevisionVerified": False,
        "apiContract": {
            "DraftFolder.create_draft": "name,width,height,fps,maintrack_adsorb,allow_replace=False",
            "ScriptFile": "append_tracks(list) is non-chainable; add_segment(segment,track_name); save()",
            "Timerange": "integer microseconds: start,duration (NOT end)",
            "segments": "VideoSegment/AudioSegment(path,target,source_timerange,volume); TextSegment(text,target,clip_settings)",
            "audioFades": "AudioSegment.add_fade(in_duration_us,out_duration_us), once before add_segment",
            "saveFiles": ["draft_content.json", "draft_meta_info.json"],
        },
        "compatibility": "Signature-checked API only; version strings do not establish compatibility",
    }
    return draft, identity


def preflight_dependency():
    """Check the optional native API without creating or opening a project."""
    _, identity = _dependency()
    return identity


def _subset(plan):
    if any("transition" in clip for clip in plan["clips"]):
        raise ExportError("Unsupported transitions: draft export accepts straight cuts only")
    if any(abs(clip["audioOffset"]) > 1e-6 and clip["hasAudio"]
           and plan["audio"]["sourceVolume"] for clip in plan["clips"]):
        raise ExportError("Unsupported delayed source-audio synchronization (audioOffset)")
    music = plan["audio"].get("music", {})
    if music.get("ducking"):
        raise ExportError("Unsupported music ducking; explicitly use ducking=false")
    end = 0
    for caption in sorted(plan["captions"], key=lambda item: item["startFrame"]):
        if caption["startFrame"] < end:
            raise ExportError("Unsupported overlapping captions on one native text track")
        end = caption["endFrame"]


def _staging_path(value, confirmed):
    if not confirmed:
        raise ExportError("--confirm-staging-only is required; never target a live editor database")
    supplied = Path(value).expanduser().absolute()
    if supplied.is_symlink() or any(parent.is_symlink() for parent in supplied.parents):
        raise ExportError("Staging paths must not traverse symlinks")
    path = supplied.resolve()
    for ancestor in (path, *path.parents):
        if ancestor.name.casefold() in LIVE_NAMES or any(
                (ancestor / marker).exists() for marker in LIVE_MARKERS):
            raise ExportError(f"Refusing a possible live editor draft/database path: {ancestor}")
    if not path.parent.is_dir():
        raise ExportError("The staging root's parent directory must already exist")
    if path.exists() and (not path.is_dir() or any(path.iterdir())):
        raise ExportError("Staging root must be absent or empty; existing content is never overwritten")
    return path


def _sidecars(source):
    """Adjacent basename.* and non-media stem.* files are source sidecars."""
    result = []
    for item in sorted(source.parent.iterdir()):
        if item == source:
            continue
        match = item.name.startswith(source.name + ".") or (
            item.name.startswith(source.stem + ".")
            and item.suffix.lower() not in MEDIA_SUFFIXES)
        if match:
            if item.is_symlink() or not item.is_file():
                raise ExportError(f"Source sidecar must be a regular non-symlink file: {item}")
            result.append(item)
    return result


def _credits(plan, files):
    credit = (plan["attribution"] or {}).get("text", "")
    required = []
    metadata_credit = False
    for path in files:
        if path.suffix.lower() != ".json":
            continue
        if path.stat().st_size > 1024 * 1024:
            raise ExportError(f"Sidecar JSON exceeds 1 MiB: {path}")
        try:
            metadata = json.loads(path.read_text(encoding="utf-8"),
                                  object_pairs_hook=edit_video._pairs)
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ExportError(f"Invalid source sidecar JSON {path}: {exc}") from exc
        if not isinstance(metadata, dict):
            continue
        text = metadata.get("attributionText")
        mandatory = metadata.get("attributionRequired") is True or str(
            metadata.get("license", "")).upper().startswith("CC-BY")
        if mandatory and (not isinstance(text, str) or not text.strip()):
            raise ExportError(f"Mandatory source credits need verbatim attributionText: {path}")
        if isinstance(text, str) and text.strip():
            required.append(text)
            metadata_credit = True
    if not metadata_credit:
        for path in files:
            if path.name.endswith((".license.txt", ".licenses.txt")):
                text = path.read_text(encoding="utf-8").rstrip("\r\n")
                if text.strip():
                    required.append(text)
    for text in required:
        if text not in credit:
            raise ExportError("Missing mandatory verbatim source credit in plan.attribution.text")
    return required


def _us(frame, fps):
    # Rounding absolute frame boundaries keeps adjacent segments non-overlapping.
    return (frame * 1000000 + fps // 2) // fps


def _call(label, function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except PACKAGE_ERRORS as exc:
        raise ExportError(f"pyJianYingDraft {label} failed ({type(exc).__name__}): {exc}") from exc


def _write_json(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def export_plan(plan_path, staging_root, *, target_app_version,
                confirm_staging_only=False, sidecars=()):
    """Generate a new persistent handoff; never claim a native verification."""
    if not isinstance(target_app_version, str) or not target_app_version.strip():
        raise ExportError("A requested target Jianying app version is required (not a compatibility claim)")
    draft, identity = _dependency()
    plan = edit_video.validate_plan(plan_path, check_render_capabilities=False)
    _subset(plan)
    root = _staging_path(staging_root, confirm_staging_only)
    sources = list(dict.fromkeys(
        [clip["path"] for clip in plan["clips"]]
        + [plan["audio"][kind]["path"] for kind in ("narration", "music")
           if kind in plan["audio"]]))
    evidence = {source: _sidecars(Path(source)) for source in sources}
    explicit = []
    for value in sidecars:
        path = Path(value).expanduser().absolute()
        if path.is_symlink() or not path.is_file():
            raise ExportError(f"Explicit sidecar must be a regular non-symlink file: {path}")
        explicit.append(path.resolve())
    credit_texts = []
    for files in evidence.values():
        credit_texts.extend(_credits(plan, files))
    credit_texts.extend(_credits(plan, explicit))
    name = "emma-" + uuid.uuid4().hex
    bundle = root / name
    created_root = False
    created_bundle = False
    complete = False
    try:
        if not root.exists():
            root.mkdir()
            created_root = True
        if any(root.iterdir()):
            raise ExportError("Staging root became nonempty; refusing concurrent output")
        bundle.mkdir()
        created_bundle = True
        media_dir = bundle / "media"
        media_dir.mkdir()
        drafts_dir = bundle / "drafts"
        drafts_dir.mkdir()
        copies = {}
        inventory = []
        for index, source in enumerate(sources):
            path = Path(source)
            copied = media_dir / f"{index:03d}-{path.name}"
            shutil.copyfile(path, copied)
            copies[source] = str(copied)
            entry = {"source": source, "copy": str(copied), "sidecars": []}
            for sidecar in evidence[source]:
                target = media_dir / f"{index:03d}-{sidecar.name}"
                shutil.copyfile(sidecar, target)
                entry["sidecars"].append({"source": str(sidecar), "copy": str(target)})
            inventory.append(entry)
        evidence_dir = bundle / "evidence"
        evidence_dir.mkdir()
        explicit_inventory = []
        for index, path in enumerate(explicit):
            target = evidence_dir / f"{index:03d}-{path.name}"
            shutil.copyfile(path, target)
            explicit_inventory.append({"source": str(path), "copy": str(target)})
        shutil.copyfile(plan["planPath"], bundle / "original-edit-plan.json")
        _write_json(bundle / "normalized-edit-plan.json", plan)
        fps = plan["output"]["fps"]
        folder = _call("DraftFolder", draft.DraftFolder, str(drafts_dir))
        script = _call("create_draft", folder.create_draft, name,
                       plan["output"]["width"], plan["output"]["height"],
                       fps=fps, maintrack_adsorb=False, allow_replace=False)
        tracks = [draft.TrackSpec(draft.TrackType.video, "main_video")]
        for kind in ("narration", "music"):
            if kind in plan["audio"]:
                tracks.append(draft.TrackSpec(draft.TrackType.audio, kind))
        if plan["captions"]:
            tracks.append(draft.TrackSpec(draft.TrackType.text, "captions"))
        if plan["attribution"]:
            tracks.append(draft.TrackSpec(draft.TrackType.text, "credits"))
        _call("append_tracks", script.append_tracks, tracks)
        position = 0
        for clip in plan["clips"]:
            start = _us(position, fps)
            duration = _us(position + clip["durationFrames"], fps) - start
            source_frame = int(clip["sourceStart"] * fps + .5)
            segment = _call(
                "VideoSegment", draft.VideoSegment, copies[clip["path"]],
                draft.Timerange(start, duration),
                source_timerange=draft.Timerange(_us(source_frame, fps), duration),
                volume=plan["audio"]["sourceVolume"] if clip["hasAudio"] else 0)
            _call("add_segment", script.add_segment, segment, "main_video")
            position += clip["durationFrames"]
        for kind in ("narration", "music"):
            if kind not in plan["audio"]:
                continue
            audio = plan["audio"][kind]
            duration = (_us(plan["durationFrames"], fps) if kind == "music"
                        else round(audio["duration"] * 1000000))
            segment = _call("AudioSegment", draft.AudioSegment, copies[audio["path"]],
                            draft.Timerange(0, duration),
                            source_timerange=draft.Timerange(0, duration),
                            volume=audio["volume"])
            if kind == "music" and (audio["fadeInFrames"] or audio["fadeOutFrames"]):
                fade_in = _us(audio["fadeInFrames"], fps)
                fade_out = duration - _us(plan["durationFrames"] - audio["fadeOutFrames"], fps)
                _call("AudioSegment.add_fade", segment.add_fade, fade_in, fade_out)
            _call("add_segment", script.add_segment, segment, kind)
        text_groups = [("captions", plan["captions"], -0.8),
                       ("credits", [plan["attribution"]] if plan["attribution"] else [], 0.8)]
        for track, items, y in text_groups:
            for item in sorted(items, key=lambda value: value["startFrame"]):
                start = _us(item["startFrame"], fps)
                duration = _us(item["endFrame"], fps) - start
                segment = _call("TextSegment", draft.TextSegment, item["text"],
                                draft.Timerange(start, duration),
                                clip_settings=draft.ClipSettings(transform_y=y))
                _call("add_segment", script.add_segment, segment, track)
        _call("save", script.save)
        draft_dir = drafts_dir / name
        for filename in ("draft_content.json", "draft_meta_info.json"):
            path = draft_dir / filename
            try:
                if path.is_symlink() or not path.is_file():
                    raise ExportError(f"Draft save did not create a regular {filename}")
                saved = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(saved, dict) or not saved:
                    raise ExportError(f"Draft save produced an empty/non-object {filename}")
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise ExportError(f"Draft save produced unreadable {filename}: {exc}") from exc
        manifest = {
            "success": True, "generatedDraft": True,
            "nativeOpenVerified": False, "nativeExportVerified": False,
            "targetApplication": "Jianying", "requestedTargetAppVersion": target_app_version,
            "nativeCompatibility": "UNVERIFIED; open and export manually in the requested app version",
            "draftDirectory": str(draft_dir), "handoffDirectory": str(bundle),
            "dependency": identity, "supportedScope": SUPPORTED, "unsupportedScope": UNSUPPORTED,
            "media": inventory, "explicitSidecars": explicit_inventory,
            "sidecarDiscovery": "Adjacent basename.* and non-media stem.* regular files; use --sidecar for others",
            "verbatimRequiredCredits": list(dict.fromkeys(credit_texts)),
            "attribution": plan["attribution"],
            "planFiles": ["original-edit-plan.json", "normalized-edit-plan.json"],
            "handoff": "Keep this directory at its current path. Review credits and native preview, then manually export; no native app was accessed.",
        }
        _write_json(bundle / "handoff.json", manifest)
        complete = True
        return manifest
    finally:
        # Never remove a supplied root or unrelated/concurrently created paths.
        if not complete:
            if created_bundle:
                shutil.rmtree(bundle)
            if created_root and not any(root.iterdir()):
                root.rmdir()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--staging-root", required=True)
    parser.add_argument("--target-app-version", required=True)
    parser.add_argument("--confirm-staging-only", action="store_true")
    parser.add_argument("--sidecar", action="append", default=[])
    args = parser.parse_args(argv)
    try:
        result = export_plan(args.plan, args.staging_root,
                             target_app_version=args.target_app_version,
                             confirm_staging_only=args.confirm_staging_only,
                             sidecars=args.sidecar)
    except (ExportError, edit_video.EditError, OSError, UnicodeError, TypeError,
            AttributeError, RuntimeError, KeyError, IndexError, ImportError) as exc:
        print(json.dumps({"success": False, "generatedDraft": False,
                          "nativeOpenVerified": False, "nativeExportVerified": False,
                          "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
