#!/usr/bin/env python3
"""Materialize the Reel skill's Remotion starter into an empty destination."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path


TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "assets" / "remotion-starter"


def package_name(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")
    if not normalized:
        raise ValueError("Project name must contain at least one letter or number")
    return normalized


def materialize(destination: Path, name: str) -> list[str]:
    destination = destination.expanduser().resolve()
    if destination.exists() and any(destination.iterdir()):
        raise ValueError(f"Destination must be absent or empty: {destination}")
    if not TEMPLATE_DIR.is_dir():
        raise FileNotFoundError(f"Bundled starter is missing: {TEMPLATE_DIR}")

    destination.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    for source in sorted(TEMPLATE_DIR.rglob("*")):
        relative = source.relative_to(TEMPLATE_DIR)
        target = destination / relative
        if source.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        created.append(relative.as_posix())

    manifest = destination / "package.json"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace("{{PACKAGE_NAME}}", package_name(name)),
        encoding="utf-8",
    )
    return created


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--name", required=True, help="npm-compatible project name")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    try:
        created = materialize(args.destination, args.name)
    except (OSError, ValueError) as error:
        parser.error(str(error))

    result = {
        "destination": str(args.destination.expanduser().resolve()),
        "files_created": created,
        "next_steps": [
            "replace REPLACE_ME markers in REEL.md and src/reel/story.json",
            "npm install",
            "npm run validate",
            "npm run check",
            "npm run compositions",
            "npm run still",
        ],
    }
    print(json.dumps(result, indent=2) if args.as_json else f"Created {len(created)} files in {result['destination']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
