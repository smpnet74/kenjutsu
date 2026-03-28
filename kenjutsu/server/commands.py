"""Slash command parser for Kenjutsu PR comment commands.

Parses /kenjutsu commands from GitHub PR comment bodies.

Supported commands:
    /kenjutsu review            — trigger a full PR review
    /kenjutsu review <file>     — trigger a scoped review for one file
    /kenjutsu ignore            — suppress the finding at cursor position
"""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel

# Matches /kenjutsu only when it appears at the start of a line (after optional
# leading whitespace), capturing everything after the prefix on that same line.
_COMMAND_RE = re.compile(r"^[ \t]*/kenjutsu([ \t]+\S.*|[ \t]*$)", re.MULTILINE)


class CommandKind(StrEnum):
    REVIEW = "review"
    IGNORE = "ignore"


class ParsedCommand(BaseModel):
    kind: CommandKind
    file_path: str | None = None


class ParseError(Exception):
    """Raised when a /kenjutsu command is present but cannot be parsed."""


def parse_command(comment_body: str) -> ParsedCommand | None:
    """Parse a Kenjutsu slash command from a PR comment body.

    Returns:
        ParsedCommand if a /kenjutsu command is found and valid.
        None if no /kenjutsu command is present anywhere in the comment.

    Raises:
        ParseError: A /kenjutsu command was found but is malformed or unknown.
    """
    match = _COMMAND_RE.search(comment_body)
    if match is None:
        return None

    rest = match.group(1).strip()  # everything after "/kenjutsu" on that line
    tokens = rest.split() if rest else []

    if not tokens:
        raise ParseError(
            "missing subcommand — expected one of: review, ignore\nUsage: /kenjutsu review [<file>] | /kenjutsu ignore"
        )

    subcommand = tokens[0]
    args = tokens[1:]

    if subcommand == "review":
        if len(args) > 1:
            raise ParseError(f"too many arguments for 'review' — expected at most one file path, got {len(args)}")
        return ParsedCommand(kind=CommandKind.REVIEW, file_path=args[0] if args else None)

    if subcommand == "ignore":
        if args:
            raise ParseError(f"too many arguments for 'ignore' — expected no arguments, got {len(args)}")
        return ParsedCommand(kind=CommandKind.IGNORE)

    raise ParseError(f"unknown command '{subcommand}' — supported commands: review, ignore")
