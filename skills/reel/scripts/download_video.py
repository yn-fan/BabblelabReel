#!/usr/bin/env python3
"""Acquire a specified, authorized video for Reel; never search for media."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import uuid
from urllib.parse import urlsplit

BABBLELABREEL_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(BABBLELABREEL_ROOT / "tools/scripts"))
from user_paths import ArtifactContext

DOMAINS = {
    "youtube": ("youtube.com", "youtu.be", "youtube-nocookie.com"),
    "bilibili": ("bilibili.com", "b23.tv"),
    "instagram": ("instagram.com",),
    "douyin": ("douyin.com", "iesdouyin.com"),
    "xiaohongshu": ("xiaohongshu.com", "xhslink.com"),
    "wechat-channels": ("channels.weixin.qq.com", "finder.video.qq.com", "weixin.qq.com"),
}


class VideoError(ValueError):
    """A local contract failure with a fixed, non-sensitive diagnostic."""


class DependencyError(VideoError):
    """An existing dependency environment requires explicit repair."""


def platform(url: str) -> str | None:
    try:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        if (parts.scheme not in ("http", "https") or parts.username or parts.password
                or parts.port not in (None, 80, 443) or "\\" in url
                or any(ord(c) < 32 for c in url)):
            return None
    except ValueError:
        return None
    for name, domains in DOMAINS.items():
        if any(host == domain or host.endswith("." + domain) for domain in domains):
            return name
    return None


def links(text: str) -> list[str]:
    # Share prose often follows a URL without whitespace. Encoded query bytes stay intact.
    found = re.findall(r'https?://[^\s<>"\u3000-\u303f\u4e00-\u9fff\uff00-\uffef]+', text)
    return list(dict.fromkeys(
        url if "?" in url or "#" in url else url.rstrip(".,;!?:)]}'") for url in found
    ))


def source_ref(url: str, index: int) -> dict:
    name = platform(url)
    return {
        "index": index, "platform": name,
        "source": {
            "sha256": hashlib.sha256(url.encode("utf-8")).hexdigest(),
            "host": urlsplit(url).hostname if name else None,
        },
    }


def managed_environment_roots(alias: str | None = None):
    plugin_data = os.environ.get("COPILOT_PLUGIN_DATA")
    if plugin_data:
        base = Path(plugin_data).expanduser()
        if not base.is_absolute():
            raise DependencyError("COPILOT_PLUGIN_DATA must be absolute")
        yield base / "dependencies/reel-video"
    yield ArtifactContext(BABBLELABREEL_ROOT, "reel", "dependencies", alias=alias).state / "dependencies/reel-video"


def environment_python(root: Path, platform_name: str) -> Path:
    return root / ("Scripts/python.exe" if platform_name == "win32" else "bin/python")


def backend(alias: str | None = None) -> list[str] | None:
    if importlib.util.find_spec("yt_dlp") is not None:
        return [sys.executable, "-m", "yt_dlp"]
    executable = shutil.which("yt-dlp")
    if executable:
        return [executable]
    for root in managed_environment_roots(alias):
        if root.resolve().is_relative_to(BABBLELABREEL_ROOT) or "installed-plugins" in root.resolve().parts:
            raise DependencyError("Managed dependencies must be outside BabblelabReel source and installed caches")
        if root.is_symlink():
            raise DependencyError("Managed dependency directory must not be a symlink")
        if not root.exists():
            continue
        python = environment_python(root, sys.platform)
        if not root.is_dir() or not (root / "pyvenv.cfg").is_file() or not python.is_file():
            raise DependencyError("Managed environment is incomplete; request scoped dependency repair")
        tool = [str(python), "-I", "-m", "yt_dlp"]
        try:
            probe = run_process(tool + ["--version"], timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            raise DependencyError("Managed downloader cannot start; request scoped dependency repair") from None
        if probe.returncode or not re.fullmatch(r"\d{4}\.\d{1,2}\.\d{1,2}[\w.+-]*", probe.stdout.strip()):
            raise DependencyError("Managed yt-dlp is unavailable; request scoped dependency repair")
        return tool
    return None


def doctor(alias: str | None = None) -> dict:
    try:
        available = backend(alias) is not None
        diagnostic = None
    except DependencyError as error:
        available, diagnostic = False, str(error)
    tools = {
        "yt_dlp": available,
        "ffmpeg": shutil.which("ffmpeg") is not None,
        "ffprobe": shutil.which("ffprobe") is not None,
        "js_runtime": "deno" if shutil.which("deno") else ("node" if shutil.which("node") else None),
    }
    if diagnostic:
        return {"status": "dependency_error", "message": diagnostic, **tools}
    return {"status": "ready" if all(tools[k] for k in ("yt_dlp", "ffmpeg", "ffprobe"))
            else "missing_dependency", **tools}


def run_process(argv: list[str], *, timeout: int, **kwargs) -> subprocess.CompletedProcess:
    """Own the extractor's process tree, including any ffmpeg merger."""
    options = {"start_new_session": True} if os.name != "nt" else {
        "creationflags": subprocess.CREATE_NEW_PROCESS_GROUP
    }
    input_text = kwargs.pop("input", None)
    with subprocess.Popen(
        argv, stdin=subprocess.PIPE if input_text is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        encoding="utf-8", errors="replace", **options, **kwargs,
    ) as process:
        try:
            stdout, stderr = process.communicate(input_text, timeout=timeout)
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            else:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            process.kill()
            process.communicate()
            raise
        return subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)


def failure_kind(error: str) -> str:
    value = error.lower()
    # Successful cookie extraction often precedes unrelated extractor/network errors.
    error_lines = [line for line in value.splitlines() if re.match(r"\s*error:", line)]
    if error_lines:
        value = "\n".join(error_lines)
    if any(term in value for term in ("operation not permitted", "permission denied", "full disk access")):
        return "browser_access_denied" if any(
            term in value for term in ("cookie", "keychain", "browser", "full disk access")
        ) else "local_error"
    for kind, terms in (
        ("rate_limited", ("429", "captcha", "verify you", "rate limit")),
        ("site_response_or_verification_blocked", ("fresh cookies",)),
        ("requested_quality_unavailable", ("requested format is not available",)),
        ("browser_cookie_error", ("failed to decrypt", "could not copy", "could not find chrome cookies",
                                 "could not find firefox cookies", "failed to load cookies", "cookies database")),
        ("network_error", ("timed out", "resolve", "connection", "network", "proxy")),
        ("needs_login", ("sign in", "login", "log in", "cookies are needed",
                         "cookies are required", "private video", "authentication")),
        ("unavailable", ("video is unavailable", "video unavailable", "has been removed", "has been deleted")),
        ("unsupported_url", ("unsupported url",)),
    ):
        if any(term in value for term in terms):
            return kind
    return "extractor_or_download_error"


def command(args: argparse.Namespace, folder: Path, receipt: Path, tool: list[str]) -> list[str]:
    cmd = tool + [
        "--ignore-config", "--no-cache-dir", "--no-playlist", "--playlist-items", "1",
        "--no-progress", "--no-warnings", "--socket-timeout", "25", "--retries", "2",
        "--fragment-retries", "2", "--no-overwrites", "--restrict-filenames",
        "--max-filesize", f"{args.max_mb}M", "--match-filter", "!is_live & !is_upcoming",
        "--no-write-info-json", "--no-write-thumbnail", "--no-write-subs",
        "-P", str(folder), "-o", "media.%(ext)s",
    ]
    runtime = "deno" if shutil.which("deno") else ("node" if shutil.which("node") else None)
    if runtime:
        cmd += ["--js-runtimes", runtime]
    if args.cookies:
        cmd += ["--cookies", str(Path(args.cookies).expanduser().resolve(strict=True))]
    if args.browser:
        selected = args.browser + (":" + args.browser_profile if args.browser_profile else "")
        cmd += ["--cookies-from-browser", selected]
    if args.probe:
        cmd += ["--skip-download", "--dump-single-json"]
    else:
        floor = f"[width>={args.min_resolution}][height>={args.min_resolution}]" if args.min_resolution else ""
        cmd += ["-f", f"bv*{floor}+ba/b{floor}", "--format-sort", "res", "--merge-output-format", "mp4",
                "--print-to-file", "after_move:%(filepath)j", str(receipt)]
    # Signed source URLs must not appear in child argv or process listings.
    return cmd + ["--batch-file", "-"]


def positive_duration(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def positive_dimension(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None


def metadata(stdout: str) -> dict:
    data = json.loads(stdout)
    if not isinstance(data, dict):
        raise VideoError("invalid_metadata")
    if data.get("_type") in ("playlist", "multi_video"):
        entries = data.get("entries")
        if not isinstance(entries, list) or len(entries) != 1 or not isinstance(entries[0], dict):
            raise VideoError("ambiguous_collection")
        data = entries[0]
    if data.get("is_live") or data.get("live_status") in ("is_live", "is_upcoming", "post_live"):
        return {"status": "live_not_supported"}
    formats = data.get("formats") or [data]
    video_formats = [
        item for item in formats if isinstance(item, dict) and (
            item.get("vcodec") not in (None, "none")
            or (positive_duration(item.get("width"))
                and item.get("ext") in ("mp4", "mkv", "webm", "mov", "avi", "m4v", "flv", "mpeg", "ts"))
        )
    ] if isinstance(formats, list) else []
    if not video_formats:
        return {"status": "no_video_metadata"}
    # Only numeric properties leave the extractor, not URLs, headers or arbitrary identifiers.
    variants = []
    for item in video_formats:
        variant = {
            "width": positive_dimension(item.get("width")),
            "height": positive_dimension(item.get("height")),
            "fps": positive_duration(item.get("fps")),
            "bitrate_kbps": positive_duration(item.get("tbr")),
        }
        if variant not in variants:
            variants.append(variant)
    variants.sort(key=lambda item: (
        min(item["width"] or 0, item["height"] or 0),
        item["fps"] or 0, item["bitrate_kbps"] or 0,
    ), reverse=True)
    return {"status": "resolved", "duration": positive_duration(data.get("duration")),
            "formats": variants[:256], "formats_truncated": len(variants) > 256}


def verify_video(path: Path, folder: Path, max_bytes: int, timeout: int) -> dict:
    resolved = path.resolve(strict=True)
    if (not resolved.is_relative_to(folder.resolve()) or path.is_symlink()
            or any(p.is_symlink() for p in path.parents if p != folder.parent)
            or not path.is_file() or path.stat().st_nlink != 1):
        raise VideoError("unsafe_receipt")
    size = path.stat().st_size
    if not 0 < size <= max_bytes:
        raise VideoError("invalid_file_size")
    proc = run_process(
        [shutil.which("ffprobe"), "-v", "error", "-protocol_whitelist", "file",
         "-show_entries", "stream=codec_type,duration,width,height:stream_disposition=attached_pic:format=duration",
         "-of", "json", str(resolved)],
        timeout=min(timeout, 60),
    )
    if proc.returncode:
        raise VideoError("invalid_video")
    data = json.loads(proc.stdout)
    if not isinstance(data, dict) or not isinstance(data.get("streams"), list):
        raise VideoError("invalid_video")
    video = [s for s in data["streams"] if isinstance(s, dict)
             and s.get("codec_type") == "video"
             and isinstance(s.get("disposition", {}), dict)
             and not s.get("disposition", {}).get("attached_pic")]
    durations = [positive_duration(s.get("duration")) for s in video]
    fmt = data.get("format", {})
    duration = next((d for d in durations if d), None)
    if duration is None and isinstance(fmt, dict):
        duration = positive_duration(fmt.get("duration"))
    if not video or duration is None:
        raise VideoError("invalid_video")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    dimensions = {key: positive_dimension(video[0].get(key)) for key in ("width", "height")}
    return {"path": str(resolved), "bytes": size, "duration": duration,
            "sha256": digest.hexdigest(), **dimensions}


def run_one(args: argparse.Namespace, url: str, index: int, root: Path) -> dict:
    result = source_ref(url, index)
    if args.min_resolution:
        result["requested_min_resolution"] = args.min_resolution
    name = result["platform"]
    if name is None:
        return dict(result, status="unsupported_url")
    if name == "wechat-channels":
        return dict(result, status="needs_wechat_capture")
    try:
        tool = backend(args.alias)
    except DependencyError as error:
        return dict(result, status="dependency_error", message=str(error))
    missing = ([] if tool else ["yt-dlp"]) + (
        [name for name in ("ffmpeg", "ffprobe") if not shutil.which(name)] if not args.probe else []
    )
    if missing:
        return dict(result, status="missing_dependency", missing=missing)
    folder = root / f"item-{index}"
    receipt = folder / ".completed.jsonl"
    try:
        folder.mkdir(parents=True, exist_ok=False)
        proc = run_process(
            command(args, folder, receipt, tool), input=url + "\n", cwd=folder,
            timeout=args.timeout,
        )
        if proc.returncode:
            return dict(result, status=failure_kind(proc.stderr), returncode=proc.returncode)
        if args.probe:
            return dict(result, **metadata(proc.stdout))
        if not receipt.exists():
            return dict(result, status="no_video_saved", files=[])
        if receipt.is_symlink() or receipt.stat().st_size > 65536:
            raise VideoError("unsafe_receipt")
        records = receipt.read_text(encoding="utf-8").splitlines()
        if len(records) != 1:
            raise VideoError("unexpected_file_count")
        value = json.loads(records[0])
        if not isinstance(value, str) or not Path(value).is_absolute():
            raise VideoError("unsafe_receipt")
        file = verify_video(Path(value), folder, args.max_mb * 1024 * 1024, args.timeout)
        if args.min_resolution and min(file["width"] or 0, file["height"] or 0) < args.min_resolution:
            raise VideoError("requested_resolution_not_met")
        return dict(result, status="downloaded", rights=args.rights, files=[file])
    except subprocess.TimeoutExpired:
        return dict(result, status="timeout")
    except VideoError as error:
        return dict(result, status="validation_failed", reason=str(error))
    except (OSError, ValueError, RuntimeError) as error:
        return dict(result, status="local_error", error_type=type(error).__name__)
    finally:
        # The receipt is not evidence; it can contain untrusted paths.
        if receipt.exists() or receipt.is_symlink():
            receipt.unlink()


def safe_directory(path: Path, home: Path) -> Path:
    if not path.resolve().is_relative_to(home.resolve()) or path.resolve().is_relative_to(BABBLELABREEL_ROOT):
        raise VideoError("Artifact destination escapes the user binding")
    for part in (path, *path.parents):
        if part.is_symlink() or (part.exists() and not part.is_dir()):
            raise VideoError("Artifact directories must be real directories")
        if part == home:
            break
    return path


def read_manifest(path: Path, run_id: str) -> dict:
    if path.is_symlink():
        raise VideoError("Manifest must not be a symlink")
    if not path.exists():
        return {"session_id": run_id, "created": datetime.now(timezone.utc).isoformat(), "artifacts": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("session_id") != run_id or not isinstance(data.get("artifacts"), list):
        raise VideoError("Existing manifest does not match this run")
    return data


def write_json(path: Path, data: dict) -> None:
    if path.is_symlink():
        raise VideoError("Artifact file must not be a symlink")
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
            stream.close()
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def execute(args: argparse.Namespace, urls: list[str]) -> dict:
    context = ArtifactContext(
        BABBLELABREEL_ROOT, "reel", args.run_id, alias=args.alias, feature_name=args.feature_name,
        master_skill=args.master_skill, master_run_id=args.master_run_id,
        master_feature_name=args.master_feature_name,
    )
    report = safe_directory(context.report, context.user_home)
    output = safe_directory(context.output, context.user_home)
    manifest_path = report / "_manifest.json"
    manifest = read_manifest(manifest_path, args.run_id)
    parent_path = report.parent / "_manifest.json" if args.master_skill else None
    parent = read_manifest(parent_path, args.master_run_id) if parent_path else None
    acquisition = uuid.uuid4().hex
    filename = f"video-acquisition-{acquisition}.json"
    report.mkdir(parents=True, exist_ok=True)
    record_path = report / filename
    root = (report if args.probe else output) / "videos" / acquisition
    safe_directory(root, context.user_home).mkdir(parents=True, exist_ok=False)
    record = {"schemaVersion": 1, "mode": "probe" if args.probe else "download",
              "status": "pending", "results": []}
    write_json(record_path, record)
    manifest["artifacts"].append({
        "skill": "reel", "type": "video-acquisition", "file": filename,
        "written": datetime.now(timezone.utc).isoformat(),
        "summary": "Specified-link acquisition; see per-item status and rights declaration.",
    })
    write_json(manifest_path, manifest)
    if parent is not None:
        parent["artifacts"].append({
            "skill": "reel", "type": "video-acquisition", "file": f"reel/{filename}",
            "written": datetime.now(timezone.utc).isoformat(),
            "summary": "Child Reel specified-link acquisition.",
        })
        write_json(parent_path, parent)
    for index, url in enumerate(urls, 1):
        record["results"].append(run_one(args, url, index, root))
        write_json(record_path, record)
    record["status"] = "completed" if all(
        r["status"] in ("resolved", "downloaded") for r in record["results"]
    ) else "incomplete"
    write_json(record_path, record)
    return {**record, "provenance": str(record_path), "manifest": str(manifest_path)}


def positive_int(value: str) -> int:
    try:
        number = int(value)
        if number > 0:
            return number
    except ValueError:
        pass
    raise argparse.ArgumentTypeError("expected a positive integer")


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("text", nargs="?", help="Share text; prefer stdin for signed links")
    mode = cli.add_mutually_exclusive_group()
    mode.add_argument("--plan", action="store_true", help="Offline, redacted routing; no files or dependencies")
    mode.add_argument("--probe", action="store_true", help="Fetch metadata only; never download video")
    mode.add_argument("--doctor", action="store_true", help="Local dependency discovery; never install")
    auth = cli.add_mutually_exclusive_group()
    auth.add_argument("--cookies", help="Explicitly authorized local Netscape cookie file")
    auth.add_argument("--browser", choices=("chrome", "chromium", "edge", "firefox", "brave", "opera", "safari", "vivaldi"))
    cli.add_argument("--browser-profile", help="Explicitly authorized profile name, e.g. Profile 1; not a path")
    cli.add_argument("--allow-auth", action="store_true", help="User explicitly authorized the selected login state")
    cli.add_argument("--rights", choices=("owned", "authorized", "licensed"), help="User's download/use rights declaration")
    cli.add_argument("--timeout", type=positive_int, default=600)
    cli.add_argument("--max-mb", type=positive_int, default=2048)
    cli.add_argument("--min-resolution", type=positive_int,
                     help="Download-only native minimum for both dimensions; 2160 requires 4K-class output")
    cli.add_argument("--run-id", help="Host-bound report run ID; required for probe/download")
    cli.add_argument("--alias")
    cli.add_argument("--feature-name")
    cli.add_argument("--master-skill")
    cli.add_argument("--master-run-id")
    cli.add_argument("--master-feature-name")
    return cli


def main(argv: list[str] | None = None) -> int:
    cli = parser()
    args = cli.parse_args(argv)
    try:
        if args.min_resolution and (args.plan or args.probe or args.doctor):
            raise VideoError("--min-resolution applies to downloads; use --probe to inspect all formats")
        if args.browser_profile and (
            not args.browser or args.browser == "safari"
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 ._-]{0,127}", args.browser_profile)
        ):
            raise VideoError("--browser-profile requires a supported browser and a simple profile name")
        if args.doctor:
            result = doctor(args.alias)
        else:
            text = args.text if args.text is not None else (sys.stdin.read() if not sys.stdin.isatty() else "")
            urls = links(text)
            if not urls:
                raise VideoError("no_links: supply HTTP(S) share text; a WeChat card is not a link")
            if args.plan:
                result = {"status": "planned", "results": [
                    dict(source_ref(url, i), status=("needs_wechat_capture" if platform(url) == "wechat-channels"
                         else "planned" if platform(url) else "unsupported_url"))
                    for i, url in enumerate(urls, 1)
                ]}
            else:
                if not args.run_id:
                    raise VideoError("Host-bound --run-id is required")
                for value in (args.run_id, args.alias, args.feature_name, args.master_skill,
                              args.master_run_id, args.master_feature_name):
                    if value is not None and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", value):
                        raise VideoError("Invalid artifact context identifier")
                if bool(args.master_skill) != bool(args.master_run_id):
                    raise VideoError("Master skill and run ID must be supplied together")
                if not args.probe and not args.rights:
                    raise VideoError("Download requires --rights backed by user authorization or license")
                if (args.cookies or args.browser) and not args.allow_auth:
                    raise VideoError("Selected login state requires explicit authorization and --allow-auth")
                if args.cookies and not Path(args.cookies).expanduser().is_file():
                    raise VideoError("Cookie file is unavailable")
                previous = os.umask(0o077)
                try:
                    result = execute(args, urls)
                finally:
                    os.umask(previous)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0 if result["status"] in ("planned", "completed", "ready") else 1
    except VideoError as error:
        print(json.dumps({"status": "invalid_request", "message": str(error)}))
        return 2
    except (OSError, ValueError, RuntimeError) as error:
        print(json.dumps({"status": "local_error", "error_type": type(error).__name__}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
