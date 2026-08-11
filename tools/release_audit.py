#!/usr/bin/env python3
"""Fail-closed hygiene checks for the public GeNewWord Engine source tree."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


REQUIRED_FILES = {
    "LICENSE",
    "NOTICE",
    "THIRD_PARTY_NOTICES.md",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "CITATION.cff",
    "DCO",
    "README.md",
    "README.zh-CN.md",
    "pyproject.toml",
    "package.json",
    "package-lock.json",
}
ALLOWED_ROOT_FILES = REQUIRED_FILES | {
    ".gitattributes",
    ".gitignore",
    "CHANGELOG.md",
    "GOVERNANCE.md",
    "PROVENANCE.md",
    "RELEASE_CHECKLIST.md",
    "SUPPORT.md",
}
ALLOWED_ROOT_DIRS = {".github", "docs", "scripts", "tests", "tools", "world_engine"}
IGNORED_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", "dist", "build", ".pytest_cache"}
FORBIDDEN_DIRS = {
    ".agents",
    ".codex",
    "archives",
    "evidence",
    "output",
    "outputs",
    "papers",
    "phase0",
    "references",
    "runs",
    "standard_packages",
    "versions",
}
FORBIDDEN_SUFFIXES = {
    ".7z",
    ".avi",
    ".db",
    ".gz",
    ".info.json",
    ".mhtml",
    ".mkv",
    ".mov",
    ".mp4",
    ".pdf",
    ".pickle",
    ".pkl",
    ".srt",
    ".sqlite",
    ".sqlite3",
    ".tar",
    ".vtt",
    ".webm",
    ".zip",
}
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 25 * 1024 * 1024
TEXT_SCAN_LIMIT_BYTES = 2 * 1024 * 1024
FORBIDDEN_TEXT = {
    "absolute macOS home path": re.compile(r"/Users/[A-Za-z0-9._-]+/"),
    "Codex-private dependency path": re.compile(r"(?:^|[/\\])\.codex(?:[/\\])"),
    "personal iCloud email": re.compile(r"[A-Za-z0-9._%+-]+@icloud\.com", re.IGNORECASE),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "GitHub token": re.compile(r"\b(?:ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})\b"),
    "OpenAI token": re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "signed URL parameter": re.compile(
        r"(?:X-Amz-(?:Signature|Credential|Security-Token)|[?&](?:ip|expire|expires)=)",
        re.IGNORECASE,
    ),
}


def _is_ignored(relative: Path) -> bool:
    return any(part in IGNORED_DIRS or part.endswith(".egg-info") for part in relative.parts)


def _iter_source_files(root: Path):
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if _is_ignored(relative):
            continue
        if path.is_file() or path.is_symlink():
            yield path, relative


def audit_tree(root: Path) -> list[str]:
    root = root.resolve()
    failures: list[str] = []
    if not root.is_dir():
        return [f"release root does not exist: {root}"]

    root_names = {path.name for path in root.iterdir() if not _is_ignored(Path(path.name))}
    for missing in sorted(REQUIRED_FILES - root_names):
        failures.append(f"missing required release file: {missing}")
    for path in sorted(root.iterdir(), key=lambda item: item.name):
        if _is_ignored(Path(path.name)):
            continue
        if path.is_dir() and path.name not in ALLOWED_ROOT_DIRS:
            failures.append(f"unapproved root directory: {path.name}")
        if path.is_file() and path.name not in ALLOWED_ROOT_FILES:
            failures.append(f"unapproved root file: {path.name}")

    total_bytes = 0
    for path, relative in _iter_source_files(root):
        if path.is_symlink():
            failures.append(f"symlink is not allowed: {relative}")
            continue
        if any(part in FORBIDDEN_DIRS for part in relative.parts):
            failures.append(f"forbidden path family: {relative}")
        lower_name = path.name.lower()
        if any(lower_name.endswith(suffix) for suffix in FORBIDDEN_SUFFIXES):
            failures.append(f"forbidden file type: {relative}")
        size = path.stat().st_size
        total_bytes += size
        if size > MAX_FILE_BYTES:
            failures.append(f"file exceeds {MAX_FILE_BYTES} byte limit: {relative} ({size})")
        if size > TEXT_SCAN_LIMIT_BYTES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            failures.append(f"undeclared binary file: {relative}")
            continue
        for label, pattern in FORBIDDEN_TEXT.items():
            if pattern.search(text):
                failures.append(f"{label}: {relative}")
    if total_bytes > MAX_TOTAL_BYTES:
        failures.append(f"tree exceeds {MAX_TOTAL_BYTES} byte limit: {total_bytes}")

    license_path = root / "LICENSE"
    if license_path.is_file() and "Apache License" not in license_path.read_text(encoding="utf-8", errors="replace"):
        failures.append("LICENSE is not recognizable as Apache-2.0")
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=Path(__file__).resolve().parents[1], type=Path)
    args = parser.parse_args(argv)
    failures = audit_tree(args.root)
    if failures:
        print("release audit failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("release audit passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
