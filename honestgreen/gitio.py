"""Thin wrapper around the git CLI."""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


class GitError(RuntimeError):
    pass


def git(repo: Path, *args: str, check: bool = True) -> str:
    proc = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise GitError(proc.stderr.strip() or f"git {' '.join(args)} failed")
    return proc.stdout


@dataclass
class Change:
    status: str          # A, M, D, R
    old_path: str | None
    new_path: str | None


def merge_base(repo: Path, base: str, head: str) -> str:
    out = git(repo, "merge-base", base, head, check=False).strip()
    return out or git(repo, "rev-parse", base).strip()


def changes(repo: Path, base_commit: str, head: str | None) -> list[Change]:
    """Changed files between base_commit and head (or the working tree if head is None)."""
    args = ["diff", "--name-status", "-M", "-z", base_commit]
    if head:
        args.append(head)
    parts = git(repo, *args).split("\0")
    out, i = [], 0
    while i < len(parts) and parts[i]:
        status = parts[i][0]
        if status in "RC":
            out.append(Change("R", parts[i + 1], parts[i + 2]))
            i += 3
        else:
            path = parts[i + 1]
            out.append(Change(status, None if status == "A" else path, None if status == "D" else path))
            i += 2
    if head is None:  # untracked files are new in the working tree
        for path in git(repo, "ls-files", "--others", "--exclude-standard", "-z").split("\0"):
            if path:
                out.append(Change("A", None, path))
    return out


def read_at(repo: Path, commit: str, path: str) -> str | None:
    proc = subprocess.run(["git", "-C", str(repo), "show", f"{commit}:{path}"],
                          capture_output=True, text=True)
    return proc.stdout if proc.returncode == 0 else None


def read_head(repo: Path, head: str | None, path: str) -> str | None:
    if head:
        return read_at(repo, head, path)
    file = repo / path
    return file.read_text(errors="replace") if file.is_file() else None


def numstat(repo: Path, base_commit: str, head: str | None) -> dict[str, tuple[int, int]]:
    """{path: (lines added, lines removed)}; binary files count as (0, 0)."""
    args = ["diff", "--numstat", "-M", base_commit] + ([head] if head else [])
    out: dict[str, tuple[int, int]] = {}
    for line in git(repo, *args).splitlines():
        added, removed, path = line.split("\t", 2)
        if " => " in path:  # rename: "a => b" or "dir/{a => b}"
            path = re.sub(r"\{[^}]* => ([^}]*)\}", r"\1", path)
            path = path.split(" => ")[-1]
        out[path] = (int(added) if added.isdigit() else 0, int(removed) if removed.isdigit() else 0)
    if head is None:
        for path in git(repo, "ls-files", "--others", "--exclude-standard", "-z").split("\0"):
            if path and (repo / path).is_file():
                out[path] = (len((repo / path).read_text(errors="replace").splitlines()), 0)
    return out


def files_at(repo: Path, commit: str) -> list[str]:
    return [p for p in git(repo, "ls-tree", "-r", "--name-only", "-z", commit).split("\0") if p]


def commit_messages(repo: Path, base_commit: str, head: str | None) -> list[str]:
    out = git(repo, "log", "--format=%B%x00", f"{base_commit}..{head or 'HEAD'}", check=False)
    return [m.strip() for m in out.split("\0") if m.strip()]
