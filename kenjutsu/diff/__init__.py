"""Diff processing — parsing, AST extension, token budgeting.

Public surface
--------------
kenjutsu.diff.models      — PatchFile, Hunk, HunkLine, ChangeType, ScopeContext
kenjutsu.diff.parser      — parse_diff
kenjutsu.diff.ast_context — extend_hunks_with_ast, find_enclosing_scope
kenjutsu.diff.budget      — fit_to_budget, split_into_passes, count_tokens, input_token_budget
"""

from kenjutsu.diff.ast_context import extend_hunks_with_ast, find_enclosing_scope
from kenjutsu.diff.budget import count_tokens, fit_to_budget, input_token_budget, split_into_passes
from kenjutsu.diff.models import ChangeType, Hunk, HunkLine, PatchFile, ScopeContext
from kenjutsu.diff.parser import parse_diff

__all__ = [
    "ChangeType",
    "Hunk",
    "HunkLine",
    "PatchFile",
    "ScopeContext",
    "count_tokens",
    "extend_hunks_with_ast",
    "find_enclosing_scope",
    "fit_to_budget",
    "input_token_budget",
    "parse_diff",
    "split_into_passes",
]
