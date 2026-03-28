"""Data models for parsed unified diffs.

Decoupled hunk format: every HunkLine carries independent old/new line numbers
so callers can reconstruct either the old-file or new-file view without
re-parsing the hunk.

ScopeContext is populated by the AST context extension (1.4b) and consumed
by the token budget manager (1.4c).
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
class ScopeContext:
    """Enclosing function or class scope found by tree-sitter."""

    kind: str
    """Node kind: 'function', 'class', 'method', or 'block'."""

    name: str
    """Identifier of the enclosing scope (function or class name)."""

    signature: str
    """Full declaration line(s), e.g. 'def foo(x: int) -> str:'."""

    start_line: int
    """1-based line number where the scope begins."""

    end_line: int
    """1-based line number where the scope ends (inclusive)."""

    language: str
    """The language that produced this context, e.g. 'python'."""


@dataclass
class Hunk:
    """A contiguous block of changes extracted from a unified diff."""

    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: list[HunkLine]
    section_header: str = ""
    enclosing_scope: ScopeContext | None = None
    """Populated by the AST context extension (1.4b).  None when
    tree-sitter is unavailable for the language or when the hunk is
    at module top-level with no enclosing function or class."""

    @property
    def is_deletion_only(self) -> bool:
        """True when this hunk contains no ADD lines (only DELETEs and CONTEXT)."""
        return not any(ln.change_type == ChangeType.ADD for ln in self.lines)

    @property
    def new_line_range(self) -> tuple[int, int]:
        """Inclusive [start, end] in the new file."""
        end = self.new_start + max(self.new_count - 1, 0)
        return (self.new_start, end)


@dataclass
class PatchFile:
    """A single file's worth of changes from a unified diff."""

    old_path: str | None  # None when file is new (/dev/null source)
    new_path: str | None  # None when file is deleted (/dev/null target)
    hunks: list[Hunk]
    is_binary: bool = False

    @property
    def path(self) -> str:
        """Canonical path: new_path when available, otherwise old_path."""
        return self.new_path or self.old_path or ""

    @property
    def is_new_file(self) -> bool:
        return self.old_path is None and self.new_path is not None

    @property
    def is_deleted_file(self) -> bool:
        return self.old_path is not None and self.new_path is None

    @property
    def is_deletion(self) -> bool:
        """Alias for is_deleted_file — used by the AST context extension."""
        return self.is_deleted_file

    @property
    def is_rename(self) -> bool:
        return self.old_path is not None and self.new_path is not None and self.old_path != self.new_path

    @property
    def additions(self) -> int:
        return sum(1 for hunk in self.hunks for line in hunk.lines if line.change_type == ChangeType.ADD)

    @property
    def deletions(self) -> int:
        return sum(1 for hunk in self.hunks for line in hunk.lines if line.change_type == ChangeType.DELETE)
