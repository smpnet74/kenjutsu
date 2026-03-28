"""Integration tests for mirror lifecycle — real git operations, temp directories.

These tests exercise clone/fetch/delete against actual git repos created locally.
No network access required: a local bare repo is used as the remote.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from kenjutsu.mirror.lifecycle import (
    MirrorAlreadyExistsError,
    MirrorConfig,
    MirrorNotFoundError,
    all_mirror_sizes,
    clone_mirror,
    delete_mirror,
    fetch_mirror,
    mirror_size_bytes,
)


@pytest.fixture()
def local_remote(tmp_path: Path) -> Path:
    """Create a minimal local bare git repo to act as a remote.

    Adds one commit so the repo has a HEAD and at least one object.
    Returns the path to the bare repo.
    """
    src = tmp_path / "source"
    src.mkdir()
    subprocess.run(["git", "init", str(src)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(src), "config", "user.email", "test@test.com"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(src), "config", "user.name", "Test"], check=True, capture_output=True)
    (src / "README.md").write_text("# test\n")
    subprocess.run(["git", "-C", str(src), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(src), "commit", "-m", "init"], check=True, capture_output=True)

    bare = tmp_path / "remote.git"
    subprocess.run(["git", "clone", "--bare", str(src), str(bare)], check=True, capture_output=True)
    return bare


@pytest.fixture()
def mirror_store(tmp_path: Path) -> Path:
    """Return an empty directory to use as the mirror storage root."""
    store = tmp_path / "mirrors"
    store.mkdir()
    return store


class TestCloneMirrorIntegration:
    def test_clone_creates_bare_mirror(self, local_remote: Path, mirror_store: Path) -> None:
        config = MirrorConfig(storage_path=mirror_store)

        result = clone_mirror(str(local_remote), "test-repo", config)

        assert result == mirror_store / "test-repo"
        assert result.is_dir()
        # Bare repos have a HEAD file directly in the directory
        assert (result / "HEAD").exists()

    def test_clone_contains_objects(self, local_remote: Path, mirror_store: Path) -> None:
        config = MirrorConfig(storage_path=mirror_store)

        clone_mirror(str(local_remote), "test-repo", config)

        objects_dir = mirror_store / "test-repo" / "objects"
        assert objects_dir.is_dir()

    def test_clone_raises_if_already_exists(self, local_remote: Path, mirror_store: Path) -> None:
        config = MirrorConfig(storage_path=mirror_store)
        (mirror_store / "test-repo").mkdir()

        with pytest.raises(MirrorAlreadyExistsError):
            clone_mirror(str(local_remote), "test-repo", config)


class TestFetchMirrorIntegration:
    def test_fetch_succeeds_on_existing_mirror(self, local_remote: Path, mirror_store: Path) -> None:
        config = MirrorConfig(storage_path=mirror_store)
        clone_mirror(str(local_remote), "test-repo", config)

        # Should not raise
        fetch_mirror("test-repo", config)

    def test_fetch_picks_up_new_commits(self, local_remote: Path, mirror_store: Path, tmp_path: Path) -> None:
        config = MirrorConfig(storage_path=mirror_store)
        clone_mirror(str(local_remote), "test-repo", config)

        # Add a new commit to the remote by pushing from a fresh working clone
        src = tmp_path / "push-src"
        subprocess.run(["git", "clone", str(local_remote), str(src)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(src), "config", "user.email", "t@t.com"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(src), "config", "user.name", "T"], check=True, capture_output=True)
        (src / "new_file.txt").write_text("new content\n")
        subprocess.run(["git", "-C", str(src), "add", "."], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(src), "commit", "-m", "second commit"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(src), "push"], check=True, capture_output=True)

        # Fetch should update the mirror with the new commit
        fetch_mirror("test-repo", config)

        result = subprocess.run(
            ["git", "log", "--oneline", "--all"],
            cwd=str(mirror_store / "test-repo"),
            capture_output=True,
            text=True,
            check=True,
        )
        assert "second commit" in result.stdout

    def test_fetch_raises_if_mirror_absent(self, mirror_store: Path) -> None:
        config = MirrorConfig(storage_path=mirror_store)

        with pytest.raises(MirrorNotFoundError):
            fetch_mirror("nonexistent", config)


class TestDeleteMirrorIntegration:
    def test_delete_removes_cloned_mirror(self, local_remote: Path, mirror_store: Path) -> None:
        config = MirrorConfig(storage_path=mirror_store)
        clone_mirror(str(local_remote), "test-repo", config)
        assert (mirror_store / "test-repo").exists()

        delete_mirror("test-repo", config)

        assert not (mirror_store / "test-repo").exists()

    def test_delete_idempotent(self, mirror_store: Path) -> None:
        config = MirrorConfig(storage_path=mirror_store)
        delete_mirror("never-existed", config)  # must not raise


class TestStorageIntegration:
    def test_mirror_size_bytes_nonzero_after_clone(self, local_remote: Path, mirror_store: Path) -> None:
        config = MirrorConfig(storage_path=mirror_store)
        clone_mirror(str(local_remote), "test-repo", config)

        size = mirror_size_bytes("test-repo", config)

        assert size > 0

    def test_all_mirror_sizes_reflects_cloned_repos(self, local_remote: Path, mirror_store: Path) -> None:
        config = MirrorConfig(storage_path=mirror_store)
        clone_mirror(str(local_remote), "repo-a", config)
        clone_mirror(str(local_remote), "repo-b", config)

        sizes = all_mirror_sizes(config)

        assert set(sizes.keys()) == {"repo-a", "repo-b"}
        assert sizes["repo-a"] > 0
        assert sizes["repo-b"] > 0
