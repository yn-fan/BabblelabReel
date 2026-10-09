#!/usr/bin/env python3
"""Read-only, local Reel prerequisites for the selected engine.

Never installs packages, invokes npx, downloads models, contacts music services,
opens native editors, authenticates, or creates a project. A ready result proves
only the checked local prerequisites, not successful media production.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys


class PreflightError(ValueError):
    pass


def command(args):
    try:
        result = subprocess.run(
            args, capture_output=True, text=True, encoding="utf-8",
            errors="replace", stdin=subprocess.DEVNULL, timeout=20, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise PreflightError(f"Local prerequisite probe failed: {error}") from error
    if result.returncode:
        raise PreflightError(f"{Path(args[0]).name}: {result.stderr.strip()[-1500:]}")
    return result.stdout.strip()


def executable(name, *, probe_version=True):
    path = shutil.which(name)
    if not path:
        raise PreflightError(f"{name} is not available on PATH")
    if not probe_version:
        return {
            "path": path, "version": "not-probed",
            "note": "Launcher found; bootstrap availability is not verified or triggered.",
        }
    lines = command([path, "--version"]).splitlines()
    if not lines:
        raise PreflightError(f"{name} returned no version information")
    return {"path": path, "version": lines[0]}


def python_version():
    if sys.version_info < (3, 9):
        raise PreflightError("Python 3.9+ is required")
    return sys.version.split()[0]


def read_manifest(project):
    project = Path(project).expanduser().resolve()
    if not project.is_dir():
        raise PreflightError(f"Project directory does not exist: {project}")
    try:
        manifest_path = project / "package.json"
        if manifest_path.stat().st_size > 1024 * 1024:
            raise PreflightError("Project package.json exceeds the 1 MiB diagnostic limit")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise PreflightError(f"Cannot read project package.json: {error}") from error
    if not isinstance(manifest, dict):
        raise PreflightError("Project package.json must be an object")
    return project, manifest


def package_manager(project, manifest):
    declared = manifest.get("packageManager")
    if declared:
        if not isinstance(declared, str):
            raise PreflightError("packageManager must be a string")
        name = declared.split("@", 1)[0]
        if name not in ("npm", "pnpm", "yarn", "bun"):
            raise PreflightError(f"Unsupported package manager: {name}")
        return name
    locks = {
        "npm": ("package-lock.json", "npm-shrinkwrap.json"),
        "pnpm": ("pnpm-lock.yaml",),
        "yarn": ("yarn.lock",),
        "bun": ("bun.lock", "bun.lockb"),
    }
    matches = [name for name, files in locks.items() if any((project / f).is_file() for f in files)]
    if len(matches) > 1:
        raise PreflightError("Multiple package-manager lockfiles; confirm the repository's package manager")
    return matches[0] if matches else "npm"


def installed_dependencies(project, manifest, node):
    if any((parent / name).is_file() for parent in (project, *project.parents)
           for name in (".pnp.cjs", ".pnp.js")):
        raise PreflightError(
            "Yarn PnP detected: plain Node cannot verify these dependencies without "
            "loading the project loader. Use the established Yarn environment with "
            "authorization; do not reinstall packages to bypass this diagnostic."
        )
    dependencies = {}
    for field in ("dependencies", "devDependencies"):
        values = manifest.get(field, {})
        if not isinstance(values, dict):
            raise PreflightError(f"package.json {field} must be an object")
        dependencies.update(values)
    remotion = {name: version for name, version in dependencies.items()
                if name == "remotion" or name.startswith("@remotion/")}
    if "remotion" not in remotion:
        raise PreflightError("Selected package has no remotion dependency; select its video package or scaffold one")
    for name, version in remotion.items():
        if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+(?:-[\w.-]+)?", version):
            raise PreflightError(f"{name} must use an exact version, not {version!r}")
    if len(set(remotion.values())) != 1:
        raise PreflightError("All remotion and @remotion/* dependencies must have the same exact version")
    selected = {name: version for name, version in dependencies.items()
                if name in remotion or name in ("react", "react-dom", "typescript")}
    script = """
const fs = require('node:fs');
const root = process.argv[1];
const names = JSON.parse(process.argv[2]);
const result = {};
for (const name of names) {
  try {
    const file = require.resolve(name + '/package.json', {paths: [root]});
    result[name] = {version: JSON.parse(fs.readFileSync(file, 'utf8')).version};
  } catch (error) {
    result[name] = {error: error.message};
  }
}
process.stdout.write(JSON.stringify(result));
"""
    try:
        installed = json.loads(command([node, "-e", script, str(project), json.dumps(list(selected))]))
    except json.JSONDecodeError as error:
        raise PreflightError("Node returned invalid dependency metadata") from error
    if not isinstance(installed, dict):
        raise PreflightError("Node returned an invalid dependency map")
    missing = [name for name in selected if not isinstance(installed.get(name), dict)
               or not installed[name].get("version") or installed[name].get("error")]
    if missing:
        raise PreflightError("Project dependencies missing or unreadable: " + ", ".join(missing))
    mismatched = [name for name, version in remotion.items() if installed[name]["version"] != version]
    if mismatched:
        raise PreflightError("Installed Remotion versions differ from package.json: " + ", ".join(mismatched))
    return {name: installed[name]["version"] for name in selected}


def preflight(engine, *, project=None, captions=False, credits=False,
              transitions=False, music=False, narration=False,
              metadata_only=False, alias=None):
    checks = []

    def check(name, operation, action):
        try:
            detail = operation()
        except (PreflightError, OSError, ValueError, ImportError, RuntimeError) as error:
            checks.append({"id": name, "status": "blocked", "detail": str(error), "action": action})
            return None
        checks.append({"id": name, "status": "pass", "detail": detail})
        return detail

    if engine not in ("remotion", "ffmpeg", "jianying", "download", "compress"):
        raise PreflightError(f"Unknown engine: {engine}")
    if project is not None and engine != "remotion":
        raise PreflightError("--project applies only to the selected Remotion package")
    if (metadata_only or alias is not None) and engine != "download":
        raise PreflightError("--metadata-only and --alias apply only to download preflight")
    if engine in ("download", "compress") and any((captions, credits, transitions, music, narration)):
        raise PreflightError("Download/compression preflight does not edit; check production features with their own engine")
    check("python", python_version,
          "Ask permission for a supported local Python; do not install automatically.")
    limitations = [
        "Local prerequisites only: assets, permissions, media quality and successful export are not verified.",
        "No installation, provider request, authentication or project write was performed.",
    ]
    if engine == "compress":
        from compress_video import preflight_compression

        check("video-compression", preflight_compression,
              "Ask permission to configure FFmpeg/ffprobe with libx264 and AAC; do not install or upload media automatically.")
        limitations.append(
            "Only local compression tools were checked; source compatibility, size savings, "
            "the requested byte ceiling and playback quality require actual output verification."
        )
    elif engine == "download":
        import download_video

        def acquisition_tools():
            result = download_video.doctor(alias)
            if result["status"] == "dependency_error":
                raise PreflightError(result["message"])
            required = ("yt_dlp",) if metadata_only else ("yt_dlp", "ffmpeg", "ffprobe")
            missing = [name for name in required if not result[name]]
            if missing:
                raise PreflightError("Acquisition dependencies missing: " + ", ".join(missing))
            return {
                "operation": "metadata-only" if metadata_only else "download",
                "available": {name: result[name] for name in ("yt_dlp", "ffmpeg", "ffprobe", "js_runtime")},
                "discovery": "Existing selected/PATH or approved managed environment only",
            }

        check("video-acquisition", acquisition_tools,
              "Use the downloader's doctor result; request scoped installation or repair, never another blind environment install.")
        limitations.append(
            "No link, rights, login state, platform extraction or source quality was checked. "
            "Obtain any outstanding scoped permissions before acquisition; native 4K is not guaranteed."
        )
    elif engine == "remotion":
        node = check("node", lambda: executable("node"),
                     "Ask permission to configure Node.js for the affected workspace.")
        context = None
        if project is not None:
            context = check("project", lambda: read_manifest(project),
                            "Select an existing Remotion package, or authorize a new scaffold.")
            if context:
                # Paths and manifest content stay local; report only the selected directory.
                checks[-1]["detail"] = str(context[0])
        if project is None:
            manager = "npm"
        elif context:
            manager = check("package-manager-choice", lambda: package_manager(*context),
                            "Use the repository's established package manager; do not change lockfiles to bypass this.")
        else:
            manager = None
        if manager:
            # Corepack-managed launchers may download on --version.
            check("package-manager", lambda: executable(manager, probe_version=False),
                  f"Ask permission to configure {manager}; preserve the repository's package manager.")
        if context and node:
            check("project-dependencies", lambda: installed_dependencies(*context, node["path"]),
                  "Inspect the reported issue with the repository's package manager; request consent before installation or version alignment.")
        elif project is None:
            checks.append({
                "id": "project-dependencies", "status": "not-checked",
                "detail": "New project: scaffold first, then recheck with --project after approved dependency setup.",
            })
        limitations.append("Package-manager bootstrap, browser, fonts, Remotion license entitlement, composition checks and actual rendering remain separate gates.")
    else:
        import edit_video
        if engine == "ffmpeg":
            check("ffmpeg-renderer", lambda: edit_video.preflight_capabilities(
                captions=captions, credits=credits, transitions=transitions,
                music=music, narration=narration,
            ), "Ask permission to configure FFmpeg/ffprobe with the reported filters/encoders; never omit required captions or credits.")
            limitations.append("Readiness covers only selected flags; validate the final edit plan before rendering.")
        else:
            check("native-media-tools", edit_video.preflight_media_tools,
                  "Ask permission to configure FFmpeg/ffprobe for local media validation; libass is not required for native text.")
            from export_jianying import preflight_dependency
            check("native-draft-api", preflight_dependency,
                  "Ask permission for the compatible optional pyJianYingDraft dependency; never install another fork silently.")
            limitations.append("Experimental: target Jianying version, native opening/export and effect fidelity are unverified; CapCut is not assumed compatible.")
    return {
        "schemaVersion": 1, "engine": engine,
        "status": "blocked" if any(c["status"] == "blocked" for c in checks) else "ready",
        "readinessScope": "local-prerequisites-only", "checks": checks,
        "limitations": limitations,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", choices=("remotion", "ffmpeg", "jianying", "download", "compress"), required=True)
    parser.add_argument("--project", type=Path)
    parser.add_argument("--metadata-only", action="store_true")
    parser.add_argument("--alias", help="Optional host-bound identity for download dependency discovery")
    for flag in ("captions", "credits", "transitions", "music", "narration"):
        parser.add_argument("--" + flag, action="store_true")
    args = parser.parse_args()
    try:
        result = preflight(**vars(args))
    except PreflightError as error:
        print(json.dumps({"status": "blocked", "error": str(error)}))
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
