"""Diff processing — parsing, AST extension, token budgeting.

Public surface
--------------
kenjutsu.diff.models      — PatchFile, Hunk, HunkLine, ChangeType, ScopeContext
kenjutsu.diff.parser      — parse_diff
kenjutsu.diff.ast_context — extend_hunks_with_ast, find_enclosing_scope
"""

from kenjutsu.diff.ast_context import extend_hunks_with_ast, find_enclosing_scope
from kenjutsu.diff.models import ChangeType, Hunk, HunkLine, PatchFile, ScopeContext
from kenjutsu.diff.parser import parse_diff

__all__ = [
    "ChangeType",
    "Hunk",
    "HunkLine",
    "PatchFile",
    "ScopeContext",
    "extend_hunks_with_ast",
    "find_enclosing_scope",
    "parse_diff",
]
