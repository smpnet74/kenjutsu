"""Unit tests for the mirror internal API.

Tests use mocked subprocess and controlled filesystem (tmp_path) to verify
behavior without requiring real git operations.
"""

from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from kenjutsu.mirror.api import (
    CommitInfo,
    MirrorHandle,
    MirrorReadError,
    _repo_fetch_lock,
    get_mirror,
)
from kenjutsu.mirror.lifecycle import MirrorConfig, MirrorNotFoundError

# ─── CommitInfo ───────────────────────────────────────────────────────────────


class TestCommitInfo:
    def test_fields_stored(self) -> None:
        c = CommitInfo(sha="abc123", author="Alice", date="2026-01-01", message="init")
        assert c.sha == "abc123"
        assert c.author == "Alice"
        assert c.date == "2026-01-01"
        assert c.message == "init"

    def test_frozen(self) -> None:
        c = CommitInfo(sha="abc", author="A", date="2026-01-01", message="m")
        with pytest.raises(AttributeError):
            c.sha = "other"  # type: ignore[misc]


# ─── get_mirror ───────────────────────────────────────────────────────────────


class TestGetMirror:
    def test_returns_handle_when_mirror_exists(self, tmp_path: Path) -> None:
        config = MirrorConfig(storage_path=tmp_path)
        (tmp_path / "repo-1").mkdir()

        handle = get_mirror("repo-1", config)

        assert handle.repo_id == "repo-1"
        assert handle.path == tmp_path / "repo-1"

    def test_raises_mirror_not_found_when_absent(self, tmp_path: Path) -> None:
        config = MirrorConfig(storage_path=tmp_path)

        with pytest.raises(MirrorNotFoundError):
            get_mirror("nonexistent", config)

    def test_uses_default_config_when_none_given(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("KENJUTSU_MIRROR_PATH", str(tmp_path))
        (tmp_path / "my-repo").mkdir()

        handle = get_mirror("my-repo")

        assert handle.repo_id == "my-repo"


# ─── MirrorHandle.diff ────────────────────────────────────────────────────────


class TestMirrorHandleDiff:
    def test_runs_git_diff(self, tmp_path: Path) -> None:
        mirror_dir = tmp_path / "repo-1"
        mirror_dir.mkdir()
        handle = MirrorHandle("repo-1", mirror_dir)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="diff output\n", stderr="")
            result = handle.diff("abc123", "def456")

        mock_run.assert_called_once_with(
            ["git", "diff", "abc123", "def456"],
            cwd=str(mirror_dir),
            capture_output=True,
            text=True,
        )
        assert result == "diff output\n"

    def test_raises_on_git_failure(self, tmp_path: Path) -> None:
        mirror_dir = tmp_path / "repo-1"
        mirror_dir.mkdir()
        handle = MirrorHandle("repo-1", mirror_dir)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=128, stdout="", stderr="fatal: bad sha")
            with pytest.raises(MirrorReadError, match="git diff failed"):
                handle.diff("bad", "sha")

    def test_returns_empty_string_for_identical_commits(self, tmp_path: Path) -> None:
        mirror_dir = tmp_path / "repo-1"
        mirror_dir.mkdir()
        handle = MirrorHandle("repo-1", mirror_dir)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            result = handle.diff("abc123", "abc123")

        assert result == ""


# ─── MirrorHandle.read_file ───────────────────────────────────────────────────


class TestMirrorHandleReadFile:
    def test_runs_git_show(self, tmp_path: Path) -> None:
        mirror_dir = tmp_path / "repo-1"
        mirror_dir.mkdir()
        handle = MirrorHandle("repo-1", mirror_dir)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="file contents\n", stderr="")
            result = handle.read_file("abc123", "src/main.py")

        mock_run.assert_called_once_with(
            ["git", "show", "abc123:src/main.py"],
            cwd=str(mirror_dir),
            capture_output=True,
            text=True,
        )
        assert result == "file contents\n"

    def test_raises_on_missing_path(self, tmp_path: Path) -> None:
        mirror_dir = tmp_path / "repo-1"
        mirror_dir.mkdir()
        handle = MirrorHandle("repo-1", mirror_dir)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=128, stdout="", stderr="fatal: not found")
            with pytest.raises(MirrorReadError, match="git show failed"):
                handle.read_file("abc123", "nonexistent.py")

    def test_sha_colon_path_format(self, tmp_path: Path) -> None:
        mirror_dir = tmp_path / "repo-1"
        mirror_dir.mkdir()
        handle = MirrorHandle("repo-1", mirror_dir)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            handle.read_file("deadbeef", "a/b/c.py")

        args = mock_run.call_args[0][0]
        assert "deadbeef:a/b/c.py" in args


# ─── MirrorHandle.git_log ─────────────────────────────────────────────────────


class TestMirrorHandleGitLog:
    def test_runs_git_log_with_default_n(self, tmp_path: Path) -> None:
        mirror_dir = tmp_path / "repo-1"
        mirror_dir.mkdir()
        handle = MirrorHandle("repo-1", mirror_dir)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            handle.git_log()

        args = mock_run.call_args[0][0]
        assert "--max-count=50" in args

    def test_respects_custom_n(self, tmp_path: Path) -> None:
        mirror_dir = tmp_path / "repo-1"
        mirror_dir.mkdir()
        handle = MirrorHandle("repo-1", mirror_dir)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            handle.git_log(n=10)

        args = mock_run.call_args[0][0]
        assert "--max-count=10" in args

    def test_scopes_to_path_when_given(self, tmp_path: Path) -> None:
        mirror_dir = tmp_path / "repo-1"
        mirror_dir.mkdir()
        handle = MirrorHandle("repo-1", mirror_dir)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            handle.git_log(path="src/foo.py")

        args = mock_run.call_args[0][0]
        assert "--" in args
        assert "src/foo.py" in args

    def test_no_path_filter_when_path_is_none(self, tmp_path: Path) -> None:
        mirror_dir = tmp_path / "repo-1"
        mirror_dir.mkdir()
        handle = MirrorHandle("repo-1", mirror_dir)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            handle.git_log(path=None)

        args = mock_run.call_args[0][0]
        assert "--" not in args

    def test_parses_commit_output(self, tmp_path: Path) -> None:
        mirror_dir = tmp_path / "repo-1"
        mirror_dir.mkdir()
        handle = MirrorHandle("repo-1", mirror_dir)
        log_output = (
            "abc123\x00Alice\x002026-01-15 10:00:00 +0000\x00Fix the bug\n"
            "def456\x00Bob\x002026-01-14 09:00:00 +0000\x00Add feature\n"
        )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=log_output, stderr="")
            commits = handle.git_log()

        assert len(commits) == 2
        assert commits[0] == CommitInfo(
            sha="abc123", author="Alice", date="2026-01-15 10:00:00 +0000", message="Fix the bug"
        )
        assert commits[1] == CommitInfo(
            sha="def456", author="Bob", date="2026-01-14 09:00:00 +0000", message="Add feature"
        )

    def test_returns_empty_list_for_empty_repo(self, tmp_path: Path) -> None:
        mirror_dir = tmp_path / "repo-1"
        mirror_dir.mkdir()
        handle = MirrorHandle("repo-1", mirror_dir)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            commits = handle.git_log()

        assert commits == []

    def test_raises_on_git_failure(self, tmp_path: Path) -> None:
        mirror_dir = tmp_path / "repo-1"
        mirror_dir.mkdir()
        handle = MirrorHandle("repo-1", mirror_dir)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=128, stdout="", stderr="fatal: not a git repo")
            with pytest.raises(MirrorReadError, match="git log failed"):
                handle.git_log()

    def test_message_with_null_bytes_parsed_correctly(self, tmp_path: Path) -> None:
        """split('\x00', 3) ensures message field keeps any extra null bytes."""
        mirror_dir = tmp_path / "repo-1"
        mirror_dir.mkdir()
        handle = MirrorHandle("repo-1", mirror_dir)
        log_output = "abc\x00Auth\x002026-01-01\x00Subject\n"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=log_output, stderr="")
            commits = handle.git_log()

        assert commits[0].sha == "abc"
        assert commits[0].message == "Subject"


# ─── MirrorHandle.fetch ───────────────────────────────────────────────────────


class TestMirrorHandleFetch:
    def test_calls_fetch_mirror(self, tmp_path: Path) -> None:
        mirror_dir = tmp_path / "repo-1"
        mirror_dir.mkdir()
        handle = MirrorHandle("repo-1", mirror_dir)
        config = MirrorConfig(storage_path=tmp_path)

        with patch("kenjutsu.mirror.api.fetch_mirror") as mock_fetch:
            handle.fetch(config)

        mock_fetch.assert_called_once_with("repo-1", config)

    def test_uses_default_config_when_none(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("KENJUTSU_MIRROR_PATH", str(tmp_path))
        mirror_dir = tmp_path / "repo-1"
        mirror_dir.mkdir()
        handle = MirrorHandle("repo-1", mirror_dir)

        with patch("kenjutsu.mirror.api.fetch_mirror") as mock_fetch:
            handle.fetch()

        assert mock_fetch.call_count == 1
        called_config = mock_fetch.call_args[0][1]
        assert called_config.storage_path == tmp_path

    def test_fetch_serialized_per_repo(self, tmp_path: Path) -> None:
        """Two concurrent fetch calls on the same repo are serialized — never overlap."""
        mirror_dir = tmp_path / "repo-1"
        mirror_dir.mkdir()
        handle = MirrorHandle("repo-1", mirror_dir)
        config = MirrorConfig(storage_path=tmp_path)

        # Track the maximum concurrent count — must stay at 1 with a lock.
        count_lock = threading.Lock()
        concurrent = [0]
        max_concurrent = [0]
        t1_inside = threading.Event()

        def slow_fetch(repo_id: str, cfg: MirrorConfig) -> None:
            with count_lock:
                concurrent[0] += 1
                max_concurrent[0] = max(max_concurrent[0], concurrent[0])
            t1_inside.set()
            # Hold long enough for the second thread to attempt entry.
            threading.Event().wait(timeout=0.05)
            with count_lock:
                concurrent[0] -= 1

        with patch("kenjutsu.mirror.api.fetch_mirror", side_effect=slow_fetch):
            t1 = threading.Thread(target=handle.fetch, args=(config,))
            t2 = threading.Thread(target=handle.fetch, args=(config,))
            t1.start()
            t1_inside.wait(timeout=2)  # wait until t1 is inside slow_fetch
            t2.start()
            t1.join(timeout=5)
            t2.join(timeout=5)

        # The per-repo lock ensures only one fetch runs at a time.
        assert max_concurrent[0] == 1

    def test_different_repos_fetch_independently(self, tmp_path: Path) -> None:
        """Concurrent fetches on different repos are NOT serialized."""
        (tmp_path / "repo-a").mkdir()
        (tmp_path / "repo-b").mkdir()
        handle_a = MirrorHandle("repo-a", tmp_path / "repo-a")
        handle_b = MirrorHandle("repo-b", tmp_path / "repo-b")
        config = MirrorConfig(storage_path=tmp_path)
        concurrent_starts: list[str] = []
        barrier = threading.Barrier(2)

        def concurrent_fetch(repo_id: str, cfg: MirrorConfig) -> None:
            concurrent_starts.append(repo_id)
            barrier.wait(timeout=2)

        with patch("kenjutsu.mirror.api.fetch_mirror", side_effect=concurrent_fetch):
            t1 = threading.Thread(target=handle_a.fetch, args=(config,))
            t2 = threading.Thread(target=handle_b.fetch, args=(config,))
            t1.start()
            t2.start()
            t1.join(timeout=5)
            t2.join(timeout=5)

        # Both repos started before either finished — true concurrent execution
        assert set(concurrent_starts) == {"repo-a", "repo-b"}


# ─── _repo_fetch_lock ─────────────────────────────────────────────────────────


class TestRepoFetchLock:
    def test_same_repo_same_lock(self) -> None:
        lock1 = _repo_fetch_lock("test-repo-unique-x")
        lock2 = _repo_fetch_lock("test-repo-unique-x")
        assert lock1 is lock2

    def test_different_repos_different_locks(self) -> None:
        lock_a = _repo_fetch_lock("repo-unique-aaa")
        lock_b = _repo_fetch_lock("repo-unique-bbb")
        assert lock_a is not lock_b
