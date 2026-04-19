"""Thin wrapper around `git` to fetch branch, last commit, and working-tree
status for a watched folder. Silently returns None if the folder isn't a
git repo or git isn't installed."""
from __future__ import annotations

import subprocess
from pathlib import Path


def _run(cmd: list[str], cwd: Path, timeout: float = 2.0) -> str | None:
    try:
        r = subprocess.run(
            cmd, cwd=str(cwd), capture_output=True, text=True,
            timeout=timeout, check=False,
        )
        if r.returncode != 0:
            return None
        return r.stdout.strip()
    except Exception:
        return None


def get_git_info(folder: Path) -> dict | None:
    # Quick probe: is this (or any parent) a git repo?
    if _run(["git", "rev-parse", "--is-inside-work-tree"], folder) != "true":
        return None

    branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], folder) or "?"
    last_commit = _run(
        ["git", "log", "-1", "--pretty=format:%h  %s  (%an, %ar)"], folder
    ) or ""

    porcelain = _run(["git", "status", "--porcelain"], folder) or ""
    dirty_files: list[tuple[str, str]] = []
    for line in porcelain.splitlines():
        if len(line) < 3:
            continue
        code = line[:2].strip() or "?"
        path = line[3:]
        dirty_files.append((code, path))

    ahead_behind = _run(
        ["git", "rev-list", "--left-right", "--count", "@{upstream}...HEAD"], folder
    )
    ahead = behind = None
    if ahead_behind:
        parts = ahead_behind.split()
        if len(parts) == 2:
            behind, ahead = parts

    return {
        "branch": branch,
        "last_commit": last_commit,
        "dirty": dirty_files,
        "ahead": ahead,
        "behind": behind,
    }
