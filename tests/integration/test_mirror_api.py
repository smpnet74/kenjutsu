"""Integration tests for mirror internal API — real git repos, temp dirs.

Uses the same local-bare-repo fixture pattern as test_mirror_lifecycle.py.
No network access required.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from kenjutsu.mirror.api import CommitInfo, MirrorHandle, MirrorReadError, get_mirror
from kenjutsu.mirror.lifecycle import MirrorConfig, MirrorNotFoundError, clone_mirror


@pytest.fixture()
def local_remote(tmp_path: Path) -> Path:
    """Create a local bare repo with two commits (to have a meaningful diff)."""
    src = tmp_path / "source"
    src.mkdir()
    subprocess.run(["git", "init", str(src)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(src), "config", "user.email", "t@t.com"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(src), "config", "user.name", "T"], check=True, capture_output=True)
    (src / "README.md").write_text("# hello\n")
    subprocess.run(["git", "-C", str(src), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(src), "commit", "-m", "first commit"], check=True, capture_output=True)
    (src / "app.py").write_text("def main(): pass\n")
    subprocess.run(["git", "-C", str(src), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(src), "commit", "-m", "add app"], check=True, capture_output=True)

    bare = tmp_path / "remote.git"
    subprocess.run(["git", "clone", "--bare", str(src), str(bare)], check=True, capture_output=True)
    return bare


@pytest.fixture()
def mirror_store(tmp_path: Path) -> Path:
    store = tmp_path / "mirrors"
    store.mkdir()
    return store


@pytest.fixture()
def cloned_mirror(local_remote: Path, mirror_store: Path) -> tuple[Path, MirrorConfig]:
    config = MirrorConfig(storage_path=mirror_store)
    clone_mirror(str(local_remote), "test-repo", config)
    return mirror_store / "test-repo", config


def _head_sha(mirror_dir: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(mirror_dir),
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _parent_sha(mirror_dir: Path, sha: str) -> str:
    result = subprocess.run(
        ["git", "rev-parse", f"{sha}^"],
        cwd=str(mirror_dir),
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


class TestGetMirrorIntegration:
    def test_returns_handle_for_existing_mirror(self, cloned_mirror: tuple[Path, MirrorConfig]) -> None:
        _, config = cloned_mirror
        handle = get_mirror("test-repo", config)
        assert isinstance(handle, MirrorHandle)
        assert handle.repo_id == "test-repo"

    def test_raises_for_missing_mirror(self, mirror_store: Path) -> None:
        config = MirrorConfig(storage_path=mirror_store)
        with pytest.raises(MirrorNotFoundError):
            get_mirror("nonexistent", config)


class TestDiffIntegration:
    def test_diff_returns_nonempty_output(self, cloned_mirror: tuple[Path, MirrorConfig]) -> None:
        mirror_dir, config = cloned_mirror
        handle = get_mirror("test-repo", config)
        head = _head_sha(mirror_dir)
        parent = _parent_sha(mirror_dir, head)

        diff = handle.diff(parent, head)

        assert diff  # non-empty — the second commit added app.py
        assert "app.py" in diff

    def test_diff_empty_for_same_sha(self, cloned_mirror: tuple[Path, MirrorConfig]) -> None:
        mirror_dir, config = cloned_mirror
        handle = get_mirror("test-repo", config)
        head = _head_sha(mirror_dir)

        diff = handle.diff(head, head)

        assert diff == ""

    def test_diff_invalid_sha_raises(self, cloned_mirror: tuple[Path, MirrorConfig]) -> None:
        _, config = cloned_mirror
        handle = get_mirror("test-repo", config)

        with pytest.raises(MirrorReadError):
            handle.diff("deadbeef000", "cafebabe000")


class TestReadFileIntegration:
    def test_read_file_returns_contents(self, cloned_mirror: tuple[Path, MirrorConfig]) -> None:
        mirror_dir, config = cloned_mirror
        handle = get_mirror("test-repo", config)
        head = _head_sha(mirror_dir)

        contents = handle.read_file(head, "README.md")

        assert "hello" in contents

    def test_read_file_at_earlier_commit_before_file_existed(self, cloned_mirror: tuple[Path, MirrorConfig]) -> None:
        mirror_dir, config = cloned_mirror
        handle = get_mirror("test-repo", config)
        head = _head_sha(mirror_dir)
        parent = _parent_sha(mirror_dir, head)

        # app.py was added in head commit — must not exist at parent
        with pytest.raises(MirrorReadError):
            handle.read_file(parent, "app.py")

    def test_read_file_nonexistent_path_raises(self, cloned_mirror: tuple[Path, MirrorConfig]) -> None:
        mirror_dir, config = cloned_mirror
        handle = get_mirror("test-repo", config)
        head = _head_sha(mirror_dir)

        with pytest.raises(MirrorReadError):
            handle.read_file(head, "does/not/exist.py")


class TestGitLogIntegration:
    def test_log_returns_commits(self, cloned_mirror: tuple[Path, MirrorConfig]) -> None:
        _, config = cloned_mirror
        handle = get_mirror("test-repo", config)

        commits = handle.git_log()

        assert len(commits) >= 2
        assert all(isinstance(c, CommitInfo) for c in commits)

    def test_log_newest_first(self, cloned_mirror: tuple[Path, MirrorConfig]) -> None:
        _, config = cloned_mirror
        handle = get_mirror("test-repo", config)

        commits = handle.git_log()

        assert commits[0].message == "add app"
        assert commits[1].message == "first commit"

    def test_log_respects_n(self, cloned_mirror: tuple[Path, MirrorConfig]) -> None:
        _, config = cloned_mirror
        handle = get_mirror("test-repo", config)

        commits = handle.git_log(n=1)

        assert len(commits) == 1
        assert commits[0].message == "add app"

    def test_log_scoped_to_file(self, cloned_mirror: tuple[Path, MirrorConfig]) -> None:
        _, config = cloned_mirror
        handle = get_mirror("test-repo", config)

        # README.md was touched only in the first commit
        commits = handle.git_log(path="README.md")

        assert len(commits) == 1
        assert commits[0].message == "first commit"

    def test_log_commit_fields_populated(self, cloned_mirror: tuple[Path, MirrorConfig]) -> None:
        _, config = cloned_mirror
        handle = get_mirror("test-repo", config)

        commits = handle.git_log(n=1)
        c = commits[0]

        assert len(c.sha) == 40  # full SHA
        assert c.author  # non-empty
        assert c.date  # non-empty
        assert c.message == "add app"
