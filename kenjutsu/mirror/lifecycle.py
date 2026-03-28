"""Bare mirror lifecycle management.

Handles clone, fetch, and delete operations for persistent bare git mirrors.
Storage path is configurable via KENJUTSU_MIRROR_PATH env var.

Architecture ref: research/kenjutsu-architecture-v3.md § 15
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

_DEFAULT_MIRROR_PATH = Path("/var/lib/kenjutsu/mirrors")
_DEFAULT_THRESHOLD = 1 * 1024**3  # 1 GB


class MirrorError(Exception):
    """Base class for mirror lifecycle errors."""


class MirrorAlreadyExistsError(MirrorError):
    """Raised when a mirror already exists at the target path."""


class MirrorNotFoundError(MirrorError):
    """Raised when an expected mirror is absent."""


class MirrorCloneError(MirrorError):
    """Raised when git clone fails."""


class MirrorFetchError(MirrorError):
    """Raised when git fetch fails."""


@dataclass(frozen=True)
class MirrorConfig:
    """Configuration for mirror storage.

    storage_path defaults to KENJUTSU_MIRROR_PATH env var, falling back to
    /var/lib/kenjutsu/mirrors.  Pass an explicit value to override both.
    """

    storage_path: Path = field(
        default_factory=lambda: Path(os.getenv("KENJUTSU_MIRROR_PATH", str(_DEFAULT_MIRROR_PATH)))
    )
    large_repo_threshold_bytes: int = _DEFAULT_THRESHOLD
    blob_size_limit: str = "1m"


def mirror_path(config: MirrorConfig, repo_id: str) -> Path:
    """Return the filesystem path for a repo's bare mirror."""
    return config.storage_path / repo_id


def clone_mirror(
    repo_url: str,
    repo_id: str,
    config: MirrorConfig,
    repo_size_bytes: int = 0,
) -> Path:
    """Clone a bare mirror of the given repo.

    Uses blob filter for repos exceeding config.large_repo_threshold_bytes
    (partial clone — blobs fetched on demand during parsing).

    Returns the path to the newly-created mirror.
    Raises MirrorAlreadyExistsError if the mirror already exists.
    Raises MirrorCloneError on git failure.
    """
    dest = mirror_path(config, repo_id)
    if dest.exists():
        raise MirrorAlreadyExistsError(f"Mirror already exists at {dest}")

    cmd = ["git", "clone", "--bare"]
    if repo_size_bytes >= config.large_repo_threshold_bytes:
        cmd.append(f"--filter=blob:limit={config.blob_size_limit}")
    cmd += [repo_url, str(dest)]

    result = subprocess.run(cmd, capture_output=True, text=True)  # noqa: S603
    if result.returncode != 0:
        raise MirrorCloneError(result.stderr)

    # git clone --bare does not write a fetch refspec — configure it explicitly
    # so that subsequent git fetch --prune updates all refs from the remote.
    cfg = subprocess.run(
        ["git", "config", "remote.origin.fetch", "+refs/*:refs/*"],  # noqa: S607
        capture_output=True,
        text=True,
        cwd=str(dest),
    )
    if cfg.returncode != 0:
        raise MirrorCloneError(f"Failed to configure fetch refspec: {cfg.stderr}")

    return dest


def fetch_mirror(repo_id: str, config: MirrorConfig) -> None:
    """Fetch updates into an existing bare mirror.

    Should be called on push/PR webhook events to keep the mirror current.
    Raises MirrorNotFoundError if the mirror doesn't exist.
    Raises MirrorFetchError on git failure.
    """
    dest = mirror_path(config, repo_id)
    if not dest.exists():
        raise MirrorNotFoundError(f"Mirror not found at {dest}")

    result = subprocess.run(
        ["git", "fetch", "--prune"],  # noqa: S607
        capture_output=True,
        text=True,
        cwd=str(dest),
    )
    if result.returncode != 0:
        raise MirrorFetchError(result.stderr)


def delete_mirror(repo_id: str, config: MirrorConfig) -> None:
    """Delete a bare mirror.

    Called on app uninstall.  Idempotent — no error if mirror is absent.
    """
    dest = mirror_path(config, repo_id)
    if dest.exists():
        shutil.rmtree(dest)


def mirror_size_bytes(repo_id: str, config: MirrorConfig) -> int:
    """Return total disk usage of a mirror in bytes.

    Raises MirrorNotFoundError if the mirror doesn't exist.
    """
    dest = mirror_path(config, repo_id)
    if not dest.exists():
        raise MirrorNotFoundError(f"Mirror not found at {dest}")
    return sum(f.stat().st_size for f in dest.rglob("*") if f.is_file())


def all_mirror_sizes(config: MirrorConfig) -> dict[str, int]:
    """Return a mapping of repo_id -> size_bytes for every mirror.

    Returns an empty dict if the storage path doesn't exist yet.
    """
    if not config.storage_path.exists():
        return {}
    return {
        entry.name: sum(f.stat().st_size for f in entry.rglob("*") if f.is_file())
        for entry in config.storage_path.iterdir()
        if entry.is_dir()
    }
