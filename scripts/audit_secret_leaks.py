#!/usr/bin/env python3
"""Scan repository and evidence artifacts for exact configured secret values."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import zipfile
from pathlib import Path


SECRET_NAMES = (
    "DEEPSEEK_TEXT_API_KEY",
    "VOLCENGINE_VISION_API_KEY",
    "SILICONFLOW_OCR_API_KEY",
)


def _git_paths(repo: Path, *args: str) -> list[Path]:
    result = subprocess.run(["git", *args, "-z"], cwd=repo, capture_output=True, check=True)
    return [repo / item.decode("utf-8", "surrogateescape") for item in result.stdout.split(b"\0") if item]


def _safe_read(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError:
        return b""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--workspace", type=Path)
    parser.add_argument("--zip", dest="zip_path", type=Path)
    args = parser.parse_args()
    repo = args.repo.resolve()
    secrets = {name: os.environ.get(name, "").encode() for name in SECRET_NAMES}
    configured = {name: value for name, value in secrets.items() if value}

    sources: list[tuple[str, str, bytes]] = []
    for path in _git_paths(repo, "ls-files"):
        if path.is_file():
            sources.append(("git_tracked", str(path.relative_to(repo)), _safe_read(path)))
    for path in _git_paths(repo, "ls-files", "--others", "--exclude-standard"):
        if path.is_file():
            sources.append(("git_untracked", str(path.relative_to(repo)), _safe_read(path)))
    diff = subprocess.run(["git", "diff", "--binary"], cwd=repo, capture_output=True, check=True).stdout
    sources.append(("git_diff", "working_tree", diff))
    if args.workspace and args.workspace.exists():
        for path in args.workspace.rglob("*"):
            if path.is_file():
                sources.append(("workspace", str(path), _safe_read(path)))
    if args.zip_path and args.zip_path.is_file():
        with zipfile.ZipFile(args.zip_path) as archive:
            for name in archive.namelist():
                if not name.endswith("/"):
                    sources.append(("zip", name, archive.read(name)))

    failed = False
    for env_name in SECRET_NAMES:
        value = configured.get(env_name)
        if not value:
            print(f"{env_name}: not configured")
            continue
        matches = [(kind, label) for kind, label, content in sources if value in content]
        if matches:
            failed = True
            print(f"{env_name}: exact match found ({len(matches)} location(s))")
            for kind, label in matches:
                print(f"  {kind}: {label}")
        else:
            print(f"{env_name}: no exact match found")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
