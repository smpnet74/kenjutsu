"""Unit tests for mirror lifecycle state transitions.

Tests use mocked subprocess and controlled filesystem (tmp_path) to verify
behavior without requiring real git operations.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from kenjutsu.mirror.lifecycle import (
    MirrorAlreadyExistsError,
    MirrorCloneError,
    MirrorConfig,
    MirrorFetchError,
    MirrorNotFoundError,
    all_mirror_sizes,
    clone_mirror,
    delete_mirror,
    fetch_mirror,
    mirror_path,
    mirror_size_bytes,
)

# ─── MirrorConfig ────────────────────────────────────────────────────────────


class TestMirrorConfig:
    def test_default_storage_path_is_var_lib(self) -> None:
        config = MirrorConfig()
        assert config.storage_path == Path("/var/lib/kenjutsu/mirrors")

    def test_storage_path_from_env_var(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("KENJUTSU_MIRROR_PATH", str(tmp_path))
        config = MirrorConfig()
        assert config.storage_path == tmp_path

    def test_explicit_storage_path_overrides_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("KENJUTSU_MIRROR_PATH", "/should/be/ignored")
        config = MirrorConfig(storage_path=tmp_path)
        assert config.storage_path == tmp_path

    def test_large_repo_threshold_default_is_1gb(self) -> None:
        config = MirrorConfig()
        assert config.large_repo_threshold_bytes == 1 * 1024**3

    def test_blob_size_limit_default(self) -> None:
        config = MirrorConfig()
        assert config.blob_size_limit == "1m"


# ─── mirror_path ─────────────────────────────────────────────────────────────


class TestMirrorPath:
    def test_returns_storage_path_slash_repo_id(self, tmp_path: Path) -> None:
        config = MirrorConfig(storage_path=tmp_path)
        assert mirror_path(config, "owner-repo") == tmp_path / "owner-repo"

    def test_repo_id_used_verbatim(self, tmp_path: Path) -> None:
        config = MirrorConfig(storage_path=tmp_path)
        assert mirror_path(config, "123456") == tmp_path / "123456"


# ─── clone_mirror ─────────────────────────────────────────────────────────────


class TestCloneMirror:
    def test_runs_bare_clone_command(self, tmp_path: Path) -> None:
        config = MirrorConfig(storage_path=tmp_path)
        expected_dest = tmp_path / "repo-1"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            clone_mirror("https://github.com/org/repo.git", "repo-1", config)

        clone_call = mock_run.call_args_list[0]
        assert clone_call == call(
            ["git", "clone", "--bare", "https://github.com/org/repo.git", str(expected_dest)],
            capture_output=True,
            text=True,
        )

    def test_configures_fetch_refspec_after_clone(self, tmp_path: Path) -> None:
        """After bare clone, remote.origin.fetch must be configured for git fetch to work."""
        config = MirrorConfig(storage_path=tmp_path)
        expected_dest = tmp_path / "repo-1"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            clone_mirror("https://github.com/org/repo.git", "repo-1", config)

        config_call = mock_run.call_args_list[1]
        assert config_call == call(
            ["git", "config", "remote.origin.fetch", "+refs/*:refs/*"],
            capture_output=True,
            text=True,
            cwd=str(expected_dest),
        )

    def test_adds_blob_filter_for_large_repos(self, tmp_path: Path) -> None:
        config = MirrorConfig(storage_path=tmp_path, large_repo_threshold_bytes=500)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            clone_mirror("https://github.com/org/big.git", "big-repo", config, repo_size_bytes=1000)

        clone_args = mock_run.call_args_list[0][0][0]
        assert "--filter=blob:limit=1m" in clone_args

    def test_no_blob_filter_for_small_repos(self, tmp_path: Path) -> None:
        config = MirrorConfig(storage_path=tmp_path, large_repo_threshold_bytes=1 * 1024**3)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            clone_mirror("https://github.com/org/small.git", "small-repo", config, repo_size_bytes=1000)

        clone_args = mock_run.call_args_list[0][0][0]
        assert not any(a.startswith("--filter=") for a in clone_args)

    def test_returns_mirror_path(self, tmp_path: Path) -> None:
        config = MirrorConfig(storage_path=tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            result = clone_mirror("https://github.com/org/repo.git", "repo-1", config)

        assert result == tmp_path / "repo-1"

    def test_raises_if_mirror_already_exists(self, tmp_path: Path) -> None:
        config = MirrorConfig(storage_path=tmp_path)
        (tmp_path / "repo-1").mkdir()

        with pytest.raises(MirrorAlreadyExistsError):
            clone_mirror("https://github.com/org/repo.git", "repo-1", config)

    def test_raises_on_git_failure(self, tmp_path: Path) -> None:
        config = MirrorConfig(storage_path=tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=128, stderr="fatal: repository not found")
            with pytest.raises(MirrorCloneError, match="fatal: repository not found"):
                clone_mirror("https://github.com/org/missing.git", "repo-1", config)

    def test_uses_custom_blob_size_limit(self, tmp_path: Path) -> None:
        config = MirrorConfig(storage_path=tmp_path, large_repo_threshold_bytes=100, blob_size_limit="500k")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            clone_mirror("https://github.com/org/big.git", "repo-x", config, repo_size_bytes=200)

        clone_args = mock_run.call_args_list[0][0][0]
        assert "--filter=blob:limit=500k" in clone_args


# ─── fetch_mirror ─────────────────────────────────────────────────────────────


class TestFetchMirror:
    def test_runs_git_fetch_prune(self, tmp_path: Path) -> None:
        config = MirrorConfig(storage_path=tmp_path)
        mirror_dir = tmp_path / "repo-1"
        mirror_dir.mkdir()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            fetch_mirror("repo-1", config)

        mock_run.assert_called_once_with(
            ["git", "fetch", "--prune"],
            capture_output=True,
            text=True,
            cwd=str(mirror_dir),
        )

    def test_raises_mirror_not_found(self, tmp_path: Path) -> None:
        config = MirrorConfig(storage_path=tmp_path)

        with pytest.raises(MirrorNotFoundError):
            fetch_mirror("nonexistent", config)

    def test_raises_on_git_failure(self, tmp_path: Path) -> None:
        config = MirrorConfig(storage_path=tmp_path)
        (tmp_path / "repo-1").mkdir()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="error: could not fetch")
            with pytest.raises(MirrorFetchError, match="error: could not fetch"):
                fetch_mirror("repo-1", config)


# ─── delete_mirror ────────────────────────────────────────────────────────────


class TestDeleteMirror:
    def test_removes_mirror_directory(self, tmp_path: Path) -> None:
        config = MirrorConfig(storage_path=tmp_path)
        mirror_dir = tmp_path / "repo-1"
        mirror_dir.mkdir()
        (mirror_dir / "HEAD").write_text("ref: refs/heads/main\n")

        delete_mirror("repo-1", config)

        assert not mirror_dir.exists()

    def test_idempotent_when_mirror_not_found(self, tmp_path: Path) -> None:
        config = MirrorConfig(storage_path=tmp_path)
        # Should not raise
        delete_mirror("nonexistent", config)

    def test_removes_nested_contents(self, tmp_path: Path) -> None:
        config = MirrorConfig(storage_path=tmp_path)
        mirror_dir = tmp_path / "repo-1"
        (mirror_dir / "refs" / "heads").mkdir(parents=True)
        (mirror_dir / "refs" / "heads" / "main").write_text("abc123\n")

        delete_mirror("repo-1", config)

        assert not mirror_dir.exists()


# ─── mirror_size_bytes ────────────────────────────────────────────────────────


class TestMirrorSizeBytes:
    def test_returns_total_file_size(self, tmp_path: Path) -> None:
        config = MirrorConfig(storage_path=tmp_path)
        mirror_dir = tmp_path / "repo-1"
        mirror_dir.mkdir()
        (mirror_dir / "HEAD").write_bytes(b"x" * 100)
        (mirror_dir / "config").write_bytes(b"y" * 200)

        assert mirror_size_bytes("repo-1", config) == 300

    def test_counts_nested_files(self, tmp_path: Path) -> None:
        config = MirrorConfig(storage_path=tmp_path)
        mirror_dir = tmp_path / "repo-1"
        (mirror_dir / "objects" / "pack").mkdir(parents=True)
        (mirror_dir / "objects" / "pack" / "pack.idx").write_bytes(b"z" * 1024)

        assert mirror_size_bytes("repo-1", config) == 1024

    def test_raises_mirror_not_found(self, tmp_path: Path) -> None:
        config = MirrorConfig(storage_path=tmp_path)

        with pytest.raises(MirrorNotFoundError):
            mirror_size_bytes("nonexistent", config)


# ─── all_mirror_sizes ─────────────────────────────────────────────────────────


class TestAllMirrorSizes:
    def test_returns_mapping_of_repo_id_to_size(self, tmp_path: Path) -> None:
        config = MirrorConfig(storage_path=tmp_path)
        (tmp_path / "repo-a").mkdir()
        (tmp_path / "repo-a" / "HEAD").write_bytes(b"x" * 50)
        (tmp_path / "repo-b").mkdir()
        (tmp_path / "repo-b" / "HEAD").write_bytes(b"y" * 80)

        sizes = all_mirror_sizes(config)

        assert sizes == {"repo-a": 50, "repo-b": 80}

    def test_returns_empty_dict_when_storage_path_absent(self, tmp_path: Path) -> None:
        config = MirrorConfig(storage_path=tmp_path / "nonexistent")

        assert all_mirror_sizes(config) == {}

    def test_ignores_files_in_storage_root(self, tmp_path: Path) -> None:
        config = MirrorConfig(storage_path=tmp_path)
        (tmp_path / "stray-file.txt").write_text("ignored")
        (tmp_path / "repo-a").mkdir()
        (tmp_path / "repo-a" / "HEAD").write_bytes(b"x" * 10)

        sizes = all_mirror_sizes(config)

        assert set(sizes.keys()) == {"repo-a"}
