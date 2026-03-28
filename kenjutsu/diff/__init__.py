"""Unified diff parsing — structured PatchFile objects from raw diff text."""

from kenjutsu.diff.models import ChangeType, Hunk, HunkLine, PatchFile
from kenjutsu.diff.parser import parse_diff

__all__ = [
    "ChangeType",
    "Hunk",
    "HunkLine",
    "PatchFile",
    "parse_diff",
]
