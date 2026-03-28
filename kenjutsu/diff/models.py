"""Data models for parsed unified diffs.

Decoupled hunk format: every HunkLine carries independent old/new line numbers
so callers can reconstruct either the old-file or new-file view without
re-parsing the hunk.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ChangeType(StrEnum):
    ADD = "add"
    DELETE = "delete"
    CONTEXT = "context"


@dataclass
class HunkLine:
    """A single line in a hunk with its independent old/new line numbers."""

    change_type: ChangeType
    content: str
    old_lineno: int | None  # None for additions
    new_lineno: int | None  # None for deletions


@dataclass
class Hunk:
    """A contiguous block of changes extracted from a unified diff."""

    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: list[HunkLine]
    section_header: str = ""

    @property
    def is_deletion_only(self) -> bool:
        """True when this hunk contains no ADD lines (only DELETEs and CONTEXT)."""
        return not any(ln.change_type == ChangeType.ADD for ln in self.lines)


@dataclass
class PatchFile:
    """A single file's worth of changes from a unified diff."""

    old_path: str | None  # None when file is new (/dev/null source)
    new_path: str | None  # None when file is deleted (/dev/null target)
    hunks: list[Hunk]
    is_binary: bool = False

    @property
    def is_new_file(self) -> bool:
        return self.old_path is None and self.new_path is not None

    @property
    def is_deleted_file(self) -> bool:
        return self.old_path is not None and self.new_path is None

    @property
    def is_rename(self) -> bool:
        return self.old_path is not None and self.new_path is not None and self.old_path != self.new_path

    @property
    def additions(self) -> int:
        return sum(1 for hunk in self.hunks for line in hunk.lines if line.change_type == ChangeType.ADD)

    @property
    def deletions(self) -> int:
        return sum(1 for hunk in self.hunks for line in hunk.lines if line.change_type == ChangeType.DELETE)
