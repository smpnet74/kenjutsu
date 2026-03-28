"""Internal mirror API — thread-safe read access to bare mirrors.

Provides MirrorHandle for diff, file read, and log operations, plus
a get_mirror() entry point and serialized-per-repo fetch support.

Architecture ref: research/kenjutsu-architecture-v3.md § 15
"""

from __future__ import annotations

import subprocess
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING

from kenjutsu.mirror.lifecycle import MirrorConfig, MirrorNotFoundError, fetch_mirror, mirror_path

if TYPE_CHECKING:
    from pathlib import Path


class MirrorReadError(Exception):
    """Raised when a read operation (diff, show, log) fails."""


@dataclass(frozen=True)
class CommitInfo:
    """Lightweight representation of a single git commit."""

    sha: str
    author: str
    date: str
    message: str


# Per-repo fetch locks — one Lock per repo_id, created on first access.
# Reads (diff, show, log) are naturally concurrent-safe in bare repos and
# require no locking.  Writes (fetch) are serialized per repo.
_fetch_lock_map: dict[str, threading.Lock] = {}
_fetch_lock_map_guard = threading.Lock()


def _repo_fetch_lock(repo_id: str) -> threading.Lock:
    """Return (or create) the per-repo fetch Lock."""
    with _fetch_lock_map_guard:
        if repo_id not in _fetch_lock_map:
            _fetch_lock_map[repo_id] = threading.Lock()
        return _fetch_lock_map[repo_id]


class MirrorHandle:
    """Thread-safe read handle for a bare mirror.

    Read operations (diff, read_file, git_log) are inherently concurrent-safe
    against each other.  The fetch() method acquires a per-repo lock to
    prevent concurrent fetches from racing.
    """

    def __init__(self, repo_id: str, path: Path) -> None:
        self._repo_id = repo_id
        self._path = path

    @property
    def repo_id(self) -> str:
        return self._repo_id

    @property
    def path(self) -> Path:
        return self._path

    def diff(self, base_sha: str, head_sha: str) -> str:
        """Return unified diff between base_sha and head_sha.

        Raises MirrorReadError on git failure.
        """
        result = subprocess.run(  # noqa: S603
            ["git", "diff", base_sha, head_sha],  # noqa: S607
            cwd=str(self._path),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise MirrorReadError(f"git diff failed: {result.stderr.strip()}")
        return result.stdout

    def read_file(self, sha: str, path: str) -> str:
        """Return the contents of a file at a specific commit.

        Raises MirrorReadError if the path doesn't exist at that commit or on
        git failure.
        """
        result = subprocess.run(  # noqa: S603
            ["git", "show", f"{sha}:{path}"],  # noqa: S607
            cwd=str(self._path),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise MirrorReadError(f"git show failed: {result.stderr.strip()}")
        return result.stdout

    def git_log(self, path: str | None = None, n: int = 50) -> list[CommitInfo]:
        """Return up to n commits, optionally scoped to a file path.

        Commits are returned in reverse-chronological order (newest first).
        Raises MirrorReadError on git failure.
        """
        cmd: list[str] = [
            "git",
            "log",
            f"--max-count={n}",
            "--format=%H%x00%an%x00%ai%x00%s",
        ]
        if path is not None:
            cmd += ["--", path]
        result = subprocess.run(  # noqa: S603
            cmd,
            cwd=str(self._path),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise MirrorReadError(f"git log failed: {result.stderr.strip()}")
        commits: list[CommitInfo] = []
        for line in result.stdout.strip().splitlines():
            if line.strip():
                sha, author, date, message = line.split("\x00", 3)
                commits.append(CommitInfo(sha=sha, author=author, date=date, message=message))
        return commits

    def fetch(self, config: MirrorConfig | None = None) -> None:
        """Fetch remote updates into this mirror.

        Serialized per repo — only one fetch runs at a time for a given
        repo_id.  Concurrent callers block until the in-flight fetch
        completes, then return immediately (no duplicate fetch).
        """
        if config is None:
            config = MirrorConfig()
        lock = _repo_fetch_lock(self._repo_id)
        with lock:
            fetch_mirror(self._repo_id, config)


def get_mirror(repo_id: str, config: MirrorConfig | None = None) -> MirrorHandle:
    """Return a MirrorHandle for the given repo.

    Raises MirrorNotFoundError if no mirror exists for repo_id.
    """
    if config is None:
        config = MirrorConfig()
    path = mirror_path(config, repo_id)
    if not path.exists():
        raise MirrorNotFoundError(f"Mirror not found for repo {repo_id!r} at {path}")
    return MirrorHandle(repo_id=repo_id, path=path)
